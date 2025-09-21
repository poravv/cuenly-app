// MongoDB Performance Indexes
// Ejecutar después de la inicialización

db = db.getSiblingDB('cuenlyapp_warehouse');

// 1. Índices para email_configs (consulta frecuente)
db.email_configs.createIndex({ "owner_email": 1 });
db.email_configs.createIndex({ "enabled": 1 });
db.email_configs.createIndex({ "owner_email": 1, "enabled": 1 });

// 2. Índices para invoice_headers
db.invoice_headers.createIndex({ "owner_email": 1 });
db.invoice_headers.createIndex({ "created_at": -1 });
db.invoice_headers.createIndex({ "owner_email": 1, "created_at": -1 });

// 3. Índices para usuarios y trials
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "trial_start_date": 1 });
db.users.createIndex({ "ai_invoices_processed": 1 });

// 4. Índices compuestos para queries complejas
db.invoice_headers.createIndex({ 
    "owner_email": 1, 
    "processing_type": 1,
    "created_at": -1 
});

print("✅ Índices de rendimiento creados exitosamente");