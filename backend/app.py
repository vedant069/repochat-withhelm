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

OLLAMA_URL = 'https://5884-35-240-234-23.ngrok-free.app/'

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
        
        # Try to get existing collection
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

            all_contents = ''
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
                            all_contents += f"{relative_path}:\n{content}\n\n"
                            processed_files += 1
                    except UnicodeDecodeError:
                        continue
                        
            logger.info(f"Processed {processed_files} code files")

            if not all_contents.strip():
                raise ValueError("No valid code files found in the repository")

            # Get or create collection for this chat
            collection = get_collection_for_chat(chat_id)
            
            # Clear existing documents in the collection
            collection.delete(where={"chat_id": chat_id})
            
            # Add new documents
            add_document_to_vector_db(collection, all_contents, chat_id, chunk_size)
            logger.info("Successfully added document chunks to vector database")

    except Exception as e:
        logger.error(f"Error in parse_github_repo_and_add_to_vector_db: {str(e)}")
        raise

def add_document_to_vector_db(collection: chromadb.Collection, text: str, chat_id: str, chunk_size: int = 1500):
    """Add document chunks to the specified collection."""
    try:
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0

        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1

            if current_length >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        if not chunks:
            raise ValueError("No valid chunks created from the text")

        embeddings = encoder.encode(chunks)
        
        # Add metadata to track which chat these chunks belong to
        metadata = [{"chat_id": chat_id} for _ in chunks]

        collection.add(
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=metadata,
            ids=[f"{chat_id}_chunk_{i}" for i in range(len(chunks))]
        )
        logger.info(f"Added {len(chunks)} chunks to collection")

    except Exception as e:
        logger.error(f"Error in add_document_to_vector_db: {str(e)}")
        raise

def generate_response(chat_id: str, conversation_history: str, query: str) -> str:
    """Generate a response using improved RAG with better context selection."""
    try:
        collection = get_collection_for_chat(chat_id)
        query_embedding = encoder.encode(query)
        
        # Retrieve more results initially to allow for better filtering
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            where={"chat_id": chat_id},
            n_results=10  # Increased from 3
        )

        if not results['documents'][0]:
            raise ValueError("No relevant information found in the repository")

        # Extract file paths from chunks
        def extract_file_path(chunk):
            # Look for pattern "path/to/file.ext:"
            lines = chunk.split('\n')
            if lines and ':' in lines[0]:
                return lines[0].split(':')[0]
            return None

        # Group chunks by file
        file_chunks = {}
        for chunk in results['documents'][0]:
            file_path = extract_file_path(chunk)
            if file_path:
                if file_path not in file_chunks:
                    file_chunks[file_path] = []
                file_chunks[file_path].append(chunk)

        # Score files based on query relevance
        file_scores = {}
        for file_path, chunks in file_chunks.items():
            # Score based on filename similarity to query
            filename = os.path.basename(file_path)
            filename_similarity = encoder.encode([filename, query])
            filename_score = np.dot(filename_similarity[0], filename_similarity[1])
            
            # Score based on content similarity
            content = " ".join(chunks)
            content_similarity = encoder.encode([content, query])
            content_score = np.dot(content_similarity[0], content_similarity[1])
            
            # Combine scores (giving more weight to filename match for specific file queries)
            file_scores[file_path] = (filename_score * 0.6) + (content_score * 0.4)

        # Select most relevant files and their chunks
        relevant_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)[:2]
        selected_chunks = []
        for file_path, _ in relevant_files:
            selected_chunks.extend(file_chunks[file_path])

        # Create enhanced context with file structure
        context = "Repository structure:\n"
        for file_path, _ in relevant_files:
            context += f"- {file_path}\n"
        context += "\nRelevant code sections:\n"
        context += "\n---\n".join(selected_chunks)

        messages = [
            {
                "role": "system",
                "content": f"""You are a helpful AI assistant analyzing code repositories. 
                When answering questions about specific files, focus primarily on the content 
                and purpose of those files. Use the following context: {context}

                Guidelines:
                - If the user asks about a specific file, prioritize explaining that file's contents
                - Only mention relationships to other files if directly relevant
                - If file A imports file B and the user asks about file B, focus on B's implementation
                - Provide specific code examples from the relevant file when appropriate"""
            }
        ]

        # Add conversation history
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
            response = ollama_client.chat(model='llama3.2:3b', messages=messages)
        
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