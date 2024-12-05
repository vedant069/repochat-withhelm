from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import tempfile
from urllib.parse import urlparse
import git
import chromadb
from sentence_transformers import SentenceTransformer
import ollama
import logging
import re
import httpx

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

# Store active collections and file contexts
active_collections = {}
active_file_contexts = {}

OLLAMA_URL = 'https://c412-34-168-69-254.ngrok-free.app/'

def set_active_file(chat_id: str, filename: str) -> None:
    """Set the active file context for a specific chat."""
    active_file_contexts[chat_id] = filename
    logger.info(f"Set active file for chat {chat_id} to: {filename}")

def get_active_file(chat_id: str) -> str:
    """Get the active file context for a specific chat."""
    return active_file_contexts.get(chat_id)

def parse_query(query: str, chat_id: str) -> tuple[str, str]:
    """Parse the query to extract file context and actual query."""
    file_match = re.match(r'^@(\S+)\s*(.*)', query)
    
    if file_match:
        filename = file_match.group(1)
        actual_query = file_match.group(2).strip()
        set_active_file(chat_id, filename)
        return filename, actual_query if actual_query else "Explain this file"
    
    active_file = get_active_file(chat_id)
    if active_file:
        return active_file, query
    
    return None, query

def is_code_file(file_path: str) -> bool:
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
    
    return ext.lower() in code_extensions or file_name in {'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'}

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
        collection = chroma_client.get_or_create_collection(name=collection_name)
        logger.info(f"Retrieved or created collection: {collection_name}")
        return collection
    except Exception as e:
        logger.error(f"Error in get_collection_for_chat: {str(e)}")
        raise

def create_chunks(content: str, file_path: str, chunk_size: int = 1500) -> list[dict]:
    """Create chunks from content with smart splitting."""
    chunks = []
    current_chunk = []
    current_length = 0
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        # Start new chunk if adding this line would exceed chunk size
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
    
    # Add remaining content as final chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append({
            'content': chunk_text,
            'file_path': file_path,
            'start_line': len(lines) - len(current_chunk) + 1,
            'end_line': len(lines)
        })
    
    return chunks

def add_chunks_to_vector_db(collection: chromadb.Collection, chunks: list[dict], chat_id: str, file_path: str):
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

def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using RAG with context-aware retrieval."""
    try:
        collection = get_collection_for_chat(chat_id)
        file_context, actual_query = parse_query(query, chat_id)
        query_embedding = encoder.encode(actual_query)
        
        # Query with file context if specified
        if file_context:
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                where={"$and": [
                    {"chat_id": chat_id},
                    {"file_path": file_context}
                ]},
                n_results=5
            )
            system_message = f"You are a code expert analyzing the file {file_context}. Provide a comprehensive answer based on the file's content."
        else:
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                where={"chat_id": chat_id},
                n_results=3
            )
            system_message = "You are a helpful AI assistant specialized in code explanation."

        if not results['documents'][0]:
            raise ValueError("No relevant information found")

        context = "\n---\n".join([
            f"\nFile: {metadata['file_path']} (lines {metadata['start_line']}-{metadata['end_line']})\n{doc}"
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0])
        ])

        messages = [
            {"role": "system", "content": f"{system_message}\nUse the following code context:\n{context}"}
        ]

        # Add conversation history
        if conversation_history:
            for line in conversation_history.split('\n'):
                if line.startswith('User: '):
                    messages.append({"role": "user", "content": line[6:]})
                elif line.startswith('Assistant: '):
                    messages.append({"role": "assistant", "content": line[11:]})

        messages.append({"role": "user", "content": actual_query})

        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            response = ollama_client.chat(model='llama3.2:3b', messages=messages)
        
        logger.info("Generated response from RAG pipeline")
        return response['message']['content']

    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        raise

@app.route('/load-repo', methods=['POST'])
def load_repo():
    """Load a GitHub repository and process it for RAG."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        repo_url = data.get('repo_url')
        chat_id = data.get('chat_id')

        if not repo_url or not chat_id:
            return jsonify({'error': 'repo_url and chat_id are required'}), 400

        logger.info(f"Loading repository: {repo_url} for chat: {chat_id}")
        parse_github_repo_and_add_to_vector_db(repo_url, chat_id)
        return jsonify({'status': 'success'})

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Server error in load_repo: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/files', methods=['POST'])
def get_files():
    """Get list of files in the repository for a specific chat."""
    try:
        data = request.json
        if not data or 'chat_id' not in data:
            return jsonify({'error': 'chat_id is required'}), 400

        chat_id = data['chat_id']
        collection = get_collection_for_chat(chat_id)
        
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

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """Handle chat requests with RAG integration."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        query = data.get('query')
        chat_id = data.get('chat_id')
        conversation_history = data.get('conversation_history', '')

        if not query or not chat_id:
            return jsonify({'error': 'query and chat_id are required'}), 400

        logger.info(f"Processing chat query for chat: {chat_id}")
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