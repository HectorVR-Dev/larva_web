import { useEffect, useRef, useState } from "react";
import Message from "./Message";
import PromptForm from "./PromptForm";
import Sidebar from "./Sidebar";
import { Menu } from "lucide-react";
import "./chatbot.css";
import websocketService from './websocketService';

const ChatBot = ({ 
  apiUrl = import.meta.env.VITE_API_URL,
  theme: initialTheme = 'light',
  title = 'Asistente LARVA',
  placeholder = 'Mensaje...',
  width = '100%',
  height = '600px',
  className = '',
  showWelcome = true,
  isVisible, 
  isNavBarVisible 
}) => {
  // Main app state
  const [isLoading, setIsLoading] = useState(false);
  const typingInterval = useRef(null);
  const messagesContainerRef = useRef(null);
  const accumulatedTextRef = useRef('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => window.innerWidth > 768);

  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("chat-theme");
    if (savedTheme) {
      return savedTheme;
    }
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    return prefersDark ? "dark" : initialTheme;
  });

  const [inference, setInference] = useState(false);

  const [conversations, setConversations] = useState(() => {
    try {
      // Load conversations from localStorage or use default
      const saved = localStorage.getItem("chat-conversations");
      return saved ? JSON.parse(saved) : [{ id: "default", title: "New Chat", messages: [] }];
    } catch {
      return [{ id: "default", title: "New Chat", messages: [] }];
    }
  });
  const [activeConversation, setActiveConversation] = useState(() => {
    return localStorage.getItem("chat-activeConversation") || "default";
  });
  
  useEffect(() => {
    localStorage.setItem("chat-activeConversation", activeConversation);
  }, [activeConversation]);
  // Save conversations to localStorage
  useEffect(() => {
    localStorage.setItem("chat-conversations", JSON.stringify(conversations));
  }, [conversations]);
  // Handle theme changes
  useEffect(() => {
    localStorage.setItem("chat-theme", theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  // Get current active conversation
  const currentConversation = conversations.find((c) => c.id === activeConversation) || conversations[0];
  // Scroll to bottom of container
  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  };
  // Effect to scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [conversations, activeConversation]);


  const typingEffect = (text, messageId) => {
    let textElement = document.querySelector(`#${messageId} .text`);
    if (!textElement) return;

    // Initially set the content to empty and mark as loading
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === activeConversation
          ? {
            ...conv,
            messages: conv.messages.map((msg) => (msg.id === messageId ? { ...msg, content: "", loading: true } : msg)),
          }
          : conv
      )
    );


    // Set up typing animation
    textElement.textContent = "";
    const words = text.split(" ");
    let wordIndex = 0;
    let currentText = "";
    clearInterval(typingInterval.current);

    typingInterval.current = setInterval(() => {
      if (wordIndex < words.length) {
        // Update the current text being displayed
        currentText += (wordIndex === 0 ? "" : " ") + words[wordIndex++];
        textElement.textContent = currentText;
        // Update state with current progress
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === activeConversation
              ? {
                ...conv,
                messages: conv.messages.map((msg) => (msg.id === messageId ? { ...msg, content: currentText, loading: true } : msg)),
              }
              : conv
          )
        );
        scrollToBottom();
      } else {
        // Animation complete
        clearInterval(typingInterval.current);
        // Final update, mark as finished loading
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === activeConversation
              ? {
                ...conv,
                messages: conv.messages.map((msg) => (msg.id === messageId ? { ...msg, content: currentText, loading: false } : msg)),
              }
              : conv
          )
        );
        setIsLoading(false);
      }
    }, 40);
  };

  // Update specific bot message
  const updateBotMessage = (botId, content, isError = false) => {
    setConversations((prev) =>
      prev.map((conv) =>
        conv.id === activeConversation
          ? {
            ...conv,
            messages: conv.messages.map((msg) => (msg.id === botId ? { ...msg, content, loading: false, error: isError } : msg)),
          }
          : conv
      )
    );
  };

  useEffect(() => {
    websocketService.connect();

    websocketService.onStreamingResponse(({ chunk, messageId }) => {
      accumulatedTextRef.current += chunk;
      // No actualizar aquí, solo acumular
    });

    websocketService.onCompleteResponse(({ messageId }) => {
      // Cuando termina, usar tu typingEffect existente
      typingEffect(accumulatedTextRef.current, messageId);
      accumulatedTextRef.current = '';
    });

    websocketService.onError(({ error, messageId }) => {
      setIsLoading(false);
      updateBotMessage(messageId, error, true);
      accumulatedTextRef.current = '';
    });

    return () => websocketService.disconnect();
  }, [activeConversation]);
  
  const generateResponseWebSocket = async (conversation, botMessageId) => {
    try {
      setIsLoading(true);
      accumulatedTextRef.current = '';
      websocketService.sendMessage(conversation, botMessageId);
    } catch (error) {
      setIsLoading(false);
      updateBotMessage(botMessageId, error.message, true);
    }
  };

  // Generate AI response
  const generateResponse = async (conversation, botMessageId) => {

    // Format messages for API
    const formattedMessages = conversation.messages?.map((msg) => ({
      role: msg.role === "bot" ? "model" : msg.role,
      parts: [{ text: msg.content }],
    }));

    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contents: formattedMessages }),
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.error.message);

      // Clean up response formatting
      const responseText = data.candidates[0].content.parts[0].text.replace(/\*\*([^*]+)\*\*/g, "$1").trim();
      typingEffect(responseText, botMessageId);
    } catch (error) {
      setIsLoading(false);
      updateBotMessage(botMessageId, error.message, true);
    }
  };


  if (!isVisible) return null;

  return (
    <div 
      className={`chatbot-container ${theme === "light" ? "light-theme" : "dark-theme"} ${className}`}
    >
      <main className="chatbot-main-container">

        <header className="chatbot-main-header">
          <button onClick={() => setIsSidebarOpen(true)} className="chatbot-sidebar-toggle">
            <Menu size={18} />
          </button>
        </header>

        {currentConversation.messages.length === 0 && showWelcome ? (
          // Welcome container
          <div className="chatbot-welcome-container">
            <img className="chatbot-welcome-logo" src="/microscope.svg" alt="microscope Logo" />
            <h1 className="chatbot-welcome-heading">{title}</h1>
            <p className="chatbot-welcome-text">Soy tu asistente de esta practica, pregunta lo que necesites.</p>
          </div>
        ) : (
          // Messages container
          <div className="chatbot-messages-container" ref={messagesContainerRef}>
            {currentConversation.messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
          </div>
        )}
        {/* Prompt input */}
        <div className="chatbot-prompt-container">
          <div className="chatbot-prompt-wrapper">
            <PromptForm 
              conversations={conversations} 
              setConversations={setConversations} 
              activeConversation={activeConversation} 
              generateResponse={generateResponseWebSocket} 
              isLoading={isLoading} 
              setIsLoading={setIsLoading}
              placeholder={placeholder}
            />
          </div>
          <p className="chatbot-disclaimer-text">Los LLM pueden generar respuestas incorrectas o engañosas. Por favor, verifica la información antes de actuar.</p>
        </div>
      </main>

      <div className={`chatbot-overlay ${isSidebarOpen ? "show" : "hide"}`} onClick={() => setIsSidebarOpen(false)}></div>

      <Sidebar 
        conversations={conversations} 
        setConversations={setConversations} 
        activeConversation={activeConversation} 
        setActiveConversation={setActiveConversation} 
        theme={theme} 
        setTheme={setTheme}
        isInferenceEnabled={inference}
        setInferenceEnabled={setInference}
        isSidebarOpen={isSidebarOpen} 
        setIsSidebarOpen={setIsSidebarOpen} 
      />
    </div>
  );
};

export default ChatBot;