"""
Migration utility for Flask CRM application
Handles database schema changes and initial data setup
"""

import logging
from datetime import datetime

from werkzeug.security import generate_password_hash

from database import db
from models import User


def create_admin_user():
    """
    Create default admin user if it doesn't exist
    This should be called during application initialization
    """
    try:
        # Check if admin user already exists
        admin = User.query.filter_by(username="admin").first()

        if not admin:
            # Create admin user with default credentials
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                role="admin",
                created_at=datetime.utcnow(),
            )
            db.session.add(admin)
            db.session.commit()

            logging.info("Default admin user created successfully")
            print("✓ Default admin user created: admin/admin123")
            return True
        else:
            logging.info("Admin user already exists")
            print("✓ Admin user already exists")
            return False

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating admin user: {str(e)}")
        print(f"✗ Error creating admin user: {str(e)}")
        return False


def run_initial_setup():
    """
    Run initial database setup including creating admin user
    """
    print("Running initial database setup...")

    # Create admin user
    create_admin_user()

    print("Initial database setup completed.")


if __name__ == "__main__":
    # This allows running migrations directly
    from app import app

    with app.app_context():
        run_initial_setup()
