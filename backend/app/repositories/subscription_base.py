"""
Base mixin for SubscriptionRepository: init, DB access, collection properties, indexes, date utils.
"""
import calendar
from datetime import datetime
from typing import Optional
import logging

from app.config.settings import settings
from app.core.database import get_mongo_client

logger = logging.getLogger(__name__)


class _SubscriptionBase:
    _indexes_ensured: bool = False

    def __init__(self, conn_str: Optional[str] = None, db_name: Optional[str] = None):
        self.db_name = db_name or settings.MONGODB_DATABASE

    def _get_db(self):
        return get_mongo_client()[self.db_name]

    @property
    def plans_collection(self):
        return self._get_db().subscription_plans

    @property
    def subscriptions_collection(self):
        return self._get_db().user_subscriptions

    @property
    def users_collection(self):
        return self._get_db().auth_users

    @property
    def payment_methods_collection(self):
        return self._get_db().payment_methods

    @property
    def transactions_collection(self):
        return self._get_db().subscription_transactions

    def _ensure_indexes(self):
        if _SubscriptionBase._indexes_ensured:
            return
        try:
            self.subscriptions_collection.create_index([("user_email", 1)])
            self.subscriptions_collection.create_index([("status", 1), ("next_billing_date", 1)])
            self.subscriptions_collection.create_index([("pagopar_user_id", 1)])

            self.payment_methods_collection.create_index([("user_email", 1)], unique=True)
            self.payment_methods_collection.create_index([("pagopar_user_id", 1)])

            self.transactions_collection.create_index([("subscription_id", 1)])
            self.transactions_collection.create_index([("user_email", 1)])
            self.transactions_collection.create_index([("created_at", -1)])
            self.transactions_collection.create_index([
                ("user_email", 1), ("status", 1), ("created_at", -1)
            ])

            _SubscriptionBase._indexes_ensured = True
            logger.info("Índices de suscripciones creados/verificados")
        except Exception as e:
            logger.warning(f"Error creando índices: {e}")

    @staticmethod
    def calculate_next_billing_date(from_date: datetime, billing_day: int) -> datetime:
        """
        Próxima fecha de cobro por aniversario.
        Si billing_day=31 y el mes tiene 28 días, usa día 28.
        """
        if from_date.month == 12:
            next_month, next_year = 1, from_date.year + 1
        else:
            next_month, next_year = from_date.month + 1, from_date.year
        max_day = calendar.monthrange(next_year, next_month)[1]
        actual_day = min(billing_day, max_day)
        return datetime(next_year, next_month, actual_day, 0, 0, 0)
