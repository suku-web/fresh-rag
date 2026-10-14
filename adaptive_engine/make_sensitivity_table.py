# FRESH-RAG - Sensitivity Table Generator

from engine import make_decision


def main():
    relevance_scores = [0.3, 0.5, 0.8, 0.9]
    confidence_score = 0.9
    cost = 0.02

    print("FRESH-RAG Sensitivity Table")
    print("-" * 65)
    print(f"{'Relevance':<15}{'Confidence':<15}{'Cost':<15}{'Decision'}")
    print("-" * 65)

    for relevance in relevance_scores:
        decision = make_decision(
            relevance,
            confidence_score,
            cost
        )

        print(
            f"{relevance:<15}{confidence_score:<15}"
            f"{cost:<15}{decision}"
        )


if __name__ == "__main__":
    main()