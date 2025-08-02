from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger()

class DeploymentEngine:
    def __init__(self):
        self.deployment_strategies = {
            'vm': {
                'description': 'Virtual Machine deployment',
                'suitable_for': ['traditional apps', 'complex dependencies', 'stateful apps'],
                'cost': 'medium',
                'complexity': 'low'
            },
            'serverless': {
                'description': 'Serverless function deployment',
                'suitable_for': ['stateless APIs', 'event-driven', 'low traffic'],
                'cost': 'low',
                'complexity': 'medium'
            },
            'container': {
                'description': 'Containerized deployment',
                'suitable_for': ['microservices', 'scalable apps', 'modern frameworks'],
                'cost': 'medium',
                'complexity': 'medium'
            },
            'kubernetes': {
                'description': 'Kubernetes cluster deployment',
                'suitable_for': ['high availability', 'microservices', 'enterprise'],
                'cost': 'high',
                'complexity': 'high'
            }
        }
    
    def determine_strategy(self, requirements: Dict, repo_analysis: Dict) -> Dict:
        """
        Determine the optimal deployment strategy based on requirements and analysis
        """
        logger.info("Determining deployment strategy...")
        
        strategy_scores = {}
        
        # Score each strategy based on various factors
        for strategy in self.deployment_strategies.keys():
            score = self._calculate_strategy_score(strategy, requirements, repo_analysis)
            strategy_scores[strategy] = score
        
        # Select the best strategy
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        
        # Check user preference override
        user_preference = requirements.get('deployment_preference')
        if user_preference and user_preference != 'auto':
            if user_preference in self.deployment_strategies:
                best_strategy = user_preference
                logger.info(f"Using user-preferred strategy: {best_strategy}")
        
        # Generate deployment configuration
        deployment_config = self._generate_deployment_config(
            best_strategy, requirements, repo_analysis
        )
        
        logger.info(f"Selected deployment strategy: {best_strategy}")
        return deployment_config
    
    def _calculate_strategy_score(self, strategy: str, requirements: Dict, repo_analysis: Dict) -> float:
        """Calculate suitability score for a deployment strategy"""
        score = 0.0
        
        language = repo_analysis.get('language')
        framework = repo_analysis.get('framework')
        services = repo_analysis.get('required_services', [])
        scaling = requirements.get('scaling', 'minimal')
        environment = requirements.get('environment', 'production')
        
        if strategy == 'vm':
            # VM is good for traditional apps and complex dependencies
            score += 0.5  # Base score
            
            if language in ['python', 'java']:
                score += 0.2
            
            if len(services) > 0:
                score += 0.3  # Good for apps with databases
            
            if framework in ['django', 'spring']:
                score += 0.2
            
            if scaling == 'minimal':
                score += 0.1
        
        elif strategy == 'serverless':
            # Serverless is good for stateless APIs and simple apps
            score += 0.3  # Base score
            
            if framework in ['flask', 'fastapi', 'express']:
                score += 0.4
            
            if len(services) == 0:
                score += 0.3  # No external dependencies
            
            if scaling == 'minimal':
                score += 0.2
            
            if language == 'nodejs':
                score += 0.1
            
            # Penalize if has databases or complex requirements
            if len(services) > 1:
                score -= 0.5
        
        elif strategy == 'container':
            # Container is good for modern apps and moderate scaling
            score += 0.4  # Base score
            
            if repo_analysis.get('dockerfile_present'):
                score += 0.3
            
            if framework in ['fastapi', 'express', 'flask']:
                score += 0.2
            
            if scaling in ['moderate', 'high']:
                score += 0.2
            
            if language in ['python', 'nodejs']:
                score += 0.1
        
        elif strategy == 'kubernetes':
            # Kubernetes is good for high availability and enterprise
            score += 0.2  # Base score
            
            if scaling == 'high':
                score += 0.4
            
            if environment == 'production':
                score += 0.2
            
            if len(services) > 2:
                score += 0.2
            
            # Penalize for simple apps
            if scaling == 'minimal':
                score -= 0.3
        
        return max(score, 0.0)
    
    def _generate_deployment_config(self, strategy: str, requirements: Dict, repo_analysis: Dict) -> Dict:
        """Generate deployment configuration for the selected strategy"""
        
        config = {
            'strategy': strategy,
            'cloud_provider': requirements.get('cloud_provider', 'aws'),
            'environment': requirements.get('environment', 'production'),
            'application': {
                'language': repo_analysis.get('language'),
                'framework': repo_analysis.get('framework'),
                'port': repo_analysis.get('port', self._get_default_port(repo_analysis)),
                'build_commands': repo_analysis.get('build_commands', []),
                'start_commands': repo_analysis.get('start_commands', []),
                'environment_vars': repo_analysis.get('environment_vars', []),
                'dependencies': repo_analysis.get('dependencies', {}),
            },
            'infrastructure': self._generate_infrastructure_config(strategy, requirements, repo_analysis),
            'services': self._generate_services_config(repo_analysis.get('required_services', [])),
            'networking': self._generate_networking_config(strategy, repo_analysis),
            'monitoring': self._generate_monitoring_config(strategy, requirements),
            'estimated_cost': self._estimate_cost(strategy, requirements, repo_analysis)
        }
        
        return config
    
    def _get_default_port(self, repo_analysis: Dict) -> int:
        """Get default port based on framework"""
        framework = repo_analysis.get('framework')
        language = repo_analysis.get('language')
        
        port_mapping = {
            'flask': 5000,
            'django': 8000,
            'fastapi': 8000,
            'express': 3000,
            'spring': 8080,
            'streamlit': 8501
        }
        
        if framework in port_mapping:
            return port_mapping[framework]
        elif language == 'python':
            return 8000
        elif language == 'nodejs':
            return 3000
        else:
            return 8080
    
    def _generate_infrastructure_config(self, strategy: str, requirements: Dict, repo_analysis: Dict) -> Dict:
        """Generate infrastructure configuration"""
        
        base_config = {
            'region': 'us-east-1',  # Default region
            'availability_zones': ['us-east-1a', 'us-east-1b'],
        }
        
        if strategy == 'vm':
            base_config.update({
                'instance_type': self._determine_instance_type(requirements, repo_analysis),
                'storage': '20GB',
                'auto_scaling': False,
                'load_balancer': False
            })
        
        elif strategy == 'serverless':
            base_config.update({
                'memory': repo_analysis.get('estimated_memory', '512MB'),
                'timeout': '30s',
                'runtime': self._get_serverless_runtime(repo_analysis),
                'triggers': ['http']
            })
        
        elif strategy == 'container':
            base_config.update({
                'container_registry': True,
                'instance_type': self._determine_instance_type(requirements, repo_analysis),
                'replicas': 1,
                'auto_scaling': True,
                'load_balancer': True
            })
        
        elif strategy == 'kubernetes':
            base_config.update({
                'cluster_size': 2,
                'node_type': self._determine_instance_type(requirements, repo_analysis),
                'auto_scaling': True,
                'load_balancer': True,
                'ingress': True
            })
        
        return base_config
    
    def _determine_instance_type(self, requirements: Dict, repo_analysis: Dict) -> str:
        """Determine appropriate instance type"""
        scaling = requirements.get('scaling', 'minimal')
        language = repo_analysis.get('language')
        services = len(repo_analysis.get('required_services', []))
        
        if scaling == 'high' or services > 2:
            return 't3.large'
        elif scaling == 'moderate' or language == 'java':
            return 't3.medium'
        else:
            return 't3.micro'
    
    def _get_serverless_runtime(self, repo_analysis: Dict) -> str:
        """Get serverless runtime based on language"""
        language = repo_analysis.get('language')
        
        runtime_mapping = {
            'python': 'python3.9',
            'nodejs': 'nodejs18.x',
            'java': 'java11'
        }
        
        return runtime_mapping.get(language, 'python3.9')
    
    def _generate_services_config(self, required_services: List[str]) -> Dict:
        """Generate configuration for required services"""
        services_config = {}
        
        for service in required_services:
            if service == 'postgresql':
                services_config['database'] = {
                    'type': 'postgresql',
                    'version': '13',
                    'instance_class': 'db.t3.micro',
                    'storage': '20GB'
                }
            elif service == 'mysql':
                services_config['database'] = {
                    'type': 'mysql',
                    'version': '8.0',
                    'instance_class': 'db.t3.micro',
                    'storage': '20GB'
                }
            elif service == 'redis':
                services_config['cache'] = {
                    'type': 'redis',
                    'version': '6.2',
                    'node_type': 'cache.t3.micro'
                }
            elif service == 'mongodb':
                services_config['database'] = {
                    'type': 'mongodb',
                    'version': '4.4',
                    'instance_class': 't3.small'
                }
        
        return services_config
    
    def _generate_networking_config(self, strategy: str, repo_analysis: Dict) -> Dict:
        """Generate networking configuration"""
        port = repo_analysis.get('port', self._get_default_port(repo_analysis))
        
        config = {
            'vpc': True,
            'public_subnets': 2,
            'private_subnets': 2,
            'internet_gateway': True,
            'application_port': port,
            'health_check_path': '/' if strategy != 'serverless' else None
        }
        
        if strategy in ['container', 'kubernetes']:
            config['load_balancer'] = True
            config['ssl_certificate'] = True
        
        return config
    
    def _generate_monitoring_config(self, strategy: str, requirements: Dict) -> Dict:
        """Generate monitoring configuration"""
        environment = requirements.get('environment', 'production')
        
        config = {
            'logging': True,
            'metrics': True,
            'alerts': environment == 'production',
            'log_retention': '30 days' if environment == 'production' else '7 days'
        }
        
        if strategy in ['container', 'kubernetes']:
            config['distributed_tracing'] = True
        
        return config
    
    def _estimate_cost(self, strategy: str, requirements: Dict, repo_analysis: Dict) -> Dict:
        """Estimate monthly cost for the deployment"""
        
        base_costs = {
            'vm': {'t3.micro': 8.5, 't3.medium': 33.7, 't3.large': 67.4},
            'serverless': {'base': 0, 'per_million_requests': 0.20},
            'container': {'base': 50, 'per_instance': 33.7},
            'kubernetes': {'base': 73, 'per_node': 67.4}
        }
        
        cost_estimate = {
            'strategy': strategy,
            'monthly_estimate_usd': 0,
            'breakdown': {}
        }
        
        if strategy == 'vm':
            instance_type = self._determine_instance_type(requirements, repo_analysis)
            cost = base_costs['vm'].get(instance_type, 33.7)
            cost_estimate['monthly_estimate_usd'] = cost
            cost_estimate['breakdown']['compute'] = cost
        
        elif strategy == 'serverless':
            cost_estimate['monthly_estimate_usd'] = 5  # Estimated for low traffic
            cost_estimate['breakdown']['functions'] = 5
        
        elif strategy == 'container':
            base_cost = base_costs['container']['base']
            instance_cost = base_costs['container']['per_instance']
            total_cost = base_cost + instance_cost
            cost_estimate['monthly_estimate_usd'] = total_cost
            cost_estimate['breakdown']['container_service'] = base_cost
            cost_estimate['breakdown']['compute'] = instance_cost
        
        elif strategy == 'kubernetes':
            base_cost = base_costs['kubernetes']['base']
            node_cost = base_costs['kubernetes']['per_node'] * 2  # 2 nodes
            total_cost = base_cost + node_cost
            cost_estimate['monthly_estimate_usd'] = total_cost
            cost_estimate['breakdown']['cluster'] = base_cost
            cost_estimate['breakdown']['nodes'] = node_cost
        
        # Add service costs
        services = repo_analysis.get('required_services', [])
        service_cost = len(services) * 15  # Rough estimate per service
        cost_estimate['monthly_estimate_usd'] += service_cost
        if service_cost > 0:
            cost_estimate['breakdown']['services'] = service_cost
        
        return cost_estimate
