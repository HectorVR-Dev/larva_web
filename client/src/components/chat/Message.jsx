import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const Message = ({ message }) => {
  if (!message || !message.content) return null;

  // Limpia saltos de línea excesivos (solo esta línea)
  const cleanContent = message.content
    .replace(/\n\s*\n\s*\n+/g, '\n\n')
    .trim();

  return (
    <div
      id={message.id}
      className={`chatbot-message ${message.role}-message ${message.loading ? "loading" : ""} ${message.error ? "error" : ""}`}
    >
      {message.role === "bot" && (
        <img className="avatar" src="/microscope.svg" alt="Bot Avatar" />
      )}
      <div className='text'>
        <ReactMarkdown
          components={{
            code(props) {
              const { children, className, node, ...rest } = props;
              const match = /language-(\w+)/.exec(className || '');
              return match ? (
                <SyntaxHighlighter
                  {...rest}
                  PreTag="div"
                  language={match[1]}
                  style={vscDarkPlus}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : (
                <code {...rest} className={className}>
                  {children}
                </code>
              );
            },

            // SOLUCIÓN SIMPLE Y SEGURA: quita los <p> que envuelven listas
            p: ({ children }) => <>{children}</>,

            // Listas con márgenes mínimos
            ul: ({ children }) => <ul className="list-disc ml-5 my-2">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal ml-5 my-2">{children}</ol>,
            li: ({ children }) => <li className="my-1">{children}</li>,
          }}
        >
          {cleanContent}
        </ReactMarkdown>
      </div>
    </div>
  );
};

export default Message;