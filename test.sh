#!/bin/bash
set +e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

info() {
    echo -e "${YELLOW}ℹ INFO${NC}: $1"
}

# Test 1: Prerequisites
echo ""
echo "=== Testing Prerequisites ==="
if which k3d >/dev/null 2>&1; then pass "k3d installed"; else fail "k3d not found (install: brew install k3d)"; fi
if which helm >/dev/null 2>&1; then pass "helm installed"; else fail "helm not found (install: brew install helm)"; fi
if which kubectl >/dev/null 2>&1; then pass "kubectl installed"; else fail "kubectl not found (install: brew install kubectl)"; fi
if which python3 >/dev/null 2>&1; then pass "python3 installed"; else fail "python3 not found"; fi
if which docker >/dev/null 2>&1; then pass "docker installed"; else fail "docker not found"; fi

# Test 2: File structure
echo ""
echo "=== Testing File Structure ==="
test -f "Makefile" && pass "Makefile exists" || fail "Makefile missing"
test -f "README.md" && pass "README.md exists" || fail "README.md missing"
test -f "MEDIUM_ARTICLE_DRAFT.md" && pass "Article exists" || fail "Article missing"
test -d "keda" && pass "keda/ directory exists" || fail "keda/ missing"
test -d "workload" && pass "workload/ directory exists" || fail "workload/ missing"
test -d "cluster" && pass "cluster/ directory exists" || fail "cluster/ missing"
test -d "load-generator" && pass "load-generator/ directory exists" || fail "load-generator/ missing"
test -d "analysis" && pass "analysis/ directory exists" || fail "analysis/ missing"

# Test 3: Kubernetes cluster
echo ""
echo "=== Testing Kubernetes Cluster ==="
if kubectl get nodes >/dev/null 2>&1; then
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    if [ "$NODE_COUNT" -ge 1 ]; then
        pass "Cluster accessible ($NODE_COUNT nodes)"
    else
        fail "Cluster has no nodes"
    fi
else
    fail "Cannot connect to cluster (run: make cluster-up)"
fi

# Test 4: KEDA installation
echo ""
echo "=== Testing KEDA ==="
if kubectl get namespace keda >/dev/null 2>&1; then
    pass "KEDA namespace exists"

    KEDA_PODS=$(kubectl get pods -n keda -l app.kubernetes.io/name=keda-operator --no-headers 2>/dev/null | wc -l)
    if [ "$KEDA_PODS" -gt 0 ]; then
        pass "KEDA operator pod running"
    else
        warn "KEDA operator pod not found (run: make keda-up)"
    fi
else
    warn "KEDA namespace not found (run: make keda-up)"
fi

# Test 5: Workload image
echo ""
echo "=== Testing Workload Image ==="
if docker images | grep -q "keda-demo"; then
    pass "Workload image built locally"
else
    warn "Workload image not found (run: make build)"
fi

if kubectl get nodes >/dev/null 2>&1; then
    # Check if image can be pulled in cluster
    IMAGE_CHECK=$(kubectl describe pod -n demo --all 2>/dev/null | grep -c "keda-demo" 2>/dev/null || echo "0")
    if [ -n "$IMAGE_CHECK" ] && [ "$IMAGE_CHECK" -gt 0 ]; then
        pass "Workload image running in cluster"
    else
        info "Workload image not yet tested in cluster (run: make demo-sqs N=1)"
    fi
fi

# Test 6: Python dependencies
echo ""
echo "=== Testing Python Dependencies ==="
python3 -c "import boto3" >/dev/null 2>&1 && pass "boto3 installed" || fail "boto3 not found (pip install boto3)"
python3 -c "import json" >/dev/null 2>&1 && pass "json (stdlib) available" || fail "json not found (should be stdlib)"

# Test 7: Makefile targets
echo ""
echo "=== Testing Makefile Targets ==="
make help >/dev/null 2>&1 && pass "make help works" || fail "make help failed"

# Test 8: Scripts
echo ""
echo "=== Testing Scripts ==="
python3 load-generator/send_messages.py --help >/dev/null 2>&1 && pass "load-generator works" || fail "load-generator failed"
python3 analysis/cost_model.py >/dev/null 2>&1 && pass "cost-model works" || fail "cost-model failed"
python3 -c "import workload.handler" >/dev/null 2>&1 || python3 workload/handler.py >/dev/null 2>&1 || warn "handler.py could not be validated (requires env vars)"

# Test 9: Dev environment
echo ""
echo "=== Testing Dev Environment ==="
test -f ".devcontainer/devcontainer.json" && pass "devcontainer.json exists" || fail "devcontainer.json missing"
test -f ".devcontainer/post-create.sh" && pass "post-create.sh exists" || fail "post-create.sh missing"
test -f "devbox.json" && pass "devbox.json exists" || fail "devbox.json missing"
test -f ".gitignore" && pass ".gitignore exists" || fail ".gitignore missing"

# Test 10: ScaledJob manifests
echo ""
echo "=== Testing Kubernetes Manifests ==="
kubectl apply -f keda/scaled-job-cron.yaml -n demo --dry-run=client >/dev/null 2>&1 && pass "scaled-job-cron.yaml is valid" || fail "scaled-job-cron.yaml has syntax errors"
kubectl apply -f keda/scaled-job-sqs.yaml -n demo --dry-run=client >/dev/null 2>&1 && pass "scaled-job-sqs.yaml is valid" || fail "scaled-job-sqs.yaml has syntax errors"
kubectl apply -f keda/scaled-job-sns.yaml -n demo --dry-run=client >/dev/null 2>&1 && pass "scaled-job-sns.yaml is valid" || fail "scaled-job-sns.yaml has syntax errors"

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}PASSED${NC}: $PASSED"
echo -e "${RED}FAILED${NC}: $FAILED"
echo -e "${YELLOW}Total Tests${NC}: $((PASSED + FAILED))"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed! ✓${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. make cluster-up          # If cluster not running"
    echo "  2. make keda-up             # If KEDA not running"
    echo "  3. make build               # If image not built"
    echo "  4. make demo-sqs N=5        # Test SQS trigger"
    echo "  5. kubectl get jobs -n demo # Watch jobs complete"
    exit 0
else
    echo -e "\n${RED}Some tests failed. See above for details.${NC}"
    exit 1
fi
