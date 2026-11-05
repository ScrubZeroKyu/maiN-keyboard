#!/usr/bin/env python3
"""
Regenerate the bundled word lists (currently English only) from the FrequencyWords project
(https://github.com/hermitdave/FrequencyWords, OpenSubtitles 2018 data,
content licensed CC-BY-SA-4.0).

Usage: python3 tools/build_wordlists.py
"""

import os
import urllib.request

URL = 'https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/{0}/{0}_50k.txt'
WORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'words')
KEEP = 20000

# Not suggested; users can still add them with the + button
BLOCKLIST = {
    'en': {
        'fuck', 'fucking', 'fucked', 'fucker', 'fuckers', 'fuckin', 'fucks',
        'motherfucker', 'motherfuckers', 'shit', 'shits', 'shitty', 'bullshit',
        'bitch', 'bitches', 'cunt', 'cunts', 'dick', 'dicks', 'cock', 'cocks',
        'pussy', 'whore', 'whores', 'slut', 'sluts', 'asshole', 'assholes',
        'nigger', 'niggers', 'nigga', 'niggas', 'faggot', 'faggots', 'fag',
        'retard', 'retarded', 'twat', 'wanker', 'dickhead', 'jackass',
    },
    'de': {
        'scheiße', 'scheisse', 'scheiß', 'scheiss', 'ficken', 'fick', 'fickt',
        'gefickt', 'fickst', 'arschloch', 'arschlöcher', 'arsch', 'hure',
        'huren', 'hurensohn', 'schlampe', 'wichser', 'fotze', 'schwuchtel',
        'nutte', 'bumsen', 'missgeburt', 'spast', 'neger', 'vögeln',
    },
}

# The source splits contractions at the apostrophe ("don", "t"). These
# pieces are replaced by the full word, in the same place in the list.
CONTRACTION_PIECES = {
    'en': {
        'don': "don't", 'didn': "didn't", 'doesn': "doesn't", 'isn': "isn't",
        'wasn': "wasn't", 'wouldn': "wouldn't", 'haven': "haven't",
        'couldn': "couldn't", 'aren': "aren't", 'ain': "ain't",
        'shouldn': "shouldn't", 'weren': "weren't", 'hasn': "hasn't",
        'hadn': "hadn't", 'mustn': "mustn't", 'needn': "needn't",
        're': None, 'll': None, 've': None, 'im': None,
        # Misspellings without the apostrophe (typing them still finds
        # the right word)
        'dont': None, 'thats': None, 'whats': None, 'youre': None,
        'didnt': None, 'hes': None, 'ive': None, 'theres': None,
    },
}

# Contractions placed right after the word they start with
CONTRACTIONS_AFTER = {
    'en': {
        'you': ["I'm", "I'll", "I've", "I'd", "you're", "you'll", "you've", "you'd"],
        'it': ["it's", "it'll"],
        'that': ["that's", "that'll"],
        'what': ["what's"],
        'we': ["we're", "we'll", "we've", "we'd"],
        'he': ["he's", "he'll", "he'd"],
        'can': ["can't"],
        'there': ["there's"],
        'here': ["here's"],
        'they': ["they're", "they'll", "they've", "they'd"],
        'she': ["she's", "she'll", "she'd"],
        'how': ["how's"],
        'who': ["who's"],
        'let': ["let's"],
        'where': ["where's"],
        'won': ["won't"],
    },
}


def add_contractions(lang: str, words: list[str]) -> list[str]:
    """Swap split-up contraction pieces for whole words (see above)."""
    pieces = CONTRACTION_PIECES.get(lang, {})
    after = CONTRACTIONS_AFTER.get(lang, {})
    present = {w.lower() for w in words}
    result = []
    for word in words:
        if word in pieces:
            if pieces[word] and pieces[word].lower() not in present:
                result.append(pieces[word])
            continue
        result.append(word)
        for extra in after.get(word, []):
            if extra.lower() not in present:
                result.append(extra)
    return result


HEADER = {
    'en': '# Common English words, most frequent first.',
    'de': '# Häufige deutsche Wörter, häufigste zuerst.',
}


def build(lang: str):
    with urllib.request.urlopen(URL.format(lang), timeout=60) as resp:
        lines = resp.read().decode('utf-8').splitlines()

    words = []
    for line in lines:
        word = line.split(' ')[0].strip()
        if len(word) < 2 or not word.replace("'", '').isalpha() or word in BLOCKLIST[lang]:
            continue
        words.append(word)
        if len(words) >= KEEP:
            break
    words = add_contractions(lang, words)

    path = os.path.join(WORDS_DIR, f'{lang}.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(HEADER[lang] + '\n')
        f.write('# Source: FrequencyWords by Hermit Dave (OpenSubtitles 2018),\n')
        f.write('# https://github.com/hermitdave/FrequencyWords, CC-BY-SA-4.0.\n')
        f.write('\n'.join(words) + '\n')
    print(f'{path}: {len(words)} words')


if __name__ == '__main__':
    # German keeps its small hand-written list for now
    for lang in ('en',):
        build(lang)
