import { app } from "../../scripts/app.js";

const NODE_ID = "LoraSidecarLoader";
const PLACEHOLDER = "Run to read the sidecar metadata.";

// The preview is filled by the backend after execution; it is never serialized
// into the workflow, so a saved workflow does not carry stale metadata.
function makeReadOnly(widget) {
    widget.disabled = true;
    widget.options ??= {};
    widget.options.read_only = true;
    if (widget.inputEl) widget.inputEl.readOnly = true;
    widget.callback = () => {};
    widget.serializeValue = () => "";
}

function install(node) {
    const widget = node.widgets?.find((item) => item.name === "preview");
    if (!widget) return;
    makeReadOnly(widget);
    if (!widget.value) widget.value = PLACEHOLDER;
}

app.registerExtension({
    name: "comfyui-custom-nodes.lora-sidecar",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const previousCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = previousCreated?.apply(this, args);
            install(this);
            return result;
        };
        const previousExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message, ...args) {
            const result = previousExecuted?.call(this, message, ...args);
            const text = message?.lora_sidecar?.[0];
            if (typeof text === "string") {
                const widget = this.widgets?.find((item) => item.name === "preview");
                if (widget && widget.value !== text) {
                    widget.value = text;
                    this.setDirtyCanvas?.(true, true);
                }
            }
            return result;
        };
    },
});
