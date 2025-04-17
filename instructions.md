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

5. **Vector Database:**
   - This project uses ChromaDB with a `PersistentClient`.
   - Vector data and metadata are stored locally in the `./chroma_db` directory within the `backend`.

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

1.  **Initialization:**
    *   `App.js` loads the API specification from `src/assistants/geminiAiApi.json`. <!-- Updated path -->
    *   State is initialized for selected model, method, and required input modalities (defaulting to `gemini-pro`, `generateContent`, `['text']`).
2.  **User Interaction:**
    *   User selects a Gemini model and method using dropdowns below the chat window.
    *   `App.js` state (`selectedModel`, `selectedMethod`) is updated.
    *   `useEffect` hooks update the available methods for the selected model and determine the `requiredInputs` based on the JSON spec for the selected model/method.
    *   The `QueryForm` component receives the `requiredInputs` array as a prop.
    *   `QueryForm` dynamically renders input fields (e.g., text area, image file input) based on the contents of `requiredInputs`.
3.  **User Input & Submission:**
    *   User fills the displayed input fields (text, selects an image, etc.).
    *   User clicks "Submit".
    *   `QueryForm`'s `onSubmit` creates a `formData` object containing the values from the rendered inputs (e.g., `{ text: '...', image: File }`).
    *   `QueryForm` calls the `handleQuerySubmit` function in `App.js`, passing the `formData` object.
4.  **Initiation (`App.js`):**
    *   `handleQuerySubmit` receives the `formData`.
    *   The text part of the query is added to the `ChatWindow`. (Image display not implemented).
    *   Input fields are cleared. Progress bar reset.
5.  **Delegation to Concierge (`App.js`):**
    *   `handleQuerySubmit` retrieves the `Concierge Assistant`.
    *   It creates a `taskPayload` containing the original `formData`, selected model/method details, and the primary text query.
    *   It calls the `Concierge Assistant`'s `performTask` method with the `taskPayload` and callbacks.
6.  **Concierge Planning (`AssistantClass.js` - Concierge):**
    *   Receives the `taskPayload`.
    *   Makes a `POST` request to `/api/generate_plan` (currently sending only the primary text query for planning).
    *   Receives and displays the plan. Parses the plan.
7.  **Plan Execution (`AssistantClass.js` - Concierge):**
    *   Iterates through steps.
    *   For each step, prepares a `stepPayload` including the task description and context from the previous step, **and potentially details from the original user request (`originalRequest`) if needed by the target assistant.**
    *   Calls the target assistant's `performTask`. Captures the result.
8.  **Execution Completion (`AssistantClass.js` - Concierge):**
    *   After successfully executing all steps:
        *   The Concierge updates the overall progress bar (`Plan execution finished.`).
        *   It adds a final completion message to the chat. (The final result from the last step might be implicitly shown via the last assistant's chat update, or the Concierge could explicitly display `currentContextData` if needed).
        *   It marks itself as complete.
9.  **System Assistant Task Execution (`AssistantClass.js` - Target Assistant):**
    *   Receives the `stepPayload`. Extracts task query, context, and potentially original request details.
    *   **If `ChromaDB Admin`:** Calls `/api/query` (backend infers count intent or performs retrieval based on the query). <!-- Clarified role -->
    *   Other assistants (`Internet Searcher`, `File Manager`, `Code Interpreter`) use the `taskQuery` from the step payload to perform their actions via respective API calls.
10. **Response Handling & Return (`AssistantClass.js` - Target Assistant):**
    *   The assistant receives the backend response.
    *   It processes the response based on its type (answer, search results, file list, file content, code output).
    *   It adds an appropriate message to the chat.
    *   It updates its progress and marks itself complete.
    *   It returns its processed result (`taskResult`) back to the calling Concierge.

## Backend Workflow (`app.py` - `/api/query`)

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `query`, optional `task_instruction`, and **optional `external_context` (list of strings)**.
2.  **Count Intent Check:** (Skipped if `external_context` or `task_instruction` is present).
3.  **Context Selection:**
    *   **If `external_context` is provided:** Use it directly (`source_type="external"`).
    *   **Else:** Perform ChromaDB retrieval and potentially internet search fallback (`source_type="documents"` or `"internet"` or `"none"`).
4.  **Prompt Formatting:** Call `gemini.prompts.format_rag_prompt` with query, selected context, `source_type`, and `task_instruction`.
5.  **LLM Generation:** Call `gemini.client.GeminiAPI.generate_response`.
6.  **Response Processing:** Parse LLM response, append source info (including `"(Source: Provided Context)"` if applicable).
7.  **Return Response:** Return `jsonify({'answer': final_answer})`.

## Backend Workflow (`app.py` - `/api/generate_plan`)

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `query`.
2.  **Load API Spec:** Attempts to load and parse `backend/gemini/documents/geminiAiApi.json`. Extracts a summary of the Gemini API's capabilities.
3.  **Prepare Planning Prompt:** Constructs a detailed instruction for the LLM.
    *   It lists the available assistant types:
        *   `Internet Searcher`: Searches the web.
        *   `File Manager`: Reads/lists files in persistent storage.
        *   **`ChromaDB Admin`**: Interacts with the local vector store (`./chroma_db`) via the backend to count items or retrieve relevant document chunks based on a query. <!-- Updated description -->
        *   `Gemini API Admin`: Handles LLM tasks using loaded API capabilities.
        *   `Code Interpreter`: Executes Python code (INSECURE).
    *   It instructs the LLM to assign tasks appropriately.
4.  **LLM Call:** Calls `gemini.generate_response` with the planning instruction.
5.  **Validate Plan:** Performs a basic check on the LLM response.
6.  **Return Response:** Returns `jsonify({'plan': plan_text})` or `jsonify({'error': error_message})`.

## Backend Workflow (`app.py` - `/api/search`)

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `query` and optional `num_results`.
2.  **Call Search Function:** Calls `processing.perform_internet_search(query, num_results)`.
3.  **Return Response:** Returns `jsonify({'results': list_of_strings})` on success or `jsonify({'error': error_message})` on failure.

## Backend Workflow (`app.py` - `/api/file_operation`) **[NEW]**

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `operation` ('list' or 'read') and optional `filename` (required for 'read').
2.  **Perform Operation:**
    *   **If 'list':** Reads filenames from `PERSISTENT_DOCUMENTS_DIR`.
    *   **If 'read':** Reads the content (up to 10k chars) of the specified `filename` from `PERSISTENT_DOCUMENTS_DIR` after validation.
3.  **Return Response:** Returns `jsonify({'files': [...]})` for list, `jsonify({'filename': ..., 'content': ...})` for read, or `jsonify({'error': ...})` on failure.

## Backend Workflow (`app.py` - `/api/execute_code`) **[NEW & DANGEROUS]**

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `code` snippet.
2.  **Execute Code:** Uses Python's `exec()` function to run the provided `code_snippet`. **WARNING: THIS IS HIGHLY INSECURE.**
3.  **Capture Output:** Redirects and captures `stdout` and `stderr` during execution.
4.  **Return Response:** Returns `jsonify({'stdout': ..., 'stderr': ..., 'message': ..., 'error'?: ...})`.

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