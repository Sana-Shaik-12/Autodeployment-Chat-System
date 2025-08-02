import os
import json
import tempfile
import subprocess
import asyncio
from typing import Dict, Optional
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger()

class InfrastructureProvisioner:
    def __init__(self):
        self.terraform_dir = None
        
    async def provision(self, deployment_config: Dict, deployment_id: str) -> Dict:
        """
        Provision infrastructure using Terraform based on deployment configuration
        """
        try:
            strategy = deployment_config['strategy']
            cloud_provider = deployment_config['cloud_provider']
            
            logger.info(f"Provisioning {strategy} infrastructure on {cloud_provider}")
            
            # Create temporary directory for Terraform files
            self.terraform_dir = tempfile.mkdtemp(prefix=f"terraform_{deployment_id}_")
            
            # Generate Terraform configuration
            await self._generate_terraform_config(deployment_config, deployment_id)
            
            # Initialize Terraform
            await self._run_terraform_command("init")
            
            # Plan infrastructure
            await self._run_terraform_command("plan", ["-out=tfplan"])
            
            # Apply infrastructure
            await self._run_terraform_command("apply", ["tfplan"])
            
            # Get outputs
            infrastructure_info = await self._get_terraform_outputs()
            
            logger.info(f"Infrastructure provisioned successfully: {infrastructure_info}")
            return infrastructure_info
            
        except Exception as e:
            logger.error(f"Infrastructure provisioning failed: {e}")
            # Cleanup on failure
            if self.terraform_dir:
                await self._cleanup_on_failure()
            raise
    
    async def _generate_terraform_config(self, deployment_config: Dict, deployment_id: str):
        """Generate Terraform configuration files"""
        
        strategy = deployment_config['strategy']
        cloud_provider = deployment_config['cloud_provider']
        
        # Generate main.tf
        main_tf = self._generate_main_tf(deployment_config, deployment_id)
        with open(os.path.join(self.terraform_dir, "main.tf"), "w") as f:
            f.write(main_tf)
        
        # Generate variables.tf
        variables_tf = self._generate_variables_tf(deployment_config)
        with open(os.path.join(self.terraform_dir, "variables.tf"), "w") as f:
            f.write(variables_tf)
        
        # Generate outputs.tf
        outputs_tf = self._generate_outputs_tf(deployment_config)
        with open(os.path.join(self.terraform_dir, "outputs.tf"), "w") as f:
            f.write(outputs_tf)
        
        # Generate terraform.tfvars
        tfvars = self._generate_tfvars(deployment_config, deployment_id)
        with open(os.path.join(self.terraform_dir, "terraform.tfvars"), "w") as f:
            f.write(tfvars)
        
        # Generate user data script for VM deployments
        if strategy == 'vm':
            user_data = self._generate_user_data_script(deployment_config)
            with open(os.path.join(self.terraform_dir, "user_data.sh"), "w") as f:
                f.write(user_data)
    
    def _generate_main_tf(self, deployment_config: Dict, deployment_id: str) -> str:
        """Generate main Terraform configuration"""
        
        strategy = deployment_config['strategy']
        cloud_provider = deployment_config['cloud_provider']
        
        if cloud_provider == 'aws':
            return self._generate_aws_main_tf(deployment_config, deployment_id)
        else:
            raise ValueError(f"Unsupported cloud provider: {cloud_provider}")
    
    def _generate_aws_main_tf(self, deployment_config: Dict, deployment_id: str) -> str:
        """Generate AWS Terraform configuration"""
        
        strategy = deployment_config['strategy']
        
        terraform_config = f"""
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}

# VPC and Networking
resource "aws_vpc" "main" {{
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {{
    Name = "autodeployment-vpc-${{var.deployment_id}}"
  }}
}}

resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id

  tags = {{
    Name = "autodeployment-igw-${{var.deployment_id}}"
  }}
}}

resource "aws_subnet" "public" {{
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${{count.index + 1}}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {{
    Name = "autodeployment-public-subnet-${{count.index + 1}}-${{var.deployment_id}}"
  }}
}}

resource "aws_route_table" "public" {{
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }}

  tags = {{
    Name = "autodeployment-public-rt-${{var.deployment_id}}"
  }}
}}

resource "aws_route_table_association" "public" {{
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}}

data "aws_availability_zones" "available" {{
  state = "available"
}}

# Security Groups
resource "aws_security_group" "app" {{
  name_prefix = "autodeployment-app-${{var.deployment_id}}"
  vpc_id      = aws_vpc.main.id

  ingress {{
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  ingress {{
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = {{
    Name = "autodeployment-app-sg-${{var.deployment_id}}"
  }}
}}
"""

        if strategy == 'vm':
            terraform_config += self._generate_vm_resources(deployment_config)
        elif strategy == 'serverless':
            terraform_config += self._generate_serverless_resources(deployment_config)
        elif strategy == 'container':
            terraform_config += self._generate_container_resources(deployment_config)
        
        return terraform_config
    
    def _generate_vm_resources(self, deployment_config: Dict) -> str:
        """Generate VM-specific Terraform resources"""
        return """
# Key Pair
resource "aws_key_pair" "app" {
  key_name   = "autodeployment-key-${var.deployment_id}"
  public_key = var.ssh_public_key
}

# EC2 Instance
resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name              = aws_key_pair.app.key_name
  vpc_security_group_ids = [aws_security_group.app.id]
  subnet_id             = aws_subnet.public[0].id
  
  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = "autodeployment-app-${var.deployment_id}"
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
"""
    
    def _generate_serverless_resources(self, deployment_config: Dict) -> str:
        """Generate serverless-specific Terraform resources"""
        return """
# Lambda Function
resource "aws_lambda_function" "app" {
  filename         = "deployment.zip"
  function_name    = "autodeployment-app-${var.deployment_id}"
  role            = aws_iam_role.lambda.arn
  handler         = var.lambda_handler
  runtime         = var.lambda_runtime
  timeout         = 30

  tags = {
    Name = "autodeployment-app-${var.deployment_id}"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "autodeployment-lambda-role-${var.deployment_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# API Gateway
resource "aws_api_gateway_rest_api" "app" {
  name = "autodeployment-api-${var.deployment_id}"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.app.id
  parent_id   = aws_api_gateway_rest_api.app.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.app.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.app.id
  resource_id = aws_api_gateway_method.proxy.resource_id
  http_method = aws_api_gateway_method.proxy.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.app.invoke_arn
}

resource "aws_api_gateway_deployment" "app" {
  depends_on = [aws_api_gateway_integration.lambda]

  rest_api_id = aws_api_gateway_rest_api.app.id
  stage_name  = "prod"
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.app.execution_arn}/*/*"
}
"""
    
    def _generate_container_resources(self, deployment_config: Dict) -> str:
        """Generate container-specific Terraform resources"""
        return """
# ECS Cluster
resource "aws_ecs_cluster" "app" {
  name = "autodeployment-cluster-${var.deployment_id}"

  tags = {
    Name = "autodeployment-cluster-${var.deployment_id}"
  }
}

# ECR Repository
resource "aws_ecr_repository" "app" {
  name = "autodeployment-app-${var.deployment_id}"

  tags = {
    Name = "autodeployment-app-${var.deployment_id}"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = "autodeployment-app-${var.deployment_id}"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = 256
  memory                  = 512
  execution_role_arn      = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name  = "app"
      image = "${aws_ecr_repository.app.repository_url}:latest"
      portMappings = [
        {
          containerPort = var.app_port
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "app" {
  name            = "autodeployment-service-${var.deployment_id}"
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    security_groups = [aws_security_group.app.id]
    subnets         = aws_subnet.public[*].id
    assign_public_ip = true
  }

  depends_on = [aws_iam_role_policy_attachment.ecs_execution]
}

# IAM Role for ECS
resource "aws_iam_role" "ecs_execution" {
  name = "autodeployment-ecs-execution-role-${var.deployment_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/autodeployment-app-${var.deployment_id}"
  retention_in_days = 7
}
"""
    
    def _generate_variables_tf(self, deployment_config: Dict) -> str:
        """Generate variables.tf file"""
        return """
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "deployment_id" {
  description = "Unique deployment identifier"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "app_port" {
  description = "Application port"
  type        = number
  default     = 8000
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 access"
  type        = string
  default     = ""
}

variable "lambda_handler" {
  description = "Lambda function handler"
  type        = string
  default     = "app.handler"
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.9"
}
"""
    
    def _generate_outputs_tf(self, deployment_config: Dict) -> str:
        """Generate outputs.tf file"""
        strategy = deployment_config['strategy']
        
        outputs = """
output "deployment_id" {
  value = var.deployment_id
}

output "vpc_id" {
  value = aws_vpc.main.id
}
"""
        
        if strategy == 'vm':
            outputs += """
output "instance_ip" {
  value = aws_instance.app.public_ip
}

output "instance_dns" {
  value = aws_instance.app.public_dns
}

output "application_url" {
  value = "http://${aws_instance.app.public_ip}:${var.app_port}"
}
"""
        elif strategy == 'serverless':
            outputs += """
output "api_gateway_url" {
  value = "${aws_api_gateway_deployment.app.invoke_url}"
}

output "lambda_function_name" {
  value = aws_lambda_function.app.function_name
}

output "application_url" {
  value = "${aws_api_gateway_deployment.app.invoke_url}"
}
"""
        elif strategy == 'container':
            outputs += """
output "ecs_cluster_name" {
  value = aws_ecs_cluster.app.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "application_url" {
  value = "http://ecs-service-url:${var.app_port}"
}
"""
        
        return outputs
    
    def _generate_tfvars(self, deployment_config: Dict, deployment_id: str) -> str:
        """Generate terraform.tfvars file"""
        infrastructure = deployment_config.get('infrastructure', {})
        app_config = deployment_config.get('application', {})
        
        tfvars = f'''deployment_id = "{deployment_id}"
aws_region = "{infrastructure.get('region', 'us-east-1')}"
app_port = {app_config.get('port', 8000)}
'''
        
        if deployment_config['strategy'] == 'vm':
            tfvars += f'instance_type = "{infrastructure.get("instance_type", "t3.micro")}"\n'
            # Generate SSH key pair
            tfvars += self._generate_ssh_key_pair()
        
        if deployment_config['strategy'] == 'serverless':
            runtime = infrastructure.get('runtime', 'python3.9')
            tfvars += f'lambda_runtime = "{runtime}"\n'
            tfvars += f'lambda_handler = "{self._get_lambda_handler(deployment_config)}"\n'
        
        return tfvars
    
    def _generate_ssh_key_pair(self) -> str:
        """Generate SSH key pair for EC2 access"""
        try:
            # Generate SSH key pair
            key_path = os.path.join(self.terraform_dir, "deployment_key")
            subprocess.run([
                "ssh-keygen", "-t", "rsa", "-b", "2048", 
                "-f", key_path, "-N", ""
            ], check=True, capture_output=True)
            
            # Read public key
            with open(f"{key_path}.pub", "r") as f:
                public_key = f.read().strip()
            
            return f'ssh_public_key = "{public_key}"\n'
        except Exception as e:
            logger.warning(f"Failed to generate SSH key: {e}")
            return 'ssh_public_key = ""\n'
    
    def _get_lambda_handler(self, deployment_config: Dict) -> str:
        """Get appropriate Lambda handler based on language"""
        language = deployment_config.get('application', {}).get('language')
        
        if language == 'python':
            return "app.handler"
        elif language == 'nodejs':
            return "index.handler"
        else:
            return "app.handler"
    
    def _generate_user_data_script(self, deployment_config: Dict) -> str:
        """Generate user data script for VM initialization"""
        app_config = deployment_config.get('application', {})
        language = app_config.get('language', 'python')
        build_commands = app_config.get('build_commands', [])
        start_commands = app_config.get('start_commands', [])
        
        script = """#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y git curl wget unzip

# Create application directory
mkdir -p /opt/app
cd /opt/app

# Install language-specific dependencies
"""
        
        if language == 'python':
            script += """
# Install Python and pip
apt-get install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
"""
        elif language == 'nodejs':
            script += """
# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs
"""
        elif language == 'java':
            script += """
# Install Java
apt-get install -y openjdk-11-jdk maven
"""
        
        script += """
# Clone repository (this will be replaced with actual repo URL)
# git clone REPO_URL .

# Install dependencies
"""
        
        for cmd in build_commands:
            script += f"# {cmd}\n"
        
        script += """
# Create systemd service
cat > /etc/systemd/system/app.service << EOF
[Unit]
Description=Autodeployment Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/app
"""
        
        if language == 'python':
            script += "Environment=PATH=/opt/app/venv/bin\n"
        
        if start_commands:
            script += f"ExecStart={start_commands[0]}\n"
        else:
            script += "ExecStart=/bin/bash -c 'echo \"No start command specified\"'\n"
        
        script += """Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable app
# systemctl start app

# Log completion
echo "User data script completed" > /var/log/user-data.log
"""
        
        return script
    
    async def _run_terraform_command(self, command: str, args: list = None) -> str:
        """Run a Terraform command"""
        if args is None:
            args = []
        
        cmd = ["terraform", command] + args
        
        try:
            logger.info(f"Running Terraform command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.terraform_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Terraform {command} failed: {error_msg}")
            
            output = stdout.decode()
            logger.info(f"Terraform {command} completed successfully")
            return output
            
        except Exception as e:
            logger.error(f"Terraform {command} failed: {e}")
            raise
    
    async def _get_terraform_outputs(self) -> Dict:
        """Get Terraform outputs"""
        try:
            output = await self._run_terraform_command("output", ["-json"])
            outputs = json.loads(output)
            
            # Extract values from Terraform output format
            result = {}
            for key, value in outputs.items():
                result[key] = value.get('value')
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Terraform outputs: {e}")
            return {}
    
    async def _cleanup_on_failure(self):
        """Cleanup resources on deployment failure"""
        try:
            logger.info("Cleaning up infrastructure due to deployment failure...")
            await self._run_terraform_command("destroy", ["-auto-approve"])
        except Exception as e:
            logger.error(f"Failed to cleanup infrastructure: {e}")
    
    async def destroy_infrastructure(self, deployment_id: str):
        """Destroy infrastructure for a deployment"""
        try:
            if self.terraform_dir and os.path.exists(self.terraform_dir):
                await self._run_terraform_command("destroy", ["-auto-approve"])
                logger.info(f"Infrastructure destroyed for deployment {deployment_id}")
        except Exception as e:
            logger.error(f"Failed to destroy infrastructure: {e}")
            raise
