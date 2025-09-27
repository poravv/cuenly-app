erDiagram
    %% Colecciones principales de MongoDB
    
    AUTH_USERS {
        ObjectId _id PK
        string email UK "Usuario único"
        string name
        string uid "Firebase UID"
        string role "admin/user"
        string status "active/suspended"
        int ai_invoices_processed "Contador IA usado"
        int ai_invoices_limit "Límite IA (-1=ilimitado)"
        boolean is_trial_user
        datetime trial_expires_at
        datetime created_at
        datetime updated_at
        datetime last_login
    }
    
    SUBSCRIPTION_PLANS {
        ObjectId _id PK
        string name "Nombre del plan"
        string description
        float price
        string billing_period "monthly/yearly/one_time"
        int ai_invoices_limit "Límite IA del plan"
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    
    USER_SUBSCRIPTIONS {
        ObjectId _id PK
        string user_email FK "Referencia a AUTH_USERS.email"
        ObjectId plan_id FK "Referencia a SUBSCRIPTION_PLANS._id"
        object plan "Snapshot del plan al suscribirse"
        string status "active/cancelled/expired"
        datetime start_date
        datetime end_date
        string billing_period
        datetime created_at
        datetime updated_at
    }
    
    INVOICE_HEADERS {
        ObjectId _id PK
        string user_email FK "Referencia a AUTH_USERS.email"
        string numero_factura
        datetime fecha_emision
        string ruc_emisor
        string ruc_receptor
        float monto_total
        float iva_5
        float iva_10
        string moneda
        string condicion_operacion
        datetime processed_at
        datetime created_at
    }
    
    INVOICE_ITEMS {
        ObjectId _id PK
        ObjectId header_id FK "Referencia a INVOICE_HEADERS._id"
        string descripcion
        int cantidad
        float precio_unitario
        float precio_total
        int codigo_iva "5/10/exento"
        datetime created_at
    }
    
    EXPORT_TEMPLATES {
        ObjectId _id PK
        string user_email FK "Referencia a AUTH_USERS.email"
        string name
        string description
        array fields "Configuración de campos"
        datetime created_at
        datetime updated_at
    }
    
    EMAIL_CONFIGS {
        ObjectId _id PK
        string user_email FK "Referencia a AUTH_USERS.email"
        string host
        int port
        string username
        string password
        boolean use_tls
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    
    TASKS {
        ObjectId _id PK
        string user_email FK "Referencia a AUTH_USERS.email"
        string task_type "upload/process/email"
        string status "pending/processing/completed/failed"
        object metadata
        datetime created_at
        datetime updated_at
    }
    
    %% Relaciones
    AUTH_USERS ||--o{ USER_SUBSCRIPTIONS : "has"
    SUBSCRIPTION_PLANS ||--o{ USER_SUBSCRIPTIONS : "defines"
    AUTH_USERS ||--o{ INVOICE_HEADERS : "owns"
    INVOICE_HEADERS ||--o{ INVOICE_ITEMS : "contains"
    AUTH_USERS ||--o{ EXPORT_TEMPLATES : "creates"
    AUTH_USERS ||--o{ EMAIL_CONFIGS : "configures"
    AUTH_USERS ||--o{ TASKS : "executes"