import asyncio
import socketio
from aiohttp import web
import zmq
import zmq.asyncio
import uuid
import json
from datetime import datetime

# Tus imports
from db_handler import DBHandler
from API_llm_handler import OpenRouterLLMHandler as LLMHandler

# --- 1. CONFIGURACIÓN ZMQ (Backend) ---
IPC_TRIGGER = "ipc:///tmp/zmq_sockets/trigger_webrtc.ipc"
IPC_RESULT = "ipc:///tmp/zmq_sockets/result_llm.ipc"

# Contexto ZMQ Asíncrono (Vital para no bloquear el loop mientras esperamos a DeepStream)
zmq_ctx = zmq.asyncio.Context()
zmq_sockets = {}

def setup_zmq():
    # Enviar orden a WebRTC
    push = zmq_ctx.socket(zmq.PUSH)
    push.connect(IPC_TRIGGER)
    # Recibir respuesta de DeepStream
    pull = zmq_ctx.socket(zmq.PULL)
    pull.bind(IPC_RESULT)
    
    zmq_sockets['push'] = push
    zmq_sockets['pull'] = pull
    print("🔗 ZMQ Backend conectado y listo.")

# --- 2. CARGA DE RECURSOS ---
db = DBHandler()
llm = LLMHandler(model="nvidia/nemotron-nano-12b-v2-vl:free",
                 vectorstore=db)

# Servidor Socket.IO
# ping_timeout alto para dar margen si la red está lenta, 
# pero el executor evitará que dependamos de esto.
sio = socketio.AsyncServer(async_mode='aiohttp', ping_timeout=60, cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

active_sessions = {}

# --- 3. HELPER: INFERENCIA VISUAL ---
async def get_visual_context(sid):
    """
    Gestiona el ciclo de petición de visión de forma lineal
    pero no bloqueante para el servidor.
    """
    request_id = str(uuid.uuid4())
    print(f"👁️ [{sid}] Solicitando visión ID: {request_id}")

    try:
        # 1. Disparar cámara (Rápido)
        await zmq_sockets['push'].send_json({"action": "CAPTURE", "id": request_id})
        
        # 2. Esperar resultado (Lento - DeepStream)
        # Usamos wait_for para no quedarnos colgados eternamente si falla la cámara
        msg = await asyncio.wait_for(zmq_sockets['pull'].recv_json(), timeout=20.0)
        print(f"👁️ [{sid}] Visión recibida para ID: {request_id}: {msg}")
        if msg.get('id') == request_id:
            return msg.get('detections', [])
        return None

    except asyncio.TimeoutError:
        print(f"⚠️ [{sid}] Timeout esperando visión.")
        return None
    except Exception as e:
        print(f"❌ [{sid}] Error visión: {e}")
        return None

# --- 4. EVENTOS SOCKET.IO ---

@sio.event
async def connect(sid, environ):
    print(f"✅ Cliente conectado: {sid}")
    active_sessions[sid] = {'connected_at': datetime.now()}

@sio.event
async def disconnect(sid):
    print(f"❌ Cliente desconectado: {sid}")
    if sid in active_sessions: del active_sessions[sid]

@sio.event
async def message(sid, data):
    """
    Manejador principal. Es 'async', por lo que podemos usar 'await'
    para pausar esta función sin detener el servidor.
    """
    print(f"\n📨 Mensaje de {sid}")
    
    messages = data.get('messages', [])
    message_id = data.get('messageId')
    vision_enabled = data.get('vision_enabled', False) # Boolean desde cliente
    print(f"   Mensajes recibidos: {len(messages)} | Visión: {vision_enabled}")
    
    visual_context = None

    # PASO 1: Obtener contexto visual (Si se requiere)
    if vision_enabled:
        # Aquí 'await' pausa ESTA función, pero el servidor sigue vivo (pings ok)
        visual_context = await get_visual_context(sid)
        print(f"   Contexto visual obtenido: {visual_context}")

    # PASO 2: Consultar LLM
    user_query = messages[-1]['content']
    print(f"🤖 Consultando LLM: '{user_query}'...")

    # IMPORTANTE: run_in_executor
    # Aunque la lógica es lineal, envolvemos la llamada al LLM en un hilo
    # para evitar que el cálculo de vectores congele el heartbeat de socketio.
    loop = asyncio.get_running_loop()
    
    try:
        resp = await loop.run_in_executor(None, lambda: llm.ask(
            task=user_query,
            visual_context=visual_context,
            score_threshold=20,
            k=5
        ))
    except Exception as e:
        resp = f"Error procesando solicitud: {str(e)}"
        print(f"❌ Error LLM: {e}")

    # PASO 3: Responder
    # Ya tenemos la respuesta en 'resp', enviamos al cliente.
    print(f"📤 Enviando respuesta...")
    print(resp)
    
    await sio.emit('response_chunk', {'chunk': resp, 'messageId': message_id}, room=sid)
    await sio.emit('response_complete', {'messageId': message_id}, room=sid)

# --- 5. INICIO ---

async def init_app():
    setup_zmq()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8005) # 0.0.0.0 para acceso externo
    print("🚀 Backend LLM + Visión iniciado en puerto 8005")
    await site.start()
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(init_app())
    except KeyboardInterrupt:
        pass