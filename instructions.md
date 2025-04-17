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
4.  **Concierge Planning (`AssistantClass.js` - Concierge):**
    *   The Concierge's `performTask` updates progress (`Analyzing query...`).
    *   It makes a `POST` request to the backend `/api/generate_plan` endpoint, sending the user's query.
    *   It updates progress while waiting (`Requesting plan...`, `Waiting for plan...`).
5.  **Plan Presentation & Parsing (`AssistantClass.js` - Concierge):**
    *   Upon receiving a successful response (`{ "plan": "..." }`) from `/api/generate_plan`:
        *   The Concierge calls the `updateChat` callback to display the generated plan steps to the user.
        *   It parses the plan text into a structured list of steps (task description, assistant name).
        *   If parsing fails, it informs the user and stops.
6.  **Plan Execution (`AssistantClass.js` - Concierge):**
    *   The Concierge initializes an empty variable (`currentContextData`) to hold results passed between steps.
    *   It iterates through the parsed steps.
    *   For each step:
        *   It updates the overall progress bar indicating the current step.
        *   It retrieves the target assistant instance using `getAssistant`.
        *   It prepares a payload for the target assistant, including the task description (as `query`) and the **current value of `currentContextData` (results from the previous step)**.
        *   It calls the target assistant's `performTask` method with the payload and callbacks.
        *   It **waits for the step to complete and captures the result returned by the assistant's `performTask` method into `currentContextData`**, overwriting the previous context.
        *   If a step fails (indicated by the assistant's state or a thrown error), the execution loop stops, and an error is reported.
7.  **Execution Completion (`AssistantClass.js` - Concierge):**
    *   After successfully executing all steps:
        *   The Concierge updates the overall progress bar (`Plan execution finished.`).
        *   It adds a final completion message to the chat. (The final result from the last step might be implicitly shown via the last assistant's chat update, or the Concierge could explicitly display `currentContextData` if needed).
        *   It marks itself as complete.
8.  **System Assistant Task Execution (`AssistantClass.js` - Target Assistant):**
    *   The target assistant receives the payload, potentially including `contextData` (results from the previous step).
    *   **If `Gemini API Admin`:** It includes the `contextData` as `external_context` in its request to `/api/query`.
    *   **If `Internet Searcher`:** It calls `/api/search`. `contextData` might be ignored or used to refine the search query if implemented.
    *   **If `ChromaDB Admin`:** It calls `/api/query` (for count). `contextData` is likely ignored.
    *   It performs its fetch request.
9.  **Response Handling & Return (`AssistantClass.js` - Target Assistant):**
    *   The assistant receives the backend response.
    *   It processes the response (`answer` or `results`).
    *   It adds an appropriate message to the chat (e.g., final answer, summary, or confirmation of search completion like "Results passed to next step").
    *   It updates its progress and marks itself complete.
    *   **It returns its processed result (`taskResult`)** (e.g., the answer string, the list of search results) back to the calling Concierge, allowing it to be captured in `currentContextData`.

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
2.  **Prepare Planning Prompt:** Constructs a detailed instruction for the LLM, asking it to break down the user's `query` into steps and suggest an appropriate assistant type (from a predefined list, including "Internet Searcher") for each step.
3.  **LLM Call:** Calls `gemini.generate_response` with the planning instruction (no document context needed).
4.  **Validate Plan:** Performs a basic check on the LLM response.
5.  **Return Response:** Returns `jsonify({'plan': plan_text})` or `jsonify({'error': error_message})`.

## Backend Workflow (`app.py` - `/api/search`)

1.  **Request Received:** Flask endpoint receives `POST` request with JSON body containing `query` and optional `num_results`.
2.  **Call Search Function:** Calls `processing.perform_internet_search(query, num_results)`.
3.  **Return Response:** Returns `jsonify({'results': list_of_strings})` on success or `jsonify({'error': error_message})` on failure.

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