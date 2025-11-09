import os
from flask import current_app, url_for
from flask_mail import Message

from app.extensions import mail


def send_email(subject: str, recipients: list[str], html_body: str) -> None:
    # Check if using Resend API (free email service)
    resend_api_key = os.environ.get("RESEND_API_KEY")
    
    if resend_api_key:
        # Use Resend (free, no SMTP needed)
        import resend
        resend.api_key = resend_api_key
        
        params = {
            "from": os.environ.get("MAIL_DEFAULT_SENDER", "PulseWatch <onboarding@resend.dev>"),
            "to": recipients,
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)
    else:
        # Fall back to Flask-Mail (SMTP)
        msg = Message(subject=subject, recipients=recipients)
        msg.html = html_body
        mail.send(msg)


def send_reset_email(user) -> None:
    token = user.generate_reset_token()
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    subject = "PulseWatch Password Reset"
    html_body = f"""
        <p>Hello {user.name},</p>
        <p>You requested a password reset for your PulseWatch account.</p>
        <p><a href='{reset_url}'>Click here to reset your password</a>. This link expires in 1 hour.</p>
        <p>If you did not request this change, you can safely ignore this email.</p>
        <p>— PulseWatch Team</p>
    """
    send_email(subject, [user.email], html_body)


def send_verification_email(user, code: str) -> None:
    subject = "Verify your PulseWatch email"
    html_body = f"""
        <p>Hello {user.name},</p>
        <p>Thanks for creating a PulseWatch account. Use the verification code below to activate your account:</p>
        <p style='font-size: 22px; letter-spacing: 0.3em; font-weight: bold; color: #4f46e5;'>{code}</p>
        <p>This code expires in 60 minutes.</p>
        <p>If you didn't sign up, you can ignore this email.</p>
        <p>— PulseWatch Team</p>
    """
    send_email(subject, [user.email], html_body)
