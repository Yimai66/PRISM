# PRISM: Cross-Language Search Prototype

## Overview

PRISM is a cross-language search engine built in the first half of the course. You type a
question, it runs that question on Wikipedia in a few languages at once, shows the results in side
by side columns, and an LLM looks at the columns and tries to label what kind of disagreement
is between them. 

The purpose of PRISM is not to produce one single final answer. Instead, it is designed to show how different language communities, source contexts, or national framings may answer the same question differently.

This repository contains the technical prototype and dataset-processing scripts for the PRISM group project.

---

## Prototype Features

The repository includes:

- a user question input box
- case-specific language selections
- side-by-side multilingual Wikipedia result panels
- translated query handling for supported demo cases
- disagreement detection based on the six-type taxonomy
- CSV export for evaluation
- scraper and classifier scripts for the weak set and Case Book evaluations

---

## Current Stable Version

The current stable version supports both the live demo and the evaluation pipeline.

For the live demo, the app can take a user question, show multilingual search results side by side, and use an LLM-based classifier to label the disagreement type.

For the dataset pipeline, the repository now includes:

- a Wikipedia scraper for the weak-set candidates
- filtering logic for missing pages and short lead text
- classifier outputs for the 133 surviving weak-set cases
- a separate Case Book classifier output for Case-1 through Case-12

The weak-set pipeline starts from 150 candidate cases. After scraping and filtering, 133 cases were kept, giving an 89% yield. Dropped cases and reasons are recorded in `weak_set/drop_log.csv`.

The Case Book evaluation is kept separate from the weak-set evaluation. `sacred_set/predictions_casebook12.csv` contains predictions for Case-1 through Case-12, while `weak_set/predictions.csv` contains predictions for the 133 surviving weak-set candidate IDs.

---

## Repository Structure

```text
data/
  150_candidates.xlsx
  PRISM_CaseBook_Cases_1-12_Merged-2.pdf

scripts/
  wiki_scraper.py
  run_weak_classifier.py
  run_casebook_classifier.py

weak_set/
  scraped/
  kept_cases.csv
  drop_log.csv
  drop_summary.json
  predictions.csv

sacred_set/
  predictions_casebook12.csv

app.py
README.md
requirements.txt
```

---

## Live and Mock Modes

The prototype supports both mock and live components.

For the live demo, the app can use live search results and an OpenAI-compatible LLM API to classify disagreement types. The LLM receives the user question, the language-specific result panels, and the six-type disagreement taxonomy.

Some parts of the demo can still use mock or pre-selected inputs when needed. This keeps the demo stable for presentation and avoids unexpected changes from live search or translation results.

The current stable pipeline is:

User question → language-specific search/results → side-by-side multilingual panels → LLM disagreement classification → CSV export for evaluation

---

## Case Book and Weak Set Evaluation

The project now includes two evaluation outputs.

The first output is the Case Book evaluation. This uses the 12 hand-written Case Book cases, with IDs from Case-1 to Case-12. The prediction file is: 

`sacred_set/predictions_casebook12.csv`
The second output is the weak-set evaluation. The weak set started from 150 candidate cases. After scraping and filtering, 133 cases were kept. The prediction file is: 

`weak_set/predictions.csv`

Dropped weak-set cases and their reasons are recorded in: 

`weak_set/drop_log.csv`

These two evaluation files are kept separate because they use different ID systems. The Case Book file uses Case-1 to Case-12, while the weak-set file uses candidate IDs such as T1-03 and T2-05.

---

## Case-Specific Language Sets

PRISM uses different language settings for the Case Book evaluation and the weak-set pipeline.

For the Case Book evaluation, the language set is case-specific. Each of the 12 Case Book cases uses the languages that are most relevant to that question. For example, the North Pole case compares English, Russian, and Norwegian, while the printing case compares English, Chinese, Korean, and German.

For the weak-set pipeline, we used a fixed four-language setup: English, Chinese, Korean, and Russian. The scraper attempted to collect the lead text and infobox from these four Wikipedia language editions for each candidate case.

A weak-set case was kept only if the required language pages and usable lead text were available. Cases with missing pages or very short lead text were recorded in `weak_set/drop_log.csv`.

This means that the Case Book evaluation uses case-specific language comparison, while the weak-set expansion uses a fixed multilingual pipeline for consistency.

---

## Disagreement Taxonomy
The disagreement detection is based on a six-type taxonomy.
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
   python3 -m pip install -r requirements.txt
   ```

3. Create a `.env` file from the example file:

   ```bash
   cp .env.example .env
   ```

4. Add the required API keys in `.env`:

   ```env
   BRAVE_API_KEY=your_brave_key_here
   DEEPL_API_KEY=
   OPENAI_API_KEY=your_openai_key_here
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

## How to Reproduce the Evaluation Outputs

The repository includes scripts for reproducing the weak-set and Case Book prediction files.

Run the weak-set scraper and filtering step:

```bash
python3 scripts/wiki_scraper.py
```

This creates or updates the following files:

```text
weak_set/kept_cases.csv
weak_set/drop_log.csv
weak_set/drop_summary.json
weak_set/scraped/
```

Run the classifier on the surviving weak-set cases:

```bash
python3 scripts/run_weak_classifier.py
```

This creates or updates:

```text
weak_set/predictions.csv
```

Run the classifier on the 12 Case Book cases:

```bash
python3 scripts/run_casebook_classifier.py
```

This creates or updates:

```text
sacred_set/predictions_casebook12.csv
```

The weak-set prediction file and the Case Book prediction file are kept separate because they use different ID systems. The weak-set file uses candidate IDs such as `T1-03`, while the Case Book file uses IDs from `Case-1` to `Case-12`.

---

## Notes and Limitations

- This is a research prototype, not a production search engine.
- Brave Search API is used for live multilingual search in the demo.
- LLM disagreement detection is live when USE_LIVE_LLM=true.
- Live translation is optional. The stable demo can use pre-selected or manually checked query inputs when needed, to keep the presentation stable.
- Some language-region combinations are not fully supported by the search API, so fallback results may be used.
- The Case Book evaluation and weak-set evaluation are separate. The Case Book output uses IDs from Case-1 to Case-12, while the weak-set output uses candidate IDs such as T1-03.
- The weak-set prediction file only includes cases that passed the scraping and filtering stage. Dropped cases and reasons are recorded in `weak_set/drop_log.csv`.
- The War of 1812 case is an edge case because it compares U.S., Canadian, and British English-language framings rather than clearly separate languages.
