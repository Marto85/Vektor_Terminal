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


def is_email_delivery_configured() -> bool:
    return bool(RESEND_API_KEY or (SMTP_HOST and SMTP_USER and SMTP_PASSWORD))


def _deliver_email(
    to_email: str,
    subject: str,
    text_body: str,
    console_tag: str,
    console_lines: list[str],
) -> dict:
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

    print("\n" + "=" * 68)
    print(f"[{console_tag} -> {to_email}]")
    for line in console_lines:
        print(line)
    print("=" * 68 + "\n")
    return {"delivery": "console"}


def send_recovery_email(
    to_email: str,
    full_name: str,
    username: str,
    raw_token: str,
) -> dict:
    """
    Envía correo de recuperación de usuario y contraseña.
    Prioridad: Resend API -> SMTP estándar -> consola local (US$ 0).
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
    return _deliver_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        console_tag="VEKTOR RECOVERY EMAIL",
        console_lines=[
            f"Usuario registrado : {username}",
            f"Código / Token     : {raw_token}",
            f"Enlace directo     : {reset_link}",
        ],
    )


def send_verification_email(
    to_email: str,
    full_name: str,
    username: str,
    raw_token: str,
) -> dict:
    """Envía enlace de confirmación de correo electrónico al registrarse."""
    verify_link = f"{FRONTEND_APP_URL}/?verify_token={raw_token}"
    subject = "VektorTerminal — Confirmá tu correo electrónico"
    text_body = (
        f"Hola {full_name},\n\n"
        f"Gracias por registrarte en VektorTerminal (usuario: {username}).\n\n"
        f"Para activar tu cuenta (válido por 24 horas), confirmá tu correo haciendo clic acá:\n"
        f"{verify_link}\n\n"
        f"Si no creaste esta cuenta, podés ignorar este mensaje."
    )
    return _deliver_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        console_tag="VEKTOR VERIFY EMAIL",
        console_lines=[
            f"Usuario registrado : {username}",
            f"Token verificación : {raw_token}",
            f"Enlace directo     : {verify_link}",
        ],
    )
