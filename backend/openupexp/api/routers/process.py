import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from openupexp.api.auth import current_user
from openupexp.config import get_settings
from openupexp.db.models import AppUser
from openupexp.process.manifest import bpmn_source_commit, get_manifest

router = APIRouter(prefix="/api/process")

# Arquivos renomeados na exportação do BPMN (commit e0e865a): manifestos antigos ainda os citam.
RENAMED_BPMN = {
    "OpenUPExp Process.bpmn": "0 OpenUPExp Process.bpmn",
    "2 -Elicit Explainability Requirements.bpmn": "2 Elicit Explainability Requirements.bpmn",
}


@router.get("/manifest")
async def manifest(version: str | None = None, user: AppUser = Depends(current_user)):
    """Manifesto vigente ou, com ?version=, o de uma execução antiga."""
    if version is not None:
        if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not (
                get_settings().process_dir / "manifest" / f"openupexp-{version}.yaml").exists():
            raise HTTPException(404, "Versão de manifesto inexistente")
    m = get_manifest(version)
    return {**m.model_dump(mode="json"), "sha256": m.sha256(), "bpmn_commit": bpmn_source_commit()}


@router.get("/bpmn")
async def bpmn_files(user: AppUser = Depends(current_user)):
    return sorted(p.name for p in get_settings().bpmn_dir.glob("*.bpmn"))


@router.get("/bpmn/{filename}")
async def bpmn_file(filename: str, user: AppUser = Depends(current_user)):
    folder = get_settings().bpmn_dir.resolve()
    path = (folder / RENAMED_BPMN.get(filename, filename)).resolve()
    if path.parent != folder or path.suffix != ".bpmn" or not path.exists():
        raise HTTPException(404, "Arquivo BPMN inexistente")
    return Response(path.read_bytes(), media_type="application/xml")
