# Instructions for Running the Gemini RAG Project

This document provides step-by-step instructions for setting up, running, and testing the Gemini Retrieval-Augmented Generation (RAG) project. Follow these steps carefully to ensure the application runs smoothly.

---

## Prerequisites

1. **Operating System:**
   - Windows (tested on Windows 10/11).

2. **Software Requirements:**
   - Python 3.8 or higher.
   - Node.js (for the frontend).
   - A virtual environment (`venv`) for Python dependencies.

3. **API Keys:**
   - Google Gemini API Key.
   - Ensure the `.env` file in the `backend` directory contains the following:
     ```properties
     GEMINI_API_KEY=your_gemini_api_key
     ```

4. **Environment Setup:**
   - Install Python and Node.js.
   - Install `pip` for Python package management.

---

## Backend Setup

1. **Navigate to the Backend Directory:**
   ```bash
   cd e:\2024 RESET\geminirag\backend
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Load Documents into ChromaDB:**
   ```bash
   python load_data.py --data_directory documents --persist_directory chroma_storage --collection_name documents_collection
   ```

5. **Run the Backend Server:**
   ```bash
   python app.py
   ```
   - The server will start on `http://localhost:5000`.

---

## Frontend Setup

1. **Navigate to the Frontend Directory:**
   ```bash
   cd e:\2024 RESET\geminirag\frontend
   ```

2. **Install Dependencies:**
   ```bash
   npm install
   ```

3. **Start the Frontend Development Server:**
   ```bash
   npm start
   ```
   - The application will open in your default browser at `http://localhost:3000`.

---

## Testing the Application

1. **Upload Documents:**
   - Use the file upload section in the frontend to upload `.txt` or `.csv` files.

2. **Query the Assistant:**
   - Enter a query in the input box and click "Submit."
   - The assistant will respond with an answer and relevant sources.

3. **Interact with the LLM:**
   - Open the modal by clicking "Interact with LLM."
   - Enter a query and view the response.

---

## Troubleshooting

1. **Backend Issues:**
   - Check the terminal for error logs.
   - Ensure the `.env` file contains the correct API key.

2. **Frontend Issues:**
   - Check the browser console for errors.
   - Ensure the backend server is running.

3. **Database Issues:**
   - Verify that the ChromaDB files are present in the `chroma_storage` directory.

---

## Deployment

1. **Backend Deployment:**
   - Use platforms like Heroku, AWS, or Azure to deploy the Flask server.

2. **Frontend Deployment:**
   - Use platforms like Vercel or Netlify to deploy the React application.

3. **Environment Variables:**
   - Ensure the API keys are securely stored in the deployment environment.

---

## Additional Notes

- Replace the example documents in the `documents` folder with your own files to customize the assistant's knowledge base.
- Regularly update the dependencies by running:
  ```bash
  pip install --upgrade -r requirements.txt
  npm update
  ```

---

# RAG Operations Query Workflow

This document outlines the sequence of operations when a user submits a query to the RAG system.

## Overview

The system uses a frontend React application and a backend Flask server. The frontend employs an agentic structure (simulated via `AssistantClass`) where a `Concierge Assistant` orchestrates the workflow by delegating tasks to specialized system assistants (`ChromaDB Admin`, `Gemini API Admin`).

## Frontend Workflow (`App.js` & `AssistantClass.js`)

1.  **User Input:** User types a query into `QueryForm` and submits.
2.  **Initiation (`App.js`):**
    *   `handleQuerySubmit` is triggered.
    *   User's query is added to the `ChatWindow` history.
    *   Input field is cleared.
    *   Overall progress bar is reset.
3.  **Delegation to Concierge (`App.js`):**
    *   `handleQuerySubmit` retrieves the `Concierge Assistant` instance.
    *   It calls the `Concierge Assistant`'s `performTask` method, passing the query and callbacks (`setOverallProgress`, `updateChat`).
4.  **Concierge Analysis (`AssistantClass.js` - Concierge):**
    *   The Concierge's `performTask` analyzes the query text.
    *   It determines the primary intent:
        *   **Count Query:** If keywords like "how many", "count", "documents" are present.
        *   **Summarization/Topic Query:** If keywords like "summarize", "what topics" are present along with "document" or "context".
        *   **Default RAG Query:** For all other cases.
    *   It updates the overall progress bar (`Concierge: Analyzing query...`).
5.  **Concierge Delegation (`AssistantClass.js` - Concierge):**
    *   Based on the intent, it identifies the target system assistant:
        *   `ChromaDB Admin` for count queries.
        *   `Gemini API Admin` for summarization, topic extraction, or default RAG.
    *   It may generate a specific `taskInstruction` string (e.g., "Summarize the main points...").
    *   It updates the overall progress bar (`Concierge: Delegating...`).
    *   It calls the target system assistant's `performTask` method, passing a payload object `{ query, taskInstruction }` and the original callbacks.
6.  **System Assistant Task Execution (`AssistantClass.js` - Target Assistant):**
    *   The target assistant (`ChromaDB Admin` or `Gemini API Admin`) receives the payload.
    *   It updates the overall progress bar (`AssistantName: Preparing request...`).
    *   It constructs the JSON body for the backend API call, including `query` and `task_instruction`.
    *   It makes a `POST` request to the backend `/api/query` endpoint using `fetch`.
    *   It updates the overall progress bar (`AssistantName: Sending request...`, `AssistantName: Waiting for response...`).
7.  **Response Handling (`AssistantClass.js` - Target Assistant):**
    *   The assistant receives the JSON response from the backend.
    *   **On Success:**
        *   It extracts the `answer` from the response.
        *   It calls the `updateChat` callback to add the answer to the `ChatWindow`.
        *   It calls `setOverallProgress` to set progress to 100% and display a success message.
    *   **On Failure:**
        *   It extracts the `error` message.
        *   It calls the `updateChat` callback to add the error message to the `ChatWindow`.
        *   It calls `setOverallProgress` to set progress to 0% and display a failure message.
    *   The assistant marks itself as complete.
8.  **Concierge Completion (`AssistantClass.js` - Concierge):**
    *   After the delegated task finishes (success or failure), control returns to the Concierge's `performTask`.
    *   The Concierge updates the overall progress bar (`Concierge: Delegation complete.`) and marks itself as complete.

## Backend Workflow (`app.py` - `/api/query`)

1.  **Request Received:** Flask endpoint receives the `POST` request with JSON body containing `query` and optional `task_instruction`.
2.  **Count Intent Check:**
    *   If `task_instruction` is **not** provided, the backend checks if the `query` matches keywords for a document count request.
    *   If it's a count query:
        *   Call `chromadb_wrapper.count_documents()`.
        *   Format a response string (e.g., "There are X documents indexed.").
        *   Return `jsonify({'answer': count_response})`.
3.  **RAG - Step 1: ChromaDB Retrieval:**
    *   Call `chromadb_wrapper.retrieve(query)` to get relevant document chunks from the vector database.
    *   Log the number of documents found.
4.  **RAG - Step 2: Context Selection & Fallback:**
    *   **If ChromaDB documents found:** Use these documents as context (`source_type="documents"`).
    *   **If no ChromaDB documents found:**
        *   Call `perform_internet_search(query)` (placeholder).
        *   **If internet results found:** Use these results as context (`source_type="internet"`).
        *   **If no internet results found:** Use empty context (`source_type="none"`).
5.  **RAG - Step 3: Prompt Formatting:**
    *   Call `gemini.prompts.format_rag_prompt`, passing the original `query`, the selected `documents` (context), the determined `source_type`, and the `task_instruction` received from the frontend.
    *   The prompter creates the final text prompt for the LLM, including specific instructions and context if available.
6.  **RAG - Step 4: LLM Generation:**
    *   Call `gemini.client.GeminiAPI.generate_response` with the formatted prompt.
    *   The client sends the prompt to the configured Gemini model.
7.  **RAG - Step 5: Response Processing:**
    *   Parse the response from the Gemini model.
    *   Append source information (e.g., "(Source: Internal Documents)") based on `source_type`.
8.  **Return Response:** Return `jsonify({'answer': final_answer})` or `jsonify({'error': error_message})` in case of exceptions.

## File Upload Workflow

1.  **User Upload (Frontend):** User selects file via `FileUpload` component **and optionally provides context/query** in the text area.
2.  **API Call (Frontend):** `FileUpload` sends the file **and optional context string** via `FormData` in a `POST` request to `/api/upload`. Progress is updated via `setProgress`.
3.  **File Save & Context Retrieval (Backend):** `/api/upload` receives the file and context (`request.form.get('context')`), uses `secure_filename`, checks for existing filename in `persistent_documents`, saves temporarily to `uploads`.
4.  **Processing (Backend):** Calls `process_uploaded_file` from `processing/file_processor.py`, **passing the file path, filename, ChromaDB instance, persistent dir, and the optional context string**.
5.  **Indexing (Backend - `file_processor`):**
    *   `_load_and_split_documents` is called **with the context string**.
    *   Text is extracted based on file type.
    *   Text is split into chunks.
    *   **Base metadata including `source` (filename) and `user_context` (if provided) is added to each chunk.**
    *   `chromadb_wrapper.add_documents` is called to embed and store chunks with metadata in ChromaDB.
6.  **Move File (Backend - `file_processor`):** If processing and indexing succeed, moves the original file from `uploads` to `persistent_documents`.
7.  **Response (Backend):** Returns success or error message to the frontend.
8.  **UI Update (Frontend):** `FileUpload` displays message, clears inputs, calls `onUploadSuccess` (`handleUploadSuccess` in `App.js`).
9.  **Document List Refresh (Frontend):** `handleUploadSuccess` calls `fetchDocuments` to update the list in the footer. It also notifies the `Flask Server Admin` assistant (simulation).

---

By following these instructions, you should be able to set up and run the Gemini RAG project successfully. For further assistance, refer to the project documentation or contact the development team.