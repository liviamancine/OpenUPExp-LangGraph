from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from openupexp.api.auth import current_user
from openupexp.config import get_settings
from openupexp.db.models import AppUser
from openupexp.process.manifest import bpmn_source_commit, get_manifest

router = APIRouter(prefix="/api/process")


@router.get("/manifest")
async def manifest(user: AppUser = Depends(current_user)):
    m = get_manifest()
    return {**m.model_dump(mode="json"), "sha256": m.sha256(), "bpmn_commit": bpmn_source_commit()}


@router.get("/bpmn")
async def bpmn_files(user: AppUser = Depends(current_user)):
    return sorted(p.name for p in get_settings().bpmn_dir.glob("*.bpmn"))


@router.get("/bpmn/{filename}")
async def bpmn_file(filename: str, user: AppUser = Depends(current_user)):
    folder = get_settings().bpmn_dir.resolve()
    path = (folder / filename).resolve()
    if path.parent != folder or path.suffix != ".bpmn" or not path.exists():
        raise HTTPException(404, "Arquivo BPMN inexistente")
    return Response(path.read_bytes(), media_type="application/xml")
