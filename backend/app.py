import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_cors import CORS
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter
import logging


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

@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json()
    query_text = data.get("query")
    if not query_text:
        return jsonify({"error": "No query provided"}), 400

    try:
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

        # Load the file into ChromaDB
        loader = DirectoryLoader("uploads", glob="**/*")
        documents = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        docs = text_splitter.split_documents(documents)
        vectordb.add_documents(docs)

        return jsonify({'message': 'File uploaded and processed successfully'}), 200
    except Exception as e:
        logging.error(f"Error processing file upload: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
