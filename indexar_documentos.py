
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# Diretórios
PASTA_DOCUMENTOS = Path("documentos RAG") / "RAG"
PASTA_CHROMA = Path("chroma_db")

# Configuração da indexação
NOME_COLECAO = "openup_exp"
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TAMANHO_CHUNK = 1000
SOBREPOSICAO = 150


def extrair_paginas(caminho_pdf):
    """Extrai o texto de cada página do PDF."""
    leitor = PdfReader(str(caminho_pdf))
    paginas = []

    for numero, pagina in enumerate(leitor.pages, start=1):
        texto = pagina.extract_text() or ""

        if texto.strip():
            paginas.append({
                "pagina": numero,
                "texto": texto.strip()
            })

    return paginas


def dividir_texto(texto, tamanho=1000, sobreposicao=150):
    """Divide o texto em chunks com sobreposição."""
    chunks = []
    inicio = 0

    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))
        trecho = texto[inicio:fim].strip()

        if trecho:
            chunks.append(trecho)

        if fim == len(texto):
            break

        inicio = fim - sobreposicao

    return chunks


def main():
    if not PASTA_DOCUMENTOS.exists():
        raise FileNotFoundError(
            f"Pasta de documentos não encontrada: {PASTA_DOCUMENTOS}"
        )

    arquivos_pdf = sorted(PASTA_DOCUMENTOS.glob("*.pdf"))

    if not arquivos_pdf:
        raise FileNotFoundError(
            f"Nenhum PDF encontrado em: {PASTA_DOCUMENTOS}"
        )

    print(f"PDFs encontrados: {len(arquivos_pdf)}")
    print(f"Carregando modelo de embeddings: {MODELO_EMBEDDING}")

    modelo = SentenceTransformer(MODELO_EMBEDDING)

    cliente = chromadb.PersistentClient(path=str(PASTA_CHROMA))

    # Recria a coleção para evitar duplicação de chunks
    # ao executar novamente a indexação.
    try:
        cliente.delete_collection(NOME_COLECAO)
    except Exception:
        pass

    colecao = cliente.create_collection(
        name=NOME_COLECAO,
        metadata={"hnsw:space": "cosine"}
    )

    documentos = []
    metadados = []
    ids = []

    for caminho_pdf in arquivos_pdf:
        print(f"Processando: {caminho_pdf.name}")

        paginas = extrair_paginas(caminho_pdf)

        for item in paginas:
            chunks = dividir_texto(
                item["texto"],
                TAMANHO_CHUNK,
                SOBREPOSICAO
            )

            for indice, chunk in enumerate(chunks):
                documentos.append(chunk)
                metadados.append({
                    "arquivo": caminho_pdf.name,
                    "pagina": item["pagina"],
                    "chunk": indice
                })
                ids.append(
                    f"{caminho_pdf.stem}_p{item['pagina']}_c{indice}"
                )

    if not documentos:
        raise ValueError(
            "Nenhum texto foi extraído dos PDFs. "
            "Verifique se os arquivos contêm texto selecionável."
        )

    print(f"Chunks preparados: {len(documentos)}")
    print("Gerando embeddings e armazenando no Chroma...")

    TAMANHO_LOTE = 64

    for inicio in range(0, len(documentos), TAMANHO_LOTE):
        fim = inicio + TAMANHO_LOTE

        lote_documentos = documentos[inicio:fim]
        lote_metadados = metadados[inicio:fim]
        lote_ids = ids[inicio:fim]

        embeddings = modelo.encode(
            lote_documentos,
            normalize_embeddings=True
        ).tolist()

        colecao.add(
            ids=lote_ids,
            documents=lote_documentos,
            metadatas=lote_metadados,
            embeddings=embeddings
        )

        print(f"Indexados: {min(fim, len(documentos))}/{len(documentos)}")

    print("\nIndexação concluída!")
    print(f"Total de chunks: {colecao.count()}")
    print(f"Base persistida em: {PASTA_CHROMA.resolve()}")


if __name__ == "__main__":
    main()
