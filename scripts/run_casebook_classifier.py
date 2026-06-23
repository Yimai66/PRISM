import os
import re
import json
import sys
import types
import pandas as pd
from pypdf import PdfReader


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
    Fake streamlit module so app.py can be imported without launching the UI.
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


PDF_PATH = "data/PRISM_CaseBook_Cases_1-12_Merged-2.pdf"
OUTPUT_PATH = "sacred_set/predictions_casebook12.csv"


def extract_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n".join(pages)


def extract_case_sections(full_text):
    """
    Split the Case Book into Case 1 to Case 12 sections.
    """
    pattern = r"(Case\s+\d+:[\s\S]*?)(?=Case\s+\d+:|3\. Cross-Case Analysis|Appendix A|$)"
    matches = re.findall(pattern, full_text)

    case_sections = []

    for section in matches:
        title_match = re.search(r"Case\s+(\d+):\s*(.+)", section)
        question_match = re.search(
            r"Question\s*\n(.+?)(?=\nSources Compared|\nExcerpts|\nDisagreement Type)",
            section,
            flags=re.S
        )

        if not title_match:
            continue

        case_num = int(title_match.group(1))
        title = title_match.group(2).strip()

        if case_num < 1 or case_num > 12:
            continue

        if question_match:
            question = " ".join(question_match.group(1).split())
        else:
            question = title

        case_sections.append({
            "id": f"Case-{case_num}",
            "case_num": case_num,
            "title": title,
            "question": question,
            "section_text": section.strip()
        })

    case_sections = sorted(case_sections, key=lambda x: x["case_num"])

    return case_sections


def run_classifier_for_case(case):
    """
    Feed one Case Book case into the existing PRISM classifier.
    """
    question = case["question"]
    section_text = case["section_text"]

    translated_queries = {
        "casebook": question
    }

    results_by_language = {
        "casebook": [
            {
                "title": case["title"],
                "url": "",
                "description": section_text[:6000]
            }
        ]
    }

    prediction = detect_disagreement(
        question=question,
        translated_queries=translated_queries,
        results_by_language=results_by_language
    )

    return prediction


def main(test_rows=None):
    os.makedirs("sacred_set", exist_ok=True)

    full_text = extract_pdf_text(PDF_PATH)
    cases = extract_case_sections(full_text)

    print(f"Extracted {len(cases)} cases from Case Book PDF.")

    if len(cases) != 12:
        print("WARNING: Expected 12 cases. Please check PDF extraction.")

    if test_rows is not None:
        cases = cases[:test_rows]

    rows = []

    for i, case in enumerate(cases, start=1):
        print(f"\n[{i}/{len(cases)}] Running {case['id']}: {case['title']}")
        print(f"Question: {case['question']}")

        try:
            prediction = run_classifier_for_case(case)

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

        rows.append({
            "id": case["id"],
            "case_num": case["case_num"],
            "title": case["title"],
            "question": case["question"],
            "predicted_labels": "; ".join(labels) if isinstance(labels, list) else str(labels),
            "summary": summary,
            "omission_notes": omission_notes,
            "confidence": confidence,
            "raw_prediction": raw_prediction
        })

        # Save after every case, so progress is not lost
        pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
        print(f"  Saved progress to {OUTPUT_PATH}")

    print("\n==============================")
    print("CASE BOOK CLASSIFIER SUMMARY")
    print("==============================")
    print(f"Saved predictions to: {OUTPUT_PATH}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main(test_rows=None)