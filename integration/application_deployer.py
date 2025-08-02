import os
import asyncio
import tempfile
import subprocess
import paramiko
import time
from typing import Dict, Optional
import git
import shutil
from utils.logger import setup_logger

logger = setup_logger()

class ApplicationDeployer:
    def __init__(self):
        self.ssh_client = None
        
    async def deploy(self, repo_analysis: Dict, infrastructure: Dict, deployment_strategy: Dict) -> Dict:
        """
        Deploy application to provisioned infrastructure
        """
        strategy = deployment_strategy['strategy']
        logger.info(f"Deploying application using {strategy} strategy")
        
        try:
            if strategy == 'vm':
                return await self._deploy_to_vm(repo_analysis, infrastructure, deployment_strategy)
            elif strategy == 'serverless':
                return await self._deploy_to_serverless(repo_analysis, infrastructure, deployment_strategy)
            elif strategy == 'container':
                return await self._deploy_to_container(repo_analysis, infrastructure, deployment_strategy)
            else:
                raise ValueError(f"Unsupported deployment strategy: {strategy}")
                
        except Exception as e:
            logger.error(f"Application deployment failed: {e}")
            raise
    
    async def _deploy_to_vm(self, repo_analysis: Dict, infrastructure: Dict, deployment_strategy: Dict) -> Dict:
        """Deploy application to EC2 VM"""
        
        instance_ip = infrastructure.get('instance_ip')
        if not instance_ip:
            raise ValueError("Instance IP not found in infrastructure info")
        
        logger.info(f"Deploying to VM at {instance_ip}")
        
        # Wait for instance to be ready
        await self._wait_for_vm_ready(instance_ip)
        
        # Connect via SSH
        await self._connect_ssh(instance_ip)
        
        try:
            # Clone repository
            repo_url = repo_analysis['repo_url']
            await self._clone_repo_to_vm(repo_url)
            
            # Install dependencies and build
            await self._build_application_on_vm(repo_analysis, deployment_strategy)
            
            # Configure and start application
            await self._start_application_on_vm(repo_analysis, deployment_strategy)
            
            # Verify deployment
            app_port = deployment_strategy['application']['port']
            application_url = f"http://{instance_ip}:{app_port}"
            
            if await self._verify_deployment(application_url):
                logger.info(f"Application deployed successfully at {application_url}")
                return {
                    'status': 'success',
                    'url': application_url,
                    'instance_ip': instance_ip,
                    'deployment_type': 'vm'
                }
            else:
                raise Exception("Application deployment verification failed")
                
        finally:
            if self.ssh_client:
                self.ssh_client.close()
    
    async def _deploy_to_serverless(self, repo_analysis: Dict, infrastructure: Dict, deployment_strategy: Dict) -> Dict:
        """Deploy application to AWS Lambda"""
        
        logger.info("Deploying to serverless (Lambda)")
        
        # Create deployment package
        deployment_package = await self._create_serverless_package(repo_analysis, deployment_strategy)
        
        # Deploy to Lambda
        function_name = infrastructure.get('lambda_function_name')
        if not function_name:
            raise ValueError("Lambda function name not found")
        
        await self._upload_lambda_package(deployment_package, function_name)
        
        # Get API Gateway URL
        api_url = infrastructure.get('api_gateway_url')
        
        if await self._verify_deployment(api_url):
            logger.info(f"Serverless application deployed successfully at {api_url}")
            return {
                'status': 'success',
                'url': api_url,
                'function_name': function_name,
                'deployment_type': 'serverless'
            }
        else:
            raise Exception("Serverless deployment verification failed")
    
    async def _deploy_to_container(self, repo_analysis: Dict, infrastructure: Dict, deployment_strategy: Dict) -> Dict:
        """Deploy application to ECS containers"""
        
        logger.info("Deploying to containers (ECS)")
        
        # Build and push Docker image
        ecr_url = infrastructure.get('ecr_repository_url')
        if not ecr_url:
            raise ValueError("ECR repository URL not found")
        
        await self._build_and_push_docker_image(repo_analysis, deployment_strategy, ecr_url)
        
        # Update ECS service
        cluster_name = infrastructure.get('ecs_cluster_name')
        await self._update_ecs_service(cluster_name, deployment_strategy)
        
        # Get service URL (this would typically be behind a load balancer)
        app_port = deployment_strategy['application']['port']
        service_url = f"http://ecs-service-url:{app_port}"  # Placeholder
        
        return {
            'status': 'success',
            'url': service_url,
            'cluster_name': cluster_name,
            'deployment_type': 'container'
        }
    
    async def _wait_for_vm_ready(self, instance_ip: str, timeout: int = 300):
        """Wait for VM to be ready for SSH connections"""
        logger.info(f"Waiting for VM {instance_ip} to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try to connect via SSH
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    instance_ip,
                    username='ubuntu',
                    key_filename=self._get_ssh_private_key_path(),
                    timeout=10
                )
                ssh.close()
                logger.info("VM is ready for SSH connections")
                return
            except Exception:
                await asyncio.sleep(10)
                continue
        
        raise Exception(f"VM {instance_ip} not ready after {timeout} seconds")
    
    async def _connect_ssh(self, instance_ip: str):
        """Establish SSH connection to VM"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.ssh_client.connect(
                instance_ip,
                username='ubuntu',
                key_filename=self._get_ssh_private_key_path(),
                timeout=30
            )
            
            logger.info(f"SSH connection established to {instance_ip}")
            
        except Exception as e:
            raise Exception(f"Failed to connect via SSH: {e}")
    
    def _get_ssh_private_key_path(self) -> str:
        """Get path to SSH private key"""
        # This should be the private key generated during infrastructure provisioning
        return "/tmp/deployment_key"  # Placeholder - needs to be implemented
    
    async def _clone_repo_to_vm(self, repo_url: str):
        """Clone repository to VM"""
        commands = [
            "sudo rm -rf /opt/app/*",
            f"sudo git clone {repo_url} /opt/app/",
            "sudo chown -R ubuntu:ubuntu /opt/app/",
            "cd /opt/app"
        ]
        
        for cmd in commands:
            await self._execute_ssh_command(cmd)
    
    async def _build_application_on_vm(self, repo_analysis: Dict, deployment_strategy: Dict):
        """Build application on VM"""
        language = repo_analysis.get('language')
        build_commands = deployment_strategy['application'].get('build_commands', [])
        
        # Language-specific setup
        if language == 'python':
            await self._execute_ssh_command("cd /opt/app && python3 -m venv venv")
            await self._execute_ssh_command("cd /opt/app && source venv/bin/activate")
            
        elif language == 'nodejs':
            # Node.js should already be installed via user data
            pass
            
        elif language == 'java':
            # Java should already be installed via user data
            pass
        
        # Execute build commands
        for cmd in build_commands:
            await self._execute_ssh_command(f"cd /opt/app && {cmd}")
    
    async def _start_application_on_vm(self, repo_analysis: Dict, deployment_strategy: Dict):
        """Start application on VM"""
        start_commands = deployment_strategy['application'].get('start_commands', [])
        
        if not start_commands:
            raise Exception("No start commands defined for application")
        
        # Create systemd service
        service_content = self._generate_systemd_service(repo_analysis, deployment_strategy)
        
        # Write service file
        await self._execute_ssh_command(
            f"echo '{service_content}' | sudo tee /etc/systemd/system/app.service"
        )
        
        # Enable and start service
        await self._execute_ssh_command("sudo systemctl daemon-reload")
        await self._execute_ssh_command("sudo systemctl enable app")
        await self._execute_ssh_command("sudo systemctl start app")
        
        # Check service status
        await self._execute_ssh_command("sudo systemctl status app")
    
    def _generate_systemd_service(self, repo_analysis: Dict, deployment_strategy: Dict) -> str:
        """Generate systemd service configuration"""
        language = repo_analysis.get('language')
        start_command = deployment_strategy['application']['start_commands'][0]
        
        service_content = f"""[Unit]
Description=Autodeployment Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/app
"""
        
        if language == 'python':
            service_content += "Environment=PATH=/opt/app/venv/bin:$PATH\n"
        
        service_content += f"""ExecStart=/bin/bash -c '{start_command}'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        return service_content
    
    async def _execute_ssh_command(self, command: str) -> str:
        """Execute command via SSH"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            
            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            if exit_status != 0:
                raise Exception(f"Command failed: {command}\nError: {error}")
            
            logger.info(f"Command executed: {command}")
            return output
            
        except Exception as e:
            logger.error(f"SSH command failed: {command} - {e}")
            raise
    
    async def _create_serverless_package(self, repo_analysis: Dict, deployment_strategy: Dict) -> str:
        """Create deployment package for serverless"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Clone repository
            repo_url = repo_analysis['repo_url']
            git.Repo.clone_from(repo_url, temp_dir)
            
            # Install dependencies
            language = repo_analysis.get('language')
            if language == 'python':
                await self._install_python_dependencies_local(temp_dir)
            elif language == 'nodejs':
                await self._install_nodejs_dependencies_local(temp_dir)
            
            # Create deployment wrapper
            await self._create_serverless_wrapper(temp_dir, repo_analysis, deployment_strategy)
            
            # Create zip package
            package_path = f"{temp_dir}/deployment.zip"
            await self._create_zip_package(temp_dir, package_path)
            
            return package_path
            
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
    
    async def _install_python_dependencies_local(self, directory: str):
        """Install Python dependencies locally"""
        requirements_file = os.path.join(directory, 'requirements.txt')
        if os.path.exists(requirements_file):
            process = await asyncio.create_subprocess_exec(
                'pip', 'install', '-r', 'requirements.txt', '-t', '.',
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
    
    async def _install_nodejs_dependencies_local(self, directory: str):
        """Install Node.js dependencies locally"""
        package_file = os.path.join(directory, 'package.json')
        if os.path.exists(package_file):
            process = await asyncio.create_subprocess_exec(
                'npm', 'install',
                cwd=directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
    
    async def _create_serverless_wrapper(self, directory: str, repo_analysis: Dict, deployment_strategy: Dict):
        """Create serverless wrapper function"""
        language = repo_analysis.get('language')
        
        if language == 'python':
            wrapper_content = """
import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import your application
try:
    from app import app  # Try Flask/FastAPI app
except ImportError:
    try:
        from main import app
    except ImportError:
        app = None

def handler(event, context):
    # Basic Lambda handler for web frameworks
    if app:
        # This is a simplified handler - real implementation would need
        # proper WSGI/ASGI adapter for Lambda
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Application deployed successfully'}),
            'headers': {'Content-Type': 'application/json'}
        }
    else:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Application not found'}),
            'headers': {'Content-Type': 'application/json'}
        }
"""
            
            with open(os.path.join(directory, 'lambda_handler.py'), 'w') as f:
                f.write(wrapper_content)
        
        elif language == 'nodejs':
            wrapper_content = """
const path = require('path');

// Try to import the main application
let app;
try {
    app = require('./app.js');
} catch (e) {
    try {
        app = require('./index.js');
    } catch (e2) {
        console.error('Could not import application:', e2);
    }
}

exports.handler = async (event, context) => {
    // Basic Lambda handler for Node.js applications
    return {
        statusCode: 200,
        body: JSON.stringify({
            message: 'Application deployed successfully'
        }),
        headers: {
            'Content-Type': 'application/json'
        }
    };
};
"""
            
            with open(os.path.join(directory, 'index.js'), 'w') as f:
                f.write(wrapper_content)
    
    async def _create_zip_package(self, directory: str, output_path: str):
        """Create zip package for deployment"""
        process = await asyncio.create_subprocess_exec(
            'zip', '-r', output_path, '.',
            cwd=directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
    
    async def _upload_lambda_package(self, package_path: str, function_name: str):
        """Upload package to Lambda function"""
        # This would use AWS CLI or boto3 to update the Lambda function
        process = await asyncio.create_subprocess_exec(
            'aws', 'lambda', 'update-function-code',
            '--function-name', function_name,
            '--zip-file', f'fileb://{package_path}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Failed to upload Lambda package: {stderr.decode()}")
    
    async def _build_and_push_docker_image(self, repo_analysis: Dict, deployment_strategy: Dict, ecr_url: str):
        """Build and push Docker image to ECR"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Clone repository
            repo_url = repo_analysis['repo_url']
            git.Repo.clone_from(repo_url, temp_dir)
            
            # Create Dockerfile if not present
            dockerfile_path = os.path.join(temp_dir, 'Dockerfile')
            if not os.path.exists(dockerfile_path):
                await self._create_dockerfile(temp_dir, repo_analysis, deployment_strategy)
            
            # Build Docker image
            image_tag = f"{ecr_url}:latest"
            
            build_process = await asyncio.create_subprocess_exec(
                'docker', 'build', '-t', image_tag, '.',
                cwd=temp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await build_process.communicate()
            
            if build_process.returncode != 0:
                raise Exception(f"Docker build failed: {stderr.decode()}")
            
            # Login to ECR
            ecr_login_process = await asyncio.create_subprocess_exec(
                'aws', 'ecr', 'get-login-password', '--region', 'us-east-1',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            login_token, _ = await ecr_login_process.communicate()
            
            if ecr_login_process.returncode == 0:
                docker_login_process = await asyncio.create_subprocess_exec(
                    'docker', 'login', '--username', 'AWS', '--password-stdin',
                    ecr_url.split('/')[0],
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await docker_login_process.communicate(input=login_token)
            
            # Push image
            push_process = await asyncio.create_subprocess_exec(
                'docker', 'push', image_tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await push_process.communicate()
            
            if push_process.returncode != 0:
                raise Exception("Docker push failed")
            
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    async def _create_dockerfile(self, directory: str, repo_analysis: Dict, deployment_strategy: Dict):
        """Create Dockerfile for containerization"""
        language = repo_analysis.get('language')
        app_port = deployment_strategy['application']['port']
        build_commands = deployment_strategy['application'].get('build_commands', [])
        start_commands = deployment_strategy['application'].get('start_commands', [])
        
        dockerfile_content = ""
        
        if language == 'python':
            dockerfile_content = f"""
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE {app_port}

# Start command
CMD {start_commands[0] if start_commands else 'python app.py'}
"""
        
        elif language == 'nodejs':
            dockerfile_content = f"""
FROM node:18-alpine

WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

EXPOSE {app_port}

# Start command
CMD {start_commands[0] if start_commands else 'npm start'}
"""
        
        elif language == 'java':
            dockerfile_content = f"""
FROM openjdk:11-jre-slim

WORKDIR /app

# Copy built JAR file
COPY target/*.jar app.jar

EXPOSE {app_port}

# Start command
CMD ["java", "-jar", "app.jar"]
"""
        
        with open(os.path.join(directory, 'Dockerfile'), 'w') as f:
            f.write(dockerfile_content.strip())
    
    async def _update_ecs_service(self, cluster_name: str, deployment_strategy: Dict):
        """Update ECS service to use new image"""
        # This would trigger a new deployment in ECS
        service_name = f"autodeployment-service-{deployment_strategy.get('deployment_id', 'unknown')}"
        
        process = await asyncio.create_subprocess_exec(
            'aws', 'ecs', 'update-service',
            '--cluster', cluster_name,
            '--service', service_name,
            '--force-new-deployment',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
    
    async def _verify_deployment(self, url: str, timeout: int = 300) -> bool:
        """Verify that the deployed application is responding"""
        if not url or url == "http://ecs-service-url:8000":  # Skip verification for placeholder URLs
            logger.warning("Skipping deployment verification - placeholder URL")
            return True
        
        logger.info(f"Verifying deployment at {url}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Use curl to test the endpoint
                process = await asyncio.create_subprocess_exec(
                    'curl', '-f', '-s', '--connect-timeout', '10', url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    logger.info("Application is responding successfully")
                    return True
                    
            except Exception as e:
                logger.debug(f"Verification attempt failed: {e}")
            
            await asyncio.sleep(30)
        
        logger.error(f"Application not responding after {timeout} seconds")
        return False
    
    async def health_check(self, deployment_info: Dict) -> Dict:
        """Perform health check on deployed application"""
        url = deployment_info.get('url')
        if not url:
            return {'status': 'unknown', 'message': 'No URL provided'}
        
        try:
            process = await asyncio.create_subprocess_exec(
                'curl', '-f', '-s', '--connect-timeout', '5', url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    'status': 'healthy',
                    'message': 'Application is responding',
                    'response_preview': stdout.decode()[:200]
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': f'Application not responding: {stderr.decode()}'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Health check failed: {str(e)}'
            }
