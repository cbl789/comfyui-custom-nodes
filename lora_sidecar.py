"""LoRA loader that reads the model's v2 sidecar and can insert its trigger words."""

import os

import comfy.sd
import comfy.utils
import folder_paths
from comfy_api.latest import io

from .sidecar_meta import (
    MODES, compose_prompt, load_sidecar, strength_values, summary, trigger_texts,
)


_cached_lora = {}


def _load_lora(lora_path):
    """Load the LoRA weights, reusing the previous file while it is unchanged."""
    stat = os.stat(lora_path)
    key = (lora_path, stat.st_mtime_ns, stat.st_size)
    cached = _cached_lora.get("entry")
    if cached and cached[0] == key:
        return cached[1], cached[2]
    lora, metadata = comfy.utils.load_torch_file(
        lora_path, safe_load=True, return_metadata=True,
    )
    _cached_lora["entry"] = (key, lora, metadata)
    return lora, metadata


class LoraSidecarLoader(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        # The lora list is resolved when the node definition is built, like ComfyUI's own loaders.
        loras = folder_paths.get_filename_list("loras") or [""]
        return io.Schema(
            node_id="LoraSidecarLoader",
            display_name="LoRA Loader (Sidecar)",
            category="loaders",
            search_aliases=["lora", "lora loader", "trigger words", "sidecar", "metadata"],
            description=(
                "The built-in LoRA loader plus the model's sidecar metadata. Show only applies the "
                "LoRA and reports its trigger words without touching the prompt. Append triggers "
                "adds the sidecar's trigger words to the prompt. The preview is read-only and "
                "filled after the run; it does not change the prompt."
            ),
            inputs=[
                io.Model.Input("model", tooltip="The diffusion model the LoRA will be applied to."),
                io.Clip.Input("clip", tooltip="The CLIP model the LoRA will be applied to."),
                io.Combo.Input("lora_name", options=loras,
                               tooltip="LoRA file. Its sidecar is read from the same folder, named "
                                       "after the full filename plus .json."),
                io.Combo.Input("mode", options=MODES, default=MODES[0],
                               tooltip="Show only: the prompt passes through unchanged. "
                                       "Append triggers: the trigger words are added to the prompt."),
                io.String.Input("prompt", default="", multiline=True,
                                tooltip="The positive prompt. Left unchanged in Show only mode."),
                io.Float.Input("strength_model", default=1.0, min=-100.0, max=100.0, step=0.01,
                               tooltip="How strongly to modify the diffusion model."),
                io.Float.Input("strength_clip", default=1.0, min=-100.0, max=100.0, step=0.01,
                               tooltip="How strongly to modify the CLIP model."),
                io.Boolean.Input("use_sidecar_strength", default=False, advanced=True,
                                 tooltip="Use the sidecar's creator-recommended model and clip strengths "
                                         "instead of the values above, where the sidecar records them."),
                io.String.Input("preview", default="", multiline=True, advanced=True,
                                tooltip="Read-only sidecar summary, filled after the run."),
            ],
            outputs=[
                io.Model.Output("model", tooltip="The modified diffusion model."),
                io.Clip.Output("clip", tooltip="The modified CLIP model."),
                io.String.Output("prompt", tooltip="The prompt: unchanged in Show only mode, "
                                                  "with trigger words in Append triggers mode."),
                io.String.Output("triggers", tooltip="Trigger words from the sidecar; empty when it lists none."),
            ],
        )

    @classmethod
    def execute(cls, model, clip, lora_name, mode=MODES[0], prompt="", strength_model=1.0,
                strength_clip=1.0, use_sidecar_strength=False, preview=None):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")

        lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
        metadata = load_sidecar(lora_path)
        triggers = trigger_texts(metadata)

        if use_sidecar_strength:
            sidecar_model, sidecar_clip = strength_values(metadata)
            if sidecar_model is not None:
                strength_model = sidecar_model
            if sidecar_clip is not None:
                strength_clip = sidecar_clip

        if strength_model == 0 and strength_clip == 0:
            model_lora, clip_lora = model, clip
        else:
            lora, lora_metadata = _load_lora(lora_path)
            model_lora, clip_lora = comfy.sd.load_lora_for_models(
                model, clip, lora, strength_model, strength_clip, lora_metadata=lora_metadata,
            )

        text = compose_prompt(prompt, triggers, mode)
        ui = {"lora_sidecar": [summary(metadata, lora_name)]}
        return io.NodeOutput(model_lora, clip_lora, text, ", ".join(triggers), ui=ui)
