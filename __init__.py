"""Custom ComfyUI nodes for resolution selection, photographic prompts and Krea 2 prompt writing."""

import math

from comfy_api.latest import ComfyExtension, io
from comfy_extras.nodes_resolution import ResolutionSelector
from .prompt_assembler import LightingStylePromptAssembler
from .krea2_prompt_writer import Krea2PromptWriter

WEB_DIRECTORY = "./web"

# Existing option strings remain valid so saved workflows continue to load.
FORMATS = [
    "Flux 2 / Klein (128 channels)",
    "Flux 3 (128 channels)",
    "Qwen Image 2.1 (64 channels)",
    "Krea 2 (16 channels, single frame)",
    "Qwen Image (16 channels, single frame)",
    "Z-Image / HiDream (16 channels)",
    "Hunyuan Image 2.1 (64 channels)",
    "HiDream-O1 (pixel space)",
    "SD / SDXL (4 channels)",
    "SD3 / Flux (16 channels)",
]

# Generator family, minimum spatial alignment. Image presets only: a single
# frame is explicit for models whose latent representation has a time axis.
LATENT_FORMATS = {
    "Flux 2 / Klein (128 channels)": ("flux2", 16),
    "Flux 3 (128 channels)": ("flux2", 16),
    "Qwen Image 2.1 (64 channels)": ("qwen21", 16),
    "Krea 2 (16 channels, single frame)": ("single_frame", 16),
    "Qwen Image (16 channels, single frame)": ("single_frame", 16),
    "Z-Image / HiDream (16 channels)": ("sd3", 16),
    "Hunyuan Image 2.1 (64 channels)": ("hunyuan_image", 32),
    "HiDream-O1 (pixel space)": ("hidream_o1", 32),
    "SD / SDXL (4 channels)": ("sd", 8),
    "SD3 / Flux (16 channels)": ("sd3", 8),
}


class ResolutionSelectorLatent(ResolutionSelector):
    @classmethod
    def define_schema(cls):
        schema = ResolutionSelector.define_schema()
        schema.node_id = "ResolutionSelectorWithLatent"
        schema.display_name = "Resolution Selector + Latent"
        # Keep the preview's name and position so existing workflow widgets map correctly.
        # The frontend extension handles reference mode without displaying the dropdown ratio.
        schema.inputs = [
            io.String.Input("preview", default="", multiline=False,
                            tooltip="Calculated dimensions. Reference-image dimensions update after execution.")
            if item.id == "preview" else item
            for item in schema.inputs
        ]
        # A 32-pixel increment is compatible with every image preset below.
        # Existing workflows retain their serialized multiple value.
        next(item for item in schema.inputs if item.id == "multiple").default = 32
        schema.description = (
            "The built-in Resolution Selector with an optional empty image latent. "
            "An optional reference image overrides the aspect ratio, not the megapixel target. "
            "Choose the latent format required by your model. Disable generate_latent "
            "to use only width and height without allocating a tensor."
        )
        schema.inputs.extend([
            io.Boolean.Input("generate_latent", default=True,
                             tooltip="Create an empty latent. When off, latent returns None."),
            io.Combo.Input("latent_format", options=FORMATS, default=FORMATS[0],
                           tooltip="Choose the image model family. Current and legacy presets are supported; "
                           "single-frame presets produce image latents, not video sequences."),
            io.Int.Input("batch_size", default=1, min=1, max=4096, advanced=True),
            io.Image.Input("reference_image", optional=True,
                           tooltip="Use this image's proportions instead of the aspect-ratio dropdown. "
                           "Only its dimensions are read; its content is not encoded."),
        ])
        schema.outputs.append(io.Latent.Output("latent"))
        return schema

    @classmethod
    def execute(cls, aspect_ratio, megapixels, multiple, generate_latent=True,
                latent_format=FORMATS[0], batch_size=1, preview=None, reference_image=None):
        reference_width = reference_height = None
        if reference_image is None:
            width, height = ResolutionSelector.execute(
                aspect_ratio=aspect_ratio, megapixels=megapixels,
                multiple=multiple, preview=preview,
            ).result
        else:
            shape = reference_image.shape
            if len(shape) != 4 or any(size <= 0 for size in shape):
                raise ValueError("reference_image must be a non-empty IMAGE batch (B, H, W, C).")
            reference_height, reference_width = int(shape[1]), int(shape[2])
            if not math.isfinite(megapixels) or megapixels <= 0 or multiple <= 0:
                raise ValueError("megapixels and multiple must be positive finite values.")
            scale = math.sqrt(megapixels * 1024 * 1024 / (reference_width * reference_height))
            width = round(reference_width * scale / multiple) * multiple
            height = round(reference_height * scale / multiple) * multiple
            if width <= 0 or height <= 0:
                raise ValueError("Reference aspect ratio is too extreme for the selected megapixels and multiple.")
        ui = {"resolution": [{
            "width": width, "height": height,
            "reference_width": reference_width, "reference_height": reference_height,
            "megapixels": megapixels, "multiple": multiple,
        }]}
        if not generate_latent:
            return io.NodeOutput(width, height, None, ui=ui)
        if latent_format not in LATENT_FORMATS:
            raise ValueError(f"Unknown latent format: {latent_format}")
        family, alignment = LATENT_FORMATS[latent_format]
        if width % alignment or height % alignment:
            raise ValueError(
                f"{latent_format} requires dimensions divisible by {alignment}; "
                f"selected {width} x {height}. Set multiple to {alignment} or a "
                f"multiple of {alignment} (in advanced controls)."
            )
        if family == "sd":
            from nodes import EmptyLatentImage
            latent = EmptyLatentImage().generate(width, height, batch_size)[0]
        elif family == "sd3":
            from comfy_extras.nodes_sd3 import EmptySD3LatentImage
            latent = EmptySD3LatentImage.execute(width, height, batch_size)[0]
        elif family == "flux2":
            from comfy_extras.nodes_flux import EmptyFlux2LatentImage
            latent = EmptyFlux2LatentImage.execute(width, height, batch_size)[0]
        elif family == "single_frame":
            from comfy_extras.nodes_hunyuan import EmptyHunyuanLatentVideo
            latent = EmptyHunyuanLatentVideo.execute(width, height, 1, batch_size)[0]
        elif family == "hunyuan_image":
            from comfy_extras.nodes_hunyuan import EmptyHunyuanImageLatent
            latent = EmptyHunyuanImageLatent.execute(width, height, batch_size)[0]
        elif family == "hidream_o1":
            if not (64 <= width <= 4096 and 64 <= height <= 4096 and 1 <= batch_size <= 64):
                raise ValueError("HiDream-O1 requires width/height from 64 to 4096 and batch_size from 1 to 64.")
            from comfy_extras.nodes_hidream_o1 import EmptyHiDreamO1LatentImage
            latent = EmptyHiDreamO1LatentImage.execute(
                width=width, height=height, batch_size=batch_size,
            )[0]
        elif family == "qwen21":
            import torch
            import comfy.model_management
            samples = torch.zeros(
                (batch_size, 64, height // 16, width // 16),
                device=comfy.model_management.intermediate_device(),
                dtype=comfy.model_management.intermediate_dtype(),
            )
            latent = {"samples": samples, "downscale_ratio_spacial": 16}
        else:
            raise ValueError(f"Unknown latent generator family: {family}")
        return io.NodeOutput(width, height, latent, ui=ui)


class CustomNodesExtension(ComfyExtension):
    async def get_node_list(self):
        return [ResolutionSelectorLatent, LightingStylePromptAssembler, Krea2PromptWriter]


async def comfy_entrypoint():
    return CustomNodesExtension()
