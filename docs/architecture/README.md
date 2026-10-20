# Arquitetura da Plataforma OpenUPExp — Documento de Referência

> **Status:** rascunho para discussão (v0.1) · **Branch:** `docs/arquitetura-plataforma`
> **Escopo:** documentação apenas — nenhum código, agente ou template foi alterado.
> **Referência teórica:** repositório `OpenUPExp` (BPMN, tarefas, papéis, templates).
> **Projeto executável:** este repositório (`OpenUPExp-LangGraph`).

Este conjunto de documentos é a referência técnica e científica para transformar o
protótipo atual (seis workers LangGraph/BAML executados em linha de comando) numa
plataforma web de Engenharia de Requisitos de Explicabilidade orientada ao processo
OpenUPExp, com agentes de IA, validação humana, rastreabilidade e gestão de contexto.

---

## Legenda obrigatória

Todo conteúdo deste documento é marcado com uma das etiquetas abaixo. **Decisões
arquiteturais nunca devem ser lidas como definições originais do modelo OpenUPExp.**

| Etiqueta | Significado | Fonte |
|---|---|---|
| **[TEORIA]** | Definido pelo modelo OpenUPExp | `OpenUPExp/web/bpmn/*.bpmn`, `tarefas/`, `artefatos/`, `papeis/`, `ciclo de vida/` |
| **[IMPLEMENTADO]** | Existe hoje no código executável | `main.py`, `baml_src/`, `rag_retriever.py`, `indexar_documentos.py` |
| **[PROPOSTA]** | Decisão de arquitetura/engenharia proposta neste documento | — |
| **[PENDENTE-AUTORA]** | Depende de definição da autora da teoria | lista consolidada no cap. 12 |
| **[PENDENTE-EQUIPE]** | Decisão técnica ainda em aberto na equipe | lista consolidada no cap. 12 |

---

## Índice

| # | Documento | Público principal |
|---|---|---|
| 01 | [Teoria e estado atual](01-teoria-e-estado-atual.md) | autora, orientador, equipe |
| 02 | [Mapeamento completo da Fase 1 — Visão](02-mapeamento-fase-1-visao.md) | autora, equipe |
| 03 | [Arquitetura preliminar das Fases 2–4](03-fases-2-4-preliminar.md) | autora, equipe |
| 04 | [Arquitetura de software](04-arquitetura-de-software.md) | equipe |
| 05 | [ContextBuilder, recuperação e evidências](05-contexto-e-evidencias.md) | equipe, orientador |
| 06 | [Modelo de dados](06-modelo-de-dados.md) | equipe |
| 07 | [Human-in-the-loop: aprovação e consenso](07-human-in-the-loop.md) | autora, equipe |
| 08 | [Contratos BAML](08-contratos-baml.md) | equipe |
| 09 | [Observabilidade e metodologia experimental](09-observabilidade-e-metodologia.md) | orientador, equipe |
| 10 | [Interface web](10-interface-web.md) | autora, equipe |
| 11 | [Roadmap, testes e riscos](11-roadmap-testes-riscos.md) | equipe, orientador |
| 12 | [Decisões pendentes](12-decisoes-pendentes.md) | todos |
| 13 | [Notas de implementação (M0–M3, Fases 2 a 4)](13-notas-de-implementacao.md) | equipe |
| 14 | [Modelos de linguagem, modelo local e laboratório](14-modelos-e-laboratorio.md) | equipe, orientador |

Para gerar uma versão PDF única para discussão (sem criar documentos divergentes):

```bash
pandoc docs/architecture/README.md docs/architecture/[0-9]*.md \
  -o openupexp-arquitetura.pdf --toc -F mermaid-filter
```

---

## Princípios de arquitetura [PROPOSTA]

1. **O BPMN é referência, não motor de execução.** Os modelos BPMN do OpenUPExp
   definem o processo; o LangGraph executa a orquestração dos agentes. A ponte entre
   os dois é um **manifesto de processo versionado**, curado manualmente e validado
   automaticamente contra os arquivos `.bpmn`. Não se promete executar BPMN arbitrário.
2. **Dados estruturados são a fonte de verdade; Markdown é artefato documental gerado.**
   Cada artefato é JSON tipado (contrato BAML), com IDs estáveis e versões. O Markdown
   é gerado a partir dos templates, versionado e preservado como documento oficial.
3. **BAML é a fonte única dos contratos dos agentes.** Os tipos Pydantic usados pela
   API e pelo frontend (via JSON Schema) são gerados do BAML, nunca escritos à mão.
4. **Contexto é montado, não acumulado.** Um `ContextBuilder` com estratégias
   intercambiáveis entrega a cada agente apenas o necessário, com verificação
   determinística de completude quando a tarefa exige ver todos os itens.
5. **Toda afirmação normativa tem evidência verificável.** Requisitos derivados da base
   de referência apontam para trechos (chunks) específicos, e a citação é conferida
   mecanicamente contra o texto da fonte.
6. **Decisões humanas são imutáveis e auditáveis.** Aprovações, rejeições, retornos e
   consensos ficam registrados; versões anteriores nunca são apagadas.
7. **Conformidade processual ≠ qualidade dos artefatos.** São medidas separadamente:
   um agente pode cumprir todas as etapas do BPMN e ainda produzir requisitos ruins.
8. **Independência de domínio.** O caso INPI (registro de marcas) é o estudo de caso
   inicial; domínio vive nos dados do projeto (escopo, corpus), nunca nos prompts.
9. **Reprodutibilidade por construção.** Toda execução fixa versões de manifesto,
   prompts (commit do `baml_src`), modelos, embeddings, corpus e estratégia de contexto.
10. **Simplicidade operacional.** PostgreSQL concentra dados, checkpoints, fila, busca
    híbrida e notificações. Nenhum componente extra (Redis, Elasticsearch, MinIO) entra
    sem necessidade demonstrada.

---

## Resumo das decisões arquiteturais [PROPOSTA]

| Tema | Decisão | Alternativa descartada (por ora) | Capítulo |
|---|---|---|---|
| Frontend | React + Vite + TypeScript + bpmn-js, desktop responsivo | React Native (bpmn-js depende do DOM) | 10 |
| API | FastAPI (REST + SSE) | — | 04 |
| Execução dos agentes | Worker service separado, mesma imagem, outro *entrypoint* | Workers dentro do processo da API | 04 |
| Fila | Tabela `job` no PostgreSQL com `FOR UPDATE SKIP LOCKED` + `LISTEN/NOTIFY` | Redis + Celery/ARQ | 04 |
| Persistência | PostgreSQL 16 + pgvector | Elasticsearch, Chroma | 06 |
| Checkpoints | `langgraph-checkpoint-postgres`; estado do grafo guarda só **referências** | Estado com conteúdo (blackboard atual) | 04, 06 |
| Busca | Híbrida: `tsvector` (português) + pgvector, fusão RRF | Somente vetorial | 05 |
| Chunking | Estrutural (artigo de lei, seção de manual) | Janela fixa de 1000 caracteres | 05 |
| Contexto | `ContextBuilder` com estratégias A/B/C/D e *coverage guard* | Markdown integral para todos os agentes | 05 |
| Contratos | BAML como fonte única; Pydantic e JSON Schema gerados | Pydantic manual | 08 |
| HITL | Dois mecanismos: aprovação individual (gateway) e consenso assíncrono | Um único tipo de interrupção | 07 |
| Versionamento | `draft → in_review → approved → superseded`, além de `stale` por invalidação | Sobrescrever `blackboard.json` | 06 |
| Observabilidade | BAML `Collector` + tabela `llm_call`; Phoenix/OTel opcional | Langfuse v3 (infraestrutura pesada) | 09 |
| Arquivos | Volume Docker | MinIO (quando houver necessidade) | 04 |
