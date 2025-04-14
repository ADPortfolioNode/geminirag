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

By following these instructions, you should be able to set up and run the Gemini RAG project successfully. For further assistance, refer to the project documentation or contact the development team.