# PulseWatch

PulseWatch is a full-featured uptime monitoring platform built with Flask, SQLAlchemy, and Tailwind CSS. It allows teams to track the availability and performance of their web services, receive downtime alerts, and share public status pages.

## Features

- User registration, login, logout, and secure session management with Flask-Login
- Password reset via email with signed tokens
- Dark-mode responsive UI powered by Tailwind CSS and Alpine.js
- Dashboard with real-time uptime metrics and historical charts using Chart.js
- Create, edit, pause, and delete HTTP monitors with flexible polling intervals
- Background scheduler (APScheduler) for continuous uptime checks
- REST API secured via per-user API keys, with rate limiting
- Email and Telegram downtime notifications
- Public status pages for sharing monitor health externally
- Admin area for monitoring platform health (WIP)

## Project Structure

```
.
├── app
│   ├── __init__.py
│   ├── api
│   ├── auth
│   ├── dashboard
│   ├── extensions.py
│   ├── forms
│   ├── models.py
│   ├── scheduler.py
│   ├── settings
│   ├── templates
│   ├── utils
│   └── views
├── config.py
├── migrations
├── requirements.txt
├── run.py
└── README.md
```

## Getting Started

1. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   set FLASK_APP=run.py
   set FLASK_ENV=development
   set SECRET_KEY=change-me
   set DATABASE_URL=sqlite:///pulsewatch.db
   set MAIL_SERVER=smtp.example.com
   set MAIL_PORT=587
   set MAIL_USERNAME=your-user
   set MAIL_PASSWORD=your-pass
   set MAIL_USE_TLS=1
   set TELEGRAM_BOT_TOKEN=your-bot-token
   ```

4. **Initialize the database**
   ```bash
   flask db upgrade
   ```

5. **Run the development server**
   ```bash
   flask run
   ```

The background scheduler automatically starts with the Flask application and will begin performing uptime checks once monitors are created.

## Production Notes

- Configure a production-ready WSGI server such as Gunicorn or uWSGI.
- Schedule the application process via systemd or a container orchestrator.
- Configure HTTPS for all inbound traffic.
- Provide environment-specific configuration using `PulseWatchConfig` subclasses in `config.py`.
- Ensure outbound network access for HTTP checks and notification providers.

## License

MIT
