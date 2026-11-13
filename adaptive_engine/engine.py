
# FRESH-RAG - Adaptive Decision Engine
# Member 1: Decision Engine

def make_decision(relevance_score, confidence_score, cost):
    """
    Decide whether to answer, answer without refresh, or abstain.
    """

    if relevance_score < 0.4 or confidence_score < 0.5:
        return "ABSTAIN"

    elif cost > 0.10:
        return "ANSWER_WITHOUT_REFRESH"

    else:
        return "ANSWER"


def run_test(test_number, relevance_score, confidence_score, cost):
    decision = make_decision(
        relevance_score,
        confidence_score,
        cost
    )

    print(f"\nTEST {test_number}")
    print("-------------------------")
    print(f"Relevance Score   : {relevance_score:.2f} ({relevance_score * 100:.0f}%)")
    print(f"Confidence Score  : {confidence_score:.2f} ({confidence_score * 100:.0f}%)")
    print(f"Estimated Cost    : {cost:.4f}")
    print(f"Decision          : {decision}")


def main():

    print("FRESH-RAG Adaptive Decision Engine")
    print("===================================")

    # Test 1: Good relevance + high confidence + low cost
    run_test(
        1,
        relevance_score=0.85,
        confidence_score=0.90,
        cost=0.02
    )

    # Test 2: Low relevance
    run_test(
        2,
        relevance_score=0.30,
        confidence_score=0.90,
        cost=0.02
    )

    # Test 3: Low confidence
    run_test(
        3,
        relevance_score=0.85,
        confidence_score=0.40,
        cost=0.02
    )

    # Test 4: High cost
    run_test(
        4,
        relevance_score=0.85,
        confidence_score=0.90,
        cost=0.15
    )


if __name__ == "__main__":
    main()
