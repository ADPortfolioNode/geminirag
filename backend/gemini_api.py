import google.generativeai as genai
import logging

class GeminiAPI:
    def __init__(self, api_key):
        """Initializes the Gemini API client."""
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro') # Or specify the model you intend to use
            logging.info("Gemini API configured successfully.")
        except Exception as e:
            logging.error(f"Failed to configure Gemini API: {e}")
            raise

    def generate_response(self, query, documents):
        """Generates a response using the Gemini model based on the query and retrieved documents."""
        try:
            # Prepare the context from the retrieved documents
            context = "\n".join(documents)
            prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"

            # Generate content using the Gemini model
            response = self.model.generate_content(prompt)

            # Extract the text response
            # Accessing response.text might vary depending on the exact library version and response structure
            if response and hasattr(response, 'text'):
                 return response.text
            elif response and response.parts:
                 # Handle potential multipart responses if applicable
                 return "".join(part.text for part in response.parts if hasattr(part, 'text'))
            else:
                 logging.warning("Gemini API response structure not as expected or empty.")
                 return "Sorry, I couldn't generate a response based on the provided information."

        except Exception as e:
            logging.error(f"Error generating response from Gemini API: {e}")
            return f"Error generating response: {e}"

# Example usage (optional, for testing)
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        gemini_api = GeminiAPI(api_key=api_key)
        test_query = "What is the capital of France?"
        test_docs = ["France is a country in Europe.", "Paris is its capital city."]
        response = gemini_api.generate_response(test_query, test_docs)
        print(f"Query: {test_query}")
        print(f"Response: {response}")
    else:
        print("GOOGLE_API_KEY not found in environment variables.")