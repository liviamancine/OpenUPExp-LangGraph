# 11 — Roteiro, testes e riscos

> **Em poucas palavras.** A plataforma foi construída em marcos, um de cada vez, cada um com um
> critério de "pronto" verificável. Quase todos estão concluídos; o que falta é sobretudo
> **pesquisa** (gabaritos, estudos de caso, repetições) e as **decisões da autora** (cap. 12).

## 11.1 Roteiro

```mermaid
flowchart LR
  M0["M0 Fundações ✓"] --> M1["M1 Busca e evidências ✓"]
  M1 --> M2["M2 Etapa 1 executável ✓"]
  M2 --> M3["M3 Interface ✓"]
  M3 --> M5["M5 Etapa 2 + consenso ✓"]
  M5 --> M6["M6 Etapas 3 e 4 ✓"]
  M6 --> M7["M7 Modelos de IA<br/>e modelo local ✓"]
  M7 --> M8["M8 Laboratório ✓"]
  M8 --> M4["M4 Experimentos<br/>(parcial)"]
  T[["Decisões da autora<br/>(cap. 12)"]] -. substituem as<br/>interpretações provisórias .-> M5 & M6
```

| Marco | O que entrega | Situação |
|---|---|---|
| **M0 Fundações** | Projeto organizado, Docker Compose, banco, fila, migrações, testes automáticos | Concluído |
| **M1 Busca e evidências** | Divisão de leis por artigo e de manuais por seção, busca híbrida, conferência de citações | Concluído |
| **M2 Etapa 1 executável** | Visão de ponta a ponta, com aprovação, retorno a 1.1/1.2 e documento exportado | Concluído |
| **M3 Interface** | Interface web; depois **redesenhada** com linguagem simples, identidade visual e diagramas em português | Concluído |
| **M5 Etapa 2 + consenso** | Elicitação com envio de material, consenso e aprovação | Concluído (formatos provisórios) |
| **M6 Etapas 3 e 4** | Análise e Especificação; DRE completo | Concluído (formatos provisórios) |
| **M7 Modelos de IA** | Catálogo de modelos, administração, testes de conexão e compatibilidade, **modelo local opcional** | Concluído (cap. 14) |
| **M8 Laboratório** | Mesma tarefa em vários modelos e estratégias de contexto, repetições, gabarito, notas e CSV | Concluído (cap. 14) |
| **M4 Experimentos** | Gabaritos de especialistas, juiz por IA, ≥ 2 novos domínios, campanha com repetições | **Parcial**: as ferramentas existem (M8); faltam os gabaritos, os casos e a campanha |

### O que falta

1. **Conduzir um projeto inteiro com IA real** (até agora: tarefas avulsas no laboratório e o
   processo completo em modo de teste).
2. **Decisões da autora** (cap. 12), substituindo os formatos provisórios.
3. **Gabaritos feitos por especialistas** e medida de concordância entre eles.
4. **Juiz por IA** para emparelhar respostas e gabaritos além da semelhança de texto.
5. **Novos estudos de caso** em outros domínios (E-09).

### Plano original dos marcos

O texto abaixo é o plano escrito no início, mantido como registro.

| Marco | Escopo | Critério de saída |
|---|---|---|
| **M0 Fundações** | `pyproject.toml` com versões fixadas; `generators.baml`; reorganização de diretórios e `legacy/`; `docker-compose` (db, api, worker, frontend vazio); Alembic; job runner com SKIP LOCKED; CI (lint, testes); correção do `"\\n"` (P-10) no legado | `docker compose up` sobe tudo; o legado roda e reproduz `blackboard.json`; teste da fila passa |
| **M1 Retrieval e evidências** | Ingestão com chunkers estruturais (lei, manual); `corpus_version`; embeddings escolhidos; busca híbrida RRF; filtro por referência explícita; verificação mecânica de citação | Conjunto de 20–30 consultas de teste com trechos esperados (ex.: "Art. 20 LGPD") — recall@10 medido e superior ao Chroma atual |
| **M2 Fase 1 executável** | Manifesto 0.1 da Fase 1 + teste manifesto↔BPMN; Artifact Store; ContextBuilder C e D; contratos BAML da Fase 1; subgrafos 1.1/1.2/1.3; `ApprovalGate`; API mínima | Execução completa INPI: pausa em 1.3, retomada, *revisit* 1.2 com invalidação correta, aprovação final, export `.md` |
| **M3 Frontend MVP** | Navegador BPMN com overlays; linha do tempo com SSE; inbox; aprovação com edição e comentários; evidências; diff; login e RBAC | Um Engenheiro conduz a Fase 1 inteira pela web |
| **M4 Observabilidade e experimentos** | `llm_call`; custos; ContextBuilder A e B; experimentos; gabarito; rubrica e avaliação humana; LLM-juiz | Experimento piloto: 4 estratégias × 1 caso × 5 repetições |
| **M5 Fase 2 + consenso** | Templates da Fase 2; ingestão de transcrições; `ConsensusGate`; duplicatas por similaridade | Fase 2 do INPI com consenso real de ≥ 2 participantes |
| **M6 Fases 3–4** | Map/reduce por requisito; coverage guard; conflitos e dependências; MoSCoW; histórias, critérios, matriz | DRE completo do INPI |

**Sem esperar as decisões da autora:** todas as etapas foram construídas com interpretações de
trabalho documentadas (cap. 02 e cap. 12). Quando a autora decidir diferente, o impacto fica
restrito ao manifesto e a alguns contratos dos agentes, porque a arquitetura não muda.

## 11.2 Estratégia de testes

| Nível | O que testar | Como |
|---|---|---|
| Unidade | Coverage guard; atribuição determinística de IDs; verificação de citação; RRF; política de consenso | pytest, sem LLM |
| Banco | Invalidação recursiva; ciclo de estados; unicidade de versão aprovada; idempotência do `hitl_request` | pytest + Postgres em container (testcontainers) |
| Fila | Concorrência (2 workers, 1 job); reaper de jobs órfãos; job único por `thread_id` | pytest com múltiplos processos |
| Grafo | Roteamento dos gateways; **retomada dupla** (resume reenviado não duplica efeitos); reinício do worker no meio de uma tarefa | LangGraph com **LLM falso** (cliente BAML apontando para servidor *stub* `openai-generic` que devolve fixtures) |
| Contrato | Prompts produzem os tipos; asserções de não invenção; snapshot de JSON Schema | `baml-cli test` + pytest |
| Conformidade | Todo elemento BPMN de referência está no manifesto e vice-versa; IDs existem nos `.bpmn` | pytest lendo `process/bpmn/*.bpmn` |
| Domínio | Prompts sem termos de domínio dos casos | *lint* em CI |
| Retrieval | Recall@k em conjunto de consultas anotadas; regressão ao trocar o chunker ou o embedding | script de avaliação versionado |
| Integração | `docker compose up` → executar Fase 1 com LLM falso → aprovar via API → export | pytest/httpx no CI |
| E2E | Fluxo do Engenheiro na UI (iniciar, acompanhar, revisar, revisitar, aprovar) | Playwright |
| Qualidade (pesquisa) | Métricas do cap. 09 | harness experimental (fora do CI) |

## 11.3 Riscos técnicos

| ID | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| R-01 | A teoria muda durante a implementação (templates, tarefas) | Alta | Médio | Manifesto versionado; execuções presas à versão; contratos com `schema_hash` |
| R-02 | Duas fontes de verdade (checkpoint × domínio) divergem | Média | Alto | Estado do grafo só com referências (cap. 04 §4.4); testes de reinício |
| R-03 | Efeitos duplicados na retomada de `interrupt()` | Média | Alto | Nó de gate sem efeitos; UPSERT idempotente; teste de retomada dupla |
| R-04 | Não determinismo do LLM invalida comparações | Alta | Alto | Repetições, temperatura fixa, sem fallback, registro completo |
| R-05 | Extração de PDF ruim (manuais extensos, páginas digitalizadas) | Média | Alto | Avaliar extração antes de M1; OCR se necessário; inspeção amostral dos chunks |
| R-06 | Provedor ou modelo descontinuado (já ocorreu duas vezes: `gemini-1.5-flash` e `gemini-2.5-flash`) | Alta | Médio | Catálogo administrável; teste de compatibilidade detecta a falha; registro da versão usada em cada execução |
| R-07 | Custo de LLM nas fases 3–4 (map por requisito, pares) | Média | Médio | Geração de candidatos por similaridade; perfis baratos para tarefas simples; orçamento por execução |
| R-08 | Dados pessoais em transcrições de elicitação (LGPD) | Média | Alto | Consentimento; pseudonimização na ingestão; política de retenção; provedores com termos adequados |
| R-09 | Export BPMN com referências quebradas (I-02) quebra o viewer | Média | Baixo | Testar no bpmn-js; pedir re-export à autora; fallback para SVG do Bizagi |
| R-10 | Engessamento: o manifesto vira um "motor BPMN caseiro" | Média | Médio | Escopo explícito: apenas padrões usados pelo OpenUPExp (sequência, subprocesso, gateway de aprovação, consenso) |
| R-11 | Juiz LLM com viés | Média | Alto | Família diferente, calibração humana, cegamento |
| R-12 | Embedding pesado no worker (memória) | Baixa | Baixo | Serviço de embedding separado, se necessário |
| R-13 | Repositório pesado (PDFs e `chroma_db` versionados — P-15) | Alta | Baixo | Mover o corpus para o volume ou Git LFS; não versionar índices |
| R-14 | Modelo local trava máquinas sem placa de vídeo | Alta | Médio | Modelo local **desligado por padrão**; teto de CPU e memória; opção de rodá-lo em um servidor (cap. 14) |
| R-15 | Chaves de API expostas | Média | Alto | Chaves só no `.env` do servidor (fora do Git); cadastro guarda apenas o nome da variável; lista de servidores permitidos |

## 11.4 Decisões arquiteturais registradas (ADR resumido)

| ADR | Decisão | Status |
|---|---|---|
| ADR-001 | BPMN como referência + manifesto versionado; sem motor BPMN genérico | Proposta |
| ADR-002 | React + Vite + TS + bpmn-js; sem React Native | Aceita (equipe) |
| ADR-003 | Worker separado; fila em PostgreSQL; sem Redis | Aceita (equipe) |
| ADR-004 | PostgreSQL + pgvector + FTS; sem Elasticsearch | Aceita (equipe) |
| ADR-005 | BAML como fonte única de contratos | Aceita (equipe) |
| ADR-006 | Estado LangGraph somente com referências | Proposta |
| ADR-007 | ContextBuilder com estratégias A/B/C/D e coverage guard | Proposta |
| ADR-008 | Evidência com verificação mecânica de citação | Proposta |
| ADR-009 | HITL em dois mecanismos (aprovação × consenso) | Aceita (equipe); regra de consenso pendente da autora |
| ADR-010 | Markdown como export versionado; JSON tipado como fonte de verdade | Aceita (equipe) |
| ADR-011 | Observabilidade via BAML Collector + tabelas próprias | Proposta |
| ADR-012 | Conformidade processual e qualidade avaliadas separadamente | Proposta |
| ADR-013 | Catálogo de modelos administrável, com snapshot por execução | Aceita (equipe) |
| ADR-014 | Modelo local como referência opcional, desligado por padrão | Aceita (equipe) |
| ADR-015 | Laboratório reexecuta tarefas com o pacote de contexto guardado | Aceita (equipe) |
