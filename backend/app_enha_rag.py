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
from typing import List, Dict, Tuple
import httpx
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

# Store active collections for each chat
active_collections = {}

OLLAMA_URL = 'https://e641-34-91-185-230.ngrok-free.app/'

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

def extract_code_metadata(content: str) -> dict:
    """Extract metadata from code content."""
    metadata = {
        'functions': [],
        'classes': [],
        'imports': [],
        'file_type': None
    }
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('def '):
            metadata['functions'].append(line[4:].split('(')[0])
        elif line.startswith('class '):
            metadata['classes'].append(line[6:].split('(')[0].split(':')[0])
        elif line.startswith('import ') or line.startswith('from '):
            metadata['imports'].append(line)
            
    return metadata

def extract_code_metadata(content: str) -> dict:
    """Extract metadata from code content."""
    metadata = {
        'functions': '',  # Changed from list to string
        'classes': '',    # Changed from list to string
        'imports': '',    # Changed from list to string
        'file_type': ''
    }
    
    lines = content.split('\n')
    functions = []
    classes = []
    imports = []
    
    for line in lines:
        line = line.strip()
        if line.startswith('def '):
            functions.append(line[4:].split('(')[0])
        elif line.startswith('class '):
            classes.append(line[6:].split('(')[0].split(':')[0])
        elif line.startswith('import ') or line.startswith('from '):
            imports.append(line)
            
    # Join lists into strings
    metadata['functions'] = ', '.join(functions)
    metadata['classes'] = ', '.join(classes)
    metadata['imports'] = ', '.join(imports)
            
    return metadata

def parse_github_repo_and_add_to_vector_db(repo_url: str, chat_id: str, auth_token: str = None, chunk_size: int = 1500):
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
                clone_url = repo_url
                if auth_token:
                    # Insert token into clone URL for authentication
                    parsed = urlparse(repo_url)
                    clone_url = f"https://{auth_token}@{parsed.netloc}{parsed.path}"
                
                repo = git.Repo.clone_from(clone_url, os.path.join(temp_dir, repo_name))
                logger.info(f"Cloned repository: {repo_name}")
            except git.exc.GitCommandError as e:
                if "Authentication failed" in str(e):
                    raise ValueError("Authentication failed. Please check your GitHub token.")
                logger.error(f"Git clone failed: {str(e)}")
                raise ValueError("Failed to clone repository. Please check the URL and permissions.")

            collection = get_collection_for_chat(chat_id)
            collection.delete(where={"chat_id": chat_id})
            
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
                                
                            # Extract metadata
                            metadata = extract_code_metadata(content)
                            metadata['file_path'] = relative_path
                            metadata['chat_id'] = chat_id
                            
                            # Smart chunking based on code structure
                            chunks = smart_code_chunking(content, chunk_size)
                            
                            if chunks:
                                embeddings = encoder.encode(chunks)
                                
                                # Add chunks with metadata
                                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                                    chunk_metadata = metadata.copy()
                                    chunk_metadata['chunk_index'] = str(i)
                                    
                                    collection.add(
                                        embeddings=[embedding.tolist()],
                                        documents=[chunk],
                                        metadatas=[chunk_metadata],
                                        ids=[f"{chat_id}_{relative_path}_chunk_{i}"]
                                    )
                    except UnicodeDecodeError:
                        continue

            logger.info("Successfully processed repository and added to vector database")

    except Exception as e:
        logger.error(f"Error in parse_github_repo_and_add_to_vector_db: {str(e)}")
        raise


def smart_code_chunking(content: str, chunk_size: int) -> List[str]:
    """Implement smart chunking based on code structure."""
    chunks = []
    current_chunk = []
    current_size = 0
    
    # Split by potential logical boundaries
    boundaries = ['\nclass ', '\ndef ', '\n\n# ', '\n\n## ']
    
    lines = content.split('\n')
    
    for line in lines:
        current_chunk.append(line)
        current_size += len(line)
        
        # Check if we should create a new chunk
        if current_size >= chunk_size or any(boundary in line for boundary in boundaries):
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
                
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
        
    return chunks

def refine_query(initial_query: str, relevant_chunks: List[str], chat_history: str = "") -> str:
    """Generate a refined query based on initial results and chat history."""
    try:
        # Create a prompt for query refinement
        refinement_prompt = {
            "role": "system",
            "content": """You are an AI that helps improve code-related queries. 
            Based on the initial query and the retrieved code context, create a more specific and technically accurate query.
            Focus on:
            1. Technical terminology found in the code
            2. Specific functions or classes mentioned
            3. The actual implementation patterns visible in the code
            4. Only include elements that are actually present in the provided context
            5.focus on the file mentioned
            6. Don't mention that you're using any context
            7.if you dont find any context use the initial query.
            8.if notihng works  use your brain to answer it or ask for help"""
        }

        context_summary = "\n".join(relevant_chunks)
        
        messages = [
            refinement_prompt,
            {
                "role": "user",
                "content": f"""Original query: {initial_query}
                Retrieved code context:
                {context_summary}
                
                Previous conversation context:
                {chat_history}
                
                Generate a refined, more specific version of the query that will help find the most relevant code sections."""
            }
        ]

        # Get refined query from LLM
        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            response = ollama_client.chat(model='llama3.2:3b', messages=messages)
            
        refined_query = response['message']['content']
        
        # Extract just the query part if the LLM included explanations
        if '\n' in refined_query:
            refined_query = refined_query.split('\n')[0]
            
        logger.info(f"Refined query: {refined_query}")
        return refined_query

    except Exception as e:
        logger.error(f"Error in query refinement: {str(e)}")
        # Fallback to original query if refinement fails
        return initial_query

def get_relevant_chunks(collection: chromadb.Collection, query: str, chat_id: str, n_results: int = 3) -> Tuple[List[str], float]:
    """Get relevant chunks and their average similarity score."""
    query_embedding = encoder.encode(query)
    
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        where={"chat_id": chat_id},
        n_results=n_results
    )
    
    # Calculate average similarity score
    if results['distances'] and results['distances'][0]:
        avg_similarity = 1 - (sum(results['distances'][0]) / len(results['distances'][0]))
    else:
        avg_similarity = 0
        
    return results['documents'][0], avg_similarity

def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using two-stage RAG with query refinement."""
    try:
        collection = get_collection_for_chat(chat_id)
        
        # Stage 1: Initial retrieval
        initial_chunks, initial_similarity = get_relevant_chunks(collection, query, chat_id)
        
        if not initial_chunks:
            raise ValueError("No relevant information found in the repository")
            
        # Stage 2: Query refinement and second retrieval
        refined_query = refine_query(query, initial_chunks, conversation_history)
        final_chunks, final_similarity = get_relevant_chunks(collection, refined_query, chat_id)
        
        # Use chunks with better similarity score
        if final_similarity > initial_similarity:
            context = "\n".join(final_chunks)
            used_query = refined_query
        else:
            context = "\n".join(initial_chunks)
            used_query = query
            
        # Generate final response
        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful AI assistant specializing in code explanation. 
                Base your response on this code context: {context}
                
                Important guidelines:
                1. Only reference information actually present in the context
                2. If you're unsure about any details, acknowledge the uncertainty
                3. Use technical terminology found in the code
                4. Focus on practical implementation details
                5. Don't mention that you're using any context"""
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
            "content": used_query
        })

        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            response = ollama_client.chat(model='llama3.2:3b', messages=messages)
            
        logger.info("Generated response from refined RAG pipeline")
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
        auth_token = None

        if not repo_url:
            return jsonify({'error': 'repo_url is required'}), 400
        if not chat_id:
            return jsonify({'error': 'chat_id is required'}), 400

        # Extract auth token from headers if present
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            auth_token = auth_header.split(' ')[1]

        logger.info(f"Loading repository: {repo_url} for chat: {chat_id}")
        parse_github_repo_and_add_to_vector_db(repo_url, chat_id, auth_token)
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

if __name__ == '__main__':
    # Initialize logging configuration at startup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
    
    # Log startup information
    logger.info("Starting RAG-enhanced code assistant...")
    logger.info(f"Ollama URL: {OLLAMA_URL}")
    
    # Verify critical components
    try:
        # Test encoder
        test_embedding = encoder.encode("Test encoding")
        logger.info("Sentence transformer encoder verified")
        
        # Test ChromaDB
        test_collection = chroma_client.get_or_create_collection(name="test_collection")
        chroma_client.delete_collection(name="test_collection")  # Clean up test collection
        logger.info("ChromaDB connection verified")
        
        # Test Ollama connection
        with httpx.Client(verify=False) as client:
            ollama_client = ollama.Client(host=OLLAMA_URL)
            test_response = ollama_client.chat(
                model='llama3.2:3b',
                messages=[{"role": "user", "content": "test"}]
            )
        logger.info("Ollama connection verified")
        
    except Exception as e:
        logger.error(f"Startup verification failed: {str(e)}")
        raise
    
    # Start the Flask application
    app.run(
        host='0.0.0.0',  # Accept connections from all networks
        port=5000,       # Default Flask port
        debug=True       # Enable debug mode for development
    )