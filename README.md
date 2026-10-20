# OpenUPExp — plataforma

Engenharia de requisitos de explicabilidade orientada ao processo **OpenUPExp**, com agentes de IA
(LangGraph + BAML), validação humana nos pontos de decisão do BPMN, rastreabilidade e gestão de contexto.

- **Arquitetura e decisões:** [`docs/architecture/`](docs/architecture/README.md)
- **Manifesto do processo (BPMN → execução):** [`process/manifest/openupexp-0.1.0.yaml`](process/manifest/openupexp-0.1.0.yaml)
- **BPMN de referência** (cópia fixada do repositório teórico): [`process/bpmn/`](process/bpmn/)
- **Estudo de caso INPI** (escopo e base de referência): [`experiments/cases/inpi/`](experiments/cases/inpi/)
- **Protótipo original** (6 workers, linha de base experimental): [`legacy/`](legacy/README.md)

## Estado

| Marco | Situação |
|---|---|
| M0 Fundações (compose, banco, fila, migrações, manifesto) | implementado |
| M1 Retrieval e evidências (chunking estrutural, busca híbrida, verificação de citação) | implementado |
| M2 Fase 1 executável (grafo, HITL de aprovação, revisit, versionamento, exportação) | implementado |
| M3 Frontend (BPMN com status, decisões, edição, evidências, métricas) | implementado (MVP) |
| M4 Experimentos (estratégia B, harness, gabaritos, avaliação) | pendente |
| M5 Fase 2 + consenso | pendente — depende dos templates da teoria |
| M6 Fases 3–4 | pendente — depende dos templates da teoria |

As interpretações de trabalho adotadas para as decisões pendentes da autora estão em
[`docs/architecture/12-decisoes-pendentes.md`](docs/architecture/12-decisoes-pendentes.md).

## Subir com Docker

```bash
cp .env.example .env          # preencha ao menos uma chave de LLM (GROQ_API_KEY, OPENAI_API_KEY…)
docker compose up -d --build  # db, migrate, api (:8010), worker, frontend (:5173)

# usuários
docker compose exec worker openupexp create-user admin@exemplo.org "Admin" --admin
docker compose exec worker openupexp create-user eng@exemplo.org "Engenheira"

# estudo de caso INPI (experiments/cases/inpi, com embeddings)
docker compose exec worker openupexp seed-inpi --owner-email eng@exemplo.org
```

Acesse <http://localhost:5173>, entre como a engenheira, abra o projeto e inicie a Fase 1.
Sem chave de LLM, escolha **Agentes: Simulado** para percorrer o processo (HITL, retornos,
versões, exportação) com saídas determinísticas.

## Desenvolvimento local

```bash
docker compose up -d db
cd backend
uv sync --extra embeddings
uv run alembic upgrade head
uv run baml-cli generate --from baml_src      # após alterar contratos BAML
uv run openupexp check-manifest              # conformidade manifesto ↔ BPMN
uv run uvicorn openupexp.api.main:app --port 8010 --reload
uv run openupexp worker                      # em outro terminal
uv run pytest                                # usa o banco openupexp_test, gateway simulado

cd ../frontend && npm install && npm run dev  # http://localhost:5173 (proxy /api → :8010)
```

CLI útil sem a interface: `openupexp start <projeto> --gateway fake`, `openupexp status <execução>`,
`openupexp decide <execução> revisit_1_2 --comment "..."`, `openupexp drain`.

## Componentes

```
backend/
  baml_src/            contratos e prompts dos agentes (fonte única)
  openupexp/
    agents/            grafo LangGraph da Fase 1, handlers por tarefa, gateway BAML/simulado
    context/           ContextBuilder (estratégias A, C, D; B no M4)
    retrieval/         ingestão, chunking estrutural, embeddings, busca híbrida, citações
    domain/            artefatos versionados, invalidação, serviços, eventos, diff
    queue/             fila em PostgreSQL (SKIP LOCKED)
    process/           manifesto e verificação contra o BPMN
    exports/           Documento de Visão (template derivado da teoria)
    observability/     chamadas LLM via Collector do BAML
    api/               FastAPI (REST + SSE), autenticação e papéis
  migrations/          Alembic
  tests/               unidade, banco, fluxo completo da Fase 1, API
frontend/              React + Vite + TypeScript + bpmn-js
process/               manifesto versionado e BPMN de referência
experiments/cases/     escopo e corpus de cada estudo de caso (INPI)
legacy/                protótipo original de 6 workers (linha de base)
docs/architecture/     arquitetura, decisões e notas de implementação
```
