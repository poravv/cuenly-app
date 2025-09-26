// Inicialización de MongoDB para CuenlyApp
// Este script se ejecuta automáticamente al crear el contenedor

// Cambiar a la base de datos principal
db = db.getSiblingDB('cuenlyapp_warehouse');

print('🔧 Inicializando base de datos cuenlyapp_warehouse...');

// Colección legacy 'facturas_completas' eliminada: v2 (invoice_headers/items) es la única fuente

// Crear colección para logs de procesamiento (idempotente)
try {
  db.createCollection('processing_logs', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['timestamp', 'action', 'status'],
        properties: {
          timestamp: {
            bsonType: 'date',
            description: 'Fecha y hora del evento'
          },
          action: {
            bsonType: 'string',
            enum: ['PROCESS_EMAILS', 'EXPORT_EXCEL', 'EXPORT_MONGODB', 'MANUAL_UPLOAD'],
            description: 'Tipo de acción realizada'
          },
          status: {
            bsonType: 'string',
            enum: ['SUCCESS', 'ERROR', 'WARNING'],
            description: 'Estado del procesamiento'
          }
        }
      }
    }
  });

  // Índices para logs
  db.processing_logs.createIndex({ 'timestamp': -1 });
  db.processing_logs.createIndex({ 'action': 1, 'timestamp': -1 });
  
  print('✅ Colección processing_logs creada');
} catch (e) {
  print('⚠️ processing_logs ya existe: ' + e.message);
}

// Crear colección para estadísticas mensuales (materializada) (idempotente)
try {
  db.createCollection('monthly_stats');
  db.monthly_stats.createIndex({ 'year_month': 1 }, { unique: true });
  print('✅ Colección monthly_stats creada');
} catch (e) {
  print('⚠️ monthly_stats ya existe: ' + e.message);
}

print('✅ Colecciones auxiliares creadas');

// Insertar documento de configuración inicial (idempotente)
try {
  const existingConfig = db.system_config.findOne({ _id: 'app_config' });
  if (!existingConfig) {
    db.system_config.insertOne({
      _id: 'app_config',
      version: '2.0.0',
      created_at: new Date(),
      features: {
        mongodb_primary: true,
        excel_export_enabled: true,
        auto_export_excel: true,
        retention_days: 365
      },
      indexes_created: true,
      last_updated: new Date()
    });
    print('✅ Configuración inicial guardada');
  } else {
    print('⚠️ Configuración ya existe, actualizando timestamp...');
    db.system_config.updateOne(
      { _id: 'app_config' },
      { $set: { last_updated: new Date() } }
    );
  }
} catch (e) {
  print('⚠️ Error en configuración: ' + e.message);
}

// ------------------------------
// Nuevas colecciones: cabecera y detalle
// ------------------------------
try {
  db.createCollection('invoice_headers');
  db.invoice_headers.createIndex({ _id: 1 }, { unique: true });
  db.invoice_headers.createIndex({ 'emisor.ruc': 1, 'fecha_emision': -1 });
  db.invoice_headers.createIndex({ mes_proceso: 1 });
  db.invoice_headers.createIndex({ owner_email: 1 }); // ✅ Índice multi-tenant
  print('✅ Colección invoice_headers lista');
} catch (e) { 
  print('⚠️ invoice_headers ya existe o error: ' + e.message);
}

try {
  db.createCollection('invoice_items');
  db.invoice_items.createIndex({ header_id: 1, linea: 1 }, { unique: true });
  print('✅ Colección invoice_items lista');
} catch (e) { 
  print('⚠️ invoice_items ya existe o error: ' + e.message);
}

// Crear colección de usuarios autenticados
try {
  db.createCollection('auth_users', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['email', 'uid', 'role', 'status'],
        properties: {
          email: {
            bsonType: 'string',
            pattern: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            description: 'Email del usuario (único)'
          },
          uid: {
            bsonType: 'string',
            description: 'UID de Firebase'
          },
          name: {
            bsonType: 'string',
            description: 'Nombre del usuario'
          },
          picture: {
            bsonType: 'string',
            description: 'URL de la foto de perfil'
          },
          role: {
            bsonType: 'string',
            enum: ['admin', 'user'],
            description: 'Rol del usuario (admin o user)'
          },
          status: {
            bsonType: 'string',
            enum: ['active', 'suspended'],
            description: 'Estado del usuario (activo o suspendido)'
          },
          created_at: {
            bsonType: 'date',
            description: 'Fecha de creación del usuario'
          },
          last_login: {
            bsonType: 'date',
            description: 'Último login del usuario'
          },
          is_trial_user: {
            bsonType: 'bool',
            description: 'Si es usuario de prueba'
          },
          trial_expires_at: {
            bsonType: 'date',
            description: 'Fecha de expiración del trial'
          },
          ai_invoices_processed: {
            bsonType: 'int',
            minimum: 0,
            description: 'Número de facturas procesadas con IA'
          },
          ai_invoices_limit: {
            bsonType: 'int',
            minimum: -1,
            description: 'Límite de facturas con IA (-1 = sin límite)'
          },
          email_processing_start_date: {
            bsonType: 'date',
            description: 'Fecha desde la cual procesar correos'
          }
        }
      }
    }
  });
  
  // Crear índices para usuarios
  db.auth_users.createIndex({ email: 1 }, { unique: true });
  db.auth_users.createIndex({ uid: 1 });
  db.auth_users.createIndex({ role: 1 });
  db.auth_users.createIndex({ status: 1 });
  db.auth_users.createIndex({ trial_expires_at: 1 });
  db.auth_users.createIndex({ ai_invoices_processed: 1 });
  db.auth_users.createIndex({ is_trial_user: 1 });
  db.auth_users.createIndex({ created_at: -1 });
  
  print('✅ Colección auth_users configurada');
  
} catch (e) { 
  print('⚠️ auth_users ya existe o error: ' + e.message);
}

// Inicializar usuario administrador principal
try {
  const adminEmail = 'andyvercha@gmail.com';
  const existingAdmin = db.auth_users.findOne({ email: adminEmail });
  
  if (!existingAdmin) {
    // Crear usuario admin inicial
    db.auth_users.insertOne({
      email: adminEmail,
      uid: 'admin-init-' + new Date().getTime(), // UID temporal hasta que se autentique por primera vez
      name: 'Andy Verchá',
      picture: '',
      role: 'admin',
      status: 'active',
      created_at: new Date(),
      last_login: null,
      is_trial_user: false, // Admin no tiene limitaciones de trial
      trial_expires_at: null,
      ai_invoices_processed: 0,
      ai_invoices_limit: -1, // Sin límite
      email_processing_start_date: new Date()
    });
    print('✅ Usuario administrador creado: ' + adminEmail);
  } else {
    // Si ya existe, asegurar que tenga rol admin y no sea trial
    db.auth_users.updateOne(
      { email: adminEmail },
      { 
        $set: { 
          role: 'admin',
          status: 'active',
          is_trial_user: false,
          ai_invoices_limit: -1,
          last_updated: new Date()
        }
      }
    );
    print('✅ Usuario administrador actualizado: ' + adminEmail);
  }
} catch (e) {
  print('⚠️ Error inicializando admin: ' + e.message);
}

// ==============================
// PLANES Y SUSCRIPCIONES
// ==============================

// Crear colección de planes
try {
  db.createCollection('subscription_plans', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['name', 'code', 'price', 'currency', 'billing_period', 'features', 'status', 'created_at'],
        properties: {
          name: {
            bsonType: 'string',
            description: 'Nombre del plan'
          },
          code: {
            bsonType: 'string',
            description: 'Código único del plan'
          },
          description: {
            bsonType: 'string',
            description: 'Descripción del plan'
          },
          price: {
            bsonType: 'double',
            minimum: 0,
            description: 'Precio del plan'
          },
          currency: {
            bsonType: 'string',
            enum: ['USD', 'EUR', 'PYG'],
            description: 'Moneda del precio'
          },
          billing_period: {
            bsonType: 'string',
            enum: ['monthly', 'yearly', 'one_time'],
            description: 'Período de facturación'
          },
          features: {
            bsonType: 'object',
            required: ['ai_invoices_limit', 'email_processing', 'export_formats'],
            properties: {
              ai_invoices_limit: {
                bsonType: 'int',
                minimum: -1,
                description: 'Límite de facturas con IA (-1 = sin límite)'
              },
              email_processing: {
                bsonType: 'bool',
                description: 'Procesamiento automático de emails'
              },
              export_formats: {
                bsonType: 'array',
                items: {
                  bsonType: 'string',
                  enum: ['excel', 'csv', 'json', 'pdf']
                },
                description: 'Formatos de exportación disponibles'
              },
              api_access: {
                bsonType: 'bool',
                description: 'Acceso a API externa'
              },
              priority_support: {
                bsonType: 'bool',
                description: 'Soporte prioritario'
              },
              custom_templates: {
                bsonType: 'bool',
                description: 'Plantillas personalizadas'
              }
            }
          },
          status: {
            bsonType: 'string',
            enum: ['active', 'inactive', 'deprecated'],
            description: 'Estado del plan'
          },
          is_popular: {
            bsonType: 'bool',
            description: 'Si es el plan más popular'
          },
          sort_order: {
            bsonType: 'int',
            description: 'Orden de visualización'
          },
          created_at: {
            bsonType: 'date',
            description: 'Fecha de creación'
          },
          updated_at: {
            bsonType: 'date',
            description: 'Fecha de última actualización'
          }
        }
      }
    }
  });
  
  // Índices para planes
  db.subscription_plans.createIndex({ code: 1 }, { unique: true });
  db.subscription_plans.createIndex({ status: 1, sort_order: 1 });
  db.subscription_plans.createIndex({ billing_period: 1, status: 1 });
  
  print('✅ Colección subscription_plans configurada');
  
} catch (e) { 
  print('⚠️ subscription_plans ya existe o error: ' + e.message);
}

// Crear colección de suscripciones de usuarios
try {
  db.createCollection('user_subscriptions', {
    validator: {
      $jsonSchema: {
        bsonType: 'object',
        required: ['user_email', 'plan_code', 'plan_price', 'currency', 'status', 'created_at'],
        properties: {
          user_email: {
            bsonType: 'string',
            pattern: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            description: 'Email del usuario'
          },
          plan_code: {
            bsonType: 'string',
            description: 'Código del plan suscrito'
          },
          plan_name: {
            bsonType: 'string',
            description: 'Nombre del plan al momento de la suscripción'
          },
          plan_price: {
            bsonType: 'double',
            minimum: 0,
            description: 'Precio pagado por el plan'
          },
          currency: {
            bsonType: 'string',
            enum: ['USD', 'EUR', 'PYG'],
            description: 'Moneda del pago'
          },
          billing_period: {
            bsonType: 'string',
            enum: ['monthly', 'yearly', 'one_time'],
            description: 'Período de facturación'
          },
          status: {
            bsonType: 'string',
            enum: ['active', 'cancelled', 'expired', 'pending'],
            description: 'Estado de la suscripción'
          },
          started_at: {
            bsonType: 'date',
            description: 'Fecha de inicio de la suscripción'
          },
          expires_at: {
            bsonType: 'date',
            description: 'Fecha de expiración'
          },
          cancelled_at: {
            bsonType: 'date',
            description: 'Fecha de cancelación'
          },
          payment_method: {
            bsonType: 'string',
            enum: ['credit_card', 'paypal', 'bank_transfer', 'manual'],
            description: 'Método de pago'
          },
          payment_reference: {
            bsonType: 'string',
            description: 'Referencia del pago'
          },
          created_at: {
            bsonType: 'date',
            description: 'Fecha de creación del registro'
          },
          updated_at: {
            bsonType: 'date',
            description: 'Fecha de última actualización'
          }
        }
      }
    }
  });
  
  // Índices para suscripciones
  db.user_subscriptions.createIndex({ user_email: 1, status: 1 });
  db.user_subscriptions.createIndex({ plan_code: 1, created_at: -1 });
  db.user_subscriptions.createIndex({ status: 1, expires_at: 1 });
  db.user_subscriptions.createIndex({ created_at: -1 });
  
  print('✅ Colección user_subscriptions configurada');
  
} catch (e) { 
  print('⚠️ user_subscriptions ya existe o error: ' + e.message);
}

// Insertar planes iniciales
try {
  const existingPlans = db.subscription_plans.countDocuments();
  if (existingPlans === 0) {
    const plans = [
      {
        name: 'Plan Básico',
        code: 'basic',
        description: 'Ideal para emprendedores y pequeños negocios',
        price: 9.99,
        currency: 'USD',
        billing_period: 'monthly',
        features: {
          ai_invoices_limit: 50,
          email_processing: true,
          export_formats: ['excel', 'csv'],
          api_access: false,
          priority_support: false,
          custom_templates: false
        },
        status: 'active',
        is_popular: false,
        sort_order: 1,
        created_at: new Date(),
        updated_at: new Date()
      },
      {
        name: 'Plan Profesional',
        code: 'professional',
        description: 'Para empresas medianas con mayor volumen',
        price: 29.99,
        currency: 'USD',
        billing_period: 'monthly',
        features: {
          ai_invoices_limit: 200,
          email_processing: true,
          export_formats: ['excel', 'csv', 'json'],
          api_access: true,
          priority_support: false,
          custom_templates: true
        },
        status: 'active',
        is_popular: true,
        sort_order: 2,
        created_at: new Date(),
        updated_at: new Date()
      },
      {
        name: 'Plan Empresarial',
        code: 'enterprise',
        description: 'Para grandes empresas sin limitaciones',
        price: 99.99,
        currency: 'USD',
        billing_period: 'monthly',
        features: {
          ai_invoices_limit: -1,
          email_processing: true,
          export_formats: ['excel', 'csv', 'json', 'pdf'],
          api_access: true,
          priority_support: true,
          custom_templates: true
        },
        status: 'active',
        is_popular: false,
        sort_order: 3,
        created_at: new Date(),
        updated_at: new Date()
      }
    ];
    
    db.subscription_plans.insertMany(plans);
    print('✅ Planes iniciales creados: ' + plans.length + ' planes');
  } else {
    print('⚠️ Ya existen planes en la base de datos: ' + existingPlans);
  }
} catch (e) {
  print('⚠️ Error insertando planes iniciales: ' + e.message);
}

print('==================================');
print('✅ MongoDB inicializado correctamente para CuenlyApp');
print('📊 Base de datos: cuenlyapp_warehouse');
print('👤 Usuario: root (sin usuario adicional por simplicidad)');
print('📑 Colecciones creadas: processing_logs, monthly_stats, invoice_headers, invoice_items, auth_users, subscription_plans, user_subscriptions');
print('🔍 Índices optimizados aplicados');
print('💳 Planes de suscripción inicializados');
print('⚙️ Configuración inicial completada');
print('🎯 Sistema listo para aceptar conexiones de la aplicación');
print('==================================');
