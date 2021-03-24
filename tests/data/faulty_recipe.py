"""A recipe with a faulty regexp for testing preprocessor functionality."""

UNACCEPTED_CHARS = r"[^a-zåäöA-ZÅÄÖ \n]"

REGEXPS = [
    # Remove punctuation
    (r"[.,!?':]", r""),
    # Faulty regexp with an unmatched parenthesis
    (r"(the", r""),
    # Strip any remaining extra spaces
    (r"^\s+", r""),
    (r"\s+", r" "),
    (r" $", r""),
]

TRANSLATIONS = {
    "ß": "ss",
}
