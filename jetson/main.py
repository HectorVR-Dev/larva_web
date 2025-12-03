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
# 1. CONFIGURACIÓN TRITON (HTTP DIRECTO)
# ==========================================
TRITON_URL = "localhost:8000"
MODEL_NAME = "trichuris_yolon11_of"
INPUT_NAME = "images"
OUTPUT_NAME = "output0"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.4

# Inicializamos el cliente Triton una sola vez
try:
    triton_client = httpclient.InferenceServerClient(url=TRITON_URL)
    if not triton_client.is_server_live():
        print("⚠️ ADVERTENCIA: Triton no parece estar corriendo en localhost:8000")
    else:
        print(f"🧠 Conectado directamente a Triton: {TRITON_URL}")
except Exception as e:
    print(f"❌ Error conectando a Triton: {e}")
    triton_client = None

# Mapa de clases (Ajusta según tu modelo)
CLASS_MAP = {
    0: "trichuris_egg",
    1: "trichuris_larva"
}

# ==========================================
# 2. CONFIGURACIÓN ZMQ
# ==========================================
ctx = zmq.Context()

# Socket A: TRIGGER (El LLM nos pide una foto por aquí)
zmq_trigger = ctx.socket(zmq.PULL)
zmq_trigger.bind("ipc:///tmp/zmq_sockets/trigger_webrtc.ipc")

# Socket B: RESPUESTA (Enviamos el JSON con detecciones al LLM)
zmq_sender = ctx.socket(zmq.PUSH)
zmq_sender.connect("ipc:///tmp/zmq_sockets/result_llm.ipc")

zmq_poller = zmq.Poller()
zmq_poller.register(zmq_trigger, zmq.POLLIN)

# ==========================================
# 3. EXECUTORS (HILOS DE FONDO)
# ==========================================
# Para motores (serializado)
motor_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
# Para INFERENCIA (HTTP es bloqueante, así que va aquí para no frenar el video)
inference_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ==========================================
# 4. HARDWARE Y MOTORES
# ==========================================
print("🔌 Inicializando hardware...")
#pcf = ctrl.PCF8574_Manager(7, 0x20)
motorY = ctrl.StepMotor([7,11,13,15], fc=31, dir_orig=-1)
motorX = ctrl.StepMotor([19,21,23,29], fc=33, dir_orig=-1)
motorZ = None  # ctrl.StepMotor_I2C(pcf)
motorFitZ = ctrl.StepMotor([24,26,32,36])
motorLente = ctrl.StepMotor([12,16,18,22])
light = None #ctrl.PotenciometerX9C(pcf)

comand_list = {
    'y_R':  lambda: motorY.step(10, 1),
    'y_L':  lambda: motorY.step(10, -1),
    'x_R':  lambda: motorX.step(10, 1),
    'x_L':  lambda: motorX.step(10, -1),
    'z_R':  lambda: motorZ,#.step(10, 1),
    'z_L':  lambda: motorZ,#.step(10, -1),
    'zf_R': lambda: motorFitZ.step(20, 1),
    'zf_L': lambda: motorFitZ.step(20, -1),
    '1':    lambda: light,#.set_position(80),
    '2':    lambda: light,#.set_position(90),
    '3':    lambda: light,#.set_position(100),
}

async def ejecutar_motor_async(comand):
    funcion = comand_list.get(comand)
    if funcion:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(motor_executor, funcion)

# ==========================================
# 5. FUNCIONES DE INFERENCIA (CORREN EN HILO)
# ==========================================
def task_run_inference(frame_bgr, request_id):
    """
    Esta función corre en un hilo separado.
    Hace: Preproceso -> HTTP a Triton -> NMS -> Envía ZMQ al LLM
    """
    if triton_client is None:
        print("❌ No hay conexión con Triton")
        return

    try:
        start_t = time.time()

        # --- A. Preprocesamiento (FP32) ---
        img_resized = cv2.resize(frame_bgr, (640, 640))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_t = np.transpose(img_norm, (2, 0, 1))
        input_data = np.expand_dims(img_t, axis=0)

        # --- B. Llamada HTTP a Triton ---
        inputs = httpclient.InferInput(INPUT_NAME, input_data.shape, "FP32")
        inputs.set_data_from_numpy(input_data)
        outputs = httpclient.InferRequestedOutput(OUTPUT_NAME)

        response = triton_client.infer(model_name=MODEL_NAME, inputs=[inputs], outputs=[outputs])
        result = response.as_numpy(OUTPUT_NAME) # [1, 6, 8400]

        # --- C. Post-procesamiento (NMS) ---
        predictions = result[0].T
        boxes = []
        scores = []
        class_ids = []

        for row in predictions:
            classes_scores = row[4:] 
            max_score = np.max(classes_scores)
            if max_score > CONF_THRESHOLD:
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                left = int(cx - w/2)
                top = int(cy - h/2)
                width = int(w)
                height = int(h)
                boxes.append([left, top, width, height])
                scores.append(float(max_score))
                class_ids.append(np.argmax(classes_scores))

        indices = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
        
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                c_id = class_ids[i]
                c_name = CLASS_MAP.get(c_id, f"class_{c_id}")
                conf = round(scores[i], 4)
                detections.append([c_name, conf])

        elapsed = time.time() - start_t

        # --- D. Enviar Respuesta al LLM por ZMQ ---
        final_response = {
            "id": request_id,
            "detections": detections,
            "inference_time": elapsed
        }
        zmq_sender.send_json(final_response)
        
        log_msg = f"📤 ID: {request_id} | Time: {elapsed:.3f}s | Objs: {len(detections)}"
        print(log_msg)

    except Exception as e:
        print(f"❌ Error en inferencia: {e}")

# ==========================================
# 6. WEBRTC & SOCKETIO
# ==========================================
if len(sys.argv) > 1:
    ip = sys.argv[1]
else:
    ip = "0.0.0.0"

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
        
        if not self.cap.isOpened():
            raise RuntimeError("❌ Error Cámara")
        self._start = time.time()  
        print("🔥 Cámara iniciada")
    
    async def recv(self):
        loop = asyncio.get_running_loop()
        
        # 1. Captura (No bloqueante)
        ret, frame = await loop.run_in_executor(None, self.cap.read)
        if not ret: return None
        
        # 2. Revisar Trigger ZMQ (Timeout=0 para no bloquear video)
        socks = dict(zmq_poller.poll(timeout=0))
        
        if zmq_trigger in socks and socks[zmq_trigger] == zmq.POLLIN:
            try:
                msg = zmq_trigger.recv_json(flags=zmq.NOBLOCK)
                req_id = msg.get('id', 'unknown')
                print(f"📸 [TRIGGER] Procesando ID: {req_id}")

                # 3. Lanzar Inferencia en hilo de fondo
                # Usamos frame.copy() para que WebRTC no corrompa los datos mientras se procesan
                loop.run_in_executor(inference_executor, task_run_inference, frame.copy(), req_id)
                
            except zmq.ZMQError as e:
                print(f"⚠️ Error ZMQ: {e}")

        # 4. Enviar a WebRTC
        frame_yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        video_frame = VideoFrame.from_ndarray(frame_yuv, format="yuv420p")
        now = time.time()
        video_frame.pts = int((now - self._start) * 90000)
        video_frame.time_base = Fraction(1, 90000)
    
        return video_frame
    
    def __del__(self):
        if self.cap.isOpened(): self.cap.release()

# --- CONTROL WEBRTC ---
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
    if pc:
        await pc.restartIce()
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await sio.emit("offer", {"offer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}, "room": ROOM_ID, "jetson": True}, namespace='/')

def on_control_message(msg):
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
        asyncio.run(main())
    except KeyboardInterrupt:
        pass