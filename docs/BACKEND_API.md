graph TB
    %% Capa de API
    subgraph "🌐 FastAPI Application"
        API[api.py<br/>FastAPI Main App]
        STARTUP[Startup Event<br/>Scheduler Init]
    end
    
    %% Grupos de endpoints
    subgraph "📡 API Endpoints"
        AUTH_EP[🔐 Authentication<br/>/user/* endpoints]
        PROCESS_EP[🤖 AI Processing<br/>/process, /upload]
        INVOICE_EP[📄 Invoice Management<br/>/v2/invoices/*]
        ADMIN_EP[👑 Admin Panel<br/>/admin/*]
        SYSTEM_EP[⚙️ System Control<br/>/job/*, /system/*]
        EMAIL_EP[📧 Email Config<br/>/email-configs/*]
        TEMPLATE_EP[📊 Export Templates<br/>/export-templates/*]
    end
    
    %% Capa de servicios
    subgraph "🔧 Core Services"
        OPENAI_PROC[OpenAI Processor<br/>AI Invoice Processing]
        EMAIL_PROC[Email Processor<br/>Multi-account Email]
        SCHEDULER[Scheduler<br/>Monthly Reset Tasks]
        RESET_SERVICE[Monthly Reset Service<br/>AI Limits Management]
    end
    
    %% Capa de repositorios
    subgraph "🗃️ Data Repositories"
        USER_REPO[User Repository<br/>auth_users]
        INVOICE_REPO[Invoice Repository<br/>headers + items]
        SUBSCRIPTION_REPO[Subscription Repository<br/>plans + subscriptions]
        TEMPLATE_REPO[Template Repository<br/>export_templates]
        EMAIL_REPO[Email Config Repository<br/>email_configs]
        TASK_REPO[Task Repository<br/>tasks]
    end
    
    %% Base de datos
    subgraph "🗄️ MongoDB Database"
        MONGODB[(MongoDB<br/>cuenlyapp_warehouse)]
    end
    
    %% Servicios externos
    subgraph "🌍 External Services"
        OPENAI[OpenAI API<br/>GPT-4 Processing]
        FIREBASE[Firebase Auth<br/>User Authentication]
        EMAIL_SERVERS[Email Servers<br/>IMAP/SMTP]
    end
    
    %% Flujos principales
    API --> AUTH_EP
    API --> PROCESS_EP
    API --> INVOICE_EP
    API --> ADMIN_EP
    API --> SYSTEM_EP
    API --> EMAIL_EP
    API --> TEMPLATE_EP
    
    AUTH_EP --> USER_REPO
    PROCESS_EP --> OPENAI_PROC
    PROCESS_EP --> TASK_REPO
    INVOICE_EP --> INVOICE_REPO
    ADMIN_EP --> USER_REPO
    ADMIN_EP --> SUBSCRIPTION_REPO
    ADMIN_EP --> RESET_SERVICE
    EMAIL_EP --> EMAIL_PROC
    EMAIL_EP --> EMAIL_REPO
    TEMPLATE_EP --> TEMPLATE_REPO
    
    OPENAI_PROC --> OPENAI
    OPENAI_PROC --> INVOICE_REPO
    EMAIL_PROC --> EMAIL_SERVERS
    SCHEDULER --> RESET_SERVICE
    RESET_SERVICE --> USER_REPO
    RESET_SERVICE --> SUBSCRIPTION_REPO
    
    USER_REPO --> MONGODB
    INVOICE_REPO --> MONGODB
    SUBSCRIPTION_REPO --> MONGODB
    TEMPLATE_REPO --> MONGODB
    EMAIL_REPO --> MONGODB
    TASK_REPO --> MONGODB
    
    AUTH_EP --> FIREBASE
    STARTUP --> SCHEDULER
    
    %% Estilos
    classDef apiClass fill:#e1f5fe
    classDef serviceClass fill:#f3e5f5
    classDef repoClass fill:#e8f5e8
    classDef dbClass fill:#fff3e0
    classDef externalClass fill:#ffebee
    
    class API,AUTH_EP,PROCESS_EP,INVOICE_EP,ADMIN_EP,SYSTEM_EP,EMAIL_EP,TEMPLATE_EP apiClass
    class OPENAI_PROC,EMAIL_PROC,SCHEDULER,RESET_SERVICE serviceClass
    class USER_REPO,INVOICE_REPO,SUBSCRIPTION_REPO,TEMPLATE_REPO,EMAIL_REPO,TASK_REPO repoClass
    class MONGODB dbClass
    class OPENAI,FIREBASE,EMAIL_SERVERS externalClass