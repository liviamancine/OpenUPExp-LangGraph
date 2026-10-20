
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


PASTA_CHROMA = Path(__file__).parent / "chroma_db"
NOME_COLECAO = "openup_exp"

MODELO_EMBEDDING = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


class RAGRetriever:
    def __init__(self):
        self.modelo = SentenceTransformer(MODELO_EMBEDDING)

        self.cliente = chromadb.PersistentClient(
            path=str(PASTA_CHROMA)
        )

        self.colecao = self.cliente.get_collection(
            name=NOME_COLECAO
        )

    def buscar(self, consulta: str, k: int = 5) -> list[dict]:
        """Recupera os trechos mais relevantes para uma consulta."""

        if not consulta or not consulta.strip():
            raise ValueError("A consulta não pode estar vazia.")

        quantidade = min(k, self.colecao.count())

        embedding_consulta = self.modelo.encode(
            consulta,
            normalize_embeddings=True
        ).tolist()

        resultado = self.colecao.query(
            query_embeddings=[embedding_consulta],
            n_results=quantidade,
            include=["documents", "metadatas", "distances"]
        )

        trechos = []

        for documento, metadados, distancia in zip(
            resultado["documents"][0],
            resultado["metadatas"][0],
            resultado["distances"][0]
        ):
            trechos.append({
                "texto": documento,
                "arquivo": metadados.get("arquivo", "Não identificado"),
                "pagina": metadados.get("pagina"),
                "chunk": metadados.get("chunk"),
                "distancia": distancia
            })

        return trechos


if __name__ == "__main__":
    retriever = RAGRetriever()

    consulta_teste = (
        "Identifique, separadamente, os critérios de registrabilidade previstos na Lei da Propriedade"
        " Industrial (LPI) e no Manual de Marcas do INPI — incluindo liceidade, distintividade, "
        "veracidade e disponibilidade do sinal marcário — e as informações sobre os critérios e "
        "procedimentos utilizados pela solução de IA que poderiam fundamentar a explicação da "
        "decisão. Como o Art. 20 da Lei Geral de Proteção de Dados Pessoais (LGPD) se relaciona à"
        " explicabilidade de decisões automatizadas de deferimento ou indeferimento de pedidos de"
        " registro de marcas?Considere exclusivamente o Art. 20 da LGPD, sem utilizar outros artigos"
        " dessa lei. Diferencie os fundamentos legais da decisão dos requisitos de explicabilidade"
        " do sistema."
    )

    resultados = retriever.buscar(consulta_teste, k=10)

    print(f"\nConsulta: {consulta_teste}")
    print(f"Trechos recuperados: {len(resultados)}\n")

    for indice, trecho in enumerate(resultados, start=1):
        print(f"--- Resultado {indice} ---")
        print(f"Arquivo: {trecho['arquivo']}")
        print(f"Página: {trecho['pagina']}")
        print(f"Distância: {trecho['distancia']:.4f}")
        print(f"Texto: {trecho['texto'][:700]}")
        print()
