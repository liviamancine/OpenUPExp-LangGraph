"""Verificação mecânica de citações (docs/architecture/05-contexto-e-evidencias.md §5.8).

Uma citação é válida quando é trecho literal do chunk, após normalização de
espaços, hifenização, aspas e caixa. Reticências separam segmentos que devem
aparecer na mesma ordem.
"""

import re
import unicodedata

MIN_SEGMENT_CHARS = 12


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}))
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def verify_quote(quote: str, source: str) -> bool:
    q = normalize(quote).strip(" \"'.,;:")
    if len(q) < MIN_SEGMENT_CHARS:
        return False
    src = normalize(source)
    pos = 0
    segments = [s.strip(" \"'.,;:") for s in re.split(r"\.\.\.|…|\[\.\.\.\]", q)]
    segments = [s for s in segments if s]
    for seg in segments:
        found = src.find(seg, pos)
        if found < 0:
            return False
        pos = found + len(seg)
    return bool(segments)
