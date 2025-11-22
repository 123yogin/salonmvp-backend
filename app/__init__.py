from flask import Flask
from flask_cors import CORS
from app.config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.extensions import db
    db.init_app(app)

    CORS(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        from app import models
        db.create_all()

    return app
