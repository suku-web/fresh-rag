# FRESH-RAG - Quality Evaluation
# Member 1: Quality Component

def evaluate_quality(relevance_score, confidence_score):
    """
    Evaluate the quality of a response using relevance and confidence.
    """

    if relevance_score < 0 or relevance_score > 1:
        raise ValueError("Relevance score must be between 0 and 1")

    if confidence_score < 0 or confidence_score > 1:
        raise ValueError("Confidence score must be between 0 and 1")

    quality_score = (relevance_score + confidence_score) / 2

    if quality_score >= 0.8:
        quality = "HIGH"
    elif quality_score >= 0.5:
        quality = "MEDIUM"
    else:
        quality = "LOW"

    return quality_score, quality


if __name__ == "__main__":
    score, quality = evaluate_quality(0.85, 0.90)

    print("FRESH-RAG Quality Evaluation")
    print("----------------------------")
    print("Quality Score:", round(score, 2))
    print("Quality Level:", quality)