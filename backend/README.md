# Chat with your documents

This folder contains a (very) minimal, self-contained example of how to make an application to chat with your documents, using Chroma and Google Gemini's API.
It uses the 2022 and 2023 U.S state of the union addresses as example documents.

## How it works

The basic flow is as follows:

0. The text documents in the `documents` folder are loaded line by line, then embedded and stored in a Chroma collection.

1. When the user submits a question, it gets embedded using the same model as the documents, and the lines most relevant to the query are retrieved by Chroma.
2. The user-submitted question is passed to Google Gemini's API, along with the extra context retrieved by Chroma. The Google Gemini API generates a response.
3. The response is displayed to the user, along with the lines used as extra context.

## Running the example

You will need an Google API key to run this demo.

Install dependencies and run the example:

```bash
# Install dependencies
pip install -r requirements.txt

# Load the example documents into Chroma
python load_data.py

# Run the chatbot
python main.py
```

Example output:

```
Query: What was said about the pandemic?

Thinking...

Based on the given context, several points were made about the pandemic. First, it is described as punishing, indicating the severity and impact it had on various aspects of life. It is mentioned that schools were closed and everything was being shut down in response to the COVID crisis, suggesting the significant measures taken to combat the virus.

The context then shifts to discussing the progress made in the fight against the pandemic itself. While no specific details are provided, it is implied that there has been progress, though the extent of it is unclear.

Additionally, it is stated that children were already facing struggles before the pandemic, such as bullying, violence, trauma, and the negative effects of social media. This suggests that these issues were likely exacerbated by the pandemic.

The context then mentions a spike in violent crime in 2020, which is attributed to the first year of the pandemic. This implies that there was an increase in violent crime during that time period, but the underlying causes or specific details are not provided.

Lastly, it is mentioned that the pandemic also disrupted global supply chains. Again, no specific details are given, but this suggests that the pandemic had negative effects on the movement and availability of goods and resources at a global level.

In conclusion, based on the provided context, it is stated that the pandemic has been punishing and has resulted in the closure of schools and the shutdown of various activities. Progress is mentioned in fighting against the pandemic, though the specifics are not given. The pandemic is also said to have worsened pre-existing issues such as bullying and violence among children, and disrupted global supply chains.
```

You can replace the example text documents in the `documents` folder with your own documents, and the chatbot will use those instead.

## New Functionality: File Upload Integration with ChromaDB

### Overview
The application now supports uploading files via the frontend, which are processed and stored in ChromaDB for Retrieval Augmented Generation (RAG) operations. This allows users to upload their own documents and use them as context for AI-generated responses.

### How It Works
1. **Frontend File Upload:**
   - Users can upload files through the `FileUpload` component in the React frontend.
   - The files are sent to the backend via the `/api/upload` endpoint.

2. **Backend File Processing:**
   - The backend saves the uploaded files to the `uploads/` directory.
   - The files are processed using LangChain's `DirectoryLoader` and `CharacterTextSplitter`.
   - The processed content is added to ChromaDB for future queries.

3. **RAG Operations:**
   - When a user submits a query, the application retrieves relevant context from ChromaDB, combines it with the query, and sends it to the AI model for response generation.

### Steps to Use
1. **Upload Files:**
   - Navigate to the file upload section in the frontend.
   - Select a file and click "Upload."
   - A success message will appear once the file is processed and stored in ChromaDB.

2. **Query the AI:**
   - Use the chat interface to ask questions related to the uploaded documents.
   - The AI will use the uploaded content as context to generate responses.

### Example Workflow
1. Upload a document (e.g., `state_of_the_union_2023.txt`).
2. Ask a question like, "What was said about the economy in 2023?"
3. The AI will retrieve relevant lines from the uploaded document and generate a response.

### Adding Future Functionalities
To add new functionalities, follow this process:
1. **Define the Feature:** Clearly outline the new functionality and its purpose.
2. **Frontend Integration:**
   - Create a new React component or update an existing one.
   - Ensure the component interacts with the backend via an appropriate API endpoint.
3. **Backend Integration:**
   - Add or update API endpoints in the Flask backend.
   - Implement the necessary logic to process data and interact with ChromaDB or other services.
4. **Update Documentation:**
   - Add a section in this README to describe the new functionality.
   - Include steps for usage and examples.

### Example for Adding a New Feature
If adding a feature like "Multimedia File Support":
1. Update the `FileUpload` component to accept multimedia files.
2. Modify the `/api/upload` endpoint to process multimedia files (e.g., extract text from audio or video).
3. Add the extracted content to ChromaDB.
4. Document the feature in this README.

By following this process, you can ensure consistency and maintainability as new features are added.
