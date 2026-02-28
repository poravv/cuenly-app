"""
Modelos para el sistema de suscripciones y pagos recurrentes con Pagopar.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class BillingPeriod(str, Enum):
    """Periodos de facturación disponibles."""
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class SubscriptionStatus(str, Enum):
    """Estados posibles de una suscripción."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TransactionStatus(str, Enum):
    """Estados de transacciones de pago."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class PlanCode(str, Enum):
    """Códigos de planes disponibles."""
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ============================================================================
# Modelos de Base de Datos
# ============================================================================

class Plan(BaseModel):
    """Modelo de plan de suscripción."""
    code: PlanCode
    name: str
    description: str
    amount: float = Field(..., ge=0, description="Monto en PYG")
    currency: str = Field(default="PYG")
    billing_period: BillingPeriod = Field(default=BillingPeriod.MONTHLY)
    features: Dict[str, Any] = Field(default_factory=dict)
    active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class Subscription(BaseModel):
    """Modelo de suscripción de usuario."""
    user_email: str
    pagopar_user_id: Optional[str] = None  # identificador en Pagopar
    plan_id: Optional[str] = None  # ObjectId del plan
    plan_code: PlanCode
    plan_name: str
    plan_price: float = Field(..., ge=0)
    currency: str = Field(default="PYG")
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    next_billing_date: Optional[datetime] = None
    last_billing_date: Optional[datetime] = None
    retry_count: int = Field(default=0, ge=0)
    last_retry_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class PaymentMethod(BaseModel):
    """Modelo de método de pago catastrado."""
    user_email: str
    pagopar_user_id: str
    provider: str = Field(default="Bancard")
    # No guardamos alias_token porque es temporal (15 min)
    # Se obtiene mediante list_cards justo antes de cobrar
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


class SubscriptionTransaction(BaseModel):
    """Modelo de transacción de pago de suscripción."""
    subscription_id: str  # ObjectId
    user_email: str
    amount: float = Field(..., ge=0)
    currency: str = Field(default="PYG")
    status: TransactionStatus
    pagopar_order_hash: Optional[str] = None
    pagopar_order_id: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int = Field(default=1, ge=1)
    created_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


# ============================================================================
# DTOs para API
# ============================================================================

class PlanResponse(BaseModel):
    """Response DTO para plan."""
    id: str
    code: str
    name: str
    description: str
    amount: float
    currency: str
    billing_period: str
    features: Dict[str, Any]
    active: bool


class SubscribeRequest(BaseModel):
    """Request para iniciar suscripción."""
    plan_code: PlanCode
    provider: str = Field(default="Bancard", description="Proveedor de pago (Bancard o uPay)")
    use_existing_card: bool = Field(default=False, description="Intentar usar tarjeta existente")

    class Config:
        use_enum_values = True


class SubscribeResponse(BaseModel):
    """Response después de iniciar suscripción."""
    form_id: Optional[str] = None
    pagopar_user_id: str
    message: str
    subscription_active: bool = False # Flag para indicar si se activó directamente


class ConfirmCardRequest(BaseModel):
    """Request para confirmar tarjeta catastrada."""
    pagopar_user_id: Optional[str] = None


class SubscriptionResponse(BaseModel):
    """Response con detalles de suscripción."""
    id: str
    user_email: str
    plan_code: str
    plan_name: str
    plan_price: float
    currency: str
    status: str
    next_billing_date: Optional[str] = None
    last_billing_date: Optional[str] = None
    has_payment_method: bool
    created_at: str


class PaymentMethodResponse(BaseModel):
    """Response con método de pago."""
    provider: str
    last_four_digits: Optional[str] = None
    card_type: Optional[str] = None
    created_at: str


class TransactionResponse(BaseModel):
    """Response con transacción."""
    id: str
    amount: float
    currency: str
    status: str
    pagopar_order_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str


class CancelSubscriptionRequest(BaseModel):
    """Request para cancelar suscripción."""
    reason: Optional[str] = None


class UpdateSubscriptionStatusRequest(BaseModel):
    """Request admin para cambiar estado de suscripción."""
    status: SubscriptionStatus

    class Config:
        use_enum_values = True
