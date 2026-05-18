"""
PRISM Role 1 Prototype — patched version with multi-provider LLM support.

Changes from original:
- Adds Anthropic Claude as an alternative LLM provider (free tier available).
- Auto-detects which API key is present (ANTHROPIC_API_KEY preferred, then OPENAI_API_KEY).
- LLM failures gracefully fall back to mock with a visible UI warning, so the demo never crashes.
- All original behavior (mock mode, Brave Search, translation) is preserved.

How to enable live LLM:
- Easiest path: sign up at console.anthropic.com, create an API key, put it in .env as
  ANTHROPIC_API_KEY=sk-ant-...
  Then set USE_LIVE_LLM=true in .env. Done.
- Alternative: keep using OpenAI with OPENAI_API_KEY=sk-... (requires $5 minimum deposit).
"""

import os
import json
from typing import Dict, List, Any

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# Optional providers — imported lazily so the app still runs if libs aren't installed.
try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # type: ignore

try:
    import anthropic  # type: ignore
except ImportError:
    anthropic = None  # type: ignore


load_dotenv()

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_LIVE_SEARCH = os.getenv("USE_LIVE_SEARCH", "false").lower() == "true"
USE_LIVE_TRANSLATION = os.getenv("USE_LIVE_TRANSLATION", "false").lower() == "true"
USE_LIVE_LLM = os.getenv("USE_LIVE_LLM", "false").lower() == "true"

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

# LLM provider config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()  # "auto" | "anthropic" | "openai"


LANGUAGE_CODES = {
    "English": {"deepl": "EN", "search": "en", "region": "US"},
    "Chinese": {"deepl": "ZH", "search": "zh-hans", "region": "CN"},
    "German": {"deepl": "DE", "search": "de", "region": "DE"},
    "French": {"deepl": "FR", "search": "fr", "region": "FR"},
    "Spanish": {"deepl": "ES", "search": "es", "region": "ES"},
    "Russian": {"deepl": "RU", "search": "ru", "region": "RU"},
    "Greek": {"deepl": "EL", "search": "el", "region": "GR"},
    "Korean": {"deepl": "KO", "search": "ko", "region": "KR"},
    "Italian": {"deepl": "IT", "search": "it", "region": "IT"},
    "Icelandic": {"deepl": "IS", "search": "en", "region": "IS"},
}

LANGUAGES = list(LANGUAGE_CODES.keys())

DEMO_QUESTIONS = [
    "When did World War II start?",
    "Who invented the printing press?",
    "Who won the War of 1812?",
    "What caused the Opium Wars?",
    "When did the Roman Empire fall?",
    "Who discovered America?",
]

CASE_LANGUAGE_MAP = {
    "When did World War II start?": ["English", "Chinese", "Russian"],
    "Who invented the printing press?": ["English", "Chinese", "Korean", "German"],
    "Who won the War of 1812?": ["English"],
    "What caused the Opium Wars?": ["English", "Chinese", "French"],
    "When did the Roman Empire fall?": ["English", "Greek", "Italian"],
    "Who discovered America?": ["English", "Spanish", "Icelandic"],
}

TAXONOMY = """
Type A — Factual Divergence: different concrete facts such as dates, numbers, or names for the same event.
Type B — Attribution: different people, places, or cultures credited with the same invention or discovery.
Type C — Outcome: different winners, losers, or end-states described.
Type D — Framing: same facts, but different emphasized causes, motives, or significance.
Type E — Definitional Boundary: the same name is used for entities or periods that are bounded differently.
Type F — Omission: information central to one source is absent in another. This is not the same as contradiction.
"""

MOCK_TRANSLATIONS = {
    "When did World War II start?": {
        "English": "When did World War II start?",
        "Chinese": "第二次世界大战什么时候开始？",
        "Russian": "Когда началась Вторая мировая война?",
    },
    "Who invented the printing press?": {
        "English": "Who invented the printing press?",
        "Chinese": "谁发明了活字印刷术？",
        "Korean": "누가 인쇄술을 발명했는가?",
        "German": "Wer erfand den Buchdruck?",
    },
    "Who won the War of 1812?": {
        "English": "Who won the War of 1812?",
    },
    "What caused the Opium Wars?": {
        "English": "What caused the Opium Wars?",
        "Chinese": "鸦片战争的起因是什么？",
        "French": "Quelles sont les causes des guerres de l'opium ?",
    },
    "When did the Roman Empire fall?": {
        "English": "When did the Roman Empire fall?",
        "Greek": "Πότε έπεσε η Ρωμαϊκή Αυτοκρατορία;",
        "Italian": "Quando cadde l'Impero romano?",
    },
    "Who discovered America?": {
        "English": "Who discovered America?",
        "Spanish": "¿Quién descubrió América?",
        "Icelandic": "Hver uppgötvaði Ameríku?",
    },
}

MOCK_RESULTS = [
    {"title": "Sample result title", "url": "https://example.com", "description": "This is a mock search result used for interface testing."},
    {"title": "Another sample source", "url": "https://example.org", "description": "Replace mock mode with live API calls for final testing."},
]

MOCK_CASE_RESULTS = {
    "When did World War II start?": {
        "English": [
            {"title": "World War II", "url": "https://en.wikipedia.org/wiki/World_War_II",
             "description": "Frames World War II as beginning on 1 September 1939, with Germany's invasion of Poland."},
            {"title": "German invasion of Poland", "url": "https://en.wikipedia.org/wiki/Invasion_of_Poland",
             "description": "Presents the invasion of Poland as the immediate event that triggered the European war."},
        ],
        "Chinese": [
            {"title": "第二次世界大战", "url": "https://zh.wikipedia.org/wiki/第二次世界大战",
             "description": "Mentions the common 1939 start date, but also notes the view that the war began in 1937 with the Marco Polo Bridge Incident."},
            {"title": "七七事变", "url": "https://zh.wikipedia.org/wiki/七七事变",
             "description": "Connects the beginning of full-scale war in China to 7 July 1937."},
        ],
        "Russian": [
            {"title": "Великая Отечественная война", "url": "https://ru.wikipedia.org/wiki/Великая_Отечественная_война",
             "description": "Frames 1941–1945 as the Great Patriotic War, the Soviet phase treated as central in Russian memory."},
            {"title": "Вторая мировая война", "url": "https://ru.wikipedia.org/wiki/Вторая_мировая_война",
             "description": "Also recognizes 1939 for World War II, but Russian-language memory strongly foregrounds 1941."},
        ],
    },
    "When did the Roman Empire fall?": {
        "English": [
            {"title": "Fall of the Western Roman Empire", "url": "https://en.wikipedia.org/wiki/Fall_of_the_Western_Roman_Empire",
             "description": "Uses 476 CE and the deposition of Romulus Augustulus as the conventional fall of Rome."},
            {"title": "Romulus Augustulus", "url": "https://en.wikipedia.org/wiki/Romulus_Augustulus",
             "description": "Links the fall to the last Western Roman emperor and Odoacer's takeover."},
        ],
        "Greek": [
            {"title": "Ρωμαϊκή Αυτοκρατορία", "url": "https://el.wikipedia.org/wiki/Ρωμαϊκή_Αυτοκρατορία",
             "description": "Mentions 476 for the Western Empire but also treats the Eastern Roman Empire as continuing until Constantinople fell in 1453."},
            {"title": "Άλωση της Κωνσταντινούπολης", "url": "https://el.wikipedia.org/wiki/Άλωση_της_Κωνσταντινούπολης",
             "description": "Connects the end of the Eastern Roman Empire to 1453."},
        ],
        "Italian": [
            {"title": "Caduta dell'Impero romano d'Occidente", "url": "https://it.wikipedia.org/wiki/Caduta_dell%27Impero_romano_d%27Occidente",
             "description": "Frames the fall as a long historical process, conventionally ending in 476."},
            {"title": "Impero romano d'Occidente", "url": "https://it.wikipedia.org/wiki/Impero_romano_d%27Occidente",
             "description": "Focuses specifically on the Western Roman Empire rather than the whole Roman imperial tradition."},
        ],
    },
    "What caused the Opium Wars?": {
        "English": [
            {"title": "First Opium War", "url": "https://en.wikipedia.org/wiki/First_Opium_War",
             "description": "Frames the war as arising from opium enforcement, trade, diplomatic relations, and British demands for equal recognition."},
            {"title": "Opium Wars", "url": "https://en.wikipedia.org/wiki/Opium_Wars",
             "description": "Discusses the conflicts through trade, diplomacy, and imperial expansion."},
        ],
        "Chinese": [
            {"title": "第一次鸦片战争", "url": "https://zh.wikipedia.org/wiki/第一次鸦片战争",
             "description": "Frames the war as a British war against Qing China, triggered by anti-opium enforcement and resulting in the unequal Treaty of Nanjing."},
            {"title": "南京条约", "url": "https://zh.wikipedia.org/wiki/南京条约",
             "description": "Emphasizes defeat, unequal treaty, cession of Hong Kong Island, and treaty ports."},
        ],
        "French": [
            {"title": "Guerres de l'opium", "url": "https://fr.wikipedia.org/wiki/Guerres_de_l%27opium",
             "description": "Frames the conflicts as commercially motivated wars over the opium trade between China and the United Kingdom."},
            {"title": "Première guerre de l'opium", "url": "https://fr.wikipedia.org/wiki/Première_guerre_de_l%27opium",
             "description": "Places trade and the imposition of opium commerce near the center of the explanation."},
        ],
    },
    "Who discovered America?": {
        "English": [
            {"title": "Christopher Columbus", "url": "https://en.wikipedia.org/wiki/Christopher_Columbus",
             "description": "Describes Columbus's voyages as opening the way for European exploration and colonization of the Americas."},
            {"title": "European colonization of the Americas", "url": "https://en.wikipedia.org/wiki/European_colonization_of_the_Americas",
             "description": "Frames 1492 as a major turning point in European contact with the Americas."},
        ],
        "Spanish": [
            {"title": "Cristóbal Colón", "url": "https://es.wikipedia.org/wiki/Cristóbal_Colón",
             "description": "Uses the phrase Discovery of America and names Columbus's arrival in 1492."},
            {"title": "Descubrimiento de América", "url": "https://es.wikipedia.org/wiki/Descubrimiento_de_América",
             "description": "Frames the event through the Spanish-language tradition of discovery."},
        ],
        "Icelandic": [
            {"title": "Leifur Eiríksson", "url": "https://is.wikipedia.org/wiki/Leifur_Eiríksson",
             "description": "Credits Leif Erikson as the first European to set foot on mainland North America around the year 1000."},
            {"title": "Vínland", "url": "https://is.wikipedia.org/wiki/Vínland",
             "description": "Connects Norse exploration to North America before Columbus."},
        ],
    },
    "Who won the War of 1812?": {
        "English": [
            {"title": "War of 1812", "url": "https://en.wikipedia.org/wiki/War_of_1812",
             "description": "Frames the war as ending with the Treaty of Ghent and a restoration of the status quo ante bellum, making a simple winner/loser answer difficult."},
            {"title": "The Canadian Encyclopedia, War of 1812", "url": "https://www.thecanadianencyclopedia.ca/en/article/war-of-1812",
             "description": "Frames the war as important for Canadian identity and the defense of Canada against American invasion."},
            {"title": "British framing of the War of 1812", "url": "https://www.britannica.com/event/War-of-1812",
             "description": "Frames the war as a secondary theatre within the larger Napoleonic Wars, with Britain focused primarily on Europe."},
        ],
    },
    "Who invented the printing press?": {
        "English": [
            {"title": "Printing press", "url": "https://en.wikipedia.org/wiki/Printing_press",
             "description": "Credits Johannes Gutenberg with inventing the printing press in the Holy Roman Empire around 1440."},
            {"title": "Johannes Gutenberg", "url": "https://en.wikipedia.org/wiki/Johannes_Gutenberg",
             "description": "Presents Gutenberg as the key figure associated with the European printing press."},
        ],
        "Chinese": [
            {"title": "活字印刷术", "url": "https://zh.wikipedia.org/wiki/活字印刷术",
             "description": "Foregrounds Bi Sheng's invention of clay movable type during the Song dynasty around 1041–1048."},
            {"title": "毕昇", "url": "https://zh.wikipedia.org/wiki/毕昇",
             "description": "Credits Bi Sheng as the Chinese inventor of movable-type printing."},
        ],
        "Korean": [
            {"title": "직지심체요절", "url": "https://ko.wikipedia.org/wiki/직지심체요절",
             "description": "Highlights Jikji, printed in 1377 with metal movable type, as the oldest extant metal movable-type book."},
            {"title": "금속활자", "url": "https://ko.wikipedia.org/wiki/금속활자",
             "description": "Emphasizes Korean metal movable type and surviving printed artifacts."},
        ],
        "German": [
            {"title": "Johannes Gutenberg", "url": "https://de.wikipedia.org/wiki/Johannes_Gutenberg",
             "description": "Presents Gutenberg as a German inventor of printing with movable metal type and the printing press."},
            {"title": "Buchdruck", "url": "https://de.wikipedia.org/wiki/Buchdruck",
             "description": "Frames Gutenberg as central to the history of European book printing."},
        ],
    },
}


def identify_original_question_from_query(query: str) -> str | None:
    """Find the original Role 2 demo question from a translated query."""
    for original_question, translations in MOCK_TRANSLATIONS.items():
        if query in translations.values():
            return original_question
    return None


MOCK_DISAGREEMENTS = {
    "When did World War II start?": {
        "labels": ["Type A — Factual Divergence", "Type E — Definitional Boundary"],
        "summary": "The language results foreground different start points: 1939 in English, 1937 as an alternative frame in Chinese, and 1941 as the Soviet-centered frame in Russian.",
        "omission_notes": "Each language frame risks omitting a start date central to another historical memory.",
        "confidence": "mock output based on Role 2 Case Book",
    },
    "Who invented the printing press?": {
        "labels": ["Type B — Attribution", "Type F — Omission"],
        "summary": "The results credit different people or traditions with the invention: Gutenberg in English and German, Bi Sheng in Chinese, and Korean metal movable-type history through Jikji in Korean.",
        "omission_notes": "Some language results foreground one inventor or artifact while omitting figures that are central in other language traditions.",
        "confidence": "mock output based on Role 2 Case Book",
    },
    "What caused the Opium Wars?": {
        "labels": ["Type D — Framing"],
        "summary": "The results agree on the broad historical events but frame causality differently. English-language framing often emphasizes trade, diplomacy, and legal recognition, while Chinese-language framing foregrounds British aggression, opium suppression, and unequal treaties. French framing places commercial conflict and the opium trade near the center.",
        "omission_notes": "The disagreement is less about missing facts and more about which cause is placed at the center of the story.",
        "confidence": "mock output based on Role 2 Case Book",
    },
    "Who discovered America?": {
        "labels": ["Type B — Attribution", "Type D — Framing", "Type F — Omission"],
        "summary": "The results differ not only in who is credited, but also in whether the question itself is legitimate. Spanish-language framing foregrounds Columbus, Icelandic framing foregrounds Leif Erikson, while Indigenous-perspective sources challenge the discovery premise altogether.",
        "omission_notes": "A Columbus-centered result may omit earlier Norse contact or the prior existence of Indigenous peoples in the Americas.",
        "confidence": "mock output based on Role 2 Case Book",
    },
    "Who won the War of 1812?": {
        "labels": ["Type C — Outcome", "Type D — Framing"],
        "summary": "The case does not produce one simple winner. Different traditions frame the outcome differently: as a restoration of the pre-war status quo, as a successful defense of Canada, or as a minor theatre within the larger Napoleonic Wars. The disagreement is therefore partly about outcome and partly about national framing.",
        "omission_notes": "A single-language result may omit how other national traditions interpret the war's significance, especially the Canadian identity-building frame or the British Napoleonic-war frame.",
        "confidence": "mock output based on Role 2 Case Book",
    },
    "When did the Roman Empire fall?": {
        "labels": ["Type E — Definitional Boundary", "Type D — Framing"],
        "summary": "The results define the Roman Empire differently. English and Italian results focus on the Western Roman Empire and the conventional date 476, while Greek results also treat the Eastern Roman Empire as continuing until Constantinople fell in 1453.",
        "omission_notes": "A Western-focused result may omit the Eastern Roman continuation that is central in Greek-language framing.",
        "confidence": "mock output based on Role 2 Case Book",
    },
}


def translate_query(question: str, target_language: str) -> str:
    """Translate the user query with DeepL, or use mock translation when live translation is disabled."""
    if target_language == "English":
        return question

    if not USE_LIVE_TRANSLATION:
        return MOCK_TRANSLATIONS.get(question, {}).get(
            target_language,
            f"[{target_language} translation of] {question}",
        )

    if not DEEPL_API_KEY:
        raise RuntimeError("Missing DEEPL_API_KEY. Use USE_LIVE_TRANSLATION=false or add a DeepL API key.")

    target_lang = LANGUAGE_CODES[target_language]["deepl"]
    response = requests.post(
        "https://api-free.deepl.com/v2/translate",
        data={
            "auth_key": DEEPL_API_KEY,
            "text": question,
            "target_lang": target_lang,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["translations"][0]["text"]


def search_web(query: str, language: str, count: int = 3) -> List[Dict[str, str]]:
    """Search the web using Brave Search API, or use mock results when live search is disabled/fails."""
    original_question = identify_original_question_from_query(query)

    def fallback_results() -> List[Dict[str, str]]:
        if original_question:
            case_results = MOCK_CASE_RESULTS.get(original_question, {}).get(language)
            if case_results:
                return case_results[:count]
        return [
            {
                **item,
                "description": f"{item['description']} Query: {query} | Language: {language}",
            }
            for item in MOCK_RESULTS[:count]
        ]

    if not USE_LIVE_SEARCH:
        return fallback_results()

    if not BRAVE_API_KEY:
        raise RuntimeError("Missing BRAVE_API_KEY. Use USE_LIVE_SEARCH=false or add a Brave API key.")

    lang_info = LANGUAGE_CODES[language]

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            params={
                "q": query,
                "count": count,
                "search_lang": lang_info["search"],
                "country": lang_info["region"],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("web", {}).get("results", [])
        return [
            {
                "title": item.get("title", "Untitled"),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
            for item in results
        ]
    except requests.exceptions.RequestException as exc:
        return [
            {
                "title": f"Live search unavailable for {language}; using Case Book fallback",
                "url": "",
                "description": f"Brave Search returned an error for this language/context: {exc}",
            },
            *fallback_results(),
        ][:count]


def build_llm_input(question: str, translated_queries: Dict[str, str], results_by_language: Dict[str, List[Dict[str, str]]]) -> str:
    blocks = []
    for language, results in results_by_language.items():
        result_lines = []
        for i, result in enumerate(results, start=1):
            result_lines.append(
                f"{i}. Title: {result['title']}\nURL: {result['url']}\nSnippet: {result['description']}"
            )
        blocks.append(
            f"LANGUAGE: {language}\nTRANSLATED QUERY: {translated_queries[language]}\nRESULTS:\n" + "\n".join(result_lines)
        )
    return "\n\n---\n\n".join(blocks)


SYSTEM_PROMPT = f"""You are the disagreement-detection layer for PRISM, a cross-language search prototype.

Your task: compare the language-specific result panels and identify where they differ.
Do NOT synthesize all language results into a single final answer.

Classify the disagreement using one or more of the following labels (use the exact label strings, including the "Type X" prefix):

{TAXONOMY}

Pay special attention to Type F (Omission). A source being silent about a fact is NOT the same as contradicting it.
If you see different language sources focused on different facts, that may be Type F even when nothing directly contradicts.

Return your answer as STRICT, VALID JSON with exactly these keys and no others:
  - "labels": list of strings, each one a full type label such as "Type A — Factual Divergence"
  - "summary": one short paragraph (3–5 sentences) comparing the language panels
  - "omission_notes": one short paragraph specifically about what each panel leaves out
  - "confidence": one of "high", "medium", "low" (your confidence in the classification)

Output ONLY the JSON. No prose before or after."""


def _parse_llm_json(content: str) -> Dict[str, Any]:
    """Parse LLM output as JSON. Strip code fences if present. Return a safe dict on failure."""
    text = content.strip()
    # Strip markdown code fences (e.g. ```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "labels": ["LLM output could not be parsed"],
            "summary": content,
            "omission_notes": "The LLM response was not valid JSON.",
            "confidence": "low",
        }


def _detect_with_openai(source_text: str) -> Dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": source_text},
        ],
        temperature=0.2,
    )
    return _parse_llm_json(response.choices[0].message.content)


def _detect_with_anthropic(source_text: str) -> Dict[str, Any]:
    if anthropic is None:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": source_text}],
    )
    # Anthropic returns a list of content blocks; the text one carries the JSON.
    text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return _parse_llm_json("".join(text_blocks))


def detect_disagreement(question: str, translated_queries: Dict[str, str], results_by_language: Dict[str, List[Dict[str, str]]]) -> Dict[str, object]:
    """Classify cross-language disagreement types.

    Strategy:
      1. If USE_LIVE_LLM=false, return the Case Book mock.
      2. Otherwise, try the configured provider (or auto-select).
      3. If the provider call fails for any reason, gracefully fall back to mock
         and add a fallback_note so the UI can display a warning.
    """

    if not USE_LIVE_LLM:
        analysis = MOCK_DISAGREEMENTS.get(question, {
            "labels": ["No mock disagreement defined"],
            "summary": "This custom question does not yet have a case-specific mock disagreement analysis.",
            "omission_notes": "No omission analysis available in mock mode.",
            "confidence": "low / mock output",
        })
        return {**analysis, "_source": "mock (USE_LIVE_LLM=false)"}

    source_text = build_llm_input(question, translated_queries, results_by_language)

    # Determine provider order
    if LLM_PROVIDER == "anthropic":
        provider_order = ["anthropic"]
    elif LLM_PROVIDER == "openai":
        provider_order = ["openai"]
    else:  # "auto"
        provider_order = []
        if ANTHROPIC_API_KEY:
            provider_order.append("anthropic")
        if OPENAI_API_KEY:
            provider_order.append("openai")

    if not provider_order:
        analysis = MOCK_DISAGREEMENTS.get(question, {
            "labels": ["Mock fallback (no LLM key)"],
            "summary": "No LLM API key was found. Showing Case Book mock instead.",
            "omission_notes": "Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env to enable live detection.",
            "confidence": "low / mock fallback",
        })
        return {**analysis, "_source": "mock (no API key found)"}

    last_error = None
    for provider in provider_order:
        try:
            if provider == "anthropic":
                analysis = _detect_with_anthropic(source_text)
                return {**analysis, "_source": f"live LLM ({ANTHROPIC_MODEL} via Anthropic)"}
            elif provider == "openai":
                analysis = _detect_with_openai(source_text)
                return {**analysis, "_source": f"live LLM ({OPENAI_MODEL} via OpenAI)"}
        except Exception as exc:
            last_error = f"{provider}: {exc}"

    # All providers failed: fall back to mock with a clear notice
    analysis = MOCK_DISAGREEMENTS.get(question, {
        "labels": ["Mock fallback after LLM error"],
        "summary": "Live LLM call failed. Showing Case Book mock so the demo can continue.",
        "omission_notes": "Check the API key and console for the error message.",
        "confidence": "low / mock fallback",
    })
    return {**analysis, "_source": f"mock (LLM failed: {last_error})"}


def make_export_rows(question: str, translated_queries: Dict[str, str], results_by_language: Dict[str, List[Dict[str, str]]], analysis: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for language, results in results_by_language.items():
        for rank, result in enumerate(results, start=1):
            rows.append({
                "question": question,
                "language": language,
                "translated_query": translated_queries.get(language, ""),
                "rank": rank,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", ""),
                "auto_labels": "; ".join(analysis.get("labels", [])),
                "llm_summary": analysis.get("summary", ""),
                "omission_notes": analysis.get("omission_notes", ""),
                "confidence": analysis.get("confidence", ""),
                "analysis_source": analysis.get("_source", ""),
            })
    return pd.DataFrame(rows)


# =================== Streamlit UI ===================

st.set_page_config(page_title="PRISM Prototype", layout="wide")
st.title("PRISM: Cross-Language Search Prototype")
st.caption("Role 1 demo: translation → multilingual search → disagreement detection")

with st.sidebar:
    st.header("Settings")
    st.write("Mode:", "Mock mode" if MOCK_MODE else "Live API mode")
    # Show which LLM provider is wired up
    provider_status = []
    if ANTHROPIC_API_KEY:
        provider_status.append(f"Anthropic ({ANTHROPIC_MODEL})")
    if OPENAI_API_KEY:
        provider_status.append(f"OpenAI ({OPENAI_MODEL})")
    if not provider_status:
        provider_status.append("No LLM key — will use mock")
    st.write("LLM provider(s) available:", ", ".join(provider_status))
    st.write("Live LLM:", "ON" if USE_LIVE_LLM else "OFF (using mock)")
    search_count = st.slider("Results per language", min_value=1, max_value=5, value=3)
    st.markdown("### Disagreement taxonomy")
    st.markdown(TAXONOMY)

selected_demo = st.selectbox("Choose a Role 2 demo question or write your own below:", [""] + DEMO_QUESTIONS)
custom_question = st.text_input("Question", value=selected_demo or "Who invented the printing press?")

default_languages = CASE_LANGUAGE_MAP.get(custom_question, ["English", "Chinese", "German"])
selected_languages = st.multiselect(
    "Languages to compare",
    LANGUAGES,
    default=default_languages,
)

run_button = st.button("Run PRISM search", type="primary")

if run_button:
    if not custom_question.strip():
        st.error("Please enter a question.")
    elif not selected_languages:
        st.error("Please select at least one language.")
    else:
        with st.spinner("Translating queries and searching across language contexts..."):
            try:
                translated_queries = {
                    language: translate_query(custom_question, language)
                    for language in selected_languages
                }
                results_by_language = {
                    language: search_web(translated_queries[language], language, count=search_count)
                    for language in selected_languages
                }
            except Exception as exc:
                st.error(f"Translation/search error: {exc}")
                st.stop()

        st.subheader("Translated queries")
        query_cols = st.columns(len(selected_languages))
        for col, language in zip(query_cols, selected_languages):
            with col:
                st.markdown(f"**{language}**")
                st.write(translated_queries[language])

        st.subheader("Side-by-side multilingual search results")
        result_cols = st.columns(len(selected_languages))
        for col, language in zip(result_cols, selected_languages):
            with col:
                st.markdown(f"### {language}")
                for i, result in enumerate(results_by_language[language], start=1):
                    st.markdown(f"**{i}. [{result['title']}]({result['url']})**")
                    st.write(result["description"])

        with st.spinner("Classifying disagreement types..."):
            analysis = detect_disagreement(custom_question, translated_queries, results_by_language)

        st.subheader("Disagreement detection")

        # Show prominent banner if we fell back to mock
        source_note = analysis.get("_source", "")
        if "mock" in source_note.lower():
            st.warning(f"⚠️ Showing mock output. Reason: {source_note}")
        else:
            st.success(f"✅ Live LLM classification. Source: {source_note}")

        st.markdown("**Detected type(s):** " + ", ".join(analysis.get("labels", [])))
        st.markdown("**Comparative summary:**")
        st.write(analysis.get("summary", ""))
        st.markdown("**Omission-specific notes:**")
        st.write(analysis.get("omission_notes", ""))
        st.markdown("**Confidence:** " + str(analysis.get("confidence", "")))

        export_df = make_export_rows(custom_question, translated_queries, results_by_language, analysis)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download results for Role 4 evaluation",
            data=csv_bytes,
            file_name="prism_role1_output.csv",
            mime="text/csv",
        )
        with st.expander("Raw export table"):
            st.dataframe(export_df, use_container_width=True)
