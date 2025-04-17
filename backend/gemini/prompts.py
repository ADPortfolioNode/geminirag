def format_rag_prompt(query: str, documents: list[str], source_type: str = "documents", task_instruction: str = None) -> str:
    """
    Formats the prompt for RAG, allowing for specific task instructions.

    Args:
        query: The user's original query or topic.
        documents: A list of context strings (from ChromaDB or Internet).
        source_type: A string indicating the source ('documents', 'internet', 'none').
        task_instruction: Specific instruction for the LLM (e.g., "Summarize...", "Answer the question...").

    Returns:
        The formatted prompt string.
    """
    context = "\n".join(documents)

    # Determine the base instruction if none provided
    if not task_instruction:
        # Refined Default Instruction
        task_instruction = f"Answer the following question: {query}"
        # Add context guidance if context exists
        if source_type != "none" and context:
             task_instruction += " Use the provided context to inform your answer."
        # If no context, it remains a general knowledge question

    # Add source information to the instruction
    if source_type == "documents" and context:
        source_description = "using the following documents retrieved from internal storage"
    elif source_type == "internet" and context:
        source_description = "using the following information found on the internet"
    else:
        source_description = "" # No specific source for context

    # Construct the prompt
    if context:
        # Place instruction first, clearly separate context
        prompt = f"Instruction: {task_instruction} {source_description}.\n\nContext:\n---\n{context}\n---\n\nResponse:"
    else:
        prompt = f"Instruction: {task_instruction}.\n\nResponse:"

    return prompt
