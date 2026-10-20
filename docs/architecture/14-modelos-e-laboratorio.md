# 14 — Modelos de linguagem, modelo local e laboratório [PROPOSTA]

Este capítulo trata de **qual modelo de linguagem executa os agentes** e de como compará-los.
Nada aqui vem da teoria OpenUPExp: é decisão de arquitetura da plataforma.

| Passo | Entrega | Situação |
|---|---|---|
| 0 | Este capítulo: arquitetura, modelo de dados e plano | [IMPLEMENTADO] |
| 1 | Ollama opcional no Compose, modelo local protegido, escolha do perfil por execução, registro da configuração usada | [IMPLEMENTADO] |
| 2 | Administração de modelos e perfis, com teste de conexão, teste de compatibilidade e lista de servidores permitidos | [PROPOSTA] |
| 3 | Laboratório v1: reexecutar tarefas reais com o mesmo pacote de contexto em vários modelos | [PROPOSTA] |
| 4 | Laboratório v2: estratégias A–D (com a B), matriz modelo × estratégia, gabaritos (M4) | [PROPOSTA] |

## 14.1 Princípios

1. **Modelo local como referência (baseline), não como obrigação — e opcional na instalação.**
   Um modelo pequeno, executado na própria máquina via Ollama, vem cadastrado e protegido: não
   pode ser excluído nem ter a configuração-base alterada pela interface. Quando ligado, é o perfil
   padrão; cada execução pode usar outro modelo habilitado. Como ele é pesado sem GPU, a
   instalação pode **não** subi-lo (padrão): o cadastro continua, desligado, e o padrão passa a
   ser a "nuvem com reserva".
2. **Provedores externos continuam valendo.** Groq, OpenAI, Anthropic, Google e servidores
   compatíveis com a API da OpenAI (vLLM, Ollama remoto).
3. **Modelo ≠ perfil de inferência.** O modelo diz *onde* e *qual* (provedor, endereço, nome,
   chave). O perfil diz *como* (temperatura, limite de saída, tamanho de contexto, raciocínio).
   O mesmo modelo pode ter vários perfis.
4. **Configuração congelada por execução.** Ao iniciar uma execução, o perfil é resolvido e copiado
   para `run.model_profile` (snapshot). Editar o cadastro depois não altera o que a execução usou.
5. **Sem fallback silencioso em perfis cadastrados.** Uma execução com perfil escolhido usa só
   aquele modelo; falhas aparecem como falhas. O fallback entre famílias (`OpenUPExpDefault` em
   `clients.baml`) continua disponível como perfil "nuvem com reserva".
6. **Segredos fora do banco e do navegador.** O cadastro guarda só o *nome* da variável de
   ambiente com a chave (`api_key_env`). O valor é lido pelo worker.
7. **Contratos únicos.** Todos os modelos usam as mesmas funções BAML; a troca é feita com o
   `ClientRegistry` do BAML em tempo de execução, sem duplicar prompts.

## 14.2 Arquitetura

```mermaid
flowchart LR
  UI[Interface] -->|perfil escolhido| API
  API -->|resolve e congela| RUN[(run.model_profile)]
  API -.->|versão dos pesos| OLL
  W[Worker] -->|lê snapshot| RUN
  W -->|ClientRegistry: add_llm_client + set_primary| BAML[Funções BAML]
  BAML -->|OpenAI-compatível| OLL[Ollama · modelo local]
  BAML --> EXT[Provedores externos]
  W --> LLMCALL[(llm_call: modelo, tokens, latência)]
```

- **Ollama** é um serviço **opcional** do Docker Compose, no perfil `local-llm` (`ollama`,
  imagem fixada, volume `ollama_models`, teto de CPU e memória configurável). Um serviço de
  inicialização (`ollama-pull`) baixa o modelo e cria a variante da plataforma com os parâmetros
  do perfil (contexto de 16 mil tokens, temperatura 0).

### Ligar ou não o modelo local

| Situação | Configuração | Efeito |
|---|---|---|
| Máquina sem GPU / com pouca memória (padrão) | `LOCAL_LLM_ENABLED=false`; `docker compose up -d` | Ollama não sobe; modelo local aparece desligado; padrão = nuvem com reserva |
| Quer o modelo local | `LOCAL_LLM_ENABLED=true`; `docker compose --profile local-llm up -d` | Ollama sobe com teto `OLLAMA_CPUS` (4) e `OLLAMA_MEM_LIMIT` (6 GB); padrão = modelo local |
| Ollama em outra máquina (servidor com GPU) | `LOCAL_LLM_ENABLED=true`; `OLLAMA_URL=http://servidor:11434` | Nenhum container local; mesma interface |

A terceira linha é o caminho natural para a pesquisa: o modelo "local" roda em um servidor da
instituição, e as máquinas de desenvolvimento não carregam o modelo.
- O **worker** monta o cliente BAML a partir do snapshot (`provider`, `base_url`, `model`,
  parâmetros, chave lida de `api_key_env`) e o define como primário para todas as funções.
- A **API** registra, ao iniciar a execução, o identificador da versão dos pesos do modelo
  local (`digest` do Ollama), para auditoria.

### Modelo local inicial

O candidato inicial é o **Qwen3 4B Instruct-2507** quantizado em 4 bits
(`qwen3:4b-instruct-2507-q4_K_M`, 2,5 GB), da família Qwen3. O **Qwen3 8B** fica para comparação.
A escolha não foi feita por desempenho medido; a decisão final depende das medições (§14.6).

O Qwen3 "híbrido" tem um **modo de raciocínio** que gera um bloco de pensamento antes da resposta.
Na CPU isso multiplica o tempo e pode atrapalhar a leitura da saída estruturada. A variante
Instruct-2507 não tem esse modo, por isso foi escolhida. O parâmetro `think` fica registrado no
perfil para quando o laboratório comparar variantes com raciocínio.

## 14.3 Modelo de dados

```mermaid
erDiagram
  llm_model ||--o{ inference_profile : "tem"
  inference_profile ||--o{ run : "congelado em run.model_profile"
  llm_model {
    uuid id PK
    string slug UK
    string nome
    string provider "ollama | openai-generic | openai | openai-responses | anthropic | google-ai | baml-named"
    string base_url
    string model
    string api_key_env "nome da variável; nunca o valor"
    bool local
    bool protected "não editável nem excluível pela interface"
    bool enabled
    jsonb meta
  }
  inference_profile {
    uuid id PK
    uuid model_id FK
    string slug UK
    string nome
    jsonb params "temperature, max_tokens, num_ctx, think"
    bool protected
    bool is_default "exatamente um"
    bool enabled
  }
```

Snapshot em `run.model_profile` (já existia; passa a ter estrutura definida):

```json
{
  "profile_id": "…", "profile_slug": "local-qwen3-4b", "profile_nome": "Qwen3 4B local",
  "model_slug": "qwen3-4b-local", "provider": "ollama", "base_url": "http://ollama:11434/v1",
  "model": "openupexp-qwen3-4b", "params": {"temperature": 0, "think": false},
  "api_key_env": null, "local": true, "model_digest": "sha256:…", "resolved_at": "…"
}
```

Planejado para o passo 3 (laboratório):

| Tabela | Conteúdo |
|---|---|
| `lab_comparison` | Tarefa, execução de origem, pacote de contexto reutilizado, perfis comparados, quem criou, situação |
| `lab_trial` | Uma tentativa por perfil: snapshot do perfil, saída bruta e validada, validade do contrato, cobertura, verificação das evidências, tokens, latência, custo, erro |
| `lab_rating` | Nota humana por tentativa (escala e critérios a definir com a autora) |

Alterações nos cadastros vão para `audit_log` (já existente), incluindo troca de versão dos pesos
do modelo local.

## 14.4 Administração (passo 2)

- Somente o papel `admin` acessa. Lista de modelos e perfis; o modelo local aparece com cadeado.
- **Cadastro** valida o endereço contra uma lista de servidores permitidos
  (`LLM_ALLOWED_HOSTS`), porque os agentes enviam conteúdo dos documentos do projeto ao modelo.
- **Teste de conexão**: lista os modelos do servidor ou faz uma chamada mínima.
- **Teste de compatibilidade**: executa uma função BAML curta com entrada fixa e verifica se a
  saída é aceita pelo contrato. Só modelos aprovados podem ser habilitados para execuções.
- Habilitar/desabilitar e escolher o perfil padrão (o local é o padrão inicial).

## 14.5 Laboratório (passos 3 e 4)

Objetivo: comparar modelos **com tudo o mais fixo**.

- **Reexecução com o mesmo pacote de contexto.** Cada tarefa executada já guarda o pacote de
  contexto que o agente recebeu (`context_package`). O laboratório reexecuta a tarefa X da
  execução Y com esse mesmo pacote em N perfis. Entradas, trechos recuperados, prompt (versão de
  `baml_src`) e evidências ficam idênticos; muda só o modelo.
- **Fila e concorrência.** As tentativas passam pela fila do PostgreSQL com limite de
  concorrência por modelo (1 para o modelo local em CPU) e podem ser canceladas.
- **Métricas automáticas** (já disponíveis na plataforma): validade do contrato, uma saída por
  item esperado (cobertura), verificação mecânica das citações, tokens, latência, custo.
- **Avaliação humana**: nota por tentativa no próprio laboratório. Precisão e cobertura em
  relação a uma resposta correta dependem de gabaritos, previstos no M4 (cap. 09 §9.4).
- **Passo 4**: comparar estratégias de contexto A/B/C/D (a B ainda não existe) separadamente e em
  matriz cruzada com os modelos, para detectar interação entre os fatores.

### Pergunta de pesquisa possível [PROPOSTA]

> Até que ponto modelos pequenos executados localmente produzem artefatos de engenharia de
> requisitos de explicabilidade com qualidade, conformidade ao processo e rastreabilidade
> comparáveis às de modelos comerciais, sob diferentes estratégias de contexto?

Registrada como sugestão. Incluí-la no estudo é decisão da pesquisadora e da autora da teoria.

## 14.6 Medições no ambiente de desenvolvimento

Máquina de desenvolvimento: 8 núcleos, 30 GB de RAM, sem GPU dedicada; Ollama 0.34.4 sem teto
de CPU. Uma única função (1.1.1 `DefineExplainabilityProblem`) com o escopo do caso INPI,
chamada pelo mesmo caminho do worker (`ClientRegistry`, perfil local):

| Medição | Tempo total | Tokens (entrada/saída) |
|---|---|---|
| 1ª chamada (modelo carregando) | 169 s | — |
| 2ª chamada (modelo em memória) | 95 s | 1.277 / 706 (~8 tokens/s na saída) |

Observação qualitativa (uma amostra, não é avaliação): a saída respeitou o contrato BAML e
identificou os quatro stakeholders, mas deixou a maior parte dos campos vazia, com lacunas,
alegando que o escopo não trata de explicabilidade. É o comportamento conservador pedido pelas
regras de não invenção, levado ao extremo — exatamente o tipo de diferença que o laboratório
deve medir contra modelos maiores.

Estimativa para uma etapa: a Fase 1 faz ~10 chamadas com entradas maiores que esta; na CPU, algo
entre 20 e 40 minutos com o modelo em memória. É estimativa, não medição.

## 14.7 Riscos

| Risco | Mitigação |
|---|---|
| Modelo local lento em CPU | Usado como referência; perfis externos para uso diário; laboratório com fila |
| Contexto do Ollama menor que o prompt (padrão de poucos milhares de tokens) | Variante do modelo criada com contexto explícito; alerta quando o prompt estimado excede |
| Saída fora do contrato em modelos pequenos | Parser tolerante do BAML; teste de compatibilidade antes de habilitar; falha visível |
| Endpoint cadastrado vazar documentos | Lista de servidores permitidos; cadastro restrito a `admin`; auditoria |
| Comparações injustas por diferenças de RAG | Reexecução com o mesmo pacote de contexto |
