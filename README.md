# PRISM Role 1 Prototype

## Overview

PRISM is a cross-language search prototype that runs the same question across multiple language contexts and displays the results side by side.

The purpose of PRISM is not to produce one single final answer. Instead, it is designed to show how different language communities, source contexts, or national framings may answer the same question differently.

This repository contains the Role 1 technical prototype for the PRISM group project.

---

## Role 1 Goal

Role 1 is responsible for building the working web demo.

The prototype includes:

- a user question input box
- six preset demo questions from Role 2's Case Book
- case-specific language selections
- translated queries
- side-by-side multilingual search results
- disagreement detection based on Role 2's six-type taxonomy
- CSV export for Role 4 evaluation

---

## Current Stable Version

The current stable version uses:

- **Live Brave Search API** for multilingual web search
- **Case Book-based mock translations** for the six verified questions
- **Live LLM disagreement detection** for taxonomy classification

This means the prototype retrieves live search results where supported, uses manually verified translations from Role 2's Case Book, and asks an LLM to classify disagreement types based on the search result panels.

This setup keeps the demo stable while still allowing Role 4 to evaluate the LLM's output against Role 2's human-coded Case Book labels.

---

## Why Translation Uses Mock Mode

The prototype includes optional live modes for:

- DeepL translation
- OpenAI-compatible LLM disagreement detection

In the current stable version, translation remains in mock mode because the six demo questions already have manually verified translations from Role 2's Case Book. This avoids translation instability and keeps the demo aligned with the case analysis.

However, disagreement detection is now run through a live LLM API. The LLM receives the translated queries and search result panels, then classifies the disagreement using Role 2's six-type taxonomy.

The current stable pipeline is therefore:

User question
↓
Case Book-based translation
↓
Live Brave Search API
↓
Side-by-side multilingual results
↓
Live LLM disagreement classification
↓
CSV export for evaluation

---

## Six Demo Questions

The prototype includes all six questions from Role 2's Case Book:

-When did World War II start?
-Who invented the printing press?
-Who won the War of 1812?
-What caused the Opium Wars?
-When did the Roman Empire fall?
-Who discovered America?

Each preset question uses the language set identified in the Case Book.

---

## Case-Specific Language Sets
The prototype does not compare every possible language for every question. Instead, each case uses the languages selected and verified by Role 2.
| Case                             | Languages                        |
| -------------------------------- | -------------------------------- |
| When did World War II start?     | English, Chinese, Russian        |
| Who invented the printing press? | English, Chinese, Korean, German |
| Who won the War of 1812?         | EN-US, EN-CA, EN-UK                        |
| What caused the Opium Wars?      | English, Chinese, French         |
| When did the Roman Empire fall?  | English, Greek, Italian          |
| Who discovered America?          | English, Spanish, Icelandic      |


The War of 1812 case is treated as an edge case because its disagreement is mainly between U.S., Canadian, and British English-language framings rather than between clearly separate languages.

---

## Disagreement Taxonomy
The disagreement detection is based on Role 2's six-type taxonomy:
| Type                           | Description                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------------ |
| Type A — Factual Divergence    | Sources state different concrete facts, such as dates, names, or numbers.                  |
| Type B — Attribution           | Sources credit different people, places, or cultures with the same invention or discovery. |
| Type C — Outcome               | Sources describe different winners, losers, or end-states.                                 |
| Type D — Framing               | Sources agree on basic facts but emphasize different causes, motives, or significance.     |
| Type E — Definitional Boundary | Sources use the same name for entities or periods that are bounded differently.            |
| Type F — Omission              | One source omits information that another source treats as central.                        |

The prototype does not return a simple "same / different" label. It classifies disagreements using one or more of these six categories.

---

## How to Run Locally

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file from the example file:

   ```bash
   cp .env.example .env
   ```

4. Use this stable configuration in `.env`:

   ```env
   BRAVE_API_KEY=your_brave_key_here
   DEEPL_API_KEY=
   OPENAI_API_KEY=your_brave_key_here
   If using an OpenAI-compatible API provider, set `OPENAI_BASE_URL` accordingly. If using the official OpenAI API, this can be left blank.
   OPENAI_MODEL=gpt-4o-mini

   MOCK_MODE=false

   USE_LIVE_SEARCH=true
   USE_LIVE_TRANSLATION=false
   USE_LIVE_LLM=true
   ```

5. Run the app:

   ```bash
   streamlit run app.py
   ```

6. Open the local URL shown in the terminal, usually:

   ```text
   http://localhost:8501
   ```

---

## Notes and Limitations
- Brave Search API is live in the current demo.
- LLM disagreement detection is live in the current demo.
- DeepL translation is implemented as an optional live mode, but the stable version uses Case Book-based translations because the six demo translations were manually verified.
- Some Brave Search language-region combinations are not fully supported, so fallback results may be used.
- The War of 1812 case is an edge case because it compares U.S., Canadian, and British English-language framings rather than separate languages.
- This is a research prototype, not a production search engine.

---

## Output for Role 4
The app includes a CSV export button. The exported file can be used by Role 4 to compare the live LLM-generated disagreement labels with Role 2's manually verified Case Book labels.
