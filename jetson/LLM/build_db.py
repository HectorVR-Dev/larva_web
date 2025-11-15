# build_db.py
import os
import glob
from pathlib import Path

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# ===================== CONFIGURACIÓN =====================
DATA_DIR = "./data"
CHROMA_DIR = "./chroma_db"
EMB_MODEL = "sentence-transformers/multi-qa-mpnet-base-cos-v1"
FORCE_REBUILD = True  # Cambia a False para evitar reconstrucción

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
# =========================================================


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
    documents = []
    for file_path in md_files:
        loader = UnstructuredMarkdownLoader(
            file_path,
            mode="single",
            strategy="fast"
        )
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = os.path.basename(file_path)
            doc.metadata["file_path"] = file_path
        documents.extend(filter_complex_metadata(docs))

    print(f"Documentos cargados: {len(documents)}")

    print("Dividiendo en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Chunks generados: {len(chunks)}")

    print(f"\nCargando modelo de embeddings: {EMB_MODEL}")
    embedder = HuggingFaceEmbeddings(
        model_name=EMB_MODEL,
        model_kwargs={"trust_remote_code": True},
        encode_kwargs={"prompt_name": "document"},
    )

    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)

    print(f"\nConstruyendo base de datos en: {CHROMA_DIR}")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=CHROMA_DIR  # ← Persistencia automática
    )

    # ELIMINA ESTA LÍNEA:
    # vectorstore.persist()  # ← YA NO EXISTE

    print(f"Base de datos creada exitosamente!")
    print(f"   → Total de chunks: {vectorstore._collection.count()}")
    print(f"   → Ubicación: {CHROMA_DIR}")


if __name__ == "__main__":
    main()