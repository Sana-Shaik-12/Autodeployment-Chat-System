
import re
import json
import os
from typing import Dict, List, Optional
import openai
from utils.logger import setup_logger

logger = setup_logger()

class NLPParser:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    async def parse_requirements(self, description: str) -> Dict:
        """
        Parse natural language description to extract deployment requirements
        """
        try:
            # First, try to extract basic information using regex patterns
            basic_info = self._extract_basic_patterns(description)
            
            # Then use AI for more sophisticated parsing
            ai_parsed = await self._ai_parse_description(description)
            
            # Combine both approaches for robustness
            requirements = {
                **basic_info,
                **ai_parsed,
                "original_description": description
            }
            
            # Set defaults if not specified
            requirements.setdefault("cloud_provider", "aws")
            requirements.setdefault("environment", "production")
            requirements.setdefault("scaling", "minimal")
            
            logger.info(f"Parsed requirements: {requirements}")
            return requirements
            
        except Exception as e:
            logger.error(f"Error parsing requirements: {e}")
            # Fallback to basic parsing
            return self._fallback_parse(description)
    
    def _extract_basic_patterns(self, description: str) -> Dict:
        """Extract basic information using regex patterns"""
        description_lower = description.lower()
        requirements = {}
        
        # Cloud provider detection
        if any(word in description_lower for word in ["aws", "amazon"]):
            requirements["cloud_provider"] = "aws"
        elif any(word in description_lower for word in ["gcp", "google", "cloud platform"]):
            requirements["cloud_provider"] = "gcp"
        elif any(word in description_lower for word in ["azure", "microsoft"]):
            requirements["cloud_provider"] = "azure"
        
        # Application type detection
        if any(word in description_lower for word in ["flask", "django", "python"]):
            requirements["app_type"] = "python"
        elif any(word in description_lower for word in ["node", "express", "javascript"]):
            requirements["app_type"] = "nodejs"
        elif any(word in description_lower for word in ["spring", "java"]):
            requirements["app_type"] = "java"
        
        # Deployment preferences
        if any(word in description_lower for word in ["serverless", "lambda", "function"]):
            requirements["deployment_preference"] = "serverless"
        elif any(word in description_lower for word in ["kubernetes", "k8s", "container"]):
            requirements["deployment_preference"] = "kubernetes"
        elif any(word in description_lower for word in ["vm", "virtual machine", "ec2"]):
            requirements["deployment_preference"] = "vm"
        
        # Environment detection
        if any(word in description_lower for word in ["development", "dev", "test"]):
            requirements["environment"] = "development"
        elif any(word in description_lower for word in ["staging", "stage"]):
            requirements["environment"] = "staging"
        elif any(word in description_lower for word in ["production", "prod", "live"]):
            requirements["environment"] = "production"
        
        # Scaling requirements
        if any(word in description_lower for word in ["high traffic", "scale", "load"]):
            requirements["scaling"] = "high"
        elif any(word in description_lower for word in ["minimal", "simple", "basic"]):
            requirements["scaling"] = "minimal"
        
        return requirements
    
    async def _ai_parse_description(self, description: str) -> Dict:
        """Use AI to parse more complex requirements"""
        try:
            prompt = f"""
            Parse the following deployment description and extract structured information.
            Return a JSON object with the following fields:
            - cloud_provider: aws, gcp, or azure
            - app_type: python, nodejs, java, etc.
            - deployment_preference: vm, serverless, kubernetes, or auto
            - environment: development, staging, or production
            - scaling: minimal, moderate, or high
            - special_requirements: list of any special requirements
            - estimated_resources: small, medium, or large
            
            Description: "{description}"
            
            Return only valid JSON:
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean up the response to extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1]
            
            return json.loads(content)
            
        except Exception as e:
            logger.warning(f"AI parsing failed: {e}")
            return {}
    
    def _fallback_parse(self, description: str) -> Dict:
        """Fallback parsing when AI fails"""
        return {
            "cloud_provider": "aws",
            "app_type": "unknown",
            "deployment_preference": "auto",
            "environment": "production",
            "scaling": "minimal",
            "special_requirements": [],
            "estimated_resources": "small",
            "original_description": description,
            "parsing_method": "fallback"
        }
    
    def validate_requirements(self, requirements: Dict) -> bool:
        """Validate that requirements are complete and valid"""
        required_fields = [
            "cloud_provider", "environment", "scaling"
        ]
        
        for field in required_fields:
            if field not in requirements:
                return False
        
        # Validate cloud provider
        valid_providers = ["aws", "gcp", "azure"]
        if requirements["cloud_provider"] not in valid_providers:
            return False
        
        return True
