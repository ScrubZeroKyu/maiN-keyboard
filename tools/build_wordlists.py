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
        if len(word) < 2 or not word.isalpha() or word in BLOCKLIST[lang]:
            continue
        words.append(word)
        if len(words) >= KEEP:
            break

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
