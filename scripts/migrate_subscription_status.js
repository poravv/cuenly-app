// Migration: Normalizar status de suscripciones a minúsculas
// Ejecutar con: mongosh <connection_string> scripts/migrate_subscription_status.js
// O en Docker: docker compose exec mongodb mongosh cuenly scripts/migrate_subscription_status.js

print("=== Migración: Normalizar subscription status a minúsculas ===");

// Verificar estado actual
print("\nEstado ANTES de la migración:");
print("  ACTIVE:", db.user_subscriptions.countDocuments({ status: "ACTIVE" }));
print("  active:", db.user_subscriptions.countDocuments({ status: "active" }));
print("  PAST_DUE:", db.user_subscriptions.countDocuments({ status: "PAST_DUE" }));
print("  past_due:", db.user_subscriptions.countDocuments({ status: "past_due" }));
print("  CANCELLED:", db.user_subscriptions.countDocuments({ status: "CANCELLED" }));
print("  cancelled:", db.user_subscriptions.countDocuments({ status: "cancelled" }));
print("  EXPIRED:", db.user_subscriptions.countDocuments({ status: "EXPIRED" }));
print("  expired:", db.user_subscriptions.countDocuments({ status: "expired" }));

// Migrar
var r1 = db.user_subscriptions.updateMany({ status: "ACTIVE" }, { $set: { status: "active" } });
print("\nACTIVE -> active: " + r1.modifiedCount + " documentos actualizados");

var r2 = db.user_subscriptions.updateMany({ status: "PAST_DUE" }, { $set: { status: "past_due" } });
print("PAST_DUE -> past_due: " + r2.modifiedCount + " documentos actualizados");

var r3 = db.user_subscriptions.updateMany({ status: "CANCELLED" }, { $set: { status: "cancelled" } });
print("CANCELLED -> cancelled: " + r3.modifiedCount + " documentos actualizados");

var r4 = db.user_subscriptions.updateMany({ status: "EXPIRED" }, { $set: { status: "expired" } });
print("EXPIRED -> expired: " + r4.modifiedCount + " documentos actualizados");

// Verificar estado final
print("\nEstado DESPUÉS de la migración:");
print("  active:", db.user_subscriptions.countDocuments({ status: "active" }));
print("  past_due:", db.user_subscriptions.countDocuments({ status: "past_due" }));
print("  cancelled:", db.user_subscriptions.countDocuments({ status: "cancelled" }));
print("  expired:", db.user_subscriptions.countDocuments({ status: "expired" }));

var total = r1.modifiedCount + r2.modifiedCount + r3.modifiedCount + r4.modifiedCount;
print("\n=== Total: " + total + " documentos migrados ===");
