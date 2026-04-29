import re

_GENERIC_SEARCH_WORDS = {
    "analyse",
    "analyze",
    "api",
    "catalog",
    "catalogue",
    "csv",
    "data",
    "database",
    "dataset",
    "datasets",
    "donnee",
    "donnees",
    "donnée",
    "données",
    "excel",
    "fichier",
    "fichiers",
    "find",
    "give",
    "jeu",
    "jeux",
    "json",
    "list",
    "lookup",
    "montre",
    "please",
    "quels",
    "quelles",
    "query",
    "recherche",
    "rechercher",
    "search",
    "show",
    "table",
    "tableau",
    "tableaux",
    "tell",
    "trouve",
    "trouver",
    "xlsx",
    "xml",
}

_QUESTION_WORDS = {
    "a",
    "about",
    "an",
    "are",
    "au",
    "aux",
    "available",
    "avec",
    "ce",
    "ces",
    "comment",
    "dans",
    "de",
    "des",
    "do",
    "est",
    "for",
    "from",
    "have",
    "i",
    "il",
    "in",
    "is",
    "je",
    "la",
    "le",
    "les",
    "me",
    "mes",
    "mon",
    "my",
    "of",
    "on",
    "or",
    "ou",
    "par",
    "pour",
    "que",
    "quel",
    "quelle",
    "quelles",
    "quels",
    "show",
    "sur",
    "the",
    "there",
    "to",
    "un",
    "une",
    "with",
    "you",
}


def clean_search_query(query: str) -> str:
    """
    Clean search query by removing generic stop words that are not typically
    present in dataset metadata but are often added by users.
    """
    stop_words = {
        "données",
        "donnee",
        "donnees",
        "fichier",
        "fichiers",
        "fichier de",
        "fichiers de",
        "tableau",
        "tableaux",
        "csv",
        "excel",
        "xlsx",
        "json",
        "xml",
    }

    words = query.split()
    cleaned_words = [word for word in words if word.lower().strip() not in stop_words]

    cleaned_query = " ".join(cleaned_words)
    return " ".join(cleaned_query.split())


def extract_catalog_query(question: str) -> str:
    """
    Convert a natural-language prompt into a compact keyword-style catalog query.

    The data.gouv.fr search APIs are most useful with short keyword queries. This
    helper keeps the user's domain terms while removing question boilerplate.
    """
    normalized = re.sub(r"[^\w\s'-]+", " ", question, flags=re.UNICODE)
    raw_tokens = normalized.split()
    filtered_tokens: list[str] = []

    for token in raw_tokens:
        cleaned = token.strip(" -_'")
        lowered = cleaned.lower()
        if not cleaned:
            continue
        if lowered in _GENERIC_SEARCH_WORDS or lowered in _QUESTION_WORDS:
            continue
        filtered_tokens.append(cleaned)

    candidate = " ".join(filtered_tokens)
    candidate = clean_search_query(candidate)

    if candidate:
        return candidate

    fallback = clean_search_query(" ".join(raw_tokens))
    return fallback or question.strip()
