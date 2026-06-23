import os
import re
import json
import sys
import types
import pandas as pd


# Make sure we can import app.py from project root
sys.path.append(os.getcwd())


class DummySidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __getattr__(self, name):
        def dummy(*args, **kwargs):
            return None
        return dummy


class DummyStreamlit(types.ModuleType):
    """
    Fake streamlit module so app.py can be imported without launching/running the UI.
    """

    def __init__(self):
        super().__init__("streamlit")
        self.sidebar = DummySidebar()

    def __getattr__(self, name):
        if name in ["cache_data", "cache_resource"]:
            def decorator(*args, **kwargs):
                if args and callable(args[0]):
                    return args[0]

                def wrapper(func):
                    return func

                return wrapper

            return decorator

        if name == "button":
            return lambda *args, **kwargs: False

        if name == "selectbox":
            return lambda label, options, **kwargs: options[0] if options else None

        if name == "multiselect":
            return lambda label, options, default=None, **kwargs: default or []

        if name == "text_input":
            return lambda *args, **kwargs: kwargs.get("value", "")

        if name == "slider":
            return lambda *args, **kwargs: kwargs.get("value", None)

        def dummy(*args, **kwargs):
            return None

        return dummy


# Replace streamlit with dummy version before importing app.py
sys.modules["streamlit"] = DummyStreamlit()

from app import detect_disagreement


KEPT_CASES_PATH = "weak_set/kept_cases.csv"
SCRAPED_DIR = "weak_set/scraped"
OUTPUT_PATH = "weak_set/predictions.csv"

LANGS = ["en", "zh", "ko", "ru"]


def safe_name(text):
    text = str(text)
    text = re.sub(r"[^\w\-]+", "_", text)
    return text[:80]


def read_text_file(path, max_chars=1000):
    """
    Read only the lead section to keep classifier input short.
    """
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    if "INFOBOX" in text:
        text = text.split("INFOBOX")[0]

    text = text.replace("LEAD PARAGRAPHS", "").replace("================", "").strip()

    return text[:max_chars]


def build_results_for_case(case_id, entity):
    """
    Convert scraped Wikipedia txt files into the format expected by app.py:
    results_by_language = {
        "en": [{"title": ..., "url": ..., "description": ...}],
        ...
    }
    """
    folder_name = f"{case_id}_{safe_name(entity)}"
    case_folder = os.path.join(SCRAPED_DIR, folder_name)
    metadata_path = os.path.join(case_folder, "metadata.json")

    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    results_by_language = {}

    for lang in LANGS:
        txt_path = os.path.join(case_folder, f"{lang}.txt")
        text = read_text_file(txt_path)

        lang_meta = metadata.get("languages", {}).get(lang, {})
        url = lang_meta.get("url", "")

        results_by_language[lang] = [
            {
                "title": f"{entity} ({lang} Wikipedia)",
                "url": url,
                "description": text
            }
        ]

    return results_by_language


def main(test_rows=None):
    kept_df = pd.read_csv(KEPT_CASES_PATH)

    processed_ids = set()

    if os.path.exists(OUTPUT_PATH):
        old_predictions = pd.read_csv(OUTPUT_PATH)
        if "id" in old_predictions.columns:
            processed_ids = set(old_predictions["id"].astype(str))
            print(f"Already processed: {len(processed_ids)} cases")

    kept_df = kept_df[~kept_df["id"].astype(str).isin(processed_ids)]

    if test_rows is not None:
        kept_df = kept_df.head(test_rows)

    print(f"Running classifier on {len(kept_df)} remaining cases...")

    for idx, row in kept_df.iterrows():
        case_id = row["id"]
        entity = row["entity"]
        question = row["question"]

        print(f"\nProcessing {case_id}: {entity}")

        translated_queries = {
            "en": question,
            "zh": question,
            "ko": question,
            "ru": question
        }

        results_by_language = build_results_for_case(case_id, entity)

        try:
            prediction = detect_disagreement(
                question=question,
                translated_queries=translated_queries,
                results_by_language=results_by_language
            )

            labels = prediction.get("labels", [])

            if not labels:
                labels = ["No label returned"]

            summary = prediction.get("summary", "")
            omission_notes = prediction.get("omission_notes", "")
            confidence = prediction.get("confidence", "")
            raw_prediction = json.dumps(prediction, ensure_ascii=False)

            print(f"  labels: {labels}")
            print(f"  confidence: {confidence}")

        except Exception as e:
            labels = ["ERROR"]
            summary = str(e)
            omission_notes = ""
            confidence = "error"
            raw_prediction = ""

            print(f"  ERROR: {e}")

        prediction_row = {
            "id": case_id,
            "entity": entity,
            "question": question,
            "predicted_labels": "; ".join(labels) if isinstance(labels, list) else str(labels),
            "summary": summary,
            "omission_notes": omission_notes,
            "confidence": confidence,
            "raw_prediction": raw_prediction
        }

        prediction_df = pd.DataFrame([prediction_row])

        if os.path.exists(OUTPUT_PATH):
            prediction_df.to_csv(OUTPUT_PATH, mode="a", header=False, index=False)
        else:
            prediction_df.to_csv(OUTPUT_PATH, index=False)

        print(f"  Saved prediction for {case_id}")

    print("\n==============================")
    print("CLASSIFIER SUMMARY")
    print("==============================")

    if os.path.exists(OUTPUT_PATH):
        final_df = pd.read_csv(OUTPUT_PATH)
        print(f"Saved predictions to: {OUTPUT_PATH}")
        print(f"Rows currently saved: {len(final_df)}")
    else:
        print("No predictions file was created.")


if __name__ == "__main__":
    main(test_rows=None)