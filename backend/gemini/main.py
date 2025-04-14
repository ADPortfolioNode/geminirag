import argparse
import os
from typing import List

import google.generativeai as genai
from langchain.chains import RetrievalQA
from langchain.embeddings import OpenAIEmbeddings
import chromadb

# Configure Gemini API key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model
model = genai.GenerativeModel("gemini-pro")

def configure_google_embedding():
    return OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=os.getenv("GEMINI_API_KEY"))

def get_gemini_response(query, qa: RetrievalQA):
    return qa.run(query)

def main(
    collection_name: str = "documents_collection", persist_directory: str = "."
) -> None:
    # Check if the GOOGLE_API_KEY environment variable is set. Prompt the user to set it if not.
    google_api_key = None
    if "GOOGLE_API_KEY" not in os.environ:
        gapikey = input("Please enter your Google API Key: ")
        genai.configure(api_key=gapikey)
        google_api_key = gapikey
    else:
        google_api_key = os.environ["GOOGLE_API_KEY"]

    # Instantiate a persistent chroma client in the persist_directory.
    # This will automatically load any previously saved collections.
    client = chromadb.PersistentClient(path=persist_directory)

    # Create embedding function
    embedding_function = configure_google_embedding()

    # Get the collection
    collection = client.get_collection(
        name=collection_name, embedding_function=embedding_function
    )

    # We use a simple input loop
    while True:
        # Get the user's query
        query = input("Query: ")
        if len(query) == 0:
            print("Please enter a question. Ctrl+C to Quit.\n")
            continue
        print("\nThinking...\n")

        # Query the collection to get the 5 most relevant results
        results = collection.query(
            query_texts=[query], n_results=5, include=["documents", "metadatas"]
        )

        sources = "\n".join(
            [
                f"{result['filename']}: line {result['line_number']}"
                for result in results["metadatas"][0]  # type: ignore
            ]
        )

        # Get the response from Gemini using the LangChain chain
        qa = RetrievalQA.from_chain_type(llm=model, chain_type="stuff", retriever=collection.as_retriever())
        response = qa({"query": query})["result"]

        # Output, with sources
        print(response)
        print("\n")
        print(f"Source documents:\n{sources}")
        print("\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load documents from a directory into a Chroma collection"
    )

    parser.add_argument(
        "--persist_directory",
        type=str,
        default="chroma_storage",
        help="The directory where you want to store the Chroma collection",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        default="documents_collection",
        help="The name of the Chroma collection",
    )

    # Parse arguments
    args = parser.parse_args()

    main(
        collection_name=args.collection_name,
        persist_directory=args.persist_directory,
    )
