from flask import Blueprint, jsonify

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return jsonify({"message": "Welcome to Salon MVP Backend!"})

@main.route('/health')
def health():
    return jsonify({"status": "healthy"})
