def format_rag_prompt(query: str, documents: list[str], source_type: str = "documents", task_instruction: str = None) -> str:
    """
    Formats the prompt for RAG, allowing for specific task instructions and handling different context sources.

    Args:
        query: The user's original query or topic for the current step.
        documents: A list of context strings (from ChromaDB, Internet, or External).
        source_type: A string indicating the source ('documents', 'internet', 'external', 'none').
        task_instruction: Specific instruction for the LLM (e.g., "Summarize...", "Answer the question...").

    Returns:
        The formatted prompt string.
    """
    context = "\n".join(documents)

    # Determine the base instruction if none provided
    if not task_instruction:
        task_instruction = f"Answer the following question: {query}"
        if source_type != "none" and context:
             task_instruction += " Use the provided context to inform your answer."

    # Add source information to the instruction
    if source_type == "documents" and context:
        source_description = "using the following documents retrieved from internal storage"
    elif source_type == "internet" and context:
        source_description = "using the following information found on the internet"
    elif source_type == "external" and context: # Handle external context source
        source_description = "using the following provided context"
    else:
        source_description = ""

    # Construct the prompt
    if context:
        prompt = f"Instruction: {task_instruction} {source_description}.\n\nContext:\n---\n{context}\n---\n\nResponse:"
    else:
        prompt = f"Instruction: {task_instruction}.\n\nResponse:"

    return prompt
