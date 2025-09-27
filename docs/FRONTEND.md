graph TB
    %% Aplicación principal
    subgraph "🅰️ Angular Application"
        APP[App Component<br/>Main Shell]
        ROUTER[Router<br/>Navigation Guard]
        NOTIFICATION[Notification System<br/>Modern UI Feedback]
    end
    
    %% Componentes públicos
    subgraph "🔓 Public Components"
        LOGIN[Login Component<br/>Firebase Auth]
        TRIAL[Trial Banner<br/>User Onboarding]
    end
    
    %% Componentes principales
    subgraph "🏠 Main Features"
        DASHBOARD[Dashboard<br/>Overview & Stats]
        UPLOAD[🔼 Upload Components<br/>PDF & XML Processing]
        INVOICES[📄 Invoice Explorer<br/>Data Visualization]
        INVOICES_V2[📊 Invoices V2<br/>Advanced Grid View]
    end
    
    %% Herramientas de usuario
    subgraph "🔧 User Tools"
        EMAIL_CONFIG[📧 Email Configuration<br/>IMAP Setup]
        EXPORT_TEMPLATES[📊 Export Templates<br/>Excel Customization]
        SUBSCRIPTION[💳 Subscription<br/>Plan Management]
    end
    
    %% Panel administrativo
    subgraph "👑 Admin Panel"
        ADMIN_MAIN[Admin Panel<br/>Multi-tab Interface]
        ADMIN_STATS[📈 Statistics Tab<br/>User & Invoice Analytics]
        ADMIN_USERS[👥 Users Tab<br/>Role & Status Management]
        ADMIN_PLANS[💼 Plans Tab<br/>Subscription Management]
        ADMIN_AI[🤖 AI Limits Tab<br/>Reset Automation]
        PLANS_MGMT[Plans Management<br/>CRUD Operations]
    end
    
    %% Componentes compartidos
    subgraph "🔄 Shared Components"
        NAVBAR[Navigation Bar<br/>User Menu & Logo]
        FOOTER[Footer<br/>App Information]
        HELP[Help Component<br/>User Guide]
        SHARED_NOTIF[Notification Container<br/>Toast Messages]
    end
    
    %% Servicios
    subgraph "⚙️ Angular Services"
        API_SERVICE[API Service<br/>Backend Communication]
        AUTH_SERVICE[Auth Service<br/>Firebase Integration]
        NOTIFICATION_SERVICE[Notification Service<br/>UI Feedback System]
    end
    
    %% Backend connection
    subgraph "🔗 Backend APIs"
        BACKEND[FastAPI Backend<br/>REST Endpoints]
    end
    
    %% Servicios externos
    subgraph "🌍 External Services"
        FIREBASE_EXT[Firebase<br/>Authentication]
    end
    
    %% Flujos de navegación
    APP --> ROUTER
    APP --> NOTIFICATION
    ROUTER --> LOGIN
    ROUTER --> DASHBOARD
    ROUTER --> UPLOAD
    ROUTER --> INVOICES
    ROUTER --> INVOICES_V2
    ROUTER --> EMAIL_CONFIG
    ROUTER --> EXPORT_TEMPLATES
    ROUTER --> SUBSCRIPTION
    ROUTER --> ADMIN_MAIN
    
    %% Admin panel tabs
    ADMIN_MAIN --> ADMIN_STATS
    ADMIN_MAIN --> ADMIN_USERS
    ADMIN_MAIN --> ADMIN_PLANS
    ADMIN_MAIN --> ADMIN_AI
    ADMIN_PLANS --> PLANS_MGMT
    
    %% Componentes compartidos
    APP --> NAVBAR
    APP --> FOOTER
    APP --> SHARED_NOTIF
    DASHBOARD --> HELP
    
    %% Servicios
    LOGIN --> AUTH_SERVICE
    ADMIN_STATS --> API_SERVICE
    ADMIN_USERS --> API_SERVICE
    PLANS_MGMT --> API_SERVICE
    ADMIN_AI --> API_SERVICE
    UPLOAD --> API_SERVICE
    INVOICES --> API_SERVICE
    INVOICES_V2 --> API_SERVICE
    EMAIL_CONFIG --> API_SERVICE
    EXPORT_TEMPLATES --> API_SERVICE
    SUBSCRIPTION --> API_SERVICE
    
    NOTIFICATION --> NOTIFICATION_SERVICE
    SHARED_NOTIF --> NOTIFICATION_SERVICE
    
    %% Conexiones externas
    API_SERVICE --> BACKEND
    AUTH_SERVICE --> FIREBASE_EXT
    
    %% Características especiales
    TRIAL -.-> SUBSCRIPTION
    ADMIN_AI -.-> "🔄 Monthly Reset Scheduler"
    PLANS_MGMT -.-> "💳 User Subscription Assignment"
    
    %% Estilos
    classDef appClass fill:#e3f2fd
    classDef publicClass fill:#f1f8e9
    classDef mainClass fill:#fff3e0
    classDef toolClass fill:#f3e5f5
    classDef adminClass fill:#ffebee
    classDef sharedClass fill:#e8f5e8
    classDef serviceClass fill:#fce4ec
    classDef backendClass fill:#e0f2f1
    classDef externalClass fill:#f9fbe7
    
    class APP,ROUTER,NOTIFICATION appClass
    class LOGIN,TRIAL publicClass
    class DASHBOARD,UPLOAD,INVOICES,INVOICES_V2 mainClass
    class EMAIL_CONFIG,EXPORT_TEMPLATES,SUBSCRIPTION toolClass
    class ADMIN_MAIN,ADMIN_STATS,ADMIN_USERS,ADMIN_PLANS,ADMIN_AI,PLANS_MGMT adminClass
    class NAVBAR,FOOTER,HELP,SHARED_NOTIF sharedClass
    class API_SERVICE,AUTH_SERVICE,NOTIFICATION_SERVICE serviceClass
    class BACKEND backendClass
    class FIREBASE_EXT externalClass