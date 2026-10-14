from pathlib import Path


def load_document(file_path: str) -> str:
    """
    Load a text document from the local filesystem.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    return path.read_text(encoding="utf-8")


def search_document(document_text: str, query: str) -> str:
    """
    Perform simple keyword-based retrieval from a document.

    Returns the relevant lines containing query words.
    """

    query_words = query.lower().split()

    lines = document_text.splitlines()

    relevant_lines = []

    for line in lines:
        line_lower = line.lower()

        if any(word in line_lower for word in query_words):
            relevant_lines.append(line)

    if not relevant_lines:
        return "No relevant information found."

    return "\n".join(relevant_lines)


def calculate_relevance(document_text: str, query: str) -> float:
    """
    Calculate a simple relevance score based on
    how many query words are found in the document.
    """

    query_words = query.lower().split()

    if not query_words:
        return 0.0

    document_lower = document_text.lower()

    matched_words = 0

    for word in query_words:
        if word in document_lower:
            matched_words += 1

    return matched_words / len(query_words)


def calculate_confidence(
    relevance_score: float,
    retrieved_lines: list
) -> float:
    """
    Calculate a simple confidence score based on
    relevance and the amount of retrieved information.
    """

    if not retrieved_lines:
        return 0.0

    information_score = min(len(retrieved_lines) / 5, 1.0)

    confidence = (relevance_score + information_score) / 2

    return round(confidence, 2)


if __name__ == "__main__":

    document_path = "data/sample.txt"

    document = load_document(document_path)

    query = "knowledge refresh"

    result = search_document(
        document,
        query
    )

    relevance_score = calculate_relevance(
        document,
        query
    )

    retrieved_lines = [
        line
        for line in document.splitlines()
        if any(
            word in line.lower()
            for word in query.lower().split()
        )
    ]

    confidence_score = calculate_confidence(
        relevance_score,
        retrieved_lines
    )

    print("FRESH-RAG Retrieval")
    print("-------------------")
    print("Query:", query)

    print("\nRetrieved Information:")
    print(result)

    print("\nRelevance Score:", relevance_score)
    print("Confidence Score:", confidence_score)