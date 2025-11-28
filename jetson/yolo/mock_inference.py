import zmq
import time
import json
import cv2
import numpy as np
import os # Importado para manejo de rutas si fuera necesario

# --- CONFIGURACIÓN ---
# Rutas IPC (Deben ser IDÉNTICAS a las del WebRTC y Backend)
IPC_INPUT = "ipc:///tmp/zmq_sockets/input_deepstream.ipc"  # Recibimos frames aquí
IPC_OUTPUT = "ipc:///tmp/zmq_sockets/result_llm.ipc"       # Enviamos resultados aquí

# Respuesta MOCK que quieres probar (Modifica esto a tu gusto)
MOCK_DETECTIONS = [["trichuris_egg", 0.95]]

def main():
    context = zmq.Context()

    # 1. Socket de ENTRADA (Recibe del WebRTC)
    try:
        receiver = context.socket(zmq.PULL)
        receiver.bind(IPC_INPUT)
        print(f"✅ Escuchando frames en: {IPC_INPUT}")
    except zmq.ZMQError as e:
        print(f"❌ Error al hacer bind en {IPC_INPUT}: {e}")
        print("   -> Asegúrate de que no haya otro proceso (o el docker real) corriendo.")
        return

    # 2. Socket de SALIDA (Envía al LLM)
    sender = context.socket(zmq.PUSH)
    sender.connect(IPC_OUTPUT)
    print(f"🔗 Conectado para enviar respuestas a: {IPC_OUTPUT}")

    print("\n🧠 [MOCK DEEPSTREAM] Listo y esperando imágenes...")
    print("-" * 40)

    while True:
        try:
            # --- A. Recibir Datos (Multipart: Metadata + Imagen) ---
            metadata = receiver.recv_json()
            image_bytes = receiver.recv()

            request_id = metadata.get('id', 'unknown')
            
            print(f"📥 Frame recibido! ID: {request_id}")

            # --- B. Validar Integridad de la Imagen ---
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                print("   ⚠️ Error: Se recibieron bytes, pero no es una imagen válida.")
                continue
            
            h, w, _ = frame.shape
            print(f"   📸 Imagen decodificada correctamente: {w}x{h} px")

            # --- NUEVO: GUARDAR IMAGEN EN DISCO ---
            # Guardamos la imagen para inspección visual
            filename = f"data/test_received_{request_id}.jpg"
            cv2.imwrite(filename, frame)
            print(f"   💾 [DEBUG] Imagen guardada en disco: {filename}")
            # --------------------------------------

            # --- C. Simular Inferencia (Latencia) ---
            print("   ⚙️  Procesando (simulando GPU)...")
            time.sleep(0.5) 

            # --- D. Enviar Respuesta ---
            response = {
                "id": request_id,
                "detections": MOCK_DETECTIONS, 
                "inference_time": 0.5
            }
            
            sender.send_json(response)
            print(f"📤 Respuesta enviada al LLM para ID: {request_id}")
            print("-" * 40)

        except KeyboardInterrupt:
            print("\n🛑 Deteniendo Mock...")
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    main()