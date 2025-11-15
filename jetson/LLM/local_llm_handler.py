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
            
            ("human", """TAREA: {task}
            RESPUESTA:"""),
        ])

        print("LLM cargado y listo.")

    # ------------------------------------------------------------------ #
    # MÉTODOS PRINCIPALES
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # MÉTODO 1: CREA LA CADENA (UNA VEZ)
    # ------------------------------------------------------------------ #
    def create_chain(self, vector_db, k: int = 1, **search_kwargs):
        """
        Crea una cadena RAG reutilizable.
        Usa 'task' como query para el retriever.
        """
        retriever = vector_db.get_retriever(k=k, **search_kwargs)

        return (
            {
                # 1. Pasa el input completo
                "input": RunnablePassthrough(),

                # 2. Extrae 'task' para el retriever
                "context": lambda x: retriever.invoke(x["task"]),

                # 3. Pasa 'task' y 'visual_context' al prompt
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
        task: str,
        visual_context: str,
        chain  # ← Cadena pre-creada con create_chain()
    ) -> str:
        """
        Pregunta usando una cadena ya construida.
        """
        return chain.invoke({
            "task": task,
            "visual_context": visual_context
        })
    
    def health_check(self) -> Dict[str, Any]:
        """Verificación rápida del LLM."""
        return {
            "model_id": self.model_id,
            "device": next(self.model.parameters()).device,
            "max_new_tokens": self.max_new_tokens,
            "status": "healthy"
        }