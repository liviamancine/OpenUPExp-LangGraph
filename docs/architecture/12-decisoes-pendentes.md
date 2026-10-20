# 12 — Decisões pendentes

## 12.1 Para a autora da teoria [PENDENTE-AUTORA]

Ordenadas por impacto no início da implementação. "Bloqueia" indica o primeiro marco do
roadmap (cap. 11) que depende da decisão.

| ID | Questão | Contexto | Interpretação de trabalho proposta | Bloqueia |
|---|---|---|---|---|
| A-01 | Como modelar o retorno *No* dos gateways? A escolha entre X.1 e X.2 é a única granularidade, ou o Engenheiro pode escolher tarefas específicas? | I-01: só o fluxo *Yes* existe; o retorno está em anotação | Duas saídas (`revisit_X_1`, `revisit_X_2`); granularidade fina desligada | M2 |
| A-02 | Qual é a ordem das tarefas de 1.1 e 1.2? | I-02: fluxos do XML com IDs inexistentes | Ordem pela numeração | M2 |
| A-03 | Qual tarefa BPMN produz a **Declaração de Posicionamento** (§2.2)? | Sem tarefa BPMN; o passo 1 de `definir-visao.md` a registra | Nó próprio, depois de 1.2.1 e ligado a 1.2.4 | M2 |
| A-04 | Qual a diferença entre **1.1.3 Stakeholder Needs** e **1.2.1 Explainability Needs**? | I-06 | 1.1.3 = solicitações brutas com origem; 1.2.1 = necessidades conceituais | M2 |
| A-05 | Qual o alinhamento entre os 7 passos de `definir-visao.md` e as 9 tarefas BPMN da Visão? | I-03 | Tabela do cap. 02 §2.2 | M2 |
| A-06 | Em que fase se atribui o **aspecto associado** (§4.1 do template × passo 2 da Análise)? | I-10, P-13 | Campo opcional na Visão; obrigatório na Análise | M2 |
| A-07 | Quem prioriza os requisitos complementares (§5.6) na Visão? | O W6 não prioriza por regra | O Engenheiro, na revisão 1.3 | M2 |
| A-08 | A IA pode participar da **revisão** (1.3.1), ou apenas pré-calcular verificações? | Passo 7: "Obter consenso (revisão da Visão)" | Apenas checklist objetivo; decisão humana | M2 |
| A-09 | A Fase 1 tem consenso (passos 2 e 7) mesmo sem tarefa "Reach Consensus" no BPMN? | §7.4 | Opcional por projeto; desligado por padrão | M3 |
| A-10 | Template do **Glossário** (`glossario.md` vazio) | — | Termo, definição, sinônimos, origem | M2 |
| A-11 | **Nome canônico** do documento (DRE × ERD; "Documento de Requisitos de Explicabilidade" × "Documento de Referência de Especificação") | I-04 | DRE em português, ERD como alias | M2 |
| A-12 | **Composição do ERD** em cada fase | I-05 | Visão + Glossário (F1) + Requisitos (F2) + Análise (F3) + Especificação (F4) | M5 |
| A-13 | Quem participa de cada **Reach Consensus** e qual a regra de fechamento? | I-08; BPMN com lane única | `no_blocking_objection`; no timeout, o Engenheiro decide | M5 |
| A-14 | Templates das fases 2–4: Plano de Elicitação, RER, História de Usuário, Critério de Aceitação, Características da Explicação, Matriz de Rastreabilidade | I-09 | — | M5/M6 |
| A-15 | Taxonomias de aspectos e de tipos de explicação são **fechadas** ou extensíveis? | `analisar-requisito.md` passos 2–3 | Fechadas com "outro (justificar)" | M6 |
| A-16 | Quem decide o **MoSCoW**? | 3.2.6 | IA sugere, humanos decidem no consenso | M6 |
| A-17 | É permitido **reabrir** uma macroatividade aprovada? | `Fase Concepção.md`: "DRE continuamente atualizado" | Sim, com justificativa e invalidação em cascata | M5 |
| A-18 | Relação entre **1.2.2** e **2.2.3** (mesmo nome: Identify Complementary Requirements) | — | 2.2.3 refina 1.2.2 com os requisitos elicitados | M5 |
| A-19 | A **Lista de Itens de Trabalho** está no escopo da plataforma? | Citada em várias tarefas, marcada "VALIDAR" | Fora do MVP | — |
| A-20 | Corrigir os nomes no BPMN ("Draf", "3.1.2Consolidate", "Reach Consensus" sem número…) e o vocabulário "Workers" no template (I-11)? | I-07, I-11 | O manifesto usa IDs BPMN, então não bloqueia | — |

## 12.2 Para a equipe [PENDENTE-EQUIPE]

| ID | Questão | Opções | Recomendação | Até |
|---|---|---|---|---|
| E-01 | Modelo de embedding | `bge-m3` · `multilingual-e5-base` · outro | Avaliar recall@10 com consultas anotadas em M1 | M1 |
| E-02 | Extração de PDF dos manuais do INPI | `pypdf` · `pymupdf` · OCR | Inspecionar amostras antes de fixar | M1 |
| E-03 | Biblioteca de fila | Implementação própria · `procrastinate` | `procrastinate`, se cobrir LISTEN/NOTIFY e o reaper | M0 |
| E-04 | Provedores e perfis de LLM | Groq · OpenAI · Anthropic · Google · local | Ao menos 2 famílias diferentes, para fallback e juiz | M2 |
| E-05 | Autenticação | JWT local · OIDC (Keycloak) | JWT local no MVP | M3 |
| E-06 | Biblioteca de componentes UI | Mantine · shadcn/ui · MUI | — | M3 |
| E-07 | BPMN: cópia fixada ou submódulo do repositório teórico | cópia · submódulo | Submódulo (mantém o vínculo de commit) | M0 |
| E-08 | Corpus no Git | manter · Git LFS · volume externo | Volume + script de *download*; índice fora do Git | M0 |
| E-09 | Domínios adicionais do experimento | crédito, saúde, … | ≥ 2 domínios com regulação distinta da do INPI | M4 |
| E-10 | Observabilidade externa | nenhuma · Phoenix (OTel) · Langfuse | Nenhuma no início; Phoenix se necessário | M4 |
| E-11 | Ferramenta de export para PDF/DOCX | pandoc · outra | pandoc com template próprio | M2 |

## 12.3 Como registrar as decisões

Cada decisão da autora vira:

1. uma atualização no repositório **OpenUPExp**: BPMN, tarefa ou template;
2. um incremento de versão do **manifesto**, referenciando o commit da teoria;
3. a atualização da linha correspondente nesta tabela, com data e referência.

As decisões da equipe viram ADRs (cap. 11 §11.4).
