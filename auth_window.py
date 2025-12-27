# auth_window.py

from PySide6.QtWidgets import QWidget, QLineEdit, QPushButton, QVBoxLayout, QLabel, QMessageBox
from auth_module import AuthManager

class LoginWindow(QWidget):
    def __init__(self, on_success_callback):
        super().__init__()
        self.auth = AuthManager()
        self.on_success = on_success_callback
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("로그인")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("아이디")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("비밀번호")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_btn = QPushButton("로그인")
        self.signup_btn = QPushButton("회원가입")

        self.login_btn.clicked.connect(self.login)
        self.signup_btn.clicked.connect(self.signup)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("로그인 또는 회원가입"))
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_btn)
        layout.addWidget(self.signup_btn)
        self.setLayout(layout)

    def login(self):
        user = self.username_input.text()
        pw = self.password_input.text()
        if self.auth.verify_user(user, pw):
            self.on_success(user)
            self.close()
        else:
            QMessageBox.warning(self, "오류", "로그인 실패: 아이디 또는 비밀번호를 확인하세요")

    def signup(self):
        user = self.username_input.text()
        pw = self.password_input.text()
        if self.auth.register_user(user, pw):
            QMessageBox.information(self, "성공", "회원가입 완료! 로그인해주세요")
        else:
            QMessageBox.warning(self, "오류", "이미 존재하는 아이디입니다")
