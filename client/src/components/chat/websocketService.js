// websocketService.js
import { io } from 'socket.io-client';

const systemIp = import.meta.env.VITE_SYSTEM_IP || "0.0.0.0";

class WebSocketService {
  constructor() {
    this.socket = null;
    this.messageHandlers = new Map();
  }

  connect(url = `http://${systemIp}:8005`) {
    this.socket = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    this.socket.on('connect', () => {
      console.log('Connected to WebSocket server');
    });

    this.socket.on('disconnect', () => {
      console.log('Disconnected from WebSocket server');
    });

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    return this.socket;
  }

  sendMessage(conversation, botMessageId) {
    console.log('Socket connected?', this.socket?.connected);

    if (!this.socket?.connected) {
      throw new Error('WebSocket not connected');
    }

    const formattedMessages = conversation.messages?.map((msg) => ({
      role: msg.role === "bot" ? "assistant" : "user",
      content: msg.content,
    }));

    console.log('Sending message:', { formattedMessages, botMessageId });

    this.socket.emit('message', {
      messages: formattedMessages,
      messageId: botMessageId,
      vision_enabled: true,
    });
  }

  onStreamingResponse(handler) {
    this.socket.on('response_chunk', handler);
  }

  onCompleteResponse(handler) {
    this.socket.on('response_complete', handler);
  }

  onError(handler) {
    this.socket.on('response_error', handler);
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
}

export default new WebSocketService();