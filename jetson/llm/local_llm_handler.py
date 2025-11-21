from typing import Dict, Any
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFacePipeline
from langchain_core.output_parsers import StrOutputParser
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from huggingface_hub import login
from dotenv import load_dotenv
import os

load_dotenv()
login(token=os.getenv("AUTH_TOKEN_HUGGINGFACE"))

class LLMHandler:
    """
    Manejador del LLM: carga, configura y ejecuta el modelo Qwen3-4B-Instruct.
    Integra Chroma + visión en una cadena RAG determinística.
    """

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-1.5B-Instruct",
        vectorstore: Any = None,
        device_map: str = "auto",
        torch_dtype: str = "auto",
        load_in_4bit: bool = True,
        max_new_tokens: int = 256,
        temperature: float = 0.1,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        trust_remote_code: bool = True,
        verbose: bool = False,
    ):
        self.vectorstore = vectorstore
        self.model_id = model_id
        self.max_new_tokens = max_new_tokens

        print(f"Cargando modelo: {model_id}...")
        if verbose:
            print("   → Esto puede tomar 1-2 minutos la primera vez.")

        # 1. Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote_code=trust_remote_code,
        )


        # 2. Modelo (cuantizado)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map=device_map,
            torch_dtype=torch_dtype,
            load_in_4bit=False,
            trust_remote_code=trust_remote_code,
            low_cpu_mem_usage=True,
            quantization_config=None
        )

        # 3. Pipeline
        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=max_new_tokens,
            return_full_text=verbose,
            do_sample=False,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )

        # 4. LLM de LangChain
        self.llm = HuggingFacePipeline(pipeline=self.pipe)

        # 5. Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un asistente con acceso a base de datos Chroma.
            CONFIGURACIÓN:
            - Idioma: Español
            - Modo: Análisis determinístico
             
            CAPACIDADES:
            1. VISUAL: Puedes ver y analizar objetos en el contexto visual proporcionado
            2. CHROMA: Tienes acceso a información recuperada de la base vectorial Chroma
            3. SÍNTESIS: Debes combinar ambas fuentes para responder
             
            REGLAS ESTRICTAS:
            1. Solo usa información del CONTEXTO_VISUAL y CONTEXTO_CHROMA
            2. Respuesta clara y concisa en español
            3. La respuesta solo debe responder a la TAREA dada
             
            CONTEXTO_CHROMA:
            {context}
            CONTEXTO_VISUAL:
            {visual_context}
            INSTRUCCIONES DE PROCESAMIENTO:
            1. Identifica en contexto_visual
            2. Busca información en contexto_chroma
            3. Sintetiza una respuesta coherente """),
            
            ("human", """TAREA: {task}"""),
        ])
        print("LLM cargado y listo.")
        self.create_chain()
        print("Cadena creada y lista.")



    # ------------------------------------------------------------------ #
    # NORMALIZACIÓN DE CONTEXTO VISUAL
    # ------------------------------------------------------------------ #


    # Normalización desde YOLO → categoría académica
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

    def normalize_category(self, visual_context: list) -> str | None:
        if not visual_context:
            return None

        for key, value in self.CATEGORY_MAP.items():
            for item in visual_context:
                if key in item[0]:
                    return value
        return None
    
    def normalize_species(self, visual_context: list) -> str | None:
        if not visual_context:
            return None
        for key, value in self.SPECIES_MAP.items():
            for item in visual_context:
                if key in item[0]:
                    return value
        return None
    
    def normalize_visual_context(self, visual_context: list) -> str:
        if not visual_context:
            return "No se detectaron objetos relevantes en la imagen."

        lines = []
        for label, score in visual_context:
            lines.append(f"Estas {score * 100:.1f}% seguro de observar: {label}")

        return "\n".join(lines)
    
    # ------------------------------------------------------------------ #
    # MÉTODOS PRINCIPALES
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # MÉTODO 1: CREA LA CADENA (UNA VEZ)
    # ------------------------------------------------------------------ #
    def create_chain(self):
        """
        Crea una única chain reutilizable.
        category, species, k, threshold
        serán recibidos dinámicamente en cada pregunta.
        """

        def dynamic_retriever(inputs):
            """
            inputs contiene:
                - task
                - category
                - species
                - k
                - score_threshold
            """
            return self.vectorstore.hybrid_search(
                query=inputs["task"],
                category=inputs.get("category"),
                species=inputs.get("species"),
                k=inputs.get("k"),
                score_threshold=inputs.get("score_threshold")
            )

        def format_context(results):
            # results = [(doc, score)]
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

    # ------------------------------------------------------------------ #
    # MÉTODO 2: PREGUNTA RÁPIDA (usa cadena pre-creada)
    # ------------------------------------------------------------------ #
    def ask(
        self,
        task,
        visual_context,
        k=12,
        score_threshold=0.55
    ):
        return self.chain.invoke({
            "task": task,
            "visual_context": self.normalize_visual_context(visual_context),
            "category": self.normalize_category(visual_context),
            "species": self.normalize_species(visual_context),
            "k": k,
            "score_threshold": score_threshold
        })