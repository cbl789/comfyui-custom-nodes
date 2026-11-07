---
name: verify
description: Run all tests of this node pack — frontend tests locally with Node.js and the Python tests inside the comfyui container on 192.168.50.152. Use after changing nodes, tests or web/ extensions; the Python tests need the changes pushed.
---

1. Frontend tests (local): `for f in tests/*.mjs; do node "$f" || echo "FAILED $f"; done`
2. Python tests need ComfyUI, which only exists in the container, and they run against the deployed copy, which comes from `git pull`. Commit and push the changes first (commits go to `main`; ask the user before committing if they did not ask for it), then pull without restarting and run them:
   ```sh
   ./deploy.sh --no-restart
   ssh christian@192.168.50.152 'cd /home/christian/ai/comfyui/custom_nodes/comfyui-custom-nodes && docker exec -w $PWD comfyui sh -c "COMFYUI_PATH=/home/christian/ai/comfyui /home/christian/ai/comfyui/venv/bin/python -m unittest discover -s tests -p \"test_*.py\" 2>&1 | grep -v DeprecationWarning | tail -25"'
   ```
   Never restart ComfyUI here. The tests import the files directly, so a restart is not needed for them; the running ComfyUI keeps the old Python code until the user deploys with a restart.
3. Report: number of tests run, failures with their message, and whether the running ComfyUI is now behind the tested code (Python or `web/` changes not yet restarted).
