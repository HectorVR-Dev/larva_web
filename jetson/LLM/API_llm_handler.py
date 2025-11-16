from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from os import getenv

load_dotenv()

class OpenRouterLLMHandler:
    """
    Manejador remoto equivalente al manejador local Qwen,
    pero usando OpenRouter como backend.
    Funciona con la nueva base Chroma + metadatos + hybrid_search().
    """

    # =========================
    # MAPEO DE CATEGORÍAS
    # =========================
    CATEGORY_MAP = {
        "nematode": "nematodo",
        "cestodo": "cestodo",
        "trematodo": "trematodo",
    }

    SPECIES_MAP = {
        "ascaris_egg_fertile": "ascaris lumbricoides",
        "ascaris_egg_infertile": "ascaris lumbricoides",
        "trichuris_egg": "trichuris trichiura",
        "fasciola_egg": "fasciola hepatica",
        "taenia_egg": "taenia saginata",
    }

    def __init__(
        self,
        model: str = "nvidia/nemotron-nano-12b-v2-vl:free",
        temperature: float = 0.1,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        verbose: bool = False,
        vectorstore=None
    ):
        self.model_name = model
        self.verbose = verbose
        self.vectorstore = vectorstore

        api_key = getenv("OPENROUTER_API_KEY")
        if api_key is None:
            raise ValueError("Falta OPENROUTER_API_KEY en .env")

        # LLM remoto
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model=model,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=0,
            presence_penalty=0,
            verbose=verbose,
        )

        # Prompt idéntico al manejador local
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un asistente con acceso a base de datos Chroma.
            CONFIGURACIÓN:
            - Idioma: Español
            - Modo: Análisis determinístico
            
            CAPACIDADES:
            1. VISUAL: Puedes ver y analizar objetos en el contexto visual
            2. CHROMA: Es tu fuente principal de información textual
            3. SÍNTESIS: Debes combinar ambas fuentes para responder
            
            REGLAS ESTRICTAS:
            1. Solo usa información del CONTEXTO_VISUAL y CONTEXTO_CHROMA
            2. Respuesta clara y concisa en español
            3. La respuesta solo debe responder a la TAREA dada
            4. Si no hay suficiente información, responde "No lo sé"
            5. No menciones el proceso de obtención de información
            6. CONTEXTO_VISUAL define la búsqueda en CHROMA
             
            CONTEXTO_CHROMA:
            {context}

            CONTEXTO_VISUAL:
            {visual_context}

            INSTRUCCIONES:
            1. Identifica el contexto_visual
            2. Busca información en contexto_chroma
            3. Da una respuesta coherente y clara"""),

            ("human", """TAREA: {task}

            RESPUESTA:"""),
        ])

        print(f"✓ Handler remoto cargado: {model}")
        self.chain = self.create_chain()

    # =========================================================
    # NORMALIZADORES DEL CONTEXTO VISUAL
    # =========================================================
    def normalize_category(self, visual_context):
        if not visual_context:
            return None
        for key, value in self.CATEGORY_MAP.items():
            for item in visual_context:
                if key in item[0]:
                    return value
        return None

    def normalize_species(self, visual_context):
        if not visual_context:
            return None
        for key, value in self.SPECIES_MAP.items():
            for item in visual_context:
                if key in item[0]:
                    return value
        return None

    def normalize_visual_context(self, visual_context):
        if not visual_context:
            return "No se detectaron objetos relevantes."
        return "\n".join([
            f"Estas {score*100:.1f}% seguro de observar: {label}"
            for label, score in visual_context
        ])

    # =========================================================
    # CREAR LA CHAIN (exactamente igual al local)
    # =========================================================
    def create_chain(self):
        def dynamic_retriever(inputs):
            """
            Igual que en el manejador local:
            Retorna [(doc, score), ...]
            """

            return self.vectorstore.hybrid_search(
                query=inputs["task"],
                category=inputs.get("category"),
                species=inputs.get("species"),
                k=inputs.get("k"),
                score_threshold=inputs.get("score_threshold"),
            )

        def format_context(results):
            return "\n\n".join([doc.page_content for doc, score in results])

        self.chain = (
            {
                "input": RunnablePassthrough(),
                "context": lambda x: format_context(dynamic_retriever(x)),
                "task": lambda x: x["task"],
                "visual_context": lambda x: x["visual_context"],
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

        return self.chain

    # =========================================================
    # EJECUTAR UNA CONSULTA
    # =========================================================
    def ask(
        self,
        task: str,
        visual_context: list,
        k: int = 12,
        score_threshold: float = 0.55
    ):
        return self.chain.invoke({
            "task": task,
            "visual_context": self.normalize_visual_context(visual_context),
            "category": self.normalize_category(visual_context),
            "species": self.normalize_species(visual_context),
            "k": k,
            "score_threshold": score_threshold,
        })

    # =========================================================
    # HEALTH CHECK
    # =========================================================
    def health_check(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "provider": "OpenRouter",
            "status": "healthy",
        }
