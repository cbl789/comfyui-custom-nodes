#!/bin/zsh
# Update the node pack and the krea2-prompting skill on the ComfyUI server with git pull, then
# restart the ComfyUI container if its queue is empty. Usage: ./deploy.sh [--no-restart]
# Only pushed commits reach the server: commit and push first.
set -e
HOST=christian@192.168.50.152
DEST=/home/christian/ai/comfyui/custom_nodes/comfyui-custom-nodes
SKILL_REPO=https://github.com/rakshazi/krea2-prompting.git
COMFY=http://192.168.50.152:8190
cd "$(dirname "$0")"

git fetch -q origin
if [[ -n "$(git status --porcelain)" || "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo "Warning: local changes or commits are not on origin/main; the server only gets what is pushed."
fi

ssh "$HOST" "set -e; cd $DEST; git pull -q --ff-only; git log --oneline -1
  if [ -d skills/krea2-prompting/.git ]; then git -C skills/krea2-prompting pull -q --ff-only
  else git clone -q $SKILL_REPO skills/krea2-prompting; fi
  echo \"skill: \$(git -C skills/krea2-prompting log --oneline -1)\""

[[ "$1" == "--no-restart" ]] && exit 0
busy=$(curl -s -m 5 "$COMFY/queue" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['queue_running'])+len(d['queue_pending']))")
if [[ "$busy" != "0" ]]; then
  echo "ComfyUI has $busy job(s) running or queued; not restarting. Run again when it is idle."
  exit 1
fi
ssh "$HOST" "docker restart comfyui" >/dev/null
for i in {1..60}; do
  sleep 5
  if curl -s -m 3 "$COMFY/object_info/Krea2PromptWriter" | grep -q Krea2PromptWriter; then
    echo "ComfyUI restarted; Krea 2 Prompt Writer is available. Refresh the browser."
    exit 0
  fi
done
echo "ComfyUI did not report the node within 5 minutes; check: ssh $HOST 'docker logs --tail 50 comfyui'"
exit 1
