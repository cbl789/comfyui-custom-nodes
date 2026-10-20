"""Run with ComfyUI's Python: COMFYUI_PATH=/path/to/ComfyUI python tests/test_resolution_selector.py."""

import asyncio
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


if os.environ.get("COMFYUI_PATH"):
    sys.path.insert(0, os.environ["COMFYUI_PATH"])
_original_argv = sys.argv[:]
sys.argv = [sys.argv[0], "--cpu"]
import torch
from comfy_extras.nodes_resolution import AspectRatio, ResolutionSelector

_node_path = Path(os.environ.get(
    "RESOLUTION_NODE_PATH", Path(__file__).resolve().parents[1] / "__init__.py"
))
_spec = importlib.util.spec_from_file_location("resolution_selector_under_test", _node_path)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
sys.argv = _original_argv
Node = _module.ResolutionSelectorLatent


class ResolutionSelectorTests(unittest.TestCase):
    def dimensions(self, reference=None, **kwargs):
        return Node.execute(
            kwargs.pop("aspect_ratio", "1:1 (Square)"),
            kwargs.pop("megapixels", 1.0), kwargs.pop("multiple", 8),
            generate_latent=False, reference_image=reference, **kwargs,
        )

    def test_schema_and_extension(self):
        self.assertEqual(Node.define_schema().node_id, "ResolutionSelectorWithLatent")
        inputs = Node.INPUT_TYPES()
        self.assertEqual(inputs["optional"]["reference_image"][0], "IMAGE")
        self.assertEqual(len(Node.define_schema().outputs), 3)
        extension = asyncio.run(_module.comfy_entrypoint())
        registered = asyncio.run(extension.get_node_list())
        self.assertIn(Node, registered)
        self.assertEqual({item.define_schema().node_id for item in registered},
                         {"ResolutionSelectorWithLatent", "LightingStylePromptAssembler"})

    def test_no_reference_matches_builtin_all_presets(self):
        with patch.object(torch, "zeros", side_effect=AssertionError("Unexpected allocation")):
            for ratio in AspectRatio:
                for mp in (0.1, 1.0, 2.0, 16.0):
                    for multiple in (8, 12, 16, 32, 128):
                        with self.subTest(ratio=ratio, mp=mp, multiple=multiple):
                            expected = ResolutionSelector.execute(ratio, mp, multiple).result
                            actual = self.dimensions(aspect_ratio=ratio, megapixels=mp,
                                                     multiple=multiple).result
                            self.assertEqual(actual, (*expected, None))

    def test_reference_overrides_dropdown_and_handles_arbitrary_ratios(self):
        for height, width in ((2, 3), (3, 2), (7, 11), (11, 7), (1, 1)):
            image = torch.empty((1, height, width, 3))
            for mp in (0.1, 1.0, 2.0):
                for multiple in (8, 16, 32):
                    with self.subTest(height=height, width=width, mp=mp, multiple=multiple):
                        scale = math.sqrt(mp * 1024 * 1024 / (width * height))
                        expected = (round(width * scale / multiple) * multiple,
                                    round(height * scale / multiple) * multiple, None)
                        # An unrecognized dropdown value must never be read in reference mode.
                        result = self.dimensions(image, aspect_ratio="unused",
                                                 megapixels=mp, multiple=multiple)
                        self.assertEqual(result.result, expected)

    def test_reference_ratios_match_equivalent_builtin_presets(self):
        for height, width, ratio in ((2, 3, "3:2 (Photo)"),
                                     (3, 2, "2:3 (Portrait Photo)"),
                                     (9, 16, "16:9 (Widescreen)")):
            actual = self.dimensions(torch.empty((1, height, width, 3)))
            expected = ResolutionSelector.execute(ratio, 1.0, 8).result
            self.assertEqual(actual.result[:2], expected)

    def test_disabled_latent_does_not_allocate_or_inspect_pixels(self):
        class ShapeOnlyImage:
            shape = (3, 7, 11, 3)

        with patch.object(torch, "zeros", side_effect=AssertionError("Unexpected allocation")):
            output = self.dimensions(ShapeOnlyImage())
        self.assertIsNone(output[2])

    def test_reference_pixels_and_source_batch_do_not_affect_dimensions(self):
        black = torch.zeros((1, 7, 11, 3))
        white = torch.ones((4, 7, 11, 3))
        self.assertEqual(self.dimensions(black).result, self.dimensions(white).result)

    def test_ui_payload_contains_actual_reference_and_selected_dimensions(self):
        result = self.dimensions(torch.empty((1, 7, 11, 3)), megapixels=2.0, multiple=16)
        self.assertEqual(result.ui["resolution"], [{
            "width": result[0], "height": result[1],
            "reference_width": 11, "reference_height": 7,
            "megapixels": 2.0, "multiple": 16,
        }])
        manual = self.dimensions()
        self.assertIsNone(manual.ui["resolution"][0]["reference_width"])
        self.assertIsNone(manual.ui["resolution"][0]["reference_height"])

    def test_all_latent_formats_match_reference_dimensions_and_batch_size(self):
        image = torch.empty((3, 3, 2, 3))
        specs = {
            "SD / SDXL (4 channels)": (4, 8, False),
            "SD3 / Flux (16 channels)": (16, 8, False),
            "Flux 2 / Klein (128 channels)": (128, 16, False),
            "Flux 3 (128 channels)": (128, 16, False),
            "Qwen Image 2.1 (64 channels)": (64, 16, False),
            "Krea 2 (16 channels, single frame)": (16, 8, True),
            "Qwen Image (16 channels, single frame)": (16, 8, True),
            "Z-Image / HiDream (16 channels)": (16, 8, False),
            "Hunyuan Image 2.1 (64 channels)": (64, 32, False),
            "HiDream-O1 (pixel space)": (3, 1, False),
        }
        self.assertEqual(set(specs), set(_module.FORMATS))
        for fmt, (channels, divisor, single_frame) in specs.items():
            with self.subTest(format=fmt):
                width, height, latent = Node.execute(
                    "1:1 (Square)", 0.1, 32, reference_image=image,
                    latent_format=fmt, batch_size=2,
                ).result
                samples = latent["samples"]
                expected = (2, channels, height // divisor, width // divisor)
                if single_frame:
                    expected = (2, channels, 1, height // divisor, width // divisor)
                self.assertEqual(tuple(samples.shape), expected)
                self.assertEqual(samples.device.type, "cpu")
                self.assertEqual(torch.count_nonzero(samples).item(), 0)

    def test_rejects_empty_or_malformed_reference(self):
        for shape in ((3, 7, 3), (0, 7, 11, 3), (1, 0, 11, 3),
                      (1, 7, 0, 3), (1, 7, 11, 0)):
            with self.subTest(shape=shape), self.assertRaisesRegex(ValueError, "non-empty IMAGE"):
                self.dimensions(torch.empty(shape))

    def test_rejects_invalid_reference_resolution_settings(self):
        image = torch.empty((1, 7, 11, 3))
        for mp in (0, -1, math.nan, math.inf):
            with self.subTest(megapixels=mp), self.assertRaises(ValueError):
                self.dimensions(image, megapixels=mp)
        with self.assertRaises(ValueError):
            self.dimensions(image, multiple=0)

    def test_rejects_reference_that_rounds_to_zero(self):
        class ExtremeImage:
            shape = (1, 1, 1000000, 3)

        with self.assertRaisesRegex(ValueError, "too extreme"):
            self.dimensions(ExtremeImage(), megapixels=0.1, multiple=128)

    def test_rejects_incompatible_latent_dimensions(self):
        with self.assertRaisesRegex(ValueError, "divisible by 16"):
            Node.execute("1:1 (Square)", 0.1, 8,
                         reference_image=torch.empty((1, 3, 2, 3)),
                         latent_format="Flux 2 / Klein (128 channels)")

    def test_legacy_format_names_remain_valid(self):
        choices = next(item.options for item in Node.define_schema().inputs
                       if item.id == "latent_format")
        for fmt in ("SD / SDXL (4 channels)", "SD3 / Flux (16 channels)",
                    "Flux 2 / Klein (128 channels)"):
            self.assertIn(fmt, choices)

    def test_qwen21_metadata_uses_16_pixel_compression(self):
        result = Node.execute("1:1 (Square)", 0.1, 16,
                              latent_format="Qwen Image 2.1 (64 channels)")
        self.assertEqual(result[2]["downscale_ratio_spacial"], 16)

    def test_hidream_o1_rejects_out_of_range_sizes_and_batches(self):
        for args in ((16.0, "21:9 (Ultrawide)", 1), (0.1, "1:1 (Square)", 65)):
            mp, ratio, batch = args
            with self.assertRaisesRegex(ValueError, "HiDream-O1 requires"):
                Node.execute(ratio, mp, 32, latent_format="HiDream-O1 (pixel space)",
                             batch_size=batch)


if __name__ == "__main__":
    unittest.main()
