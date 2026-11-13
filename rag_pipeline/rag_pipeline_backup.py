import sys
from pathlib import Path

# Add project root to Python path so adaptive_engine can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adaptive_engine.engine import make_decision
from adaptive_engine.quality import evaluate_quality
from adaptive_engine.cost import calculate_cost


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


def search_document(document_text: str, query: str) -> list:
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

    return relevant_lines


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

    print("FRESH-RAG Finance Assistant")
    print("---------------------------")

    query = input("Enter your question: ").strip()

    if not query:
        print("Please enter a question.")
        raise SystemExit

    document_path = "data/interest_rates.txt"

    document = load_document(document_path)

    # --------------------------------
    # 3. Retrieve relevant information
    # --------------------------------

    retrieved_lines = search_document(
        document,
        query
    )

    result = "\n".join(retrieved_lines)

    if not result:
        result = "No relevant information found."

    # --------------------------------
    # 4. Calculate relevance
    # --------------------------------

    relevance_score = calculate_relevance(
        document,
        query
    )

    # --------------------------------
    # 5. Calculate confidence
    # --------------------------------

    confidence_score = calculate_confidence(
        relevance_score,
        retrieved_lines
    )

    # --------------------------------
    # 6. MEMBER 1 - Quality
    # --------------------------------

    quality_score, quality = evaluate_quality(
        relevance_score,
        confidence_score
    )

    # --------------------------------
    # 7. MEMBER 1 - Cost
    # --------------------------------
    #
    # Temporary estimated values.
    # Later, actual Bedrock token usage
    # will be connected here.

    input_tokens = len(query.split())
    output_tokens = len(result.split())

    input_rate = 0.01
    output_rate = 0.02

    cost = calculate_cost(
        input_tokens,
        output_tokens,
        input_rate,
        output_rate
    )

    # --------------------------------
    # 8. MEMBER 1 - Adaptive Decision
    # --------------------------------

    decision = make_decision(
        relevance_score,
        confidence_score,
        cost
    )

    # --------------------------------
    # 9. Display complete pipeline
    # --------------------------------

    print("FRESH-RAG Adaptive RAG Pipeline")
    print("--------------------------------")

    print("Query:", query)

    print("\nRetrieved Information:")
    print(result)

    print("\nRelevance Score:", round(relevance_score, 2))
    print("Confidence Score:", round(confidence_score, 2))

    print("\nQuality Score:", round(quality_score, 2))
    print("Quality Level:", quality)

    print("\nEstimated Cost:", round(cost, 4))

    print("\nAdaptive Decision:", decision)