# FRESH-RAG - Adaptive Decision Engine
# Member 1: Decision Engine

def make_decision(relevance_score, confidence_score, cost):
    """
    Decide whether to refresh knowledge, answer, or abstain.
    """

    if relevance_score < 0.4 or confidence_score < 0.5:
        return "ABSTAIN"

    elif cost > 0.10:
        return "ANSWER_WITHOUT_REFRESH"

    else:
        return "ANSWER"


def main():
    relevance_score = 0.85
    confidence_score = 0.90
    cost = 0.02

    decision = make_decision(
        relevance_score,
        confidence_score,
        cost
    )

    print("FRESH-RAG Decision Engine")
    print("-------------------------")
    print("Relevance Score:", relevance_score)
    print("Confidence Score:", confidence_score)
    print("Cost:", cost)
    print("Decision:", decision)


if __name__ == "__main__":
    main()