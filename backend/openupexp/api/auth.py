"""Autenticação local (JWT) e controle de acesso por papel no projeto."""

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.api.deps import get_session
from openupexp.config import get_settings
from openupexp.db.models import AppUser, ProjectMember
from openupexp.db.session import session_scope

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

PLATFORM_ROLES = ("requirements_engineer", "participant", "observer", "researcher")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except Exception:
        return False


def issue_token(user: AppUser) -> str:
    s = get_settings()
    payload = {"sub": str(user.id), "email": user.email,
               "exp": datetime.now(timezone.utc) + timedelta(hours=s.jwt_ttl_hours)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


async def current_user(request: Request, token: str | None = Depends(oauth2),
                       session: AsyncSession = Depends(get_session)) -> AppUser:
    # EventSource (SSE) não envia cabeçalhos: aceita também ?access_token=
    token = token or request.query_params.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    user = await session.get(AppUser, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inexistente")
    return user


async def require_member(session: AsyncSession, project_id: uuid.UUID, user: AppUser,
                         roles: tuple[str, ...] | None = None) -> str:
    """Garante que o usuário participa do projeto (admin tem acesso total)."""
    if user.papel_global == "admin":
        return "admin"
    m = await session.get(ProjectMember, (project_id, user.id))
    if m is None or (roles and m.papel_plataforma not in roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão neste projeto")
    return m.papel_plataforma


async def create_user(session: AsyncSession, email: str, nome: str, password: str,
                      papel_global: str = "user") -> AppUser:
    user = AppUser(email=email.lower().strip(), nome=nome, password_hash=hash_password(password),
                   papel_global=papel_global)
    session.add(user)
    await session.flush()
    return user


async def bootstrap_admin() -> None:
    """Cria o administrador inicial a partir de ADMIN_EMAIL/ADMIN_PASSWORD, se não houver usuários."""
    s = get_settings()
    if not (s.admin_email and s.admin_password):
        return
    async with session_scope() as session:
        if await session.scalar(select(func.count(AppUser.id))):
            return
        await create_user(session, s.admin_email, "Administrador", s.admin_password, "admin")
