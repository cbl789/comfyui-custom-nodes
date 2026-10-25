import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/krea2-prompt-writer.js", import.meta.url), "utf8");
let extension;
vm.runInNewContext(source.replace(/^import .*;\n/, ""), {
    app: { registerExtension(value) { extension = value; } },
});

class Node {
    constructor() {
        this.widgets = ["mode", "brief", "change", "current_prompt", "current_aspect"]
            .map((name) => ({ name, value: "" }));
        this.widgets[0].value = "Apply change";
        this.widgets[2].value = "red hair";
        this.dirty = 0;
    }
    setDirtyCanvas() { this.dirty++; }
}
await extension.beforeRegisterNodeDef(Node, { name: "Krea2PromptWriter" });
const value = (node, name) => node.widgets.find((item) => item.name === name).value;

// Apply change: prompt and aspect filled, change cleared, mode switched to Keep.
const node = new Node();
node.onExecuted({ krea2_writer: [{ prompt: "A photo with red hair.", aspect: "2:3 (Portrait Photo)", mode: "Apply change" }] });
assert.equal(value(node, "current_prompt"), "A photo with red hair.");
assert.equal(value(node, "current_aspect"), "2:3 (Portrait Photo)");
assert.equal(value(node, "change"), "");
assert.equal(value(node, "mode"), "Keep current prompt");
assert.ok(node.dirty > 0);

// Write new prompt keeps whatever is in the change field.
const second = new Node();
second.widgets[0].value = "Write new prompt";
second.onExecuted({ krea2_writer: [{ prompt: "New.", aspect: "3:2 (Photo)", mode: "Write new prompt" }] });
assert.equal(value(second, "change"), "red hair");
assert.equal(value(second, "mode"), "Keep current prompt");

// Messages from other nodes are ignored.
const third = new Node();
third.onExecuted({ text: ["x"] });
assert.equal(value(third, "mode"), "Apply change");
console.log("krea2-prompt-writer frontend tests passed");
