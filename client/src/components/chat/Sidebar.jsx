import { Menu, Moon, Plus, Sparkles, Sun, Trash2 } from "lucide-react";
import { LuEyeClosed } from "react-icons/lu";
import { FaEye } from "react-icons/fa";

const Sidebar = ({ isSidebarOpen, setIsSidebarOpen, conversations, setConversations, activeConversation, setActiveConversation, theme, setTheme, isInferenceEnabled, setInferenceEnabled }) => {

  // Create new conversation
  const createNewConversation = () => {
    // Check if any existing conversation is empty
    const emptyConversation = conversations.find((conv) => conv.messages.length === 0);
    if (emptyConversation) {
      // If an empty conversation exists, make it active instead of creating a new one
      setActiveConversation(emptyConversation.id);
      return;
    }

    // Only create a new conversation if there are no empty ones
    const newId = `conv-${Date.now()}`;
    setConversations([{ id: newId, title: "Nuevo Chat", messages: [] }, ...conversations]);
    setActiveConversation(newId);
  };

  // Delete conversation and handle active selection
  const deleteConversation = (id, e) => {
    e.stopPropagation(); // Prevent triggering conversation selection
    // Check if this is the last conversation
    if (conversations.length === 1) {
      // Create new conversation with ID "default"
      const newConversation = { id: "default", title: "Nuevo Chat", messages: [] };
      setConversations([newConversation]);
      setActiveConversation("default"); // Set active to match the new conversation ID
    } else {
      // Remove the conversation
      const updatedConversations = conversations.filter((conv) => conv.id !== id);
      setConversations(updatedConversations);
      // If deleting the active conversation, switch to another one
      if (activeConversation === id) {
        // Find the first conversation that isn't being deleted
        const nextConversation = updatedConversations[0];
        setActiveConversation(nextConversation.id);
      }
    }
  };


  return (
    <aside className={`chatbot-sidebar ${isSidebarOpen ? "open" : "closed"}`}>
     
      {/* Sidebar Header */}
      <div className="chatbot-sidebar-header">
        <button className="chatbot-sidebar-toggle" onClick={() => setIsSidebarOpen((prev) => !prev)}>
          <Menu size={18} />
        </button>
        <button className="chatbot-new-chat-btn" onClick={createNewConversation}>
          <Plus size={20} />
          <span>Nuevo Chat</span>
        </button>
      </div>
      
      {/* Conversation List */}
      <div className="chatbot-sidebar-content">
        <h2 className="chatbot-sidebar-title">Chat history</h2>
        <ul className="chatbot-conversation-list">
          {conversations.map((conv) => (
            <li key={conv.id} className={`chatbot-conversation-item ${activeConversation === conv.id ? "active" : ""}`} onClick={() => setActiveConversation(conv.id)}>
              <div className="chatbot-conversation-icon-title">
                <div className="chatbot-conversation-icon">
                  <Sparkles size={14} />
                </div>
                <span className="chatbot-conversation-title">{conv.title}</span>
              </div>
              {/* Only show delete button if more than one chat or not a new chat */}
              <button className={`chatbot-delete-btn ${conversations.length > 1 || conv.title !== "Nuevo Chat" ? "" : "hide"}`} onClick={(e) => deleteConversation(conv.id, e)}>
                <Trash2 size={16} />
              </button>
            </li>
          ))}
        </ul>
      </div>
      
      {/* Theme Toggle */}
      <div className="chatbot-sidebar-footer">
        <button className="chatbot-theme-toggle" onClick={() => setInferenceEnabled(!isInferenceEnabled)}>
          {isInferenceEnabled ? (
            <>
              <FaEye size={20} />
              <span>Inferencia Habilitada</span>
            </>
          ) : (
            <>
              <LuEyeClosed size={20} />
              <span>Habilitar Inferencia</span>
            </>
          )}
        </button>
      </div>
    
    </aside>
  );
};
export default Sidebar;