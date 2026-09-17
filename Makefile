.PHONY: cluster-up cluster-down localstack-up init-aws keda-up build demo-sqs demo-sns cost-model clean

CLUSTER_NAME ?= keda-lambda
NAMESPACE_DEMO ?= demo
NAMESPACE_KEDA ?= keda
NAMESPACE_LOCALSTACK ?= localstack
DOCKER_IMAGE ?= keda-demo:latest

# Cluster setup
cluster-up:
	@echo "Creating k3d cluster..."
	k3d cluster create --config cluster/k3d-config.yaml
	@echo "Waiting for nodes ready..."
	kubectl wait --for=condition=Ready node --all --timeout=60s
	@echo "Cluster ready."

cluster-down:
	@echo "Destroying k3d cluster..."
	k3d cluster delete $(CLUSTER_NAME)

# LocalStack setup
localstack-up:
	@echo "Creating localstack namespace..."
	kubectl create namespace $(NAMESPACE_LOCALSTACK) --dry-run=client -o yaml | kubectl apply -f -
	@echo "Deploying LocalStack..."
	kubectl apply -f cluster/localstack/deployment.yaml -n $(NAMESPACE_LOCALSTACK)
	kubectl apply -f cluster/localstack/service.yaml -n $(NAMESPACE_LOCALSTACK)
	@echo "Waiting for LocalStack pod ready..."
	kubectl wait --for=condition=ready pod -l app=localstack -n $(NAMESPACE_LOCALSTACK) --timeout=60s
	@echo "LocalStack ready."

init-aws:
	@echo "Creating SQS queues and SNS topic..."
	sleep 2  # Give LocalStack API a moment
	awslocal --endpoint-url http://localhost:4566 sqs create-queue --queue-name demo-queue --region us-east-1 || true
	awslocal --endpoint-url http://localhost:4566 sqs create-queue --queue-name demo-sns-queue --region us-east-1 || true
	awslocal --endpoint-url http://localhost:4566 sns create-topic --name demo-topic --region us-east-1 || true
	@echo "Creating SNS subscription to SQS..."
	awslocal --endpoint-url http://localhost:4566 sns subscribe \
		--topic-arn arn:aws:sns:us-east-1:000000000000:demo-topic \
		--protocol sqs \
		--notification-endpoint arn:aws:sqs:us-east-1:000000000000:demo-sns-queue \
		--region us-east-1 || true
	@echo "AWS resources created."

# KEDA setup
keda-up:
	@echo "Adding KEDA Helm repo..."
	helm repo add kedacore https://kedacore.github.io/charts || true
	helm repo update
	@echo "Creating keda namespace..."
	kubectl create namespace $(NAMESPACE_KEDA) --dry-run=client -o yaml | kubectl apply -f -
	@echo "Installing KEDA..."
	helm install keda kedacore/keda --namespace $(NAMESPACE_KEDA) -f keda/values.yaml
	@echo "Waiting for KEDA pods ready..."
	kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=keda-operator -n $(NAMESPACE_KEDA) --timeout=60s
	@echo "KEDA ready."

# Workload build
build:
	@echo "Building workload image..."
	docker build -t $(DOCKER_IMAGE) workload/
	@echo "Importing image into k3d..."
	k3d image import $(DOCKER_IMAGE) -c $(CLUSTER_NAME)
	@echo "Image ready."

# Demo: SQS trigger
demo-sqs:
	@echo "Creating demo namespace..."
	kubectl create namespace $(NAMESPACE_DEMO) --dry-run=client -o yaml | kubectl apply -f -
	@echo "Applying SQS ScaledJob..."
	kubectl apply -f keda/scaled-job-sqs.yaml -n $(NAMESPACE_DEMO)
	@echo "Waiting for ScaledJob to be ready..."
	sleep 2
	@echo "Sending $(N) messages to SQS..."
	python load-generator/send_messages.py --queue demo-queue --count $(N) --endpoint http://localhost:4566
	@echo "Watch jobs: kubectl get jobs -n $(NAMESPACE_DEMO) -w"

# Demo: SNS trigger (SNS -> SQS -> jobs)
demo-sns:
	@echo "Creating demo namespace..."
	kubectl create namespace $(NAMESPACE_DEMO) --dry-run=client -o yaml | kubectl apply -f -
	@echo "Applying SNS ScaledJob..."
	kubectl apply -f keda/scaled-job-sns.yaml -n $(NAMESPACE_DEMO)
	@echo "Waiting for ScaledJob to be ready..."
	sleep 2
	@echo "Sending $(N) messages to SNS..."
	python load-generator/send_messages.py --topic demo-topic --count $(N) --endpoint http://localhost:4566
	@echo "Watch jobs: kubectl get jobs -n $(NAMESPACE_DEMO) -w"

# Cost analysis
cost-model:
	@echo "Generating cost analysis..."
	python3 analysis/cost_model.py

# Cleanup
clean:
	@echo "Deleting demo namespace..."
	kubectl delete namespace $(NAMESPACE_DEMO) --ignore-not-found=true
	@echo "Deleting LocalStack..."
	kubectl delete namespace $(NAMESPACE_LOCALSTACK) --ignore-not-found=true
	@echo "Cleanup done."

help:
	@echo "KEDA-as-Lambda POC — Makefile targets:"
	@echo ""
	@echo "  make cluster-up        Create k3d cluster"
	@echo "  make cluster-down      Destroy k3d cluster"
	@echo "  make localstack-up     Deploy LocalStack (SQS/SNS mock)"
	@echo "  make init-aws          Create SQS queues, SNS topic, subscription"
	@echo "  make keda-up           Install KEDA via Helm"
	@echo "  make build             Build and import workload image"
	@echo "  make demo-sqs N=20     Send N messages to SQS, spawn jobs"
	@echo "  make demo-sns N=20     Publish N messages to SNS, spawn jobs via SQS subscription"
	@echo "  make cost-model        Generate cost comparison"
	@echo "  make clean             Delete demo and localstack namespaces"
