import re
import bcrypt
from database.database_manager import DatabaseManager
from datetime import datetime


class AuthManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def validate_username(self, username):
        if not username or len(username) < 5:
            return False, "Username must be at least 5 characters."
        if username == "..":
            return False, "Invalid username."
        if re.match(r'^[0-9]+$', username):
            return False, "Username cannot be only numbers."
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            return False, "Username can only contain letters, numbers, underscore and dot."
        return True, "Valid"

    def validate_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format."
        # Prevent low quality emails like 123@gmail.com (strict check)
        local_part = email.split('@')[0]
        if re.match(r'^[0-9]+$', local_part):
            return False, "Email local part cannot be only numbers."
        return True, "Valid"

    def validate_password(self, password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters."
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one number."
        if not re.search(r'[!@#$%^&*]', password):
            return False, "Password must contain at least one special character (!@#$%^&*)."
        return True, "Valid"

    def hash_password(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password, hashed):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def register(self, username, email, password, role):
        # Validations
        valid, msg = self.validate_username(username)
        if not valid: return False, msg

        valid, msg = self.validate_email(email)
        if not valid: return False, msg

        valid, msg = self.validate_password(password)
        if not valid: return False, msg

        hashed_pw = self.hash_password(password)
        return self.db.add_user(username, email, hashed_pw, role)

    def login(self, username, password):
        user = self.db.get_user(username)
        if not user:
            # Generic message to prevent enumeration
            return None

            # Check lockout
        if user['lockout_time']:
            lockout_dt = datetime.fromisoformat(str(user['lockout_time']))
            if datetime.now() < lockout_dt:
                return None  # Still locked

        if self.check_password(password, user['password']):
            self.db.update_login_attempt(user['id'], success=True)
            return {'id': user['id'], 'username': user['username'], 'role': user['role']}
        else:
            self.db.update_login_attempt(user['id'], success=False)
            return None