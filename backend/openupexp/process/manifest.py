"""Manifesto do processo: ponte entre os elementos BPMN de referência e a execução.

Ver docs/architecture/02-mapeamento-fase-1-visao.md §2.6.
"""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from openupexp.config import get_settings

Mechanism = Literal["agent", "deterministic", "hitl_approval", "hitl_consensus"]
Select = Literal["full", "all_items", "digest"]
Completeness = Literal["none", "all_items", "all_pairs"]

BPMN_EXECUTABLE_TAGS = {"task", "userTask", "serviceTask", "callActivity", "exclusiveGateway"}


class ReadSpec(BaseModel):
    artifact: str
    select: Select = "full"
    required: bool = True


class WriteSpec(BaseModel):
    artifact: str
    item_prefix: str | None = None
    evidence: Literal["none", "required"] = "none"


class RetrievalSpec(BaseModel):
    store: Literal["reference_base"] = "reference_base"
    planner: str | None = None
    mode: Literal["hybrid", "lexical", "vector"] = "hybrid"
    top_k: int = 12
    per_query_k: int = 6


class Outcome(BaseModel):
    next: str
    comment_required: bool = False


class TaskSpec(BaseModel):
    id: str
    name: str
    bpmn_element: str | None = None
    bpmn_anchor: str | None = None
    mechanism: Mechanism
    baml_function: str | None = None
    handler: str | None = None
    theory_ref: str | None = None
    pending: list[str] = Field(default_factory=list)
    reads: list[ReadSpec] = Field(default_factory=list)
    writes: list[WriteSpec] = Field(default_factory=list)
    retrieval: RetrievalSpec | None = None
    completeness: Completeness = "none"
    template_sections: list[str] = Field(default_factory=list)
    decided_by_role: str | None = None
    reviews: str | None = None
    outcomes: dict[str, Outcome] = Field(default_factory=dict)


class SubprocessSpec(BaseModel):
    id: str
    name: str | None = None
    bpmn_file: str
    bpmn_element: str
    pending: list[str] = Field(default_factory=list)
    tasks: list[TaskSpec]


class PhaseSpec(BaseModel):
    id: str
    name: str
    openup_phase: str
    implemented: bool = False
    bpmn_file: str
    bpmn_element: str
    subprocesses: list[SubprocessSpec]

    def tasks(self) -> list[TaskSpec]:
        return [t for sp in self.subprocesses for t in sp.tasks]

    def subprocess_of(self, task_id: str) -> SubprocessSpec:
        for sp in self.subprocesses:
            if any(t.id == task_id for t in sp.tasks):
                return sp
        raise KeyError(task_id)

    def subprocess(self, sp_id: str) -> SubprocessSpec:
        for sp in self.subprocesses:
            if sp.id == sp_id:
                return sp
        raise KeyError(sp_id)

    def writers(self) -> dict[str, TaskSpec]:
        """artifact_type -> tarefa que o produz."""
        return {w.artifact: t for t in self.tasks() for w in t.writes}


class Manifest(BaseModel):
    manifest_version: str
    process: str
    bpmn_source: dict
    root: dict
    phases: list[PhaseSpec]

    def phase(self, phase_id: str) -> PhaseSpec:
        for p in self.phases:
            if p.id == phase_id:
                return p
        raise KeyError(phase_id)

    def task(self, task_id: str) -> TaskSpec:
        for p in self.phases:
            for t in p.tasks():
                if t.id == task_id:
                    return t
        raise KeyError(task_id)

    def sha256(self) -> str:
        raw = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()


def load_manifest(path: Path | None = None) -> Manifest:
    path = path or get_settings().manifest_path
    with open(path, encoding="utf-8") as fh:
        return Manifest.model_validate(yaml.safe_load(fh))


@lru_cache
def get_manifest() -> Manifest:
    return load_manifest()


def bpmn_source_commit() -> str | None:
    p = get_settings().bpmn_dir / "SOURCE_COMMIT"
    return p.read_text().strip() if p.exists() else None


# ---------------------------------------------------------------------------
# Conformidade manifesto ↔ BPMN
# ---------------------------------------------------------------------------


def _clean(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").replace("\xa0", " ")).strip()


def bpmn_elements(bpmn_file: Path) -> dict[str, tuple[str, str]]:
    """id -> (tag, nome) dos elementos executáveis de um arquivo BPMN."""
    root = ET.parse(bpmn_file).getroot()
    found: dict[str, tuple[str, str]] = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in BPMN_EXECUTABLE_TAGS and el.get("id"):
            found[el.get("id")] = (tag, _clean(el.get("name")))
    return found


def check_conformance(manifest: Manifest, bpmn_dir: Path) -> list[str]:
    """Lista de violações; vazia quando manifesto e BPMN estão alinhados."""
    problems: list[str] = []
    root_els = bpmn_elements(bpmn_dir / manifest.root["bpmn_file"])
    for phase in manifest.phases:
        if phase.bpmn_element not in root_els:
            problems.append(f"fase {phase.id}: {phase.bpmn_element} ausente do BPMN raiz")
        phase_file = bpmn_dir / phase.bpmn_file
        if not phase_file.exists():
            problems.append(f"fase {phase.id}: arquivo {phase.bpmn_file} inexistente")
            continue
        phase_els = bpmn_elements(phase_file)
        for sp in phase.subprocesses:
            if sp.bpmn_element not in phase_els:
                problems.append(f"subprocesso {sp.id}: {sp.bpmn_element} ausente de {phase.bpmn_file}")
            sp_file = bpmn_dir / sp.bpmn_file
            if not sp_file.exists():
                problems.append(f"subprocesso {sp.id}: arquivo {sp.bpmn_file} inexistente")
                continue
            sp_els = bpmn_elements(sp_file)
            mapped = set()
            for t in sp.tasks:
                if t.bpmn_element is None:
                    if not t.pending:
                        problems.append(f"tarefa {t.id}: sem elemento BPMN e sem decisão pendente")
                    continue
                if t.bpmn_element not in sp_els:
                    problems.append(f"tarefa {t.id}: {t.bpmn_element} ausente de {sp.bpmn_file}")
                mapped.add(t.bpmn_element)
            for el_id, (tag, name) in sp_els.items():
                if el_id not in mapped:
                    problems.append(f"{sp.bpmn_file}: {tag} '{name}' ({el_id}) não mapeado no manifesto")
    return problems
