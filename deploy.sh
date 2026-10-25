#!/bin/zsh
# Copy this node pack and the krea2-prompting skill to the ComfyUI server, then restart
# the ComfyUI container if its queue is empty. Usage: ./deploy.sh [--no-restart]
set -e
HOST=christian@192.168.50.152
DEST=/home/christian/ai/comfyui/custom_nodes/comfyui-custom-nodes
SKILL=$HOME/repos/krea2-prompting
COMFY=http://192.168.50.152:8190
cd "$(dirname "$0")"

rsync -a --exclude .git --exclude skills --exclude __pycache__ --exclude deploy.sh ./ "$HOST:$DEST/"
ssh "$HOST" "mkdir -p $DEST/skills"
rsync -a --delete --exclude .git "$SKILL/" "$HOST:$DEST/skills/krea2-prompting/"
echo "Copied node pack and skill to $HOST:$DEST"

[[ "$1" == "--no-restart" ]] && exit 0
busy=$(curl -s -m 5 "$COMFY/queue" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['queue_running'])+len(d['queue_pending']))")
if [[ "$busy" != "0" ]]; then
  echo "ComfyUI has $busy job(s) running or queued; not restarting. Run again when it is idle."
  exit 1
fi
ssh "$HOST" "docker restart comfyui-new" >/dev/null
for i in {1..60}; do
  sleep 5
  if curl -s -m 3 "$COMFY/object_info/Krea2PromptWriter" | grep -q Krea2PromptWriter; then
    echo "ComfyUI restarted; Krea 2 Prompt Writer is available. Refresh the browser."
    exit 0
  fi
done
echo "ComfyUI did not report the node within 5 minutes; check: ssh $HOST 'docker logs --tail 50 comfyui-new'"
exit 1
