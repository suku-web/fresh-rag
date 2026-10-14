# FRESH-RAG - Cost Calculation
# Member 1: Cost Component

def calculate_cost(input_tokens, output_tokens, input_rate, output_rate):
    """
    Calculate the estimated cost of processing tokens.
    Rates are cost per 1,000 tokens.
    """

    if min(input_tokens, output_tokens, input_rate, output_rate) < 0:
        raise ValueError("Values cannot be negative")

    input_cost = (input_tokens / 1000) * input_rate
    output_cost = (output_tokens / 1000) * output_rate

    return input_cost + output_cost


if __name__ == "__main__":
    cost = calculate_cost(1000, 500, 0.01, 0.02)

    print("FRESH-RAG Cost Calculator")
    print("-------------------------")
    print("Estimated Cost:", round(cost, 4))