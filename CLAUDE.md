# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ComfyUI custom node pack (V3 node API, `comfy_api.latest.io`), registered in `__init__.py` via `CustomNodesExtension.get_node_list`. Runs on the ComfyUI server 192.168.50.152 (Docker container `comfyui`, web/API on port 8190); there is no ComfyUI on this Mac.

## Nodes

- Saved workflows store widget values by position: never rename, reorder or remove inputs or existing option strings (e.g. `FORMATS` in `__init__.py`); only append.
- `web/photo_presets.json` is read by both `prompt_assembler.py` and `web/prompt-assembler.js`; a change affects both.
- Each `web/*.js` extension must keep exactly one single-line import (`import { app } from "../../scripts/app.js";`) as its first line: the `.mjs` tests strip that line and run the file in `vm`.

## Testing

- Frontend tests run locally: `node tests/<name>.mjs` (one file per extension in `web/`).
- Python tests import ComfyUI, so they only run inside the container, against the deployed copy (commit and push first). The `verify` skill has the exact command.
- When a new node is added, update the registered-node set in `tests/test_resolution_selector.py`, the node list in `.claude/skills/deploy/SKILL.md` step 4, and the README.
- End-to-end tests go through ComfyUI's queue API (`POST :8190/prompt`, poll `/history/<id>`). API prompts must include every input, including `advanced=True` ones; take defaults from `/object_info/<NodeId>`. Copy rendered images to `~/Downloads/`.

## Deploy

- The server folder is a git clone. `./deploy.sh` runs `git pull --ff-only` there and in the krea2-prompting skill clone (git-ignored `skills/krea2-prompting`, from github.com/rakshazi/krea2-prompting), then restarts `comfyui` only when the queue is empty. Only pushed commits reach the server; never copy files there with rsync/scp, it leaves the clone dirty and blocks `git pull`. Never restart ComfyUI (or run `deploy.sh` without `--no-restart`) unless the user said so: other jobs may be running.
- Python and `web/` changes need a restart plus a browser refresh. `krea2_writer_instructions.md` and the skill files are read on every call: `--no-restart` is enough.

## Krea 2 Prompt Writer

- Calls an OpenAI-compatible endpoint (default oMLX on 192.168.50.159, model Qwen3.6-35B-A3B-Uncensored-Heretic-MLX-4bit). The model thinks for up to ~3,000 tokens before answering; keep `max_tokens` well above that.
- `fingerprint_inputs` returns NaN for the model modes so ComfyUI never serves a cached prompt; keep that when changing the node.
- The test workflow in `example_workflows/` uses the KNPV4.1 LoRA, which undresses subjects regardless of the prompt; switch it off when judging clothing/explicitness of prompts.

## Repo

- Commit directly to `main`; short imperative subject lines ("Add …", "Support …").
