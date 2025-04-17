import logging
import requests # Import requests
import json     # Import json

# DuckDuckGo Instant Answer API endpoint (unofficial)
DDG_API_URL = "https://api.duckduckgo.com/"

def perform_internet_search(query: str, num_results: int = 3) -> list[str]:
    """
    Performs an internet search using the DuckDuckGo Instant Answer API.

    Args:
        query: The search query string.
        num_results: The desired number of results (used to limit returned snippets).

    Returns:
        A list of strings representing search result snippets or summaries.
        Returns an empty list if the search fails or yields no results.
    """
    logging.info(f"Performing internet search for: '{query}' using DuckDuckGo API")

    params = {
        "q": query,
        "format": "json",
        "no_html": 1,       # Remove HTML tags from results
        "skip_disambig": 1 # Skip disambiguation pages
    }
    headers = {
        # Some APIs appreciate a User-Agent
        "User-Agent": "gemini-rag-application/1.0"
    }

    results = []
    try:
        response = requests.get(DDG_API_URL, params=params, headers=headers, timeout=5) # Add timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json()

        # Extract relevant information - Structure might vary based on query type
        # Prioritize AbstractText, then RelatedTopics text
        if data.get("AbstractText"):
            results.append(data["AbstractText"])

        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"]:
                # Check for nested topics first (common structure)
                if topic.get("Topics"):
                     for sub_topic in topic["Topics"]:
                         if sub_topic.get("Text") and len(results) < num_results:
                             results.append(sub_topic["Text"])
                # Otherwise, check the top-level topic
                elif topic.get("Text") and len(results) < num_results:
                    results.append(topic["Text"])
                if len(results) >= num_results:
                    break # Stop once we have enough results

        if not results and data.get("Definition"): # Fallback to definition
             results.append(data["Definition"])

        if results:
            logging.info(f"Found {len(results)} results from DuckDuckGo for '{query}'")
        else:
            logging.warning(f"DuckDuckGo search yielded no parseable results for: '{query}'")

        return results[:num_results] # Return up to num_results

    except requests.exceptions.RequestException as e:
        logging.error(f"Internet search failed for '{query}' (Network/HTTP Error): {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response from DuckDuckGo for '{query}': {e}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred during internet search for '{query}': {e}", exc_info=True)
        return []

# Example usage (optional, for testing)
# if __name__ == '__main__':
#     test_queries = ["capital of france", "python web framework", "latest news on mars rover"]
#     for q in test_queries:
#         print(f"\n--- Searching for: {q} ---")
#         search_results = perform_internet_search(q)
#         if search_results:
#             for i, res in enumerate(search_results):
#                 print(f"{i+1}. {res}")
#         else:
#             print("No results found.")

