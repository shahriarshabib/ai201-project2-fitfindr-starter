"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.

    Uses regex — documented in planning.md under Planning Loop.
    """
    working = query.strip()
    max_price = None
    size = None

    price_match = re.search(
        r"(?:under|below|max|less than)\s+\$?\s*(\d+(?:\.\d+)?)",
        working,
        re.IGNORECASE,
    )
    if price_match:
        max_price = float(price_match.group(1))
        working = working[: price_match.start()] + working[price_match.end() :]

    dollar_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", working)
    if dollar_match and max_price is None:
        max_price = float(dollar_match.group(1))
        working = working[: dollar_match.start()] + working[dollar_match.end() :]

    size_match = re.search(
        r"(?:size|sz)\s*[:.]?\s*([A-Za-z0-9/\.\s]+?)(?:\s*,|\s+under|\s+in|\s*$)",
        working,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1).strip()
        working = working[: size_match.start()] + working[size_match.end() :]
    else:
        standalone_size = re.search(
            r"\b(in\s+)?size\s+(XS|S|M|L|XL|XXS|XXL|\d+)\b",
            working,
            re.IGNORECASE,
        )
        if standalone_size:
            size = standalone_size.group(2).strip()
            working = working[: standalone_size.start()] + working[standalone_size.end() :]

    description = re.sub(
        r"\b(i('m| am)? looking for|find me|show me|what('s| is) out there)\b",
        "",
        working,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"\s+", " ", description).strip(" .,!?")
    description = re.sub(
        r"\.\s*(i mostly wear|how would i style|what's out there).*$",
        "",
        description,
        flags=re.IGNORECASE,
    ).strip(" .,!?")

    if not description:
        description = query.strip()

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    parsed = parse_query(query)
    session["parsed"] = parsed

    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        size_label = parsed["size"] or "any"
        price_label = (
            f"${parsed['max_price']:.0f}"
            if parsed["max_price"] is not None
            else "no limit"
        )
        session["error"] = (
            f"No listings found for '{parsed['description']}' "
            f"(size: {size_label}, max price: {price_label}). "
            "Try removing the size or price filter, or use broader keywords "
            "like 'graphic tee' instead of a very specific phrase."
        )
        return session

    session["selected_item"] = results[0]

    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )

    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    return session


def format_listing(item: dict) -> str:
    """Format a listing dict into readable text for the UI."""
    brand = item.get("brand") or "Unknown brand"
    colors = ", ".join(item.get("colors", []))
    tags = ", ".join(item.get("style_tags", []))
    return (
        f"{item['title']}\n"
        f"${item['price']:.2f} · {item['platform'].title()} · {item['condition'].title()} condition\n"
        f"Size: {item['size']} · Category: {item['category']}\n"
        f"Brand: {brand}\n"
        f"Colors: {colors}\n"
        f"Tags: {tags}\n\n"
        f"{item['description']}"
    )


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
