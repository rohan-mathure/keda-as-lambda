#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
kubectl apply -f manifests.yaml
kubectl -n bench create configmap watcher-script --from-file=watcher.py --dry-run=client -o yaml | kubectl apply -f -
kubectl -n bench create configmap worker-script --from-file=worker.py --dry-run=client -o yaml | kubectl apply -f -
kubectl -n bench rollout restart deploy/watcher >/dev/null
for d in redis pusher watcher; do kubectl -n bench rollout status deploy/$d --timeout=180s; done
echo "setup ok"
