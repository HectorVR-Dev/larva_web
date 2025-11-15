# test.py
from db_handler import DBHandler
from local_llm_handler import LLMHandler

# 1. Carga DB y LLM
db = DBHandler()
llm = LLMHandler()

# 2. CREA LA CADENA UNA VEZ
chain = llm.create_chain(db, k=2)

# 3. PREGUNTAS DINÁMICAS (rápidas)
print(llm.ask(
    task="¿Qué combustible usa el camión?",
    visual_context="Camión amarillo",
    chain=chain
))

print(llm.ask(
    task="¿A que familia pertenece el perro?",
    visual_context="perro bulldog",
    chain=chain
))