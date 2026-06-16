"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase keyword tokens, dropping very short words."""
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 1]


def _score_listing(listing: dict, keywords: list[str]) -> int:
    """Score a listing by keyword overlap (tags weighted 2x, title/description 1x)."""
    if not keywords:
        return 0

    score = 0
    title_tokens = set(_tokenize(listing.get("title", "")))
    desc_tokens = set(_tokenize(listing.get("description", "")))
    tag_tokens = set(_tokenize(" ".join(listing.get("style_tags", []))))

    for keyword in keywords:
        if keyword in title_tokens or keyword in desc_tokens:
            score += 1
        if keyword in tag_tokens:
            score += 2
        # Partial match for compound tags like "graphic" matching "graphic tee"
        for tag in listing.get("style_tags", []):
            if keyword in tag.lower():
                score += 2

    return score


def _size_matches(listing_size: str, requested_size: str) -> bool:
    """Case-insensitive substring match (e.g. 'M' matches 'S/M')."""
    return requested_size.strip().lower() in listing_size.lower()


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.
    """
    listings = load_listings()
    keywords = _tokenize(description)

    filtered: list[tuple[int, dict]] = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and not _size_matches(listing["size"], size):
            continue

        score = _score_listing(listing, keywords)
        if score > 0:
            filtered.append((score, listing))

    filtered.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in filtered]


def _call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Call Groq LLM and return the assistant message content."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def _format_wardrobe_items(wardrobe: dict) -> str:
    """Format wardrobe items into a readable bullet list for the LLM prompt."""
    lines = []
    for item in wardrobe.get("items", []):
        tags = ", ".join(item.get("style_tags", []))
        colors = ", ".join(item.get("colors", []))
        notes = item.get("notes") or ""
        note_text = f" Notes: {notes}" if notes else ""
        lines.append(
            f"- {item['name']} ({item['category']}, {colors}; tags: {tags}){note_text}"
        )
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    """
    item_summary = (
        f"Title: {new_item.get('title', 'Unknown item')}\n"
        f"Description: {new_item.get('description', '')}\n"
        f"Category: {new_item.get('category', '')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}"
    )

    wardrobe_items = wardrobe.get("items", [])
    system_prompt = (
        "You are a personal stylist helping someone style a secondhand find. "
        "Give practical, specific outfit advice in a friendly tone. "
        "Suggest 1–2 complete looks with fit tips (tucking, rolling sleeves, layering)."
    )

    try:
        if not wardrobe_items:
            user_prompt = (
                f"The user has an empty wardrobe and is considering this thrift find:\n\n"
                f"{item_summary}\n\n"
                "Suggest general styling ideas: what categories of items would pair well, "
                "what vibe or era this piece suits, and 1–2 example outfit directions "
                "without referencing specific owned pieces."
            )
        else:
            wardrobe_text = _format_wardrobe_items(wardrobe)
            user_prompt = (
                f"The user is considering buying this thrift find:\n\n"
                f"{item_summary}\n\n"
                f"Their existing wardrobe:\n{wardrobe_text}\n\n"
                "Suggest 1–2 complete outfit combinations using the new item and "
                "specific pieces from their wardrobe by name. Include styling tips."
            )

        return _call_llm(system_prompt, user_prompt, temperature=0.7)
    except Exception as exc:
        tags = ", ".join(new_item.get("style_tags", [])) or "casual"
        return (
            f"Couldn't reach the styling assistant ({exc}). "
            f"Based on the item's {new_item.get('category', 'style')} and "
            f"{tags} vibe, try pairing it with neutral bottoms and shoes "
            f"that match the {', '.join(new_item.get('colors', ['main']))} tones."
        )


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    """
    if not outfit or not outfit.strip():
        return (
            "Cannot create a fit card: no outfit suggestion was provided. "
            "Run suggest_outfit first."
        )

    title = new_item.get("title", "this find")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "a thrift app")

    system_prompt = (
        "You write casual, authentic Instagram/TikTok outfit captions — "
        "not product descriptions. Use lowercase vibes, occasional emoji, "
        "and sound like a real person sharing an OOTD. Keep it to 2–4 sentences."
    )
    user_prompt = (
        f"Item: {title}\n"
        f"Price: ${price}\n"
        f"Platform: {platform}\n"
        f"Outfit styling:\n{outfit}\n\n"
        "Write a shareable fit card caption. Mention the item name, price, "
        "and platform naturally once each."
    )

    try:
        return _call_llm(system_prompt, user_prompt, temperature=0.9)
    except Exception as exc:
        return (
            f"scored {title.lower()} on {platform} for ${price} and honestly "
            f"it's the move 🖤 {outfit[:120]}..."
            f" (caption helper unavailable: {exc})"
        )
