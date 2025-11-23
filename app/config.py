import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///salon.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Server Configuration
    HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # CORS Configuration
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
    
    # AWS Cognito Configuration
    COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
    COGNITO_APP_CLIENT_ID = os.environ.get('COGNITO_APP_CLIENT_ID')
    COGNITO_CLIENT_SECRET = os.environ.get('COGNITO_CLIENT_SECRET')
    COGNITO_REGION = os.environ.get('COGNITO_REGION', 'us-east-1')
    
    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_LIFETIME_DAYS = int(os.environ.get('SESSION_LIFETIME_DAYS', 7))
    PERMANENT_SESSION_LIFETIME = timedelta(days=SESSION_LIFETIME_DAYS)
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = ENV == 'production'  # Automatically set to True in production
