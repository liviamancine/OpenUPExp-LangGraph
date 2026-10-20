"""Administração de modelos e perfis de inferência — somente papel admin (cap. 14 §14.4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.api.auth import current_user
from openupexp.api.deps import get_session
from openupexp.config import get_settings
from openupexp.db.models import AppUser, InferenceProfile, LlmModel
from openupexp.llm import admin
from openupexp.llm.catalog import effective_default_slug, ensure_catalog, key_configured

router = APIRouter(prefix="/api/admin/llm")


async def require_admin(user: AppUser = Depends(current_user)) -> AppUser:
    if user.papel_global != "admin":
        raise HTTPException(403, "Apenas administradores.")
    return user


class ModelIn(BaseModel):
    slug: str | None = None
    nome: str | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    enabled: bool | None = None
    params: dict | None = None


class ProfileIn(BaseModel):
    slug: str | None = None
    nome: str | None = None
    params: dict | None = None
    enabled: bool | None = None


def _profile(p: InferenceProfile, default: str) -> dict:
    return {"id": str(p.id), "slug": p.slug, "nome": p.nome, "params": p.params, "protegido": p.protected,
            "padrao_marcado": p.is_default, "padrao_efetivo": p.slug == default, "habilitado": p.enabled,
            "compat": p.checks.get("compat")}


async def _payload(session: AsyncSession) -> dict:
    await ensure_catalog(session)
    default = await effective_default_slug(session)
    models = (await session.scalars(select(LlmModel).order_by(LlmModel.local.desc(), LlmModel.nome))).all()
    profiles = (await session.scalars(select(InferenceProfile).order_by(InferenceProfile.nome))).all()
    s = get_settings()
    return {
        "servidores_permitidos": admin.allowed_hosts(),
        "provedores": admin.PROVIDERS,
        "parametros": {k: {"tipo": t.__name__, "min": lo, "max": hi} for k, (t, lo, hi) in admin.PARAMS.items()},
        "modelo_local_ligado": s.local_llm_enabled,
        "padrao_efetivo": default,
        "modelos": [{
            "id": str(m.id), "slug": m.slug, "nome": m.nome, "provider": m.provider, "model": m.model,
            "endereco": admin.endpoint(m), "api_key_env": m.api_key_env, "local": m.local, "protegido": m.protected,
            "habilitado": m.enabled, "chave_configurada": key_configured(m) if not m.local else None,
            "descricao": m.meta.get("descricao") or m.meta.get("papel"), "conexao": m.meta.get("conexao"),
            "perfis": [_profile(p, default) for p in profiles if p.model_id == m.id],
        } for m in models],
    }


def _err(exc: admin.AdminError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("")
async def overview(user: AppUser = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await _payload(session)


@router.post("/models")
async def create_model(body: ModelIn, user: AppUser = Depends(require_admin),
                       session: AsyncSession = Depends(get_session)):
    try:
        m = await admin.create_model(session, body.model_dump(exclude_none=True), user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"id": str(m.id)}


@router.patch("/models/{model_id}")
async def update_model(model_id: uuid.UUID, body: ModelIn, user: AppUser = Depends(require_admin),
                       session: AsyncSession = Depends(get_session)):
    try:
        await admin.update_model(session, model_id, body.model_dump(exclude_unset=True), user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.delete("/models/{model_id}")
async def delete_model(model_id: uuid.UUID, user: AppUser = Depends(require_admin),
                       session: AsyncSession = Depends(get_session)):
    try:
        await admin.delete_model(session, model_id, user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.post("/models/{model_id}/test-connection")
async def test_connection(model_id: uuid.UUID, user: AppUser = Depends(require_admin),
                          session: AsyncSession = Depends(get_session)):
    try:
        return await admin.test_connection(session, model_id, user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc


@router.post("/models/{model_id}/profiles")
async def create_profile(model_id: uuid.UUID, body: ProfileIn, user: AppUser = Depends(require_admin),
                         session: AsyncSession = Depends(get_session)):
    try:
        p = await admin.create_profile(session, model_id, body.model_dump(exclude_none=True), user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"id": str(p.id)}


@router.patch("/profiles/{profile_id}")
async def update_profile(profile_id: uuid.UUID, body: ProfileIn, user: AppUser = Depends(require_admin),
                         session: AsyncSession = Depends(get_session)):
    try:
        await admin.update_profile(session, profile_id, body.model_dump(exclude_unset=True), user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: uuid.UUID, user: AppUser = Depends(require_admin),
                         session: AsyncSession = Depends(get_session)):
    try:
        await admin.delete_profile(session, profile_id, user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.post("/profiles/{profile_id}/default")
async def set_default(profile_id: uuid.UUID, user: AppUser = Depends(require_admin),
                      session: AsyncSession = Depends(get_session)):
    try:
        await admin.set_default(session, profile_id, user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
    return {"ok": True}


@router.post("/profiles/{profile_id}/test-compat")
async def test_compat(profile_id: uuid.UUID, user: AppUser = Depends(require_admin),
                      session: AsyncSession = Depends(get_session)):
    try:
        return await admin.request_compat_test(session, profile_id, user.id)
    except admin.AdminError as exc:
        raise _err(exc) from exc
