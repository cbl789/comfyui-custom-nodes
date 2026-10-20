# Resolution Selector + Latent

ComfyUI's built-in Resolution Selector, extended with an empty `LATENT` output.
Requires a recent ComfyUI with the built-in `ResolutionSelector` and V3 node API.
Uses ComfyUI's original schema, resolution calculation, resolution preview widget,
and empty-latent generators. No additional Python packages or frontend scripts.

## Outputs

| Output | Type | Description |
| --- | --- | --- |
| `width` | `INT` | Selected width in pixels |
| `height` | `INT` | Selected height in pixels |
| `latent` | `LATENT` | Empty latent at the selected size, or `None` when disabled |

## Install

Copy this directory to `ComfyUI/custom_nodes/comfyui-resolution-selector-latent`,
restart ComfyUI, and refresh the browser. Search for **Resolution Selector + Latent**
under **utilities**.

## Use

- Select the aspect ratio, megapixels and advanced `multiple` as in the built-in node.
- Outputs remain `width`, `height`, followed by the new `latent` output.
- Connect `latent` directly to the sampler's latent input instead of using an
  additional Empty Latent Image node.
- Choose `SD / SDXL`, `SD3 / Flux`, or `Flux 2 / Klein` to match the empty-latent
  node your workflow normally uses. These are image latents; video and layered
  image latents require their own generators.
- For Flux 2 / Klein, set advanced `multiple` to **16** (or 32, 48, etc.).
  For the other formats use **8** or a multiple of 8. Incompatible dimensions
  raise an error instead of silently generating a different image size.
- Advanced `batch_size` defaults to 1.
- Turn `generate_latent` off for dimensions only; no latent tensor is allocated.
  The latent socket stays visible and returns `None` when disabled. Disconnect
  it from consumers before using dimensions-only mode.

The built-in resolution preview displays the calculated dimensions; it is not a
generated image preview. Width and height always match the built-in node exactly.

## Upstream

This extension imports ComfyUI's implementation rather than copying it:
[Resolution Selector source](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_resolution.py)
