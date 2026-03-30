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

# Importar cliente de Triton
import tritonclient.http as httpclient

# Importar control de motores
import device.microscopio as ctrl

# ==========================================
# 1. CONFIGURACIÓN GENERAL
# ==========================================
TRITON_URL = "localhost:8000"
MODEL_NAME = "trichuris_yolon11_of"
INPUT_NAME = "images"
OUTPUT_NAME = "output0"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.4

# Mapa de clases
CLASS_MAP = {
    0: "trichuris_egg",
    1: "trichuris_larva"
}

# ==========================================
# 2. CONFIGURACIÓN ZMQ
# ==========================================
ctx = zmq.Context()
zmq_trigger = ctx.socket(zmq.PULL)
zmq_trigger.bind("ipc:///tmp/zmq_sockets/trigger_webrtc.ipc")

zmq_sender = ctx.socket(zmq.PUSH)
zmq_sender.connect("ipc:///tmp/zmq_sockets/result_llm.ipc")

zmq_poller = zmq.Poller()
zmq_poller.register(zmq_trigger, zmq.POLLIN)

# ==========================================
# 3. EXECUTORS
# ==========================================
motor_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
inference_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ==========================================
# 4. HARDWARE
# ==========================================
print("🔌 Inicializando hardware...")
try:
    pcf = ctrl.PCF8574_Manager(7, 0x20)
    motorY = ctrl.StepMotor([7,11,13,15], fc=31, dir_orig=-1)
    motorX = ctrl.StepMotor([19,21,23,29], fc=33, dir_orig=-1)
    motorZ = ctrl.StepMotor_I2C(pcf)
    motorFitZ = ctrl.StepMotor([24,26,32,36])
    motorLente = ctrl.StepMotor([12,16,18,22])
    light = ctrl.PotenciometerX9C(pcf)
except Exception as e:
    print(f"⚠️ Error Hardware (Ignorable si es test): {e}")

comand_list = {
    'y_R':  lambda: motorY.step(10, 1),
    'y_L':  lambda: motorY.step(10, -1),
    'x_R':  lambda: motorX.step(10, 1),
    'x_L':  lambda: motorX.step(10, -1),
    'z_R':  lambda: motorZ.step(10, 1),
    'z_L':  lambda: motorZ.step(10, -1),
    'zf_R': lambda: motorFitZ.step(20, -1),
    'zf_L': lambda: motorFitZ.step(20, 1),
    '1':    lambda: light.set_position(80),
    '2':    lambda: light.set_position(90),
    '3':    lambda: light.set_position(100),
}

async def ejecutar_motor_async(comand):
    funcion = comand_list.get(comand)
    if funcion:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(motor_executor, funcion)

# ==========================================
# 5. LÓGICA DE INFERENCIA (THREAD-SAFE)
# ==========================================

def enviar_resultado_zmq(data):
    """Ejecutado por el Main Thread"""
    try:
        zmq_sender.send_json(data)
        count = len(data["detections"])
        print(f"📤 ID: {data['id']} | Time: {data['inference_time']:.3f}s | Objs: {count}")
    except Exception as e:
        print(f"❌ Error enviando ZMQ: {e}")

def task_run_inference(frame_bgr, request_id, loop):
    """
    Corre en Hilo Secundario.
    Instancia Triton AQUÍ MISMO para evitar error de Greenlet/Thread Switch.
    """
    try:
        start_t = time.time()
        
        # 1. Crear cliente local al hilo (ESTO SOLUCIONA EL ERROR GREENLET)
        client = httpclient.InferenceServerClient(url=TRITON_URL)
        
        # 2. Preprocesamiento
        img_resized = cv2.resize(frame_bgr, (640, 640))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_t = np.transpose(img_norm, (2, 0, 1))
        input_data = np.expand_dims(img_t, axis=0)

        # 3. Inferencia
        inputs = httpclient.InferInput(INPUT_NAME, input_data.shape, "FP32")
        inputs.set_data_from_numpy(input_data)
        outputs = httpclient.InferRequestedOutput(OUTPUT_NAME)

        response = client.infer(model_name=MODEL_NAME, inputs=[inputs], outputs=[outputs])
        result = response.as_numpy(OUTPUT_NAME)

        # 4. Post-procesamiento (NMS)
        predictions = result[0].T
        boxes = []
        scores = []
        class_ids = []

        for row in predictions:
            classes_scores = row[4:] 
            max_score = np.max(classes_scores)
            if max_score > CONF_THRESHOLD:
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                boxes.append([int(cx - w/2), int(cy - h/2), int(w), int(h)])
                scores.append(float(max_score))
                class_ids.append(np.argmax(classes_scores))

        indices = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
        
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                c_name = CLASS_MAP.get(class_ids[i], "unknown")
                detections.append([c_name, round(scores[i], 4)])

        elapsed = time.time() - start_t

        # 5. Volver al Main Thread para enviar ZMQ
        final_response = {
            "id": request_id,
            "detections": detections,
            "inference_time": elapsed
        }
        
        loop.call_soon_threadsafe(enviar_resultado_zmq, final_response)
        # Cerramos el cliente explícitamente por higiene
        client.close()

    except Exception as e:
        print(f"❌ Error en hilo de inferencia: {e}")

# ==========================================
# 6. WEBRTC
# ==========================================
if len(sys.argv) > 1: ip = sys.argv[1]
else: ip = "192.168.55.1"

urllib3.disable_warnings()
sio = socketio.AsyncClient(reconnection_attempts=5, reconnection_delay=0.1)
ROOM_ID = "jetson-room"
pc = None 

class SignalingNamespace(socketio.AsyncClientNamespace):
    def on_connect(self): print("✅ Conectado a Señalización")
    def on_disconnect(self): print("ℹ️ Desconectado")
sio.register_namespace(SignalingNamespace('/'))

class VideoTrack(MediaStreamTrack):
    kind = "video"
    
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not self.cap.isOpened(): raise RuntimeError("❌ Error Cámara")
        self._start = time.time()
        print("🔥 Cámara iniciada")
    
    async def recv(self):
        loop = asyncio.get_running_loop()
        
        ret, frame = await loop.run_in_executor(None, self.cap.read)
        if not ret: return None
        
        # --- TRIGGER ZMQ ---
        socks = dict(zmq_poller.poll(timeout=0))
        if zmq_trigger in socks and socks[zmq_trigger] == zmq.POLLIN:
            try:
                msg = zmq_trigger.recv_json(flags=zmq.NOBLOCK)
                req_id = msg.get('id', 'unknown')
                print(f"📸 [TRIGGER] Procesando ID: {req_id}")

                # Lanzamos al hilo secundario pasando el 'loop' y una COPIA del frame
                loop.run_in_executor(inference_executor, task_run_inference, frame.copy(), req_id, loop)
                
            except zmq.ZMQError as e:
                print(f"⚠️ Error ZMQ Recv: {e}")

        frame_yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        video_frame = VideoFrame.from_ndarray(frame_yuv, format="yuv420p")
        now = time.time()
        video_frame.pts = int((now - self._start) * 90000)
        video_frame.time_base = Fraction(1, 90000)
        return video_frame
    
    def __del__(self):
        if self.cap.isOpened(): self.cap.release()

# --- HANDLERS WEBRTC ---

@sio.on("answer", namespace='/')
async def on_answer(data):
    if pc and pc.signalingState == "have-local-offer":
        await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type=data["type"]))

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
    if pc:
        # CORRECCIÓN AQUÍ: 'restartIce' no existe en aiortc.
        # Se usa ice_restart=True al crear la oferta.
        offer = await pc.createOffer(ice_restart=True)
        await pc.setLocalDescription(offer)
        await sio.emit("offer", {
            "offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}, 
            "room": ROOM_ID, 
            "jetson": True
        }, namespace='/')

def on_control_message(msg):
    print(f"🎮 CMD: {msg}")
    asyncio.create_task(ejecutar_motor_async(msg))

def createPeerConnection():
    config = RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
    new_pc = RTCPeerConnection(configuration=config)
    new_pc.addTrack(VideoTrack())
    channel = new_pc.createDataChannel("control")
    channel.on("message", on_control_message)
    return new_pc

async def main():
    global pc
    try:
        await sio.connect(f"http://{ip}:5000", transports=["websocket"], namespaces=['/'])
        await sio.emit("join", {"room": ROOM_ID}, namespace='/')
        pc = createPeerConnection()
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await sio.emit("offer", {"offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}, "room": ROOM_ID, "jetson": True}, namespace='/')
        while True: await asyncio.sleep(1)
    finally:
        await sio.disconnect()
        ctx.term()
        motor_executor.shutdown(wait=False)
        inference_executor.shutdown(wait=False)

if __name__ == "__main__":
    try:
        # NOTA SOBRE PERMISOS:
        # Si ves "Could not open /dev/mem", ejecuta este script con:
        # sudo ./venv/bin/python main.py
        # O añade tu usuario al grupo gpio: sudo usermod -aG gpio $USER
        asyncio.run(main())
    except KeyboardInterrupt:
        pass