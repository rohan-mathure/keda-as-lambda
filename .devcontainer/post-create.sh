#!/bin/bash
set -e

echo "🔧 Setting up KEDA-as-Lambda development environment..."

# Install system dependencies
echo "📦 Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  curl \
  wget \
  build-essential \
  python3-pip \
  python3-venv \
  zsh \
  git

# Install k3d
echo "🐳 Installing k3d..."
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Install helm
echo "📊 Installing Helm..."
curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install kubectl
echo "☸️  Installing kubectl..."
curl -s https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl
chmod +x /usr/local/bin/kubectl

# Install awscli-local
echo "🌐 Installing awscli-local..."
pip install -q awscli-local boto3 2>/dev/null || true

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install -q -r load-generator/requirements.txt
pip install -q -r workload/requirements.txt

echo "✅ Setup complete!"
echo ""
echo "🚀 Quick start:"
echo "   make cluster-up      # Create k3d cluster"
echo "   make localstack-up   # Deploy LocalStack (SQS/SNS mock)"
echo "   make init-aws        # Create AWS resources"
echo "   make keda-up         # Install KEDA"
echo "   make build           # Build workload image"
echo "   make demo-sqs N=5    # Send 5 test messages"
echo ""
echo "📊 Or run the cron demo:"
echo "   kubectl apply -f keda/scaled-job-cron.yaml -n demo"
echo "   kubectl get jobs -n demo -w"
