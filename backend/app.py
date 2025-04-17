import os
import uuid
import logging
import chromadb
import shutil

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from gemini import GeminiAPI
from processing import process_uploaded_file, perform_internet_search

# === CONSTANTS ===
UPLOAD_FOLDER = "uploads"
PERSISTENT_DOCUMENTS_DIR = "persistent_documents"

# === ENV INIT ===
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_API_KEY")

# === APP INIT ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PERSISTENT_DOCUMENTS_DIR, exist_ok=True)

# Initialize ChromaDB Client and Collection
try:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_or_create_collection("rag_collection")
    logging.info("ChromaDB client initialized using persistent storage and collection retrieved/created.")
except Exception as e:
    logging.error(f"Failed to initialize ChromaDB: {e}")
    raise

class ChromaDBWrapper:
    def __init__(self, collection_instance):
        self.collection = collection_instance

    def retrieve(self, query, n_results=5):
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results, include=['documents', 'metadatas'])
            retrieved_docs = results.get("documents", [[]])[0]
            return retrieved_docs
        except Exception as e:
            logging.error(f"Error retrieving from ChromaDB: {e}", exc_info=True)
            return []

    def add_texts(self, texts, metadatas):
        if not texts:
            logging.warning("Attempted to add empty list of texts.")
            return
        try:
            ids = [str(uuid.uuid4()) for _ in texts]
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logging.info(f"Added {len(texts)} text segments to ChromaDB.")
        except Exception as e:
            logging.error(f"Error adding texts to ChromaDB: {e}", exc_info=True)

    def add_documents(self, docs):
        if not docs:
            logging.warning("Attempted to add empty list of documents.")
            return
        try:
            texts = [getattr(doc, "page_content", "") for doc in docs]
            metadatas = [getattr(doc, "metadata", {}) for doc in docs]
            ids = [str(uuid.uuid4()) for _ in docs]
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logging.info(f"Added {len(docs)} documents to ChromaDB.")
        except Exception as e:
            logging.error(f"Error adding documents to ChromaDB: {e}", exc_info=True)

    def get_all_document_sources(self):
        try:
            results = self.collection.get(include=["metadatas"])
            sources = set()
            if results and results.get("metadatas"):
                for meta in results["metadatas"]:
                    if meta and 'source' in meta:
                        source_val = meta['source']
                        if isinstance(source_val, str):
                            sources.add(source_val)
                        else:
                            logging.warning(f"Found non-string source metadata: {source_val}")
            logging.info(f"Retrieved {len(sources)} distinct document sources.")
            return sorted(list(sources))
        except Exception as e:
            logging.error(f"Error getting document sources from ChromaDB: {e}", exc_info=True)
            return []

    def count_documents(self):
        """Counts the total number of documents in the collection."""
        try:
            count = self.collection.count()
            logging.info(f"Counted {count} documents in ChromaDB.")
            return count
        except Exception as e:
            logging.error(f"Error counting documents in ChromaDB: {e}", exc_info=True)
            return -1

chromadb_wrapper = ChromaDBWrapper(collection)
gemini = GeminiAPI(api_key=GOOGLE_API_KEY)

# Keywords to infer document count intent
COUNT_KEYWORDS = {"how many", "count", "number of", "total", "amount"}
DOCUMENT_KEYWORDS = {"document", "documents", "file", "files", "item", "items", "entry", "entries", "indexed", "stored", "saved", "encoded", "collection"}

@app.route('/api/query', methods=['POST'])
def handle_query():
    data = request.json
    if not data or 'query' not in data:
        logging.warning("Received query request with missing data or query field.")
        return jsonify({'error': 'Missing query in request body.'}), 400

    query = data.get('query', '').strip()
    task_instruction = data.get('task_instruction', None)
    external_context = data.get('external_context', None) # Expecting a list of strings
    query_lower = query.lower()
    logging.info(f"Received query: '{query}' (Task: {task_instruction or 'Default'}, External Context: {'Yes' if external_context else 'No'})")

    # --- Intent Inference for Document Count ---
    # Only run if no external context and no specific task instruction
    if not external_context and not task_instruction:
        is_count_query = False
        contains_count_keyword = any(keyword in query_lower for keyword in COUNT_KEYWORDS)
        contains_doc_keyword = any(keyword in query_lower for keyword in DOCUMENT_KEYWORDS)
        if contains_count_keyword and contains_doc_keyword:
             is_count_query = True

        if is_count_query:
            logging.info("Inferred intent: Document count query.")
            try:
                count = chromadb_wrapper.count_documents()
                if count != -1:
                    if count == 0:
                        answer = "There are currently no documents indexed."
                    elif count == 1:
                        answer = "There is currently 1 document indexed."
                    else:
                        answer = f"There are currently {count} documents indexed."
                    return jsonify({'answer': answer})
                else:
                    return jsonify({'error': 'Sorry, I encountered an issue trying to count the documents.'}), 500
            except Exception as e:
                logging.error(f"Error handling inferred document count query: {e}", exc_info=True)
                return jsonify({'error': 'An internal error occurred while counting documents.'}), 500
    # --- End Intent Inference ---

    # --- RAG Workflow ---
    try:
        documents = []
        source_type = "none"

        # Check for external context first
        if external_context and isinstance(external_context, list):
            logging.info(f"Using provided external context ({len(external_context)} items).")
            documents = external_context
            source_type = "external"
        else:
            # --- Original RAG/Search Logic (if no external context) ---
            logging.info("Step 1: Retrieving documents from ChromaDB...")
            chroma_documents = chromadb_wrapper.retrieve(query, n_results=7)

            if chroma_documents:
                logging.info(f"Found {len(chroma_documents)} relevant document chunks in ChromaDB.")
                # Log snippets for verification (optional, can be verbose)
                for i, doc in enumerate(chroma_documents):
                     logging.debug(f"  Doc {i+1}: {doc[:100]}...")
                documents = chroma_documents
                source_type = "documents"
            else:
                # Fallback to internet search
                logging.info("No relevant documents found in ChromaDB. Step 2: Performing internet search...")
                internet_results = perform_internet_search(query)
                if internet_results:
                    logging.info(f"Found {len(internet_results)} results from internet search.")
                    documents = internet_results
                    source_type = "internet"
                else:
                    logging.info("No relevant results found from internet search or ChromaDB.")
                    # documents remains []
                    # source_type remains "none"
            # --- End Original RAG/Search Logic ---

        # --- Generation Step (Common for all paths) ---
        logging.info(f"Step 3: Generating response using source type '{source_type}'.")
        answer = gemini.generate_response(
            query=query, # Pass the original query for context if needed by LLM
            documents=documents,
            source_type=source_type,
            task_instruction=task_instruction
        )

        logging.info(f"Generated answer for query '{query}'.")
        return jsonify({'answer': answer})

    except Exception as e:
        logging.error(f"Error handling query '{query}': {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred while processing your query.'}), 500

@app.route('/api/generate_plan', methods=['POST'])
def generate_plan():
    data = request.json
    if not data or 'query' not in data:
        logging.warning("[Plan] Received plan request with missing data or query field.")
        return jsonify({'error': 'Missing query in request body.'}), 400

    query = data.get('query', '').strip()
    logging.info(f"[Plan] Received request to generate plan for query: '{query}'")

    try:
        # Define assistant types available for planning
        # Keep this list updated if assistant capabilities change
        available_assistants = [
            "Internet Searcher: Searches the web for current information on a specific topic.", # Clarify role
            "File Manager: Reads, writes, or modifies files in the persistent storage.",
            "ChromaDB Admin: Queries the vector database for relevant documents or counts items.",
            "Gemini API Admin: Generates text, summarizes, answers questions based on context or general knowledge.",
            "Code Interpreter: Executes Python code snippets (Use with caution!)."
        ]
        assistants_description = "\n".join([f"- {a}" for a in available_assistants])

        # Instruction for the LLM to generate a plan
        planning_instruction = (
            f"Based on the user's request, break it down into a sequence of logical steps. "
            f"For each step, identify the most appropriate assistant type from the following list to perform it. "
            f"Present the plan as a numbered list, clearly stating the step and the suggested assistant type.\n\n"
            f"Available Assistant Types:\n{assistants_description}\n\n"
            f"User Request: \"{query}\""
        )

        # Use the Gemini client to generate the plan (no context needed)
        # We use the 'query' parameter here mainly for logging consistency in generate_response
        # The actual instruction is in 'task_instruction'
        plan_text = gemini.generate_response(
            query=f"Plan for: {query}", # For logging/tracking
            documents=[],
            source_type="none",
            task_instruction=planning_instruction
        )

        # Basic check if the response looks like a plan (contains numbers, etc.)
        if not plan_text or not any(char.isdigit() for char in plan_text):
             logging.warning(f"[Plan] LLM did not return a valid-looking plan for query: '{query}'. Response: {plan_text}")
             # Fallback or error
             plan_text = "Sorry, I couldn't generate a detailed plan for that request."


        logging.info(f"[Plan] Generated plan for query '{query}'.")
        return jsonify({'plan': plan_text})

    except Exception as e:
        logging.error(f"[Plan] Error generating plan for query '{query}': {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred while generating the plan.'}), 500

@app.route('/api/search', methods=['POST'])
def handle_search():
    data = request.json
    if not data or 'query' not in data:
        logging.warning("[Search] Received search request with missing data or query field.")
        return jsonify({'error': 'Missing query in request body.'}), 400

    query = data.get('query', '').strip()
    num_results = data.get('num_results', 3) # Allow specifying number of results

    logging.info(f"[Search] Received internet search request for: '{query}'")
    try:
        search_results = perform_internet_search(query, num_results=num_results)
        logging.info(f"[Search] Found {len(search_results)} results for '{query}'.")
        # Return results as a list under the 'results' key
        return jsonify({'results': search_results})
    except Exception as e:
        logging.error(f"[Search] Error performing internet search for query '{query}': {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred while performing the search.'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logging.error("[Upload] No file part in the request.")
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("[Upload] No file selected for upload.")
        return jsonify({'error': 'No file selected for upload.'}), 400

    # Get optional context from form data
    file_context = request.form.get('context', None) # Use request.form for non-file fields
    if file_context:
        logging.info(f"Received file context: '{file_context}'")

    filename = secure_filename(file.filename)
    if not filename:
        logging.error("[Upload] Invalid filename provided.")
        return jsonify({'error': 'Invalid filename provided.'}), 400

    logging.info(f"Received file upload (secured name): {filename}")

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    persistent_filepath = os.path.join(PERSISTENT_DOCUMENTS_DIR, filename)
    if os.path.exists(persistent_filepath):
        logging.warning(f"File '{filename}' already exists in persistent storage. Aborting upload.")
        return jsonify({'error': f"File '{filename}' already exists. Please rename and upload again."}), 409

    try:
        file.save(filepath)
        logging.info(f"File saved temporarily to: {filepath}")

        # Pass context to processing function
        success, message = process_uploaded_file(
            filepath,
            filename,
            chromadb_wrapper,
            PERSISTENT_DOCUMENTS_DIR,
            file_context=file_context # Pass the context
        )

        if success:
            logging.info(f"Successfully processed and moved file: {filename}")
            return jsonify({'message': message}), 200
        else:
            logging.warning(f"Failed to process file: {filename}. Reason: {message}")
            status_code = 500 if "internal error" in message.lower() else 400
            if "Missing dependencies" in message:
                status_code = 501
            return jsonify({'error': message}), status_code
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logging.info(f"Cleaned up temporary file after upload error: {filepath}")
            except Exception as cleanup_error:
                logging.error(f"Error cleaning up file {filepath} after upload error: {cleanup_error}")
        logging.error(f"[Upload] An unexpected error occurred for file {filename}: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected internal error occurred during upload.'}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Returns a list of filenames from the persistent documents directory."""
    try:
        if not os.path.isdir(PERSISTENT_DOCUMENTS_DIR):
            logging.warning(f"Persistent documents directory not found: {PERSISTENT_DOCUMENTS_DIR}")
            return jsonify([])

        files = [f for f in os.listdir(PERSISTENT_DOCUMENTS_DIR)
                 if os.path.isfile(os.path.join(PERSISTENT_DOCUMENTS_DIR, f)) and not f.startswith('.')]
        logging.info(f"Retrieved {len(files)} files from {PERSISTENT_DOCUMENTS_DIR}.")
        return jsonify(sorted(files))
    except Exception as e:
        logging.error(f"Error retrieving document list from filesystem: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve document list.'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=True)
