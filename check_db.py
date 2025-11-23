print("Starting check_db.py...")
from app import create_app
from app.extensions import db
from sqlalchemy import text

print("Imports done.")

try:
    app = create_app()
    print("App created.")

    with app.app_context():
        print("Inside app context.")
        try:
            # Check connection
            result = db.session.execute(text('SELECT 1'))
            print(f"Connection successful: {result.scalar()}")
            
            # Check if tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Tables found: {tables}")
            
        except Exception as e:
            print(f"Database check failed: {e}")
except Exception as e:
    print(f"App creation failed: {e}")