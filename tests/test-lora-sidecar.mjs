import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/lora-sidecar.js", import.meta.url), "utf8");
const calls = [];
let reply = {
    ok: true,
    json: async () => ({ name: "x", found: true, summary: "LoRA: x\nTriggers: famegrid", triggers: ["famegrid"] }),
};
let extension;
vm.runInNewContext(source.replace(/^import .*;\n/, ""), {
    app: { registerExtension(value) { extension = value; } },
    fetch: async (url) => { calls.push(String(url)); return reply; },
});

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const LORA = "krea2/cinematic movie still.safetensors";

class Node {
    constructor() {
        this.widgets = [
            { name: "lora_name", value: LORA, callback() { calls.push("previous-callback"); } },
            { name: "preview", value: "" },
        ];
        this.dirty = 0;
        this.executed = 0;
    }
    setDirtyCanvas() { this.dirty++; }
    onExecuted() { this.executed++; }
}
await extension.beforeRegisterNodeDef(Node, { name: "LoraSidecarLoader" });

const node = new Node();
node.onNodeCreated();
const lora = () => node.widgets[0];
const preview = () => node.widgets[1];

assert.equal(preview().disabled, true);
assert.equal(preview().options.read_only, true);
assert.equal(preview().serializeValue(), "");

await tick();
assert.equal(calls.length, 1, "the current LoRA is read on creation");
assert.ok(calls[0].includes(encodeURIComponent(LORA)), "the name is URL encoded");
assert.match(preview().value, /Triggers: famegrid/, "summary shown before any run");

// Choosing another LoRA refreshes without waiting for execution.
lora().value = "loras/other.safetensors";
lora().callback();
assert.equal(calls.length, 3, "previous widget callback is preserved");
await tick();
assert.equal(calls[2], "/comfyui-custom-nodes/sidecar?name=loras%2Fother.safetensors");

// A LoRA without a sidecar says so instead of showing stale text.
reply = { ok: false, json: async () => ({ error: "unknown lora" }) };
lora().value = "missing.safetensors";
lora().callback();
await tick();
assert.equal(preview().value, "No sidecar metadata for missing.safetensors");

// The executed payload still wins after a run.
node.onExecuted({ lora_sidecar: ["LoRA: z\nTriggers: q"] });
assert.match(preview().value, /Triggers: q/);
assert.equal(node.executed, 1, "Existing onExecuted hook preserved");
node.onExecuted({ other: ["ignored"] });
assert.match(preview().value, /Triggers: q/);

// A reloaded workflow refreshes the preview too.
reply = { ok: true, json: async () => ({ summary: "LoRA: reloaded" }) };
node.onConfigure({});
await tick();
assert.equal(preview().value, "LoRA: reloaded");

// Another node type gains no hook at all.
class OtherNode {
    constructor() { this.widgets = [{ name: "preview", value: "" }]; }
    setDirtyCanvas() {}
}
await extension.beforeRegisterNodeDef(OtherNode, { name: "NotThisNode" });
assert.equal(OtherNode.prototype.onNodeCreated, undefined, "Other nodes gain no hook");

console.log("PASS: preview on selection, URL encoding, missing sidecar, execution, reload, hook chaining");
