import os
import uuid
import logging
import chromadb
import shutil
import io  # For capturing exec output
import contextlib  # For capturing exec output
import json  # For handling JSON

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from gemini import GeminiAPI
from processing import process_uploaded_file, perform_internet_search

# === CONSTANTS ===
UPLOAD_FOLDER = "uploads"
PERSISTENT_DOCUMENTS_DIR = "persistent_documents"
GEMINI_API_SPEC_PATH = os.path.join("gemini", "documents", "geminiAiApi.json")

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

    # --- Load Gemini API Spec ---
    gemini_api_summary = "General text generation, summarization, and question answering." # Default summary
    try:
        if os.path.exists(GEMINI_API_SPEC_PATH):
            with open(GEMINI_API_SPEC_PATH, 'r') as f:
                api_spec = json.load(f)
                # *** Generate a summary from the spec (adjust based on actual JSON structure) ***
                capabilities = []
                if 'functions' in api_spec: # Example: Assuming a 'functions' key
                    for func_name, details in api_spec['functions'].items():
                        desc = details.get('description', 'No description available.')
                        capabilities.append(f"- {func_name}: {desc}")
                elif 'models' in api_spec: # Alternative: Summarize models
                     for model in api_spec['models']:
                         capabilities.append(f"- Model '{model.get('name', 'N/A')}': {model.get('description', 'N/A')}")

                if capabilities:
                    gemini_api_summary = "Specific capabilities include:\n" + "\n".join(capabilities)
                else:
                    logging.warning(f"[Plan] Could not extract specific capabilities from {GEMINI_API_SPEC_PATH}. Using default summary.")
            logging.info(f"[Plan] Loaded Gemini API spec summary from {GEMINI_API_SPEC_PATH}")
        else:
            logging.warning(f"[Plan] Gemini API spec file not found at {GEMINI_API_SPEC_PATH}. Using default summary.")
    except (json.JSONDecodeError, OSError, Exception) as e:
        logging.error(f"[Plan] Failed to load or parse Gemini API spec file {GEMINI_API_SPEC_PATH}: {e}", exc_info=True)
        # Continue with the default summary if loading fails

    # --- Prepare Planning Prompt ---
    try:
        # Define assistant types available for planning
        available_assistants = [
            "Internet Searcher: Searches the web for current information on a specific topic.",
            "File Manager: Reads files from or lists files in the persistent storage directory.",
            "ChromaDB Admin: Queries the vector database for relevant documents or counts items.",
            # *** Integrate the loaded summary here ***
            f"Gemini API Admin: Handles tasks related to the Google Gemini API. {gemini_api_summary}",
            "Code Interpreter: Executes a given Python code snippet (Use with extreme caution!)."
        ]
        assistants_description = "\n".join([f"- {a}" for a in available_assistants])

        # Instruction for the LLM to generate a plan
        planning_instruction = (
            f"Based on the user's request, break it down into a sequence of logical steps. "
            f"For each step, identify the most appropriate assistant type from the following list to perform it. "
            f"Pay close attention to the specific capabilities listed for the Gemini API Admin.\n" # Added emphasis
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

# --- NEW: Endpoint for File Operations ---
@app.route('/api/file_operation', methods=['POST'])
def handle_file_operation():
    data = request.json
    if not data or 'operation' not in data:
        return jsonify({'error': 'Missing operation type (e.g., read, list) in request body.'}), 400

    operation = data.get('operation', '').lower()
    filename = data.get('filename', None) # Required for 'read'

    logging.info(f"[FileOp] Received request for operation: '{operation}'" + (f" on file: '{filename}'" if filename else ""))

    try:
        if operation == 'list':
            if not os.path.isdir(PERSISTENT_DOCUMENTS_DIR):
                return jsonify({'error': f'Persistent documents directory not found: {PERSISTENT_DOCUMENTS_DIR}'}), 404
            files = [f for f in os.listdir(PERSISTENT_DOCUMENTS_DIR)
                     if os.path.isfile(os.path.join(PERSISTENT_DOCUMENTS_DIR, f)) and not f.startswith('.')]
            logging.info(f"[FileOp] Listed {len(files)} files.")
            return jsonify({'files': sorted(files)})

        elif operation == 'read':
            if not filename:
                return jsonify({'error': "Missing 'filename' for read operation."}), 400

            # Secure the filename again, although it should come from a plan
            safe_filename = secure_filename(filename)
            if not safe_filename or safe_filename != filename: # Basic check against path traversal attempts
                 return jsonify({'error': 'Invalid filename provided for read operation.'}), 400

            filepath = os.path.join(PERSISTENT_DOCUMENTS_DIR, safe_filename)

            if not os.path.exists(filepath) or not os.path.isfile(filepath):
                return jsonify({'error': f"File not found or is not accessible: '{safe_filename}'"}), 404

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    # Limit reading size to prevent loading huge files into memory/response
                    content = f.read(10000) # Read max 10k characters
                    if len(content) == 10000:
                         content += "\n... (file content truncated)"
                logging.info(f"[FileOp] Read content from '{safe_filename}'.")
                return jsonify({'filename': safe_filename, 'content': content})
            except Exception as read_err:
                 logging.error(f"[FileOp] Error reading file '{safe_filename}': {read_err}", exc_info=True)
                 return jsonify({'error': f"Could not read file: {read_err}"}), 500

        # Add elif for 'write', 'delete' here if implementing (with extreme caution)

        else:
            return jsonify({'error': f"Unsupported file operation: '{operation}'. Supported: list, read."}), 400

    except Exception as e:
        logging.error(f"[FileOp] Unexpected error during file operation '{operation}': {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred during the file operation.'}), 500


# --- NEW: Endpoint for Code Execution (DANGEROUS) ---
@app.route('/api/execute_code', methods=['POST'])
def handle_execute_code():
    # *** SERIOUS SECURITY WARNING ***
    # This endpoint executes arbitrary Python code using exec().
    # It provides NO SANDBOXING and is extremely insecure.
    # DO NOT USE IN PRODUCTION OR SHARED ENVIRONMENTS.
    # ONLY FOR LOCAL, TRUSTED DEVELOPMENT.
    logging.warning("[CodeExec] Received request to execute code. THIS IS INSECURE.")

    data = request.json
    if not data or 'code' not in data:
        return jsonify({'error': 'Missing Python code snippet in request body.'}), 400

    code_snippet = data.get('code', '').strip()

    if not code_snippet:
         return jsonify({'error': 'Received empty code snippet.'}), 400

    # Attempt to capture stdout/stderr during execution
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        # Use contextlib to redirect stdout/stderr
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            # Execute the code in a restricted global/local scope if possible,
            # but exec itself is the main danger.
            # Passing empty dicts provides *some* isolation but doesn't prevent access to builtins or imports.
            exec(code_snippet, {}, {})

        stdout_result = stdout_capture.getvalue()
        stderr_result = stderr_capture.getvalue()

        logging.info(f"[CodeExec] Executed code snippet. Stdout captured: {len(stdout_result)} chars, Stderr captured: {len(stderr_result)} chars.")

        response_data = {
            'stdout': stdout_result,
            'stderr': stderr_result,
            'message': 'Code executed successfully.' if not stderr_result else 'Code executed with errors.'
        }
        return jsonify(response_data)

    except Exception as e:
        stderr_result = stderr_capture.getvalue() # Get any stderr captured before the exception
        error_message = f"Execution failed: {type(e).__name__}: {e}"
        logging.error(f"[CodeExec] Error executing code snippet: {error_message}", exc_info=False) # Avoid logging full trace unless needed
        return jsonify({
            'stdout': stdout_capture.getvalue(),
            'stderr': f"{stderr_result}\n{error_message}", # Combine captured stderr with exception
            'error': error_message
        }), 500 # Use 500 for execution failure

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
