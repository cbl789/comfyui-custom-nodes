---
name: deploy
description: Update this node pack and the krea2-prompting skill on the ComfyUI server 192.168.50.152 with git pull, restart comfyui if its queue is empty, and confirm the nodes load. Pass --no-restart to only pull.
disable-model-invocation: true
---

Deploy the node pack. Arguments: $ARGUMENTS

1. Run the local frontend tests first: `for f in tests/*.mjs; do node "$f" || exit 1; done`. Stop and report if one fails.
2. Only pushed commits reach the server. If `git status` shows uncommitted changes or commits not on `origin/main`, tell the user and ask whether to commit and push first.
3. Run `./deploy.sh $ARGUMENTS` from the repo root. It prints the deployed commit and skill commit.
   - If it reports jobs running or queued, do not restart by any other means. Tell the user and stop.
4. Unless `--no-restart` was passed, confirm every node is registered:
   `for n in ResolutionSelectorWithLatent LightingStylePromptAssembler Krea2PromptWriter; do curl -s -m 5 http://192.168.50.152:8190/object_info/$n | grep -q "\"$n\"" && echo "ok $n" || echo "MISSING $n"; done`
   If a node is missing, show `ssh christian@192.168.50.152 'docker logs --tail 80 comfyui' 2>&1 | grep -iA5 "comfyui-custom-nodes\|Traceback"`.
5. Report the deployed commits, whether ComfyUI restarted, and remind the user to refresh the browser.
