graph TB
    subgraph "🌐 Cliente (Navegador)"
        USER[👤 Usuario]
        BROWSER[🌍 Navegador Web]
    end
    
    subgraph "🔄 Capa de Proxy"
        NGINX_PROXY[📡 Nginx Proxy<br/>Puerto 4200]
    end
    
    subgraph "🎨 Frontend Angular"
        ANGULAR[🅰️ Angular App<br/>SPA]
        COMPONENTS[📦 Componentes]
        SERVICES[⚙️ Servicios]
    end
    
    subgraph "🔧 Backend FastAPI"
        FASTAPI[🚀 FastAPI Server<br/>Puerto 8000]
        ENDPOINTS[📡 API Endpoints]
        BUSINESS[🧠 Lógica de Negocio]
        SCHEDULER[⏲️ Scheduler Tasks]
    end
    
    subgraph "🗄️ Base de Datos"
        MONGODB[🍃 MongoDB<br/>Puerto 27017]
        COLLECTIONS[📚 8 Colecciones]
    end
    
    subgraph "🌍 Servicios Externos"
        FIREBASE[🔥 Firebase Auth]
        OPENAI[🤖 OpenAI API]
        EMAIL_SERV[📧 Email Servers]
    end
    
    USER --> BROWSER
    BROWSER --> NGINX_PROXY
    NGINX_PROXY --> ANGULAR
    NGINX_PROXY --> FASTAPI
    
    ANGULAR --> COMPONENTS
    ANGULAR --> SERVICES
    SERVICES --> FASTAPI
    
    FASTAPI --> ENDPOINTS
    FASTAPI --> BUSINESS
    FASTAPI --> SCHEDULER
    FASTAPI --> MONGODB
    
    FASTAPI --> FIREBASE
    FASTAPI --> OPENAI
    FASTAPI --> EMAIL_SERV
    
    MONGODB --> COLLECTIONS