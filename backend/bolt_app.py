from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
import shutil
from urllib.parse import urlparse
import git
import chromadb
from sentence_transformers import SentenceTransformer
import ollama
import PyPDF2
import numpy as np
from typing import List, Dict
import httpx
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize global variables
try:
    encoder = SentenceTransformer('all-MiniLM-L6-v2')
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    logger.info("Successfully initialized encoder and ChromaDB client")
except Exception as e:
    logger.error(f"Error initializing components: {str(e)}")
    raise

# Store active collections for each chat
active_collections = {}


OLLAMA_URL = 'https://8215-34-83-153-210.ngrok-free.app/'

def is_code_file(file_path: str) -> bool:
    """Check if the file is a relevant code file."""
    code_extensions = {
        '.py', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php',
        '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
        '.html', '.css', '.scss', '.sass',
        '.json', '.yaml', '.yml', '.toml', '.ini',
        '.tf', '.hcl', 
        'Dockerfile', '.dockerignore',
        '.md'
    }
    
    _, ext = os.path.splitext(file_path)
    file_name = os.path.basename(file_path)
    
    if file_name in {'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'}:
        return True
        
    return ext.lower() in code_extensions

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

def get_collection_for_chat(chat_id: str) -> chromadb.Collection:
    """Get or create a collection for a specific chat."""
    try:
        collection_name = f"chat_{chat_id}"
        
        try:
            collection = chroma_client.get_or_create_collection(name=collection_name)
            logger.info(f"Retrieved or created collection: {collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Error getting/creating collection: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in get_collection_for_chat: {str(e)}")
        raise
    
def parse_github_repo_and_add_to_vector_db(repo_url: str, chat_id: str, chunk_size: int = 1500):
    """Parse repository and add chunks to the chat-specific collection."""
    try:
        parsed_url = urlparse(repo_url)
        if not parsed_url.scheme or not parsed_url.netloc or not parsed_url.path:
            raise ValueError("Invalid GitHub repository URL")

        repo_name = os.path.splitext(parsed_url.path.split('/')[-1])[0]
        logger.info(f"Parsing repository: {repo_name}")

        ignored_directories = {
            '.git', '__pycache__', 'node_modules', 'venv', 'env',
            'dist', 'build', 'target', 'bin', 'obj', 'out',
            'coverage', '.idea', '.vscode', '.next', '.nuxt'
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Created temporary directory")
            try:
                repo = git.Repo.clone_from(repo_url, os.path.join(temp_dir, repo_name))
                logger.info(f"Cloned repository: {repo_name}")
            except git.exc.GitCommandError as e:
                logger.error(f"Git clone failed: {str(e)}")
                raise ValueError("Failed to clone repository. Please check the URL and try again.")

            collection = get_collection_for_chat(chat_id)
            collection.delete(where={"chat_id": chat_id})
            
            processed_files = 0
            for root, dirs, files in os.walk(os.path.join(temp_dir, repo_name)):
                dirs[:] = [d for d in dirs if d not in ignored_directories]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, os.path.join(temp_dir, repo_name))
                    
                    if not is_code_file(file_path) or is_binary_or_large_file(file_path):
                        continue
                        
                    try:
                        with open(file_path, "r", encoding="utf-8") as content_file:
                            content = content_file.read()
                            if not content.strip():
                                continue
                            
                            # Process file content into chunks and add to vector DB
                            chunks = create_chunks(content, relative_path, chunk_size)
                            if chunks:
                                add_chunks_to_vector_db(collection, chunks, chat_id, relative_path)
                                processed_files += 1
                                
                    except UnicodeDecodeError:
                        continue

            logger.info(f"Processed {processed_files} code files")
            if processed_files == 0:
                raise ValueError("No valid code files found in the repository")

    except Exception as e:
        logger.error(f"Error in parse_github_repo_and_add_to_vector_db: {str(e)}")
        raise

def create_chunks(content: str, file_path: str, chunk_size: int = 1500) -> List[Dict[str, str]]:
    """Create chunks from content with smart splitting and metadata."""
    chunks = []
    current_chunk = []
    current_length = 0
    
    # Split content into lines for better context preservation
    lines = content.split('\n')
    
    for line in lines:
        # Start new chunk if adding this line would exceed chunk size
        if current_length + len(line) > chunk_size and current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'content': chunk_text,
                'file_path': file_path,
                'start_line': len(chunks) * len(current_chunk) + 1,
                'end_line': (len(chunks) + 1) * len(current_chunk)
            })
            current_chunk = []
            current_length = 0
        
        # Add line to current chunk
        current_chunk.append(line)
        current_length += len(line) + 1  # +1 for newline
        
        # Check if we should create a new chunk based on code structure
        if any(marker in line for marker in ['class ', 'def ', 'function ', '@app.route', 'public class']):
            if current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'file_path': file_path,
                    'start_line': len(chunks) * len(current_chunk) + 1,
                    'end_line': (len(chunks) + 1) * len(current_chunk)
                })
                current_chunk = []
                current_length = 0
    
    # Add any remaining content as the last chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append({
            'content': chunk_text,
            'file_path': file_path,
            'start_line': len(chunks) * len(current_chunk) + 1,
            'end_line': (len(chunks) + 1) * len(current_chunk)
        })
    
    return chunks

def add_chunks_to_vector_db(collection: chromadb.Collection, chunks: List[Dict[str, str]], chat_id: str, file_path: str):
    """Add chunks to the vector database with metadata."""
    try:
        if not chunks:
            return

        # Prepare data for batch insertion
        documents = [chunk['content'] for chunk in chunks]
        embeddings = encoder.encode(documents)
        
        # Create metadata for each chunk
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "chat_id": chat_id,
                "file_path": file_path,
                "start_line": chunk['start_line'],
                "end_line": chunk['end_line'],
                "chunk_index": i
            }
            metadatas.append(metadata)

        # Generate unique IDs for each chunk
        ids = [f"{chat_id}_{file_path}_chunk_{i}" for i in range(len(chunks))]

        # Add to collection
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
    
def extract_function_name(query: str) -> str:
    """Extract function or class name from the query."""
    # Common patterns for function references in natural language
    patterns = [
        r'(?:function|method|class)\s+([a-zA-Z_]\w*)',  # "function xyz" or "method xyz"
        r'(?:the|a)\s+([a-zA-Z_]\w*)\s+(?:function|method|class)',  # "the xyz function"
        r'how\s+does\s+([a-zA-Z_]\w*)\s+work',  # "how does xyz work"
        r'what\s+does\s+([a-zA-Z_]\w*)\s+do',  # "what does xyz do"
        r'explain\s+(?:the\s+)?([a-zA-Z_]\w*)',  # "explain xyz"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def extract_functions_and_classes(content: str) -> List[Dict[str, any]]:
    """Extract functions and classes from code content."""
    structures = []
    lines = content.split('\n')
    current_structure = None
    
    # Regex patterns for different programming languages
    patterns = {
        'python': r'^\s*(def|class)\s+(\w+)',
        'javascript': r'^\s*(function|class)\s+(\w+)|^\s*(\w+)\s*=\s*(async\s*)?function',
        'java': r'^\s*(public|private|protected)?\s*(static\s+)?(class|interface|enum)\s+(\w+)|^\s*(public|private|protected)?\s*(static\s+)?\w+\s+(\w+)\s*\(',
    }
    
    for i, line in enumerate(lines):
        for lang, pattern in patterns.items():
            match = re.match(pattern, line)
            if match:
                if current_structure:
                    current_structure['end_line'] = i
                    structures.append(current_structure)
                
                current_structure = {
                    'type': match.group(1) if match.group(1) else 'function',
                    'name': match.group(2) if match.group(2) else match.group(0),
                    'start_line': i + 1,
                    'content': line,
                    'language': lang
                }
                break
    
    if current_structure:
        current_structure['end_line'] = len(lines)
        structures.append(current_structure)
    
    return structures

def create_chunks(content: str, file_path: str, chunk_size: int = 1500) -> List[Dict[str, str]]:
    """Create chunks from content with smart splitting based on code structure."""
    chunks = []
    
    # Extract functions and classes
    structures = extract_functions_and_classes(content)
    
    if structures:
        # Create chunks based on functions and classes
        lines = content.split('\n')
        current_pos = 0
        
        for structure in structures:
            # Add chunk for the code before the current structure if it exists
            if structure['start_line'] - 1 > current_pos:
                chunk_content = '\n'.join(lines[current_pos:structure['start_line']-1])
                if chunk_content.strip():
                    chunks.append({
                        'content': chunk_content,
                        'file_path': file_path,
                        'start_line': current_pos + 1,
                        'end_line': structure['start_line'] - 1,
                        'type': 'code_block'
                    })
            
            # Add chunk for the function or class
            chunk_content = '\n'.join(lines[structure['start_line']-1:structure['end_line']])
            chunks.append({
                'content': chunk_content,
                'file_path': file_path,
                'start_line': structure['start_line'],
                'end_line': structure['end_line'],
                'type': structure['type'],
                'name': structure['name']
            })
            
            current_pos = structure['end_line']
        
        # Add remaining code as a chunk if it exists
        if current_pos < len(lines):
            chunk_content = '\n'.join(lines[current_pos:])
            if chunk_content.strip():
                chunks.append({
                    'content': chunk_content,
                    'file_path': file_path,
                    'start_line': current_pos + 1,
                    'end_line': len(lines),
                    'type': 'code_block'
                })
    else:
        # If no functions/classes found, fall back to size-based chunking
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
                    'end_line': i,
                    'type': 'code_block'
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
                'end_line': len(lines),
                'type': 'code_block'
            })
    
    return chunks


def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using RAG with context-aware retrieval and general question handling."""
    try:
        collection = get_collection_for_chat(chat_id)
        query_embedding = encoder.encode(query)
        
        # List of keywords that indicate a general question about the codebase
        general_keywords = [
            'what is this code for',
            'what does this do',
            'explain this code',
            'purpose of this',
            'overview',
            'summarize',
            'describe the code',
            'how does this work',
            'what is the functionality'
        ]
        
        # Check if it's a general question
        is_general_question = any(keyword in query.lower() for keyword in general_keywords)
        
        if is_general_question:
            # For general questions, get a sample of different file types
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                where={"chat_id": chat_id},
                n_results=5
            )
            
            # Create a system message focused on overall codebase understanding
            system_message = """You are a code expert analyzing a complete codebase. 
            Provide a high-level overview of the code's purpose, main components, and functionality. 
            Focus on explaining the general architecture and key features. 
            Use the following code samples as reference to understand the codebase:"""
            
        else:
            # Handle file-specific queries
            file_match = re.match(r'^@(\S+)', query)
            if file_match:
                filename = file_match.group(1)
                # Query for all chunks from the specific file
                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    where={"$and": [
                        {"chat_id": chat_id},
                        {"file_path": filename}
                    ]},
                    n_results=10
                )
                system_message = f"You are a code expert analyzing the file {file_match.group(1)}. Provide a comprehensive overview of the file's purpose, structure, and key components. Use the following code context:"
            else:
                # Check if query is about a specific function
                function_keywords = ['function', 'method', 'class', 'def', 'how does', 'what does', 'explain']
                is_function_query = any(keyword in query.lower() for keyword in function_keywords)
                
                if is_function_query:
                    function_name = extract_function_name(query)
                    if function_name:
                        results = collection.query(
                            query_embeddings=[query_embedding.tolist()],
                            where={"$and": [
                                {"chat_id": chat_id},
                                {"type": {"$in": ["function", "class"]}},
                                {"name": function_name}
                            ]},
                            n_results=1
                        )
                    else:
                        results = collection.query(
                            query_embeddings=[query_embedding.tolist()],
                            where={"$and": [
                                {"chat_id": chat_id},
                                {"type": {"$in": ["function", "class"]}}
                            ]},
                            n_results=3
                        )
                    system_message = "You are a code expert explaining specific functions and classes. Focus on the implementation details, parameters, return values, and purpose of the code. Use the following code context:"
                else:
                    # Regular query
                    results = collection.query(
                        query_embeddings=[query_embedding.tolist()],
                        where={"chat_id": chat_id},
                        n_results=3
                    )
                    system_message = "You are a helpful AI assistant specialized in code explanation. Use the following code context to answer the question:"

        # Handle case when no results are found
        if not results['documents'][0]:
            if is_general_question:
                # For general questions with no results, provide a generic response
                system_message = """You are a code expert. The user has asked a general question about the codebase, 
                but we don't have specific code context available. Please provide a response based on what you can 
                understand from the conversation history and general programming knowledge."""
                context = "No specific code context available."
            else:
                raise ValueError("No relevant information found in the repository")
        else:
            # Prepare context with enhanced metadata
            context_chunks = []
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                file_info = f"\nFile: {metadata['file_path']} (lines {metadata['start_line']}-{metadata['end_line']})"
                if 'type' in metadata and metadata['type'] in ['function', 'class']:
                    file_info += f"\nType: {metadata['type'].capitalize()}"
                    if 'name' in metadata:
                        file_info += f"\nName: {metadata['name']}"
                context_chunks.append(f"{file_info}\n{doc}")
            context = "\n---\n".join(context_chunks)

        messages = [
            {
                "role": "system",
                "content": f"{system_message} {context}"
            }
        ]

        if conversation_history:
            for line in conversation_history.split('\n'):
                if line.startswith('User: '):
                    messages.append({
                        "role": "user",
                        "content": line[6:]
                    })
                elif line.startswith('Assistant: '):
                    messages.append({
                        "role": "assistant",
                        "content": line[11:]
                    })

        messages.append({
            "role": "user",
            "content": query
        })

        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            response = ollama_client.chat(model='deepseek-coder-v2:latest', messages=messages)
        
        logger.info("Generated response from RAG pipeline")
        return response['message']['content']

    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        raise
    
@app.route('/load-repo', methods=['POST'])
def load_repo():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        repo_url = data.get('repo_url')
        chat_id = data.get('chat_id')

        if not repo_url:
            return jsonify({'error': 'repo_url is required'}), 400
        if not chat_id:
            return jsonify({'error': 'chat_id is required'}), 400

        logger.info(f"Loading repository: {repo_url} for chat: {chat_id}")
        parse_github_repo_and_add_to_vector_db(repo_url, chat_id)
        return jsonify({'status': 'success'})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in load_repo: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

@app.route('/files', methods=['POST'])
def get_files():
    """Get list of files in the repository for a specific chat."""
    try:
        data = request.json
        if not data or 'chat_id' not in data:
            return jsonify({'error': 'chat_id is required'}), 400

        chat_id = data['chat_id']
        collection = get_collection_for_chat(chat_id)
        
        # Query unique file paths from the collection
        results = collection.get(
            where={"chat_id": chat_id},
            include=['metadatas']
        )
        
        if not results['metadatas']:
            return jsonify({'files': []})
            
        # Extract unique file paths from metadata
        files = sorted(set(
            metadata['file_path'] 
            for metadata in results['metadatas']
            if 'file_path' in metadata
        ))
        
        return jsonify({'files': files})

    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        query = data.get('query')
        chat_id = data.get('chat_id')
        conversation_history = data.get('conversation_history', '')

        if not query:
            return jsonify({'error': 'query is required'}), 400
        if not chat_id:
            return jsonify({'error': 'chat_id is required'}), 400

        logger.info(f"Processing chat query for chat: {chat_id}")
        response = generate_response(chat_id, conversation_history, query)
        return jsonify({'response': response})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in chat_endpoint: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

if __name__ == '__main__':
    app.run(debug=True)