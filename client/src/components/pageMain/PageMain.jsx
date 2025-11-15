import styles from './PageMain.module.css';

function PageMain({ children}) {
  return (
    <div className={`flex-1 bg-[var(--color-bg-primary)] transition-all duration-300 overflow-y-auto ${styles.pageMain}`}>
      {children}
    </div>
  );
}

export default PageMain;
