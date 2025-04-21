# Instructions for Running the Gemini RAG Project (FINAL BASE)

This document provides step-by-step instructions for setting up, running, and testing the Gemini Retrieval-Augmented Generation (RAG) project.

---

## Prerequisites

1.  **Operating System:** Windows (tested on Windows 10/11).
2.  **Software Requirements:**
    *   Python 3.8+
    *   Node.js (for the frontend)
    *   `venv` (Python virtual environment)
    *   `sentence-transformers` (Python package for relevance scoring)
3.  **API Keys:**
    *   Google Gemini API Key.
    *   Create a `.env` file in the `backend` directory with:

        ```properties
        GOOGLE_API_KEY=your_gemini_api_key
        ```

4.  **Vector Database:**
    *   ChromaDB with `PersistentClient`.
    *   Vector data stored locally in `./chroma_db` within the `backend`.

---

## Backend Setup

1.  **Navigate to Backend:**

    ```bash
    cd e:\2024 RESET\geminirag\backend
    ```

2.  **Create Virtual Environment:**

    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Backend:**

    ```bash
    python app.py
    ```

    *   Server starts on `http://localhost:5000`.

---

## Frontend Setup

1.  **Navigate to Frontend:**

    ```bash
    cd e:\2024 RESET\geminirag\frontend
    ```

2.  **Install Dependencies:**

    ```bash
    npm install
    ```

3.  **Start Frontend:**

    ```bash
    npm start
    ```

    *   App opens in browser at `http://localhost:3000`.

---

## Testing

1.  **Upload Documents:** Use the file upload in the frontend (`.txt`, `.pdf`, `.docx`, `.csv`).
2.  **Query the Assistant:** Enter a query and submit. The Concierge Assistant will respond.
    *   For general conversation, just type a greeting or question.
    *   For specific tasks, start with "Can you..." or include "please".

---

## Key Components

*   **`App.js` (Frontend):** Main React component, manages state, handles user input, and orchestrates tasks.
*   **`AssistantClass.js` (Frontend):** Defines the `Assistant` class, including the Concierge Assistant's planning and execution logic.
*   **`app.py` (Backend):** Flask server, handles API requests, interacts with ChromaDB and Gemini API.
*   **`processing.py` (Backend):** Contains document processing and internet search functions.
*   **`gemini/client.py` (Backend):** Handles communication with the Gemini API.

---

## Workflow

1.  **User Input:** User enters a query in the frontend.
2.  **Concierge Analysis:** `App.js` sends the query to the Concierge Assistant.
3.  **Plan Generation (if needed):** The Concierge sends the query to `/api/generate_plan` (backend).
4.  **Plan Execution:** The Concierge executes the plan step-by-step, delegating tasks to other assistants via `/api/execute_assistant_task` (backend).
5.  **Backend Processing:** The backend routes tasks to the appropriate logic (ChromaDB, Gemini API, etc.).
6.  **Response Synthesis:** The backend returns the results to the Concierge.
7.  **Display:** The Concierge displays the final response in the chat window.

---

## Important Notes

*   This is the **FINAL BASE** RAG build. All future projects will be based on this foundation.
*   Ensure the backend and frontend servers are running concurrently.
*   Check the browser console and backend terminal for any error messages.
*   The Concierge Assistant handles both general conversation and task requests.
*   The `sentence-transformers` library is used for relevance scoring (backend).
*   The system uses a local ChromaDB instance (data stored in `./chroma_db`).