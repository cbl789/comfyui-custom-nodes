import { app } from "../../scripts/app.js";

const NODE_ID = "Krea2PromptWriter";
const KEEP = "Keep current prompt";

// After a run, show the prompt that went to the image and switch to Keep, so the
// next run renders the same prompt until the user asks for a new one or a change.
function applyResult(node, result) {
    if (!result || typeof result.prompt !== "string") return;
    const widget = (name) => node.widgets?.find((item) => item.name === name);
    const set = (name, value) => {
        const control = widget(name);
        if (control && control.value !== value) control.value = value;
    };
    set("current_prompt", result.prompt);
    if (typeof result.aspect === "string") set("current_aspect", result.aspect);
    if (result.mode === "Apply change") set("change", "");
    set("mode", KEEP);
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "comfyui-custom-nodes.krea2-prompt-writer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const previousExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message, ...args) {
            const result = previousExecuted?.call(this, message, ...args);
            applyResult(this, message?.krea2_writer?.[0]);
            return result;
        };
    },
});
