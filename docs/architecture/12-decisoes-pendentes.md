# 12 — Decisões pendentes

> **Em poucas palavras.** Aqui estão as perguntas que só a autora da teoria pode responder.
> Nenhuma delas está travando a plataforma: para cada uma, adotamos uma **interpretação
> provisória**, que já está em uso e pode ser trocada. O objetivo deste capítulo é tornar
> essas escolhas visíveis, para que sejam confirmadas ou corrigidas.

## Como ler e responder

- **Cada linha é uma pergunta.** A coluna "Interpretação adotada" mostra o que a plataforma
  faz hoje. Muitas vezes basta responder "confirmo" ou indicar a alternativa preferida.
- **As seções 12.4 a 12.6** detalham, etapa por etapa, os formatos provisórios dos artefatos
  das Fases 2 a 4 e o trecho da teoria em que cada um se apoia.
- **Para ver na prática**, dá para percorrer as etapas na plataforma em **modo de teste**
  (respostas simuladas, sem IA e sem custo) e olhar os documentos gerados.
- Uma resposta pode ser bem curta, por exemplo: *"A-16: confirmo — a IA só sugere a
  prioridade."* ou *"A-13: o consenso deve exigir maioria, e não ausência de objeção."*

### As perguntas mais importantes

Se houver tempo para poucas, estas são as que mais mudam o resultado:

1. **A-14 — Templates das Fases 2 a 4** (plano de elicitação, requisito refinado, história de
   usuário, critério de aceitação, características da explicação, matriz de rastreabilidade).
   Hoje usamos formatos derivados dos passos das tarefas (§12.4 a §12.6).
2. **A-13 — Quem participa do consenso e quando ele se encerra.** Hoje: membros do projeto
   registram posição; encerra-se sem objeção (ou com justificativa registrada).
3. **A-12 / A-11 — Composição e nome do documento final.** Hoje: o DRE soma Visão, Elicitação,
   Análise e Especificação, uma parte por etapa.
4. **A-16 — Quem decide a prioridade (MoSCoW).** Hoje: a IA sugere; as pessoas decidem.
5. **A-21 — Requisitos "WONT" e histórias de usuário.** Hoje: WONT fica fora da especificação;
   pode haver mais de uma história por requisito.
6. **A-01 — Retorno nos pontos de aprovação.** Hoje: refazer X.1 ou X.2, com comentário.

## 12.1 Para a autora da teoria [PENDENTE-AUTORA]

A última coluna indica o marco do roteiro (cap. 11) em que a pergunta surgiu. Todas já têm
interpretação provisória em uso.

| ID | Questão | Contexto | Interpretação adotada | Marco |
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
| A-21 | Requisitos com prioridade **WONT** entram na Especificação? E uma HU por requisito ou uma por stakeholder? | `especificar-requisitos.md` passo 1 ("uma necessidade principal por história") | WONT fica fora da versão, registrado no DRE; uma ou mais HU por requisito, cada uma com um stakeholder | M6 |

## 12.2 Para a equipe [PENDENTE-EQUIPE]

Decisões técnicas, sem impacto na teoria. Várias já foram tomadas durante a implementação
(indicadas na última coluna).

| ID | Questão | Opções | Recomendação | Até |
|---|---|---|---|---|
| E-01 | Modelo de embedding | `bge-m3` · `multilingual-e5-base` · outro | Avaliar recall@10 com consultas anotadas em M1 | Em uso: `multilingual-e5-base` |
| E-02 | Extração de PDF dos manuais do INPI | `pypdf` · `pymupdf` · OCR | Inspecionar amostras antes de fixar | M1 |
| E-03 | Biblioteca de fila | Implementação própria · `procrastinate` | `procrastinate`, se cobrir LISTEN/NOTIFY e o reaper | M0 |
| E-04 | Provedores e perfis de LLM | Groq · OpenAI · Anthropic · Google · local | Ao menos 2 famílias diferentes, para fallback e juiz | **Resolvida**: catálogo administrável + modelo local opcional (cap. 14) |
| E-05 | Autenticação | JWT local · OIDC (Keycloak) | JWT local no MVP | M3 |
| E-06 | Biblioteca de componentes UI | Mantine · shadcn/ui · MUI | — | **Resolvida**: componentes e ícones próprios, sem biblioteca externa (cap. 10) |
| E-07 | BPMN: cópia fixada ou submódulo do repositório teórico | cópia · submódulo | Submódulo (mantém o vínculo de commit) | Em uso: cópia fixada com o commit de origem registrado |
| E-08 | Corpus no Git | manter · Git LFS · volume externo | Volume + script de *download*; índice fora do Git | M0 |
| E-09 | Domínios adicionais do experimento | crédito, saúde, … | ≥ 2 domínios com regulação distinta da do INPI | **Em aberto** — necessário para generalizar os resultados |
| E-10 | Observabilidade externa | nenhuma · Phoenix (OTel) · Langfuse | Nenhuma no início; Phoenix se necessário | M4 |
| E-11 | Ferramenta de export para PDF/DOCX | pandoc · outra | pandoc com template próprio | M2 |

## 12.3 Como registrar as decisões

Cada decisão da autora vira:

1. uma atualização no repositório **OpenUPExp**: BPMN, tarefa ou template;
2. um incremento de versão do **manifesto**, referenciando o commit da teoria;
3. a atualização da linha correspondente nesta tabela, com data e referência.

As decisões da equipe viram ADRs (cap. 11 §11.4).

## 12.4 Interpretações provisórias adotadas na Fase 2 [PROPOSTA]

> **Em poucas palavras.** A tarefa de elicitação (`encontrar-descrever-requisitos.md`) descreve
> bem *o que* fazer, mas não traz modelos dos documentos. Criamos formatos simples a partir dos
> passos da tarefa, para que a etapa pudesse ser testada.

A Fase 2 foi implementada no manifesto 0.2.0 **antes** das definições da autora, para
permitir testar o processo e a gestão de contexto. Cada linha abaixo é uma escolha de
engenharia, **não** uma definição do OpenUPExp, e deve ser substituída quando a decisão
correspondente for tomada. Onde vive no código: `backend/baml_src/requirements_2_*.baml`,
`backend/openupexp/agents/phase2.py`, `process/manifest/openupexp-0.2.0.yaml`.

| Pendência | Interpretação provisória | Base na teoria |
|---|---|---|
| A-14 — Plano de Elicitação (2.1.2) | Um item por stakeholder: objetivo, técnicas, roteiro de perguntas, necessidades da Visão a aprofundar e lacunas da Visão visadas (`EP-n`) | Passo 1 de `encontrar-descrever-requisitos.md`; anotação BPMN "Explainability Elicitation Strategy" |
| A-14 — Técnicas de elicitação | Lista fechada `ENTREVISTA`, `WORKSHOP`, `OBSERVACAO`, `ANALISE_DOCUMENTAL`, `PROTOTIPO`, `OUTRA` | Passo 1 ("entrevistas, workshops, observação, análise documental, protótipos ou outras") |
| Fontes de elicitação (2.2.1) | O Engenheiro envia o material (transcrições, atas) como fonte `elicitacao`; a execução pausa em 2.2.1 até o envio. Sem material, pode prosseguir **com justificativa**, e as necessidades vêm só das solicitações da Visão | Passo 1 ("a elicitação pode ser realizada por meio de…") — quem conduz é humano |
| A-14 — Necessidade elicitada | `RN-n`: stakeholder, necessidade, decisão a explicar, objetivo, NEED-n relacionadas e **citação literal verificada** do material | Passos 3 e 4 |
| A-14 / A-15 — Objetivo da explicação | Lista `COMPREENSAO`, `JUSTIFICATIVA`, `TRANSPARENCIA`, `RASTREABILIDADE`, `AUDITORIA`, `CONFORMIDADE_REGULATORIA`, `CONFIANCA`, `OUTRO` | Passo 3 (lista de objetivos citada no texto) |
| A-14 — Requisito de explicabilidade | `RI-n` com enunciado "O sistema deve…" (o quê, para quem, em que situação; **não** o como), stakeholders, NEED-n e RN-n de origem | Objetivo da tarefa: nível estratégico; detalhes ficam para fases posteriores |
| A-18 — 2.2.3 × 1.2.2 | 2.2.3 **refina** os CR-n da Visão à luz dos RI-n (`RC-n`, com `cr_ids`), consultando a base de referência pelos requisitos elicitados | Mesmo nome de tarefa; passo 5 |
| Consolidação (2.2.4) | `REQ-n` com origem em RI/RC; fusão só de itens equivalentes, sugeridos por similaridade semântica (limiar 0,9); descartes com motivo; nenhum RI/RC pode sumir (verificação determinística) | "Organize and Consolidate Requirements" |
| A-13 — Reach Consensus (2.2.5) | Participantes = membros com papel `participant` ou `requirements_engineer`. Cada um registra **concordo**, **ressalvas** ou **objeção** (as duas últimas com comentário). O Engenheiro encerra; com objeção (ou sem nenhuma posição), encerrar exige justificativa, registrada no ERD. Ou pede retorno a 2.2, e as posições viram feedback para os agentes | Passo 6 ("Engenheiro de Requisitos, Stakeholders, Equipe do Projeto") |
| A-01 — Retorno do gateway 2.3 | Revisitar 2.1 ou 2.2, com comentário obrigatório | Anotação BPMN: "decides whether to revisit subprocess 2.1 or 2.2" |
| A-12 — Composição do ERD | ERD da Fase 2 = Parte 1 (Visão aprovada, com Glossário) + Parte 2 (plano, material, necessidades, requisitos, complementares, rastreabilidade NEED→REQ, consenso, lacunas) | Anotação BPMN em 2.3.2: "Create Explainability Requirement Document (ERD)" |
| Glossário na Fase 2 | **Não implementado**: o passo 2 (capturar termos) não tem tarefa BPMN própria na Fase 2; o glossário da Visão é usado como entrada | Passo 2; saídas da tarefa citam o Glossário |
| A-19 — Lista de Itens de Trabalho | Fora do escopo (passo 7) | Marcada "VAMOS TER???" |

## 12.5 Interpretações provisórias adotadas na Fase 3 [PROPOSTA]

> **Em poucas palavras.** A Análise é a etapa mais detalhada da teoria: as listas de aspectos,
> tipos de explicação, critérios de viabilidade e o MoSCoW vêm do texto. Interpretamos
> principalmente o formato do requisito refinado (RER), marcado "???Validar" na teoria.

Manifesto 0.3.0. A Fase 3 é a mais definida na teoria (`tarefas/analisar-requisito.md`): as
taxonomias, a matriz de viabilidade e o MoSCoW vêm do texto. O que segue é escolha de engenharia.
Código: `backend/baml_src/analysis_3_analyze.baml`, `backend/openupexp/agents/phase3.py`.

| Pendência | Interpretação provisória | Base na teoria |
|---|---|---|
| A-14 — Formato do RER | `RER-n` por requisito, com os campos das "perguntas úteis" do passo 1: contexto de uso, quem usa a explicação, decisão apoiada, risco (ALTO/MÉDIO/BAIXO), objetivo principal, obrigação regulatória, requisitos regulatórios associados | Passo 1; RER marcado "artefato intermediário???Validar" |
| Escopo da análise | Só os requisitos `EXPLICABILIDADE` passam por 3.1.2–3.2.6. Os `COMPLEMENTAR` (normas, desempenho…) entram como restrições e participam da análise de conflitos | "Analisar cada requisito de explicabilidade" (passo 1) |
| A-15 — Aspectos (3.2.1) | Lista do passo 2 (Compreensão, Justificativa, Confiança, Auditoria, Contestação, Aprendizado) + `OUTRO` justificado; classificação múltipla com aspecto predominante | Passo 2 e boas práticas |
| A-15 — Tipos de explicação (3.2.2) | Lista do passo 3 (Feature Importance, Local, Global, Example-based, Rule-based, Counterfactual) + `OUTRO`; sem escolher ferramenta; trechos acadêmicos da base de referência como evidência | Passo 3 ("não é selecionar uma ferramenta") |
| Conflitos (3.2.3) | Todos os pares se houver até 40 requisitos; acima disso, pares com stakeholder em comum ou similaridade ≥ 0,8. Tipos a partir dos exemplos do passo 4. A cobertura de pares fica registrada | Passo 4 |
| Dependências (3.2.4) | `depende_de` entre REQ-n e restrições tipadas; restrição regulatória exige evidência verificada na base de referência | Passo 5 (exemplo "depende de rastreabilidade — impactado pela LGPD") |
| Viabilidade (3.2.5) | Os quatro critérios da matriz do passo 6 sempre presentes (`NAO_AVALIADO` + lacuna quando o agente omite) | Passo 6 |
| A-16 — MoSCoW (3.2.6) | **A IA só sugere**; a prioridade é confirmada no consenso e na aprovação, e o Engenheiro pode editá-la. Alerta automático quando um requisito do qual outro depende tem prioridade menor | Passos 7 e 8 |
| A-13 / A-20 — Reach Consensus sem número | Tratado como 3.2.7, com a mesma regra provisória da Fase 2; retorno apenas a 3.2 | Passo 8; BPMN sem numeração |
| A-01 — Retorno do gateway 3.3 | Revisitar 3.1 ou 3.2, com comentário obrigatório | Anotação BPMN em 3.3 |
| A-12 — ERD | ERD da Fase 3 = ERD aprovado da Fase 2 (Visão + Requisitos) + Parte 3 (RER, conflitos, MoSCoW, consenso, lacunas) | "Consolidate Explainability Requirement Document" |

## 12.6 Interpretações provisórias adotadas na Fase 4 [PROPOSTA]

> **Em poucas palavras.** A tarefa de especificação traz os formatos recomendados (histórias
> "Como / Quero / Para" e critérios "Dado / Quando / Então") e a lista de características da
> explicação. Faltam os templates; os detalhes abaixo são escolhas nossas.

Manifesto 0.4.0. `tarefas/especificar-requisitos.md` define os passos, os formatos recomendados
(HU "Como / Quero / Para"; critérios "Dado / Quando / Então") e a lista de características da
explicação, mas não traz templates — `artefatos/DRE.md` contém apenas a Visão e o Glossário. A
tarefa também tem trechos marcados "(confirmar)" e "???" no texto. O que segue é escolha de engenharia.
Código: `backend/baml_src/specification_4_specify.baml`, `backend/openupexp/agents/phase4.py`.

| Pendência | Interpretação provisória | Base na teoria |
|---|---|---|
| A-21 — Escopo | Entram os requisitos `EXPLICABILIDADE` analisados na Fase 3, exceto os `WONT`, que aparecem no DRE como "não especificados nesta versão" | Definição de WONT no passo 7 da Análise |
| 4.1.2 — Preparar | Determinística: uma **ficha por requisito** com enunciado, prioridade aprovada, stakeholders, necessidades, aspecto, tipos de explicação, caracterização (RER) e restrições. As tarefas 4.2.x só recebem fichas | Entradas da tarefa (Visão + requisitos analisados) |
| A-14 / A-21 — HU (4.2.1) | `HU-n` com `req_id`, `stakeholder_id`, Como, Quero, Para. Ao menos uma HU por requisito; mais de uma quando há stakeholders com necessidades distintas. A prioridade não é campo da HU: vem da ficha | Passo 1 (formato recomendado; "uma necessidade principal por história") |
| A-14 — Critérios (4.2.2) | `CA-n` por HU, com um ou mais cenários Dado / Quando / Então. Valores mensuráveis só se estiverem nas entradas; senão, lacuna | Passo 2 |
| A-14 — Características (4.2.3) | `CEX-n` por HU com os sete itens do passo 3; nível (resumido/intermediário/detalhado), formato (textual/visual/tabular/combinado) e momento (antes/durante/após/sob demanda) como listas fechadas. Usa as respostas do checklist de limites da Visão | Passo 3; checklist "Limite da Explicabilidade" (momento, forma) |
| A-14 — Rastreabilidade (4.2.4) | **Calculada, sem LLM**: uma linha por HU com requisito, RER, stakeholder, necessidades, origens da Fase 2 (RI/RC), critérios, características e prioridade; registra requisitos sem HU e HU órfãs. Links `specifies` (CA/CEX → HU) e `refines` (HU → REQ) | Passo 4 (lista dos elementos e "rastreabilidade bidirecional") |
| A-13 / A-20 — Reach Consensus (4.2.5) | Mesma regra provisória das Fases 2–3; retorno apenas a 4.2. O passo 1 sugere validar as HU antes dos critérios, mas o BPMN tem um só consenso, depois de 4.2.4 — seguimos o BPMN | Passo 6; BPMN 4.2 |
| 4.3.1 — Pré-revisão | Checklist das boas práticas: formato das HU e dos cenários, stakeholder coerente, cobertura de critérios e características, matriz completa, consenso, ausência de stale, e uma **heurística** de termos vagos sem número no "Então" | Boas práticas dos passos 1, 2, 4 e 5 |
| A-01 — Retorno do gateway 4.3 | Revisitar 4.1 ou 4.2, com comentário obrigatório | Anotação BPMN em 4.3 |
| A-11 / A-12 — DRE | DRE final = ERD aprovado da Fase 3 (Visão, Requisitos, Análise) + Parte 4 (HU com critérios e características, matriz, consenso, lacunas) | Passo 5 ("único Documento de Requisitos de Explicabilidade") |

