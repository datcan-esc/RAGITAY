from __future__ import annotations

import re
from typing import Iterable


PREFERRED_SECTION_ORDER = [
    "talep",
    "dava",
    "davaci_isteminin_ozeti",
    "davalı_cevabının_ozeti",
    "davali_cevabinin_ozeti",
    "cevap",
    "deliller_ve_gerekce",
    "delillerin_degerlendirilmesi_ve_gerekce",
    "gerekce",
    "karar",
    "hukum",
    "sonuc",
]

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

ROMAN_SECTION_RE = re.compile(r"(?m)^([IVXLC]+\.\s+[^\n]+)$")
LOW_VALUE_PHRASES = (
    "içtihat metni",
    "uyuşmazlığın giderilmesi istemine dair",
    "uyusmazligin giderilmesi istemine dair",
)


def normalize_chunk_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def slugify_section_name(value: str) -> str:
    normalized = value.translate(TURKISH_TRANSLATION_TABLE).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_") or "full_text"


def infer_sections_from_full_text(full_text: str) -> list[tuple[str, str]]:
    normalized = normalize_chunk_text(full_text)
    if not normalized:
        return []

    matches = list(ROMAN_SECTION_RE.finditer(normalized))
    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        heading_line = match.group(1).strip()
        heading_text = heading_line.split(".", 1)[1].strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        content = normalized[start:end].strip()
        if not content:
            continue
        sections.append((slugify_section_name(heading_text), content))
    return sections


def is_low_value_chunk(text: str) -> bool:
    normalized = normalize_chunk_text(text).lower()
    if not normalized:
        return True

    alpha_count = sum(1 for char in normalized if char.isalpha())
    if alpha_count < 60:
        return True

    if len(normalized) < 300 and any(phrase in normalized for phrase in LOW_VALUE_PHRASES):
        return True

    return False


def ordered_sections(sections: dict[str, str]) -> list[tuple[str, str]]:
    if not sections:
        return []

    normalized = {
        str(key).strip(): normalize_chunk_text(str(value))
        for key, value in sections.items()
        if str(value).strip()
    }
    if not normalized:
        return []

    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()

    for key in PREFERRED_SECTION_ORDER:
        if key in normalized:
            ordered.append((key, normalized[key]))
            seen.add(key)

    for key in normalized:
        if key in seen:
            continue
        ordered.append((key, normalized[key]))

    return ordered


def split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(text):
        end = min(len(text), start + max_chars)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks


def paragraph_groups(text: str) -> list[str]:
    normalized = normalize_chunk_text(text)
    if not normalized:
        return []

    groups = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if len(groups) <= 1:
        groups = [part.strip() for part in normalized.split("\n") if part.strip()]
    return groups


def chunk_text(
    text: str,
    *,
    max_chars: int = 1200,
    overlap_chars: int = 200,
    min_chunk_chars: int = 300,
) -> list[str]:
    groups = paragraph_groups(text)
    if not groups:
        return []

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for group in groups:
        if len(group) > max_chars:
            flush()
            chunks.extend(split_long_text(group, max_chars, overlap_chars))
            continue

        candidate = f"{current}\n\n{group}".strip() if current else group
        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush()
        current = group

    flush()

    merged: list[str] = []
    index = 0
    while index < len(chunks):
        chunk = chunks[index]
        if len(chunk) < min_chunk_chars and index + 1 < len(chunks):
            candidate = f"{chunk}\n\n{chunks[index + 1]}".strip()
            if len(candidate) <= max_chars + overlap_chars:
                merged.append(candidate)
                index += 2
                continue

        if merged and len(chunk) < min_chunk_chars:
            candidate = f"{merged[-1]}\n\n{chunk}".strip()
            if len(candidate) <= max_chars + overlap_chars:
                merged[-1] = candidate
                index += 1
                continue

        merged.append(chunk)
        index += 1
    return merged


def build_decision_chunks(
    *,
    title: str,
    full_text: str,
    sections: dict[str, str],
    max_chars: int = 1200,
    overlap_chars: int = 200,
    min_chunk_chars: int = 300,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    chunk_index = 0

    section_items = ordered_sections(sections)
    if not section_items:
        inferred = infer_sections_from_full_text(full_text)
        section_items = inferred if inferred else [("full_text", normalize_chunk_text(full_text))]

    for section_name, section_text in section_items:
        if not section_text:
            continue
        section_chunks = chunk_text(
            section_text,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            min_chunk_chars=min_chunk_chars,
        )
        for piece in section_chunks:
            if is_low_value_chunk(piece):
                continue
            chunk_index += 1
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "section_name": section_name,
                    "chunk_text": piece,
                    "chunk_chars": len(piece),
                }
            )

    if not chunks and title.strip():
        chunks.append(
            {
                "chunk_index": 1,
                "section_name": "title",
                "chunk_text": title.strip(),
                "chunk_chars": len(title.strip()),
            }
        )

    return chunks
