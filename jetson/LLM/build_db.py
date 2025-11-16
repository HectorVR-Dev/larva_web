import os
import glob
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.text_splitter import MarkdownHeaderTextSplitter

# ===================== CONFIGURACIÓN =====================
DATA_DIR = "./data"
CHROMA_DIR = "./chroma_db"
EMB_MODEL = "sentence-transformers/multi-qa-mpnet-base-cos-v1"
FORCE_REBUILD = True  # Cambia a False para evitar reconstrucción

# ===================== SPLIT POR SECCIONES =====================
HEADERS = [
    ("#", "header_1"),
    ("##", "header_2"),
    #("###", "header_3"),
]

markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS)

# ===================== METADATOS MANUALES =====================
METADATA_MAP = {
    "ascaris.md": {
        "category": "nematodo",
        "species": "ascaris lumbricoides"
    },
    "trichuris.md": {
        "category": "cestodo",
        "species": "trichuris trichiura"
    },
    "fasciola.md": {
        "category": "trematodo",
        "species": "fasciola hepatica"
    },
    "taenia.md": {
        "category": "cestodo",
        "species": "taenia saginata"
    },
}
# ============================================================


def load_markdown(path: str) -> str:
    """Carga el contenido del archivo Markdown sin procesar."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    print("Iniciando construcción de la base de datos Chroma...")

    if not os.path.exists(DATA_DIR):
        raise FileNotFoundError(f"No se encontró el directorio: {DATA_DIR}")

    if os.path.exists(CHROMA_DIR) and not FORCE_REBUILD:
        print(f"Base de datos ya existe en: {CHROMA_DIR}")
        print("   → Usa FORCE_REBUILD=True para reconstruir.")
        return

    md_files = glob.glob(f"{DATA_DIR}/*.md")
    if not md_files:
        raise FileNotFoundError(f"No se encontraron archivos .md en {DATA_DIR}")

    print(f"Encontrados {len(md_files)} archivos Markdown:")
    for f in md_files:
        print(f"   - {os.path.basename(f)}")

    print("\nCargando y procesando documentos...")
    processed_docs = []

    for file_path in md_files:
        filename = os.path.basename(file_path)

        raw_markdown = load_markdown(file_path)

        # Dividir por secciones estructuradas
        sections = markdown_splitter.split_text(raw_markdown)

        for sec in sections:
            metadata = sec.metadata.copy()

            metadata["source"] = filename
            metadata["file_path"] = file_path

            # insertar metadatos manuales
            if filename in METADATA_MAP:
                for key, value in METADATA_MAP[filename].items():
                    metadata[key] = value

            processed_docs.append(
                Document(
                    page_content=sec.page_content.strip(),
                    metadata=metadata
                )
            )

    processed_docs = filter_complex_metadata(processed_docs)

    print(f"Chunks generados por secciones: {len(processed_docs)}")

    print(f"\nCargando modelo de embeddings: {EMB_MODEL}")
    embedder = HuggingFaceEmbeddings(
        model_name=EMB_MODEL,
        model_kwargs={"trust_remote_code": True},
        encode_kwargs={"prompt_name": "document"},
    )

    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    print(f"\nConstruyendo base de datos en: {CHROMA_DIR}")
    vectorstore = Chroma.from_documents(
        documents=processed_docs,
        embedding=embedder,
        persist_directory=CHROMA_DIR
    )

    print("\nBase de datos creada exitosamente!")
    print(f"   → Total de chunks: {vectorstore._collection.count()}")
    print(f"   → Ubicación: {CHROMA_DIR}")


if __name__ == "__main__":
    main()
