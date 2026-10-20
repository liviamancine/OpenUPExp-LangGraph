"""Modelo lógico — docs/architecture/06-modelo-de-dados.md."""

import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Usuários, projetos e papéis
# ---------------------------------------------------------------------------


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    papel_global: Mapped[str] = mapped_column(String(20), default="user")  # admin | user
    created_at: Mapped[datetime] = _created()


class Project(Base):
    __tablename__ = "project"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(200))
    dominio: Mapped[str | None] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = _created()


class ProjectMember(Base):
    __tablename__ = "project_member"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    # requirements_engineer | participant | observer | researcher
    papel_plataforma: Mapped[str] = mapped_column(String(40))
    # papel teórico do OpenUPExp (ex.: "Especialista em Regulação")
    papel_openupexp: Mapped[str | None] = mapped_column(String(120))


# ---------------------------------------------------------------------------
# Processo e corpus
# ---------------------------------------------------------------------------


class ProcessManifest(Base):
    __tablename__ = "process_manifest"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    bpmn_commit: Mapped[str | None] = mapped_column(String(64))
    conteudo: Mapped[dict] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class SourceDocument(Base):
    __tablename__ = "source_document"
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    arquivo: Mapped[str] = mapped_column(String(500))
    # escopo | lei | manual | academico | elicitacao
    source_kind: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(Text)
    texto: Mapped[str | None] = mapped_column(Text)
    paginas: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (UniqueConstraint("project_id", "sha256", name="uq_source_project_sha"),)


class CorpusVersion(Base):
    __tablename__ = "corpus_version"
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    embedding_provider: Mapped[str] = mapped_column(String(60))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    chunker_version: Mapped[str] = mapped_column(String(40))
    # reference: base de referência do projeto · elicitation: material de elicitação de uma execução
    purpose: Mapped[str] = mapped_column(String(20), default="reference", server_default="reference")
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE", use_alter=True,
                                                                name="fk_corpus_version_run"))
    status: Mapped[str] = mapped_column(String(20), default="building")  # building | ready | failed
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Chunk(Base):
    __tablename__ = "chunk"
    id: Mapped[uuid.UUID] = _uuid_pk()
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corpus_version.id", ondelete="CASCADE")
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE")
    )
    source_kind: Mapped[str] = mapped_column(String(20))
    stable_key: Mapped[str] = mapped_column(String(300))
    texto: Mapped[str] = mapped_column(Text)
    pagina: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    sha256: Mapped[str] = mapped_column(String(64))
    # sem dimensão fixa: cada corpus_version pode usar um modelo de embedding diferente
    embedding = mapped_column(Vector())
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('portuguese', texto)", persisted=True))
    __table_args__ = (
        UniqueConstraint("corpus_version_id", "stable_key", name="uq_chunk_version_key"),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunk_corpus_kind", "corpus_version_id", "source_kind"),
    )


# ---------------------------------------------------------------------------
# Execuções
# ---------------------------------------------------------------------------


class Experiment(Base):
    __tablename__ = "experiment"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Run(Base):
    __tablename__ = "run"
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    manifest_version: Mapped[str] = mapped_column(ForeignKey("process_manifest.version"))
    corpus_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("corpus_version.id"))
    scope_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_document.id"))
    base_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id"))
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("experiment.id"))
    phase: Mapped[str] = mapped_column(String(10))
    context_strategy: Mapped[str] = mapped_column(String(10), default="D")
    model_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    agent_gateway: Mapped[str] = mapped_column(String(20), default="baml")
    baml_src_sha: Mapped[str | None] = mapped_column(String(64))
    thread_id: Mapped[str] = mapped_column(String(80))
    # queued | running | waiting_human | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued")
    current_task: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskExecution(Base):
    __tablename__ = "task_execution"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(String(20))
    bpmn_element_id: Mapped[str | None] = mapped_column(String(80))
    iteracao: Mapped[int] = mapped_column(Integer, default=1)
    tentativa: Mapped[int] = mapped_column(Integer, default=1)
    # running | completed | failed | waiting_human
    status: Mapped[str] = mapped_column(String(20), default="running")
    inicio: Mapped[datetime] = _created()
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (Index("ix_task_execution_run", "run_id", "inicio"),)


class ContextPackageRow(Base):
    __tablename__ = "context_package"
    id: Mapped[uuid.UUID] = _uuid_pk()
    task_execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task_execution.id", ondelete="CASCADE"), unique=True
    )
    strategy: Mapped[str] = mapped_column(String(40))
    items: Mapped[list] = mapped_column(JSONB)
    coverage: Mapped[dict] = mapped_column(JSONB)
    token_estimate: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class LlmCall(Base):
    __tablename__ = "llm_call"
    id: Mapped[uuid.UUID] = _uuid_pk()
    task_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_execution.id", ondelete="CASCADE")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    baml_function: Mapped[str] = mapped_column(String(120))
    client_name: Mapped[str | None] = mapped_column(String(120))
    provider: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    custo_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    status: Mapped[str] = mapped_column(String(20))  # ok | error
    fallback_chain: Mapped[list] = mapped_column(JSONB, default=list)
    prompt_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_output: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class ModelPrice(Base):
    __tablename__ = "model_price"
    provider: Mapped[str] = mapped_column(String(60), primary_key=True)
    model: Mapped[str] = mapped_column(String(120), primary_key=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    input_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    output_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6))


# ---------------------------------------------------------------------------
# Artefatos, itens, dependências, rastreabilidade e evidências
# ---------------------------------------------------------------------------


class Artifact(Base):
    __tablename__ = "artifact"
    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    artifact_type: Mapped[str] = mapped_column(String(80))
    phase: Mapped[str] = mapped_column(String(10))
    __table_args__ = (UniqueConstraint("run_id", "artifact_type", name="uq_artifact_run_type"),)


class ArtifactVersion(Base):
    __tablename__ = "artifact_version"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artifact.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    # draft | in_review | approved | superseded | stale
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # agent | human_edit | consensus | consolidation | deterministic | import
    origin: Mapped[str] = mapped_column(String(20))
    schema_name: Mapped[str | None] = mapped_column(String(120))
    schema_hash: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)
    iteracao: Mapped[int] = mapped_column(Integer, default=1)
    produced_by_task: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_execution.id", ondelete="SET NULL")
    )
    created_by_user: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifact_version.id"))
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        UniqueConstraint("artifact_id", "version_no", name="uq_artifact_version_no"),
    )


class ArtifactItem(Base):
    __tablename__ = "artifact_item"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    item_key: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSONB)
    embedding = mapped_column(Vector(), nullable=True)
    __table_args__ = (
        UniqueConstraint("artifact_version_id", "item_key", name="uq_item_version_key"),
    )


class ArtifactDependency(Base):
    __tablename__ = "artifact_dependency"
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE"), primary_key=True
    )
    via_read: Mapped[str | None] = mapped_column(String(80))


class TraceLink(Base):
    __tablename__ = "trace_link"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    from_item_key: Mapped[str] = mapped_column(String(40))
    to_item_key: Mapped[str] = mapped_column(String(40))
    # derives_from | relates_to | supported_by | depends_on | conflicts_with | refines
    link_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    proposto_por: Mapped[str] = mapped_column(String(20), default="agent")
    origin_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        UniqueConstraint("run_id", "from_item_key", "to_item_key", "link_type", name="uq_trace"),
    )


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    item_key: Mapped[str] = mapped_column(String(40))
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chunk.id", ondelete="SET NULL"))
    chunk_ref: Mapped[str] = mapped_column(String(300))
    citacao: Mapped[str] = mapped_column(Text)
    # OBRIGACAO_NORMATIVA | RECOMENDACAO_TECNICA | DERIVADO_VISAO
    kind: Mapped[str] = mapped_column(String(30))
    # verified | unverified_quote | source_not_provided
    verification: Mapped[str] = mapped_column(String(30))
    human_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------------
# Human-in-the-loop
# ---------------------------------------------------------------------------


class HitlRequest(Base):
    __tablename__ = "hitl_request"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    task_id: Mapped[str] = mapped_column(String(20))
    bpmn_element_id: Mapped[str | None] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))  # approval | consensus
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | decided | cancelled
    round: Mapped[int] = mapped_column(Integer, default=1)
    iteracao: Mapped[int] = mapped_column(Integer, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HitlResponse(Base):
    __tablename__ = "hitl_response"
    id: Mapped[uuid.UUID] = _uuid_pk()
    hitl_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hitl_request.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    decision: Mapped[str] = mapped_column(String(40))
    comentario: Mapped[str | None] = mapped_column(Text)
    # comentários por seção/item: [{"alvo": "vision.stakeholders#STK-02", "texto": "..."}]
    item_comments: Mapped[list] = mapped_column(JSONB, default=list)
    round: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------------
# Exportações, avaliação, eventos, fila, auditoria
# ---------------------------------------------------------------------------


class Export(Base):
    __tablename__ = "export"
    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    formato: Mapped[str] = mapped_column(String(10))
    template_version: Mapped[str] = mapped_column(String(40))
    storage_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class Evaluation(Base):
    __tablename__ = "evaluation"
    id: Mapped[uuid.UUID] = _uuid_pk()
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifact_version.id", ondelete="CASCADE")
    )
    avaliador_tipo: Mapped[str] = mapped_column(String(20))  # human | llm
    avaliador_id: Mapped[str | None] = mapped_column(String(120))
    rubrica_version: Mapped[str] = mapped_column(String(40))
    scores: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class RunEvent(Base):
    __tablename__ = "run_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(40))
    dados: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (Index("ix_run_event_run", "run_id", "id"),)


class Job(Base):
    __tablename__ = "job"
    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    # queued | running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_job_queue", "status", "run_after", "priority"),
        # no máximo um job ativo por execução
        Index(
            "uq_job_active_run",
            "run_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running') AND run_id IS NOT NULL"),
        ),
    )


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(10))  # user | agent | system
    actor_id: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    dados: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = _created()


# ---------------------------------------------------------------------------
# Modelos de linguagem e perfis de inferência — docs/architecture/14-modelos-e-laboratorio.md
# ---------------------------------------------------------------------------


class LlmModel(Base):
    __tablename__ = "llm_model"
    id: Mapped[uuid.UUID] = _uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    # ollama | openai-generic | openai | openai-responses | anthropic | google-ai | baml-named
    provider: Mapped[str] = mapped_column(String(40))
    base_url: Mapped[str | None] = mapped_column(String(300))
    model: Mapped[str] = mapped_column(String(160))
    api_key_env: Mapped[str | None] = mapped_column(String(80))  # nome da variável, nunca o valor
    local: Mapped[bool] = mapped_column(Boolean, default=False)
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InferenceProfile(Base):
    __tablename__ = "inference_profile"
    id: Mapped[uuid.UUID] = _uuid_pk()
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_model.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)  # temperature, max_tokens, num_ctx, think
    checks: Mapped[dict] = mapped_column(JSONB, default=dict)  # resultado do teste de compatibilidade
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        # exatamente um perfil padrão
        Index("uq_inference_profile_default", "is_default", unique=True, postgresql_where=text("is_default")),
    )
