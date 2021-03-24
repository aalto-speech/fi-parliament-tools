"""A simple recipe for testing preprocessor functionality."""

UNACCEPTED_CHARS = r"[^a-zåäöA-ZÅÄÖ \n]"

REGEXPS = [
    # Remove punctuation
    (r"[.,!?':]", r""),
    # Strip any remaining extra spaces
    (r"^\s+", r""),
    (r"\s+", r" "),
    (r" $", r""),
]

TRANSLATIONS = {
    "ß": "ss",
}
