"""Lighting and photographic-style fragments assembled without model calls."""

import json
from pathlib import Path

from comfy_api.latest import io


PRESETS = json.loads((Path(__file__).parent / "web" / "photo_presets.json").read_text())
DEFAULT_LIGHTING = "Soft window light"
DEFAULT_STYLE = "Natural photography"
DEFAULT_SKIN = "Natural texture"


def join_fragments(*parts):
    """Keep user text intact apart from outer whitespace and skip empty sections."""
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def preset_text(group, selection):
    try:
        return PRESETS[group][selection]
    except KeyError:
        raise ValueError(f"Unknown {group} preset: {selection}") from None


def assemble_prompt(base_prompt="", lighting=DEFAULT_LIGHTING, style=DEFAULT_STYLE,
                    skin_texture=DEFAULT_SKIN, custom_lighting="", custom_style=""):
    lighting_text = join_fragments(preset_text("lighting", lighting), custom_lighting)
    style_text = join_fragments(preset_text("style", style),
                                preset_text("skin_texture", skin_texture), custom_style)
    return join_fragments(base_prompt, lighting_text, style_text), lighting_text, style_text


class LightingStylePromptAssembler(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="LightingStylePromptAssembler",
            display_name="Prompt Assembler (Lighting + Style)",
            category="utilities/prompt",
            search_aliases=["lighting", "photographic style", "skin texture", "prompt builder"],
            description=(
                "Append lighting, photographic style, and skin-texture descriptions to a prompt. "
                "Choose None to omit a section. Creates text only; it does not call a language model "
                "or change your model, LoRAs, sampler, or image."
            ),
            inputs=[
                io.String.Input("base_prompt", default="", multiline=True,
                                tooltip="Your existing subject and scene prompt. Can also be connected from another text node."),
                io.Combo.Input("lighting", options=list(PRESETS["lighting"]), default=DEFAULT_LIGHTING),
                io.Combo.Input("style", options=list(PRESETS["style"]), default=DEFAULT_STYLE),
                io.Combo.Input("skin_texture", options=list(PRESETS["skin_texture"]), default=DEFAULT_SKIN,
                               tooltip="A style detail independent of the style preset. Close-up detail is intended for close portraits; None omits skin instructions."),
                io.String.Input("custom_lighting", default="", multiline=True, advanced=True,
                                tooltip="Extra lighting text appended to the lighting preset. For custom text only, set lighting to None."),
                io.String.Input("custom_style", default="", multiline=True, advanced=True,
                                tooltip="Extra style text appended after style and skin texture. Select None for both to use custom style text only."),
                io.String.Input("preview", default="", multiline=True, advanced=True,
                                tooltip="Read-only assembled prompt. Linked values are resolved after execution."),
            ],
            outputs=[
                io.String.Output("prompt", tooltip="Full prompt: your text, then lighting, then style and skin texture."),
                io.String.Output("lighting", tooltip="Lighting preset plus custom lighting text."),
                io.String.Output("style", tooltip="Photographic style, skin texture, and custom style text."),
            ],
        )

    @classmethod
    def execute(cls, base_prompt="", lighting=DEFAULT_LIGHTING, style=DEFAULT_STYLE,
                skin_texture=DEFAULT_SKIN, custom_lighting="", custom_style="", preview=None):
        result = assemble_prompt(base_prompt, lighting, style, skin_texture,
                                 custom_lighting, custom_style)
        return io.NodeOutput(*result, ui={"assembled_prompt": [result[0]]})
