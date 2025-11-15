import styles from './ChatLLM.module.css';
import { Menu, Moon, Plus, Sparkles, Sun, Trash2 } from "lucide-react";


const Sidebar = ({ isSidebarOpen, setIsSidebarOpen, conversations, setConversations, activeConversation, setActiveConversation, theme, setTheme }) => {
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
    setConversations([{ id: newId, title: "New Chat", messages: [] }, ...conversations]);
    setActiveConversation(newId);
  };
  // Delete conversation and handle active selection
  const deleteConversation = (id, e) => {
    e.stopPropagation(); // Prevent triggering conversation selection
    // Check if this is the last conversation
    if (conversations.length === 1) {
      // Create new conversation with ID "default"
      const newConversation = { id: "default", title: "New Chat", messages: [] };
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
    <aside className={`${styles.conversationItem} ${isSidebarOpen ? "open" : "closed"}`}>
      {/* Sidebar Header */}
      <div className={styles.sidebarHeader}>
        <button className={styles.sidebarToggle} onClick={() => setIsSidebarOpen((prev) => !prev)}>
          <Menu size={18} />
        </button>
        <button className={styles.newChatBtn} onClick={createNewConversation}>
          <Plus size={20} />
          <span>New chat</span>
        </button>
      </div>
      {/* Conversation List */}
      <div className={styles.sidebarContent}>
        <h2 className={styles.sidebarTitle}>Chat history</h2>
        <ul className={styles.conversationList}>
          {conversations.map((conv) => (
            <li key={conv.id} className={`${styles.conversationItem} ${activeConversation === conv.id ? styles.active : ""}`} onClick={() => setActiveConversation(conv.id)}>
              <div className={styles.conversationIconTitle}>
                <div className={styles.conversationIcon}>
                  <Sparkles size={14} />
                </div>
                <span className={styles.conversationTitle}>{conv.title}</span>
              </div>
              {/* Only show delete button if more than one chat or not a new chat */}
              <button className={`${styles.deleteBtn} ${conversations.length > 1 || conv.title !== "New Chat" ? "" : styles.hide}`} onClick={(e) => deleteConversation(conv.id, e)}>
                <Trash2 size={16} />
              </button>
            </li>
          ))}
        </ul>
      </div>
      {/* Theme Toggle */}
      <div className={styles.sidebarFooter}>
        <button className={styles.themeToggle} onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          {theme === "light" ? (
            <>
              <Moon size={20} />
              <span>Dark mode</span>
            </>
          ) : (
            <>
              <Sun size={20} />
              <span>Light mode</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
export default Sidebar;
