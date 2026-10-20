"""Run using ComfyUI's Python, with COMFYUI_PATH set to the ComfyUI checkout."""

import importlib.util
import os
from pathlib import Path
import sys
import unittest

if os.environ.get("COMFYUI_PATH"):
    sys.path.insert(0, os.environ["COMFYUI_PATH"])
_original_argv = sys.argv[:]
sys.argv = [sys.argv[0], "--cpu"]
_source = Path(__file__).resolve().parents[1] / "prompt_assembler.py"
_spec = importlib.util.spec_from_file_location("prompt_assembler_under_test", _source)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
sys.argv = _original_argv


class PromptAssemblerTests(unittest.TestCase):
    def test_subject_text_stays_first_and_is_not_rewritten(self):
        subject = "A person reading.\nA quiet room, blue curtains."
        prompt, lighting, style = _module.assemble_prompt(subject)
        self.assertEqual(prompt.split("\n\n")[0], subject)
        self.assertIn(lighting, prompt)
        self.assertIn(style, prompt)
        self.assertEqual(prompt.count(subject), 1)

    def test_all_sections_disabled_is_passthrough(self):
        subject = "A person beside a window."
        self.assertEqual(_module.assemble_prompt(subject, "None", "None", "None"),
                         (subject, "", ""))
        self.assertEqual(_module.assemble_prompt("", "None", "None", "None"), ("", "", ""))

    def test_custom_only_mode_and_empty_sections(self):
        result = _module.assemble_prompt("  A person.  ", "None", "None", "None",
                                          "  Side light.  ", "  A neutral photograph.  ")
        self.assertEqual(result, ("A person.\n\nSide light.\n\nA neutral photograph.",
                                  "Side light.", "A neutral photograph."))

    def test_skin_is_independent_of_photographic_style(self):
        prompt, lighting, style = _module.assemble_prompt("", "None", "None", "Natural texture")
        self.assertEqual(lighting, "")
        self.assertEqual(style, _module.PRESETS["skin_texture"]["Natural texture"])
        self.assertEqual(prompt, style)

    def test_fragments_do_not_contain_subject_prompt(self):
        subject = "A person wearing a blue coat."
        prompt, lighting, style = _module.assemble_prompt(subject, custom_lighting="Soft fill.",
                                                         custom_style="Neutral colors.")
        self.assertNotIn(subject, lighting)
        self.assertNotIn(subject, style)
        self.assertIn("Soft fill.", lighting)
        self.assertIn("Neutral colors.", style)
        self.assertTrue(prompt.startswith(subject))

    def test_invalid_preset_fails_clearly(self):
        for name in ("lighting", "style", "skin_texture"):
            with self.subTest(input=name), self.assertRaisesRegex(ValueError, f"Unknown {name} preset"):
                _module.assemble_prompt(**{name: "missing-preset"})

    def test_presets_are_nonempty_except_none_and_defaults_exist(self):
        defaults = {"lighting": _module.DEFAULT_LIGHTING, "style": _module.DEFAULT_STYLE,
                    "skin_texture": _module.DEFAULT_SKIN}
        for group, choices in _module.PRESETS.items():
            self.assertEqual(choices["None"], "")
            self.assertIn(defaults[group], choices)
            for name, text in choices.items():
                if name != "None":
                    self.assertTrue(text.strip(), (group, name))

    def test_node_schema_and_execution_payload(self):
        node = _module.LightingStylePromptAssembler
        self.assertEqual(node.define_schema().node_id, "LightingStylePromptAssembler")
        self.assertEqual([item.id for item in node.define_schema().outputs],
                         ["prompt", "lighting", "style"])
        self.assertEqual(node.INPUT_TYPES()["required"]["base_prompt"][0], "STRING")
        result = node.execute("A person reading.")
        self.assertEqual(result.result, _module.assemble_prompt("A person reading."))
        self.assertEqual(result.ui, {"assembled_prompt": [result[0]]})


if __name__ == "__main__":
    unittest.main()
