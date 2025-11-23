from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    print("Creating tables in Neon PostgreSQL...")
    try:
        db.create_all()
        print("Success! Tables created.")
    except Exception as e:
        print(f"Error creating tables: {e}")