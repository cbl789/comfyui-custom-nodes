"""Krea 2 prompt writer: a local language model writes or revises a prompt following the krea2-prompting skill."""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from comfy_api.latest import io


PACK_DIR = Path(__file__).parent
INSTRUCTIONS_FILE = PACK_DIR / "krea2_writer_instructions.md"
DEFAULT_SKILL_DIR = PACK_DIR / "skills" / "krea2-prompting"
DEFAULT_ENDPOINT = "http://192.168.50.159:8000/v1"
DEFAULT_MODEL = "Qwen3.6-35B-A3B-Uncensored-Heretic-MLX-4bit"

MODES = ["Write new prompt", "Apply change", "Keep current prompt"]
REFERENCES = ["Auto", "Photoreal", "Photoreal + Adult"]
ASPECTS = [
    "1:1 (Square)", "2:3 (Portrait Photo)", "3:2 (Photo)", "3:4 (Portrait Standard)",
    "4:3 (Standard)", "9:16 (Portrait Widescreen)", "16:9 (Widescreen)", "21:9 (Ultrawide)",
]
AUTO_ASPECT = "Auto (from prompt writer)"
FALLBACK_ASPECT = "3:2 (Photo)"
# Words that make Auto add the adult reference. Matching is on whole words, case-insensitive.
# Boudoir and lingerie are left out on purpose: with the adult reference the model escalates them to nudity.
ADULT_WORDS = re.compile(
    r"\b(nude|naked|topless|nsfw|explicit|erotic|sex|sexual|porn\w*|"
    r"masturbat\w*|orgasm\w*|nipples?|breasts?|genitals?|vulva|penis|pussy|cock)\b",
    re.IGNORECASE,
)


def choose_references(selection, *texts):
    """Reference files to send with the skill for this request."""
    if selection == "Photoreal + Adult":
        return ["photoreal.md", "adult.md"]
    if selection == "Photoreal":
        return ["photoreal.md"]
    if selection != "Auto":
        raise ValueError(f"Unknown references option: {selection}")
    if any(ADULT_WORDS.search(text or "") for text in texts):
        return ["photoreal.md", "adult.md"]
    return ["photoreal.md"]


def build_system_prompt(skill_dir, references):
    skill_dir = Path(skill_dir)
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(
            f"krea2-prompting skill not found at {skill_dir}. Copy the skill folder there "
            "(see the README, section Krea 2 Prompt Writer)."
        )
    parts = [INSTRUCTIONS_FILE.read_text(), "# Skill: krea2-prompting\n\n" + skill_file.read_text()]
    for name in references:
        path = skill_dir / "references" / name
        if not path.is_file():
            raise ValueError(f"Reference file missing: {path}")
        parts.append(f"# Reference: references/{name}\n\n" + path.read_text())
    return "\n\n".join(parts)


def build_user_message(mode, brief, change, current_prompt, current_aspect):
    if mode == "Write new prompt":
        if not brief.strip():
            raise ValueError("Write a brief first: describe the image you want.")
        return f"Brief:\n{brief.strip()}"
    if mode == "Apply change":
        if not current_prompt.strip():
            raise ValueError("There is no current prompt to change yet. Use 'Write new prompt' first.")
        if not change.strip():
            raise ValueError("Describe the change first, in the change field.")
        return (
            f"Current prompt:\n{current_prompt.strip()}\n\n"
            f"Current aspect ratio: {current_aspect or FALLBACK_ASPECT}\n\n"
            f"Change to apply:\n{change.strip()}"
        )
    raise ValueError(f"Mode does not use the language model: {mode}")


def parse_reply(text):
    """Return (prompt, aspect) from a 'PROMPT: ... ASPECT_RATIO: ...' reply."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    match = re.search(r"PROMPT:\s*(.*?)\s*(?:ASPECT_RATIO:\s*(.*))?$", text, re.S)
    if not match or not match.group(1).strip():
        raise ValueError(f"The language model did not return a prompt. Reply started with: {text[:200]!r}")
    prompt = match.group(1).strip()
    aspect_text = (match.group(2) or "").strip().splitlines()
    aspect = None
    if aspect_text:
        first = aspect_text[0].strip().strip("`")
        aspect = next((a for a in ASPECTS if first in (a, a.split(" ")[0])), None)
    return prompt, aspect


def call_model(endpoint, model, api_key, system, user, timeout):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.7,
        # Qwen3.6 thinks for up to ~3,000 tokens before it writes; 4,096 left some replies empty.
        "max_tokens": 12288,
    }
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key or 'none'}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise ValueError(f"Language model server answered {error.code}: {error.read().decode(errors='replace')[:300]}") from None
    except OSError as error:
        raise ValueError(f"Language model server not reachable at {endpoint}: {error}") from None
    choice = data["choices"][0]
    content = choice["message"].get("content") or ""
    if not content.strip() and choice.get("finish_reason") == "length":
        raise ValueError("The language model used its whole token budget for thinking and wrote no prompt. Run again.")
    return content


def resolve_aspect(selected, written, current):
    if selected != AUTO_ASPECT:
        return selected
    return written or current or FALLBACK_ASPECT


def dimensions(aspect, megapixels, multiple):
    from comfy_extras.nodes_resolution import ResolutionSelector
    return ResolutionSelector.execute(aspect_ratio=aspect, megapixels=megapixels,
                                      multiple=multiple, preview=None).result


class Krea2PromptWriter(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Krea2PromptWriter",
            display_name="Krea 2 Prompt Writer",
            category="utilities/prompt",
            search_aliases=["krea", "krea2", "prompt writer", "llm prompt", "prompt enhancer"],
            description=(
                "A local language model writes a Krea 2 Turbo prompt from your brief, following the "
                "krea2-prompting skill. Write new prompt: writes from the brief. Apply change: revises the "
                "current prompt with only the change you describe. Keep current prompt: no model call. "
                "After each run the prompt appears in current_prompt (editable) and the mode switches to "
                "Keep current prompt, so re-running renders the same prompt."
            ),
            inputs=[
                io.Combo.Input("mode", options=MODES, default=MODES[0],
                               tooltip="Write new prompt from the brief, apply the change to the current prompt, "
                                       "or keep the current prompt without calling the model."),
                io.String.Input("brief", default="", multiline=True,
                                tooltip="Describe the image you want in your own words."),
                io.String.Input("change", default="", multiline=True,
                                tooltip="For Apply change: what to change, e.g. 'make her hair red, camera lower'. "
                                        "Cleared after it is applied."),
                io.String.Input("current_prompt", default="", multiline=True,
                                tooltip="The prompt that goes to the image. Filled after each run; you can edit it by hand."),
                io.Combo.Input("aspect_ratio", options=[AUTO_ASPECT] + ASPECTS, default=AUTO_ASPECT,
                               tooltip="Auto uses the ratio the prompt writer picks for the brief."),
                io.Float.Input("megapixels", default=2.0, min=0.1, max=16.0, step=0.1,
                               tooltip="Image size for the width and height outputs."),
                io.Combo.Input("references", options=REFERENCES, default=REFERENCES[0], advanced=True,
                               tooltip="Reference files sent with the skill. Auto adds the adult reference when the "
                                       "brief or change mentions nudity or sex."),
                io.String.Input("current_aspect", default="", advanced=True,
                                tooltip="Aspect ratio of the current prompt, filled after each run."),
                io.Int.Input("multiple", default=16, min=8, max=64, step=8, advanced=True,
                             tooltip="Rounding for width and height. Krea 2 needs 16."),
                io.String.Input("endpoint", default=DEFAULT_ENDPOINT, advanced=True,
                                tooltip="OpenAI-compatible server, reachable from the ComfyUI server."),
                io.String.Input("model", default=DEFAULT_MODEL, advanced=True),
                io.String.Input("api_key", default="", advanced=True,
                                tooltip="Only if the server requires one."),
                io.String.Input("skill_dir", default=str(DEFAULT_SKILL_DIR), advanced=True,
                                tooltip="Folder with the krea2-prompting skill (SKILL.md and references/)."),
                io.Int.Input("timeout", default=180, min=10, max=1200, advanced=True,
                             tooltip="Seconds to wait for the language model."),
            ],
            outputs=[
                io.String.Output("prompt", tooltip="Connect to the positive text encoder."),
                io.Int.Output("width"),
                io.Int.Output("height"),
                io.String.Output("aspect_ratio_used"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, mode="", **kwargs):
        # Model modes run every time (new variant, current skill files); Keep is cached on its inputs.
        return float("nan") if mode in MODES[:2] else mode

    @classmethod
    def execute(cls, mode, brief, change, current_prompt, aspect_ratio, megapixels,
                references="Auto", current_aspect="", multiple=16, endpoint=DEFAULT_ENDPOINT,
                model=DEFAULT_MODEL, api_key="", skill_dir=str(DEFAULT_SKILL_DIR), timeout=180):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        written_aspect = None
        if mode == "Keep current prompt":
            if not current_prompt.strip():
                raise ValueError("current_prompt is empty. Use 'Write new prompt' first, or type a prompt.")
            prompt = current_prompt.strip()
        else:
            user = build_user_message(mode, brief, change, current_prompt, current_aspect)
            refs = choose_references(references, brief, change, current_prompt if mode == "Apply change" else "")
            system = build_system_prompt(skill_dir, refs)
            reply = call_model(endpoint, model, api_key, system, user, timeout)
            prompt, written_aspect = parse_reply(reply)
        aspect = resolve_aspect(aspect_ratio, written_aspect, current_aspect if current_aspect in ASPECTS else None)
        width, height = dimensions(aspect, megapixels, multiple)
        ui = {"krea2_writer": [{"prompt": prompt, "aspect": aspect, "mode": mode}]}
        return io.NodeOutput(prompt, width, height, aspect, ui=ui)
