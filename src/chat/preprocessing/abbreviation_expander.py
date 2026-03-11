"""
Expand known abbreviations in queries using regex-based replacements.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional
from config.paths import ABBREVIATIONS_PATH


# Cache for abbreviations (loaded once on first use)
_abbreviations_cache: Optional[Dict[str, str]] = None


def load_abbreviations(path: Path) -> Dict[str, str]:
    """Load abbreviation map from JSON once and cache it for reuse."""
    global _abbreviations_cache
    
    if _abbreviations_cache is None:
        with path.open("r", encoding="utf-8") as f:
            _abbreviations_cache = json.load(f)
    
    return _abbreviations_cache


def expand_abbreviations(query: str) -> str:
    """
    Expand known abbreviations in a query using regex replacements.

    Args:
        query: The input query string
    
    Returns:
        The query string with abbreviations expanded
    """

    abbrev_map = load_abbreviations(ABBREVIATIONS_PATH)

    # Skip if empty or no map
    if not query or not abbrev_map:
        return query

    # 1) Module-with-number pattern: M/MO/MOD + digits → Module <n>
    # Negative lookbehind (?<![A-Za-z']) prevents matching after letters or apostrophes (e.g., "I'm 20" should not match the "M" in "I'm")
    module_pattern = re.compile(r"(?<![A-Za-z'])(M|MO|MOD)\s*(\d{1,2})\b", flags=re.IGNORECASE)

    def _replace_module(match: re.Match) -> str:
        """
        Replacement function specifically for "module" patterns.
        """
        num = match.group(2)
        return f"Module {num}"

    query = module_pattern.sub(_replace_module, query)

    # 2) Other abbreviations from the map
    # Sort by length descending to match longer abbreviations first
    items = sorted(abbrev_map.items(), key=lambda kv: len(kv[0]), reverse=True)

    # Build regex patterns for each key with word boundaries
    for key, val in items:
        if not key:
            continue

        # Special-case ITech: allow optional hyphen after the I (i-?tech)
        if key.lower() == "itech":
            pattern = re.compile(r"\bi-?tech\b", flags=re.IGNORECASE)
        # Default: word-boundary match
        else:
            pattern = re.compile(rf"\b{re.escape(key)}\b", flags=re.IGNORECASE)

        def _replace_abbreviation(m: re.Match) -> str:
            """
            Replacement function for known abbreviations.
            """
            token = m.group(0) # The matched token that was found
            # Do not expand "im"/"Im" which are often used as "I'm"
            if key.lower() == "im" and not token.isupper():
                return token
            # Special-case CreaTe: only expand if token is not all lowercase "create" (as this is a common English word)
            if key.lower() == "create" and token.islower():
                return token
            return val # Return the known expansion from the map

        query = pattern.sub(_replace_abbreviation, query) # Replace all occurrences in the query

    return query
