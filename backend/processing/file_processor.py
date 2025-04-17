import os
import logging
import shutil
from langchain_community.document_loaders import (
    TextLoader, UnstructuredPDFLoader, UnstructuredFileLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Define supported extensions (adjust as needed)
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".html", ".js", ".css"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}

# --- Helper Functions for Loading and Splitting ---

def _load_and_split_documents(filepath: str, filename: str, file_context: str = None) -> list:
    """Loads and splits a document based on its extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    docs = []
    loader = None

    # Base metadata including the original filename and optional context
    base_metadata = {"source": filename}
    if file_context:
        base_metadata["user_context"] = file_context  # Add user-provided context

    try:
        if ext in SUPPORTED_TEXT_EXTENSIONS:
            loader = TextLoader(filepath, encoding="utf-8")  # Specify encoding
        elif ext in SUPPORTED_PDF_EXTENSIONS:
            loader = UnstructuredPDFLoader(filepath, mode="single")
        else:
            try:
                loader = UnstructuredFileLoader(filepath, mode="single")
                logging.info(f"Using UnstructuredFileLoader for unknown extension: {ext}")
            except Exception as unstruct_err:
                logging.warning(f"UnstructuredFileLoader failed for {filename}: {unstruct_err}. Skipping file.")
                return []  # Return empty list if loader fails

        if loader:
            logging.info(f"Loading document: {filename} using {type(loader).__name__}")
            docs = loader.load()
            logging.info(f"Loaded {len(docs)} initial document sections.")
        else:
            logging.warning(f"No suitable loader found for file extension: {ext}. Skipping file.")
            return []

        # Split the loaded documents
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        split_docs = text_splitter.split_documents(docs)

        # Add base metadata to each split chunk
        for doc in split_docs:
            doc.metadata = {**base_metadata, **doc.metadata}  # Merge base metadata with any loader metadata

        logging.info(f"Split document into {len(split_docs)} chunks.")
        return split_docs

    except Exception as e:
        logging.error(f"Error loading/splitting file {filename}: {e}", exc_info=True)
        return []  # Return empty list on error

# --- Main Processing Function ---

def process_uploaded_file(
    temp_filepath: str,
    filename: str,
    chromadb_instance,  # Expecting ChromaDBWrapper instance
    persistent_dir: str,
    file_context: str = None  # Add optional context parameter
) -> tuple[bool, str]:
    """
    Processes an uploaded file: loads, splits, adds to ChromaDB, and moves to persistent storage.

    Args:
        temp_filepath: The temporary path where the file was saved.
        filename: The original (secured) name of the file.
        chromadb_instance: An instance of ChromaDBWrapper.
        persistent_dir: The directory to move the file to upon success.
        file_context: Optional user-provided context string.

    Returns:
        A tuple (success: bool, message: str).
    """
    try:
        # Load and split document, passing context
        split_documents = _load_and_split_documents(temp_filepath, filename, file_context)

        if not split_documents:
            # Error occurred during loading/splitting or file type not supported
            # Clean up temp file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return False, f"Failed to load or split file '{filename}'. Check logs for details."

        # Add documents (chunks with metadata) to ChromaDB
        logging.info(f"Adding {len(split_documents)} chunks for '{filename}' to ChromaDB...")
        chromadb_instance.add_documents(split_documents)
        logging.info(f"Successfully added chunks for '{filename}' to ChromaDB.")

        # Move the original file to persistent storage
        persistent_filepath = os.path.join(persistent_dir, filename)
        try:
            shutil.move(temp_filepath, persistent_filepath)
            logging.info(f"Moved original file to persistent storage: {persistent_filepath}")
        except Exception as move_err:
            logging.error(f"Failed to move file {filename} to persistent storage: {move_err}", exc_info=True)
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return False, f"File processed and added to DB, but failed to move to persistent storage: {move_err}"

        return True, f"File '{filename}' processed and indexed successfully."

    except Exception as e:
        logging.error(f"An unexpected error occurred processing file {filename}: {e}", exc_info=True)
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except Exception as cleanup_error:
                logging.error(f"Error cleaning up temp file {temp_filepath} after processing error: {cleanup_error}")
        return False, f"An internal error occurred while processing '{filename}'."

