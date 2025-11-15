import React, { useRef, useState, useEffect, useCallback } from "react";
import { FaLongArrowAltLeft, FaLongArrowAltRight, FaLongArrowAltUp, FaLongArrowAltDown } from "react-icons/fa";
import { LuPower } from "react-icons/lu";
import io from "socket.io-client";

const SYSTEM_IP = import.meta.env.VITE_SYSTEM_IP || "192.168.98.102";
const SOCKET_URL = `${import.meta.env.VITE_PROTOCOL || "http"}://${SYSTEM_IP}:5000`;


const sendControlMessage = (dataChannel, msg) => {
  if (!msg || typeof msg !== "string") {
    console.warn("Mensaje inválido:", msg);
    return false;
  }

  if (dataChannel?.readyState === "open") {
    try {
      dataChannel.send(msg);
      console.log("✓ Enviado:", msg);
      return true;
    } catch (err) {
      console.error("Error enviando mensaje:", err);
      return false;
    }
  }

  console.warn("Data channel no disponible:", dataChannel?.readyState);
  return false;
};

const useSocket = () => {
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const newSocket = io(SOCKET_URL, {
      transports: ["websocket"],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      timeout: 3000
    });

    newSocket.on("connect", () => {
      console.log("✓ Socket conectado");
      setIsConnected(true);
    });

    newSocket.on("disconnect", () => {
      console.log("✗ Socket desconectado");
      setIsConnected(false);
    });

    newSocket.on("connect_error", (err) => {
      console.error("Error de conexión:", err.message);
    });

    setSocket(newSocket);

    // Cleanup al desmontar
    return () => {
      newSocket.close();
    };
  }, []);

  return { socket, isConnected };
};

export { sendControlMessage, useSocket };

//-----------------------------------------------------

const systemIp = import.meta.env.VITE_SYSTEM_IP || "192.168.98.102";
const socket = io(`http://${systemIp}:5000`, {
  transports: ["websocket"],
  timeout: 3000
});

socket.on("connect_error", (err) => {
  console.error("WebSocket connection error:", err);
});


const WebRTCComponent = ({ isNavBarVisible, isChatVisible, handleToggleChat }) => {
  const [isConnected, setIsConnected] = useState(false);
  const videoRef = useRef(null);
  const peerRef = useRef(null);
  const ROOM_ID = "jetson-room";
  const [dataChannel, setDataChannel] = useState(null);
  const [powerOn, setPowerOn] = useState(false);
  const [activeButton, setActiveButton] = useState(null); // Nuevo estado

  // Función para mover la cámara usando useCallback
  const handleMove = useCallback((direction) => {
    const moves = { up: "y_R", down: "y_L", left: "x_L", right: "x_R" };
    const msg = moves[direction];
    sendControlMessage(dataChannel, msg);
  }, [dataChannel]);

  // Función para zoom usando useCallback
  const handleZoom = useCallback((direction) => {
    const zooms = { in: "z_R", out: "z_L" };
    const msg = zooms[direction];
    sendControlMessage(dataChannel, msg);
  }, [dataChannel]);

  // Función para enviar comandos de power
  const handlePower = useCallback((command) => {
    // Solo se permite si la cámara está activa
    if (videoRef.current && videoRef.current.srcObject) {
      sendControlMessage(dataChannel, command);
      // Si se envía "turn on", activar botones adicionales
      if (command === "turn on") {
        setPowerOn(true);
      }
    } else {
      console.log("Cámara inactiva, no se puede enviar comando de power");
    }
  }, [dataChannel]);

  // Función para el botón principal de power
  const handleMainPower = useCallback(() => {
    if (videoRef.current && videoRef.current.srcObject) {
      if (powerOn) {
        sendControlMessage(dataChannel, "turn off");
        setPowerOn(false);
        setActiveButton(null);
      } else {
        sendControlMessage(dataChannel, "turn on");
        // Nuevo: Enviar el "1" inmediatamente al encender
        sendControlMessage(dataChannel, "1");
        setPowerOn(true);
        setActiveButton("1");
      }
    } else {
      console.log("Cámara inactiva, no se puede enviar comando de power");
    }
  }, [dataChannel, powerOn]);

  // Función para manejar selección de botones enumerados
  const handlePowerSelection = useCallback((num) => {
    setActiveButton(num);
    sendControlMessage(dataChannel, num);
  }, [dataChannel]);

  const initPeerConnection = () => {
    let candidateQueue = [];
    peerRef.current = new RTCPeerConnection({
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "turn:your-turn-server.com", username: "user", credential: "password" }
      ],
      sdpSemantics: "unified-plan",
      bundlePolicy: "max-bundle",
      rtcpMuxPolicy: "require",
    });


    peerRef.current.ondatachannel = (event) => {
      if (event.channel.label === "control") {
        setDataChannel(event.channel);
        event.channel.onopen = () => console.log("Canal de datos 'control' abierto (client)");
      }
    };

    peerRef.current.oniceconnectionstatechange = () =>
      console.log("ICE state (client):", peerRef.current.iceConnectionState);

    peerRef.current.addTransceiver("video", { direction: "recvonly" });

    peerRef.current.onicecandidate = (event) => {
      if (event.candidate) {
        socket.emit("candidate", { candidate: event.candidate, room: ROOM_ID });
      }
    };

    // Receptor: Escuchar streams entrantes
    peerRef.current.ontrack = (event) => {
      if (event.streams && event.streams[0]) {
        // Solo asignar si aún no se ha asignado el stream
        if (videoRef.current.srcObject !== event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          videoRef.current.onloadedmetadata = () => {
            videoRef.current.play().catch(err =>
              console.error("🚀 Video play() error:", err)
            );
          };
        }
      }
    };

    // Escuchar oferta del servidor
    socket.on("offer", async (offer) => {
      try {
        // Evitar procesar ofertas duplicadas
        if (
          peerRef.current.remoteDescription &&
          peerRef.current.remoteDescription.sdp === offer.sdp
        ) {
          console.log("❗ Oferta duplicada recibida; se ignora.");
          return;
        }
        // Si el estado no es "stable", reinicializar para evitar errores de negociación
        if (peerRef.current.signalingState !== "stable") {
          console.log("Signaling state not stable. Reinitializing connection.");
          peerRef.current.close();
          initPeerConnection();
        }
        await peerRef.current.setRemoteDescription(offer);
        while (candidateQueue.length > 0) {
          const pendingCandidate = candidateQueue.shift();
          await peerRef.current.addIceCandidate(new RTCIceCandidate(pendingCandidate));
        }
        const answer = await peerRef.current.createAnswer();
        await peerRef.current.setLocalDescription(answer);
        // Enviar un objeto simple en lugar del objeto RTCSessionDescription directamente
        socket.emit("answer", { answer: { sdp: answer.sdp, type: answer.type }, room: ROOM_ID });
      } catch (err) {
        console.error("Error al manejar oferta:", err);
      }
    });

    socket.on("candidate", (candidate) => {
      if (peerRef.current) {
        if (peerRef.current.remoteDescription) {
          peerRef.current.addIceCandidate(new RTCIceCandidate(candidate));
        } else {
          candidateQueue.push(candidate);
        }
      }
    });
  };

  const connect = () => {
    if (!isConnected) {
      initPeerConnection();

      socket.emit("join", { room: ROOM_ID });
      setIsConnected(true);
    }
  };

  const disconnect = () => {
    // Notify server to leave the room
    socket.emit("leave", { room: ROOM_ID });

    if (peerRef.current) {
      peerRef.current.close();
      peerRef.current = null;
    }
    setIsConnected(false);
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setPowerOn(false); // Agregado: reiniciar botones de power al desconectar
    // Eliminar listeners para evitar ofertas duplicadas al reconectar
    socket.off("offer");
    socket.off("candidate");
  };

  useEffect(() => {
    return () => {
      disconnect();
      socket.off("offer");
      socket.off("candidate");
    };
  }, []);

  return (
    <div className={`container w-screen mx-auto p-4 flex flex-col items-center bg-[var(--color-bg-primary)] ${(isNavBarVisible || isChatVisible) ? "hidden" : "block"} lg:block flex-col`}>
      <h1 className="text-3xl font-bold text-center text-blue-700"> Video Microscopio</h1>
      <div className=" flex flex-row w-full justify-center items-start mt-4">

        {/* Izquierda */}
        <div className="flex flex-col p-1 items-center space-y-2">
          <button
            onClick={handleMainPower}
            className={`p-2 rounded-full transition-transform duration-300 ease-in-out text-white text-2xl ${powerOn
              ? "bg-red-900 hover:rotate-180 hover:scale-110 "
              : "bg-red-600 hover:bg-red-700 hover:rotate-360 hover:scale-110"
              }`}
            disabled={!(videoRef.current && videoRef.current.srcObject)}
          >
            <LuPower />
          </button>

          {/* Botones adicionales mostrados solo si power está activo */}
          {powerOn && (
          <div className="flex flex-col mt-2 space-y-3">
            <button
              onClick={() => handlePowerSelection("1")}
              className={`px-3 py-1 rounded-lg text-lg transition-transform duration-300 ease-in-out ${activeButton === "1"
                ? "bg-green-600 text-white hover:scale-125"
                : "bg-green-950 text-white hover:bg-green-700 hover:scale-125"
                }`}
            >
              1
            </button>
            <button
              onClick={() => handlePowerSelection("2")}
              className={`px-3 py-1 rounded-lg text-lg transition-transform duration-300 ease-in-out ${activeButton === "2"
                ? "bg-green-600 text-white hover:scale-125"
                : "bg-green-950 text-white hover:bg-green-700 hover:scale-125"
                }`}
            >
              2
            </button>
            <button
              onClick={() => handlePowerSelection("3")}
              className={`px-3 py-1 rounded-lg text-lg transition-transform duration-300 ease-in-out ${activeButton === "3"
                ? "bg-green-600 text-white hover:scale-125"
                : "bg-green-950 text-white hover:bg-green-700 hover:scale-125"
                }`}
            >
              3
            </button>
          </div>
          )}
        </div>

        {/* Centro */}
        <div className="flex flex-col m-4 w-full max-w-3xl h-full">
          {/* Contenedor para cámara 

          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full aspect-[4/3] mb-1 border-2 border-gray-300 rounded-lg"
            onCanPlay={() => console.log("🚀 Video listo para reproducir")}
            onError={(e) => console.error("🔥 Error de video:", e.target.error)}
          />*/}
          <img className="w-full aspect-[4/3] mb-1 border-2 border-gray-300 rounded-lg" src="ascaris.jpg" alt="" />


          {/* Controles versión mobile centrados */}
          <div className=" flex justify-center items-center mt-2 w-auto">
            <div className="grid grid-cols-5 gap-2 w-full max-w-md">
              {/* 1. Flecha arriba */}
              <button onClick={() => handleMove("up")} className="bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-800 hover:scale-110">
                <FaLongArrowAltUp />
              </button>
              {/* 2. Flecha izquierda */}
              <button onClick={() => handleMove("left")} className="bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-800 hover:scale-110">
                <FaLongArrowAltLeft />
              </button>
              {/* 3. Flecha abajo */}
              <button onClick={() => handleMove("down")} className="bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-800 hover:scale-110">
                <FaLongArrowAltDown />
              </button>
              {/* 4. Flecha derecha */}
              <button onClick={() => handleMove("right")} className="bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-800 hover:scale-110">
                <FaLongArrowAltRight />
              </button>
              {/* 5. Botón Z+ */}
              <button onClick={() => handleZoom("in")} className="bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-800 hover:scale-110">
                Z+
              </button>
              {/* 7. Botón conectar: ocupa columnas 1 a 4 */}

              {!isConnected ? (
                <button onClick={connect} className="col-span-4 px-3 py-1 bg-blue-600 text-white rounded-lg transition-transform duration-200 ease-in-out hover:bg-blue-700 hover:scale-110">Conectar</button>
              ) : (
                <button onClick={disconnect} className="col-span-4 px-3 py-1 bg-red-600 text-white rounded-lg transition-transform duration-200 ease-in-out hover:bg-red-700 hover:scale-110">Desconectar</button>
              )}

              {/* 8. Botón Z-: se ubica en la columna 5 */}
              <button onClick={() => handleZoom("out")} className="col-start-5 bg-green-600 text-white rounded-lg text-xl px-3 py-1 transition-transform duration-200 ease-in-out hover:bg-green-700 hover:scale-110">
                Z-
              </button>
            </div>
          </div>
        </div>

        {/* Derecha */}
      </div>
    </div>
  );
};

export default WebRTCComponent;