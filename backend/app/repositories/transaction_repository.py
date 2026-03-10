from datetime import datetime
from typing import List, Optional, Dict, Any
from pymongo import MongoClient
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class TransactionRepository:
    _indexes_ensured: bool = False

    def __init__(self, conn_str: Optional[str] = None, db_name: Optional[str] = None):
        self.conn_str = conn_str or settings.MONGODB_URL
        self.db_name = db_name or settings.MONGODB_DATABASE
        self._client: Optional[MongoClient] = None

    def _get_db(self):
        if not self._client:
            self._client = MongoClient(self.conn_str, serverSelectionTimeoutMS=60000)
        return self._client[self.db_name]

    @property
    def transactions_collection(self):
        db = self._get_db()
        if not TransactionRepository._indexes_ensured:
            self._create_indexes(db)
        return db.transactions

    @classmethod
    def _create_indexes(cls, db: Any) -> None:
        try:
            col = db.transactions
            col.create_index("user_email")
            col.create_index("created_at")
            col.create_index([("user_email", 1), ("created_at", -1)])
            col.create_index("status")
            cls._indexes_ensured = True
            logger.info("TransactionRepository indexes ensured")
        except Exception as e:
            logger.warning(f"Could not create transaction indexes: {e}")

    async def log_transaction(self, 
                            user_email: str, 
                            amount: float, 
                            currency: str, 
                            status: str, 
                            provider: str = "pagopar",
                            reference: str = "",
                            response_data: Dict = None,
                            subscription_id: str = None) -> bool:
        """
        Log a payment transaction (success or failure).
        Status: 'success', 'failed', 'pending'
        """
        try:
            doc = {
                "user_email": user_email,
                "amount": amount,
                "currency": currency,
                "status": status,
                "provider": provider,
                "reference": reference, # e.g. order hash
                "response_data": response_data, # full pagopar response
                "subscription_id": subscription_id,
                "created_at": datetime.utcnow()
            }
            res = self.transactions_collection.insert_one(doc)
            return bool(res.inserted_id)
        except Exception as e:
            logger.error(f"Error logging transaction: {e}")
            return False

    async def get_user_transactions(self, user_email: str, limit: int = 50) -> List[Dict]:
        try:
            return list(self.transactions_collection.find(
                {"user_email": user_email},
                {"_id": 0}
            ).sort("created_at", -1).limit(limit))
        except Exception:
            return []
