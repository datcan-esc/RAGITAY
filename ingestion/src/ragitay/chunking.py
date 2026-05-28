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


def normalize_chunk_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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
    for chunk in chunks:
        if merged and len(chunk) < min_chunk_chars:
            candidate = f"{merged[-1]}\n\n{chunk}".strip()
            if len(candidate) <= max_chars + overlap_chars:
                merged[-1] = candidate
                continue
        merged.append(chunk)
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
        section_items = [("full_text", normalize_chunk_text(full_text))]

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
