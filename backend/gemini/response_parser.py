import logging

def parse_gemini_response(response) -> str:
    """Extracts the text response from the Gemini API result."""
    try:
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
        logging.error(f"Error parsing Gemini response: {e}")
        return "Error parsing response."
