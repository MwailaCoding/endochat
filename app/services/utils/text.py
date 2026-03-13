"""Text processing utilities."""

import hashlib
import re
from typing import Optional


def normalize_question(question: str) -> str:
    """Normalize question text for comparison and caching."""
    normalized = question.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s?]', '', normalized)
    return normalized


def generate_cache_hash(question: str, context: str = "") -> str:
    """Generate MD5 hash for cache keys."""
    normalized = normalize_question(question)
    combined = f"{normalized}|{context}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def truncate_text(
    text: str,
    max_length: int = 500,
    suffix: str = "...",
) -> str:
    """Truncate text to max length at word boundary."""
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > max_length * 0.7:
        return truncated[:last_space] + suffix
    return truncated + suffix


def extract_keywords(text: str, min_length: int = 3) -> list[str]:
    """Extract keywords from text."""
    stop_words = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
        "in", "with", "to", "for", "of", "from", "by", "as", "are", "was",
        "were", "been", "be", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can", "this",
        "that", "these", "those", "it", "its", "what", "how", "when", "where",
        "why", "who", "i", "me", "my", "we", "our", "you", "your"
    }

    words = re.findall(r'\b[a-z]+\b', text.lower())
    keywords = [w for w in words if len(w) >= min_length and w not in stop_words]

    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique


def clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def sentence_split(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def get_first_sentences(text: str, count: int = 2) -> str:
    """Get first N sentences from text."""
    sentences = sentence_split(text)
    return " ".join(sentences[:count])


def calculate_word_overlap(text1: str, text2: str) -> float:
    """Calculate word overlap ratio between two texts."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0
