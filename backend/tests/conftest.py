"""Fixtures: banco de teste dedicado (openupexp_test), gateway simulado e embedding hash."""

import os
import tempfile
from pathlib import Path

_BASE = os.environ.get("TEST_DATABASE_URL",
                       "postgresql+psycopg://openupexp:openupexp@localhost:5433/openupexp_test")
os.environ["DATABASE_URL"] = _BASE
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["AGENT_GATEWAY"] = "fake"
os.environ["JWT_SECRET"] = "segredo-de-teste-com-mais-de-32-bytes!!"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="openupexp-test-")
for k in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
    os.environ.setdefault(k, "test-key")

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from openupexp.db.session import dispose_engine, get_engine  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
CASE_DIR = REPO / "experiments" / "cases" / "inpi"
SCOPE_PDF = CASE_DIR / "escopo_projeto.pdf"
CORPUS_DIR = CASE_DIR / "corpus"

LAW_TEXT = """LEI Nº 13.709, DE 14 DE AGOSTO DE 2018.
Dispõe sobre a proteção de dados pessoais.

Art. 1º Esta Lei dispõe sobre o tratamento de dados pessoais, inclusive nos meios digitais.

Art. 20. O titular dos dados tem direito a solicitar a revisão de decisões tomadas unicamente com base em
tratamento automatizado de dados pessoais que afetem seus interesses.
§ 1º O controlador deverá fornecer, sempre que solicitadas, informações claras e adequadas a respeito dos
critérios e dos procedimentos utilizados para a decisão automatizada.

Art. 21. Os dados pessoais referentes ao exercício regular de direitos não podem ser utilizados em seu prejuízo.
"""

SCOPE_TEXT = """ESCOPO DO PROJETO - Sistema de Apoio a Decisões
O projeto consiste no desenvolvimento de um sistema de apoio à análise de solicitações por uma entidade pública.
O examinador analisa cada pedido e o sistema recomenda o deferimento ou indeferimento.
O solicitante precisa compreender os motivos da decisão para eventualmente recorrer.
O regulador precisa auditar as decisões automatizadas e os critérios utilizados.
"""


def _ensure_database():
    admin = _BASE.replace("postgresql+psycopg://", "postgresql://").rsplit("/", 1)[0] + "/openupexp"
    name = _BASE.rsplit("/", 1)[1]
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _BASE)
    command.upgrade(cfg, "head")


_ensure_database()


@pytest.fixture(autouse=True)
async def clean_db():
    engine = get_engine()
    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"
        ))).scalars().all()
        if tables:
            await conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE"))
    yield
    await dispose_engine()


@pytest.fixture
def scope_bytes() -> bytes:
    return SCOPE_TEXT.encode()


@pytest.fixture
def law_bytes() -> bytes:
    return LAW_TEXT.encode()
