export interface User { id: string; email: string; nome: string; papel_global: string }

export interface Project { id: string; nome: string; dominio: string | null; descricao: string | null; created_at: string }

export interface RunSummary {
  id: string; phase: string; status: string; context_strategy: string; agent_gateway: string;
  current_task: string | null; error: string | null; manifest_version: string;
  model_profile: Record<string, unknown>; created_at: string; updated_at: string; base_run_id: string | null;
}

export interface Source {
  id: string; arquivo: string; source_kind: string; paginas: number | null; ativo: boolean;
  meta: Record<string, unknown>; sha256: string;
}

export interface Corpus {
  id: string; status: string; embedding_model: string; embedding_provider: string;
  stats: Record<string, number>; created_at: string;
}

export interface ProjectDetail extends Project {
  meu_papel: string;
  membros: { user: User; papel_plataforma: string; papel_openupexp: string | null }[];
  fontes: Source[]; corpora: Corpus[]; execucoes: RunSummary[];
}

export interface RunDetail extends RunSummary {
  project_id: string; corpus_version_id: string | null; baml_src_sha: string | null;
  pending_hitl: string | null;
  metricas: { llm_calls: number; input_tokens: number; output_tokens: number; latency_ms: number; custo_usd: number | null };
}

export interface TaskExec {
  id: string; task_id: string; bpmn_element_id: string | null; iteracao: number; tentativa: number;
  status: string; inicio: string; fim: string | null; erro: string | null; meta: Record<string, unknown>; tokens: number;
}

export interface PackageItem { origin: string; ref: string; artifact: string | null; version_id: string | null; content: unknown; reason: string }

export interface LlmCall {
  id: string; function: string; client: string | null; provider: string | null; model: string | null;
  input_tokens: number | null; output_tokens: number | null; latency_ms: number | null; custo_usd: number | null;
  status: string; fallback_chain: { client: string; provider: string; selected: boolean; model: string | null }[];
  error: string | null; prompt_sha256: string | null;
}

export interface TaskDetail {
  id: string; task_id: string; status: string; iteracao: number; erro: string | null; meta: Record<string, unknown>;
  context_package: null | {
    strategy: string; items: PackageItem[]; token_estimate: number; sha256: string;
    coverage: { required_ids: string[]; included_ids: string[]; missing_ids: string[]; satisfied: boolean; output_missing_ids: string[] };
  };
  llm_calls: LlmCall[];
}

export interface VersionRef {
  id: string; artifact_type: string; version_no: number; status: string; origin: string; schema_name: string | null;
  iteracao: number; created_at: string; created_by_user: string | null; supersedes_id: string | null;
}

export interface ArtifactSummary extends VersionRef {
  title: string; itens: number | null; editavel: boolean; list_field: string | null; secao: boolean;
}

export interface Evidence {
  id: string; item_key: string; chunk_ref: string; citacao: string; kind: string; verification: string; human_status: string;
  chunk: null | { id: string; stable_key: string; texto: string; pagina: number | null; meta: Record<string, unknown>; source_kind: string };
}

export interface VersionDetail extends VersionRef {
  title: string; run_id: string; content: Record<string, unknown>; editavel: boolean;
  list_field: string | null; documento: boolean;
  historico: VersionRef[]; dependencias: { version_id: string; artifact: string; version_no: number; status: string }[];
  evidencias: Evidence[];
}

export interface Outcome { next: string; comment_required: boolean }

export interface HitlRequest {
  id: string; run_id: string; task_id: string; bpmn_element_id: string | null; kind: string; status: string;
  payload: { reviews?: string; name?: string; phase?: string; input_kind?: string; outcomes: Record<string, Outcome> };
  policy: Record<string, unknown>; round: number; iteracao: number; created_at: string; decided_at: string | null;
  due_at: string | null;
  projeto: { id: string; nome: string } | null; run_status: string | null;
}

export interface Check { id: string; descricao: string; ok: boolean; detalhes: string[] }

export interface HitlDetail extends HitlRequest {
  meu_papel: string; phase: string;
  review_report: { checks: Check[]; lacunas_por_artefato: Record<string, number> } | null;
  stale: string[];
  consenso?: { concordo: number; ressalvas: number; objecao: number; participantes: number };
  material?: { id: string; arquivo: string; paginas: number | null }[];
  respostas: {
    id: string; user_id: string | null; user_nome: string | null; decision: string; comentario: string | null;
    item_comments: ItemComment[]; created_at: string;
  }[];
}

export interface ItemComment { alvo: string; texto: string }

export interface TaskSpec {
  id: string; name: string; bpmn_element: string | null; bpmn_anchor: string | null; mechanism: string;
  baml_function: string | null; handler: string | null; theory_ref: string | null; pending: string[];
  reads: { artifact: string; select: string; required: boolean }[];
  writes: { artifact: string; item_prefix: string | null; evidence: string }[];
  outcomes: Record<string, Outcome>;
}
export interface SubprocessSpec { id: string; name: string | null; bpmn_file: string; bpmn_element: string; pending: string[]; tasks: TaskSpec[] }
export interface PhaseSpec { id: string; name: string; openup_phase: string; implemented: boolean; bpmn_file: string; bpmn_element: string; subprocesses: SubprocessSpec[] }
export interface Manifest { manifest_version: string; root: { bpmn_file: string }; phases: PhaseSpec[]; sha256: string; bpmn_commit: string | null }

export interface RunEvent { tipo: string; dados: Record<string, unknown>; at: string }

export interface Diff {
  tipo: "itens" | "documento";
  adicionados?: Record<string, unknown>[]; removidos?: Record<string, unknown>[];
  alterados?: { id: string; campos: { campo: string; antes: unknown; depois: unknown }[] }[];
  campos: { campo: string; antes: unknown; depois: unknown }[];
}

export interface Metrics {
  total: RunDetail["metricas"];
  por_tarefa: { task_id: string; iteracao: number; function: string; chamadas: number; input_tokens: number; output_tokens: number; latency_ms: number; custo_usd: number | null }[];
}

export interface LlmProfile {
  id: string; slug: string; nome: string; padrao: boolean; protegido: boolean; disponivel: boolean;
  params: Record<string, unknown>;
  modelo: { slug: string; nome: string; provider: string; model: string; local: boolean; protegido: boolean; descricao: string | null };
}

export interface ModelSnapshot {
  profile_id?: string; profile_slug?: string; profile_nome?: string; provider?: string; model?: string;
  local?: boolean; model_digest?: string | null;
}

export interface CompatResult {
  status: "na_fila" | "concluido"; ok?: boolean; at: string; detalhe?: string; latency_ms?: number;
  input_tokens?: number | null; output_tokens?: number | null;
}
export interface ConnResult { ok: boolean; at: string; detalhe: string; latency_ms: number; modelos?: string[]; modelo_encontrado?: boolean }
export interface AdminProfile {
  id: string; slug: string; nome: string; params: Record<string, unknown>; protegido: boolean;
  padrao_marcado: boolean; padrao_efetivo: boolean; habilitado: boolean; compat: CompatResult | null;
}
export interface AdminModel {
  id: string; slug: string; nome: string; provider: string; model: string; endereco: string | null;
  api_key_env: string | null; local: boolean; protegido: boolean; habilitado: boolean; chave_configurada: boolean | null;
  descricao: string | null; conexao: ConnResult | null; perfis: AdminProfile[];
}
export interface AdminOverview {
  servidores_permitidos: string[]; provedores: Record<string, string>; modelo_local_ligado: boolean;
  padrao_efetivo: string; modelos: AdminModel[];
  parametros: Record<string, { tipo: string; min: number | null; max: number | null }>;
}
