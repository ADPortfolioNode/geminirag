import google.generativeai as genai
import logging
from .prompts import format_rag_prompt
from .response_parser import parse_gemini_response

# Define preferred models in order of preference
PREFERRED_MODELS = [
    "models/gemini-1.5-pro-latest",
    "models/gemini-1.5-flash-latest",
    "models/gemini-pro", # Keep as a fallback, though it might be deprecated
]

class GeminiAPI:
    def __init__(self, api_key): # Removed desired_model_prefix, using PREFERRED_MODELS
        """
        Initializes the Gemini API client by finding a suitable model from a preferred list
        that supports 'generateContent'.
        """
        self.model = None
        try:
            genai.configure(api_key=api_key)
            logging.info("Gemini API configured. Listing available models...")

            available_models_map = {m.name: m for m in genai.list_models()}
            selected_model_name = None

            # Iterate through preferred models and check availability and support
            for preferred_name in PREFERRED_MODELS:
                if preferred_name in available_models_map:
                    model_info = available_models_map[preferred_name]
                    if 'generateContent' in model_info.supported_generation_methods:
                        selected_model_name = preferred_name
                        logging.info(f"Found suitable preferred model supporting 'generateContent': {selected_model_name}")
                        break # Use the first suitable preferred model found

            # Fallback: If no preferred model found, search any gemini model (like before)
            if not selected_model_name:
                logging.warning(f"No preferred models ({', '.join(PREFERRED_MODELS)}) found or suitable. Searching other available models.")
                for model_name, model_info in available_models_map.items():
                     # Check if it's a 'gemini' model (excluding vision, etc. if needed) and supports generateContent
                     model_identifier = model_name.split('/')[-1]
                     if model_identifier.startswith('gemini') and 'generateContent' in model_info.supported_generation_methods:
                          # Avoid explicitly selecting known deprecated ones if possible, unless it's the only option
                          # This part might need refinement based on exact deprecation patterns
                          if "gemini-pro-vision" not in model_identifier: # Example exclusion
                               selected_model_name = model_name
                               logging.info(f"Found fallback suitable model supporting 'generateContent': {selected_model_name}")
                               break

            if selected_model_name:
                self.model = genai.GenerativeModel(selected_model_name)
                logging.info(f"GeminiAPI initialized with model: {selected_model_name}")
            else:
                logging.error("No suitable model found supporting 'generateContent' after checking preferred and fallback options.")
                raise ValueError("Could not find any suitable Gemini model supporting 'generateContent'.")

        except Exception as e:
            logging.error(f"Failed to configure or find model for Gemini API: {e}", exc_info=True)
            raise

    def generate_response(self, query, documents, source_type="documents", task_instruction=None):
        """Generates a response using the Gemini model based on the query, context, source, and specific task instruction."""
        if not self.model:
             logging.error("Gemini model not initialized.")
             return "Error: Gemini model not available."
        try:
            # Pass task_instruction to format_rag_prompt
            prompt = format_rag_prompt(query, documents, source_type=source_type, task_instruction=task_instruction)
            logging.info(f"Generated prompt for Gemini (source: {source_type}, task: {'Custom' if task_instruction else 'Default Answer'})")
            # *** Uncomment for detailed debugging ***
            # logging.debug(f"Full Prompt:\n{prompt}")

            response = self.model.generate_content(prompt)
            parsed_response = parse_gemini_response(response)

            # Optionally append source information to the final answer string
            source_suffix = ""
            if source_type == "documents" and documents:
                source_suffix = "\n\n(Source: Internal Documents)"
            elif source_type == "internet" and documents:
                source_suffix = "\n\n(Source: Internet Search)"
            elif source_type == "none":
                 source_suffix = "\n\n(Source: General Knowledge - No specific documents found)"

            return f"{parsed_response}{source_suffix}"

        except Exception as e:
            logging.error(f"Error generating response from Gemini API: {e}", exc_info=True)
            return f"Error generating response: {e}"

# Example usage (optional, for testing)
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv(dotenv_path='../.env') # Adjust path if running from gemini directory
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
