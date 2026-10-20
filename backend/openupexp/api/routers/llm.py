"""Perfis de modelo de linguagem disponíveis para as execuções (cap. 14)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.api.auth import current_user
from openupexp.api.deps import get_session
from openupexp.db.models import AppUser
from openupexp.llm.catalog import effective_default_slug, ensure_catalog, key_configured, list_profiles

router = APIRouter(prefix="/api")


@router.get("/llm/profiles")
async def profiles(user: AppUser = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await ensure_catalog(session)
    default = effective_default_slug()
    return [{
        "id": str(p.id), "slug": p.slug, "nome": p.nome, "padrao": p.slug == default, "protegido": p.protected,
        "params": p.params, "disponivel": key_configured(m),
        "modelo": {"slug": m.slug, "nome": m.nome, "provider": m.provider, "model": m.model, "local": m.local,
                   "protegido": m.protected, "descricao": m.meta.get("descricao") or m.meta.get("papel")},
    } for p, m in await list_profiles(session, only_enabled=False) if p.enabled and (m.enabled or m.local)]
