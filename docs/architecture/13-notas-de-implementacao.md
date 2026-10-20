# 13 — Notas de implementação (M0–M3)

Este capítulo registra o que foi implementado e onde a implementação se afastou dos
capítulos anteriores, ou os detalhou. Todo o conteúdo aqui é **[IMPLEMENTADO]**, salvo
indicação em contrário.

## 13.1 O que existe

| Área | Onde | Observação |
|---|---|---|
| Manifesto 0.1.0 | `process/manifest/openupexp-0.1.0.yaml` | Fase 1 executável. Fases 2–4 registradas apenas para conformidade. `openupexp check-manifest` → **conforme** com os 17 `.bpmn` |
| Contratos BAML da Fase 1 | `backend/baml_src/` | 11 funções, com assinatura `(entrada, contexto)` e regras de não invenção herdadas dos workers originais |
| Grafo da Fase 1 | `backend/openupexp/agents/graph.py` | Gerado a partir do manifesto. O gateway 1.3 usa `interrupt()`, e o nó `_apply` faz o roteamento `approve` / `revisit_1_1` / `revisit_1_2` |
| ContextBuilder | `backend/openupexp/context/builder.py` | Estratégias A, C e D. **B levanta `NotImplementedError`** (marco M4) |
| Retrieval | `backend/openupexp/retrieval/` | Chunking por artigo (leis) e por seção (manuais), busca híbrida com RRF, referência explícita por metadado, citação verificada |
| Artefatos | `backend/openupexp/domain/artifacts.py` | Versões, itens com IDs estáveis, dependências, invalidação recursiva, links de rastreabilidade |
| Fila | `backend/openupexp/queue/jobs.py` | Implementação própria com SKIP LOCKED, sem `procrastinate` (E-03 continua aberto) |
| API | `backend/openupexp/api/` | JWT local, papéis por projeto, SSE com um único `LISTEN` mais *polling* de segurança |
| Interface | `frontend/` | Navegador BPMN com status e *drill-down*, central de decisões, revisão com edição e comentários por item, evidências, proveniência, diff, métricas |
| Testes | `backend/tests/` | 24 testes: unidade, banco, fila concorrente, fluxo completo com *revisit*, idempotência do gateway, API com RBAC, *lint* de domínio nos prompts |

## 13.2 Decisões tomadas durante a implementação

| # | Decisão | Motivo | Capítulo afetado |
|---|---|---|---|
| D-01 | Artefatos pertencem a uma **execução** (`artifact.run_id`). Fases futuras referenciam a execução anterior por `run.base_run_id` | Repetições experimentais do mesmo projeto não podem compartilhar artefatos | 06 |
| D-02 | A versão "atual" é sempre a de maior `version_no`. `superseded` só indica que existe versão mais nova | Simplifica as consultas e preserva os itens anteriores para a preservação de IDs | 06 §6.4 |
| D-03 | **Edição humana não invalida dependentes.** As dependências registradas continuam apontando para a versão que o agente efetivamente usou | Correções pequenas (texto, responsabilidade) não devem forçar retorno. A proveniência real é preservada. Se a mudança for estrutural, o revisor pede *revisit* | 07 §7.3 |
| D-04 | Ao preencher um campo, o revisor remove automaticamente a lacuna correspondente | Evita lacunas "fantasmas" no documento | 08 §8.2 |
| D-05 | Na **consolidação (1.3.2)**, o documento é remontado a partir das versões mais recentes, incluindo as edições humanas, e gravado como nova versão `vision.draft` aprovada | O rascunho de 1.2.4 não reflete edições feitas durante a revisão | 02 §2.5 |
| D-06 | No *revisit*, os artefatos do subprocesso refeito e dos posteriores ficam `stale`. Os anteriores voltam a `draft`. Os contadores de iteração avançam a partir do subprocesso escolhido | Segue a anotação do BPMN (I-01), sem a granularidade fina | 07 |
| D-07 | A coluna `embedding` não tem dimensão fixa (`vector`). O índice HNSW fica para quando o corpus justificar | Cada `corpus_version` pode usar um modelo diferente. Com cerca de 700 chunks, a varredura exata é rápida | 05, 06 |
| D-08 | O modelo padrão de embedding é `intfloat/multilingual-e5-base`, com prefixos `query:`/`passage:` | Resolve P-05 (limite de 128 tokens). A comparação com `bge-m3` continua em E-01 | 05 §5.7 |
| D-09 | Seções muito curtas de manuais (sumários) são fundidas com a seção seguinte | O manual de exame substantivo é quase todo sumário: sem a fusão, a mediana era de 55 caracteres | 05 §5.7 |
| D-10 | O *coverage guard* foi implementado no posicionamento (um por stakeholder, com uma nova tentativa) e nos limites (toda pergunta do checklist recebe resposta ou lacuna). Faltas persistentes falham a tarefa | As únicas tarefas da Fase 1 com completude exigida | 05 §5.5 |
| D-11 | O gateway simulado (`AGENT_GATEWAY=fake`) também gera `llm_call` (provedor `fake`) | Testes e demonstrações exercitam a observabilidade sem LLM | 09 |
| D-12 | O protótipo original foi movido para `legacy/` e continua executável (caminhos agora relativos ao próprio arquivo). Os PDFs do caso INPI foram para `experiments/cases/inpi/` (`escopo_projeto.pdf` e `corpus/`), compartilhados pelo protótipo e pela plataforma. Apenas P-10 foi corrigido em `legacy/main.py` | Raiz organizada conforme a estrutura do cap. 04, sem duplicar o corpus | 04 §4.6 |
| D-13 | A estratégia A anexa o documento integral atual a **todas** as tarefas, inclusive as determinísticas | Mantém a linha de base comparável: o pacote registra exatamente o que seria entregue | 05 §5.4 |

## 13.3 Limitações conhecidas

- **Execução com LLM real ainda não validada.** O caminho BAML existe e está coberto pela
  renderização offline do prompt (`b.request`), mas não foi executado de ponta a ponta sem
  chaves no ambiente. Primeiro passo de validação: `cp .env.example .env`, preencher uma
  chave, iniciar a Fase 1 com "LLM real".
- **Tabela de preços vazia.** Sem linhas em `model_price`, o custo fica nulo.
- **Fora desta entrega:**
  - consenso (`hitl_consensus`), previsto para M5;
  - estratégia B, harness de experimentos e gabaritos, previstos para M4;
  - exportação `.docx`/`.pdf` via pandoc.
- **Bundle do frontend:** cerca de 610 KB (bpmn-js). A divisão de código pode vir depois.
- **Avisos do bpmn-js:** os arquivos com referências quebradas (I-02) renderizam, mas geram
  avisos de importação no console do navegador.
