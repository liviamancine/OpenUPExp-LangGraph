# 06 — Modelo de dados

> **Em poucas palavras.** Tudo o que a plataforma produz fica guardado de forma estruturada e
> com histórico: cada artefato tem versões (rascunho, em revisão, aprovada, substituída,
> desatualizada), cada item tem um identificador estável (STK-01, REQ-03…), e cada decisão
> humana fica registrada. Nada é sobrescrito.

### Tabelas acrescentadas depois do desenho original [IMPLEMENTADO]

| Tabela | O que guarda | Capítulo |
|---|---|---|
| `llm_model`, `inference_profile` | Modelos de IA cadastrados e seus perfis de uso (temperatura, limites), com o resultado do teste de compatibilidade | 14 |
| `lab_comparison`, `lab_trial`, `lab_rating` | Comparações do laboratório, cada tentativa (modelo, estratégia, repetição, métricas) e as notas humanas | 14 |
| `lab_gold` | Gabaritos por projeto e tarefa | 14 |
| `corpus_version.purpose` / `run_id` | Separa a base de consulta do material das entrevistas de cada execução | 13 |

Além disso, `run.model_profile` passou a guardar a **configuração completa do modelo** usada na
execução (inclusive a versão dos pesos do modelo local).


## 6.1 Modelo conceitual

```mermaid
flowchart LR
  PROJETO["Projeto"] -->|tem| MEMBRO["Membro"]
  PROJETO -->|executa| EXECUCAO["Execução"]
  EXECUCAO -->|segue| MANIFESTO["Manifesto"]
  EXECUCAO -->|usa| VERSAOCORPUS["Versão do corpus"]
  EXECUCAO -->|compõe-se de| EXECUCAOTAREFA["Execução de tarefa"]
  EXECUCAOTAREFA -->|recebe| PACOTECONTEXTO["Pacote de contexto"]
  EXECUCAOTAREFA -->|faz| CHAMADALLM["Chamada LLM"]
  EXECUCAOTAREFA -->|produz| VERSAOARTEFATO["Versão de artefato"]
  VERSAOARTEFATO -->|contém| ITEM["Item"]
  VERSAOARTEFATO -->|depende de| VERSAOARTEFATO
  ITEM -->|liga-se a| ITEM
  ITEM -->|sustentado por| EVIDENCIA["Evidência"]
  EVIDENCIA -->|cita| TRECHO["Trecho"]
  TRECHO -->|pertence a| DOCUMENTOFONTE["Documento-fonte"]
  DOCUMENTOFONTE -->|indexado em| VERSAOCORPUS
  EXECUCAO -->|abre| SOLICITACAOHITL["Solicitação HITL"]
  SOLICITACAOHITL -->|recebe| RESPOSTAHITL["Resposta HITL"]
  RESPOSTAHITL -->|pode gerar| VERSAOARTEFATO
  VERSAOARTEFATO -->|exportada como| EXPORTACAO["Exportação"]
  VERSAOARTEFATO -->|avaliada por| AVALIACAO["Avaliação"]
```

## 6.2 Modelo lógico (ER)

```mermaid
erDiagram
  APP_USER ||--o{ PROJECT_MEMBER : participa
  PROJECT ||--o{ PROJECT_MEMBER : tem
  PROJECT ||--o{ RUN : executa
  PROCESS_MANIFEST ||--o{ RUN : rege
  CORPUS_VERSION ||--o{ RUN : fixa
  PROJECT ||--o{ CORPUS_VERSION : possui
  CORPUS_VERSION ||--o{ SOURCE_DOCUMENT : inclui
  SOURCE_DOCUMENT ||--o{ CHUNK : divide
  RUN ||--o{ TASK_EXECUTION : contem
  TASK_EXECUTION ||--o| CONTEXT_PACKAGE : recebe
  TASK_EXECUTION ||--o{ LLM_CALL : faz
  PROJECT ||--o{ ARTIFACT : possui
  ARTIFACT ||--o{ ARTIFACT_VERSION : versiona
  TASK_EXECUTION ||--o{ ARTIFACT_VERSION : produz
  ARTIFACT_VERSION ||--o{ ARTIFACT_ITEM : contem
  ARTIFACT_VERSION ||--o{ ARTIFACT_DEPENDENCY : usa
  ARTIFACT_ITEM ||--o{ TRACE_LINK : origem
  ARTIFACT_ITEM ||--o{ EVIDENCE : sustentado
  CHUNK ||--o{ EVIDENCE : citado
  RUN ||--o{ HITL_REQUEST : abre
  HITL_REQUEST ||--o{ HITL_RESPONSE : recebe
  APP_USER ||--o{ HITL_RESPONSE : responde
  ARTIFACT_VERSION ||--o{ EXPORT : gera
  ARTIFACT_VERSION ||--o{ EVALUATION : avaliada
  RUN ||--o{ RUN_EVENT : emite
  JOB }o--|| RUN : executa

  APP_USER {
    uuid id PK
    text email
    text nome
    text papel_global
  }
  PROJECT {
    uuid id PK
    text nome
    text dominio
    text descricao
    timestamptz criado_em
  }
  PROJECT_MEMBER {
    uuid project_id FK
    uuid user_id FK
    text papel_plataforma
    text papel_openupexp
  }
  PROCESS_MANIFEST {
    text version PK
    text bpmn_commit
    jsonb conteudo
    text sha256
  }
  CORPUS_VERSION {
    uuid id PK
    uuid project_id FK
    text embedding_model
    int embedding_dim
    text chunker_version
    timestamptz criado_em
  }
  SOURCE_DOCUMENT {
    uuid id PK
    uuid corpus_version_id FK
    text arquivo
    text source_kind
    text sha256
    text storage_path
  }
  CHUNK {
    uuid id PK
    uuid source_document_id FK
    text stable_key
    text texto
    int pagina
    jsonb meta
    tsvector tsv
    vector embedding
  }
  RUN {
    uuid id PK
    uuid project_id FK
    text manifest_version FK
    uuid corpus_version_id FK
    text phase
    text context_strategy
    jsonb model_profile
    text baml_src_commit
    text thread_id
    text status
    uuid experiment_id
  }
  TASK_EXECUTION {
    uuid id PK
    uuid run_id FK
    text task_id
    text bpmn_element_id
    int iteracao
    int tentativa
    text status
    timestamptz inicio
    timestamptz fim
    text erro
  }
  CONTEXT_PACKAGE {
    uuid id PK
    uuid task_execution_id FK
    text strategy
    jsonb items
    jsonb coverage
    int token_estimate
    text sha256
  }
  LLM_CALL {
    uuid id PK
    uuid task_execution_id FK
    text baml_function
    text client_name
    text provider
    text model
    int input_tokens
    int output_tokens
    int latency_ms
    numeric custo_usd
    text status
    jsonb fallback_chain
    text prompt_sha256
  }
  ARTIFACT {
    uuid id PK
    uuid project_id FK
    text artifact_type
    text phase
  }
  ARTIFACT_VERSION {
    uuid id PK
    uuid artifact_id FK
    int version_no
    text status
    text origin
    text schema_name
    text schema_hash
    jsonb content
    uuid produced_by_task FK
    uuid created_by_user FK
    uuid supersedes_id FK
    timestamptz criado_em
  }
  ARTIFACT_ITEM {
    uuid id PK
    uuid artifact_version_id FK
    text item_key
    jsonb content
    vector embedding
  }
  ARTIFACT_DEPENDENCY {
    uuid version_id FK
    uuid depends_on_version_id FK
    text via_read
  }
  TRACE_LINK {
    uuid id PK
    text from_item_key
    text to_item_key
    uuid project_id FK
    text link_type
    text status
    text proposto_por
  }
  EVIDENCE {
    uuid id PK
    uuid artifact_item_id FK
    uuid chunk_id FK
    text citacao
    text kind
    bool verified
    text human_status
  }
  HITL_REQUEST {
    uuid id PK
    uuid run_id FK
    text bpmn_element_id
    text kind
    text idempotency_key
    jsonb payload
    jsonb policy
    text status
    timestamptz due_at
  }
  HITL_RESPONSE {
    uuid id PK
    uuid hitl_request_id FK
    uuid user_id FK
    text decision
    text comentario
    jsonb edits
    timestamptz criado_em
  }
  EXPORT {
    uuid id PK
    uuid artifact_version_id FK
    text formato
    text template_version
    text storage_path
    text sha256
  }
  EVALUATION {
    uuid id PK
    uuid artifact_version_id FK
    text avaliador_tipo
    text rubrica_version
    jsonb scores
  }
  RUN_EVENT {
    bigint id PK
    uuid run_id FK
    text tipo
    jsonb dados
    timestamptz criado_em
  }
  JOB {
    uuid id PK
    text kind
    jsonb payload
    text status
    int attempts
    text locked_by
    timestamptz locked_at
    timestamptz run_after
  }
```

Tabelas complementares, fora do diagrama por legibilidade:

- `audit_event` (append-only: ator, ação, entidade, hash antes/depois);
- `experiment` (configuração da matriz e semente);
- `gold_item` (gabaritos — cap. 09);
- os checkpoints do LangGraph, criados pelo `PostgresSaver.setup()`.

## 6.3 Decisões do modelo

| Decisão | Motivo |
|---|---|
| **`ARTIFACT_VERSION.content` em JSONB, validado pelo schema BAML** (`schema_name` + `schema_hash`) | Artefatos mudam de forma quando a teoria muda; JSONB evita uma migração por campo, e o hash do schema garante que se saiba com qual contrato a versão foi produzida |
| **`ARTIFACT_ITEM` com `item_key` estável** (`STK-02`, `REQ-014`) | Os IDs sobrevivem entre versões: o `REQ-014` da v3 é o mesmo requisito do `REQ-014` da v1. Diffs, rastreabilidade e "correções humanas" são medidas por item |
| **`TRACE_LINK` por `item_key`, não por versão** | Rastreabilidade é uma relação entre conceitos; o status do link (`proposed`/`accepted`/`rejected`) é versionado à parte |
| **`ARTIFACT_DEPENDENCY` registrado a partir do `ContextPackage`** | A dependência real é "o que o agente viu", não apenas o que o manifesto declarou |
| **`origin` da versão:** `agent`, `human_edit`, `consensus`, `consolidation`, `import` | Permite medir quanto do artefato final é humano × IA |
| **`HITL_RESPONSE` imutável** | Auditoria de decisões; um novo voto é uma nova linha |
| **Vetores em `CHUNK` e `ARTIFACT_ITEM`** | Reference Base e similaridade entre requisitos (cap. 03) |

Índices principais:
- `HNSW (embedding vector_cosine_ops)` em `chunk` e `artifact_item`;
- `GIN (tsv)` em `chunk`;
- `UNIQUE (artifact_id, version_no)`;
- `UNIQUE (hitl_request.idempotency_key)`;
- índice único parcial em `job (payload->>'run_id') WHERE status IN ('queued','running')`.

## 6.4 Ciclo de vida das versões de artefato

```mermaid
stateDiagram-v2
  [*] --> draft: agente produz / humano edita
  draft --> in_review: fase chega ao gateway
  in_review --> approved: decisão approve (consolidação)
  in_review --> superseded: decisão revisit (refeito)
  draft --> superseded: nova versão do mesmo artefato
  approved --> superseded: nova versão aprovada (iteração seguinte)
  draft --> stale: dependência foi substituída
  in_review --> stale: dependência foi substituída
  stale --> superseded: tarefa reexecutada
  approved --> [*]
  superseded --> [*]
```

Regras:
- Existe no máximo **uma** versão `approved` vigente por artefato.
- Nenhuma versão é apagada.
- `approved` só é atingido via `HITL_RESPONSE` do papel autorizado (cap. 07).
- Uma versão `stale` não pode ser aprovada; a UI bloqueia a aprovação até a reexecução.

## 6.5 Invalidação automática

Quando a versão `v` é substituída, todas as versões que dependem dela (transitivamente)
e que ainda não estão `approved`/`superseded` passam a `stale`:

```sql
-- [PROPOSTA]
WITH RECURSIVE dependentes AS (
  SELECT d.version_id
  FROM artifact_dependency d
  WHERE d.depends_on_version_id = :versao_substituida
  UNION
  SELECT d.version_id
  FROM artifact_dependency d
  JOIN dependentes x ON d.depends_on_version_id = x.version_id
)
UPDATE artifact_version av
SET status = 'stale'
FROM dependentes x
WHERE av.id = x.version_id AND av.status IN ('draft', 'in_review')
RETURNING av.id;
```

**Versões aprovadas de fases anteriores:** uma mudança na Fase 2 não invalida a Visão
aprovada. O contrário, sim: se a Visão for reaberta, tudo da Fase 2 em diante fica
`stale`. Reabrir uma fase já aprovada é uma ação explícita e auditada do Engenheiro.

**[PENDENTE-AUTORA]:** a teoria permite reabrir uma fase aprovada? O BPMN só prevê
retorno dentro da mesma macroatividade, e `Fase Concepção.md` diz que o DRE "é
continuamente atualizado a cada iteração".

## 6.6 Auditoria

Toda mutação de domínio grava `audit_event(actor_type, actor_id, action, entity,
entity_id, before_sha, after_sha, at)`:
- `actor_type`: `user`, `agent` ou `system`;
- `action`: por exemplo `approve`, `edit`, `index_corpus`.

Junto com `llm_call`, `context_package` e `hitl_response`, isso permite responder a
perguntas como:
- quem decidiu, quando e com base em quê;
- o que o agente viu;
- qual modelo foi usado e quanto custou.
