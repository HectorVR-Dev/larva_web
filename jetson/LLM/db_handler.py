from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_core.runnables import RunnableLambda
from huggingface_hub import login
from dotenv import load_dotenv
import os

import torch

#vision_model = utils.yolo_model("yolo11x.pt")
#vision_model.inference('image.png')
#visual_context = vision_model.visual_contex()

load_dotenv()
login(token=os.getenv("AUTH_TOKEN_HUGGINGFACE"))

class DBHandler(Chroma):
    """
    Clase wrapper para ChromaDB optimizada para producción.
    Carga una base de datos existente o falla con mensaje claro.
    """
    def __init__(self, persist_directory="./chroma_db"):
        if not os.path.exists(persist_directory):
            raise FileNotFoundError(f"DB no encontrada: {persist_directory}. Ejecuta build_db.py")

        # === MISMO MODELO QUE build_db.py ===
        embedder = HuggingFaceEmbeddings(
            model_name="sentence-transformers/multi-qa-mpnet-base-cos-v1",
            model_kwargs={
                'device': 'cuda' if torch.cuda.is_available() else 'cpu',  # o 'cuda' si tienes GPU
                'trust_remote_code': True
            },
            encode_kwargs={
                'normalize_embeddings': True,
                'prompt_name': 'query'  # Para búsquedas optimizadas
            }
        )

        super().__init__(
            persist_directory=persist_directory,
            embedding_function=embedder
        )

        # Verificación de dimensión
        test_vec = embedder.embed_query("test")
        expected_dim = 768  # Dimensión de multi-qa-mpnet-base-cos-v1
        if len(test_vec) != expected_dim:
            raise ValueError(
                f"¡Dimensión de embedding incorrecta!\n"
                f"   → Esperado: {expected_dim}\n"
                f"   → Obtenido: {len(test_vec)}\n"
                f"   → ¿Estás usando 'all-MiniLM-L6-v2' por error?"
            )

        print(f"Base de datos cargada desde: {persist_directory}")
        print(f"Documentos totales: {self._collection.count()}")
        print(f"Dimensión de embeddings: {len(test_vec)}")

        
    # ------------------------------------------------------------------ #
    # MÉTODOS ÚTILES PARA RAG
    # ------------------------------------------------------------------ #

    def get_retriever(self, k: int = 4, **search_kwargs):
        """
        Devuelve un retriever listo para usar en cadenas LCEL.
        Incluye formato automático de documentos.
        """
        retriever = self.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k, **search_kwargs}
        )

        # Función para formatear documentos
        def format_docs(docs):
            """Convierte Documents a texto limpio"""
            result = "\n\n".join(doc.page_content for doc in docs)
            return result

        # Encadenamos: retriever → format_docs
        return retriever | RunnableLambda(format_docs)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs
    )   -> list:
        """
        Búsqueda directa (útil para pruebas).
        """
        return super().similarity_search(query, k=k, **kwargs)

    def count_documents(self) -> int:
        """Devuelve el número total de documentos."""
        return self._collection.count()

    def health_check(self) -> dict:
        """Verificación rápida del estado de la DB."""
        return {
            #"persist_directory": self.persist_directory,
            "document_count": self.count_documents(),
            "embedding_model": self.embedding_function.model_name
            if hasattr(self.embedding_function, "model_name")
            else "custom",
            "status": "healthy" if self.count_documents() > 0 else "empty"
        }