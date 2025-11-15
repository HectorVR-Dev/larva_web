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
    Manejador para modelos remotos (OpenRouter) con el MISMO prompt, inputs
    y estructura que el manejador local con Qwen.
    """

    def __init__(
        self,
        model: str = "nvidia/nemotron-nano-12b-v2-vl:free",
        temperature: float = 0.1,
        top_p: float = 0.7,
        repetition_penalty: float = 1.2,
        verbose: bool = False,
    ):
        self.model_name = model
        self.verbose = verbose

        api_key = getenv("OPENROUTER_API_KEY")
        if api_key is None:
            raise ValueError("Falta OPENROUTER_API_KEY en .env")

        # LLM remoto equivalente al HuggingFacePipeline local
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

        # Mismo prompt del manejador local (copia textual)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un asistente con acceso a base de datos Chroma.
            CONFIGURACIÓN:
            - Idioma: Español
            - Modo: Análisis determinístico
            
            CAPACIDADES:
            1. VISUAL: Puedes ver y analizar objetos en contexto visual
            2. CHROMA: Es tu fuente principal de información textual
            3. SÍNTESIS: Debes combinar ambas fuentes para responder
            
            REGLAS ESTRICTAS:
            1. Solo usa información del CONTEXTO_VISUAL y CONTEXTO_CHROMA
            2. Respuesta clara y concisa en español
            3. La respuesta solo debe responder a la TAREA dada
            4. Si no tienes suficiente información, responde "No lo sé"
            6. No menciones el proceso de obtención de la información
            7. El CONTEXTO_VISUAL te dice a que te debes referir y buscar en CHROMA
            8. El CONTEXTO_CHROMA debe ser pertinente a la TAREA para poder usarlo
            9. Si la TAREA no está relacionada con el CONTEXTO_VISUAL y CONTEXTO_CHROMA, responde "No lo sé"
             
            CONTEXTO_VISUAL:
            {visual_context}
            
             INSTRUCCIONES DE PROCESAMIENTO:
            1. Identifica el contexto_visual
            2. Busca información en contexto_chroma
            3. Sintetiza una respuesta coherente"""),
            ("human", """TAREA: {task}
            
            CONTEXTO_CHROMA:
            {context}
             
            RESPUESTA:"""),
        ])

        print(f"✓ Handler remoto cargado: {model}")

    # ----------------------------------------------------------- #
    # CREAR LA CADENA (equivalente al local)
    # ----------------------------------------------------------- #
    def create_chain(self, vector_db, k: int = 1, **search_kwargs):
        self.retriever = vector_db.get_retriever(k=k, **search_kwargs)

        return (
            {
                "input": RunnablePassthrough(),
                "context": lambda x: self.retriever.invoke(x["task"]),
                "task": lambda x: x["task"],
                "visual_context": lambda x: x["visual_context"],
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    # ----------------------------------------------------------- #
    # EJECUTAR UNA CONSULTA
    # ----------------------------------------------------------- #
    def ask(self, task: str, visual_context: str, chain):
        raw_input = {
            "task": task,
            "visual_context": visual_context
        }

        if self.verbose:
            print("\n================= DEBUG LLM HANDLER =================")

            print("\n[1] INPUTS")
            print(f"• task: {task}")
            print(f"• visual_context: {visual_context}")

            # 1. Ejecutar el retriever REAL
            try:
                context = self.retriever.invoke(task)
            except:
                context = ""

            print("\n[2] CONTEXTO CHROMA RECUPERADO")
            print(context if context else "(sin contexto)")

            # 2. Renderizar prompt con contexto real
            rendered_prompt = self.prompt.format(
                task=task,
                visual_context=visual_context,
                context=context,
            )

            print("\n[3] PROMPT FINAL ENVIADO AL MODELO")
            print(rendered_prompt)

            print("\n=====================================================\n")

        return chain.invoke(raw_input)


    # ----------------------------------------------------------- #
    # HEALTH CHECK
    # ----------------------------------------------------------- #
    def health_check(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "provider": "OpenRouter",
            "status": "healthy",
        }
