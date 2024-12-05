from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
import shutil
from urllib.parse import urlparse
import git
import chromadb
from sentence_transformers import SentenceTransformer
import PyPDF2
import numpy as np
from typing import List, Dict, Optional
import logging

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
DATA_DIR = os.path.join(os.getcwd(), "data")
DB_PATH = os.path.join(DATA_DIR, "chroma_db")

def initialize_components():
    """Initialize encoder and ChromaDB client with proper error handling."""
    try:
        # Create data directory with proper permissions
        logger.debug(f"DATA_DIR: {DATA_DIR}")
        logger.debug(f"DB_PATH: {DB_PATH}")

        os.makedirs(DATA_DIR, mode=0o755, exist_ok=True)
        os.makedirs(DB_PATH, mode=0o755, exist_ok=True)
        
        # Set proper permissions for the DB directory
        for root, dirs, files in os.walk(DB_PATH):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)
        
        # Initialize components
        encoder = SentenceTransformer('all-MiniLM-L6-v2')
        chroma_client = chromadb.PersistentClient(path=DB_PATH)
        
        logger.info("Successfully initialized encoder and ChromaDB client")
        return encoder, chroma_client
    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}")
        raise RuntimeError(f"Failed to initialize components: {str(e)}")

# Initialize global variables with better error handling
try:
    encoder, chroma_client = initialize_components()
except Exception as e:
    logger.error(f"Critical error during initialization: {str(e)}")
    raise

# Store active collections for each chat
active_collections = {}

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

def get_collection_for_chat(chat_id: str) -> chromadb.Collection:
    """Get or create a collection for a specific chat with enhanced error handling."""
    try:
        collection_name = f"chat_{chat_id}"
        
        # First try to get existing collection
        try:
            collection = chroma_client.get_collection(name=collection_name)
            logger.info(f"Retrieved existing collection: {collection_name}")
            return collection
        except Exception as e:
            logger.info(f"Collection {collection_name} not found, creating new one")
            
        # Create new collection if it doesn't exist
        try:
            collection = chroma_client.create_collection(name=collection_name)
            logger.info(f"Created new collection: {collection_name}")
            return collection
        except Exception as e:
            logger.error(f"Error creating collection: {str(e)}")
            raise RuntimeError(f"Failed to create collection: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in get_collection_for_chat: {str(e)}")
        raise

def create_chunks(content: str, file_path: str, chunk_size: int = 1500) -> List[Dict[str, str]]:
    """Create intelligent chunks from content with enhanced metadata and file-based splitting."""
    chunks = []
    file_name = os.path.basename(file_path)
    
    # Add file header as the first chunk with complete file info
    file_header = f"File: {file_path}\nName: {file_name}\nContent Overview:\n{content[:200]}..."
    chunks.append({
        'content': file_header,
        'file_path': file_path,
        'file_name': file_name,
        'chunk_type': 'header',
        'start_line': 0,
        'end_line': 0
    })
    
    lines = content.split('\n')
    current_chunk = []
    current_length = 0
    current_start_line = 1
    in_function = False
    in_class = False
    
    for i, line in enumerate(lines, 1):
        # Detect structural elements
        if any(marker in line for marker in ['class ', 'def ', 'function ', '@app.route', 'public class']):
            # If we were already in a function/class, save the current chunk
            if (in_function or in_class) and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'file_path': file_path,
                    'file_name': file_name,
                    'chunk_type': 'code_block',
                    'start_line': current_start_line,
                    'end_line': i - 1
                })
                current_chunk = []
                current_length = 0
                current_start_line = i
            
            in_function = 'def ' in line or 'function ' in line
            in_class = 'class ' in line
        
        # Handle chunk size limits
        if current_length + len(line) > chunk_size and current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'content': chunk_text,
                'file_path': file_path,
                'file_name': file_name,
                'chunk_type': 'code_block',
                'start_line': current_start_line,
                'end_line': i - 1
            })
            current_chunk = []
            current_length = 0
            current_start_line = i
        
        current_chunk.append(line)
        current_length += len(line) + 1
    
    # Add remaining content as the last chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append({
            'content': chunk_text,
            'file_path': file_path,
            'file_name': file_name,
            'chunk_type': 'code_block',
            'start_line': current_start_line,
            'end_line': len(lines)
        })
    
    return chunks

def add_chunks_to_vector_db(collection: chromadb.Collection, chunks: List[Dict[str, str]], chat_id: str, file_path: str):
    """Add chunks to the vector database with enhanced metadata."""
    try:
        if not chunks:
            return

        documents = [chunk['content'] for chunk in chunks]
        embeddings = encoder.encode(documents)
        
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "chat_id": chat_id,
                "file_path": file_path,
                "file_name": chunk['file_name'],
                "chunk_type": chunk['chunk_type'],
                "start_line": chunk['start_line'],
                "end_line": chunk['end_line'],
                "chunk_index": i
            }
            metadatas.append(metadata)

        ids = [f"{chat_id}_{chunk['file_name']}_chunk_{i}" for i, chunk in enumerate(chunks)]

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
    
def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using enhanced RAG with file-based context."""
    try:
        collection = get_collection_for_chat(chat_id)
        query_embedding = encoder.encode(query)
        
        # Check if query is about a specific file
        file_query = False
        query_lower = query.lower()
        if '.py' in query_lower or '.js' in query_lower or 'file' in query_lower:
            file_query = True
            # Extract potential filename from query
            words = query_lower.split()
            potential_files = [word for word in words if '.' in word]
            if potential_files:
                # Query specifically for chunks from this file using proper where clause
                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    where={"$and": [
                        {"chat_id": chat_id},
                        {"file_name": potential_files[0]}
                    ]},
                    n_results=10
                )
            else:
                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    where={"chat_id": chat_id},
                    n_results=5
                )
        else:
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                where={"chat_id": chat_id},
                n_results=3
            )

        if not results['documents'] or not results['documents'][0]:
            return "I couldn't find any relevant information in the repository to answer your question. Could you please rephrase or ask about something else?"

        # Prepare context with enhanced formatting
        context_chunks = []
        current_file = None
        
        for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
            if metadata['file_name'] != current_file:
                current_file = metadata['file_name']
                context_chunks.append(f"\n=== File: {metadata['file_name']} ===\n")
            
            if metadata['chunk_type'] == 'header':
                context_chunks.append(doc)
            else:
                context_chunks.append(f"\nLines {metadata['start_line']}-{metadata['end_line']}:\n{doc}")
        
        context = "\n".join(context_chunks)

        # Adjust system prompt based on query type
        if file_query:
            system_prompt = f"""You are a coding assistant specialized in explaining code files and their structure. 
For the current query about code files, provide a clear, well-structured explanation that includes:
1. An overview of the file's purpose and main components
2. Detailed explanations of key functions and their purposes
3. Any important patterns or architectural decisions
4. Notable dependencies or external integrations

Use the following code context to inform your response: {context}"""
        else:
            system_prompt = f"""You are a helpful AI assistant specialized in code explanation. 
Use the following code context to answer the question, but don't mention that you're using any context: {context}"""

        messages = [
            {
                "role": "system",
                "content": system_prompt
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

        # Load model directly
        from transformers import AutoTokenizer, AutoModelForCausalLM

        tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.2-1B")
        model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-1B")

        # Tokenize input messages
        input_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        inputs = tokenizer(input_text, return_tensors="pt")

        # Generate response
        outputs = model.generate(inputs["input_ids"], max_length=250, num_return_sequences=1)
        response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract assistant's response
        response = response_text.split("Assistant: ")[-1].strip()

        logger.info("Generated response from enhanced RAG pipeline")
        return response

    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
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

@app.route('/load-repo', methods=['POST'])
def load_repo():
    """Load repository endpoint with improved error handling."""
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
        
        # Test database access before proceeding
        try:
            collection = get_collection_for_chat(chat_id)
            # Try a simple operation to verify database access
            collection.count()
        except Exception as e:
            logger.error(f"Database access test failed: {str(e)}")
            return jsonify({'error': 'Database access error. Please check permissions and try again.'}), 500

        parse_github_repo_and_add_to_vector_db(repo_url, chat_id)
        return jsonify({'status': 'success'})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in load_repo: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500
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

@app.route('/files', methods=['POST'])
def get_files():
    """Get list of files in the repository for a specific chat."""
    try:
        data = request.json
        if not data or 'chat_id' not in data:
            return jsonify({'error': 'chat_id is required'}), 400

        chat_id = data['chat_id']
        collection = get_collection_for_chat(chat_id)
        
        # Query for header chunks to get file information
        results = collection.get(
            where={"$and": [
                {"chat_id": chat_id},
                {"chunk_type": "header"}
            ]}
        )
        
        if not results['metadatas']:
            return jsonify({'files': []})
            
        # Extract unique file paths from metadata
        files = sorted(set(meta['file_path'] for meta in results['metadatas']))
        return jsonify({'files': files})

    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)