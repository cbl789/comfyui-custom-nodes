import { app } from "../../scripts/app.js";

const NODE_ID = "LoraSidecarLoader";
const ROUTE = "/comfyui-custom-nodes/sidecar";
const PLACEHOLDER = "Choose a LoRA to read its sidecar.";

// The preview is filled by the backend: as soon as a LoRA is chosen, and again
// after every run. It is never serialized into the workflow, so a saved
// workflow does not carry stale metadata.
function makeReadOnly(widget) {
    widget.disabled = true;
    widget.options ??= {};
    widget.options.read_only = true;
    if (widget.inputEl) widget.inputEl.readOnly = true;
    widget.callback = () => {};
    widget.serializeValue = () => "";
}

function findWidget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function setPreview(node, text) {
    const preview = findWidget(node, "preview");
    if (!preview || preview.value === text) return;
    preview.value = text;
    node.setDirtyCanvas?.(true, true);
}

async function refreshPreview(node) {
    const name = findWidget(node, "lora_name")?.value;
    if (!name) {
        setPreview(node, PLACEHOLDER);
        return;
    }
    // Ignore a reply that arrives after the selection changed again.
    node.__sidecarRequest = (node.__sidecarRequest ?? 0) + 1;
    const request = node.__sidecarRequest;
    try {
        const reply = await fetch(ROUTE + "?name=" + encodeURIComponent(name));
        if (request !== node.__sidecarRequest) return;
        if (!reply.ok) {
            setPreview(node, "No sidecar metadata for " + name);
            return;
        }
        const data = await reply.json();
        if (request !== node.__sidecarRequest) return;
        setPreview(node, typeof data.summary === "string" ? data.summary : PLACEHOLDER);
    } catch (error) {
        if (request === node.__sidecarRequest) setPreview(node, "Could not read sidecar metadata.");
    }
}

function install(node) {
    const preview = findWidget(node, "preview");
    if (preview) {
        makeReadOnly(preview);
        if (!preview.value) preview.value = PLACEHOLDER;
    }
    const lora = findWidget(node, "lora_name");
    if (lora) {
        const previous = lora.callback;
        lora.callback = function (...args) {
            const result = previous?.apply(this, args);
            refreshPreview(node);
            return result;
        };
    }
    refreshPreview(node);
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
        const previousConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = previousConfigure?.apply(this, args);
            refreshPreview(this);
            return result;
        };
        const previousExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message, ...args) {
            const result = previousExecuted?.call(this, message, ...args);
            const text = message?.lora_sidecar?.[0];
            if (typeof text === "string") setPreview(this, text);
            return result;
        };
    },
});
