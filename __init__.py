"""ComfyUI's Resolution Selector with an optional empty image latent."""

from comfy_api.latest import ComfyExtension, io
from comfy_extras.nodes_resolution import ResolutionSelector


FORMATS = ["SD / SDXL (4 channels)", "SD3 / Flux (16 channels)", "Flux 2 / Klein (128 channels)"]


class ResolutionSelectorLatent(ResolutionSelector):
    @classmethod
    def define_schema(cls):
        schema = ResolutionSelector.define_schema()
        schema.node_id = "ResolutionSelectorWithLatent"
        schema.display_name = "Resolution Selector + Latent"
        schema.description = (
            "The built-in Resolution Selector with an optional empty image latent. "
            "Choose the latent format required by your model. Disable generate_latent "
            "to use only width and height without allocating a tensor."
        )
        schema.inputs.extend([
            io.Boolean.Input("generate_latent", default=True,
                             tooltip="Create an empty latent. When off, latent returns None."),
            io.Combo.Input("latent_format", options=FORMATS, default=FORMATS[0]),
            io.Int.Input("batch_size", default=1, min=1, max=4096, advanced=True),
        ])
        schema.outputs.append(io.Latent.Output("latent"))
        return schema

    @classmethod
    def execute(cls, aspect_ratio, megapixels, multiple, generate_latent=True,
                latent_format=FORMATS[0], batch_size=1, preview=None):
        width, height = ResolutionSelector.execute(
            aspect_ratio=aspect_ratio, megapixels=megapixels,
            multiple=multiple, preview=preview,
        ).result
        if not generate_latent:
            return io.NodeOutput(width, height, None)
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
        return io.NodeOutput(width, height, latent)


class ResolutionSelectorLatentExtension(ComfyExtension):
    async def get_node_list(self):
        return [ResolutionSelectorLatent]


async def comfy_entrypoint():
    return ResolutionSelectorLatentExtension()
