# Plataforma OpenUPExp — documentação de arquitetura

> **Para quem é este material:** para a autora da teoria OpenUPExp, para a orientação e para a
> equipe que desenvolve a plataforma. Ele explica *o que* foi construído, *por que* foi construído
> assim e *o que ainda depende de decisões da teoria*.
>
> **Repositório da teoria:** `OpenUPExp` (BPMN, tarefas, papéis, templates).
> **Repositório da plataforma:** este (`OpenUPExp-LangGraph`), branch `docs/arquitetura-plataforma`.

## Comece por aqui

A plataforma transforma o processo OpenUPExp em um sistema web. Agentes de IA preparam
os artefatos de cada etapa — Visão, requisitos, análise e especificação — e **as pessoas
continuam decidindo**: aprovam, pedem ajustes e chegam a consenso nos mesmos pontos em que
o BPMN prevê decisões humanas.

Toda a teoria continua vindo do repositório OpenUPExp. A plataforma **lê** os diagramas
BPMN e os textos das tarefas; ela não os altera. Quando a teoria ainda não define algo
(um template, uma regra de consenso), a plataforma adota uma **interpretação provisória**,
registrada e marcada como tal, para que a autora possa confirmar ou corrigir.

Se você tem pouco tempo, leia nesta ordem:

1. **[00 — A plataforma em linguagem simples](00-visao-geral.md)**: um passeio por um projeto
   do início ao fim, sem jargão.
2. **[12 — Decisões pendentes](12-decisoes-pendentes.md)**: as perguntas que dependem da
   autora e as interpretações que adotamos enquanto isso.
3. **[03 — Como as Fases 2 a 4 foram desenhadas](03-fases-2-4-preliminar.md)** e
   **[02 — Fase 1](02-mapeamento-fase-1-visao.md)**: como cada tarefa do BPMN virou trabalho
   da IA ou decisão de pessoas.

## Onde estamos hoje

| O quê | Situação |
|---|---|
| As quatro etapas do processo (Visão, Elicitação, Análise, Especificação) | **Funcionam de ponta a ponta**, com aprovação e consenso nos pontos do BPMN |
| Documento final (DRE) | Gerado ao fim de cada etapa e acumulado até a Especificação |
| Rastreabilidade e evidências | Cada item aponta para sua origem; citações de leis e manuais são conferidas automaticamente |
| Interface web | Redesenhada com linguagem simples, cores por etapa, tema escuro e textos dos diagramas em português |
| Modelos de IA | Vários provedores (OpenAI, Google, Groq, Anthropic) e um **modelo local opcional** |
| Laboratório de modelos | Compara modelos e estratégias de contexto na mesma tarefa, com métricas, gabarito e notas humanas |
| Interpretações provisórias | Fases 2, 3 e 4 têm formatos provisórios, à espera da autora (cap. 12) |
| Uso com IA real | Testado tarefa a tarefa (laboratório); ainda falta conduzir um projeto inteiro com IA real |

## Como ler as etiquetas

Cada trecho importante vem marcado. A regra principal: **nada marcado como proposta deve
ser lido como definição original do OpenUPExp.**

| Etiqueta | O que quer dizer |
|---|---|
| **[TEORIA]** | Vem do modelo OpenUPExp (BPMN, tarefas, papéis, templates) |
| **[IMPLEMENTADO]** | Já existe e funciona na plataforma |
| **[PROPOSTA]** | Escolha de engenharia da equipe — pode mudar |
| **[PENDENTE-AUTORA]** | Precisa de uma definição da autora da teoria (lista no cap. 12) |
| **[PENDENTE-EQUIPE]** | Decisão técnica ainda em aberto na equipe |

## Capítulos

| # | Capítulo | O que você encontra | Para quem |
|---|---|---|---|
| 00 | [A plataforma em linguagem simples](00-visao-geral.md) | O caminho de um projeto, o que a IA faz e o que as pessoas decidem | todos — **comece aqui** |
| 01 | [Teoria e estado inicial](01-teoria-e-estado-atual.md) | O que a teoria define, as inconsistências encontradas e o protótipo de onde partimos | autora, orientação |
| 02 | [Fase 1 — Visão, tarefa por tarefa](02-mapeamento-fase-1-visao.md) | Como cada tarefa do BPMN da Visão foi mapeada | autora, equipe |
| 03 | [Fases 2 a 4 — como foram desenhadas](03-fases-2-4-preliminar.md) | O desenho das etapas de Elicitação, Análise e Especificação | autora, equipe |
| 04 | [Arquitetura de software](04-arquitetura-de-software.md) | As peças do sistema e como conversam | equipe |
| 05 | [Contexto e evidências](05-contexto-e-evidencias.md) | O que a IA recebe para ler e como as citações são conferidas | equipe, orientação |
| 06 | [Modelo de dados](06-modelo-de-dados.md) | Como versões, itens e decisões são guardados | equipe |
| 07 | [Pessoas no processo: aprovação e consenso](07-human-in-the-loop.md) | Como funcionam as decisões humanas | autora, equipe |
| 08 | [Contratos dos agentes (BAML)](08-contratos-baml.md) | O formato que cada agente precisa respeitar | equipe |
| 09 | [Medição e metodologia experimental](09-observabilidade-e-metodologia.md) | Como avaliar a qualidade e o custo | orientação, equipe |
| 10 | [Interface web](10-interface-web.md) | As telas e a linguagem usada | autora, equipe |
| 11 | [Roteiro, testes e riscos](11-roadmap-testes-riscos.md) | O que já foi feito, o que falta, os riscos | equipe, orientação |
| 12 | [Decisões pendentes](12-decisoes-pendentes.md) | Perguntas para a autora e interpretações provisórias | **autora** |
| 13 | [Notas de implementação](13-notas-de-implementacao.md) | Diário técnico: o que foi feito e por quê | equipe |
| 14 | [Modelos de IA, modelo local e laboratório](14-modelos-e-laboratorio.md) | Escolha de modelos, modelo local e comparação científica | orientação, equipe |

## Pequeno glossário

Termos técnicos que aparecem ao longo dos capítulos, explicados sem rodeios.

| Termo | Em palavras simples |
|---|---|
| **Agente** | Um pedido bem delimitado a um modelo de IA, com entradas e formato de saída definidos — por exemplo, "identifique os stakeholders a partir do escopo" |
| **Modelo de linguagem (LLM)** | O "motor" de IA que lê e escreve texto (GPT, Gemini, Qwen…) |
| **Modelo local** | Um modelo que roda no próprio computador ou servidor, sem enviar documentos para fora |
| **BAML** | A linguagem em que escrevemos os pedidos aos agentes e o formato exato das respostas |
| **LangGraph** | A ferramenta que encadeia as tarefas, pausa para as decisões humanas e retoma depois |
| **Manifesto do processo** | Um arquivo que liga cada tarefa do BPMN ao que a plataforma executa nela |
| **Artefato** | Cada resultado estruturado (lista de stakeholders, requisitos, histórias…) — o DRE é montado a partir deles |
| **Versão desatualizada (stale)** | Um artefato cuja entrada mudou depois que ele foi feito; precisa ser refeito |
| **Lacuna** | Uma informação que a IA declarou não encontrar nas entradas — vira pergunta para as pessoas |
| **Evidência** | Um trecho literal de lei, manual ou entrevista que sustenta um item; a plataforma confere se o trecho existe |
| **Contexto** | O material que a IA recebe para ler em cada tarefa |
| **Estratégia de contexto (A, B, C, D)** | Formas diferentes de escolher esse material, comparadas na pesquisa |
| **Busca híbrida / recuperação** | Encontrar nos documentos os trechos mais relacionados a uma pergunta |
| **Embedding** | Uma "impressão digital" numérica do texto que permite achar textos parecidos |
| **Token** | Pedaço de palavra; é a unidade de tamanho e de custo dos modelos |
| **Gateway / aprovação** | O ponto do BPMN em que o Engenheiro de Requisitos aprova ou pede retorno |
| **Consenso** | A rodada em que a equipe registra se concorda, concorda com observações ou discorda |
| **Digest** | Um resumo de uma etapa já aprovada, usado como contexto nas etapas seguintes |
| **Laboratório** | A área que refaz uma mesma tarefa com modelos ou estratégias diferentes, para comparar |
| **Gabarito** | A lista de itens que uma resposta correta deveria conter, feita por especialistas |

## Princípios que guiaram a construção [PROPOSTA]

1. **O BPMN é a referência, não o motor.** A plataforma segue os diagramas da teoria por meio
   do manifesto, conferido automaticamente contra os arquivos `.bpmn`.
2. **Dados estruturados primeiro, documento depois.** Cada artefato é guardado de forma
   estruturada e versionada; o DRE em Markdown é gerado a partir deles.
3. **A IA recebe só o necessário.** O contexto de cada tarefa é montado sob medida, com
   verificação de que nada obrigatório ficou de fora.
4. **Afirmações normativas precisam de evidência conferível.** Requisitos que vêm de leis e
   manuais apontam para o trecho exato, e a citação é verificada mecanicamente.
5. **Decisões humanas ficam registradas.** Aprovações, retornos e consensos não se apagam;
   versões anteriores são preservadas.
6. **Seguir o processo ≠ produzir bons requisitos.** As duas coisas são medidas separadamente.
7. **Independente de domínio.** O caso INPI é o primeiro estudo de caso; o domínio vive nos
   documentos do projeto, nunca nos prompts.
8. **Reprodutível.** Cada execução guarda a versão do processo, dos prompts, do modelo e dos
   documentos que usou.
9. **Simples de operar.** Um único banco (PostgreSQL) guarda dados, fila e busca; componentes
   pesados, como o modelo local, são opcionais.

## Principais decisões técnicas [PROPOSTA]

| Tema | Decisão | Capítulo |
|---|---|---|
| Interface | React + TypeScript, com os diagramas BPMN originais (bpmn-js) | 10 |
| Serviços | API (FastAPI) e um "worker" separado que executa os agentes | 04 |
| Banco e fila | PostgreSQL com pgvector; fila na própria base | 04, 06 |
| Busca nos documentos | Híbrida (palavras + semântica), com divisão por artigo e seção | 05 |
| Contexto | Estratégias A/B/C/D e verificação de completude | 05 |
| Contratos dos agentes | BAML como fonte única | 08 |
| Decisões humanas | Aprovação individual e consenso, como mecanismos distintos | 07 |
| Modelos de IA | Catálogo administrável; modelo local opcional como referência | 14 |
| Comparação científica | Laboratório com mesmas entradas, repetições e gabarito | 14, 09 |

Para gerar um PDF único para leitura:

```bash
pandoc docs/architecture/README.md docs/architecture/[0-9]*.md \
  -o openupexp-arquitetura.pdf --toc -F mermaid-filter
```
