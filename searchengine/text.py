"""Text normalisation shared by indexing and querying.

The browser front end repeats the same steps (lowercase, split on [a-z0-9]+, drop stop
words), then maps each word to its stem with a lookup table exported from here, so
queries match exactly what the index stored.
"""

import re

from nltk.stem.snowball import SnowballStemmer

WORD = re.compile(r"[a-z0-9]+")

# The NLTK English stop word list, inlined so no corpus download is needed.
STOP_WORDS = frozenset(
    """a about above after again against ain all am an and any are aren as at be because been before being below
    between both but by can couldn d did didn do does doesn doing don down during each few for from further had
    hadn has hasn have haven having he her here hers herself him himself his how i if in into is isn it its itself
    just ll m ma me mightn more most mustn my myself needn no nor not now o of off on once only or other our ours
    ourselves out over own re s same shan she should shouldn so some such t than that the their theirs them
    themselves then there these they this those through to too under until up ve very was wasn we were weren what
    when where which while who whom why will with won wouldn y you your yours yourself yourselves""".split()
)

_stemmer = SnowballStemmer("english")


def words(text: str) -> list[str]:
    """Lowercased words with stop words removed, in order."""
    return [w for w in WORD.findall(text.lower()) if w not in STOP_WORDS]


def stem(word: str) -> str:
    return _stemmer.stem(word)


def terms(text: str) -> list[str]:
    """The index terms for a piece of text: its words, stemmed."""
    return [stem(w) for w in words(text)]
