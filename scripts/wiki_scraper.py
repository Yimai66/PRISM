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
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "sup"]):
        tag.decompose()

    infobox_text = ""
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if infobox:
        infobox_text = infobox.get_text("\n", strip=True)

    content = soup.find("div", {"id": "mw-content-text"})
    lead_paragraphs = []

    if content:
        parser_output = content.find("div", class_="mw-parser-output")

        if parser_output:
            for child in parser_output.children:
                name = getattr(child, "name", None)

                if name == "h2":
                    break

                if name == "div" and child.get("class") and "mw-heading" in child.get("class"):
                    break

                if name == "p":
                    text = child.get_text(" ", strip=True)
                    if text:
                        lead_paragraphs.append(text)

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

            with open(os.path.join(case_folder, "metadata.json"), "w", encoding="utf-8") as f:
                os.makedirs(case_folder, exist_ok=True)
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            continue

        # Save English page
        en_lead, en_infobox = extract_lead_and_infobox(en_html)
        save_case_language(case_folder, "en", en_lead, en_infobox)

        metadata["languages"]["en"] = {
            "url": en_url,
            "status": "scraped",
            "lead_chars": len(en_lead),
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
                "has_infobox": bool(infobox_text)
            }

            print(f"    Saved. Lead chars: {len(lead_text)}, Infobox: {bool(infobox_text)}")

            time.sleep(0.5)

        with open(os.path.join(case_folder, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    scrape(test_rows=10)