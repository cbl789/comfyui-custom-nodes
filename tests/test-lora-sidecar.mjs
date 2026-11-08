import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/lora-sidecar.js", import.meta.url), "utf8");
let extension;
vm.runInNewContext(source.replace(/^import .*;\n/, ""), {
    app: { registerExtension(value) { extension = value; } },
});

class Node {
    constructor() {
        this.widgets = [{ name: "preview", value: "" }];
        this.dirty = 0;
        this.executed = 0;
    }
    setDirtyCanvas() { this.dirty++; }
    onExecuted() { this.executed++; }
}
await extension.beforeRegisterNodeDef(Node, { name: "LoraSidecarLoader" });

const node = new Node();
node.onNodeCreated();
const widget = () => node.widgets[0];
assert.equal(widget().disabled, true);
assert.equal(widget().options.read_only, true);
assert.equal(widget().serializeValue(), "");
assert.equal(widget().value, "Run to read the sidecar metadata.");

node.onExecuted({ lora_sidecar: ["LoRA: loras/krea2/x.safetensors\nTriggers: famegrid"] });
assert.match(widget().value, /^LoRA: .*Triggers: famegrid$/s);
assert.equal(node.dirty, 1);
assert.equal(node.executed, 1, "Existing onExecuted hook preserved");

node.onExecuted({ other: ["ignored"] });
assert.match(widget().value, /famegrid/);
assert.equal(node.dirty, 1, "A message from another node changes nothing");

// Another node type gains no hook at all.
class OtherNode {
    constructor() { this.widgets = [{ name: "preview", value: "" }]; }
    setDirtyCanvas() {}
}
await extension.beforeRegisterNodeDef(OtherNode, { name: "NotThisNode" });
assert.equal(OtherNode.prototype.onNodeCreated, undefined, "Other nodes gain no hook");
assert.equal(new OtherNode().widgets[0].disabled, undefined);
console.log("PASS: read-only preview, backend summary, hook chaining, other nodes untouched");
