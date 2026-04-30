"""
Facade de SubscriptionRepository.

Todos los call sites existentes (27+) importan este módulo sin cambios.
La lógica vive en los mixins especializados:

  subscription_base.py              — init, DB, colecciones, índices, fechas
  subscription_payment_mixin.py     — métodos de pago + billing recurrente
  subscription_transaction_mixin.py — registro e historial de transacciones
  subscription_plan_mixin.py        — CRUD de planes
  subscription_subscriptions_mixin.py — ciclo de vida de suscripciones
"""

from app.repositories.subscription_base import _SubscriptionBase
from app.repositories.subscription_payment_mixin import _PaymentMixin
from app.repositories.subscription_transaction_mixin import _TransactionMixin
from app.repositories.subscription_plan_mixin import _PlanMixin
from app.repositories.subscription_subscriptions_mixin import _SubscriptionsMixin


class SubscriptionRepository(
    _SubscriptionBase,
    _PlanMixin,
    _PaymentMixin,
    _TransactionMixin,
    _SubscriptionsMixin,
):
    """Repositorio de suscripciones — hereda todos los mixins."""
    pass
