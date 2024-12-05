import os
import tempfile
import git
from flask import jsonify, request
import logging
import re
from typing import Optional, Dict, List
import ollama
import httpx

logger = logging.getLogger(__name__)

class FileOperationManager:
    def __init__(self):
        self.file_operations = {}
        self.OLLAMA_URL = "https://867d-35-185-179-50.ngrok-free.app/"

    def is_code_file(self, file_path: str) -> bool:
        """Check if the file is a relevant code file."""
        code_extensions = {
            '.py', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php',
            '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
            '.html', '.css', '.scss', '.sass',
            '.json', '.yaml', '.yml', '.toml', '.ini',
            '.tf', '.hcl', 'Dockerfile', '.dockerignore', '.md'
        }
        
        _, ext = os.path.splitext(file_path)
        file_name = os.path.basename(file_path)
        
        return ext.lower() in code_extensions or file_name in {'Dockerfile', 'docker-compose.yml'}

    def is_binary_or_large_file(self, file_path: str, max_size_mb: int = 1) -> bool:
        """Check if file is binary or too large."""
        if os.path.getsize(file_path) > max_size_mb * 1024 * 1024:
            return True
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file.read(1024)
                return False
        except (UnicodeDecodeError, IOError):
            return True

    def create_chunks(self, content: str, file_path: str, chunk_size: int = 1500) -> list[dict]:
        """Create chunks from content with smart splitting."""
        chunks = []
        current_chunk = []
        current_length = 0
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if current_length + len(line) > chunk_size and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'file_path': file_path,
                    'start_line': i - len(current_chunk) + 1,
                    'end_line': i
                })
                current_chunk = []
                current_length = 0
            
            current_chunk.append(line)
            current_length += len(line) + 1
        
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'content': chunk_text,
                'file_path': file_path,
                'start_line': len(lines) - len(current_chunk) + 1,
                'end_line': len(lines)
            })
        
        return chunks

    def add_chunks_to_vector_db(self, collection, chunks: list[dict], chat_id: str, file_path: str, encoder):
        """Add chunks to the vector database with metadata."""
        try:
            if not chunks:
                return

            documents = [chunk['content'] for chunk in chunks]
            embeddings = encoder.encode(documents)
            
            metadatas = [{
                "chat_id": chat_id,
                "file_path": file_path,
                "start_line": chunk['start_line'],
                "end_line": chunk['end_line'],
                "chunk_index": i
            } for i, chunk in enumerate(chunks)]

            ids = [f"{chat_id}_{file_path}_chunk_{i}" for i in range(len(chunks))]

            collection.add(
                embeddings=embeddings.tolist(),
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(chunks)} chunks from {file_path} to collection")

        except Exception as e:
            logger.error(f"Error in add_chunks_to_vector_db: {str(e)}")
            raise

    def parse_github_repo_and_add_to_vector_db(self, repo_url: str, chat_id: str, chroma_client, encoder, chunk_size: int = 1500):
        """Parse repository and add chunks to the chat-specific collection."""
        try:
            collection = chroma_client.get_or_create_collection(name=f"chat_{chat_id}")
            collection.delete(where={"chat_id": chat_id})
            
            with tempfile.TemporaryDirectory() as temp_dir:
                repo = git.Repo.clone_from(repo_url, temp_dir)
                
                ignored_directories = {
                    '.git', '__pycache__', 'node_modules', 'venv',
                    'dist', 'build', 'target', 'bin', 'obj'
                }
                
                processed_files = 0
                for root, dirs, files in os.walk(temp_dir):
                    dirs[:] = [d for d in dirs if d not in ignored_directories]
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, temp_dir)
                        
                        if not self.is_code_file(file_path) or self.is_binary_or_large_file(file_path):
                            continue
                            
                        try:
                            with open(file_path, "r", encoding="utf-8") as content_file:
                                content = content_file.read()
                                if not content.strip():
                                    continue
                                
                                chunks = self.create_chunks(content, relative_path, chunk_size)
                                if chunks:
                                    self.add_chunks_to_vector_db(collection, chunks, chat_id, relative_path, encoder)
                                    processed_files += 1
                                    
                        except UnicodeDecodeError:
                            continue

                logger.info(f"Processed {processed_files} code files")
                if processed_files == 0:
                    raise ValueError("No valid code files found in the repository")

        except Exception as e:
            logger.error(f"Error in parse_github_repo_and_add_to_vector_db: {str(e)}")
            raise

    def handle_code_request(self, chat_id: str, query: str, conversation_history: str) -> str:
        """Handle code generation and modification requests."""
        try:
            # Analyze the query to determine the type of code request
            file_match = re.search(r'(?:create|make|generate|write|add|implement|fix)\s+(?:a|an)?\s*(?:new)?\s*(?:file)?\s*(?:called)?\s*[`"]?([^`"\s]+)[`"]?', query.lower())
            
            if file_match:
                # File creation/modification request
                filename = file_match.group(1)
                return self.generate_code_file(chat_id, filename, query, conversation_history)
            else:
                # Code modification request
                return self.modify_existing_code(chat_id, query, conversation_history)
        
        except Exception as e:
            logger.error(f"Error handling code request: {str(e)}")
            raise

    def generate_code_file(self, chat_id: str, filename: str, query: str, conversation_history: str) -> str:
        """Generate a new code file based on the query."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert programmer using DeepSeek Coder. Generate complete, production-ready code files based on user requests."
                },
                {
                    "role": "user",
                    "content": f"Generate a complete, production-ready {filename} file with the following requirements:\n\n{query}"
                }
            ]

            ollama_client = ollama.Client(host=self.OLLAMA_URL)
            response = ollama_client.chat(model='deepseek-coder-v2:latest', messages=messages)
            
            # Extract code from response
            code_content = self.extract_code_from_response(response['message']['content'])
            
            # Save the file
            self.save_generated_file(chat_id, filename, code_content)
            
            return f"I've created the {filename} file with the following content:\n\n```\n{code_content}\n```"

        except Exception as e:
            logger.error(f"Error generating code file: {str(e)}")
            raise

    def modify_existing_code(self, chat_id: str, query: str, conversation_history: str) -> str:
        """Modify existing code based on the query."""
        try:
            active_file = self.file_operations.get(chat_id, {}).get('active_file')
            if not active_file:
                raise ValueError("No active file selected for modification")

            with open(active_file, 'r') as f:
                current_code = f.read()
            
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert programmer using DeepSeek Coder. Modify the existing code based on the user's request."
                },
                {
                    "role": "user",
                    "content": f"Here's the current code:\n\n{current_code}\n\nModify it according to this request:\n{query}"
                }
            ]

            ollama_client = ollama.Client(host=self.OLLAMA_URL)
            response = ollama_client.chat(model='deepseek-coder-v2:latest', messages=messages)
            
            # Extract and save modified code
            modified_code = self.extract_code_from_response(response['message']['content'])
            self.save_modified_file(chat_id, active_file, modified_code)
            
            return f"I've modified the code as requested:\n\n```\n{modified_code}\n```"

        except Exception as e:
            logger.error(f"Error modifying code: {str(e)}")
            raise

    def extract_code_from_response(self, response: str) -> str:
        """Extract code blocks from the response."""
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        return code_blocks[0] if code_blocks else response

    def save_generated_file(self, chat_id: str, filename: str, content: str):
        """Save a newly generated file."""
        try:
            file_path = os.path.join('generated_files', chat_id, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            self.file_operations[chat_id] = self.file_operations.get(chat_id, {})
            self.file_operations[chat_id]['active_file'] = file_path
            self.file_operations[chat_id][file_path] = {
                'status': 'done',
                'progress': 100
            }
            
            logger.info(f"Saved generated file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving generated file: {str(e)}")
            raise

    def save_modified_file(self, chat_id: str, file_path: str, content: str):
        """Save modifications to an existing file."""
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            
            self.file_operations[chat_id] = self.file_operations.get(chat_id, {})
            self.file_operations[chat_id][file_path] = {
                'status': 'done',
                'progress': 100
            }
            
            logger.info(f"Saved modified file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving modified file: {str(e)}")
            raise

    def get_files_endpoint(self, chroma_client):
        """Handle the /files endpoint."""
        try:
            data = request.json
            if not data or 'chat_id' not in data:
                return jsonify({'error': 'chat_id is required'}), 400

            chat_id = data['chat_id']
            collection = chroma_client.get_or_create_collection(name=f"chat_{chat_id}")
            
            results = collection.get(
                where={"chat_id": chat_id},
                include=['metadatas']
            )
            
            if not results['metadatas']:
                return jsonify({'files': []})
            
            files = sorted(set(
                metadata['file_path'] 
                for metadata in results['metadatas']
                if 'file_path' in metadata
            ))
            
            return jsonify({'files': files})

        except Exception as e:
            logger.error(f"Error getting files: {str(e)}")
            return jsonify({'error': str(e)}), 500

    def save_file_endpoint(self):
        """Handle the /save-file endpoint."""
        try:
            data = request.json
            if not data or 'path' not in data or 'content' not in data or 'chat_id' not in data:
                return jsonify({'error': 'Missing required fields'}), 400

            chat_id = data['chat_id']
            file_path = data['path']
            content = data['content']

            # Update file operations status
            self.file_operations[chat_id] = self.file_operations.get(chat_id, {})
            self.file_operations[chat_id][file_path] = {
                'status': 'saving',
                'progress': 0
            }

            # Save the file
            self.save_generated_file(chat_id, file_path, content)

            return jsonify({'success': True})

        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return jsonify({'error': str(e)}), 500

    def get_file_status_endpoint(self):
        """Handle the /file-status endpoint."""
        chat_id = request.args.get('chat_id')
        file_path = request.args.get('path')
        
        if not chat_id or not file_path:
            return jsonify({'error': 'Missing required parameters'}), 400

        status = self.file_operations.get(chat_id, {}).get(file_path, {
            'status': 'unknown',
            'progress': 0
        })

        return jsonify(status)