"""Run using ComfyUI's Python, with COMFYUI_PATH set to the ComfyUI checkout. No network calls."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

if os.environ.get("COMFYUI_PATH"):
    sys.path.insert(0, os.environ["COMFYUI_PATH"])
_original_argv = sys.argv[:]
sys.argv = [sys.argv[0], "--cpu"]
_source = Path(__file__).resolve().parents[1] / "krea2_prompt_writer.py"
_spec = importlib.util.spec_from_file_location("krea2_prompt_writer_under_test", _source)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
sys.argv = _original_argv


class ReferenceChoiceTests(unittest.TestCase):
    def test_auto_adds_adult_reference_only_for_adult_briefs(self):
        self.assertEqual(_module.choose_references("Auto", "a man feeding pigeons"), ["photoreal.md"])
        self.assertEqual(_module.choose_references("Auto", "a woman lying nude on a bed"),
                         ["photoreal.md", "adult.md"])
        self.assertEqual(_module.choose_references("Auto", "", "make it explicit"),
                         ["photoreal.md", "adult.md"])

    def test_auto_matches_whole_words_only(self):
        self.assertEqual(_module.choose_references("Auto", "Sussex countryside, a cocktail bar"), ["photoreal.md"])

    def test_auto_keeps_boudoir_and_lingerie_suggestive(self):
        self.assertEqual(_module.choose_references("Auto", "a boudoir photo in black lace lingerie"), ["photoreal.md"])

    def test_explicit_selection_wins(self):
        self.assertEqual(_module.choose_references("Photoreal", "nude"), ["photoreal.md"])
        self.assertEqual(_module.choose_references("Photoreal + Adult", "pigeons"), ["photoreal.md", "adult.md"])


class ReplyParsingTests(unittest.TestCase):
    def test_prompt_and_full_aspect(self):
        prompt, aspect = _module.parse_reply("PROMPT:\nAn amateur phone photo.\n\nASPECT_RATIO:\n9:16 (Portrait Widescreen)")
        self.assertEqual((prompt, aspect), ("An amateur phone photo.", "9:16 (Portrait Widescreen)"))

    def test_short_aspect_and_thinking_are_handled(self):
        prompt, aspect = _module.parse_reply("<think>plan</think>PROMPT: A photo.\nASPECT_RATIO: `3:2`")
        self.assertEqual((prompt, aspect), ("A photo.", "3:2 (Photo)"))

    def test_unknown_or_missing_aspect_returns_none(self):
        self.assertEqual(_module.parse_reply("PROMPT: A photo.\nASPECT_RATIO: 5:4")[1], None)
        self.assertEqual(_module.parse_reply("PROMPT: A photo.")[1], None)

    def test_missing_prompt_raises(self):
        with self.assertRaises(ValueError):
            _module.parse_reply("I cannot help with that.")


class RequestTests(unittest.TestCase):
    def test_new_prompt_needs_a_brief(self):
        with self.assertRaises(ValueError):
            _module.build_user_message("Write new prompt", "  ", "", "", "")
        self.assertIn("a red apple", _module.build_user_message("Write new prompt", "a red apple", "", "", ""))

    def test_change_includes_current_prompt_aspect_and_change(self):
        message = _module.build_user_message("Apply change", "", "red hair", "A photo.", "2:3 (Portrait Photo)")
        for part in ("A photo.", "2:3 (Portrait Photo)", "red hair"):
            self.assertIn(part, message)

    def test_change_needs_prompt_and_change(self):
        with self.assertRaises(ValueError):
            _module.build_user_message("Apply change", "", "red hair", "", "")
        with self.assertRaises(ValueError):
            _module.build_user_message("Apply change", "", " ", "A photo.", "")

    def test_system_prompt_contains_instructions_skill_and_references(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "references").mkdir()
            (Path(folder) / "SKILL.md").write_text("SKILL BODY")
            (Path(folder) / "references" / "photoreal.md").write_text("PHOTOREAL BODY")
            system = _module.build_system_prompt(folder, ["photoreal.md"])
            self.assertIn("Style first", system)
            self.assertIn("SKILL BODY", system)
            self.assertIn("PHOTOREAL BODY", system)
            with self.assertRaises(ValueError):
                _module.build_system_prompt(folder, ["adult.md"])

    def test_missing_skill_folder_explains_the_fix(self):
        with self.assertRaisesRegex(ValueError, "skill not found"):
            _module.build_system_prompt("/nonexistent/krea2-prompting", ["photoreal.md"])


class AspectTests(unittest.TestCase):
    def test_manual_choice_wins_then_writer_then_current_then_fallback(self):
        auto = _module.AUTO_ASPECT
        self.assertEqual(_module.resolve_aspect("1:1 (Square)", "3:2 (Photo)", None), "1:1 (Square)")
        self.assertEqual(_module.resolve_aspect(auto, "9:16 (Portrait Widescreen)", "3:2 (Photo)"),
                         "9:16 (Portrait Widescreen)")
        self.assertEqual(_module.resolve_aspect(auto, None, "2:3 (Portrait Photo)"), "2:3 (Portrait Photo)")
        self.assertEqual(_module.resolve_aspect(auto, None, None), _module.FALLBACK_ASPECT)

    def test_model_modes_always_rerun_and_keep_is_cached(self):
        fingerprint = _module.Krea2PromptWriter.fingerprint_inputs
        for mode in ("Write new prompt", "Apply change"):
            value = fingerprint(mode=mode, brief="a cat")
            self.assertNotEqual(value, value)
        self.assertEqual(fingerprint(mode="Keep current prompt"), fingerprint(mode="Keep current prompt"))

    def test_keep_mode_does_not_call_the_model(self):
        _module.call_model = lambda *args: self.fail("model must not be called in Keep mode")
        result = _module.Krea2PromptWriter.execute(
            mode="Keep current prompt", brief="", change="", current_prompt=" A photo. ",
            aspect_ratio=_module.AUTO_ASPECT, megapixels=2.0, current_aspect="3:2 (Photo)",
        )
        prompt, width, height, aspect = result.result
        self.assertEqual((prompt, aspect), ("A photo.", "3:2 (Photo)"))
        self.assertEqual((width % 16, height % 16), (0, 0))
        self.assertGreater(width, height)


if __name__ == "__main__":
    unittest.main()
