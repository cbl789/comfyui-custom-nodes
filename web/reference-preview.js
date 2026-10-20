import { app } from "../../scripts/app.js";

const NODE_ID = "ResolutionSelectorWithLatent";

function roundHalfToEven(value) {
    const floor = Math.floor(value);
    return value - floor === 0.5 ? floor + (floor % 2) : Math.round(value);
}

function dimensionLabel(width, height) {
    return `${width} × ${height} · ${(width * height / (1024 * 1024)).toFixed(2)} MP`;
}

function installPreview(node) {
    const widget = (name) => node.widgets?.find((item) => item.name === name);
    const input = (name) => node.inputs?.find((item) => item.name === name);
    const connected = (name) => input(name)?.link != null;
    const preview = widget("preview");
    if (!preview) return;
    preview.disabled = true;
    preview.options ??= {};
    preview.options.read_only = true;
    preview.callback = () => {};
    // Preserve this widget's serialization position without saving execution details.
    preview.serializeValue = () => "";

    // Do not persist reference dimensions. An upstream image may change between runs.
    let lastSignature;
    let lastResult;
    const signature = () => JSON.stringify([
        ...["aspect_ratio", "megapixels", "multiple"].map((name) => [
            widget(name)?.value, input(name)?.link,
        ]),
        input("reference_image")?.link,
    ]);
    const setLabel = (label) => {
        if (preview.value === label) return;
        preview.value = label;
        node.setDirtyCanvas?.(true, true);
    };
    const refresh = () => {
        const current = signature();
        if (lastSignature !== current) {
            lastSignature = current;
            lastResult = undefined;
        }
        const reference = connected("reference_image");
        const aspect = widget("aspect_ratio");
        if (aspect) aspect.disabled = reference;
        if (reference) {
            setLabel(lastResult
                ? `Last run: ${dimensionLabel(lastResult.width, lastResult.height)}`
                : "Reference connected · run to calculate");
            return;
        }
        // Linked scalar inputs are only resolved by the backend at execution time.
        if (["aspect_ratio", "megapixels", "multiple"].some(connected)) {
            setLabel(lastResult
                ? `Last run: ${dimensionLabel(lastResult.width, lastResult.height)}`
                : "Linked controls · run to calculate");
            return;
        }
        const match = /^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)/.exec(String(aspect?.value));
        const megapixels = Number(widget("megapixels")?.value);
        const multiple = Number(widget("multiple")?.value);
        if (!match || !Number.isFinite(megapixels) || megapixels <= 0 ||
            !Number.isFinite(multiple) || multiple <= 0) {
            setLabel("—");
            return;
        }
        const ratioWidth = Number(match[1]);
        const ratioHeight = Number(match[2]);
        if (ratioWidth <= 0 || ratioHeight <= 0) {
            setLabel("—");
            return;
        }
        const scale = Math.sqrt(megapixels * 1024 * 1024 / (ratioWidth * ratioHeight));
        const width = roundHalfToEven(ratioWidth * scale / multiple) * multiple;
        const height = roundHalfToEven(ratioHeight * scale / multiple) * multiple;
        setLabel(width > 0 && height > 0 ? dimensionLabel(width, height) : "—");
    };
    const invalidate = () => {
        lastResult = undefined;
        refresh();
    };
    for (const name of ["aspect_ratio", "megapixels", "multiple"]) {
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
        // Some frontend versions notify before updating the input's link.
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
        const resolution = message?.resolution?.[0];
        const valid = resolution && [resolution.width, resolution.height].every(
            (value) => Number.isInteger(value) && value > 0,
        );
        // A queued execution may finish after the controls have been edited.
        const sameControls = ["megapixels", "multiple"].every((name) =>
            connected(name) || resolution?.[name] === Number(widget(name)?.value),
        );
        const referenceResult = Number.isInteger(resolution?.reference_width) &&
            resolution.reference_width > 0 && Number.isInteger(resolution?.reference_height) &&
            resolution.reference_height > 0;
        const sameMode = connected("reference_image") === referenceResult;
        if (valid && sameControls && sameMode) lastResult = resolution;
        else lastResult = undefined;
        refresh();
        return result;
    };
    refresh();
}

app.registerExtension({
    name: "comfyui-custom-nodes.reference-resolution-preview",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_ID) return;
        const previous = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = previous?.apply(this, args);
            installPreview(this);
            return result;
        };
    },
});
