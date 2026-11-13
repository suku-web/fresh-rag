
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adaptive_engine.engine import make_decision
from adaptive_engine.quality import evaluate_quality
from adaptive_engine.cost import calculate_cost


DATA_DIR = PROJECT_ROOT / "data"

FINANCE_DOCUMENTS = [
    "loan_policy.txt",
    "interest_rates.txt",
    "kyc_rules.txt",
    "credit_card_terms.txt",
]


def load_document(file_path: Path) -> str:
    """Load a finance document from the data folder."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    return file_path.read_text(encoding="utf-8")


def search_document(document_text: str, query: str) -> list:
    """
    Retrieve relevant lines from a document.

    KYC questions receive special handling so that
    identity, address and PAN requirements are retrieved.
    """

    query_lower = query.lower()

    # -------------------------------------------------
    # Special retrieval for KYC document questions
    # -------------------------------------------------

    if "kyc" in query_lower and any(
        word in query_lower
        for word in [
            "document",
            "documents",
            "need",
            "needed",
            "required"
        ]
    ):

        keywords = [
            "accepted identity document",
            "valid address information",
            "tax identification document",
            "documents must be valid",
            "address document",
            "identity verification",
            "address verification",
            "pan verification",
        ]

        lines = [
            line.strip()
            for line in document_text.splitlines()
            if line.strip()
        ]

        results = []

        for keyword in keywords:
            for line in lines:
                if keyword in line.lower() and line not in results:
                    results.append(line)

        return results[:8]

    # -------------------------------------------------
    # General keyword retrieval
    # -------------------------------------------------

    stop_words = {
        "what", "which", "is", "the", "a", "an",
        "for", "of", "in", "on", "to", "and",
        "are", "was", "were", "do", "does", "how",
        "much", "me", "tell", "about", "please",
        "needed", "need", "required"
    }

    query_words = {
        word.strip("?!.,:;()-").lower()
        for word in query.split()
    }

    query_words = {
        word
        for word in query_words
        if len(word) > 2 and word not in stop_words
    }

    if not query_words:
        return []

    scored_lines = []

    for index, line in enumerate(
        document_text.splitlines()
    ):

        line = line.strip()

        if not line:
            continue

        line_words = {
            word.strip("?!.,:;()-").lower()
            for word in line.split()
        }

        matched_words = query_words.intersection(
            line_words
        )

        if matched_words:
            score = (
                len(matched_words)
                / len(query_words)
            )

            scored_lines.append(
                (score, index, line)
            )

    # Highest-scoring lines first
    scored_lines.sort(
        key=lambda item: (-item[0], item[1])
    )

    # Return the best 8 lines
    return [
        line
        for score, index, line in scored_lines[:8]
    ]


def calculate_relevance(
    retrieved_text: str,
    query: str
) -> float:
    """
    Calculate keyword overlap between the
    retrieved information and the user query.
    """

    stop_words = {
        "what", "which", "is", "the", "a", "an",
        "for", "of", "in", "on", "to", "and",
        "are", "was", "were", "do", "does", "how",
        "much", "me", "tell", "about", "please",
        "needed", "need", "required"
    }

    query_words = {
        word.strip("?!.,:;()-").lower()
        for word in query.split()
    }

    query_words = {
        word
        for word in query_words
        if len(word) > 2 and word not in stop_words
    }

    if not query_words:
        return 0.0

    retrieved_words = {
        word.strip("?!.,:;()-").lower()
        for word in retrieved_text.split()
    }

    matched_words = query_words.intersection(
        retrieved_words
    )

    return round(
        len(matched_words) / len(query_words),
        2
    )


def calculate_confidence(
    relevance_score: float,
    retrieved_lines: list
) -> float:
    """
    Calculate confidence using relevance and
    amount of retrieved information.
    """

    if not retrieved_lines:
        return 0.0

    information_score = min(
        len(retrieved_lines) / 5,
        1.0
    )

    confidence = (
        relevance_score + information_score
    ) / 2

    return round(confidence, 2)


def main():
    """Run the complete FRESH-RAG pipeline."""

    print("FRESH-RAG Finance Assistant")
    print("---------------------------")

    # -------------------------------------------------
    # 1. Get user query
    # -------------------------------------------------

    query = input(
        "Enter your question: "
    ).strip()

    if not query:
        print("Please enter a question.")
        return

    # -------------------------------------------------
    # 2. Search all finance documents
    # -------------------------------------------------

    document_results = []

    for filename in FINANCE_DOCUMENTS:

        file_path = DATA_DIR / filename

        if not file_path.exists():
            print(
                f"Warning: {filename} not found; skipping."
            )
            continue

        document_text = load_document(
            file_path
        )

        retrieved_lines = search_document(
            document_text,
            query
        )

        if retrieved_lines:

            retrieved_text = "\n".join(
                retrieved_lines
            )

            relevance = calculate_relevance(
                retrieved_text,
                query
            )

            document_results.append({
                "filename": filename,
                "lines": retrieved_lines,
                "relevance": relevance,
            })

    # -------------------------------------------------
    # 3. No information found
    # -------------------------------------------------

    if not document_results:

        print(
            "\nNo matching information found "
            "in the finance documents."
        )

        print(
            "Adaptive Decision: ABSTAIN"
        )

        return

    # -------------------------------------------------
    # 4. Select best document
    # -------------------------------------------------

    best_result = max(
        document_results,
        key=lambda item: item["relevance"]
    )

    retrieved_lines = best_result["lines"]

    result = "\n".join(
        retrieved_lines
    )

    relevance_score = (
        best_result["relevance"]
    )

    # -------------------------------------------------
    # 5. Calculate confidence
    # -------------------------------------------------

    confidence_score = calculate_confidence(
        relevance_score,
        retrieved_lines
    )

    # -------------------------------------------------
    # 6. Evaluate quality
    # -------------------------------------------------

    quality_score, quality = evaluate_quality(
        relevance_score,
        confidence_score
    )

    # -------------------------------------------------
    # 7. Estimate cost
    # -------------------------------------------------

    # Temporary rates.
    # Actual Bedrock token billing will be
    # connected later.

    input_tokens = len(
        query.split()
    )

    output_tokens = len(
        result.split()
    )

    input_rate = 0.01
    output_rate = 0.02

    cost = calculate_cost(
        input_tokens,
        output_tokens,
        input_rate,
        output_rate
    )

    # -------------------------------------------------
    # 8. Adaptive decision
    # -------------------------------------------------

    decision = make_decision(
        relevance_score,
        confidence_score,
        cost
    )

    # -------------------------------------------------
    # 9. Display complete pipeline
    # -------------------------------------------------

    print("\nQuery:", query)

    print(
        "Documents searched:",
        len(FINANCE_DOCUMENTS)
    )

    print(
        "Best matching document:",
        best_result["filename"]
    )

    print("\nRetrieved Information:")
    print(result)

    print(
        "\nRelevance Score:",
        f"{relevance_score:.0%}"
    )

    print(
        "Confidence Score:",
        f"{confidence_score:.0%}"
    )

    print(
        "Quality Score:",
        f"{quality_score:.0%}"
    )

    print(
        "Quality Level:",
        quality
    )

    print(
        "Estimated Cost:",
        f"{cost:.4f}"
    )

    print(
        "Adaptive Decision:",
        decision
    )


if __name__ == "__main__":
    main()
