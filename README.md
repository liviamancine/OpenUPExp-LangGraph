<p align="center"><img src="frontend/public/logo-horizontal.svg" alt="OpenUPExp" width="360"></p>

# OpenUPExp — plataforma

Engenharia de requisitos de explicabilidade orientada ao processo **OpenUPExp**, com agentes de IA
(LangGraph + BAML), validação humana nos pontos de decisão do BPMN, rastreabilidade e gestão de contexto.

- **Arquitetura e decisões:** [`docs/architecture/`](docs/architecture/README.md) — comece pela
  [visão geral em linguagem simples](docs/architecture/00-visao-geral.md)
- **Manifesto do processo (BPMN → execução):** [`process/manifest/openupexp-0.4.0.yaml`](process/manifest/openupexp-0.4.0.yaml)
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
| M4 Experimentos (estratégia B, harness, gabaritos, avaliação) | parcial: estratégia B, laboratório, gabaritos e CSV prontos; faltam gabaritos de especialistas e novos casos |
| M5 Fase 2 + consenso | implementado com formatos provisórios (manifesto 0.2.0; ver cap. 12 §12.4) |
| M6 Fases 3–4 | implementado com formatos provisórios (manifestos 0.3.0 e 0.4.0; cap. 12 §12.5–§12.6) |
| M7 Modelos de IA (catálogo, administração, modelo local opcional) | implementado (cap. 14) |
| M8 Laboratório de modelos | implementado (cap. 14) |

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

### Modelo local (opcional)

O modelo local (Qwen3 4B via Ollama) **não sobe por padrão**: sem placa de vídeo ele é lento
(~1,5 min por chamada) e ocupa ~3 GB de RAM e boa parte da CPU. Para ligar:

```bash
# no .env: LOCAL_LLM_ENABLED=true (e, se quiser, OLLAMA_CPUS / OLLAMA_MEM_LIMIT)
docker compose --profile local-llm up -d   # baixa ~2,5 GB na primeira vez
```

Também é possível apontar `OLLAMA_URL` para um Ollama em outra máquina. Detalhes no
[cap. 14](docs/architecture/14-modelos-e-laboratorio.md).

Acesse <http://localhost:5173>, entre como a engenheira, abra o projeto e inicie a Fase 1.
Sem chave de LLM nem modelo local, escolha **Modo de teste** para percorrer o processo (HITL, retornos,
versões, exportação) com saídas determinísticas.

Com a Visão aprovada, inicie a **Fase 2** escolhendo essa execução como base. A execução
pausa em 2.2.1 para você enviar o material de elicitação (fonte do tipo "Material de
elicitação") e em 2.2.5 para o consenso: membros com papel *participante* registram posição
na Central de decisões, e a engenheira encerra a rodada.

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
    agents/            grafo LangGraph por fase, handlers das Fases 1–3, gateway BAML/simulado
    context/           ContextBuilder (estratégias A, B, C, D)
    retrieval/         ingestão, chunking estrutural, embeddings, busca híbrida, citações
    domain/            artefatos versionados, invalidação, serviços, eventos, diff
    queue/             fila em PostgreSQL (SKIP LOCKED)
    process/           manifesto e verificação contra o BPMN
    exports/           Documento de Visão (template derivado da teoria)
    observability/     chamadas LLM via Collector do BAML
    api/               FastAPI (REST + SSE), autenticação e papéis
  migrations/          Alembic
  tests/               unidade, banco, fluxos completos das Fases 1–4, API
frontend/              React + Vite + TypeScript + bpmn-js
process/               manifesto versionado e BPMN de referência
experiments/cases/     escopo e corpus de cada estudo de caso (INPI)
legacy/                protótipo original de 6 workers (linha de base)
docs/architecture/     arquitetura, decisões e notas de implementação
```
