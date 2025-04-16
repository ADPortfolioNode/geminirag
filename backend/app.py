import os
import uuid
import logging
import datetime
import time
import chromadb
import speech_recognition as sr

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from moviepy import VideoFileClip
from threading import Lock

import google.generativeai as genai
from tqdm import tqdm
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_chroma import Chroma
from chromadb.utils import embedding_functions
from langchain_google_genai import GoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain_core.embeddings import Embeddings

# === ENV INIT ===
load_dotenv()
logging.basicConfig(level=logging.INFO)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise Exception("Missing GOOGLE_API_KEY")

# === APP INIT ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow requests from the frontend origin

# === STATUS TRACKING ===
query_status_map = {}
status_lock = Lock()

# === EMBEDDING WRAPPER ===
class SentenceTransformerWrapper(Embeddings):
    def __init__(self, model_name="all-mpnet-base-v2"):
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    def embed_documents(self, texts):
        return self._ef(texts)
    def embed_query(self, text):
        return self._ef([text])[0]

# === VECTORSTORE SETUP ===
embedding_function = SentenceTransformerWrapper()
chroma_client = chromadb.PersistentClient(path="chroma_db")
vectordb = Chroma(
    client=chroma_client,
    collection_name="documents_collection",
    embedding_function=embedding_function
)

# === LLM SETUP WITH FAILSAFE ===
genai.configure(api_key=GOOGLE_API_KEY)

# Define a list of compatible models for GoogleGenerativeAI
compatible_models = [
    "models/gemini-1.5-pro-001",
    "models/gemini-1.5-pro-002",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-001",
    "models/gemini-2.0-pro-exp",
    # Add other compatible models as needed
]

# Fetch available models and validate the model name
try:
    available_models = genai.list_models()
    if not available_models:
        logging.error("[LLM Setup] No models returned by the API. Check your API key and permissions.")
        raise Exception("No models available in the Generative AI API.")

    # Log the raw structure of the models for debugging
    logging.info(f"[LLM Setup] Raw model data: {available_models}")

    # Extract model details based on the actual structure of the objects
    model_details = [
        {"name": getattr(model, 'name', None), "methods": getattr(model, 'supportedMethods', [])}
        for model in available_models
    ]
    logging.info(f"[LLM Setup] Available models and their supported methods: {model_details}")

    # Select the first compatible model from the available models
    selected_model = next(
        (model['name'] for model in model_details if model['name'] in compatible_models),
        None
    )
    if not selected_model:
        logging.warning("[LLM Setup] No compatible models found. Using a hardcoded fallback model.")
        selected_model = "models/gemini-1.5-pro-001"  # Replace with a valid fallback model if known
except Exception as e:
    logging.error(f"[LLM Setup] Failed to fetch models: {e}")
    # Failsafe: Use a hardcoded default model or disable LLM functionality
    selected_model = "models/gemini-1.5-pro-001"  # Replace with a valid fallback model if known
    logging.warning(f"[LLM Setup] Failsafe activated. Using fallback model: {selected_model}")

try:
    llm = GoogleGenerativeAI(
        model=selected_model,
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=2048
    )
    logging.info(f"[LLM Setup] Using model: {selected_model}")
except Exception as e:
    logging.error(f"[LLM Setup] Failed to initialize LLM with model '{selected_model}': {e}")
    raise Exception("Critical error: Unable to configure the LLM.")

# === QA CHAIN ===
PROMPT = PromptTemplate(
    template="""You are a helpful assistant. Use the following context to answer the question at the end. If you don't know, say so.

Context:
{context}

Question: {question}
Helpful Answer:""",
    input_variables=["context", "question"]
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectordb.as_retriever(search_kwargs={"k": 3}),
    return_source_documents=True,
    chain_type_kwargs={"prompt": PROMPT}
)

# === MULTIMEDIA EXTRACTION ===
def extract_text_from_multimedia(file_path):
    try:
        if file_path.endswith(('.mp4', '.avi', '.mov')):
            video = VideoFileClip(file_path)
            audio_path = file_path.replace(file_path.split('.')[-1], 'wav')
            video.audio.write_audiofile(audio_path)
            file_path = audio_path

        if file_path.endswith(('.mp3', '.wav', '.ogg')):
            recognizer = sr.Recognizer()
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)
                return recognizer.recognize_google(audio_data)

        if file_path.endswith('.pdf'):
            try:
                from unstructured.partition.pdf import partition_pdf
                elements = partition_pdf(file_path)
                return "\n".join([str(element) for element in elements])
            except ImportError:
                logging.error("[PDF Processing] Missing dependencies for partition_pdf(). Install with: pip install 'unstructured[pdf]'")
                return "Error: Missing dependencies for PDF processing."
    except Exception as e:
        logging.error(f"[Multimedia] {e}")
        return ""

# === UPLOAD ENDPOINT ===
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        logging.error("[Upload] No file part in the request.")
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("[Upload] No file selected for upload.")
        return jsonify({'error': 'No file selected for upload.'}), 400

    try:
        # Ensure the uploads directory exists
        os.makedirs("uploads", exist_ok=True)
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)

        ext = filepath.split('.')[-1].lower()
        if ext in ('mp4', 'avi', 'mov', 'mp3', 'wav', 'ogg'):
            # Process multimedia files
            text = extract_text_from_multimedia(filepath)
            if text:
                vectordb.add_texts([text], metadatas=[{"source": file.filename}])
                logging.info(f"[Upload] Multimedia file processed: {file.filename}")
            else:
                logging.warning(f"[Upload] No text extracted from multimedia file: {file.filename}")
        elif ext == 'pdf':
            # Process PDF files
            try:
                from unstructured.partition.pdf import partition_pdf
                elements = partition_pdf(filepath)
                text = "\n".join([str(element) for element in elements])
                vectordb.add_texts([text], metadatas=[{"source": file.filename}])
                logging.info(f"[Upload] PDF file processed: {file.filename}")
            except ImportError:
                logging.error("[Upload] Missing dependencies for PDF processing. Install with: pip install 'unstructured[pdf]'")
                return jsonify({'error': 'Missing dependencies for PDF processing. Install with: pip install "unstructured[pdf]"'}), 500
        else:
            # Process other text-based files
            loader = DirectoryLoader("uploads", glob="**/*")
            documents = loader.load()
            splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            split_docs = splitter.split_documents(documents)
            vectordb.add_documents(split_docs)
            logging.info(f"[Upload] Text-based file processed: {file.filename}")

        return jsonify({'message': '✅ File uploaded & processed successfully.'}), 200

    except Exception as e:
        logging.error(f"[Upload] An error occurred while processing the file: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred while processing the file. Please try again later.'}), 500

# === QUERY ENDPOINT WITH PER-REQUEST STATUS ===
@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json()
    if not data:
        logging.error("[Query] No JSON payload received.")
        return jsonify({"error": "Invalid request. No JSON payload received."}), 400

    query_text = data.get("query", "").strip()
    if not query_text:
        logging.error("[Query] No query provided in the request.")
        return jsonify({"error": "No query provided"}), 400

    query_id = str(uuid.uuid4())
    with status_lock:
        query_status_map[query_id] = {"phase": "loading", "progress": 10}

    try:
        logging.info(f"[Query] Processing query: {query_text}")

        for _ in tqdm(range(3)):
            time.sleep(0.3)

        with status_lock:
            query_status_map[query_id] = {"phase": "retrieving", "progress": 50}

        result = qa_chain.invoke({"query": query_text})
        if not result:
            raise ValueError("No result returned from QA chain.")

        answer = result.get("result", "No answer found.")
        sources = [
            doc.metadata.get("source", "unknown") for doc in result.get("source_documents", [])
        ]

        with status_lock:
            query_status_map[query_id] = {"phase": "done", "progress": 100}

        logging.info(f"[Query] Query processed successfully. ID: {query_id}")
        return jsonify({
            "id": query_id,
            "answer": answer,
            "sources": sources
        })

    except google.generativeai.exceptions.ResourceExhausted as e:
        logging.error(f"[Query Error] Quota exceeded: {e}")
        return jsonify({"error": "Quota exceeded. Please check your plan and billing details."}), 429

    except Exception as e:
        logging.error(f"[Query Error] {e}", exc_info=True)
        with status_lock:
            query_status_map[query_id] = {"phase": "error", "progress": 0}
        return jsonify({"error": "An error occurred while processing the query. Please try again later."}), 500

# === STATUS ENDPOINT ===
@app.route("/api/result/<query_id>", methods=["GET"])
def get_result(query_id):
    global query_status_map
    result = query_status_map.get(query_id)
    if not result:
        logging.error(f"[Result] Query ID {query_id} not found in result map.")
        return jsonify({"error": "Result not found"}), 404
    return jsonify(result)

@app.route("/api/query_status/<query_id>", methods=["GET"])
def get_query_status(query_id):
    with status_lock:
        status = query_status_map.get(query_id, {"phase": "unknown", "progress": 0})
    return jsonify(status)

@app.route("/api/status", methods=["GET"])
def get_system_status():
    return jsonify({"status": "Server is running", "uptime": "24 hours"}), 200

# === DOCUMENT LISTING ===
@app.route("/api/documents", methods=["GET"])
def get_documents():
    try:
        uploads_dir = "uploads"
        if not os.path.exists(uploads_dir):
            return jsonify([])

        documents = []
        for filename in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, filename)
            if os.path.isfile(file_path):
                upload_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
                documents.append({
                    "name": filename,
                    "type": filename.split(".")[-1].upper(),
                    "uploadDate": upload_time.strftime("%Y-%m-%d %H:%M:%S")
                })

        return jsonify(documents)
    except Exception as e:
        logging.error(f"[Documents] {e}")
        return jsonify({"error": "Failed to fetch documents."}), 500

# === LAUNCH SERVER ===
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app.run(debug=True, port=5000, use_reloader=False)
