import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from moviepy import VideoFileClip
import speech_recognition as sr

from langchain.chains import RetrievalQA
from langchain.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_chroma import Chroma

# === INIT ===
load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# === ENV SETUP ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "jsonkeyfile.json"
google_api_key = os.getenv("GEMINI_API_KEY")
assert google_api_key, "Missing GEMINI_API_KEY in .env"

# === EMBEDDING CONFIG ===
embedding_function = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=google_api_key)

# === CHROMA VECTOR STORE ===
persist_directory = "chroma_storage"
collection_name = "documents_collection"

vectordb = Chroma(
    persist_directory=persist_directory,
    embedding_function=embedding_function,
    collection_name=collection_name
)

qa = RetrievalQA.from_chain_type(
    llm=None,  # Replace with appropriate LLM initialization
    chain_type="stuff",
    retriever=vectordb.as_retriever(),
    return_source_documents=True
)

# === AUDIO/VIDEO TO TEXT UTIL ===
def extract_text_from_video(file_path):
    try:
        video = VideoFileClip(file_path)
        audio_file = "temp_audio.wav"
        video.audio.write_audiofile(audio_file)
        text = extract_text_from_audio(audio_file)
        os.remove(audio_file)
        return text
    except (ValueError, KeyError) as e:
        logging.error("Specific error occurred: %s", e)
        return ""
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return ""

def extract_text_from_audio(file_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except (ValueError, KeyError) as e:
        logging.error("Specific error occurred: %s", e)
        return ""
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return ""

def extract_text_from_multimedia(file_path):
    ext = file_path.split(".")[-1].lower()
    if ext in ("mp4", "avi", "mov"):
        return extract_text_from_video(file_path)
    elif ext in ("mp3", "wav", "ogg"):
        return extract_text_from_audio(file_path)
    return ""

# === DOCUMENT INGESTION ===
def load_documents_into_chroma(folder_path="uploads"):
    loader = DirectoryLoader(folder_path, glob="**/*")
    documents = loader.load()

    for doc in documents:
        ext = doc.metadata["source"].split(".")[-1].lower()
        if ext in ("mp4", "avi", "mov", "mp3", "wav", "ogg"):
            doc.page_content = extract_text_from_multimedia(doc.metadata["source"])

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    docs = text_splitter.split_documents(documents)
    vectordb.add_documents(docs)

# === ROUTES ===
@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json()
    user_query = data.get("query")

    if not user_query:
        return jsonify({"error": "Missing query"}), 400

    try:
        result = qa({"query": user_query})
        answer = result["result"]
        sources = []

        for doc in result.get("source_documents", []):
            meta = doc.metadata
            source = f"{meta.get('source', 'unknown')} (line {meta.get('line_number', 'N/A')})"
            sources.append(source)

        return jsonify({
            "answer": answer,
            "sources": sources
        })
    except (ValueError, KeyError) as e:
        logging.error("Specific error occurred: %s", e)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        os.makedirs("uploads", exist_ok=True)
        file_path = os.path.join("uploads", file.filename)
        file.save(file_path)

        load_documents_into_chroma("uploads")
        return jsonify({"message": "File uploaded and processed."}), 200
    except (ValueError, KeyError) as e:
        logging.error("Specific error occurred: %s", e)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return jsonify({"error": str(e)}), 500

# === BOOT ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
