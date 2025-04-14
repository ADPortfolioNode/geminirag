import os
import argparse
from tqdm import tqdm
from textwrap import shorten
from langchain.embeddings import OpenAIEmbeddings

import chromadb
from chromadb.utils import embedding_functions

# === CONFIG ===
MAX_DOC_SIZE = 3500
MAX_BATCH_SIZE = 50


def load_lines_from_files(documents_directory):
    documents = []
    metadatas = []
    files = os.listdir(documents_directory)
    for filename in files:
        file_path = os.path.join(documents_directory, filename)
        with open(file_path, "r", encoding="utf-8") as file:
            for line_number, line in enumerate(tqdm(file.readlines(), desc=f"Reading {filename}"), 1):
                line = line.strip()
                if not line:
                    continue
                safe_line = shorten(line, width=MAX_DOC_SIZE, placeholder="...")
                documents.append(safe_line)
                metadatas.append({"filename": filename, "line_number": line_number})
    return documents, metadatas


# Use OpenAI embeddings for ChromaDB
def configure_google_embedding():
    return OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=os.getenv("GEMINI_API_KEY"))


def load_into_chroma(documents, metadatas, collection):
    print("🔍 Checking existing documents to avoid duplicates...")
    existing_docs_set = set()

    try:
        # Chroma only returns up to 10,000 by default. You can set limit=None if needed.
        existing_data = collection.get(include=["documents"], limit=None)
        if "documents" in existing_data:
            existing_docs_set = set(existing_data["documents"])
    except Exception as e:
        print(f"⚠️ Warning: Failed to fetch existing documents. Proceeding fresh. Error: {e}")

    # Filter unique content
    new_docs, new_meta = [], []
    for doc, meta in zip(documents, metadatas):
        if doc not in existing_docs_set:
            new_docs.append(doc)
            new_meta.append(meta)

    print(f"📂 {len(new_docs)} new unique documents to add (skipped {len(documents) - len(new_docs)} duplicates).")

    if not new_docs:
        print("🛑 No new data to upload. All content already exists.")
        return

    # Create new IDs for unique entries
    start_id = collection.count()
    ids = [str(start_id + i) for i in range(len(new_docs))]

    for i in tqdm(range(0, len(new_docs), MAX_BATCH_SIZE), desc="Adding new documents"):
        batch_docs = new_docs[i:i + MAX_BATCH_SIZE]
        batch_ids = ids[i:i + MAX_BATCH_SIZE]
        batch_meta = new_meta[i:i + MAX_BATCH_SIZE]

        try:
            collection.add(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
            )
        except ValueError as e:
            print(f"❌ ValueError occurred: {e}")
        except KeyError as e:
            print(f"❌ KeyError occurred: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    print(f"✅ Added {collection.count() - start_id} new documents.")


def main(documents_directory="documents", collection_name="documents_collection", persist_directory="chroma_storage"):
    documents, metadatas = load_lines_from_files(documents_directory)
    embedding_function = configure_google_embedding()
    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(name=collection_name, embedding_function=embedding_function)
    load_into_chroma(documents, metadatas, collection)
    print("🏁 Load complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load documents into a ChromaDB vector collection (unique entries only)")
    parser.add_argument("--data_directory", type=str, default="documents", help="Path to your .txt files")
    parser.add_argument("--collection_name", type=str, default="documents_collection", help="Chroma collection name")
    parser.add_argument("--persist_directory", type=str, default="chroma_storage", help="Chroma DB storage path")
    args = parser.parse_args()

    main(
        documents_directory=args.data_directory,
        collection_name=args.collection_name,
        persist_directory=args.persist_directory,
    )
    # Example usage:
    # python load_data.py --data_directory documents --collection_name my_collection --persist_directory chroma_storage
    # This will load all .txt files from the 'documents' directory into a ChromaDB collection named 'my_collection'
    # and store the database in 'chroma_storage'.
    # Ensure you have the necessary environment variables set for Google API keys.  
    # chroma_db = ChromaClient()
    # chroma_db.load_data("documents", "my_collection", "chroma_storage")
    # chroma_db.add_documents("documents", "my_collection", "chroma_storage")
    # chroma_db.add_documents("documents", "my_collection", "chroma_storage", "documents")

