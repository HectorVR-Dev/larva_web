import zmq
import time
import json
import cv2
import numpy as np
import tritonclient.http as httpclient

# --- CONFIGURACIÓN ZMQ ---
IPC_INPUT = "ipc:///tmp/zmq_sockets/input_deepstream.ipc"
IPC_OUTPUT = "ipc:///tmp/zmq_sockets/result_llm.ipc"

# --- CONFIGURACIÓN TRITON ---
TRITON_URL = "localhost:8000"
MODEL_NAME = "trichuris_yolon11_of"
INPUT_NAME = "images"
OUTPUT_NAME = "output0"
CONF_THRESHOLD = 0.5   # Solo detecciones > 50%
IOU_THRESHOLD = 0.4    # Para eliminar cajas repetidas (NMS)

# Mapa de Clases (Ajusta los nombres para que coincidan con lo que espera tu app)
CLASS_MAP = {
    0: "trichuris_egg",  # Ajusta según tu entrenamiento real
    1: "Trichuris_larva"
}

def preprocess_frame(frame):
    """
    Convierte el frame de OpenCV (BGR) al tensor FP32 para Triton.
    """
    # 1. Resize a 640x640
    img_resized = cv2.resize(frame, (640, 640))
    
    # 2. BGR a RGB
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    
    # 3. Normalizar (0-1) y float32
    img_norm = img_rgb.astype(np.float32) / 255.0
    
    # 4. Transponer (HWC -> CHW)
    img_t = np.transpose(img_norm, (2, 0, 1))
    
    # 5. Expandir dims para Batch (1, 3, 640, 640)
    img_batch = np.expand_dims(img_t, axis=0)
    
    return img_batch

def run_inference(client, frame):
    """
    Ejecuta todo el ciclo: Preproceso -> Inferencia -> NMS -> Formato Lista
    """
    # --- 1. Preprocesamiento ---
    input_data = preprocess_frame(frame)
    
    # Configurar Tensores
    inputs = httpclient.InferInput(INPUT_NAME, input_data.shape, "FP32")
    inputs.set_data_from_numpy(input_data)
    outputs = httpclient.InferRequestedOutput(OUTPUT_NAME)
    
    # --- 2. Inferencia en Triton ---
    start_time = time.time()
    response = client.infer(model_name=MODEL_NAME, inputs=[inputs], outputs=[outputs])
    inference_time = time.time() - start_time
    
    result = response.as_numpy(OUTPUT_NAME)
    
    # --- 3. Post-procesamiento (NMS) ---
    # La salida es [1, 6, 8400] -> Transponemos a [8400, 6]
    predictions = result[0].T
    
    boxes = []
    scores = []
    class_ids = []
    
    # Filtrado inicial por confianza
    for row in predictions:
        classes_scores = row[4:] 
        max_score = np.max(classes_scores)
        
        if max_score > CONF_THRESHOLD:
            # Extraemos coordenadas solo para el NMS (aunque no se envíen)
            cx, cy, w, h = row[0], row[1], row[2], row[3]
            
            # NMS requiere formato (left, top, w, h) en enteros
            left = int(cx - w/2)
            top = int(cy - h/2)
            width = int(w)
            height = int(h)
            
            boxes.append([left, top, width, height])
            scores.append(float(max_score))
            class_ids.append(np.argmax(classes_scores))
            
    # Aplicar NMS (Elimina duplicados)
    indices = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
    
    final_detections = []
    
    if len(indices) > 0:
        for i in indices.flatten():
            score = scores[i]
            class_id = class_ids[i]
            class_name = CLASS_MAP.get(class_id, "unknown")
            
            # Formato solicitado por tu mock: ["nombre", score]
            final_detections.append([class_name, round(score, 4)])
            
    return final_detections, inference_time

def main():
    # --- INICIALIZACIÓN ZMQ ---
    context = zmq.Context()
    
    try:
        receiver = context.socket(zmq.PULL)
        receiver.bind(IPC_INPUT)
        print(f"✅ ZMQ: Escuchando en {IPC_INPUT}")
    except zmq.ZMQError as e:
        print(f"❌ Error ZMQ bind: {e}")
        return

    sender = context.socket(zmq.PUSH)
    sender.connect(IPC_OUTPUT)
    print(f"✅ ZMQ: Conectado a {IPC_OUTPUT}")

    # --- INICIALIZACIÓN TRITON ---
    print("⏳ Conectando a Triton Inference Server...")
    try:
        triton_client = httpclient.InferenceServerClient(url=TRITON_URL)
        if not triton_client.is_server_live():
            print("❌ Error: El servidor Triton no responde. ¿Está corriendo el Docker?")
            return
        print(f"🧠 Triton Conectado en {TRITON_URL}")
        # Carga dummy para "calentar" el modelo (opcional)
        # triton_client.get_model_metadata(MODEL_NAME) 
    except Exception as e:
        print(f"❌ Error al conectar con Triton: {e}")
        return

    print("-" * 40)
    print("🚀 SERVICIO DE INFERENCIA LISTO")

    while True:
        try:
            # --- A. Recibir Datos ---
            metadata = receiver.recv_json()
            image_bytes = receiver.recv()
            request_id = metadata.get('id', 'unknown')
            
            # --- B. Decodificar Imagen ---
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                print("⚠️ Frame vacío recibido.")
                continue

            # --- C. Inferencia REAL ---
            # print(f"⚙️ Procesando ID: {request_id}...")
            detections, inf_time = run_inference(triton_client, frame)

            # --- D. Enviar Respuesta ---
            response = {
                "id": request_id,
                "detections": detections,  # Ejemplo: [["trichuris_egg", 0.95], ["larva", 0.88]]
                "inference_time": round(inf_time, 4)
            }
            
            sender.send_json(response)
            
            # Log ligero para no saturar consola
            if len(detections) > 0:
                print(f"📤 ID: {request_id} | Tiempo: {inf_time:.3f}s | Detecciones: {detections}")
            else:
                print(f"📤 ID: {request_id} | Tiempo: {inf_time:.3f}s | Sin detecciones")

        except KeyboardInterrupt:
            print("\n🛑 Deteniendo servicio...")
            break
        except Exception as e:
            print(f"❌ Error en el bucle principal: {e}")
            # Pequeña pausa para no saturar CPU si hay error persistente
            time.sleep(0.1)

if __name__ == "__main__":
    main()