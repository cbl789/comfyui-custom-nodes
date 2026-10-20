"""Resolution selection from presets or a reference image, with optional latent."""

import math

from comfy_api.latest import ComfyExtension, io
from comfy_extras.nodes_resolution import ResolutionSelector

WEB_DIRECTORY = "./web"

FORMATS = ["SD / SDXL (4 channels)", "SD3 / Flux (16 channels)", "Flux 2 / Klein (128 channels)"]


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
        schema.description = (
            "The built-in Resolution Selector with an optional empty image latent. "
            "An optional reference image overrides the aspect ratio, not the megapixel target. "
            "Choose the latent format required by your model. Disable generate_latent "
            "to use only width and height without allocating a tensor."
        )
        schema.inputs.extend([
            io.Boolean.Input("generate_latent", default=True,
                             tooltip="Create an empty latent. When off, latent returns None."),
            io.Combo.Input("latent_format", options=FORMATS, default=FORMATS[0]),
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
        if latent_format not in FORMATS:
            raise ValueError(f"Unknown latent format: {latent_format}")
        divisor = 16 if latent_format == FORMATS[2] else 8
        if width % divisor or height % divisor:
            raise ValueError(
                f"{latent_format} requires dimensions divisible by {divisor}; "
                f"selected {width} x {height}. Set multiple to {divisor} or a "
                f"multiple of {divisor} (in advanced controls)."
            )
        if latent_format == FORMATS[0]:
            from nodes import EmptyLatentImage
            latent = EmptyLatentImage().generate(width, height, batch_size)[0]
        elif latent_format == FORMATS[1]:
            from comfy_extras.nodes_sd3 import EmptySD3LatentImage
            latent = EmptySD3LatentImage.execute(width, height, batch_size)[0]
        else:
            from comfy_extras.nodes_flux import EmptyFlux2LatentImage
            latent = EmptyFlux2LatentImage.execute(width, height, batch_size)[0]
        return io.NodeOutput(width, height, latent, ui=ui)


class ResolutionSelectorLatentExtension(ComfyExtension):
    async def get_node_list(self):
        return [ResolutionSelectorLatent]


async def comfy_entrypoint():
    return ResolutionSelectorLatentExtension()
