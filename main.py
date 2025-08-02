from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
import uuid
import logging
from typing import Optional
import os
from datetime import datetime

from services.nlp_parser import NLPParser
from services.repository_analyzer import RepositoryAnalyzer
from services.deployment_engine import DeploymentEngine
from services.infrastructure_provisioner import InfrastructureProvisioner
from services.application_deployer import ApplicationDeployer
from utils.logger import setup_logger

app = FastAPI(title="Autodeployment Chat System", version="1.0.0")
logger = setup_logger()

# In-memory storage for deployment status (in production, use Redis/DB)
deployment_status = {}

class DeploymentRequest(BaseModel):
    description: str
    repository_url: str
    user_id: Optional[str] = "default"

class DeploymentResponse(BaseModel):
    deployment_id: str
    status: str
    message: str

@app.post("/deploy", response_model=DeploymentResponse)
async def deploy_application(request: DeploymentRequest, background_tasks: BackgroundTasks):
    """
    Main endpoint to deploy applications based on natural language and repository
    """
    deployment_id = str(uuid.uuid4())
    
    # Initialize deployment status
    deployment_status[deployment_id] = {
        "status": "initiated",
        "steps": [],
        "logs": [],
        "start_time": datetime.now().isoformat(),
        "error": None
    }
    
    # Start background deployment process
    background_tasks.add_task(process_deployment, deployment_id, request)
    
    return DeploymentResponse(
        deployment_id=deployment_id,
        status="initiated",
        message="Deployment process started. Use /status/{deployment_id} to track progress."
    )

@app.get("/status/{deployment_id}")
async def get_deployment_status(deployment_id: str):
    """
    Get the current status of a deployment
    """
    if deployment_id not in deployment_status:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    return deployment_status[deployment_id]

@app.get("/logs/{deployment_id}")
async def get_deployment_logs(deployment_id: str):
    """
    Get detailed logs for a deployment
    """
    if deployment_id not in deployment_status:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    return {"logs": deployment_status[deployment_id]["logs"]}

async def process_deployment(deployment_id: str, request: DeploymentRequest):
    """
    Main deployment processing pipeline
    """
    try:
        # Update status
        update_deployment_status(deployment_id, "processing", "Starting deployment analysis...")
        
        # Parse natural language
        log_step(deployment_id, "Parsing natural language requirements...")
        nlp_parser = NLPParser()
        deployment_requirements = await nlp_parser.parse_requirements(request.description)
        log_step(deployment_id, f"Parsed requirements: {deployment_requirements}")
        
        # Analyzing repository
        log_step(deployment_id, f"Analyzing repository: {request.repository_url}")
        repo_analyzer = RepositoryAnalyzer()
        repo_analysis = await repo_analyzer.analyze_repository(request.repository_url)
        log_step(deployment_id, f"Repository analysis complete: {repo_analysis}")
        
        # Determining deployment strategy
        log_step(deployment_id, "Determining optimal deployment strategy...")
        deployment_engine = DeploymentEngine()
        deployment_strategy = deployment_engine.determine_strategy(
            deployment_requirements, repo_analysis
        )
        log_step(deployment_id, f"Deployment strategy: {deployment_strategy}")
        
        # Provision infrastructure
        log_step(deployment_id, "Provisioning cloud infrastructure...")
        infra_provisioner = InfrastructureProvisioner()
        infrastructure = await infra_provisioner.provision(
            deployment_strategy, deployment_id
        )
        log_step(deployment_id, f"Infrastructure provisioned: {infrastructure}")
        
        # Application Deployment
        log_step(deployment_id, "Deploying application...")
        app_deployer = ApplicationDeployer()
        deployment_result = await app_deployer.deploy(
            repo_analysis, infrastructure, deployment_strategy
        )
        log_step(deployment_id, f"Application deployed successfully: {deployment_result}")
        
        # Update final status
        update_deployment_status(
            deployment_id, 
            "completed", 
            f"Deployment successful! Application available at: {deployment_result.get('url', 'N/A')}"
        )
        
        # Adding final deployment info
        deployment_status[deployment_id]["deployment_url"] = deployment_result.get("url")
        deployment_status[deployment_id]["infrastructure"] = infrastructure
        deployment_status[deployment_id]["end_time"] = datetime.now().isoformat()
        
    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {str(e)}")
        update_deployment_status(deployment_id, "failed", f"Deployment failed: {str(e)}")
        deployment_status[deployment_id]["error"] = str(e)

def update_deployment_status(deployment_id: str, status: str, message: str):
    """Update deployment status and log message"""
    deployment_status[deployment_id]["status"] = status
    deployment_status[deployment_id]["message"] = message
    log_step(deployment_id, message)

def log_step(deployment_id: str, message: str):
    """Add a step to the deployment logs"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "message": message
    }
    deployment_status[deployment_id]["logs"].append(log_entry)
    deployment_status[deployment_id]["steps"].append(message)
    logger.info(f"[{deployment_id}] {message}")

@app.get("/")
async def root():
    return {
        "message": "Autodeployment Chat System API",
        "version": "1.0.0",
        "endpoints": {
            "deploy": "POST /deploy",
            "status": "GET /status/{deployment_id}",
            "logs": "GET /logs/{deployment_id}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
