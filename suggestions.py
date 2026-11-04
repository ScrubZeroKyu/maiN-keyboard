"""Word completion suggestions, ranked by how often the user picks each word."""

import json
import os

WORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'words')
USER_DIR = os.path.expanduser('~/.config/osk')

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
    """
    Prefix lookup over a word list.

    Order: words the user has used most come first; ties keep list order
    (user-added words, then the bundled list from most to least common).
    """

    def __init__(self, language: str):
        self.language = language
        self._user_words_path = os.path.join(USER_DIR, f'words-{language}.txt')
        self._usage_path = os.path.join(USER_DIR, f'word-usage-{language}.json')

        words = _read_words(self._user_words_path)
        words += _read_words(os.path.join(WORDS_DIR, f'{language}.txt'))

        self._words: list[tuple[str, str]] = []  # (lowercase, original)
        self._rank: dict[str, int] = {}
        for word in words:
            lower = word.lower()
            if lower not in self._rank:
                self._rank[lower] = len(self._words)
                self._words.append((lower, word))

        self._usage: dict[str, int] = {}
        try:
            with open(self._usage_path, encoding='utf-8') as f:
                self._usage = {k: int(v) for k, v in json.load(f).items()}
        except (OSError, ValueError, AttributeError):
            pass

    @classmethod
    def for_layout(cls, layout: str) -> 'WordList':
        return cls(LAYOUT_LANGUAGES.get(layout, 'en'))

    def is_known(self, word: str) -> bool:
        return word.lower() in self._rank

    def complete(self, prefix: str, typeable: set[str], limit: int = 3) -> list[str]:
        """
        Return up to `limit` completions for `prefix`, keeping the
        prefix exactly as typed. Words whose remaining letters can't be
        typed on the current layout are skipped.
        """
        if not prefix:
            return []

        lower_prefix = prefix.lower()
        matches = [
            (lower, word) for lower, word in self._words
            if len(lower) > len(lower_prefix) and lower.startswith(lower_prefix)
        ]
        matches.sort(key=lambda m: (-self._usage.get(m[0], 0), self._rank[m[0]]))

        all_caps = len(prefix) > 1 and prefix.isupper()
        results = []
        for _, word in matches:
            rest = word[len(prefix):]
            if all_caps:
                rest = rest.upper()
            if all(ch in typeable for ch in rest):
                results.append(prefix + rest)
                if len(results) >= limit:
                    break
        return results

    def record_use(self, word: str):
        """Count a finished word so it ranks higher next time."""
        lower = word.lower()
        if lower not in self._rank:
            return
        self._usage[lower] = self._usage.get(lower, 0) + 1
        self._save_usage()

    def add_word(self, word: str):
        """Add a word to the user's list (~/.config/osk/words-<lang>.txt)."""
        lower = word.lower()
        if lower in self._rank:
            return
        os.makedirs(USER_DIR, exist_ok=True)
        with open(self._user_words_path, 'a', encoding='utf-8') as f:
            f.write(word + '\n')
        # Rank above every existing word on ties
        self._rank[lower] = min(self._rank.values(), default=0) - 1
        self._words.insert(0, (lower, word))
        self.record_use(word)

    def _save_usage(self):
        os.makedirs(USER_DIR, exist_ok=True)
        tmp = self._usage_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._usage, f)
        os.replace(tmp, self._usage_path)
