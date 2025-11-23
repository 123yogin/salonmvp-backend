from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    
    # Verify schema
    import sqlite3
    conn = sqlite3.connect('instance/salon.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"User table columns: {columns}")
    
    if 'cognito_sub' in columns:
        print("SUCCESS: cognito_sub column exists.")
    else:
        print("FAILURE: cognito_sub column MISSING.")
        
    print("Database initialized successfully.")
