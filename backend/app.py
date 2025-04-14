import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_cors import CORS
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter
import logging
from tqdm import tqdm
import time
from moviepy import VideoFileClip, AudioFileClip
import speech_recognition as sr
import datetime

app = Flask(__name__)
# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
# Ensure your Google API key is set in your environment
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    raise Exception("Missing GOOGLE_API_KEY environment variable.")

# Configure the generativeai client with your API key
genai.configure(api_key=API_KEY)

# Instantiate the GenerativeModel with the valid model name and desired parameters
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",  # Valid model name
    generation_config={
        "temperature": 0.7,
        "top_p": 0.95,
        "max_output_tokens": 2048
    }
)

def extract_text_from_multimedia(file_path):
    """Extract text from multimedia files (audio/video)."""
    try:
        if file_path.endswith(('.mp4', '.avi', '.mov')):
            # Extract audio from video
            video = VideoFileClip(file_path)
            audio_path = file_path.replace(file_path.split('.')[-1], 'wav')
            video.audio.write_audiofile(audio_path)
            file_path = audio_path

        if file_path.endswith(('.mp3', '.wav', '.ogg')):
            # Transcribe audio to text
            recognizer = sr.Recognizer()
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)
                return recognizer.recognize_google(audio_data)

    except Exception as e:
        logging.error(f"Error extracting text from multimedia: {e}")
        return ""

def get_rag_response(query):
    """Performs RAG (Retrieval Augmented Generation) using ChromaDB and OpenAI API."""
    try:
        # Query ChromaDB for relevant context
        results = collection.query(query_texts=[query], n_results=5)
        context = "\n".join([doc for doc in results["documents"][0]])

        # If context is found in ChromaDB, use it to construct the prompt
        if context:
            prompt = f"""
            Use the following context to answer the question at the end. 
            If you don't know the answer, just say that you don't know, don't try to make up an answer.

            Context:
            {context}

            Question: {query}
            """
        else:
            # If no context is found, fallback to a general internet search
            prompt = f"""
            You are a helpful assistant. Answer the following question based on your general knowledge:

            Question: {query}
            """

        # Generate a response using OpenAI API
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        return completion.choices[0].message.content

    except Exception as e:
        logging.error(f"Error in RAG workflow: {e}")
        return "Error retrieving context or generating response."

@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json()
    query_text = data.get("query")
    if not query_text:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Simulate progress tracking
        for i in tqdm(range(5), desc="Processing query"):
            time.sleep(1)  # Simulate processing time

        # Generate content using the updated model
        response = model.generate_content(query_text)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Save the uploaded file to the uploads directory
        os.makedirs("uploads", exist_ok=True)
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)

        # Process multimedia files
        if filepath.split('.')[-1].lower() in ('mp4', 'avi', 'mov', 'mp3', 'wav', 'ogg'):
            extracted_text = extract_text_from_multimedia(filepath)
            if extracted_text:
                # Add extracted text to ChromaDB
                vectordb.add_documents([{
                    'content': extracted_text,
                    'metadata': {'source': file.filename}
                }])
        else:
            # Handle text files
            loader = DirectoryLoader(filepath)
            documents = loader.load()
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            docs = text_splitter.split_documents(documents)
            vectordb.add_documents(docs)

        # Sync uploaded documents to ensure the last document is accurate
        sync_uploaded_documents()

        return jsonify({'message': 'File uploaded and processed successfully'}), 200
    except Exception as e:
        logging.error(f"Error processing file upload: {e}")
        return jsonify({'error': str(e)}), 500

def sync_uploaded_documents():
    """Syncs the uploaded documents to ensure the last document is accurate."""
    try:
        uploads_dir = "uploads"
        if not os.path.exists(uploads_dir):
            return

        for filename in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, filename)
            if os.path.isfile(file_path):
                loader = DirectoryLoader(uploads_dir, glob="**/*")
                documents = loader.load()
                text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
                docs = text_splitter.split_documents(documents)
                vectordb.add_documents(docs)
    except Exception as e:
        logging.error(f"Error syncing uploaded documents: {e}")

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
                file_type = filename.split(".")[-1].upper()
                upload_date = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
                documents.append({
                    "name": filename,
                    "type": file_type,
                    "uploadDate": upload_date
                })

        return jsonify(documents)
    except Exception as e:
        logging.error(f"Error fetching documents: {e}")
        return jsonify({"error": "Failed to fetch documents."}), 500

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app.run(debug=True, port=5000, use_reloader=False)