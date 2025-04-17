import os
import logging
import shutil  # Import shutil for file operations
import speech_recognition as sr
from moviepy import VideoFileClip  # Corrected import
# Assuming unstructured and langchain are installed and needed here
try:
    from unstructured.partition.pdf import partition_pdf
except ImportError:
    partition_pdf = None
    logging.warning("unstructured[pdf] not installed. PDF processing will be unavailable.")

try:
    from langchain_community.document_loaders import DirectoryLoader
    from langchain.text_splitter import CharacterTextSplitter
except ImportError:
    DirectoryLoader = None
    CharacterTextSplitter = None
    logging.warning("langchain_community or langchain not fully installed. Text file processing might be limited.")


def _extract_text_from_audio(audio_path):
    """Helper function to extract text from an audio file."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        logging.warning(f"Google Speech Recognition could not understand audio: {audio_path}")
        return ""
    except sr.RequestError as e:
        logging.error(f"Could not request results from Google Speech Recognition service; {e}: {audio_path}")
        return ""
    except Exception as e:
        logging.error(f"Error processing audio file {audio_path}: {e}")
        return ""


def _extract_text_from_video(video_path):
    """Helper function to extract text from a video file."""
    try:
        video = VideoFileClip(video_path)
        # Create a temporary audio file path
        base, _ = os.path.splitext(video_path)
        audio_path = base + ".wav"
        video.audio.write_audiofile(audio_path, codec='pcm_s16le')  # Specify codec for compatibility
        text = _extract_text_from_audio(audio_path)
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return text
    except Exception as e:
        logging.error(f"Error processing video file {video_path}: {e}")
        return ""
    finally:
        # Ensure cleanup even if extraction fails mid-way
        if 'audio_path' in locals() and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as cleanup_error:
                logging.error(f"Error cleaning up temporary audio file {audio_path}: {cleanup_error}")


def _extract_text_from_pdf(pdf_path):
    """Helper function to extract text from a PDF file."""
    if partition_pdf is None:
        logging.error("PDF processing dependency 'unstructured' is not installed.")
        raise ImportError("Missing dependencies for PDF processing. Install with: pip install 'unstructured[pdf]'")
    try:
        elements = partition_pdf(pdf_path)
        return "\n".join([str(element) for element in elements])
    except Exception as e:
        logging.error(f"Error processing PDF file {pdf_path}: {e}")
        return ""


def _load_and_split_text_files(directory_path):
    """Loads and splits documents from a directory."""
    if DirectoryLoader is None or CharacterTextSplitter is None:
        logging.error("Text processing dependencies 'langchain_community' or 'langchain' are not fully installed.")
        raise ImportError("Missing dependencies for text file processing.")
    try:
        loader = DirectoryLoader(directory_path, glob="**/[!.]*", show_progress=True, use_multithreading=True)
        documents = loader.load()
        if not documents:
            logging.warning(f"No documents loaded from {directory_path}")
            return []
        splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        split_docs = splitter.split_documents(documents)
        return split_docs
    except Exception as e:
        logging.error(f"Error loading/splitting text files from {directory_path}: {e}")
        return []


def process_uploaded_file(filepath, filename, chromadb_instance, persistent_dir):
    """
    Processes an uploaded file, adds it to ChromaDB, and moves the original
    to the persistent directory upon success. Cleans up temp file on failure.

    Args:
        filepath (str): The full path to the temporary uploaded file.
        filename (str): The original name of the uploaded file.
        chromadb_instance (ChromaDBWrapper): Instance to interact with ChromaDB.
        persistent_dir (str): The directory to move the file to upon success.

    Returns:
        bool: True if processing and moving was successful, False otherwise.
        str: A message indicating the outcome.
    """
    processing_successful = False
    message = f"Processing started for '{filename}'."
    target_filepath = os.path.join(persistent_dir, filename)  # Define target path

    try:
        ext = filename.split('.')[-1].lower()
        logging.info(f"Processing file: {filename} with extension: {ext}")

        # --- File Type Processing Logic ---
        if ext in ('mp4', 'avi', 'mov'):
            text = _extract_text_from_video(filepath)
            if text:
                chromadb_instance.add_texts([text], metadatas=[{"source": filename, "type": "video"}])
                processing_successful = True
                message = f"Video file '{filename}' processed."
            else:
                message = f"Could not extract text from video file '{filename}'."

        elif ext in ('mp3', 'wav', 'ogg', 'flac'):
            text = _extract_text_from_audio(filepath)
            if text:
                chromadb_instance.add_texts([text], metadatas=[{"source": filename, "type": "audio"}])
                processing_successful = True
                message = f"Audio file '{filename}' processed."
            else:
                message = f"Could not extract text from audio file '{filename}'."

        elif ext == 'pdf':
            text = _extract_text_from_pdf(filepath)
            if text:
                chromadb_instance.add_texts([text], metadatas=[{"source": filename, "type": "pdf"}])
                processing_successful = True
                message = f"PDF file '{filename}' processed."
            else:
                message = f"Could not extract text from PDF file '{filename}'."

        elif ext in ('txt', 'md', 'py', 'js', 'html', 'css', 'json', 'csv'):
            containing_dir = os.path.dirname(filepath)
            split_docs = _load_and_split_text_files(containing_dir)
            relevant_docs = [doc for doc in split_docs if doc.metadata.get('source') == filepath]
            if relevant_docs:
                for doc in relevant_docs:
                    doc.metadata['type'] = 'text'
                chromadb_instance.add_documents(relevant_docs)
                processing_successful = True
                message = f"Text file '{filename}' processed."
            else:
                message = f"Could not process text file '{filename}'."
        else:
            message = f"Unsupported file type: '{ext}'."
            logging.warning(f"Unsupported file type: {ext} for file {filename}")
            # processing_successful remains False

        # --- Move or Cleanup ---
        if processing_successful:
            try:
                # Ensure target directory exists (should be done at app start, but double-check)
                os.makedirs(persistent_dir, exist_ok=True)
                # Move the file from temporary uploads to persistent storage
                shutil.move(filepath, target_filepath)
                logging.info(f"Moved processed file from {filepath} to {target_filepath}")
                message += " File moved to persistent storage."  # Append to success message
                return True, message
            except Exception as move_error:
                logging.error(f"Failed to move file {filepath} to {persistent_dir}: {move_error}", exc_info=True)
                return False, f"Processed '{filename}' but failed to move file: {move_error}"
        else:
            return False, message

    except ImportError as e:
        logging.error(f"Import error during processing {filename}: {e}")
        return False, str(e)  # Return specific dependency error
    except Exception as e:
        logging.error(f"An error occurred while processing the file {filename}: {e}", exc_info=True)
        return False, f"An internal error occurred while processing '{filename}'."
    finally:
        # --- Cleanup on Failure ---
        if not processing_successful and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logging.info(f"Cleaned up temporary file after failed processing: {filepath}")
            except Exception as cleanup_error:
                logging.error(f"Error cleaning up failed file {filepath}: {cleanup_error}")

