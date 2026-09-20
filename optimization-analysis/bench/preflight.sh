#!/usr/bin/env bash
# Read-only checks. Writes to data/preflight.txt
cd "$(dirname "$0")"; mkdir -p data
{
echo "date: $(date -u +%FT%TZ)"
echo "--- tools"; for c in kubectl docker k3d python3; do printf "%s: " $c; which $c || echo MISSING; done
echo "--- context"; kubectl config current-context
echo "--- nodes"; kubectl get nodes -o wide
echo "--- keda"; kubectl get deploy -n keda 2>&1; kubectl get crd scaledjobs.keda.sh 2>&1 | head -2
echo "--- keda image"; kubectl get deploy -n keda keda-operator -o jsonpath='{.spec.template.spec.containers[0].image}' 2>&1; echo
echo "--- docker nodes"; docker ps --format '{{.Names}}  {{.Image}}' 2>&1 | head -20
echo "--- crictl on node"; n=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'k3d-.*-(agent|server)-0' | head -1); echo "node=$n"; docker exec "$n" sh -c 'which crictl; crictl images 2>&1 | head -8' 2>&1
echo "--- existing bench ns"; kubectl get all -n bench 2>&1 | head
echo "--- existing scaledjobs"; kubectl get scaledjob -A 2>&1 | head
echo "--- python"; python3 --version
} > data/preflight.txt 2>&1
echo done
