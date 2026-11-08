"""Run with any Python 3: this module does not import ComfyUI."""

import importlib.util
import json
import sys
from pathlib import Path
import tempfile
import unittest

_source = Path(__file__).resolve().parents[1] / "sidecar_meta.py"
_spec = importlib.util.spec_from_file_location("sidecar_meta_under_test", _source)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)


SIDECAR = {
    "schema_version": 2,
    "asset": {"name": "Example LoRA", "kind": "lora"},
    "file": {"name": "example.safetensors", "format": "safetensors"},
    "compatibility": {"base_model": "Krea 2"},
    "sources": [{"provider": "civitai", "url": "https://civitai.com/models/1?modelVersionId=2"}],
    "usage": {
        "triggers": [{"text": "famegrid"}, {"text": "rlskn"}],
        "strength": {"model": 0.8, "clip": 0.6, "min": 0.5, "max": 1.0},
    },
    "notes": "Start the prompt with the trigger word.",
}


class SidecarPathTests(unittest.TestCase):
    def test_sidecar_sits_beside_the_model_with_the_full_name(self):
        self.assertEqual(
            str(_module.sidecar_path("/models/loras/krea2/example.safetensors")),
            "/models/loras/krea2/example.safetensors.json",
        )


class LoadTests(unittest.TestCase):
    def test_missing_sidecar_is_none(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(_module.load_sidecar(Path(folder) / "none.safetensors"))

    def test_malformed_or_non_object_sidecar_is_none(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, text in (("broken.safetensors", "{oops"), ("list.safetensors", "[1, 2]")):
                model = Path(folder) / name
                model.write_text("")
                Path(str(model) + ".json").write_text(text)
                with self.subTest(name=name):
                    self.assertIsNone(_module.load_sidecar(model))

    def test_valid_sidecar_is_returned(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "example.safetensors"
            model.write_text("")
            Path(str(model) + ".json").write_text(json.dumps(SIDECAR))
            self.assertEqual(_module.load_sidecar(model), SIDECAR)


class TriggerTests(unittest.TestCase):
    def test_reads_usage_triggers_in_order(self):
        self.assertEqual(_module.trigger_texts(SIDECAR), ["famegrid", "rlskn"])

    def test_missing_or_malformed_triggers_are_skipped(self):
        metadata = {"usage": {"triggers": [{"text": "ok"}, {}, {"text": "  "}, {"text": 3}, "x"]}}
        self.assertEqual(_module.trigger_texts(metadata), ["ok"])
        self.assertEqual(_module.trigger_texts({}), [])
        self.assertEqual(_module.trigger_texts(None), [])


class StrengthTests(unittest.TestCase):
    def test_reads_model_and_clip(self):
        self.assertEqual(_module.strength_values(SIDECAR), (0.8, 0.6))

    def test_range_only_is_not_a_strength(self):
        self.assertEqual(_module.strength_values({"usage": {"strength": {"min": 0.2, "max": 1}}}),
                         (None, None))

    def test_ignores_booleans(self):
        self.assertEqual(_module.strength_values({"usage": {"strength": {"model": True}}}),
                         (None, None))


class ComposeTests(unittest.TestCase):
    def test_show_only_never_changes_the_prompt(self):
        self.assertEqual(_module.compose_prompt("a cat", ["famegrid"], "Show only"), "a cat")
        self.assertEqual(_module.compose_prompt("", ["famegrid"], "Show only"), "")

    def test_append_adds_triggers_after_the_prompt(self):
        self.assertEqual(_module.compose_prompt("a cat.  ", ["famegrid", "rlskn"], "Append triggers"),
                         "a cat., famegrid, rlskn")

    def test_append_without_prompt_returns_only_triggers(self):
        self.assertEqual(_module.compose_prompt("   ", ["famegrid"], "Append triggers"), "famegrid")

    def test_append_without_triggers_is_passthrough(self):
        self.assertEqual(_module.compose_prompt("a cat", [], "Append triggers"), "a cat")

    def test_unknown_mode_fails_clearly(self):
        with self.assertRaises(ValueError):
            _module.compose_prompt("a cat", ["x"], "nonsense")


class SummaryTests(unittest.TestCase):
    def test_missing_sidecar_says_so_and_names_the_expected_file(self):
        text = _module.summary(None, "loras/krea2/example.safetensors")
        self.assertIn("Sidecar: none", text)
        self.assertIn(".json", text)

    def test_summary_reports_the_fields_the_user_needs(self):
        text = _module.summary(SIDECAR, "loras/krea2/example.safetensors")
        for part in ("Example LoRA", "Base: Krea 2", "famegrid, rlskn", "model 0.8",
                     "clip 0.6", "range 0.5-1.0", "https://civitai.com/models/1", "Sidecar: v2"):
            self.assertIn(part, text)

    def test_long_notes_are_truncated(self):
        metadata = dict(SIDECAR, notes="x" * 400)
        self.assertIn("...", _module.summary(metadata, "x.safetensors"))


class ResponseTests(unittest.TestCase):
    def test_payload_reports_found_summary_and_triggers(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "example.safetensors"
            model.write_text("")
            Path(str(model) + ".json").write_text(json.dumps(SIDECAR))
            data = _module.response("loras/example.safetensors", model)
            self.assertTrue(data["found"])
            self.assertEqual(data["name"], "loras/example.safetensors")
            self.assertEqual(data["triggers"], ["famegrid", "rlskn"])
            self.assertIn("Example LoRA", data["summary"])

    def test_payload_without_a_sidecar_is_still_well_formed(self):
        with tempfile.TemporaryDirectory() as folder:
            data = _module.response("loras/none.safetensors", Path(folder) / "none.safetensors")
            self.assertFalse(data["found"])
            self.assertEqual(data["triggers"], [])
            self.assertIn("Sidecar: none", data["summary"])


if __name__ == "__main__":
    unittest.main()
