from flask import Flask
from flask_cors import CORS
from flask_session import Session
from app.config import Config
import logging
import re

# Custom logging filter to suppress 401 logs for /api/auth/me
class SuppressAuthMe401Filter(logging.Filter):
    def filter(self, record):
        # Check if this is a 401 error for /api/auth/me
        message = record.getMessage()
        # Werkzeug logs format: "GET /api/auth/me HTTP/1.1" 401
        if '401' in message and '/api/auth/me' in message:
            return False  # Suppress this log
        return True

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.extensions import db
    db.init_app(app)

    # Configure CORS to allow credentials
    CORS(app, supports_credentials=True, origins=[app.config['FRONTEND_URL']])
    
    # Initialize session
    Session(app)

    # Suppress 401 logging for /api/auth/me endpoint (expected after logout)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(SuppressAuthMe401Filter())

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        from app import models
        db.create_all()

    return app

