"""
pricing.py — Module for calculating the cost of LLM requests.

Provides functions for calculating total cost based on the model,
number of prompt tokens, and completion tokens used.

Prices are listed in USD per 1 million tokens (1M).
"""

# Štruktúra: "model_name": (cena_prompt_1M, cena_completion_1M)
CENNIK: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5": (1.25, 5.00),
    # Anthropic
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    # Google
    "gemini-3.1-pro": (1.25, 5.00),
    "gemini-3.1-flash": (0.075, 0.30),
    # Fallback/ostatne
    "gtfs-agent": (0.25, 2.00),  # Predpokladany gpt-5-mini v backend
}


def vypocitaj_cenu(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Vypočíta cenu v USD za daný počet tokenov podľa použitého modelu.
    """
    # Vyhľadanie modelu, ignoruj verzie ak niesu presne zhodne, najdi aspon substr
    najdeny_model = None
    if model in CENNIK:
        najdeny_model = model
    else:
        for key in CENNIK:
            if key in model:
                najdeny_model = key
                break

    if not najdeny_model:
        # Default fallback
        najdeny_model = "gpt-4o-mini"

    cena_prompt_1m, cena_completion_1m = CENNIK[najdeny_model]

    cena_prompt = (prompt_tokens / 1_000_000) * cena_prompt_1m
    cena_completion = (completion_tokens / 1_000_000) * cena_completion_1m

    return cena_prompt + cena_completion
