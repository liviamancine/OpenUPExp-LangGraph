"""Chunking estrutural (docs/architecture/05-contexto-e-evidencias.md §5.7).

Leis são divididas por artigo; manuais por seção numerada; demais fontes por
parágrafos agrupados. Cada chunk recebe uma chave estável e legível.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

CHUNKER_VERSION = "struct-1.0"

MAX_CHARS = 1800
TARGET_CHARS = 1200
MIN_SECTION_CHARS = 200


@dataclass
class Page:
    numero: int
    texto: str


@dataclass
class ChunkDraft:
    stable_key: str
    texto: str
    pagina: int | None
    meta: dict = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.texto.encode()).hexdigest()


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def guess_source_kind(filename: str) -> str:
    name = filename.lower()
    if name.startswith("lei") or "_lei_" in name or "decreto" in name:
        return "lei"
    if "manual" in name or "guia" in name:
        return "manual"
    if "escopo" in name:
        return "escopo"
    return "academico"


class _Text:
    """Concatena páginas mantendo o mapeamento posição -> página."""

    def __init__(self, pages: list[Page]):
        self.parts: list[str] = []
        self.starts: list[tuple[int, int]] = []
        pos = 0
        for p in pages:
            t = _clean_page(p.texto)
            self.starts.append((pos, p.numero))
            self.parts.append(t)
            pos += len(t) + 2
        self.text = "\n\n".join(self.parts)

    def page_at(self, pos: int) -> int | None:
        page = None
        for start, numero in self.starts:
            if start <= pos:
                page = numero
            else:
                break
        return page


def _clean_page(texto: str) -> str:
    texto = texto.replace("\r", "")
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)  # hifenização de quebra de linha
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def _windows(texto: str, limit: int = TARGET_CHARS) -> list[str]:
    """Agrupa parágrafos até o limite; parágrafos longos são cortados por frase."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ§IVX]+[\s\.\-–)])", texto) if p.strip()]
    out: list[str] = []
    buf = ""
    for para in paras:
        while len(para) > MAX_CHARS:
            cut = para.rfind(". ", 0, limit)
            cut = cut + 1 if cut > limit // 2 else limit
            pieces = para[:cut].strip()
            if buf:
                out.append(buf)
                buf = ""
            out.append(pieces)
            para = para[cut:].strip()
        if buf and len(buf) + len(para) + 1 > limit:
            out.append(buf)
            buf = para
        else:
            buf = f"{buf}\n{para}" if buf else para
    if buf:
        out.append(buf)
    return out


# ---------------------------------------------------------------------------
# Leis: um chunk por artigo (subdividido por parágrafo quando longo)
# ---------------------------------------------------------------------------

_ART_RE = re.compile(r"(?m)^\s*Art\.?\s*(\d+)\s*(?:º|°|o)?(?:\s*-\s*([A-Z]))?\s*[\.\-–]?\s")
_LEI_RE = re.compile(r"LEI\s+(?:COMPLEMENTAR\s+)?N[º°o\.]*\s*([\d\.]+)", re.IGNORECASE)


def chunk_law(doc_stem: str, pages: list[Page]) -> list[ChunkDraft]:
    t = _Text(pages)
    lei = _LEI_RE.search(t.text[:4000])
    lei_numero = lei.group(1).rstrip(".") if lei else None
    matches = list(_ART_RE.finditer(t.text))
    if not matches:
        return chunk_generic(doc_stem, pages, kind="lei")

    chunks: list[ChunkDraft] = []
    preamble = t.text[: matches[0].start()].strip()
    if preamble:
        for i, w in enumerate(_windows(preamble)):
            chunks.append(ChunkDraft(f"{doc_stem}:preambulo:c{i}", w, t.page_at(0),
                                     {"lei_numero": lei_numero, "secao": "preambulo"}))

    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(t.text)
        artigo = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
        body = t.text[m.start():end].strip()
        meta = {"lei_numero": lei_numero, "artigo": artigo}
        page = t.page_at(m.start())
        if len(body) <= MAX_CHARS:
            chunks.append(ChunkDraft(f"{doc_stem}:art{artigo}", body, page, meta))
            continue
        caput = body.split("\n", 1)[0][:300]
        for i, w in enumerate(_windows(body)):
            texto = w if i == 0 else f"[continuação do Art. {artigo}] {caput}\n{w}"
            chunks.append(ChunkDraft(f"{doc_stem}:art{artigo}:c{i}", texto, page, dict(meta, parte=i)))
    return _dedupe_keys(chunks)


# ---------------------------------------------------------------------------
# Manuais: por seção numerada (1.2.3 Título)
# ---------------------------------------------------------------------------

_SEC_RE = re.compile(r"(?m)^(\d{1,2}(?:\.\d{1,2}){0,4})\.?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{2,120})$")


def chunk_manual(doc_stem: str, pages: list[Page]) -> list[ChunkDraft]:
    t = _Text(pages)
    matches = [m for m in _SEC_RE.finditer(t.text) if not m.group(2).rstrip().endswith(".")]
    if len(matches) < 3:
        return chunk_generic(doc_stem, pages, kind="manual")
    bounds = [(0, None, "inicio")] + [(m.start(), m.group(1), m.group(2).strip()) for m in matches]
    sections: list[tuple[int, str | None, str, str]] = []
    for i, (start, secao, titulo) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(t.text)
        body = t.text[start:end].strip()
        if body:
            sections.append((start, secao, titulo, body))

    # Seções muito curtas (sumários, títulos sem corpo) são fundidas com a seguinte.
    merged: list[tuple[int, str | None, str, str]] = []
    pending: list[tuple[int, str | None, str, str]] = []
    for sec in sections:
        if len(sec[3]) < MIN_SECTION_CHARS:
            pending.append(sec)
            continue
        if pending:
            head = "\n".join(p[3] for p in pending)
            sec = (pending[0][0], sec[1], sec[2], f"{head}\n{sec[3]}")
            pending = []
        merged.append(sec)
    if pending:
        merged.append((pending[0][0], pending[-1][1], pending[-1][2], "\n".join(p[3] for p in pending)))

    chunks: list[ChunkDraft] = []
    for start, secao, titulo, body in merged:
        key_sec = f"sec{secao}" if secao else "inicio"
        for j, w in enumerate(_windows(body)):
            texto = w if j == 0 or not secao else f"[continuação de {secao} {titulo}]\n{w}"
            chunks.append(ChunkDraft(f"{doc_stem}:{key_sec}:c{j}", texto, t.page_at(start),
                                     {"secao": secao, "titulo": titulo}))
    return _dedupe_keys(chunks)


# ---------------------------------------------------------------------------
# Genérico: parágrafos agrupados, preservando a página
# ---------------------------------------------------------------------------


def chunk_generic(doc_stem: str, pages: list[Page], kind: str = "academico") -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    for p in pages:
        for j, w in enumerate(_windows(_clean_page(p.texto))):
            chunks.append(ChunkDraft(f"{doc_stem}:p{p.numero}:c{j}", w, p.numero, {"tipo": kind}))
    return _dedupe_keys(chunks)


def chunk_document(doc_stem: str, kind: str, pages: list[Page]) -> list[ChunkDraft]:
    if kind == "lei":
        return chunk_law(doc_stem, pages)
    if kind == "manual":
        return chunk_manual(doc_stem, pages)
    return chunk_generic(doc_stem, pages, kind=kind)


def _dedupe_keys(chunks: list[ChunkDraft]) -> list[ChunkDraft]:
    seen: dict[str, int] = {}
    for c in chunks:
        n = seen.get(c.stable_key, 0)
        seen[c.stable_key] = n + 1
        if n:
            c.stable_key = f"{c.stable_key}~{n}"
    return [c for c in chunks if len(c.texto) >= 20]
