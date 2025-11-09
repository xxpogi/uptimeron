from __future__ import annotations

from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError
from flask_wtf import FlaskForm

from app.models import ApiKey


TIMEZONE_CHOICES = [
    ("UTC", "UTC"),
    ("US/Eastern", "US/Eastern"),
    ("US/Central", "US/Central"),
    ("US/Mountain", "US/Mountain"),
    ("US/Pacific", "US/Pacific"),
    ("Europe/London", "Europe/London"),
    ("Europe/Paris", "Europe/Paris"),
    ("Asia/Singapore", "Asia/Singapore"),
    ("Asia/Tokyo", "Asia/Tokyo"),
]


class ProfileForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    timezone = SelectField("Timezone", choices=TIMEZONE_CHOICES, validators=[DataRequired()])
    telegram_chat_id = StringField("Telegram Chat ID", validators=[Length(max=64)])
    submit_profile = SubmitField("Save Profile")


class NotificationForm(FlaskForm):
    channel = SelectField(
        "Channel",
        choices=[("email", "Email"), ("telegram", "Telegram")],
        validators=[DataRequired()],
    )
    destination = StringField("Destination", validators=[DataRequired(), Length(max=255)])
    is_enabled = BooleanField("Enabled", default=True)
    submit_notification = SubmitField("Add Notification")

    def validate_destination(self, field):
        if self.channel.data == "email" and "@" not in field.data:
            raise ValidationError("Please enter a valid email address.")


class ApiKeyForm(FlaskForm):
    name = StringField("Key Name", validators=[DataRequired(), Length(max=120)])
    submit_api_key = SubmitField("Create API Key")


class StatusPageForm(FlaskForm):
    name = StringField("Status Page Name", validators=[DataRequired(), Length(max=120)])
    slug = StringField("Slug", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Description", validators=[Length(max=500)])
    monitors = SelectMultipleField(
        "Monitors",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Select at least one monitor")],
    )
    is_public = BooleanField("Public", default=True)
    submit_status_page = SubmitField("Create Status Page")

    def validate_slug(self, field):
        if " " in field.data:
            raise ValidationError("Slug cannot contain spaces. Use hyphens instead.")
