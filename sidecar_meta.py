"""Read v2 model sidecars beside a LoRA file, without importing ComfyUI.

The canonical format lives with the ComfyUI install; see
`~/ai/comfyui/tools/model-sidecars` on the host (schema, README, validator).
Only the fields this pack needs are read, and anything missing is treated as
absent rather than guessed.
"""

import json
from pathlib import Path


MODES = ["Show only", "Append triggers"]
SEPARATOR = ", "


def sidecar_path(model_path):
    """The sidecar for a model file: its full filename plus .json, in the same folder."""
    return Path(str(model_path) + ".json")


def load_sidecar(model_path):
    """Return the parsed sidecar, or None when it is missing or malformed."""
    try:
        data = json.loads(sidecar_path(model_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def trigger_texts(metadata):
    """Explicit trigger words from usage.triggers, in sidecar order."""
    triggers = ((metadata or {}).get("usage") or {}).get("triggers") or []
    texts = []
    for item in triggers:
        text = item.get("text") if isinstance(item, dict) else None
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    return texts


def strength_values(metadata):
    """Creator-recommended (model, clip) strengths; None where the sidecar is silent."""
    strength = ((metadata or {}).get("usage") or {}).get("strength") or {}
    model = strength.get("model")
    clip = strength.get("clip")
    return (model if isinstance(model, (int, float)) and not isinstance(model, bool) else None,
            clip if isinstance(clip, (int, float)) and not isinstance(clip, bool) else None)


def compose_prompt(prompt, triggers, mode):
    """Return the prompt unchanged in Show only mode, else the prompt plus trigger words."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode: {mode}")
    text = prompt or ""
    if mode == "Show only" or not triggers:
        return text
    trigger_text = SEPARATOR.join(triggers)
    if not text.strip():
        return trigger_text
    return text.rstrip() + SEPARATOR + trigger_text


def response(lora_name, model_path):
    """Payload for the preview widget, also served to the frontend before a run."""
    metadata = load_sidecar(model_path)
    return {
        "name": lora_name,
        "found": metadata is not None,
        "summary": summary(metadata, lora_name),
        "triggers": trigger_texts(metadata),
    }


def summary(metadata, lora_name):
    """Read-only human summary shown in the node's preview widget."""
    lines = [f"LoRA: {lora_name}"]
    if not metadata:
        lines.append("Sidecar: none")
        lines.append("Expected: the LoRA filename plus .json, beside the file.")
        return "\n".join(lines)

    asset = metadata.get("asset") or {}
    compatibility = metadata.get("compatibility") or {}
    usage = metadata.get("usage") or {}
    strength = usage.get("strength") or {}

    if asset.get("name"):
        lines.append(f"Name: {asset['name']}")
    if compatibility.get("base_model"):
        lines.append(f"Base: {compatibility['base_model']}")

    triggers = trigger_texts(metadata)
    lines.append("Triggers: " + (SEPARATOR.join(triggers) if triggers else "none"))

    parts = []
    if strength.get("model") is not None:
        parts.append(f"model {strength['model']}")
    if strength.get("clip") is not None:
        parts.append(f"clip {strength['clip']}")
    if strength.get("min") is not None and strength.get("max") is not None:
        parts.append(f"range {strength['min']}-{strength['max']}")
    if parts:
        lines.append("Strength: " + ", ".join(parts))

    sources = metadata.get("sources") or []
    url = next((item.get("url") for item in sources
                if isinstance(item, dict) and item.get("url")), None)
    if url:
        lines.append(f"Source: {url}")

    notes = metadata.get("notes")
    if isinstance(notes, str) and notes.strip():
        flat = " ".join(notes.split())
        lines.append("Notes: " + (flat[:240] + "..." if len(flat) > 240 else flat))

    lines.append(f"Sidecar: v{metadata.get('schema_version', '?')}")
    return "\n".join(lines)
