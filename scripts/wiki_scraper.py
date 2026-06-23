import os
import re
import time
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup


INPUT_FILE = "data/150_candidates.xlsx"
OUTPUT_DIR = "weak_set/scraped"

# Based on your existing Case Book examples
LANGS = ["en", "zh", "ko", "ru"]


def clean_entity(entity):
    """
    Clean the entity name from the spreadsheet.
    Example: 'the Vietnam War' -> 'Vietnam War'
    """
    entity = str(entity).strip()

    if entity.lower().startswith("the "):
        entity = entity[4:]

    return entity


def safe_name(text):
    """Make a safe folder/file name."""
    text = str(text)
    text = re.sub(r"[^\w\-]+", "_", text)
    return text[:80]


def count_sentences(text):
    """
    Rough sentence counter for English, Chinese, Korean, Russian.
    Counts common sentence-ending punctuation.
    """
    if not text or not isinstance(text, str):
        return 0

    endings = re.findall(r"[.!?。！？；;]", text)

    if len(endings) > 0:
        return len(endings)

    # fallback: if there is a long lead but no punctuation, count it as 1 sentence
    if len(text.strip()) > 80:
        return 1

    return 0


def evaluate_case(metadata, required_langs=None):
    """
    Decide whether a case should be kept or dropped.

    Drop if:
    1. Any required language is missing.
    2. Any required language has lead fewer than 2 sentences.
    """
    if required_langs is None:
        required_langs = ["en", "zh", "ko", "ru"]

    drop_reasons = []

    for lang in required_langs:
        lang_info = metadata["languages"].get(lang)

        if lang_info is None:
            drop_reasons.append(f"{lang}: missing_language_metadata")
            continue

        if lang_info.get("status") != "scraped":
            drop_reasons.append(f"{lang}: {lang_info.get('status')}")
            continue

        lead_sentences = lang_info.get("lead_sentences", 0)
        lead_chars = lang_info.get("lead_chars", 0)

        # Keep if the lead has at least 2 sentence endings,
        # or if it has 1 sentence but is still a substantial lead paragraph.
        if lead_sentences < 2 and lead_chars < 150:
            drop_reasons.append(
                f"{lang}: lead_too_short_{lead_sentences}_sentences_{lead_chars}_chars"
            )

    keep = len(drop_reasons) == 0
    return keep, drop_reasons


def get_html(url):
    headers = {
        "User-Agent": "PRISM student research scraper for educational use"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            return None

        return response.text

    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_wikipedia_url(lang, title):
    title_for_url = str(title).replace(" ", "_")
    return f"https://{lang}.wikipedia.org/wiki/{title_for_url}"


def extract_language_links(en_html):
    """
    Extract cross-language Wikipedia links from the English page.
    This helps us find the correct zh/ko/ru page titles.
    """
    soup = BeautifulSoup(en_html, "html.parser")
    lang_links = {}

    for a in soup.select("a.interlanguage-link-target"):
        lang = a.get("lang")
        href = a.get("href")

        if lang and href:
            lang_links[lang] = href

    return lang_links


def extract_lead_and_infobox(html):
    """
    Extract lead paragraphs and infobox text from Wikipedia HTML.
    More robust version for English, Chinese, Korean, and Russian pages.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "sup"]):
        tag.decompose()

    # Extract infobox
    infobox_text = ""
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if infobox:
        infobox_text = infobox.get_text("\n", strip=True)

    content = soup.find("div", {"id": "mw-content-text"})
    lead_paragraphs = []

    if content:
        parser_output = content.find("div", class_="mw-parser-output")

        if parser_output:
            # Method 1: direct children before first heading
            for child in parser_output.children:
                name = getattr(child, "name", None)

                if name == "h2":
                    break

                if name == "div" and child.get("class") and "mw-heading" in child.get("class"):
                    break

                if name == "p":
                    text = child.get_text(" ", strip=True)
                    if text and len(text) > 30:
                        lead_paragraphs.append(text)

            # Method 2 fallback: if direct-child method fails, take first useful paragraphs
            if not lead_paragraphs:
                all_paragraphs = parser_output.find_all("p")

                for p in all_paragraphs:
                    text = p.get_text(" ", strip=True)

                    if not text:
                        continue

                    # skip very short or navigation-like paragraphs
                    if len(text) < 30:
                        continue

                    lead_paragraphs.append(text)

                    # enough lead content
                    if len(lead_paragraphs) >= 3:
                        break

    lead_text = "\n\n".join(lead_paragraphs)

    return lead_text, infobox_text


def save_case_language(case_folder, lang, lead_text, infobox_text):
    os.makedirs(case_folder, exist_ok=True)
    output_path = os.path.join(case_folder, f"{lang}.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("LEAD PARAGRAPHS\n")
        f.write("================\n")
        f.write(lead_text if lead_text else "[NO LEAD FOUND]")
        f.write("\n\n\n")
        f.write("INFOBOX\n")
        f.write("=======\n")
        f.write(infobox_text if infobox_text else "[NO INFOBOX FOUND]")


def scrape(test_rows=10):
    df = pd.read_excel(INPUT_FILE)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    kept_cases = []
    dropped_cases = []

    if test_rows is not None:
        df = df.head(test_rows)

    for idx, row in df.iterrows():
        case_id = row["id"]
        raw_entity = row["entity"]
        entity = clean_entity(raw_entity)
        question = row["question"]

        case_folder_name = f"{case_id}_{safe_name(entity)}"
        case_folder = os.path.join(OUTPUT_DIR, case_folder_name)

        print(f"\nScraping {case_id}: {entity}")

        metadata = {
            "id": str(case_id),
            "template_id": str(row.get("template_id", "")),
            "template_name": str(row.get("template_name", "")),
            "raw_entity": str(raw_entity),
            "clean_entity": str(entity),
            "question": str(question),
            "primary_type": str(row.get("primary_type", "")),
            "notes": str(row.get("notes", "")),
            "languages": {}
        }

        # Step 1: always fetch English page first
        en_url = get_wikipedia_url("en", entity)
        en_html = get_html(en_url)

        if en_html is None:
            print(f"  English page missing: {en_url}")
            metadata["languages"]["en"] = {
                "url": en_url,
                "status": "missing_article"
            }

            os.makedirs(case_folder, exist_ok=True)

            keep, drop_reasons = evaluate_case(metadata)
            metadata["keep"] = keep
            metadata["drop_reasons"] = drop_reasons

            case_record = {
                "id": metadata["id"],
                "entity": metadata["clean_entity"],
                "question": metadata["question"],
                "keep": keep,
                "drop_reasons": "; ".join(drop_reasons)
            }

            for lang in LANGS:
                lang_info = metadata["languages"].get(lang, {})
                case_record[f"{lang}_status"] = lang_info.get("status", "missing")
                case_record[f"{lang}_lead_sentences"] = lang_info.get("lead_sentences", 0)
                case_record[f"{lang}_url"] = lang_info.get("url", "")

            dropped_cases.append(case_record)

            with open(os.path.join(case_folder, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            continue

        # Save English page
        en_lead, en_infobox = extract_lead_and_infobox(en_html)
        save_case_language(case_folder, "en", en_lead, en_infobox)

        metadata["languages"]["en"] = {
            "url": en_url,
            "status": "scraped",
            "lead_chars": len(en_lead),
            "lead_sentences": count_sentences(en_lead),
            "has_infobox": bool(en_infobox)
        }

        print(f"  en saved. Lead chars: {len(en_lead)}, Infobox: {bool(en_infobox)}")

        # Step 2: use English page language links to find zh/ko/ru pages
        lang_links = extract_language_links(en_html)

        for lang in ["zh", "ko", "ru"]:
            print(f"  Fetching {lang} Wikipedia...")

            if lang not in lang_links:
                print(f"    No {lang} language link found")
                metadata["languages"][lang] = {
                    "url": None,
                    "status": "missing_language_link"
                }
                continue

            url = lang_links[lang]
            html = get_html(url)

            if html is None:
                print(f"    Missing article: {url}")
                metadata["languages"][lang] = {
                    "url": url,
                    "status": "missing_article"
                }
                continue

            lead_text, infobox_text = extract_lead_and_infobox(html)
            save_case_language(case_folder, lang, lead_text, infobox_text)

            metadata["languages"][lang] = {
                "url": url,
                "status": "scraped",
                "lead_chars": len(lead_text),
                "lead_sentences": count_sentences(lead_text),
                "has_infobox": bool(infobox_text)
            }

            print(f"    Saved. Lead chars: {len(lead_text)}, Infobox: {bool(infobox_text)}")

            time.sleep(0.5)

        keep, drop_reasons = evaluate_case(metadata)

        metadata["keep"] = keep
        metadata["drop_reasons"] = drop_reasons

        case_record = {
            "id": metadata["id"],
            "entity": metadata["clean_entity"],
            "question": metadata["question"],
            "keep": keep,
            "drop_reasons": "; ".join(drop_reasons)
        }

        for lang in LANGS:
            lang_info = metadata["languages"].get(lang, {})
            case_record[f"{lang}_status"] = lang_info.get("status", "missing")
            case_record[f"{lang}_lead_sentences"] = lang_info.get("lead_sentences", 0)
            case_record[f"{lang}_url"] = lang_info.get("url", "")

        if keep:
            kept_cases.append(case_record)
        else:
            dropped_cases.append(case_record)

        with open(os.path.join(case_folder, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    kept_df = pd.DataFrame(kept_cases)
    dropped_df = pd.DataFrame(dropped_cases)

    os.makedirs("weak_set", exist_ok=True)

    kept_df.to_csv("weak_set/kept_cases.csv", index=False)
    dropped_df.to_csv("weak_set/drop_log.csv", index=False)

    total = len(kept_cases) + len(dropped_cases)
    dropped = len(dropped_cases)
    kept = len(kept_cases)
    drop_rate = dropped / total if total > 0 else 0

    summary = {
        "total_candidates": total,
        "kept_cases": kept,
        "dropped_cases": dropped,
        "drop_rate": drop_rate
    }

    with open("weak_set/drop_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n==============================")
    print("SCRAPE + FILTER SUMMARY")
    print("==============================")
    print(f"Total candidates: {total}")
    print(f"Kept cases: {kept}")
    print(f"Dropped cases: {dropped}")
    print(f"Drop rate: {drop_rate:.2%}")
    print("Saved:")
    print("  weak_set/kept_cases.csv")
    print("  weak_set/drop_log.csv")
    print("  weak_set/drop_summary.json")

if __name__ == "__main__":
    scrape(test_rows=None)