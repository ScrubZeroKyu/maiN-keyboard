"""
Word suggestions: completions for the word being typed and predictions
for the next word, ranked by how often the user picks each word.
"""

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


def _write_words(path: str, words: list[str]):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(word + '\n' for word in words)


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, path)


class WordList:
    """
    Word lookup for one language.

    Order: words that followed the previous word most often, then words
    the user has used most, then list order (user-added words, then the
    bundled list from most to least common).
    """

    def __init__(self, language: str):
        self.language = language
        self._user_words_path = os.path.join(USER_DIR, f'words-{language}.txt')
        self._blocked_path = os.path.join(USER_DIR, f'blocked-{language}.txt')
        self._usage_path = os.path.join(USER_DIR, f'word-usage-{language}.json')
        self._pairs_path = os.path.join(USER_DIR, f'word-pairs-{language}.json')
        self._load()

    def _load(self):
        words = _read_words(self._user_words_path)
        words += _read_words(os.path.join(WORDS_DIR, f'{self.language}.txt'))

        self._words: list[tuple[str, str]] = []  # (lowercase, original)
        self._rank: dict[str, int] = {}
        self._original: dict[str, str] = {}
        for word in words:
            lower = word.lower()
            if lower not in self._rank:
                self._rank[lower] = len(self._words)
                self._original[lower] = word
                self._words.append((lower, word))

        self._blocked = {w.lower() for w in _read_words(self._blocked_path)}

        self._usage: dict[str, int] = {}
        for k, v in _read_json(self._usage_path).items():
            if isinstance(v, int):
                self._usage[k] = v

        # previous word -> {next word -> times used together}
        self._pairs: dict[str, dict[str, int]] = {}
        for prev, nexts in _read_json(self._pairs_path).items():
            if isinstance(nexts, dict):
                self._pairs[prev] = {k: v for k, v in nexts.items() if isinstance(v, int)}

    @classmethod
    def for_layout(cls, layout: str) -> 'WordList':
        return cls(LAYOUT_LANGUAGES.get(layout, 'en'))

    def is_known(self, word: str) -> bool:
        return word.lower() in self._rank

    def _sort_key(self, lower: str, followers: dict[str, int]):
        return (-followers.get(lower, 0), -self._usage.get(lower, 0), self._rank[lower])

    def complete(self, prefix: str, typeable: set[str], limit: int,
                 prev: str | None = None) -> list[str]:
        """
        Return up to `limit` completions for `prefix`. The typed part is
        kept as typed. Typing without the apostrophe also finds words that
        have one ("dont" -> "don't"); the keyboard then retypes the word.
        Words that can't be typed on the current layout are skipped.
        """
        if not prefix:
            return []

        lower_prefix = prefix.lower()
        bare_prefix = lower_prefix.replace("'", '')
        followers = self._pairs.get(prev.lower(), {}) if prev else {}
        matches = []
        for lower, word in self._words:
            if len(lower) <= len(lower_prefix) or lower in self._blocked:
                continue
            if lower.startswith(lower_prefix):
                matches.append((0, lower, word))
            elif "'" in lower and lower.replace("'", '').startswith(bare_prefix):
                # Only right after the typed letters when they spell the
                # whole word ("dont"), else "hel" would put "he'll" first
                exact = lower.replace("'", '') == bare_prefix
                matches.append((0 if exact else 1, lower, word))
        matches.sort(key=lambda m: (m[0],) + self._sort_key(m[1], followers))

        all_caps = len(prefix) > 1 and prefix.isupper()
        results = []
        for _, lower, word in matches:
            if word[0].isupper():
                # Names and "I'm" keep their capital ("i" -> "I'm")
                full = word
            elif lower.startswith(lower_prefix):
                full = prefix + word[len(prefix):]
            else:
                full = word[0].upper() + word[1:] if prefix[0].isupper() else word
            if all_caps:
                full = full.upper()
            if all(ch in typeable for ch in full):
                results.append(full)
                if len(results) >= limit:
                    break
        return results

    def predict(self, prev: str | None, typeable: set[str], limit: int) -> list[str]:
        """
        Guess the next word: words that followed `prev` before, then the
        user's most used words, then the most common words in the list.
        """
        followers = self._pairs.get(prev.lower(), {}) if prev else {}
        by_pair = sorted((w for w in followers if w in self._rank),
                         key=lambda w: self._sort_key(w, followers))
        by_usage = sorted(self._usage, key=lambda w: -self._usage[w])

        results: list[str] = []
        seen: set[str] = set()

        def add(lower: str) -> bool:
            if lower in seen or lower in self._blocked or lower not in self._rank:
                return False
            seen.add(lower)
            word = self._original[lower]
            if all(ch in typeable for ch in word):
                results.append(word)
            return len(results) >= limit

        for lower in by_pair:
            if add(lower):
                return results
        for lower in by_usage:
            if add(lower):
                return results
        for lower, _ in self._words:
            if add(lower):
                return results
        return results

    def record_use(self, word: str, prev: str | None = None):
        """Count a finished word (and the word before it) so it ranks higher next time."""
        lower = word.lower()
        if lower not in self._rank:
            return
        self._usage[lower] = self._usage.get(lower, 0) + 1
        _write_json(self._usage_path, self._usage)

        if prev and prev.lower() in self._rank:
            nexts = self._pairs.setdefault(prev.lower(), {})
            nexts[lower] = nexts.get(lower, 0) + 1
            _write_json(self._pairs_path, self._pairs)

    def unrecord_use(self, word: str, prev: str | None = None):
        """Undo record_use(), e.g. when the word turned out not to be finished."""
        lower = word.lower()
        if self._usage.get(lower, 0) > 0:
            self._usage[lower] -= 1
            if not self._usage[lower]:
                del self._usage[lower]
            _write_json(self._usage_path, self._usage)
        nexts = self._pairs.get(prev.lower(), {}) if prev else {}
        if nexts.get(lower, 0) > 0:
            nexts[lower] -= 1
            if not nexts[lower]:
                del nexts[lower]
            if not nexts:
                del self._pairs[prev.lower()]
            _write_json(self._pairs_path, self._pairs)

    # --- Editing the lists (Options window) ---

    def user_words(self) -> list[str]:
        """Words the user added with the + button."""
        return _read_words(self._user_words_path)

    def add_word(self, word: str):
        """Add a word to the user's list (~/.config/osk/words-<lang>.txt)."""
        lower = word.lower()
        if lower in self._blocked:
            self.unblock_word(lower)
        if lower in self._rank:
            return
        os.makedirs(USER_DIR, exist_ok=True)
        with open(self._user_words_path, 'a', encoding='utf-8') as f:
            f.write(word + '\n')
        # Rank above every existing word on ties
        self._rank[lower] = min(self._rank.values(), default=0) - 1
        self._original[lower] = word
        self._words.insert(0, (lower, word))
        self.record_use(word)

    def remove_user_word(self, word: str):
        """Take a word out of the user's list and forget how often it was used."""
        lower = word.lower()
        _write_words(self._user_words_path,
                     [w for w in self.user_words() if w.lower() != lower])
        self._forget(lower)
        self._load()

    def blocked_words(self) -> list[str]:
        return sorted(self._blocked)

    def block_word(self, word: str):
        """Never suggest this word again."""
        lower = word.strip().lower()
        if not lower or lower in self._blocked:
            return
        self._blocked.add(lower)
        _write_words(self._blocked_path, sorted(self._blocked))

    def unblock_word(self, word: str):
        self._blocked.discard(word.lower())
        _write_words(self._blocked_path, sorted(self._blocked))

    def forget_learning(self):
        """Clear all usage counts and word pairs."""
        self._usage.clear()
        self._pairs.clear()
        _write_json(self._usage_path, self._usage)
        _write_json(self._pairs_path, self._pairs)

    def _forget(self, lower: str):
        self._usage.pop(lower, None)
        self._pairs.pop(lower, None)
        for nexts in self._pairs.values():
            nexts.pop(lower, None)
        _write_json(self._usage_path, self._usage)
        _write_json(self._pairs_path, self._pairs)
