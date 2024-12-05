from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
from urllib.parse import urlparse
import git
import logging
import httpx
import ollama
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Store repository contents
repo_contents = {}

OLLAMA_URL = 'https://5055-35-247-164-214.ngrok-free.app/'

# Create directory for storing repository text files
REPO_FILES_DIR = 'typescript_repos'
if not os.path.exists(REPO_FILES_DIR):
    os.makedirs(REPO_FILES_DIR)

def save_repo_to_file(chat_id: str, content: str) -> str:
    """
    Save repository contents to a text file.
    Returns the path to the created file.
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ts_repo_{chat_id}_{timestamp}.txt"
        file_path = os.path.join(REPO_FILES_DIR, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            # Add a header with metadata
            f.write(f"TypeScript Repository Contents\n")
            f.write(f"Chat ID: {chat_id}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(content)
            
        logger.info(f"Saved TypeScript repository contents to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving repository to file: {str(e)}")
        raise

def is_typescript_or_package_file(file_path: str) -> bool:
    """Check if the file is a TypeScript file or package.json."""
    allowed_files = {'.ts', '.tsx', 'package.json'}
    _, ext = os.path.splitext(file_path)
    file_name = os.path.basename(file_path)
    
    return ext.lower() in allowed_files or file_name == 'package.json'

def is_binary_or_large_file(file_path: str, max_size_mb: int = 1) -> bool:
    """Check if file is binary or too large."""
    if os.path.getsize(file_path) > max_size_mb * 1024 * 1024:
        return True
        
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file.read(1024)
            return False
    except (UnicodeDecodeError, IOError):
        return True

def process_repository(repo_url: str, chat_id: str):
    """Process repository and store its TypeScript and package.json contents."""
    try:
        parsed_url = urlparse(repo_url)
        if not parsed_url.scheme or not parsed_url.netloc or not parsed_url.path:
            raise ValueError("Invalid GitHub repository URL")

        repo_name = os.path.splitext(parsed_url.path.split('/')[-1])[0]
        logger.info(f"Processing TypeScript repository: {repo_name}")

        ignored_directories = {
            '.git', '__pycache__', 'node_modules', 'dist', 'build',
            'coverage', '.idea', '.vscode', '.next', '.nuxt',
            'public', 'static', 'assets'
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Created temporary directory")
            try:
                repo = git.Repo.clone_from(repo_url, os.path.join(temp_dir, repo_name))
                logger.info(f"Cloned repository: {repo_name}")
            except git.exc.GitCommandError as e:
                logger.error(f"Git clone failed: {str(e)}")
                raise ValueError("Failed to clone repository. Please check the URL and try again.")

            # Store all file contents
            files_content = []
            processed_files = 0
            
            # Add repository information
            files_content.append(f"Repository: {repo_url}")
            files_content.append(f"Repository Name: {repo_name}")
            files_content.append("=" * 80 + "\n")
            
            # First, look for package.json
            package_json_path = os.path.join(temp_dir, repo_name, 'package.json')
            if os.path.exists(package_json_path):
                try:
                    with open(package_json_path, "r", encoding="utf-8") as content_file:
                        content = content_file.read()
                        files_content.append(f"\nFile: package.json")
                        files_content.append("-" * 80)
                        files_content.append(content)
                        files_content.append("=" * 80 + "\n")
                        processed_files += 1
                except UnicodeDecodeError:
                    logger.warning("Could not read package.json")
            
            # Then process TypeScript files
            for root, dirs, files in os.walk(os.path.join(temp_dir, repo_name)):
                dirs[:] = [d for d in dirs if d not in ignored_directories]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, os.path.join(temp_dir, repo_name))
                    
                    if not is_typescript_or_package_file(file_path) or is_binary_or_large_file(file_path):
                        continue
                        
                    try:
                        with open(file_path, "r", encoding="utf-8") as content_file:
                            content = content_file.read()
                            if not content.strip():
                                continue
                            
                            # Add file metadata and content
                            files_content.append(f"\nFile: {relative_path}")
                            files_content.append("-" * 80)
                            files_content.append(content)
                            files_content.append("=" * 80 + "\n")
                            processed_files += 1
                                
                    except UnicodeDecodeError:
                        continue

            logger.info(f"Processed {processed_files} TypeScript files")
            if processed_files == 0:
                raise ValueError("No valid TypeScript files found in the repository")

            # Join all content with proper formatting
            full_content = "\n".join(files_content)
            
            # Store in memory
            repo_contents[chat_id] = full_content
            
            # Save to file (can be commented out if not needed)
            save_repo_to_file(chat_id, full_content)

    except Exception as e:
        logger.error(f"Error in process_repository: {str(e)}")
        raise

def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using the entire TypeScript codebase context."""
    try:
        if chat_id not in repo_contents:
            raise ValueError("Repository not loaded. Please load a repository first.")

        system_message = """You are a TypeScript expert analyzing a GitHub repository. 
        Provide a comprehensive answer based on the TypeScript codebase content.
        Consider TypeScript-specific features, types, and patterns in your analysis.
        When referring to specific files or code sections, mention the file names for clarity."""

        context = f"Repository contents:\n{repo_contents[chat_id]}"

        messages = [
            {"role": "system", "content": f"{system_message}\n{context}"}
        ]

        # Add conversation history
        if conversation_history:
            for line in conversation_history.split('\n'):
                if line.startswith('User: '):
                    messages.append({"role": "user", "content": line[6:]})
                elif line.startswith('Assistant: '):
                    messages.append({"role": "assistant", "content": line[11:]})

        messages.append({"role": "user", "content": query})

        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            response = ollama_client.chat(model='code2', messages=messages)
        
        logger.info("Generated response using full TypeScript repository context")
        return response['message']['content']

    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        raise

@app.route('/load-repo', methods=['POST'])
def load_repo():
    """Load a GitHub repository and process its TypeScript files."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        repo_url = data.get('repo_url')
        chat_id = data.get('chat_id')

        if not repo_url or not chat_id:
            return jsonify({'error': 'repo_url and chat_id are required'}), 400

        logger.info(f"Loading TypeScript repository: {repo_url} for chat: {chat_id}")
        process_repository(repo_url, chat_id)
        return jsonify({'status': 'success'})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in load_repo: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/files', methods=['POST'])
def get_files():
    """Get list of TypeScript files in the repository for a specific chat."""
    try:
        data = request.json
        if not data or 'chat_id' not in data:
            return jsonify({'error': 'chat_id is required'}), 400

        chat_id = data['chat_id']
        
        if chat_id not in repo_contents:
            return jsonify({'files': []})
        
        # Extract file names from the stored content
        files = []
        for line in repo_contents[chat_id].split('\n'):
            if line.startswith('File: '):
                files.append(line[6:].strip())
        
        return jsonify({'files': sorted(set(files))})

    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Handle chat requests about TypeScript code."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        query = data.get('query')
        chat_id = data.get('chat_id')
        conversation_history = data.get('conversation_history', '')

        if not query or not chat_id:
            return jsonify({'error': 'query and chat_id are required'}), 400

        logger.info(f"Processing TypeScript chat query for chat: {chat_id}")
        response = generate_response(chat_id, conversation_history, query)
        return jsonify({'response': response})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in chat_endpoint: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True)