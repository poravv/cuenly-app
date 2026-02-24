from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class ProcessedEmail(BaseModel):
    """
    Registro de correo procesado en MongoDB para soportar escalado horizontal.
    Reemplaza al archivo processed_emails.json local.
    """
    model_config = ConfigDict(populate_by_name=True)

    # El ID será compuesto: owner_email::account_email::email_uid
    id: str = Field(alias="_id")
    
    owner_email: str
    account_email: str
    email_uid: str
    message_id: Optional[str] = None

    
    status: str = "success"  # success, xml, pdf, skipped_ai_limit, error, missing_metadata
    reason: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    email_date: Optional[datetime] = None
    
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadatos para retries
    retry_count: int = 0
    last_retry_at: Optional[datetime] = None
    
    # TTL index support if needed (optional)
    expire_at: Optional[datetime] = None
