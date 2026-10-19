"""Catalog search: relevance ranking and typo tolerance.

Pure Python over product DTOs, so it behaves the same on SQLite (local, tests)
and Postgres (production). Comfortable for catalogs of a few thousand
products; beyond that, move ranking into Postgres full-text search.

Every search word must match somewhere (name, category or description).
Matches in the name count most, then category, then description. Words that
match nothing are corrected to the closest catalog word ("hodie" -> "hoodie").
"""

import difflib
import re
import unicodedata

WORD = re.compile(r"[a-z0-9]+")

# Points per search word, best match per field.
NAME_EXACT, NAME_PREFIX, NAME_PART = 12, 8, 4
CATEGORY_MATCH = 5
DESCRIPTION_MATCH = 1
CORRECTION_CUTOFF = 0.75  # how similar a typo must be to a real word (0-1)


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return WORD.findall(text.lower())


def _fields(product):
    return (
        normalize(product.name),
        normalize(product.category.name) if product.category else [],
        normalize(product.description),
    )


def _word_score(term, name, category, description):
    if term in name:
        return NAME_EXACT
    if any(w.startswith(term) for w in name):
        return NAME_PREFIX
    if any(term in w for w in name):
        return NAME_PART
    if any(w.startswith(term) for w in category):
        return CATEGORY_MATCH
    if any(w.startswith(term) for w in description):
        return DESCRIPTION_MATCH
    return 0


def score(product, terms):
    """Relevance of a product for search terms; 0 means "not a match"."""
    name, category, description = _fields(product)
    total = 0
    for term in terms:
        points = _word_score(term, name, category, description)
        if not points:
            return 0
        total += points
    return total


def vocabulary(products):
    words = set()
    for product in products:
        for field in _fields(product):
            words.update(w for w in field if len(w) > 2)
    return words


def correct(terms, words):
    """Replaces terms that match no catalog word with the closest one.

    Returns the corrected terms, or None if nothing needed (or could be) fixed.
    """
    corrected, changed = [], False
    for term in terms:
        if any(w.startswith(term) or term in w for w in words):
            corrected.append(term)
            continue
        match = difflib.get_close_matches(term, words, n=1, cutoff=CORRECTION_CUTOFF)
        if match:
            corrected.append(match[0])
            changed = True
        else:
            corrected.append(term)
    return corrected if changed else None


def search(products, query, allow_correction=True):
    """Ranks products for a query.

    Returns (ranked_products, corrected_query). corrected_query is the query
    actually used when the original had typos and found nothing, else None.
    """
    terms = normalize(query)
    if not terms:
        return list(products), None

    def ranked(search_terms):
        scored = [(score(p, search_terms), p) for p in products]
        return [p for s, p in sorted(scored, key=lambda sp: -sp[0]) if s > 0]

    results = ranked(terms)
    if results or not allow_correction:
        return results, None

    fixed = correct(terms, vocabulary(products))
    if fixed:
        return ranked(fixed), " ".join(fixed)
    return [], None
