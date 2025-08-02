#!/bin/bash

# Autodeployment Chat System Setup Script
set -e

echo " Setting up Autodeployment Chat System..."

# Check if running on supported OS
if [[ "$OSTYPE" != "linux-gnu"* ]] && [[ "$OSTYPE" != "darwin"* ]]; then
    echo " This setup script supports Linux and macOS only"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Python dependencies
echo " Installing Python dependencies..."
if command_exists pip3; then
    pip3 install -r requirements.txt
elif command_exists pip; then
    pip install -r requirements.txt
else
    echo " Python pip not found. Please install Python 3.8+ and pip"
    exit 1
fi

# Install Terraform
echo "  Installing Terraform..."
if ! command_exists terraform; then
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux installation
        TERRAFORM_VERSION="1.6.0"
        wget -q "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
        unzip -q "terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
        sudo mv terraform /usr/local/bin/
        rm "terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
        echo " Terraform installed"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS installation
        if command_exists brew; then
            brew install terraform
            echo " Terraform installed via Homebrew"
        else
            echo " Please install Homebrew or manually install Terraform"
            exit 1
        fi
    fi
else
    echo " Terraform already installed"
fi

# Install AWS CLI
echo "  Installing AWS CLI..."
if ! command_exists aws; then
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux installation
        curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
        unzip -q awscliv2.zip
        sudo ./aws/install
        rm -rf aws awscliv2.zip
        echo " AWS CLI installed"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS installation
        if command_exists brew; then
            brew install awscli
            echo " AWS CLI installed via Homebrew"
        else
            echo " Please install Homebrew or manually install AWS CLI"
            exit 1
        fi
    fi
else
    echo " AWS CLI already installed"
fi

# Install Docker (optional, for container deployments)
echo " Checking Docker installation..."
if ! command_exists docker; then
    echo "  Docker not found. Container deployments will not work."
    echo "   To install Docker, visit: https://docs.docker.com/get-docker/"
else
    echo " Docker is installed"
fi

# Install Git (usually pre-installed)
if ! command_exists git; then
    echo " Git is required but not installed. Please install Git first."
    exit 1
else
    echo " Git is available"
fi

# Create directories
echo " Creating project directories..."
mkdir -p services utils tests logs

# Create environment template
echo " Creating environment template..."
cat > .env.template << EOF
# OpenAI API Key (required for NLP processing)
OPENAI_API_KEY=your-openai-api-key-here

# AWS Credentials (required for infrastructure provisioning)
AWS_ACCESS_KEY_ID=your-aws-access-key-here
AWS_SECRET_ACCESS_KEY=your-aws-secret-key-here
AWS_DEFAULT_REGION=us-east-1

# Optional: Logging configuration
LOG_LEVEL=INFO

# Optional: API configuration
API_HOST=0.0.0.0
API_PORT=8000
EOF

# Check for existing .env file
if [ ! -f .env ]; then
    cp .env.template .env
    echo " Created .env file from template"
    echo "  Please edit .env file with your actual API keys and credentials"
else
    echo " .env file already exists"
fi

# Create simple test script
echo " Creating test script..."
cat > quick_test.py << 'EOF'
#!/usr/bin/env python3
"""Quick test to verify installation"""

import sys
import subprocess
import importlib

def test_imports():
    """Test that all required packages can be imported"""
    required_packages = [
        'fastapi', 'uvicorn', 'pydantic', 'git', 
        'openai', 'paramiko'
    ]
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f" {package}")
        except ImportError:
            print(f" {package} - not installed")
            return False
    return True

def test_commands():
    """Test that required commands are available"""
    required_commands = ['terraform', 'aws', 'git']
    
    for cmd in required_commands:
        try:
            result = subprocess.run(['which', cmd], capture_output=True)
            if result.returncode == 0:
                print(f" {cmd}")
            else:
                print(f" {cmd} - not found in PATH")
                return False
        except Exception:
            print(f" {cmd} - check failed")
            return False
    return True

if __name__ == "__main__":
    print(" Testing installation...")
    
    print("\n Testing Python packages:")
    packages_ok = test_imports()
    
    print("\n Testing system commands:")
    commands_ok = test_commands()
    
    if packages_ok and commands_ok:
        print("\n All tests passed! Installation looks good.")
        print("\nNext steps:")
        print("1. Edit .env file with your API keys")
        print("2. Run: python main.py")
        print("3. Test with: python cli.py health")
        sys.exit(0)
    else:
        print("\n Some tests failed. Please check the installation.")
        sys.exit(1)
EOF

chmod +x quick_test.py

# Create systemd service template (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo " Creating systemd service template..."
    cat > autodeployment.service << EOF
[Unit]
Description=Autodeployment Chat System API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    echo " Created autodeployment.service template"
    echo "   To install as system service: sudo cp autodeployment.service /etc/systemd/system/"
fi

# Final setup verification
echo ""
echo " Running quick installation test..."
python3 quick_test.py

echo ""
echo " Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys and AWS credentials"
echo "2. Start the API server: python main.py"
echo "3. Test deployment: python cli.py deploy 'Deploy Flask app' https://github.com/Arvo-AI/hello_world"
echo ""
echo "For more information, see README.md"
