// Inicialización de MongoDB para CuenlyApp
// Este script se ejecuta automáticamente al crear el contenedor

// Cambiar a la base de datos principal
db = db.getSiblingDB('cuenlyapp_warehouse');

print('🔧 Inicializando base de datos cuenlyapp_warehouse...');

// Crear la colección principal con validación de esquema
db.createCollection('facturas_completas', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['_id', 'factura_id', 'metadata', 'factura', 'emisor', 'montos'],
      properties: {
        _id: {
          bsonType: 'string',
          description: 'ID único de la factura'
        },
        factura_id: {
          bsonType: 'string',
          description: 'ID alternativo para búsquedas'
        },
        metadata: {
          bsonType: 'object',
          required: ['fecha_procesado', 'fuente'],
          properties: {
            fecha_procesado: {
              bsonType: 'string',
              description: 'Fecha de procesamiento ISO'
            },
            fuente: {
              bsonType: 'string',
              enum: ['XML_NATIVO', 'OPENAI_VISION'],
              description: 'Fuente de extracción de datos'
            },
            calidad_datos: {
              bsonType: 'string',
              enum: ['ALTA', 'MEDIA', 'BAJA'],
              description: 'Evaluación de calidad'
            }
          }
        },
        factura: {
          bsonType: 'object',
          required: ['numero'],
          properties: {
            numero: {
              bsonType: 'string',
              description: 'Número de factura'
            },
            fecha: {
              bsonType: ['string', 'null'],
              description: 'Fecha de factura ISO'
            }
          }
        },
        emisor: {
          bsonType: 'object',
          required: ['ruc'],
          properties: {
            ruc: {
              bsonType: 'string',
              description: 'RUC del emisor'
            },
            nombre: {
              bsonType: 'string',
              description: 'Nombre del emisor'
            }
          }
        },
        montos: {
          bsonType: 'object',
          required: ['monto_total'],
          properties: {
            monto_total: {
              bsonType: 'number',
              minimum: 0,
              description: 'Monto total de la factura'
            }
          }
        }
      }
    }
  }
});

print('✅ Colección facturas_completas creada');

// Crear índices optimizados para consultas frecuentes
db.facturas_completas.createIndex({ 'factura.fecha': 1 });
db.facturas_completas.createIndex({ 'emisor.ruc': 1 });
db.facturas_completas.createIndex({ 'receptor.ruc': 1 });
db.facturas_completas.createIndex({ 'metadata.fecha_procesado': 1 });
db.facturas_completas.createIndex({ 'indices.year_month': 1 });
db.facturas_completas.createIndex({ 'datos_tecnicos.cdc': 1 });

// Índices compuestos para consultas complejas
db.facturas_completas.createIndex({ 'emisor.ruc': 1, 'factura.fecha': -1 });
db.facturas_completas.createIndex({ 'indices.year_month': 1, 'montos.monto_total': -1 });
db.facturas_completas.createIndex({ 'metadata.calidad_datos': 1, 'indices.has_cdc': 1 });

// Índice de texto para búsquedas generales
db.facturas_completas.createIndex({
  'emisor.nombre': 'text',
  'receptor.nombre': 'text',
  'factura.descripcion': 'text',
  'productos.articulo': 'text'
});

print('✅ Índices principales creados');

// Crear colección para logs de procesamiento
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

// Crear colección para estadísticas mensuales (materializada)
db.createCollection('monthly_stats');
db.monthly_stats.createIndex({ 'year_month': 1 }, { unique: true });

print('✅ Colecciones auxiliares creadas');

// Insertar documento de configuración inicial
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
        required: ['email', 'uid'],
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
          created_at: {
            bsonType: 'date',
            description: 'Fecha de creación del usuario'
          },
          last_login: {
            bsonType: 'date',
            description: 'Último login del usuario'
          },
          is_trial: {
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
            minimum: 0,
            description: 'Límite de facturas con IA para usuarios trial'
          }
        }
      }
    }
  });
  
  // Crear índices para usuarios
  db.auth_users.createIndex({ email: 1 }, { unique: true });
  db.auth_users.createIndex({ uid: 1 });
  db.auth_users.createIndex({ trial_expires_at: 1 });
  db.auth_users.createIndex({ ai_invoices_processed: 1 });
  db.auth_users.createIndex({ is_trial: 1 });
  
  print('✅ Colección auth_users configurada');
  
} catch (e) { 
  print('⚠️ auth_users ya existe o error: ' + e.message);
}

print('==================================');
print('✅ MongoDB inicializado correctamente para CuenlyApp');
print('📊 Base de datos: cuenlyapp_warehouse');
print('👤 Usuario: root (sin usuario adicional por simplicidad)');
print('📑 Colecciones creadas: facturas_completas, processing_logs, monthly_stats, invoice_headers, invoice_items, auth_users');
print('🔍 Índices optimizados aplicados');
print('⚙️ Configuración inicial completada');
print('🎯 Sistema listo para aceptar conexiones de la aplicación');
print('==================================');
