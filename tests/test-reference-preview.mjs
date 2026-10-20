import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/reference-preview.js", import.meta.url), "utf8");
let extension;
vm.runInNewContext(source.replace(/^import .*;\n/, ""), {
    app: { registerExtension(value) { extension = value; } },
    queueMicrotask,
});
class Node {
    constructor() {
        this.widgets = [
            { name: "aspect_ratio", value: "1:1 (Square)" },
            { name: "megapixels", value: 1 },
            { name: "multiple", value: 8 },
            { name: "preview", value: "" },
        ];
        this.inputs = [{ name: "reference_image", link: null }];
    }
    setDirtyCanvas() {}
}
extension.beforeRegisterNodeDef(Node, { name: "ResolutionSelectorWithLatent" });
const node = new Node();
node.onNodeCreated();
const widget = (name) => node.widgets.find((item) => item.name === name);
const value = () => widget("preview").value;
assert.equal(value(), "1024 × 1024 · 1.00 MP");
assert.equal(widget("preview").disabled, true);
assert.equal(widget("preview").serializeValue(), "");
// Exact tie of 2.5 rounds to even 2, matching Python, not Math.round's 3.
widget("megapixels").value = 400 / (1024 * 1024);
widget("megapixels").callback();
assert.equal(value(), "16 × 16 · 0.00 MP");
widget("megapixels").value = 1;
node.inputs[0].link = 1;
node.onConnectionsChange(1, 0, true);
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Reference connected · run to calculate");
assert.equal(widget("aspect_ratio").disabled, true);
node.onExecuted({ resolution: [{ width: 1024, height: 1024, megapixels: 1, multiple: 8,
    reference_width: null, reference_height: null }] });
assert.equal(value(), "Reference connected · run to calculate", "Ignore queued manual-mode result");
const message = { resolution: [{ width: 832, height: 1248, megapixels: 1, multiple: 8,
    reference_width: 1000, reference_height: 1500 }] };
node.onExecuted(message);
assert.match(value(), /^Last run: 832 × 1248/);
widget("megapixels").value = 2;
widget("megapixels").callback();
assert.equal(value(), "Reference connected · run to calculate");
node.onExecuted(message);
assert.equal(value(), "Reference connected · run to calculate", "Ignore stale queued result");
widget("megapixels").value = 1;
widget("megapixels").callback();
node.onExecuted(message);
widget("multiple").value = 16;
widget("multiple").callback();
assert.equal(value(), "Reference connected · run to calculate");
widget("multiple").value = 8;
node.onDrawForeground();
node.onExecuted(message);
node.onConfigure({});
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Reference connected · run to calculate", "Reload must not reuse saved reference preview");
node.inputs[0].link = null;
node.onConnectionsChange(1, 0, false);
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "1024 × 1024 · 1.00 MP");
assert.equal(widget("aspect_ratio").disabled, false);
node.inputs.push({ name: "megapixels", link: 2 });
node.onConnectionsChange(1, 1, true);
await new Promise((resolve) => queueMicrotask(resolve));
assert.equal(value(), "Linked controls · run to calculate");
node.onExecuted({ resolution: [{ ...message.resolution[0], reference_width: null,
    reference_height: null }] });
assert.match(value(), /^Last run: 832 × 1248/);
console.log("PASS: manual preview, half-even rounding, reference pending/results, invalidation, reload, disconnect, linked controls");
