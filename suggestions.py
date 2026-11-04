"""Word completion suggestions from bundled and user word lists."""

import os

WORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'words')
USER_WORDS_DIR = os.path.expanduser('~/.config/osk')

# Which word list each keyboard layout uses
LAYOUT_LANGUAGES = {
    'de': 'de',
    'uk': 'en',
    'us': 'en',
}


def _read_words(path: str) -> list[str]:
    """Read one word per line, skipping blanks and # comments."""
    try:
        with open(path, encoding='utf-8') as f:
            return [line.strip() for line in f
                    if line.strip() and not line.startswith('#')]
    except OSError:
        return []


class WordList:
    """Prefix lookup over a frequency-ordered word list."""

    def __init__(self, language: str):
        # User words (~/.config/osk/words-<lang>.txt) rank above bundled ones
        words = _read_words(os.path.join(USER_WORDS_DIR, f'words-{language}.txt'))
        words += _read_words(os.path.join(WORDS_DIR, f'{language}.txt'))

        self._words: list[tuple[str, str]] = []  # (lowercase, original)
        seen = set()
        for word in words:
            lower = word.lower()
            if lower not in seen:
                seen.add(lower)
                self._words.append((lower, word))

    @classmethod
    def for_layout(cls, layout: str) -> 'WordList':
        return cls(LAYOUT_LANGUAGES.get(layout, 'en'))

    def complete(self, prefix: str, typeable: set[str], limit: int = 3) -> list[str]:
        """
        Return up to `limit` completions for `prefix`, keeping the
        prefix exactly as typed. Words whose remaining letters can't be
        typed on the current layout are skipped.
        """
        if not prefix:
            return []

        lower_prefix = prefix.lower()
        all_caps = len(prefix) > 1 and prefix.isupper()
        results = []

        for lower, word in self._words:
            if len(lower) <= len(lower_prefix) or not lower.startswith(lower_prefix):
                continue
            rest = word[len(prefix):]
            if all_caps:
                rest = rest.upper()
            if all(ch in typeable for ch in rest):
                results.append(prefix + rest)
                if len(results) >= limit:
                    break

        return results
