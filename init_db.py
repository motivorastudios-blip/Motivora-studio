#!/usr/bin/env python3
"""Initialize the database for Motivora Studio."""

from server import app, db
from models import User, Render

if __name__ == "__main__":
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database initialized successfully!")
        print(f"Location: {app.config['SQLALCHEMY_DATABASE_URI']}")


