# 10 — Interface web [PROPOSTA]

## 10.1 Stack

| Camada | Escolha | Motivo |
|---|---|---|
| Build | Vite + React 18 + TypeScript | Padrão estável; SPA para desktop responsivo |
| Roteamento / dados | React Router + TanStack Query | Cache de servidor, *refetch* por evento SSE |
| BPMN | `bpmn-js` (NavigatedViewer) | Renderiza os `.bpmn` originais da teoria, com overlays e marcadores |
| Formulários de artefato | `@rjsf/core` a partir do JSON Schema gerado do BAML | Nenhum formulário escrito à mão por artefato |
| Markdown | `react-markdown` + `remark-gfm` | Pré-visualização do Documento de Visão/DRE |
| Diff | `jsondiffpatch` (estrutura) + diff de texto por item | Comparação de versões |
| UI | Biblioteca de componentes acessível (ex.: Mantine ou shadcn/ui) [PENDENTE-EQUIPE] | — |

**Licença do bpmn-js:** a licença exige manter visível a marca d'água do bpmn.io no
diagrama.

**Portal Bizagi:** `web/bizagi-publish` continua como documentação estática da teoria e
pode ser linkado. A plataforma usa os `.bpmn`, porque o export do Bizagi não contém os
elementos das páginas folha (I-12).

## 10.2 Mapa de navegação

```mermaid
flowchart TD
  LOGIN[Login] --> PROJS[Projetos]
  PROJS --> PH[Projeto · visão geral]
  PH --> SRC[Fontes e corpus]
  PH --> RUNS[Execuções]
  PH --> PROC[Processo OpenUPExp<br/>navegador BPMN]
  PROC --> RUN[Execução · linha do tempo]
  RUN --> TASK[Detalhe da tarefa<br/>contexto · saída · evidências · chamadas LLM]
  PH --> INBOX[Central de decisões]
  INBOX --> APPROVE[Revisão e aprovação]
  INBOX --> CONS[Consenso]
  PH --> ARTS[Artefatos]
  ARTS --> ART[Editor de artefato · versões · diff]
  ARTS --> DOC[Documento DRE · export]
  ARTS --> TRACE[Matriz de rastreabilidade]
  PH --> OBS[Observabilidade]
  OBS --> EXP[Experimentos]
```

## 10.3 Telas principais

> Os wireframes usam dados **ilustrativos**: IDs, páginas, contagens e textos não são
> resultados reais de execução.

### A. Navegador do processo (BPMN + status da execução)

```
┌ Projeto: INPI Marcas ▸ Execução #7 (estratégia D · modelo X) ───────────── ● ao vivo ┐
│ [OpenUPExp] ▸ [1 Define Vision] ▸ [1.2 Develop]                     legenda: ✓ ● ⏸ ⚠ ↺ │
│ ┌──────────────────────────────────────────────────────────────┬────────────────────┐ │
│ │  (start)→[1.2.1 Needs ✓]→[1.2.2 Complementary ●]→            │ 1.2.2 Identify     │ │
│ │          [1.2.3 Limits ⏸]→[1.2.4 Elaborate ⏸]→(end)         │ Complementary Reqs │ │
│ │                    ║                                         │ Status: executando │ │
│ │             [(Reference Base)]                               │ Agente: Develop…   │ │
│ │                                                              │ Entradas: NEED×4   │ │
│ │  bpmn.io                                                     │ Trechos: 12 (híb.) │ │
│ │                                                              │ Tokens: 6.1k · 14s │ │
│ └──────────────────────────────────────────────────────────────┴────────────────────┘ │
│ Linha do tempo: 1.1.1 ✓ 1.1.2 ✓ 1.1.3 ✓ 1.1.4 ✓ 1.1.5 ✓ │ 1.2.1 ✓ 1.2.2 ● … │ iteração 2  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Overlays** sobre os elementos BPMN, com status derivado de `task_execution`:
  concluído ✓, executando ●, aguardando ⏸, aguardando humano ✋, erro ⚠, *stale* ↺.
- **Clique em *call activity*:** abre o `.bpmn` do subprocesso (*drill-down*), com
  *breadcrumb*.
- **Clique em tarefa:** abre o painel lateral com o *manifesto* da tarefa (entradas,
  saídas, mecanismo) e a última execução.
- **Gateways:** mostram as decisões já tomadas em cada iteração (✓ aprovado / ↺ retorno
  para 1.2).

### B. Central de decisões (inbox)

```
┌ Decisões pendentes ─────────────────────────────────────────────────────────────┐
│ ✋ Aprovação  · 1.3 Explainability Vision approved? · Execução #7 · há 2 h        │
│ 🗳 Consenso   · 2.2.5 Reach Consensus · 3/5 votos · prazo 05/11 · 2 divergências │
│ ✋ Aprovação  · 1.3 … · Projeto Crédito · iteração 3 (alerta: muitas iterações)   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### C. Revisão e aprovação (gateway)

```
┌ 1.3 Review Explainability Vision · rascunho v3 ─────────────────────────────────────┐
│ Seções                │ §3.1 Resumo dos Stakeholders                    [editar] 💬 │
│ ✓ §1 Definição        │ STK-01 Examinador        descrição… responsabilidade…       │
│ ⚠ §2.1 Problema (1 lac)│ STK-02 Solicitante      descrição… ⚠ lacuna: responsab.   │
│ ✓ §2.2 Posicionamento │ STK-03 Regulador ...                                        │
│ ✓ §3.1 Stakeholders   │─────────────────────────────────────────────────────────────│
│ ⚠ §5 Complementares   │ Checklist automático (PreReviewChecklist)                   │
│   (1 sem evidência)   │ ✓ todo STK tem POS   ✓ todo NEED → STK   ⚠ CR-04 sem evid.  │
│ ✓ Limites             │ Lacunas: 3 (ver)                                            │
│ ✓ Glossário (14)      │─────────────────────────────────────────────────────────────│
│                       │ Decisão:  (•) Aprovar  ( ) Revisitar 1.1  ( ) Revisitar 1.2 │
│ [diff vs v2] [prévia] │ Comentário: ________________________________ (obrig. se ↺) │
│                       │                                             [Registrar]     │
└───────────────────────┴─────────────────────────────────────────────────────────────┘
```

- Os comentários 💬 são por seção ou item e alimentam o `review_feedback` (cap. 07).
- Uma edição inline gera uma versão `human_edit`. O diff mostra quem mudou o quê (IA ×
  humano).
- A aprovação fica bloqueada se houver versões `stale`.

### D. Consenso

```
┌ 2.2.5 Reach Consensus · rodada 1 · regra: sem objeção bloqueante · prazo 05/11 ─────┐
│ Participantes: Eng. Req (coord.) · Esp. Regulação ✓ · Esp. Domínio ✓ · Analista … ⏳ │
│ ┌──────────┬─────────────────────────────────────┬──────────┬───────────────────────┐ │
│ │ Item     │ Texto                               │ Votos    │ Seu voto              │ │
│ │ REQ-007  │ O sistema deve apresentar ao…       │ ✓✓✗      │ (✓) (✓*) (✗) 💬       │ │
│ │ REQ-008  │ …                                   │ ✓✓✓      │                       │ │
│ └──────────┴─────────────────────────────────────┴──────────┴───────────────────────┘ │
│ Divergências (IA · sugestão, requer aceite): REQ-007 — 2 comentários sobre "tempo…"   │
│ [Fechar consenso]  [Nova rodada]                                   (só Eng. Req.)     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### E. Evidências

```
┌ CR-02 · Normas e Regulamentos ────────────────────────────────────────────────────┐
│ "O sistema deve permitir ao titular solicitar revisão de decisões automatizadas…" │
│ Necessidades: NEED-01, NEED-03                                                    │
│ Evidência 1 · OBRIGAÇÃO NORMATIVA · ✓ citação verificada                          │
│   lei_13709_lgpd · art. 20 · p. 12                                                │
│   "…o titular dos dados tem direito a solicitar a revisão de decisões tomadas…"   │
│   [ver trecho completo]  [Aceitar] [Rejeitar] [Reclassificar]                     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

O trecho completo aparece com a citação destacada. Uma citação não verificada aparece
com uma faixa de alerta.

### F. Detalhe da tarefa (transparência do agente)

As abas são:

- **Contexto:** o `ContextPackage`, com cada item, sua origem (*required*, *digest*,
  *retrieved*, *related*, *feedback*) e o motivo de ter entrado. Inclui o relatório de
  cobertura.
- **Saída:** JSON e a renderização no template.
- **Chamadas LLM:** modelo, tokens, latência, custo, cadeia de fallback.
- **Histórico:** iterações anteriores desta tarefa.

### G. Observabilidade e experimentos

- Por execução: tokens e custo por tarefa (barras), latência, nº de iterações por
  subprocesso, nº de lacunas.
- Por experimento: matriz estratégia × caso × modelo com as métricas do cap. 09 e a
  variância entre repetições.
- **Exportação** de CSV/Parquet para análise externa (`experiments/analysis/`).

## 10.4 Componentes principais

| Componente | Responsabilidade |
|---|---|
| `<BpmnNavigator>` | Carrega o `.bpmn`, aplica overlays de status, faz drill-down e breadcrumb |
| `<RunTimeline>` | Execuções de tarefa por iteração, em tempo real via SSE |
| `<HitlInbox>` | Lista de `hitl_request` do usuário |
| `<ApprovalPanel>` | Decisão do gateway, com validações e comentário obrigatório |
| `<ConsensusBoard>` | Votos por item, política, rodadas, fechamento |
| `<ArtifactEditor>` | Formulário gerado do JSON Schema e destaque de lacunas |
| `<VersionDiff>` | Diff estrutural por item entre versões, com autoria |
| `<DocumentPreview>` | Markdown do template renderizado e export |
| `<EvidenceCard>` | Evidência com tipo, verificação e trecho original |
| `<ContextInspector>` | `ContextPackage` com origens, cobertura e tokens |
| `<TraceMatrix>` | Matriz de rastreabilidade a partir de `trace_link` (Fase 4) |
| `<MetricsDashboard>` | Gráficos de custo, latência, qualidade |
