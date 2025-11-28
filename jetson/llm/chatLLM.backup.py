# test_websocket_server.py
import asyncio
import socketio
from aiohttp import web
import json
from datetime import datetime

from db_handler import DBHandler
#from local_llm_handler import LLMHandler
from API_llm_handler import OpenRouterLLMHandler as LLMHandler


# 1. Carga DB y LLM
db = DBHandler()

llm = LLMHandler(vectorstore=db)


# Crear servidor Socket.IO
sio = socketio.AsyncServer(
    cors_allowed_origins='*',
    async_mode='aiohttp'
)
app = web.Application()
sio.attach(app)

# Almacenar sesiones activas
active_sessions = {}

@sio.event
async def connect(sid, environ):
    print(f"\n✅ Cliente conectado: {sid}")
    active_sessions[sid] = {'connected_at': datetime.now()}

@sio.event
async def disconnect(sid):
    print(f"\n❌ Cliente desconectado: {sid}")
    if sid in active_sessions:
        del active_sessions[sid]

@sio.event
async def message(sid, data):
    print(f"\n📨 Mensaje recibido de {sid}:")
    print("-" * 50)
    
    messages = data.get('messages', [])
    message_id = data.get('messageId')

    # Procesar la pregunta y obtener respuesta
    global resp
    resp = llm.ask(
        task=messages[-1]['content'],
        visual_context=[["trichuris_egg", 0.95]], #formato de detecciones [["trichuris_egg", 0.95]]
        score_threshold=20,
        k=5
    )

    print("Answer Model:")
    print(resp)
    print("-" * 50)

    # Mostrar conversación
    for msg in messages:
        role = "🤖 Bot" if msg['role'] == 'assistant' else "👤 Usuario"
        print(f"{role}: {msg['content']}")
    
    print("-" * 50)
    
    # Iniciar tarea para responder
    asyncio.create_task(handle_response(sid, message_id))

async def handle_response(sid, message_id):
    """Envía la respuesta al cliente en chunks"""
    try:
        await sio.emit('response_chunk', {
            'chunk': resp,
            'messageId': message_id
        }, room=sid)
        
        await sio.emit('response_complete', {
            'messageId': message_id
        }, room=sid)
        print("✅ Respuesta enviada")
            
    except Exception as e:
        print(f"❌ Error al enviar: {e}")
        await sio.emit('response_error', {
            'error': str(e),
            'messageId': message_id
        }, room=sid)

async def status_monitor():
    """Muestra el estado del servidor cada 30 segundos"""
    while True:
        await asyncio.sleep(30)
        if active_sessions:
            print(f"\n📊 Sesiones activas: {len(active_sessions)}")

async def init_app():
    """Inicializa la aplicación y el monitor de estado"""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '192.168.55.1', 8000)
    
    print("🚀 Servidor WebSocket de prueba iniciado")
    print("📡 Escuchando en http://192.168.55.1:8000")
    print("-" * 50)
    
    await site.start()
    
    # Ahora sí podemos crear la tarea del monitor
    asyncio.create_task(status_monitor())
    
    # Mantener el servidor ejecutándose
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(init_app())