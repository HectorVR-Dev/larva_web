# ChatBot Component

Componente React encapsulado para integración de chatbot con Gemini AI.

## Características

- ✅ Interfaz de chat completa con sidebar
- ✅ Gestión de múltiples conversaciones
- ✅ Efecto de typing animado
- ✅ Temas claro/oscuro
- ✅ Responsive design
- ✅ Persistencia en localStorage
- ✅ Estilos encapsulados (sin conflictos)

## Instalación

1. Copiar los archivos de la carpeta `src/components/chat/` a tu proyecto
2. Asegurar que las dependencias están instaladas:
   ```bash
   npm install react lucide-react
   ```

## Uso Básico

```jsx
import ChatBot from './components/chat';

function App() {
  return (
    <div>
      <h1>Mi Aplicación</h1>
      <ChatBot 
        apiUrl="https://tu-api-endpoint.com"
        title="Mi Asistente"
      />
    </div>
  );
}
```

## Props

| Prop | Tipo | Default | Descripción |
|------|------|---------|-------------|
| `apiUrl` | string | `import.meta.env.VITE_API_URL` | URL del endpoint de la API Gemini |
| `theme` | 'light'\\|'dark' | 'light' | Tema inicial del componente |
| `title` | string | 'Asistente LARVA' | Título mostrado en la pantalla de bienvenida |
| `placeholder` | string | 'Mensaje...' | Placeholder del input de texto |
| `width` | string | '100%' | Ancho del contenedor del chatbot |
| `height` | string | '600px' | Alto del contenedor del chatbot |
| `className` | string | '' | Clase CSS adicional |
| `showWelcome` | boolean | true | Mostrar pantalla de bienvenida cuando no hay mensajes |

## Ejemplos de Uso

### Uso Simple
```jsx
<ChatBot 
  apiUrl="https://api.gemini.com/chat"
  theme="dark"
/>
```

### Uso Personalizado
```jsx
<ChatBot 
  apiUrl="https://mi-endpoint-personalizado.com/api"
  title="Asistente Personalizado"
  placeholder="Escribe tu pregunta aquí..."
  width="400px"
  height="700px"
  theme="light"
  className="mi-chatbot-custom"
  showWelcome={false}
/>
```

### Con Tema Dinámico
```jsx
import { useState } from 'react';
import ChatBot from './components/chat';

function App() {
  const [darkMode, setDarkMode] = useState(false);
  
  return (
    <div>
      <button onClick={() => setDarkMode(!darkMode)}>
        Toggle {darkMode ? 'Light' : 'Dark'} Mode
      </button>
      <ChatBot 
        theme={darkMode ? 'dark' : 'light'}
        title={darkMode ? 'Asistente Nocturno' : 'Asistente Diurno'}
      />
    </div>
  );
}
```

## Estructura de Archivos

```
src/components/chat/
├── ChatBot.jsx      # Componente principal
├── chatbot.css      # Estilos encapsulados
├── index.jsx        # Export principal
└── README.md        # Esta documentación
```

## API Requerida

El componente espera que tu API responda con el formato de Gemini AI:

```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "text": "Respuesta del modelo"
      }]
    }
  }]
}
```

## Personalización de Estilos

Los estilos están encapsulados con el prefijo `chatbot-`. Puedes sobrescribir estilos específicos:

```css
.mi-chatbot-custom .chatbot-welcome-heading {
  color: #your-color;
  font-size: 2rem;
}
```

## Limitaciones

- Requiere React 18+ o superior
- Necesita API compatible con Gemini AI
- Usa localStorage para persistencia
- Depende de lucide-react para iconos

## Soporte

Para problemas o preguntas, revisar la documentación del proyecto padre o crear un issue en el repositorio correspondiente.