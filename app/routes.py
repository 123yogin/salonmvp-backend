from flask import Blueprint, jsonify
from app.models import User, Salon, Staff, Service, ServiceLog, DailyClosing

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return jsonify({"message": "Welcome to Salon MVP Backend!"})

@main.route('/health')
def health():
    return jsonify({"status": "healthy"})
