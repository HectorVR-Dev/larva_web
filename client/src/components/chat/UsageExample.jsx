import React, { useState } from 'react';
import ChatBot from './ChatBot.jsx';

/**
 * Ejemplo de cómo usar el componente ChatBot en diferentes escenarios
 */

// Ejemplo 1: Uso básico
export function BasicUsageExample() {
  return (
    <div style={{ padding: '20px' }}>
      <h2>ChatBot Básico</h2>
      <ChatBot />
    </div>
  );
}

// Ejemplo 2: Uso personalizado con props
export function CustomizedUsageExample() {
  return (
    <div style={{ padding: '20px', backgroundColor: '#f5f5f5' }}>
      <h2>ChatBot Personalizado</h2>
      <ChatBot 
        apiUrl="https://mi-endpoint-personalizado.com/api"
        theme="dark"
        title="Mi Asistente Personalizado"
        placeholder="Pregúntame cualquier cosa..."
        width="400px"
        height="500px"
        className="mi-chatbot-dorado"
      />
    </div>
  );
}

// Ejemplo 3: Uso con tema dinámico
export function DynamicThemeExample() {
  const [darkMode, setDarkMode] = useState(false);
  
  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={() => setDarkMode(!darkMode)}
          style={{
            padding: '10px 20px',
            backgroundColor: darkMode ? '#333' : '#fff',
            color: darkMode ? '#fff' : '#000',
            border: '1px solid #ccc'
          }}
        >
          Cambiar a modo {darkMode ? 'claro' : 'oscuro'}
        </button>
      </div>
      
      <ChatBot 
        theme={darkMode ? 'dark' : 'light'}
        title={darkMode ? 'Asistente Nocturno' : 'Asistente Diurno'}
        width="600px"
        height="700px"
      />
    </div>
  );
}

// Ejemplo 4: Múltiples instancias
export function MultipleInstancesExample() {
  return (
    <div style={{ display: 'flex', gap: '20px', padding: '20px' }}>
      <div style={{ flex: 1 }}>
        <h3>ChatBot 1 - Asistente Médico</h3>
        <ChatBot 
          title="Asistente Médico"
          placeholder="¿Qué síntomas tienes?"
          width="100%"
          height="400px"
        />
      </div>
      
      <div style={{ flex: 1 }}>
        <h3>ChatBot 2 - Asistente Técnico</h3>
        <ChatBot 
          title="Asistente Técnico"
          placeholder="¿En qué problema técnico te puedo ayudar?"
          width="100%"
          height="400px"
          theme="dark"
        />
      </div>
    </div>
  );
}

// Ejemplo 5: Componente de página completa
export function FullPageExample() {
  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <ChatBot 
        width="100%"
        height="100%"
        showWelcome={true}
        className="full-page-chatbot"
      />
    </div>
  );
}

// Ejemplo principal que muestra todos los casos
export default function UsageExample() {
  const [activeExample, setActiveExample] = useState('basic');
  
  const examples = {
    basic: BasicUsageExample,
    custom: CustomizedUsageExample,
    dynamic: DynamicThemeExample,
    multiple: MultipleInstancesExample,
    fullpage: FullPageExample
  };
  
  const ActiveComponent = examples[activeExample];
  
  return (
    <div style={{ fontFamily: 'Arial, sans-serif' }}>
      <nav style={{ 
        backgroundColor: '#333', 
        padding: '10px',
        marginBottom: '20px'
      }}>
        <button 
          onClick={() => setActiveExample('basic')}
          style={{ marginRight: '10px', color: activeExample === 'basic' ? '#4CAF50' : '#fff' }}
        >
          Básico
        </button>
        <button 
          onClick={() => setActiveExample('custom')}
          style={{ marginRight: '10px', color: activeExample === 'custom' ? '#4CAF50' : '#fff' }}
        >
          Personalizado
        </button>
        <button 
          onClick={() => setActiveExample('dynamic')}
          style={{ marginRight: '10px', color: activeExample === 'dynamic' ? '#4CAF50' : '#fff' }}
        >
          Tema Dinámico
        </button>
        <button 
          onClick={() => setActiveExample('multiple')}
          style={{ marginRight: '10px', color: activeExample === 'multiple' ? '#4CAF50' : '#fff' }}
        >
          Múltiples
        </button>
        <button 
          onClick={() => setActiveExample('fullpage')}
          style={{ marginRight: '10px', color: activeExample === 'fullpage' ? '#4CAF50' : '#fff' }}
        >
          Página Completa
        </button>
      </nav>
      
      <ActiveComponent />
    </div>
  );
}