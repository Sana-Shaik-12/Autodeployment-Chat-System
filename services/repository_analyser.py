import os
import tempfile
import shutil
import json
import re
from typing import Dict, List, Optional, Tuple
import git
import asyncio
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger()

class RepositoryAnalyzer:
    def __init__(self):
        self.supported_languages = {
            'python': {
                'files': ['*.py'],
                'deps': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
                'frameworks': {
                    'flask': ['from flask', 'import flask', 'Flask(__name__)'],
                    'django': ['django', 'DJANGO_SETTINGS_MODULE', 'manage.py'],
                    'fastapi': ['from fastapi', 'import fastapi', 'FastAPI()'],
                    'streamlit': ['import streamlit', 'streamlit run']
                },
                'entry_points': ['main.py', 'app.py', 'server.py', 'run.py', 'wsgi.py']
            },
            'nodejs': {
                'files': ['*.js', '*.ts'],
                'deps': ['package.json', 'yarn.lock', 'package-lock.json'],
                'frameworks': {
                    'express': ['express', 'app.listen'],
                    'react': ['react', 'ReactDOM'],
                    'next': ['next', 'Next.js'],
                    'vue': ['vue', 'Vue'],
                    'angular': ['@angular', 'ng serve']
                },
                'entry_points': ['index.js', 'server.js', 'app.js', 'main.js']
            },
            'java': {
                'files': ['*.java'],
                'deps': ['pom.xml', 'build.gradle', 'gradle.build'],
                'frameworks': {
                    'spring': ['@SpringBootApplication', 'spring-boot'],
                    'spring-mvc': ['@Controller', '@RestController']
                },
                'entry_points': ['Application.java', 'Main.java']
            }
        }
    
    async def analyze_repository(self, repo_url: str) -> Dict:
        """
        Analyze a repository to understand its structure and requirements
        """
        temp_dir = None
        try:
            # Clone repository to temporary directory
            temp_dir = await self._clone_repository(repo_url)
            
            # Analyze the repository
            analysis = {
                'repo_url': repo_url,
                'language': None,
                'framework': None,
                'dependencies': {},
                'entry_points': [],
                'port': None,
                'environment_vars': [],
                'dockerfile_present': False,
                'docker_compose_present': False,
                'build_commands': [],
                'start_commands': [],
                'required_services': [],
                'estimated_memory': '512Mi',
                'estimated_cpu': '0.5',
                'analysis_confidence': 0.0
            }
            
            # Detect language and framework
            language_info = self._detect_language_and_framework(temp_dir)
            analysis.update(language_info)
            
            # Analyze dependencies
            analysis['dependencies'] = self._analyze_dependencies(temp_dir, analysis['language'])
            
            # Find entry points and commands
            analysis['entry_points'] = self._find_entry_points(temp_dir, analysis['language'])
            analysis['start_commands'] = self._generate_start_commands(temp_dir, analysis)
            analysis['build_commands'] = self._generate_build_commands(temp_dir, analysis)
            
            # Detect port and environment variables
            analysis['port'] = self._detect_port(temp_dir)
            analysis['environment_vars'] = self._detect_environment_vars(temp_dir)
            
            # Check for Docker files
            analysis['dockerfile_present'] = os.path.exists(os.path.join(temp_dir, 'Dockerfile'))
            analysis['docker_compose_present'] = os.path.exists(os.path.join(temp_dir, 'docker-compose.yml'))
            
            # Detect required services (databases, etc.)
            analysis['required_services'] = self._detect_required_services(temp_dir, analysis)
            
            # Estimate resources
            analysis['estimated_memory'], analysis['estimated_cpu'] = self._estimate_resources(analysis)
            
            # Calculate confidence score
            analysis['analysis_confidence'] = self._calculate_confidence(analysis)
            
            logger.info(f"Repository analysis complete: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            raise
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def _clone_repository(self, repo_url: str) -> str:
        """Clone repository to temporary directory"""
        temp_dir = tempfile.mkdtemp()
        try:
            logger.info(f"Cloning repository {repo_url} to {temp_dir}")
            repo = git.Repo.clone_from(repo_url, temp_dir)
            return temp_dir
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise Exception(f"Failed to clone repository: {e}")
    
    def _detect_language_and_framework(self, repo_path: str) -> Dict:
        """Detect primary language and framework"""
        language_scores = {}
        framework_info = {}
        
        # Count files by extension and content
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]
            
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = Path(file).suffix.lower()
                
                # Language detection by file extension
                if file_ext == '.py':
                    language_scores['python'] = language_scores.get('python', 0) + 1
                elif file_ext in ['.js', '.ts']:
                    language_scores['nodejs'] = language_scores.get('nodejs', 0) + 1
                elif file_ext == '.java':
                    language_scores['java'] = language_scores.get('java', 0) + 1
                
                # Framework detection by file content
                try:
                    if file_ext in ['.py', '.js', '.ts', '.java']:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            self._detect_framework_in_content(content, file_ext, framework_info)
                except Exception:
                    continue
        
        # Determine primary language
        primary_language = max(language_scores, key=language_scores.get) if language_scores else 'unknown'
        
        # Determine framework
        primary_framework = None
        if primary_language in framework_info:
            framework_scores = framework_info[primary_language]
            if framework_scores:
                primary_framework = max(framework_scores, key=framework_scores.get)
        
        return {
            'language': primary_language,
            'framework': primary_framework,
            'language_scores': language_scores,
            'framework_scores': framework_info
        }
    
    def _detect_framework_in_content(self, content: str, file_ext: str, framework_info: Dict):
        """Detect framework patterns in file content"""
        if file_ext == '.py':
            lang = 'python'
        elif file_ext in ['.js', '.ts']:
            lang = 'nodejs'
        elif file_ext == '.java':
            lang = 'java'
        else:
            return
        
        if lang not in framework_info:
            framework_info[lang] = {}
        
        if lang in self.supported_languages:
            for framework, patterns in self.supported_languages[lang]['frameworks'].items():
                for pattern in patterns:
                    if pattern.lower() in content.lower():
                        framework_info[lang][framework] = framework_info[lang].get(framework, 0) + 1
    
    def _analyze_dependencies(self, repo_path: str, language: str) -> Dict:
        """Analyze project dependencies"""
        dependencies = {}
        
        if language == 'python':
            # Check requirements.txt
            req_file = os.path.join(repo_path, 'requirements.txt')
            if os.path.exists(req_file):
                dependencies['requirements.txt'] = self._parse_requirements_txt(req_file)
            
            # Check setup.py
            setup_file = os.path.join(repo_path, 'setup.py')
            if os.path.exists(setup_file):
                dependencies['setup.py'] = self._parse_setup_py(setup_file)
        
        elif language == 'nodejs':
            # Check package.json
            package_file = os.path.join(repo_path, 'package.json')
            if os.path.exists(package_file):
                dependencies['package.json'] = self._parse_package_json(package_file)
        
        elif language == 'java':
            # Check pom.xml
            pom_file = os.path.join(repo_path, 'pom.xml')
            if os.path.exists(pom_file):
                dependencies['pom.xml'] = self._parse_pom_xml(pom_file)
        
        return dependencies
    
    def _parse_requirements_txt(self, file_path: str) -> List[str]:
        """Parse Python requirements.txt"""
        try:
            with open(file_path, 'r') as f:
                requirements = []
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        requirements.append(line)
                return requirements
        except Exception:
            return []
    
    def _parse_package_json(self, file_path: str) -> Dict:
        """Parse Node.js package.json"""
        try:
            with open(file_path, 'r') as f:
                package_data = json.load(f)
                return {
                    'dependencies': package_data.get('dependencies', {}),
                    'devDependencies': package_data.get('devDependencies', {}),
                    'scripts': package_data.get('scripts', {})
                }
        except Exception:
            return {}
    
    def _parse_setup_py(self, file_path: str) -> Dict:
        """Parse Python setup.py (basic parsing)"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Extract install_requires using regex
                install_requires_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if install_requires_match:
                    requirements_str = install_requires_match.group(1)
                    requirements = re.findall(r'["\']([^"\']+)["\']', requirements_str)
                    return {'install_requires': requirements}
        except Exception:
            pass
        return {}
    
    def _parse_pom_xml(self, file_path: str) -> Dict:
        """Parse Java pom.xml (basic parsing)"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Basic dependency extraction
                dependencies = re.findall(r'<artifactId>([^<]+)</artifactId>', content)
                return {'dependencies': dependencies}
        except Exception:
            return {}
    
    def _find_entry_points(self, repo_path: str, language: str) -> List[str]:
        """Find potential entry points for the application"""
        entry_points = []
        
        if language in self.supported_languages:
            possible_entries = self.supported_languages[language]['entry_points']
            
            for entry in possible_entries:
                entry_path = os.path.join(repo_path, entry)
                if os.path.exists(entry_path):
                    entry_points.append(entry)
        
        # Also check for any executable files or main functions
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if 'main' in file.lower() and not file.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    if rel_path not in entry_points:
                        entry_points.append(rel_path)
        
        return entry_points
    
    def _detect_port(self, repo_path: str) -> Optional[int]:
        """Detect the port the application runs on"""
        port_patterns = [
            r'port["\s]*[:=]["\s]*(\d+)',
            r'PORT["\s]*[:=]["\s]*(\d+)',
            r'listen\s*\(\s*(\d+)',
            r'\.listen\s*\(\s*(\d+)',
            r'app\.run\s*\([^)]*port\s*=\s*(\d+)',
        ]
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.java')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            for pattern in port_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    return int(matches[0])
                    except Exception:
                        continue
        
        return None
    
    def _detect_environment_vars(self, repo_path: str) -> List[str]:
        """Detect environment variables used by the application"""
        env_vars = set()
        env_patterns = [
            r'os\.environ\.get\(["\']([^"\']+)["\']',
            r'os\.environ\[["\']([^"\']+)["\']\]',
            r'process\.env\.([A-Z_]+)',
            r'System\.getenv\(["\']([^"\']+)["\']',
            r'\$\{([A-Z_]+)\}',
            r'env\.[A-Z_]+',
        ]
        
        # Check for .env files
        env_file = os.path.join(repo_path, '.env')
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            var_name = line.split('=')[0].strip()
                            env_vars.add(var_name)
            except Exception:
                pass
        
        # Check source code for environment variable usage
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.java', '.yml', '.yaml')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            for pattern in env_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                env_vars.update(matches)
                    except Exception:
                        continue
        
        return list(env_vars)
    
    def _detect_required_services(self, repo_path: str, analysis: Dict) -> List[str]:
        """Detect required external services (databases, caches, etc.)"""
        services = set()
        
        # Check dependencies for database/service indicators
        dependencies = analysis.get('dependencies', {})
        
        # Database detection patterns
        db_patterns = {
            'postgresql': ['psycopg2', 'postgresql', 'pg'],
            'mysql': ['mysql', 'pymysql', 'mysql2'],
            'mongodb': ['pymongo', 'mongodb', 'mongoose'],
            'redis': ['redis', 'redis-py', 'ioredis'],
            'sqlite': ['sqlite3', 'sqlite'],
            'elasticsearch': ['elasticsearch'],
        }
        
        for service, patterns in db_patterns.items():
            for dep_file, deps in dependencies.items():
                if isinstance(deps, list):
                    dep_text = ' '.join(deps).lower()
                elif isinstance(deps, dict):
                    dep_text = ' '.join(deps.keys()).lower()
                else:
                    continue
                
                for pattern in patterns:
                    if pattern in dep_text:
                        services.add(service)
        
        # Check for docker-compose services
        compose_file = os.path.join(repo_path, 'docker-compose.yml')
        if os.path.exists(compose_file):
            try:
                with open(compose_file, 'r') as f:
                    content = f.read().lower()
                    for service in db_patterns.keys():
                        if service in content:
                            services.add(service)
            except Exception:
                pass
        
        return list(services)
    
    def _generate_start_commands(self, repo_path: str, analysis: Dict) -> List[str]:
        """Generate appropriate start commands based on analysis"""
        commands = []
        language = analysis.get('language')
        framework = analysis.get('framework')
        entry_points = analysis.get('entry_points', [])
        
        if language == 'python':
            if framework == 'flask':
                if 'app.py' in entry_points:
                    commands.append('python app.py')
                elif 'main.py' in entry_points:
                    commands.append('python main.py')
                else:
                    commands.append('flask run --host=0.0.0.0')
            elif framework == 'django':
                commands.append('python manage.py runserver 0.0.0.0:8000')
            elif framework == 'fastapi':
                if 'main.py' in entry_points:
                    commands.append('uvicorn main:app --host 0.0.0.0 --port 8000')
                else:
                    commands.append('uvicorn app:app --host 0.0.0.0 --port 8000')
            elif framework == 'streamlit':
                if 'app.py' in entry_points:
                    commands.append('streamlit run app.py --server.port 8501 --server.address 0.0.0.0')
            else:
                # Generic Python app
                if entry_points:
                    commands.append(f'python {entry_points[0]}')
        
        elif language == 'nodejs':
            package_json = os.path.join(repo_path, 'package.json')
            if os.path.exists(package_json):
                try:
                    with open(package_json, 'r') as f:
                        package_data = json.load(f)
                        scripts = package_data.get('scripts', {})
                        
                        if 'start' in scripts:
                            commands.append('npm start')
                        elif 'dev' in scripts:
                            commands.append('npm run dev')
                        elif 'main' in package_data:
                            commands.append(f'node {package_data["main"]}')
                except Exception:
                    pass
            
            if not commands and entry_points:
                commands.append(f'node {entry_points[0]}')
        
        elif language == 'java':
            if framework == 'spring':
                commands.append('java -jar target/*.jar')
            else:
                commands.append('java -cp target/classes com.example.Main')
        
        # Fallback commands
        if not commands:
            if language == 'python':
                commands.append('python main.py')
            elif language == 'nodejs':
                commands.append('node index.js')
        
        return commands
    
    def _generate_build_commands(self, repo_path: str, analysis: Dict) -> List[str]:
        """Generate build commands based on project type"""
        commands = []
        language = analysis.get('language')
        
        if language == 'python':
            commands.append('pip install -r requirements.txt')
        elif language == 'nodejs':
            if os.path.exists(os.path.join(repo_path, 'package-lock.json')):
                commands.append('npm ci')
            else:
                commands.append('npm install')
        elif language == 'java':
            if os.path.exists(os.path.join(repo_path, 'pom.xml')):
                commands.append('mvn clean package -DskipTests')
            elif os.path.exists(os.path.join(repo_path, 'build.gradle')):
                commands.append('./gradlew build -x test')
        
        return commands
    
    def _estimate_resources(self, analysis: Dict) -> Tuple[str, str]:
        """Estimate memory and CPU requirements"""
        language = analysis.get('language')
        framework = analysis.get('framework')
        services = analysis.get('required_services', [])
        
        # Base requirements by language
        base_memory = {
            'python': '512Mi',
            'nodejs': '256Mi',
            'java': '1Gi'
        }
        
        base_cpu = {
            'python': '0.5',
            'nodejs': '0.25',
            'java': '0.5'
        }
        
        memory = base_memory.get(language, '512Mi')
        cpu = base_cpu.get(language, '0.5')
        
        # Adjust for framework
        if framework in ['django', 'spring']:
            memory = '1Gi'
            cpu = '1'
        elif framework in ['fastapi', 'express']:
            memory = '512Mi'
            cpu = '0.5'
        
        # Adjust for services
        if len(services) > 2:
            memory = '1Gi'
            cpu = '1'
        
        return memory, cpu
    
    def _calculate_confidence(self, analysis: Dict) -> float:
        """Calculate confidence score for the analysis"""
        confidence = 0.0
        
        # Language detection confidence
        if analysis.get('language') != 'unknown':
            confidence += 0.3
        
        # Framework detection confidence
        if analysis.get('framework'):
            confidence += 0.2
        
        # Dependencies found
        if analysis.get('dependencies'):
            confidence += 0.2
        
        # Entry points found
        if analysis.get('entry_points'):
            confidence += 0.15
        
        # Port detected
        if analysis.get('port'):
            confidence += 0.1
        
        # Commands generated
        if analysis.get('start_commands'):
            confidence += 0.05
        
        return min(confidence, 1.0)
