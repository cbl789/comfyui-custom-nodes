import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const presets = JSON.parse(fs.readFileSync(new URL("../web/photo_presets.json", import.meta.url), "utf8"));
const source = fs.readFileSync(new URL("../web/prompt-assembler.js", import.meta.url), "utf8");
let extension;
const requests = [];
vm.runInNewContext(
    source.replace(/^import .*;\n/, "").replaceAll("import.meta.url", '"https://comfy.example/extensions/custom-nodes/prompt-assembler.js"'),
    {
        app: { registerExtension(value) { extension = value; } },
        queueMicrotask,
        URL,
        fetch: async (url) => {
            requests.push(String(url));
            return { ok: true, json: async () => presets };
        },
    },
);
let calls = 0;
class Node {
    constructor() {
        this.widgets = [
            { name: "base_prompt", value: "  A portrait.  ", callback() { calls++; } },
            { name: "lighting", value: "Soft window light" },
            { name: "style", value: "Natural photography" },
            { name: "skin_texture", value: "Natural texture" },
            { name: "custom_lighting", value: "" },
            { name: "custom_style", value: "" },
            { name: "preview", value: "", inputEl: {} },
        ];
        this.inputs = [];
    }
    onExecuted() { calls++; }
    setDirtyCanvas() {}
}
await extension.beforeRegisterNodeDef(Node, { name: "LightingStylePromptAssembler" });
const node = new Node();
node.onNodeCreated();
const widget = (name) => node.widgets.find((item) => item.name === name);
const value = () => widget("preview").value;
assert.equal(value(), [
    "A portrait.", presets.lighting["Soft window light"],
    presets.style["Natural photography"], presets.skin_texture["Natural texture"],
].join("\n\n"));
assert.equal(widget("preview").inputEl.readOnly, true);
assert.equal(widget("preview").serializeValue(), "");
assert.equal(widget("preview").disabled, true);
widget("custom_lighting").value = "  A small reflector.\n ";
widget("custom_style").value = "  Muted colors.  ";
widget("custom_style").callback();
assert.match(value(), /A small reflector\.\n\n/);
assert.ok(value().endsWith("Muted colors."));
for (const name of ["lighting", "style", "skin_texture"]) widget(name).value = "None";
widget("base_prompt").value = "   ";
widget("custom_lighting").value = " \n ";
widget("custom_style").value = " Only custom. ";
widget("base_prompt").callback();
assert.equal(value(), "Only custom.");
assert.equal(calls, 1, "Existing widget callback preserved");
widget("custom_style").value = "";
node.onDrawForeground();
assert.equal(value(), "");
node.inputs.push({ name: "base_prompt", link: 1 });
node.onConnectionsChange(1, 0, true);
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Linked input — run to preview");
node.onExecuted({ assembled_prompt: ["A linked portrait."] });
assert.equal(value(), "Last run:\n\nA linked portrait.");
assert.equal(calls, 2, "Existing execution callback preserved");
widget("custom_style").value = "Another look.";
widget("custom_style").callback();
assert.equal(value(), "Linked input — run to preview");
node.onExecuted({ assembled_prompt: ["Another execution."] });
node.onConfigure({});
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Linked input — run to preview", "Reload must not restore stale preview");
node.onExecuted({ assembled_prompt: [""] });
assert.equal(value(), "Last run:\n\n", "Empty executed prompt remains valid");
node.inputs[0].link = null;
node.onConnectionsChange(1, 0, false);
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Another look.");
widget("lighting").value = "Unknown preset";
node.onDrawForeground();
assert.equal(value(), "Choose valid lighting, style, and skin texture presets.");
assert.deepEqual(requests, ["https://comfy.example/extensions/custom-nodes/photo_presets.json"]);
console.log("PASS: local assembly, shared presets, trimming, None presets, custom text, readonly preview, linked last-run display, invalidation, hook chaining, bundled-only fetch");
