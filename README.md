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
under **utilities**, or **Prompt Assembler (Lighting + Style)** under **utilities/prompt**.

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
- Choose the matching model preset from `latent_format` (see the table below).
  These are image latents; video and layered-image generation require their own generators.
- New nodes default to **Flux 2 / Klein** and advanced `multiple` **32**, which
  produces dimensions compatible with every preset. Existing workflows keep their
  saved preset and rounding value. Incompatible dimensions raise an error rather
  than silently changing the image size.
- Advanced `batch_size` defaults to 1.
- Turn `generate_latent` off for dimensions only; no latent tensor is allocated.
  The latent socket stays visible and returns `None` when disabled. Disconnect
  it from consumers before using dimensions-only mode.

The dimension preview is not a generated image preview. Without a reference,
width and height match the built-in node exactly.

## Image latent presets

| Preset | Channels | Spatial compression | Representation | Dimension alignment |
| --- | --- | --- | --- | --- |
| Flux 2 / Klein | 128 | 16x | Image | 16 |
| Flux 3 | 128 | 16x | Image | 16 |
| Qwen Image 2.1 | 64 | 16x | Image | 16 |
| Krea 2 | 16 | 8x | Single image frame | 16 |
| Qwen Image (before 2.1) | 16 | 8x | Single image frame | 16 |
| Z-Image / HiDream | 16 | 8x | Image | 16 |
| Hunyuan Image 2.1 | 64 | 32x | Image | 32 |
| HiDream-O1 | 3 | 1x | Pixel space | 32 |
| SD / SDXL | 4 | 8x | Image | 8 |
| SD3 / Flux | 16 | 8x | Image | 8 |

Dimension alignment is the required pixel increment for each preset. A `multiple`
of 32 works for all of them. These choices are explicit model presets, not automatic
model detection. Ordinary Z-Image and Z-Image Pixel Space are different variants;
the Z-Image preset above is for the ordinary latent-space model.

Krea 2 and older Qwen Image use a singleton frame axis (`B,C,1,H,W`), not a video
sequence. Existing SD3/Flux outputs also work with standard ComfyUI samplers for
these models because ComfyUI inserts the frame axis automatically.

HiDream-O1 follows its built-in generator's limits: dimensions 64–4096 and batch
size 1–64. Its documented training resolution is approximately 4 MP. Modern presets
require a ComfyUI version containing the corresponding model support.

## Prompt Assembler (Lighting + Style)

Build photographic prompts from separate lighting, style, and skin-texture choices.
Enter or connect your existing subject/scene text in `base_prompt`, then connect the
`prompt` output to your text encoder or prompt enhancer. The subject text is kept
intact apart from outer whitespace; sections are appended as paragraphs.

| Control | Purpose |
| --- | --- |
| `base_prompt` | Your subject and scene text; can be empty when you only want fragments |
| `lighting` | Window light, open shade, overcast, sunlight, golden hour, softbox, flash, or indoor lamps |
| `style` | Natural photography, unretouched portrait, documentary, editorial, or film |
| `skin_texture` | Natural texture, close-up detail, soft natural texture, or none |
| `custom_lighting` | Additional lighting text (advanced) |
| `custom_style` | Additional style text (advanced) |
| `preview` | Read-only assembled text (advanced) |

Defaults: **Soft window light + Natural photography + Natural texture**.
Each preset group has a **None** option. Skin texture is independent of photographic
style: set both to None to omit all style instructions. For custom text only, set
all three preset groups to None and enter your own fragments.

Outputs are `prompt` (full text), `lighting` (lighting fragment), and `style`
(photographic style, skin texture, and custom style together). Use either the full
prompt or the separate fragments to avoid appending the same text twice.

The preview updates live for local widget values. Connected text inputs show the
last executed prompt after running; upstream changes are reflected on the next
execution. The preview itself is not serialized into the workflow.

The skin presets describe restrained texture and tonal variation. Close-up detail
qualifies fine pores and facial hairs by image scale; it does not force exaggerated
pores or blemishes. Presets do not set identity, age, pose, body shape, or makeup.
The node uses plain text without model-specific weighting or external services.
Results still depend on the model, LoRAs, reference images, and generation settings.

All preset text lives in `web/photo_presets.json`, shared by the backend and preview.
Changing this bundled file requires a ComfyUI restart and browser refresh.

## Upstream

This extension imports ComfyUI's implementation rather than copying it:
[Resolution Selector source](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_resolution.py)

## Development checks

Run the backend tests with the Python environment used by ComfyUI:

```sh
COMFYUI_PATH=/path/to/ComfyUI python -m unittest discover -s tests -p 'test_*.py'
```

The tests run on CPU and do not load model weights. Run the frontend hook tests with Node.js:

```sh
node tests/test-reference-preview.mjs
node tests/test-prompt-assembler.mjs
```
