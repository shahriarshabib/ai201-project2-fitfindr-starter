"""
FitFindr Demo Walkthrough
Demonstrates the complete agent flow with state passing and error handling

Run with: python demo_walkthrough.py
"""

from agent import run_agent, parse_query, format_listing
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
import json


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_happy_path():
    """Demo 1: Complete multi-step workflow with all 3 tools"""
    print_section("DEMO 1: HAPPY PATH - COMPLETE WORKFLOW")
    
    print("\nNARRATION: Let's walk through a complete FitFindr interaction.")
    print("A user is looking for vintage clothing that matches their style.\n")
    
    query = "I'm looking for a vintage graphic tee under $30"
    wardrobe = get_example_wardrobe()
    
    print(f"USER INPUT: '{query}'")
    print(f"WARDROBE: Example wardrobe (10 items)")
    
    # Step 1: Parse
    print_section("STEP 1: PARSE QUERY (extract search parameters)")
    parsed = parse_query(query)
    print(f"Parsed query:")
    print(f"  - description: '{parsed['description']}'")
    print(f"  - size: {parsed['size']}")
    print(f"  - max_price: ${parsed['max_price']}")
    print("\nNARRATION: The agent uses regex to extract the search parameters.")
    print("It found 'vintage graphic tee', no size constraint, and $30 max price.")
    
    # Step 2: Search
    print_section("STEP 2: SEARCH LISTINGS (find matching items)")
    from tools import search_listings
    results = search_listings(
        description=parsed['description'],
        size=parsed['size'],
        max_price=parsed['max_price']
    )
    print(f"Search returned {len(results)} matching results")
    print(f"Top match selected: '{results[0]['title']}'")
    print(f"  Price: ${results[0]['price']}")
    print(f"  Platform: {results[0]['platform'].title()}")
    print(f"  Size: {results[0]['size']}")
    print(f"  Condition: {results[0]['condition'].title()}")
    
    print("\nNARRATION: The search found multiple listings. The top result by")
    print("relevance score is selected and stored in the session.")
    
    # Step 3: STATE PASSING - Show selected item
    print_section("STATE CHECKPOINT: selected_item in session")
    selected_item = results[0]
    print("session['selected_item'] = {")
    for key in ['id', 'title', 'price', 'platform', 'size', 'category']:
        print(f"    {key!r}: {selected_item[key]!r},")
    print("    ... (other fields)")
    print("}")
    
    print("\nNARRATION: This listing object is now stored in the session dict.")
    print("It will be passed to the next two tools without re-parsing.")
    
    # Step 4: Suggest outfit
    print_section("STEP 3: SUGGEST OUTFIT (style with wardrobe)")
    from tools import suggest_outfit
    outfit_suggestion = suggest_outfit(
        new_item=selected_item,
        wardrobe=wardrobe
    )
    print(f"Generated outfit suggestion ({len(outfit_suggestion)} chars):")
    print(f"\n{outfit_suggestion[:400]}...")
    
    print("\nNARRATION: The agent calls suggest_outfit with:")
    print("  1) The selected_item (from previous step - STATE PASSED)")
    print("  2) The user's wardrobe (10 items like baggy jeans, combat boots, etc.)")
    print("The LLM generates specific styling advice using wardrobe piece names.")
    
    # Step 5: STATE PASSING - Show outfit in session
    print_section("STATE CHECKPOINT: outfit_suggestion in session")
    print("session['outfit_suggestion'] = \"<outfit string>\"")
    print(f"(String length: {len(outfit_suggestion)} characters)")
    
    print("\nNARRATION: The outfit suggestion is stored in the session.")
    print("Now it's passed to create_fit_card along with the item.")
    
    # Step 6: Create fit card
    print_section("STEP 4: CREATE FIT CARD (generate caption)")
    from tools import create_fit_card
    fit_card = create_fit_card(
        outfit=outfit_suggestion,
        new_item=selected_item
    )
    print(f"Generated fit card caption:")
    print(f"\n\"{fit_card}\"")
    
    print("\nNARRATION: The final step generates an Instagram-style caption.")
    print("It uses high temperature (0.9) so each run produces different wording.")
    print("Notice it naturally mentions the item name, price, and platform.")
    
    # Final state
    print_section("FINAL SESSION STATE (all 3 tools executed)")
    print("session = {")
    print(f"    'query': {query!r},")
    print(f"    'selected_item': <{selected_item['title']}>  [FROM SEARCH]")
    print(f"    'outfit_suggestion': <{len(outfit_suggestion)} char string>  [FROM SUGGEST_OUTFIT]")
    print(f"    'fit_card': <{len(fit_card)} char caption>  [FROM CREATE_FIT_CARD]")
    print("    'error': None")
    print("}")
    
    print("\nNARRATION: The session dict now contains outputs from all 3 tools.")
    print("The UI displays:")
    print("  - Panel 1: Listing details")
    print("  - Panel 2: Outfit suggestion with wardrobe piece names")
    print("  - Panel 3: Shareable fit card caption")
    
    return selected_item, outfit_suggestion, fit_card


def demo_error_handling():
    """Demo 2: Error path - impossible query"""
    print_section("DEMO 2: ERROR HANDLING - NO RESULTS PATH")
    
    print("\nNARRATION: Now let's see what happens when a search fails.")
    print("The agent should handle this gracefully.\n")
    
    query = "designer ballgown size XXS under $5"
    
    print(f"USER INPUT: '{query}'")
    print("WARDROBE: Example wardrobe\n")
    
    print("NARRATION: This is an impossible query for a thrift dataset.")
    print("Designer ballgowns are rare and expensive.\n")
    
    # Step 1: Parse
    print_section("STEP 1: PARSE QUERY")
    parsed = parse_query(query)
    print(f"Parsed query:")
    print(f"  - description: '{parsed['description']}'")
    print(f"  - size: {parsed['size']}")
    print(f"  - max_price: ${parsed['max_price']}")
    
    # Step 2: Search
    print_section("STEP 2: SEARCH LISTINGS")
    from tools import search_listings
    results = search_listings(
        description=parsed['description'],
        size=parsed['size'],
        max_price=parsed['max_price']
    )
    print(f"Search returned: {len(results)} results")
    print(f"Result type: {type(results)}")
    print(f"Result: {results}")
    
    print("\nNARRATION: The search returns an empty list [].")
    print("No exception is raised - the tool handles this gracefully.")
    print("Now the agent makes a CONDITIONAL DECISION:")
    
    # Step 3: Decision point
    print_section("CONDITIONAL PLANNING LOOP DECISION POINT")
    print("Agent checks: if search_results is empty?")
    if not results:
        print("\nRESULT: YES, results is empty []")
        print("\nDECISION: Return early with error message")
        print("DO NOT call suggest_outfit or create_fit_card")
        
        error_message = (
            f"No listings found for '{parsed['description']}' "
            f"(size: {parsed['size']}, max price: ${parsed['max_price']}). "
            "Try removing the size or price filter, or use broader keywords "
            "like 'graphic tee' instead of a very specific phrase."
        )
        print(f"\nERROR MESSAGE TO USER:")
        print(f"\n\"{error_message}\"")
        
        print("\nNARRATION: The agent provides actionable feedback.")
        print("It tells the user exactly what filters were used")
        print("and suggests how to broaden their search.")
    
    # Final state on error
    print_section("FINAL SESSION STATE (error path)")
    print("session = {")
    print("    'query': '" + query + "',")
    print("    'selected_item': None")
    print("    'outfit_suggestion': None")
    print("    'fit_card': None")
    print("    'error': '<error message above>'")
    print("}")
    
    print("\nNARRATION: Notice the outfit_suggestion and fit_card are None.")
    print("The agent NEVER called those tools because search failed.")
    print("This is the conditional planning loop in action - tools only run")
    print("when previous steps succeed.")
    
    print("\nUI RESULT:")
    print("  - Panel 1 (Listing): Shows error message")
    print("  - Panel 2 (Outfit): Empty")
    print("  - Panel 3 (Fit card): Empty")


def demo_empty_wardrobe():
    """Demo 3: Edge case - empty wardrobe"""
    print_section("DEMO 3: EDGE CASE - EMPTY WARDROBE")
    
    print("\nNARRATION: What if a new user with no wardrobe finds something?")
    print("The agent should still provide useful styling advice.\n")
    
    query = "vintage graphic tee under $30"
    wardrobe = get_empty_wardrobe()
    
    print(f"USER INPUT: '{query}'")
    print(f"WARDROBE: Empty wardrobe (0 items - new user)")
    
    # Run search
    from tools import search_listings, suggest_outfit
    parsed = parse_query(query)
    results = search_listings(
        description=parsed['description'],
        size=parsed['size'],
        max_price=parsed['max_price']
    )
    selected_item = results[0]
    
    print_section("STEP: SUGGEST OUTFIT WITH EMPTY WARDROBE")
    
    print("\nNARRATION: Even with no wardrobe items, suggest_outfit succeeds.")
    print("It's not treated as a failure - it's a valid scenario.\n")
    
    outfit_suggestion = suggest_outfit(
        new_item=selected_item,
        wardrobe=wardrobe
    )
    
    print(f"Outfit suggestion generated ({len(outfit_suggestion)} chars):")
    print(f"\n{outfit_suggestion[:350]}...\n")
    
    print("NARRATION: Notice this is different from the previous example.")
    print("Instead of referencing specific wardrobe pieces like 'your baggy jeans',")
    print("it provides GENERAL styling advice:")
    print("  - What categories pair well (distressed denim, chunky jewelry)")
    print("  - What vibe/era suits the item (90s grunge)")
    print("  - Example outfit directions without specific owned pieces")
    
    print("\nNARRATION: The agent gracefully adapts to the user's situation.")
    print("New users get general advice. Experienced users get wardrobe-specific suggestions.")


def main():
    """Run all demos"""
    print("\n\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  FitFindr Agent - Complete Demo Walkthrough".center(68) + "║")
    print("║" + "  Showing: State Passing, Planning Loop, Error Handling".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Run demos
    demo_happy_path()
    demo_error_handling()
    demo_empty_wardrobe()
    
    print_section("DEMO COMPLETE")
    print("\nKEY TAKEAWAYS:")
    print("✓ Planning loop is CONDITIONAL - not all tools run every time")
    print("✓ State passes between tools without re-parsing")
    print("✓ Error handling is graceful - no crashes, helpful messages")
    print("✓ Agent adapts to edge cases (empty wardrobe)")
    print("\nSee README.md for full documentation and running instructions.")


if __name__ == "__main__":
    main()
