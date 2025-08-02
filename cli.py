#!/usr/bin/env python3
"""
Command Line Interface for the Autodeployment Chat System
"""

import argparse
import requests
import time
import json
import sys
from utils.logger import setup_logger

logger = setup_logger()

class AutodeploymentCLI:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def deploy(self, description: str, repository_url: str, follow: bool = True):
        """Deploy an application"""
        deployment_request = {
            "description": description,
            "repository_url": repository_url
        }
        
        logger.info(f"Deploying application from {repository_url}")
        logger.info(f"Description: {description}")
        
        try:
            response = requests.post(f"{self.base_url}/deploy", json=deployment_request)
            
            if response.status_code != 200:
                logger.error(f"Deployment request failed: {response.text}")
                return False
            
            deployment_data = response.json()
            deployment_id = deployment_data["deployment_id"]
            
            logger.info(f" Deployment initiated with ID: {deployment_id}")
            
            if follow:
                return self.follow_deployment(deployment_id)
            else:
                logger.info(f"Use 'python cli.py status {deployment_id}' to check progress")
                return True
                
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
    
    def follow_deployment(self, deployment_id: str):
        """Follow a deployment until completion"""
        logger.info(f"Following deployment {deployment_id}...")
        
        last_log_count = 0
        
        while True:
            try:
                # Get status
                status_response = requests.get(f"{self.base_url}/status/{deployment_id}")
                
                if status_response.status_code != 200:
                    logger.error(f"Failed to get status: {status_response.text}")
                    return False
                
                status_data = status_response.json()
                current_status = status_data["status"]
                
                # Get new logs
                logs_response = requests.get(f"{self.base_url}/logs/{deployment_id}")
                if logs_response.status_code == 200:
                    logs_data = logs_response.json()
                    logs = logs_data["logs"]
                    
                    # Print new log entries
                    for log_entry in logs[last_log_count:]:
                        timestamp = log_entry["timestamp"].split("T")[1].split(".")[0]
                        print(f"[{timestamp}] {log_entry['message']}")
                    
                    last_log_count = len(logs)
                
                if current_status == "completed":
                    if "deployment_url" in status_data:
                        logger.info(f" Deployment completed! Application available at: {status_data['deployment_url']}")
                    else:
                        logger.info(" Deployment completed successfully!")
                    return True
                
                elif current_status == "failed":
                    logger.error(" Deployment failed!")
                    if "error" in status_data:
                        logger.error(f"Error: {status_data['error']}")
                    return False
                
                # Wait before checking again
                time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                return False
            except Exception as e:
                logger.error(f"Error monitoring deployment: {e}")
                return False
    
    def status(self, deployment_id: str):
        """Get deployment status"""
        try:
            response = requests.get(f"{self.base_url}/status/{deployment_id}")
            
            if response.status_code == 404:
                logger.error(f"Deployment {deployment_id} not found")
                return False
            elif response.status_code != 200:
                logger.error(f"Failed to get status: {response.text}")
                return False
            
            status_data = response.json()
            
            print(f"\n Deployment Status: {deployment_id}")
            print(f"Status: {status_data['status']}")
            print(f"Message: {status_data.get('message', 'N/A')}")
            
            if 'start_time' in status_data:
                print(f"Started: {status_data['start_time']}")
            
            if 'end_time' in status_data:
                print(f"Completed: {status_data['end_time']}")
            
            if 'deployment_url' in status_data:
                print(f"Application URL: {status_data['deployment_url']}")
            
            if 'error' in status_data:
                print(f"Error: {status_data['error']}")
            
            print(f"Steps completed: {len(status_data.get('steps', []))}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return False
    
    def logs(self, deployment_id: str, tail: int = 20):
        """Get deployment logs"""
        try:
            response = requests.get(f"{self.base_url}/logs/{deployment_id}")
            
            if response.status_code == 404:
                logger.error(f"Deployment {deployment_id} not found")
                return False
            elif response.status_code != 200:
                logger.error(f"Failed to get logs: {response.text}")
                return False
            
            logs_data = response.json()
            logs = logs_data["logs"]
            
            print(f"\n Deployment Logs: {deployment_id}")
            print("-" * 80)
            
            # Show last N log entries
            for log_entry in logs[-tail:]:
                timestamp = log_entry["timestamp"].split("T")[1].split(".")[0]
                print(f"[{timestamp}] {log_entry['message']}")
            
            if len(logs) > tail:
                print(f"\n... ({len(logs) - tail} earlier entries)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return False
    
    def list_deployments(self):
        """List recent deployments (if endpoint exists)"""
        logger.info("Listing deployments feature not implemented in current API")
        return False
    
    def health(self):
        """Check API health"""
        try:
            response = requests.get(f"{self.base_url}/")
            
            if response.status_code == 200:
                data = response.json()
                print(f" API is healthy")
                print(f"Version: {data.get('version', 'unknown')}")
                print(f"Available endpoints: {', '.join(data.get('endpoints', {}).keys())}")
                return True
            else:
                logger.error(f"API health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Autodeployment Chat System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy a Flask application
  python cli.py deploy "Deploy this Flask app on AWS" https://github.com/user/flask-app

  # Deploy without following progress
  python cli.py deploy "Deploy Node.js app" https://github.com/user/node-app --no-follow

  # Check deployment status
  python cli.py status abc123-def456-ghi789

  # View deployment logs
  python cli.py logs abc123-def456-ghi789

  # Check API health
  python cli.py health
        """
    )
    
    parser.add_argument(
        '--url', 
        default='http://localhost:8000',
        help='API base URL (default: http://localhost:8000)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy an application')
    deploy_parser.add_argument('description', help='Natural language description of deployment')
    deploy_parser.add_argument('repository_url', help='GitHub repository URL')
    deploy_parser.add_argument('--no-follow', action='store_true', help='Don\'t follow deployment progress')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get deployment status')
    status_parser.add_argument('deployment_id', help='Deployment ID')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Get deployment logs')
    logs_parser.add_argument('deployment_id', help='Deployment ID')
    logs_parser.add_argument('--tail', type=int, default=20, help='Number of log entries to show (default: 20)')
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check API health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = AutodeploymentCLI(base_url=args.url)
    
    if args.command == 'deploy':
        success = cli.deploy(
            description=args.description,
            repository_url=args.repository_url,
            follow=not args.no_follow
        )
    elif args.command == 'status':
        success = cli.status(args.deployment_id)
    elif args.command == 'logs':
        success = cli.logs(args.deployment_id, tail=args.tail)
    elif args.command == 'health':
        success = cli.health()
    else:
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
