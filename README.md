# FitFindr

FitFindr is a multi-tool AI agent that helps users find secondhand clothing, style it against their existing wardrobe, and generate a shareable outfit caption — all from one natural language query.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run tests:

```bash
pytest tests/ -v
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

| | |
|---|---|
| **Purpose** | Search the mock listings dataset for items matching keywords, with optional size and price filters. Results are ranked by relevance (keyword overlap weighted by frequency in title, description, and style tags). |
| **Input parameters** | `description` (str) — user's search query (e.g., `"vintage graphic tee"`), tokenized into lowercase words and matched against listing fields. `size` (str \| None) — optional size filter; case-insensitive substring match (e.g., `"M"` matches `"S/M"`). `None` skips size filtering. `max_price` (float \| None) — maximum price (inclusive); listings with `price > max_price` are excluded. `None` skips price filtering. |
| **Returns** | `list[dict]` — matching listings sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price`, `colors` (list), `brand`, `platform`. Returns `[]` (empty list) when no results match; does not raise an exception. |
| **Failure mode & handling** | When no listings match the query parameters, returns an empty list. The agent detects this and sets `session["error"]` with a helpful message listing the filters used and suggestions to broaden the search. Does not call downstream tools. |

### `suggest_outfit(new_item, wardrobe)`

| | |
|---|---|
| **Purpose** | Given a thrifted item and the user's wardrobe, calls Groq LLM to suggest 1–2 complete outfit combinations. If wardrobe is empty, returns general styling advice instead. |
| **Input parameters** | `new_item` (dict) — a listing dict from `search_listings` (must have at least `title`, `description`, `style_tags`, `category`, `colors`). `wardrobe` (dict) — wardrobe schema with `items` key containing list of wardrobe item dicts (`name`, `category`, `colors`, `style_tags`, optional `notes`). May have an empty `items` list. |
| **Returns** | A non-empty `str` with 1–2 outfit suggestions or general styling advice. When wardrobe has items: names specific pieces and describes how to wear them (fit tips, tucking, layering, vibe). When wardrobe is empty: provides general guidance on categories and colors that pair well. |
| **Failure mode & handling** | Empty wardrobe is not a failure — the tool returns general styling advice. LLM/API errors: returns fallback string explaining the issue and offering basic pairing advice based on item tags and category. The agent always stores the result in `session["outfit_suggestion"]` and proceeds to `create_fit_card`. |

### `create_fit_card(outfit, new_item)`

| | |
|---|---|
| **Purpose** | Calls Groq LLM with high temperature (0.9) to generate a short, casual Instagram/TikTok caption from the outfit suggestion and item details. Produces varied outputs for the same input due to high temperature. |
| **Input parameters** | `outfit` (str) — the outfit suggestion string from `suggest_outfit()` (e.g., fit tips and piece names). `new_item` (dict) — the thrifted item listing dict (uses `title`, `price`, `platform`). |
| **Returns** | A `str` of 2–4 sentences usable as a social media caption. Mentions item name, price, and platform naturally (once each). Returns descriptive error message string if `outfit` is empty/whitespace-only; does not raise an exception. |
| **Failure mode & handling** | Empty/whitespace outfit: returns `"Cannot create a fit card: no outfit suggestion was provided. Run suggest_outfit first."` without crashing. LLM/API error: returns fallback caption template built from item fields so user still gets something shareable. |

---

## How the Planning Loop Works

`run_agent()` in `agent.py` implements **conditional sequential logic** where each step's output determines whether the next step runs. This is not a fixed pipeline:

1. **Parse Query** → Use regex to extract `description`, `size`, and `max_price` from natural language.
   - Patterns: `under $X`, `size S/M/L/XL`, descriptive keywords
   - Store in `session["parsed"]`

2. **Search** → Call `search_listings(description, size, max_price)`
   - Store full result list in `session["search_results"]`
   - **Decision point:** Is `search_results` empty?
     - **YES** → Set `session["error"]` with actionable message (e.g., *"No listings found for 'designer ballgown' (size: XXS, max price: $5). Try removing the size or price filter..."*) and **return session immediately**. Stop execution. Do not call downstream tools.
     - **NO** → Continue to next step

3. **Select Item** → Set `session["selected_item"] = search_results[0]` (top match by relevance)

4. **Suggest Outfit** → Call `suggest_outfit(selected_item, wardrobe)`
   - Store result in `session["outfit_suggestion"]`
   - This tool handles its own failure mode (empty wardrobe still returns advice)
   - Always proceed to next step

5. **Create Fit Card** → Call `create_fit_card(outfit_suggestion, selected_item)`
   - Store result in `session["fit_card"]`
   - This tool handles its own failure mode (empty outfit returns error message)
   - Always proceed to return

6. **Return** → Return the session dict with all populated or error fields

**Why this matters:** The agent's behavior is fundamentally different depending on whether the search succeeded:
- **Search finds results** → All three tools run, all three panels populate
- **Search finds nothing** → Only error panel populates, user sees actionable feedback

This conditional branching is the core of the planning loop — without it, the agent would blindly call all tools even when the first one fails.

---

## State Management

All state lives in one `session` dict per interaction:

- `parsed` — extracted search parameters
- `search_results` — full result list from search
- `selected_item` — top listing, passed to styling and fit card tools
- `wardrobe` — user's closet (from UI choice)
- `outfit_suggestion` — string from `suggest_outfit`, passed to `create_fit_card`
- `fit_card` — final caption
- `error` — set only on early termination (e.g., no search results)

Information flows without re-prompting: the listing found in step 2 is the same dict object passed to steps 3 and 4.

---

## Error Handling

Each tool is designed to fail gracefully without crashing the agent. The strategy for each tool is documented below with concrete test results:

| Tool | Failure mode | Response strategy | Test result |
|------|-------------|------------------|-------------|
| `search_listings` | No results match the query | Return empty list. Agent detects this and sets `session["error"]` with the query parameters and suggestions to broaden search. Does not call downstream tools. | **Query:** `search_listings("designer ballgown", size="XXS", max_price=5)`; **Result:** Returns `[]`; **Agent response:** `"No listings found for 'designer ballgown' (size: XXS, max price: $5). Try removing the size or price filter, or use broader keywords like 'graphic tee' instead of a very specific phrase."` |
| `suggest_outfit` | Wardrobe is empty | Not treated as a failure. Tool calls LLM with a prompt for general styling advice instead of wardrobe-specific suggestions. | **Query:** `suggest_outfit(item, get_empty_wardrobe())`; **Result:** Returns full string (1600+ chars) with general styling advice: *"This graphic tee has a great vintage vibe... suggests distressed denim... chunky jewelry..."*; Agent continues to fit card step. |
| `create_fit_card` | Outfit input is empty or whitespace | Check if outfit is empty/whitespace and return descriptive error message string instead of calling LLM. | **Query:** `create_fit_card("", item)` or `create_fit_card("   ", item)`; **Result:** Returns `"Cannot create a fit card: no outfit suggestion was provided. Run suggest_outfit first."` instead of exception. |
| `create_fit_card` | LLM/API error | Catch exception and return fallback caption built from item fields. | If Groq API is down, tool returns: `"scored <item_title> on <platform> for $<price> and honestly it's the move [outfit_excerpt]..."` so user still gets something shareable. |

**Integration test example:** Running the agent with query `"designer ballgown size XXS under $5"` using `run_agent()`:
- Search returns `[]`
- Agent sets `session["error"]` to the helpful message above
- `session["fit_card"]` remains `None` (never called)
- UI displays error in listing panel, outfit and fit card panels empty

---

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers."

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why: User asked for a specific item type with a price cap.
- Output: Top match — **Vintage Band Tee — Faded Grey**, $19.00, Depop, size L.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: `new_item=<band tee listing>`, `wardrobe=get_example_wardrobe()`
- Why: A match was found; time to style it against the user's closet.
- Output: Outfit pairing the tee with baggy jeans, chunky sneakers, and optional denim jacket.

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: `outfit=<step 2 string>`, `new_item=<band tee listing>`
- Why: User wants a shareable caption for the complete look.
- Output: Casual Instagram-style caption mentioning Depop, $19, and the grunge vibe.

**Final output to user:** Three panels — listing details, outfit suggestion, fit card caption.

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing the conditional branches in the Planning Loop section before coding made the early-exit behavior explicit. When implementing `run_agent()`, I could match each `if not results: return session` directly to the spec instead of accidentally calling all three tools in a fixed sequence.

**One divergence from your spec, and why:**

The spec described query parsing as optionally using the LLM, but I used regex instead. Regex is faster, free (no API call), and sufficient for the structured patterns in the example queries (`under $30`, `size M`). Wardrobe details mentioned in the query (e.g., "baggy jeans") are not parsed into a custom wardrobe — the UI wardrobe choice is used instead, which matches how the Gradio app is wired.

---

## AI Usage

This project used Claude (via Copilot) to implement specific, well-defined components based on detailed specifications from `planning.md`.

**Instance 1 — Tool implementations (Milestone 3):**

- **Input given to Claude:** Tool 1/2/3 specification blocks from `planning.md` (exact parameter names/types, return value format, failure mode handling) plus the function stubs with TODO steps from `tools.py`.
- **What Claude produced:** Draft implementations of all three tool functions with LLM integration for suggest_outfit and create_fit_card.
- **Changes I made before using:** 
  1. Adjusted `_score_listing` weights (style tags 2× vs title/description 1×) for better relevance ranking
  2. Added substring matching for size field (so `"M"` matches `"S/M"`)
  3. Wrapped LLM calls in try/except blocks to return fallback strings instead of crashing on API failure
  4. Increased temperature to 0.9 in create_fit_card so outputs vary across runs
- **Why these changes mattered:** The spec was precise about *what* to do, but Claude made reasonable assumptions that needed tuning for thrift/fashion context (style tags should weight heavier in matching) and robustness (API errors should return text, not exceptions).

**Instance 2 — Planning loop implementation (Milestone 4):**

- **Input given to Claude:** 
  - The Mermaid flowchart from `planning.md` (visualizing the conditional branching)
  - Planning Loop section (describing each step and the decision point)
  - State Management section (session dict table)
  - The function stubs and TODO steps in `agent.py`
- **What Claude produced:** Complete implementation of `run_agent()`, `parse_query()`, and `handle_query()` functions with proper session management and conditional branching.
- **Changes I made before using:**
  1. Extracted `format_listing()` as a separate helper function for UI formatting (Claude included inline, but isolating it makes the code clearer)
  2. Tightened the error message to include the exact parsed filters so users know what to adjust
  3. Added comments clarifying the conditional branches at the decision point (if not results: return early)
- **Why this is important:** Claude produced working code, but isolating formatting logic and being explicit about why we return early (with comments) makes the planning loop's conditional logic visible in the code — directly matching the specification. This makes it clear to anyone reading the code that *the loop is conditional, not fixed*.

---

## Demo Video

A 3–5 minute walkthrough demonstrating:
1. **Complete multi-step workflow:** Query → search → outfit suggestion → fit card, showing all three tools in sequence
2. **State passing visible:** Narrated explanation of how the `selected_item` found in step 1 flows to steps 2 and 3 without re-parsing
3. **Error handling tested:** No-results query showing graceful error message and empty panels

**Test results:**
- ✅ Happy path (`"vintage graphic tee under $30"`) with Example wardrobe: All three panels populate with listing, outfit suggestion, and shareable caption
- ✅ Happy path with Empty wardrobe: Outfit panel shows general styling advice instead of wardrobe-specific suggestions
- ✅ Error path (`"designer ballgown size XXS under $5"`): Error message displays in listing panel; outfit and fit card panels remain empty, showing agent correctly stopped after search

---

## Running the Project

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### Setup

Create a `.env` file in the project root with your Groq API key:

```
GROQ_API_KEY=your_key_from_console.groq.com
```

Get a free key at [console.groq.com](https://console.groq.com) — no credit card required.

### Running the App

```bash
python app.py
```

Opens at `http://127.0.0.1:7860` in your browser. Three panels display:
- **🛍️ Top listing found:** Full details of the best matching item
- **👗 Outfit idea:** Styling suggestions using the user's wardrobe (or general advice if new)
- **✨ Your fit card:** Shareable Instagram-style caption

### Running Tests

```bash
pytest tests/ -v
```

All 8 tests pass:
- `search_listings`: normal queries, empty results, price/size filtering
- `create_fit_card`: error handling for empty/whitespace input
- `suggest_outfit`: behavior with empty vs. full wardrobe

### Testing Individual Tools

```bash
# Test search directly
python -c "from tools import search_listings; results = search_listings('vintage graphic tee', None, 50); print(f'Found {len(results)} results')"

# Test the full agent with hardcoded input
python agent.py
```

---

## Project Structure

```
FitFindr/
├── app.py                    # Gradio web interface
├── agent.py                  # Planning loop & session management
├── tools.py                  # Three tools + LLM integration
├── utils/data_loader.py      # Data loading utilities
├── data/
│   ├── listings.json         # 60+ mock thrift listings
│   └── wardrobe_schema.json  # Wardrobe schema + examples
├── tests/test_tools.py       # 8 unit tests (all passing)
├── planning.md               # Detailed specifications
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

---

## Design Decisions

1. **Conditional planning loop, not fixed pipeline:** The agent doesn't blindly call all tools. It checks if search returned results and stops early if not. This makes the agent truly responsive to its environment.

2. **State dict over parameter passing:** Using a single session dict (not passing results between function calls) makes it easy to debug, serialize for logging, and extend with additional fields like `timestamp` or `user_id`.

3. **Regex for query parsing, not LLM:** Parsing extracts structured data (price, size) which is deterministic. LLM should be reserved for creative tasks (outfit suggestions, captions), not parsing.

4. **Graceful degradation in LLM tools:** Both suggest_outfit and create_fit_card have fallbacks. If the LLM fails or returns nothing, the agent still provides *something* useful to the user instead of crashing.

5. **High temperature in create_fit_card:** Temperature = 0.9 makes captions varied and authentic-sounding. Running the same outfit through the tool twice produces different captions, matching how users actually write on social media.

---

## Possible Extensions (Stretch Features)

1. **Price comparison tool:** Given an item, estimate fair value by analyzing prices of similar items in the dataset
2. **Style profile memory:** Remember user's style preferences and wardrobe across sessions (persist to database)
3. **Retry with loosened constraints:** If search_listings returns nothing, automatically retry with size/price filters removed and inform the user what was adjusted
4. **Trend awareness:** Check current fashion tags/hashtags to surface trending styles in the user's size range
