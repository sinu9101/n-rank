# auth_module.py

import hashlib
from pyairtable import Api
from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox

from airtable_config import AIRTABLE_API_KEY, BASE_ID

USERS_TABLE = "Users"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class AuthManager:
    def __init__(self):
        self.api = Api(AIRTABLE_API_KEY)
        self.table = self.api.base(BASE_ID).table(USERS_TABLE)

    def register_user(self, username: str, password: str) -> bool:
        # 아이디 중복 확인
        existing = self.table.all(formula=f"{{username}} = '{username}'")
        if existing:
            return False
        # 신규 저장
        self.table.create({
            "username": username,
            "password_hash": hash_password(password)
        })
        return True

    def verify_user(self, username: str, password: str) -> bool:
        records = self.table.all(formula=f"{{username}} = '{username}'")
        if not records:
            return False
        stored_hash = records[0]["fields"].get("password_hash", "")
        return stored_hash == hash_password(password)
