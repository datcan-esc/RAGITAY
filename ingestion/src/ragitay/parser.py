from __future__ import annotations

import re
from datetime import datetime
from html import unescape


TURKISH_TRANSLATION_TABLE = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "C",
        "Ğ": "G",
        "İ": "I",
        "Ö": "O",
        "Ş": "S",
        "Ü": "U",
    }
)

LETTERED_SECTION_RE = re.compile(r"(?m)^([A-ZÇĞİÖŞÜ]\)\s+[^\n:]+):")
LABELED_SECTION_RE = re.compile(
    r"(?m)^((?:TALEP|CEVAP|DAVA|SAVUNMA|DELİLLER VE GEREKÇE|DELİLLERİN DEĞERLENDİRİLMESİ VE GEREKÇE|GEREKÇE|KARAR|SONUÇ|HÜKÜM))\s*[:/]"
)
OUTCOME_RE = re.compile(
    r"\b(bozulmasına|onanmasına|düzeltilerek onanmasına|reddine|kabulüne|kısmen kabulüne)\b",
    re.IGNORECASE,
)
MAHKEME_RE = re.compile(r"MAHKEMES[İI]\s*:\s*(.+)")


def slugify(value: str) -> str:
    normalized = value.translate(TURKISH_TRANSLATION_TABLE).lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-") or "query"


def normalize_date(date_str: str) -> str:
    if not date_str:
        return ""

    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


def sanitize_text(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|li|ul|body|head|div|tr|td|table|font|b)>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return sanitize_text(text)


def extract_trial_court(text: str) -> str:
    match = MAHKEME_RE.search(text)
    if match:
        return match.group(1).strip()

    for line in text.splitlines():
        cleaned = line.strip()
        upper_cleaned = cleaned.upper()
        if "MAHKEMESI" in upper_cleaned or "MAHKEMESİ" in upper_cleaned:
            return cleaned

    return ""


def extract_title(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def extract_sections(text: str) -> dict[str, str]:
    matches = list(LETTERED_SECTION_RE.finditer(text))
    matches.extend(LABELED_SECTION_RE.finditer(text))
    matches.sort(key=lambda match: match.start())
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[content_start:content_end].strip()

        if ")" in heading:
            key_text = heading.split(")", 1)[1].strip()
        else:
            key_text = heading.strip()
        key = slugify(key_text).replace("-", "_")
        sections[key] = content

    return sections


def extract_outcome(text: str) -> str:
    match = OUTCOME_RE.search(text)
    return match.group(1).upper() if match else ""
