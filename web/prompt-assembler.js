import { app } from "../../scripts/app.js";

const NODE_ID = "LightingStylePromptAssembler";
const INPUTS = [
    "base_prompt", "lighting", "style", "skin_texture",
    "custom_lighting", "custom_style",
];

// Presets are bundled with this extension; no prompt text is sent over the network.
const presetsPromise = fetch(new URL("./photo_presets.json", import.meta.url))
    .then((response) => {
        if (!response.ok) throw new Error("Could not load bundled presets");
        return response.json();
    })
    .then((presets) => ({ presets }))
    .catch(() => ({ error: true }));

function joinParts(...parts) {
    return parts.map((part) => String(part ?? "").trim()).filter(Boolean).join("\n\n");
}

function assemblePrompt(values, presets) {
    for (const group of ["lighting", "style", "skin_texture"]) {
        if (!Object.hasOwn(presets[group] ?? {}, values[group])) return null;
    }
    const lighting = joinParts(presets.lighting[values.lighting], values.custom_lighting);
    const style = joinParts(
        presets.style[values.style], presets.skin_texture[values.skin_texture], values.custom_style,
    );
    return joinParts(values.base_prompt, lighting, style);
}

function installPreview(node, loaded) {
    const widget = (name) => node.widgets?.find((item) => item.name === name);
    const input = (name) => node.inputs?.find((item) => item.name === name);
    const preview = widget("preview");
    if (!preview) return;
    preview.disabled = true;
    preview.options ??= {};
    preview.options.read_only = true;
    if (preview.inputEl) preview.inputEl.readOnly = true;
    preview.callback = () => {};
    preview.serializeValue = () => "";

    let lastSignature;
    let lastResult;
    const signature = () => JSON.stringify(INPUTS.map((name) => [
        widget(name)?.value, input(name)?.link,
    ]));
    const setLabel = (text) => {
        if (preview.value === text) return;
        preview.value = text;
        node.setDirtyCanvas?.(true, true);
    };
    const refresh = () => {
        const current = signature();
        if (lastSignature !== current) {
            lastSignature = current;
            lastResult = undefined;
        }
        if (INPUTS.some((name) => input(name)?.link != null)) {
            setLabel(lastResult === undefined
                ? "Linked input — run to preview"
                : `Last run:\n\n${lastResult}`);
            return;
        }
        if (loaded.error) {
            setLabel("Preview unavailable: bundled presets could not be loaded. Run the node for its output.");
            return;
        }
        const values = Object.fromEntries(INPUTS.map((name) => [name, widget(name)?.value]));
        const prompt = assemblePrompt(values, loaded.presets);
        setLabel(prompt === null ? "Choose valid lighting, style, and skin texture presets." : prompt);
    };
    const invalidate = () => {
        lastResult = undefined;
        refresh();
    };
    for (const name of INPUTS) {
        const control = widget(name);
        if (!control) continue;
        const previous = control.callback;
        control.callback = function (...args) {
            const result = previous?.apply(this, args);
            invalidate();
            return result;
        };
    }
    const previousConnections = node.onConnectionsChange;
    node.onConnectionsChange = function (...args) {
        const result = previousConnections?.apply(this, args);
        invalidate();
        queueMicrotask(invalidate);
        return result;
    };
    const previousConfigure = node.onConfigure;
    node.onConfigure = function (...args) {
        const result = previousConfigure?.apply(this, args);
        invalidate();
        queueMicrotask(invalidate);
        return result;
    };
    const previousDraw = node.onDrawForeground;
    node.onDrawForeground = function (...args) {
        const result = previousDraw?.apply(this, args);
        refresh();
        return result;
    };
    const previousExecuted = node.onExecuted;
    node.onExecuted = function (message, ...args) {
        const result = previousExecuted?.call(this, message, ...args);
        refresh();
        const prompt = message?.assembled_prompt?.[0];
        lastResult = typeof prompt === "string" ? prompt : undefined;
        refresh();
        return result;
    };
    refresh();
}

app.registerExtension({
    name: "comfyui-custom-nodes.lighting-style-prompt-preview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const loaded = await presetsPromise;
        const previous = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = previous?.apply(this, args);
            installPreview(this, loaded);
            return result;
        };
    },
});
