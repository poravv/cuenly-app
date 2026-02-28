"""
Servicio de notificaciones por email (SMTP).

Envía emails transaccionales a usuarios: confirmación de pago,
fallo de pago, cancelación de suscripción, etc.

Requiere configuración SMTP en variables de entorno:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL
Si SMTP_HOST no está configurado, los envíos se loguean pero no se envían.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Servicio para enviar notificaciones por email vía SMTP."""

    def _is_configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)

    def _send(self, to_email: str, subject: str, html_body: str) -> bool:
        """Envía un email. Retorna True si se envió, False si falló o no está configurado."""
        if not self._is_configured():
            logger.info(f"[EMAIL-SKIP] SMTP no configurado. Destinatario: {to_email}, Asunto: {subject}")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)

            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
            server.quit()

            logger.info(f"[EMAIL-OK] Enviado a {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"[EMAIL-FAIL] Error enviando a {to_email}: {e}")
            return False

    # =========================================================================
    # Templates de billing
    # =========================================================================

    def send_payment_success(
        self,
        to_email: str,
        plan_name: str,
        amount: int,
        next_billing_date: str
    ) -> bool:
        """Notifica pago exitoso de suscripción."""
        subject = f"Pago confirmado - {plan_name}"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Pago Confirmado</h1>
            </div>
            <div style="background: #fff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p>Hola,</p>
                <p>Tu pago de suscripción ha sido procesado exitosamente.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 10px; color: #6b7280;">Plan:</td>
                        <td style="padding: 10px; font-weight: bold;">{plan_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; color: #6b7280;">Monto:</td>
                        <td style="padding: 10px; font-weight: bold;">{amount:,} PYG</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; color: #6b7280;">Próximo cobro:</td>
                        <td style="padding: 10px; font-weight: bold;">{next_billing_date}</td>
                    </tr>
                </table>
                <p style="color: #6b7280; font-size: 14px;">Si tienes preguntas, contáctanos respondiendo a este email.</p>
            </div>
            <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 20px;">CuenlyApp - Gestión Inteligente de Facturas</p>
        </div>
        """
        return self._send(to_email, subject, html)

    def send_payment_failed(
        self,
        to_email: str,
        plan_name: str,
        reason: str,
        retry_number: int,
        next_retry_date: str
    ) -> bool:
        """Notifica fallo de pago con información de reintento."""
        subject = f"Problema con tu pago - {plan_name}"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #f59e0b; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Problema con tu Pago</h1>
            </div>
            <div style="background: #fff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p>Hola,</p>
                <p>No pudimos procesar el cobro de tu suscripción <strong>{plan_name}</strong>.</p>
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <strong>Motivo:</strong> {reason}
                </div>
                <p>Reintentaremos el cobro automáticamente el <strong>{next_retry_date}</strong> (intento {retry_number} de 3).</p>
                <p><strong>¿Qué puedes hacer?</strong></p>
                <ul>
                    <li>Verificar que tu tarjeta tenga fondos suficientes</li>
                    <li>Actualizar tu método de pago desde la app</li>
                    <li>Contactarnos si necesitas ayuda</li>
                </ul>
                <p style="color: #6b7280; font-size: 14px;">Tu suscripción sigue activa, pero si no se resuelve el pago, podría ser cancelada.</p>
            </div>
            <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 20px;">CuenlyApp - Gestión Inteligente de Facturas</p>
        </div>
        """
        return self._send(to_email, subject, html)

    def send_subscription_cancelled(
        self,
        to_email: str,
        plan_name: str,
        reason: str
    ) -> bool:
        """Notifica cancelación de suscripción por fallos de pago."""
        subject = f"Suscripción cancelada - {plan_name}"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #ef4444; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Suscripción Cancelada</h1>
            </div>
            <div style="background: #fff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p>Hola,</p>
                <p>Lamentamos informarte que tu suscripción <strong>{plan_name}</strong> ha sido cancelada.</p>
                <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <strong>Motivo:</strong> {reason}
                </div>
                <p>Tu cuenta seguirá activa, pero no podrás procesar nuevas facturas hasta que reactives tu suscripción.</p>
                <p><strong>Para reactivar:</strong></p>
                <ol>
                    <li>Ingresa a CuenlyApp</li>
                    <li>Ve a Mi Suscripción</li>
                    <li>Selecciona un plan y agrega un método de pago</li>
                </ol>
                <p style="color: #6b7280; font-size: 14px;">Si crees que esto es un error, contáctanos respondiendo a este email.</p>
            </div>
            <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 20px;">CuenlyApp - Gestión Inteligente de Facturas</p>
        </div>
        """
        return self._send(to_email, subject, html)
