import os
import logging
import shutil
from langchain.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from unstructured.partition.auto import partition
from langchain.document_loaders import UnstructuredFileLoader

# === CONSTANTS ===
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# === Document Processing Logic ===

def process_and_add_document(filepath, filename, chromadb_wrapper, file_context=None):
    """Processes a document using unstructured and adds its content to ChromaDB."""
    logging.info(f"Processing file: {filename}")
    try:
        # Use unstructured to partition the file
        elements = partition(filename=filepath)

        # Extract text from the elements
        text = "\n\n".join([str(el.text) for el in elements])

        # Split the text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        docs = text_splitter.create_documents([text])

        # Add metadata to each chunk
        for doc in docs:
            doc.metadata['source'] = filename
            if file_context:
                doc.metadata['file_context'] = file_context

        # Add documents to ChromaDB
        chromadb_wrapper.add_documents(docs)
        logging.info(f"Successfully processed and added document: {filename}")

    except Exception as e:
        logging.error(f"Failed to process file: {filename}. Reason: {e}", exc_info=True)
        raise

# === Internet Search Logic ===
def perform_internet_search(query, num_results=3):
    # ... existing code ...

# === Relevance Scoring Logic ===
def score_relevance(query, documents):
    # ... existing code ...
