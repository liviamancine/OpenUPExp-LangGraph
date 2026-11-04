# Protótipo original (linha de base)

Primeira versão do OpenUPExp em LangGraph + BAML: seis workers sequenciais que incrementam um
`blackboard` e geram o Documento de Visão parcial. Fica preservado aqui, executável, como
**linha de base experimental** (cap. 04 §4.6 e cap. 09 da documentação de arquitetura).
A plataforma nova está em `backend/` e `frontend/`.

| Arquivo | Papel |
|---|---|
| `main.py` | grafo dos 6 workers. Lê o escopo de `experiments/cases/inpi/` |
| `baml_src/`, `baml_client/` | contratos dos workers e cliente gerado |
| `indexar_documentos.py`, `rag_retriever.py`, `chroma_db/` | indexação e busca Chroma do corpus INPI |
| `blackboard.json`, `Documento_de_Visao_Explicabilidade_Parcial.md` | saída da última execução |
| `main_15_10.py`, `main_teste.py` | versões anteriores/rascunhos, mantidos só como histórico |

```bash
python legacy/indexar_documentos.py   # recria legacy/chroma_db a partir do corpus
python legacy/main.py                 # grava as saídas em legacy/
```
