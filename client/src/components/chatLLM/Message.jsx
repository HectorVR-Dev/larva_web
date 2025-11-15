import styles from './ChatLLM.module.css';

const Message = ({ message }) => {
  return (
    <div id={message.id} className={`${styles.message} ${styles[`${message.role}Message`]} ${message.loading ? styles.loading : ""} ${message.error ? styles.error : ""}`}>
      {message.role === "bot" && <img className={styles.avatar} src="gemini.svg" alt="Bot Avatar" />}
      <p className={styles.text}>{message.content}</p>
    </div>
  );
};
export default Message;