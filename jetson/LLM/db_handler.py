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

    # Normalización desde YOLO → categoría académica
    CATEGORY_MAP = {
        "ascaris_egg": "ascaris lumbricoides",
        "ascaris_egg_fertile": "ascaris lumbricoides",
        "ascaris_egg_infertile": "ascaris lumbricoides",
        "helminto_egg": "ascaris lumbricoides",
        "nematode": "nematodo",
        "cestodo": "cestodo",
        "trematodo": "trematodo",
        "trichuris_egg": "trichuris trichiura",
        "fasciola_egg": "fasciola hepatica",
        "taenia_egg": "taenia saginata",
    }

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
    # NORMALIZACIÓN DE CATEGORÍA
    # ------------------------------------------------------------------ #
    def normalize_category(self, visual_context: str) -> str | None:
        if not visual_context:
            return None
        visual_context = visual_context.lower().strip()

        for key, value in self.CATEGORY_MAP.items():
            if key in visual_context:
                return value

        return None


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
    def hybrid_search(self, query, vectorstore, category=None, species=None, score_threshold=0.55, k=20):
        # 1. Filtro por metadata basado en detección YOLO
        metadata_filter = None
        if category:
            metadata_filter = {"category": category}
        if species:
            metadata_filter = {"species": species}

        # 2. Similarity search con score
        results = vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=metadata_filter
        )

        # 3. Re-rank y filtrar por umbral
        filtered = [
            (doc, score) for doc, score in results
            if score >= score_threshold
        ]

        # 4. Orden descendente por score
        filtered.sort(key=lambda x: x[1], reverse=True)

        # 5. Devolver solo docs si se quiere
        return filtered

    def hybrid_query(self, query: str, visual_context: str | None, k: int = 4):
        specie = self.normalize_category(visual_context)

        # --- Caso 1: Se identifica especie (gracias a YOLO)
        if specie:
            print(f"[DB] Especie detectada: {specie} → búsqueda filtrada")

            primary = self.search_by_metadata(query, {"species": specie}, k)

            if len(primary) >= k:
                return primary

            # Si no alcanza → completamos con búsqueda general
            remaining = k - len(primary)
            fallback = super().similarity_search(query, k=remaining)

            return primary + fallback

        # --- Caso 2: No hay especie
        print("[DB] Sin especie → búsqueda general")
        return super().similarity_search(query, k=k)


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
