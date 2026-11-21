import logging
import smtplib
from email.message import EmailMessage
import requests

from app.core.config import (
    FRONTEND_APP_URL,
    RESEND_API_KEY,
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger("vektor.email")


def send_recovery_email(
    to_email: str,
    full_name: str,
    username: str,
    raw_token: str,
) -> dict:
    """
    Envía correo de recuperación de usuario y contraseña.
    Prioridad:
    1) Resend API (si RESEND_API_KEY está configurada)
    2) SMTP estándar (si SMTP_HOST y SMTP_USER están configurados)
    3) Fallback desarrollo: log en consola del backend (costo US$ 0)
    """
    reset_link = f"{FRONTEND_APP_URL}/?reset_token={raw_token}"
    subject = "VektorTerminal — Recuperación de usuario y contraseña"
    text_body = (
        f"Hola {full_name},\n\n"
        f"Recibimos una solicitud para recuperar el acceso a tu cuenta en VektorTerminal.\n"
        f"Tu nombre de usuario registrado es: {username}\n\n"
        f"Para definir una nueva contraseña (válido por 15 minutos), ingresá al siguiente enlace:\n"
        f"{reset_link}\n\n"
        f"O pegá este código de recuperación en la pantalla de inicio de sesión:\n"
        f"{raw_token}\n\n"
        f"Si no solicitaste este cambio, podés ignorar este mensaje."
    )

    if RESEND_API_KEY:
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": SMTP_FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "text": text_body,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return {"delivery": "resend"}
            logger.warning("Resend devolvió status %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Error enviando vía Resend: %s", exc)

    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM_EMAIL
            msg["To"] = to_email
            msg.set_content(text_body)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            return {"delivery": "smtp"}
        except Exception as exc:
            logger.error("Error enviando vía SMTP: %s", exc)

    # Modo desarrollo local sin configuración SMTP/Resend
    print("\n" + "=" * 68)
    print(f"[VEKTOR RECOVERY EMAIL -> {to_email}]")
    print(f"Usuario registrado : {username}")
    print(f"Código / Token     : {raw_token}")
    print(f"Enlace directo     : {reset_link}")
    print("=" * 68 + "\n")
    return {"delivery": "console"}