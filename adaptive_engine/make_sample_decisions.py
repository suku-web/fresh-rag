# FRESH-RAG - Sample Decision Generator

from engine import make_decision


def main():
    samples = [
        (0.90, 0.95, 0.02),
        (0.60, 0.70, 0.05),
        (0.20, 0.30, 0.01),
        (0.85, 0.90, 0.20),
    ]

    print("FRESH-RAG Sample Decisions")
    print("--------------------------")

    for relevance, confidence, cost in samples:
        decision = make_decision(relevance, confidence, cost)

        print(
            f"Relevance: {relevance}, "
            f"Confidence: {confidence}, "
            f"Cost: {cost} -> {decision}"
        )


if __name__ == "__main__":
    main()