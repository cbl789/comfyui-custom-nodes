# ComfyUI Custom Nodes

A collection of custom nodes for ComfyUI.

## Included nodes

### Resolution Selector + Latent

ComfyUI's built-in Resolution Selector, extended with an optional reference image
and an empty `LATENT` output.
Requires a recent ComfyUI with the built-in `ResolutionSelector` and V3 node API.
Uses ComfyUI's original resolution calculation for preset ratios and its empty-latent
generators. Includes a small frontend extension for the dimension preview. No additional
Python packages are required.

## Outputs

| Output | Type | Description |
| --- | --- | --- |
| `width` | `INT` | Selected width in pixels |
| `height` | `INT` | Selected height in pixels |
| `latent` | `LATENT` | Empty latent at the selected size, or `None` when disabled |

## Install

Copy this directory to `ComfyUI/custom_nodes/comfyui-custom-nodes`,
restart ComfyUI, and refresh the browser. Search for **Resolution Selector + Latent**
under **utilities**.

## Use

- Select the aspect ratio, megapixels and advanced `multiple` as in the built-in node.
- Optionally connect an image to `reference_image`. Its aspect ratio overrides the
  dropdown; megapixels still sets the target size. Arbitrary image proportions are
  supported, subject to the selected rounding increment.
- The reference is used for dimensions only: it is not resized, encoded, or copied
  into the output latent. Reference batch size does not change `batch_size`.
- Without a reference, the preview updates live. With a reference, it shows the
  calculated dimensions labeled **Last run** after execution. Changes to this node’s
  controls or connections mark it pending. Upstream image changes are reflected on
  the next execution. Run the workflow again to refresh it. Refresh your browser after installing updates.
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

The dimension preview is not a generated image preview. Without a reference,
width and height match the built-in node exactly.

## Upstream

This extension imports ComfyUI's implementation rather than copying it:
[Resolution Selector source](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_resolution.py)

## Development checks

Run the backend tests with the Python environment used by ComfyUI:

```sh
COMFYUI_PATH=/path/to/ComfyUI python tests/test_resolution_selector.py
```

The tests run on CPU and do not load model weights. Run the frontend hook tests with Node.js:

```sh
node tests/test-reference-preview.mjs
```
