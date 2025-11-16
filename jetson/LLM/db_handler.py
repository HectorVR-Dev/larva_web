from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_core.runnables import RunnableLambda
from huggingface_hub import login
from dotenv import load_dotenv
import torch
import os


load_dotenv()
login(token=os.getenv("AUTH_TOKEN_HUGGINGFACE"))


class DBHandler(Chroma):
    """
    DBHandler con filtrado real por metadatos (category, species)
    y búsqueda semántica híbrida (categoria → query).
    """

    def __init__(self, persist_directory="./chroma_db"):
        if not os.path.exists(persist_directory):
            raise FileNotFoundError(
                f"La base de datos no existe: {persist_directory}. Ejecuta build_db.py primero."
            )

        # MISMO MODELO QUE build_db.py
        embedder = HuggingFaceEmbeddings(
            model_name="sentence-transformers/multi-qa-mpnet-base-cos-v1",
            model_kwargs={
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "trust_remote_code": True
            },
            encode_kwargs={
                "normalize_embeddings": True,
                "prompt_name": "query"
            }
        )

        super().__init__(
            persist_directory=persist_directory,
            embedding_function=embedder
        )

        print(f"[DB] Base cargada desde {persist_directory}")
        print(f"[DB] Total docs: {self._collection.count()}")


    # ------------------------------------------------------------------ #
    # BÚSQUEDAS FILTRADAS POR METADATA
    # ------------------------------------------------------------------ #
    def search_by_metadata(self, query: str, metadata: dict, k: int):
        """
        Búsqueda semántica REAL filtrando por metadatos.
        """
        try:
            return super().similarity_search(
                query,
                k=k,
                filter=metadata
            )
        except Exception as e:
            print(f"[WARN] search_by_metadata falló: {e}")
            return []


    def get_all_by_category(self, category: str):
        """
        Obtiene todos los chunks de esa categoría sin límite.
        """
        try:
            docs = self._collection.get(
                where={"category": category},
                include=["documents", "metadatas"]
            )
            return docs
        except Exception as e:
            print(f"[WARN] get_all_by_category falló: {e}")
            return []


    # ------------------------------------------------------------------ #
    # BÚSQUEDA HÍBRIDA (especie → query)
    # ------------------------------------------------------------------ #
    def hybrid_search(self, query, category=None, species=None, score_threshold=0.55, k=5):
        # 1. Filtro por metadata basado en detección YOLO
        metadata_filter = None
        if category:
            metadata_filter = {"category": category}
        if species:
            metadata_filter = {"species": species}

        # 2. Similarity search con score
        results = self.similarity_search_with_score(
            query,
            k=20,
            filter=metadata_filter
        )

        # 3. Re-rank y filtrar por umbral
        filtered = [
            (doc, score) for doc, score in results
            if score <= score_threshold
        ]
        # 4. Orden descendente por score
        #filtered.sort(key=lambda x: x[1])
        # 5. Devolver solo docs si se quiere
        return filtered[0:k]

    # ------------------------------------------------------------------ #
    # RETRIEVERS (para LCEL)
    # ------------------------------------------------------------------ #
    def get_retriever_hybrid(self, k: int = 4, visual_context: str | None = None):
        def _retrieve(query):
            results = self.hybrid_query(query, visual_context, k)
            return "\n\n".join(doc.page_content for doc in results)

        return RunnableLambda(_retrieve)

    def get_retriever(self, k: int = 4):
        retriever = super().as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

        return retriever | RunnableLambda(
            lambda docs: "\n\n".join(doc.page_content for doc in docs)
        )

    # Utils
    def count_documents(self) -> int:
        return self._collection.count()

    def health_check(self):
        return {
            "document_count": self.count_documents(),
            "status": "ready" if self.count_documents() > 0 else "empty"
        }
