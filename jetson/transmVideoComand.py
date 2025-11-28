import asyncio
import cv2
import socketio
import time
import sys
import zmq
import numpy as np
import concurrent.futures
from fractions import Fraction
import urllib3
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, MediaStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.sdp import candidate_from_sdp
from av import VideoFrame 

# Importar el módulo de control de motores
import device.microscopio as ctrl

# ==========================================
# 1. CONFIGURACIÓN ZMQ (IPC - OPTIMIZADO)
# ==========================================
# Creamos el contexto global
ctx = zmq.Context()

# Socket A: ESCUCHAR peticiones del LLM (Trigger)
# El LLM se conecta a este archivo para pedir fotos
zmq_trigger = ctx.socket(zmq.PULL)
zmq_trigger.bind("ipc:///tmp/zmq_sockets/trigger_webrtc.ipc")

# Socket B: ENVIAR frames a DeepStream (Docker)
# El Docker escucha en este archivo
zmq_sender = ctx.socket(zmq.PUSH)
zmq_sender.connect("ipc:///tmp/zmq_sockets/input_deepstream.ipc")

# Poller: Para revisar el socket A sin bloquear el video (Timeout=0)
zmq_poller = zmq.Poller()
zmq_poller.register(zmq_trigger, zmq.POLLIN)

print("✅ ZMQ IPC Configurado: Esperando triggers del LLM...")

# ==========================================
# 2. CONFIGURACIÓN MOTORES (ASÍNCRONO)
# ==========================================
# Executor para que los motores no congelen el video
# Max workers = 1 para que las órdenes se encolen y no se solapen caóticamente
motor_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

pcf = ctrl.PCF8574_Manager(7,0x20)
# --- 1. Configuración de Hardware (Tu código original) ---
print("🔌 Inicializando hardware...")
motorY = ctrl.StepMotor([7,11,13,15], fc=31 , dir_orig=-1)
motorX = ctrl.StepMotor([19,21,23,29], fc=33, dir_orig=-1)
motorZ = ctrl.StepMotor_I2C(pcf)
motorFitZ = ctrl.StepMotor([24,26,32,36])
motorLente = ctrl.StepMotor([12,16,18,22])
light = ctrl.PotenciometerX9C(pcf)

comand_list = {
    'y_R':  lambda: motorY.step(10, 1),
    'y_L':  lambda: motorY.step(10, -1),
    'x_R':  lambda: motorX.step(10, 1),
    'x_L':  lambda: motorX.step(10, -1),
    'z_R':  lambda: motorZ.step(10, 1),
    'z_L':  lambda: motorZ.step(10, -1),
    'zf_R': lambda: motorFitZ.step(20, 1),
    'zf_L': lambda: motorFitZ.step(20, -1),
    '1':    lambda: light.set_position(80),
    '2':    lambda: light.set_position(90),
    '3':    lambda: light.set_position(100),
}

async def ejecutar_motor_async(comand):
    """
    Envía la tarea al ThreadPool y espera a que termine
    sin bloquear el Event Loop principal.
    """
    #cmd_clear = str(comand).strip().strip("'\"")
    funcion = comand_list.get(comand)
    
    if funcion:
        loop = asyncio.get_running_loop()
        #print(f"\n   ⚙️ [Hilo Secundario] Ejecutando comando: {comand}")
        #start_time = time.time()
        
        await loop.run_in_executor(motor_executor, funcion)
    
        #duration = time.time() - start_time
        #print(f"   ✅ [Hilo Secundario] Motor {comand} terminó en {duration:.2f}s")
    else:
        #print(f"   ❓ comand no reconocido: {comand}")
        pass


# ==========================================
# 3. CONFIGURACIÓN WEBRTC Y SOCKETIO
# ==========================================

if len(sys.argv) > 1:
    ip = sys.argv[1]
else:
    ip = "192.168.55.1" # IP por defecto si no se pasa argumento

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sio = socketio.AsyncClient(
    reconnection_attempts=5,
    reconnection_delay=0.1,        
    reconnection_delay_max=1.0,     
    randomization_factor=0.5
)
ROOM_ID = "jetson-room"
pc = None 

class SignalingNamespace(socketio.AsyncClientNamespace):
    def on_connect(self):
        print("✅ Conectado al servidor de señalización (namespace /)")
        
    def on_disconnect(self):
        print("ℹ️ Desconexión transitoria del servidor")

sio.register_namespace(SignalingNamespace('/'))

class VideoTrack(MediaStreamTrack):
    kind = "video"
    
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.cap.isOpened():
            raise RuntimeError("Error al abrir la cámara")
        self._start = time.time()  
        print("🔥 Cámara inicializada correctamente")
    
    async def recv(self):
        """
        Ciclo principal de captura.
        Aquí es donde integramos el chequeo ZMQ
        """
        loop = asyncio.get_running_loop()
        
        # 1. Capturar frame (En executor para no bloquear IO)
        ret, frame = await loop.run_in_executor(None, self.cap.read)
        
        if not ret:
            print("🚨 Error capturando frame")
            return None
        
        # --- ZMQ LOGIC (NON-BLOCKING) ---
        # Verificamos si el LLM pidió una foto justo ahora
        # timeout=0 es CRÍTICO para que el video no se trabe
        socks = dict(zmq_poller.poll(timeout=0))
        
        if zmq_trigger in socks and socks[zmq_trigger] == zmq.POLLIN:
            try:
                # Leemos la petición del LLM
                msg = zmq_trigger.recv_json()
                req_id = msg.get('id', 'unknown')
                print(f"📸 [ZMQ] Solicitud LLM recibida ID: {req_id}")
                
                # Codificamos a JPG para enviar al Docker (DeepStream)
                # Usamos encode en lugar de write a disco para velocidad
                _, buffer = cv2.imencode('.jpg', frame)
                
                # Enviamos Multipart: Metadata + Bytes de Imagen
                zmq_sender.send_json({"id": req_id, "timestamp": time.time()}, flags=zmq.SNDMORE)
                zmq_sender.send(buffer)
                print(f"   -> Frame enviado a DeepStream")
                
            except zmq.ZMQError as e:
                print(f"⚠️ Error ZMQ: {e}")
        # --------------------------------
        
        # 2. Procesamiento para WebRTC (Convertir a YUV)
        # Nota: cvtColor consume CPU, pero en Orin es manejable para SD
        frame_yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        video_frame = VideoFrame.from_ndarray(frame_yuv, format="yuv420p")
        
        now = time.time()
        video_frame.pts = int((now - self._start) * 90000)
        video_frame.time_base = Fraction(1, 90000)
    
        return video_frame
    
    def __del__(self):
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()

# --- MANEJO DE SEÑALIZACIÓN (Ofertas/Respuestas) ---

@sio.on("answer", namespace='/')
async def on_answer(data):
    if pc and pc.signalingState == "have-local-offer":
        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(answer)

@sio.on("candidate", namespace='/')
async def on_candidate(data):
    candidate = candidate_from_sdp(data["candidate"])
    candidate.sdpMid = data["sdpMid"]
    candidate.sdpMLineIndex = data["sdpMLineIndex"]
    await pc.addIceCandidate(candidate)

@sio.on("renegotiate", namespace='/')
async def on_renegotiate(data):
    global pc
    print("🔄 Renegociación solicitada")
    if pc is None or pc.signalingState == "closed":
        pc = createPeerConnection()
    else:
        await pc.restartIce()
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await sio.emit("offer", {
         "offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
         "room": ROOM_ID,
         "jetson": True
    }, namespace='/')

# --- DATA CHANNEL (CONTROL MOTORES) ---

def on_control_message(msg):
    # Cuando llega un mensaje por el DataChannel de WebRTC
    # Programamos la tarea asíncrona en el loop principal
    # para no bloquear el hilo de red de aiortc
    print(f"📩 Mensaje WebRTC recibido: {msg}")
    asyncio.create_task(ejecutar_motor_async(msg))

def createPeerConnection():
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    pc_new = RTCPeerConnection(configuration=config)
    
    # Añadimos el Track de Video modificado
    pc_new.addTrack(VideoTrack())
    
    # Configurar Canal de Datos
    channel = pc_new.createDataChannel("control")
    channel.on("open", lambda: print("🟢 Canal de datos 'control' abierto"))
    channel.on("message", on_control_message)
    
    return pc_new

async def main():
    global pc
    try:
        await sio.connect(f"http://{ip}:5000", transports=["websocket"], namespaces=['/'], wait_timeout=3)
        await sio.emit("join", {"room": ROOM_ID}, namespace='/')
        
        pc = createPeerConnection()
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        await sio.emit("offer", {
            "offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
            "room": ROOM_ID,
            "jetson": True
        }, namespace='/')
        
        # Bucle infinito para mantener el script vivo
        while True:
            await asyncio.sleep(1)
            
    finally:
        await sio.disconnect()
        # Limpieza de recursos
        ctx.term()
        ctrl.liberate()
        motor_executor.shutdown(wait=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔌 Desconectando y cerrando recursos...")