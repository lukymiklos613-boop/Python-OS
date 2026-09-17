import sys
import os
import shutil
import subprocess
import json
import hashlib
import traceback
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ascii_art = """
██████╗ ██╗   ██╗████████╗██╗  ██╗ ██████╗ ███╗   ██╗   ██████╗ ███████╗
██╔══██╗╚██╗ ██╔╝╚══██╔══╝██║  ██║██╔═══██╗████╗  ██║  ██╔═══██╗██╔════╝
██████╔╝ ╚████╔╝    ██║   ███████║██║   ██║██╔██╗ ██║  ██║   ██║███████╗
██╔═══╝   ╚██╔╝     ██║   ██╔══██║██║   ██║██║╚██╗██║  ██║   ██║╚════██║
██║        ██║      ██║   ██║  ██║╚██████╔╝██║ ╚████║  ╚██████╔╝███████║
╚═╝        ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═════╝ ╚══════╝
"""

print(ascii_art)
print("Starting...")

# --- 1. DEPENDENCY CHECK ---
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QMdiArea, QMdiSubWindow, 
                                 QPushButton, QVBoxLayout, QWidget, QLabel, 
                                 QTextEdit, QLineEdit, QHBoxLayout, QToolBar, 
                                 QMenu, QAction, QMessageBox, QInputDialog, 
                                 QGridLayout, QSizePolicy, QTableWidget, 
                                 QTableWidgetItem, QHeaderView, QSlider, QColorDialog, 
                                 QScrollArea, QDialog, QComboBox, QListWidget, QListWidgetItem,
                                 QToolButton, QStyle, QAbstractItemView, QRubberBand)
    from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, QEvent, QRect
    from PyQt5.QtGui import QImage, QPainter, QPen, QPixmap, QColor, QTextCursor, QIcon, QBrush
except ImportError:
    print("\n[!] PyQt5 missing. Attempting to install PyQt5...")
    try: 
        os.system(sys.executable + " -m pip install PyQt5")
    except: 
        pass
    sys.exit(1)

# --- CONFIG & SECURITY HELPER ---
CONFIG_FILE = "sys_config.json"

def hash_password(password, salt="pythonos_secure_salt_2026"):
    """Creates a secure password hash."""
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# --- CUSTOM SUBWINDOW: TITLEBAR BUTTONS + VLASTNÝ TASKBAR ---
class TitleBarButton(QToolButton):
    """Jednoduché title-bar tlačidlo kreslené priamo podľa požadovaného štýlu."""
    BLUE = "#1147ff"
    BLUE_HOVER = "#0b3fd9"
    RED = "#d83232"
    RED_HOVER = "#b82020"

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(28, 20)
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.ArrowCursor)
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)

        if kind == "close":
            self.setToolTip("Zavrieť")
        elif kind == "maximize":
            self.setToolTip("Maximalizovať")
        else:
            self.setToolTip("Minimalizovať")

        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # Pozadie podľa požadovaného vzhľadu:
        # všetky tlačidlá modré, iba X červené.
        if self.kind == "close":
            bg = self.RED_HOVER if self._hover else self.RED
        else:
            bg = self.BLUE_HOVER if self._hover else self.BLUE

        painter.fillRect(self.rect(), QColor(bg))

        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.SquareCap)
        painter.setPen(pen)

        cx = self.width() // 2
        cy = self.height() // 2

        if self.kind == "minimize":
            # Biely vodorovný pásik – podľa priloženého vzoru.
            painter.fillRect(cx - 9, cy - 1, 18, 3, QColor("#ffffff"))

        elif self.kind == "maximize":
            # Biely štvorcový obrys.
            painter.drawRect(cx - 6, cy - 6, 12, 12)

        elif self.kind == "restore":
            # Dve prekryté biele plochy pre stav "obnoviť".
            painter.drawRect(cx - 4, cy - 6, 9, 9)
            painter.drawRect(cx - 7, cy - 3, 9, 9)

        elif self.kind == "close":
            # Biely krížik na červenom pozadí.
            painter.drawLine(cx - 6, cy - 5, cx + 6, cy + 5)
            painter.drawLine(cx + 6, cy - 5, cx - 6, cy + 5)

        painter.end()


class CustomSubWindow(QMdiSubWindow):
    def __init__(self, main_win, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_win = main_win

        # Odstránime natívne title-bar tlačidlá a nahradíme ich tromi
        # vlastnými tlačidlami, aby mali presne jednotný vzhľad.
        self.setWindowFlags(
            self.windowFlags()
            & ~(
                Qt.WindowMinimizeButtonHint
                | Qt.WindowMaximizeButtonHint
                | Qt.WindowCloseButtonHint
            )
        )

        self._min_btn = TitleBarButton("minimize", self)
        self._max_btn = TitleBarButton("maximize", self)
        self._close_btn = TitleBarButton("close", self)

        self._min_btn.clicked.connect(self._minimize_to_taskbar)
        self._max_btn.clicked.connect(self._toggle_maximize)
        self._close_btn.clicked.connect(self.close)

        self._reposition_titlebar_buttons()

    def _reposition_titlebar_buttons(self):
        # Tlačidlá sú zoradené rovnako ako klasický Windows title bar:
        # Min | Max | X.
        if not hasattr(self, "_close_btn"):
            return

        top = 4
        spacing = 5
        right_margin = 4
        bw = self._close_btn.width()

        close_x = self.width() - right_margin - bw
        max_x = close_x - spacing - self._max_btn.width()
        min_x = max_x - spacing - self._min_btn.width()

        self._min_btn.move(min_x, top)
        self._max_btn.move(max_x, top)
        self._close_btn.move(close_x, top)

        self._min_btn.raise_()
        self._max_btn.raise_()
        self._close_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_titlebar_buttons()

    def _minimize_to_taskbar(self):
        # Zachováva pôvodnú logiku: okno sa skryje a jeho tlačidlo
        # v hlavnom taskbare zostane dostupné na obnovenie.
        self.hide()

        if self.main_win is not None and hasattr(
            self.main_win, "sync_taskbar_button"
        ):
            self.main_win.sync_taskbar_button(self)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self._max_btn.kind = "maximize"
            self._max_btn.setToolTip("Maximalizovať")
        else:
            self.showMaximized()
            self._max_btn.kind = "restore"
            self._max_btn.setToolTip("Obnoviť")
        self._max_btn.update()
        self._reposition_titlebar_buttons()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            # Bezpečnostný fallback: ak by sa QMdiSubWindow pokúsilo
            # prejsť do natívneho minimized stavu, presmeruj ho do taskbaru.
            if self.isMinimized():
                self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
                self._minimize_to_taskbar()
                event.accept()
                return

            # Aktualizuj symbol Maximize/Restore.
            if self.isMaximized():
                self._max_btn.kind = "restore"
                self._max_btn.setToolTip("Obnoviť")
            else:
                self._max_btn.kind = "maximize"
                self._max_btn.setToolTip("Maximalizovať")

            self._max_btn.update()
            self._reposition_titlebar_buttons()

        super().changeEvent(event)

    def closeEvent(self, event):
        # Pri zatvorení odstráň tlačidlo z hlavného taskbaru.
        if self.main_win is not None and hasattr(
            self.main_win, "remove_taskbar_button"
        ):
            self.main_win.remove_taskbar_button(self)

        super().closeEvent(event)

# --- 2. OOBE (OUT-OF-BOX EXPERIENCE) DIALOG ---
class OOBEDialog(QDialog):
    def __init__(self):
        super().__init__()
        print("Preparing for first use...")
        self.setWindowTitle("Python OS 2.0 Setup - OOBE")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        title = QLabel("Welcome to Python OS 2.0!")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel("Let's set up your primary administrator account.")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        self.grid = QGridLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.theme_input = QComboBox()
        self.theme_input.addItems(["Light", "Dark"])
        
        self.grid.addWidget(QLabel("Username:"), 0, 0)
        self.grid.addWidget(self.username_input, 0, 1)
        self.grid.addWidget(QLabel("Password:"), 1, 0)
        self.grid.addWidget(self.password_input, 1, 1)
        self.grid.addWidget(QLabel("Preferred Theme:"), 2, 0)
        self.grid.addWidget(self.theme_input, 2, 1)
        
        layout.addLayout(self.grid)
        
        self.btn_finish = QPushButton("Complete Setup")
        self.btn_finish.clicked.connect(self.complete_setup)
        layout.addWidget(self.btn_finish)
        print("Done! Welcome to Python OS 2.0 OOBE")

    def complete_setup(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text()
        theme = self.theme_input.currentText()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Validation Error", "Username and Password cannot be empty!")
            return
            
        config = {
            "oobe_completed": True,
            "theme": theme,
            "bg_color": "#696969",
            "users": {
                user: {
                    "password": hash_password(pwd),
                    "role": "Admin"
                }
            }
        }
        save_config(config)
        
        user_home = os.path.join("Home", user)
        os.makedirs(user_home, exist_ok=True)
        os.makedirs(os.path.join(user_home, "Desktop"), exist_ok=True)
        
        QMessageBox.information(self, "Success", f"Administrator account '{user}' successfully created!\nPython OS 2.0 is now ready.")
        self.accept()

# --- 3. SECURE LOGIN DIALOG ---
class LoginDialog(QDialog):
    def __init__(self, config):
        super().__init__()
        self.config = config
        print("Loading...")
        self.setWindowTitle("Python OS 2.0 Login")
        self.resize(350, 180)
        
        layout = QVBoxLayout(self)
        
        title = QLabel("System Authentication")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        grid = QGridLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        grid.addWidget(QLabel("Username:"), 0, 0)
        grid.addWidget(self.username_input, 0, 1)
        grid.addWidget(QLabel("Password:"), 1, 0)
        grid.addWidget(self.password_input, 1, 1)
        
        layout.addLayout(grid)
        
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Login")
        self.btn_login.clicked.connect(self.attempt_login)
        
        btn_layout.addWidget(self.btn_login)
        layout.addLayout(btn_layout)
        
        self.authenticated_user = None
        print("Done!")

    def attempt_login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text()
        
        users = self.config.get("users", {})
        user_data = users.get(user)
        if user_data:
            stored_hash = user_data["password"] if isinstance(user_data, dict) else user_data
            if stored_hash == hash_password(pwd):
                self.authenticated_user = user
                self.accept()
                return
        
        QMessageBox.critical(self, "Access Denied", "Invalid username or password.")

# --- 4. THE APP SUITE ---

class SettingsApp(QWidget):
    def __init__(self, parent_sys, user_home, config):
        super().__init__()
        self.parent_sys = parent_sys
        self.user_home = user_home
        self.config = config
        self.setWindowTitle("Settings")
        self.resize(400, 550)
        
        layout = QVBoxLayout(self)
        
        current_user = self.parent_sys.active_user
        user_info = self.config.get("users", {}).get(current_user, {})
        self.user_role = user_info.get("role", "User") if isinstance(user_info, dict) else "User"
        
        layout.addWidget(QLabel("<b>System Appearance</b>"))
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("System Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.config.get("theme", "Light"))
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)
        
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("Desktop Background Color:"))
        btn_bg_color = QPushButton("🎨 Choose Color")
        btn_bg_color.clicked.connect(self.choose_bg_color)
        bg_layout.addWidget(btn_bg_color)
        layout.addLayout(bg_layout)

        layout.addWidget(QLabel("<hr>"))
        
        layout.addWidget(QLabel("<b>Change Password</b>"))
        self.old_pwd = QLineEdit()
        self.old_pwd.setPlaceholderText("Current Password")
        self.old_pwd.setEchoMode(QLineEdit.Password)
        self.new_pwd = QLineEdit()
        self.new_pwd.setPlaceholderText("New Password")
        self.new_pwd.setEchoMode(QLineEdit.Password)
        
        layout.addWidget(self.old_pwd)
        layout.addWidget(self.new_pwd)
        
        btn_save = QPushButton("💾 Save & Apply Settings")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        
        layout.addWidget(QLabel("<hr>"))
        
        layout.addWidget(QLabel("<b>Create New User</b>"))
        
        self.new_user_name = QLineEdit()
        self.new_user_name.setPlaceholderText("New Username")
        self.new_user_pwd = QLineEdit()
        self.new_user_pwd.setPlaceholderText("Password")
        self.new_user_pwd.setEchoMode(QLineEdit.Password)
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(["User", "Admin"])
        
        role_layout = QHBoxLayout()
        role_layout.addWidget(QLabel("Assign Role:"))
        role_layout.addWidget(self.role_combo)
        
        self.btn_create_user = QPushButton("👤 Create User")
        self.btn_create_user.clicked.connect(self.create_user)
        
        layout.addWidget(self.new_user_name)
        layout.addWidget(self.new_user_pwd)
        layout.addLayout(role_layout)
        layout.addWidget(self.btn_create_user)
        
        if self.user_role != "Admin":
            self.new_user_name.setEnabled(False)
            self.new_user_pwd.setEnabled(False)
            self.role_combo.setEnabled(False)
            self.btn_create_user.setEnabled(False)
            self.btn_create_user.setText("👤 Create User (Admin Only)")
            
            perm_warning = QLabel("<font color='red'>Creating new users is restricted to Admins only.</font>")
            perm_warning.setStyleSheet("font-size: 8pt;")
            layout.addWidget(perm_warning)
            
        layout.addWidget(QLabel("<hr>"))
        
        info_lbl = QLabel(
            f"<b>System Info:</b><br>"
            f"OS: Python OS 2.0<br>"
            f"User: {current_user} ({self.user_role})<br>"
            f"Path: {self.user_home}"
        )
        info_lbl.setStyleSheet("color: #555555; font-size: 9pt;")
        layout.addWidget(info_lbl)

    def choose_bg_color(self):
        curr_hex = self.config.get("bg_color", "#696969")
        color = QColorDialog.getColor(QColor(curr_hex), self, "Select Background Color")
        if color.isValid():
            hex_code = color.name()
            self.config["bg_color"] = hex_code
            self.parent_sys.mdi.update_theme(self.theme_combo.currentText(), custom_bg=hex_code)

    def save_settings(self):
        selected_theme = self.theme_combo.currentText()
        self.config["theme"] = selected_theme
        
        self.parent_sys.mdi.update_theme(selected_theme, custom_bg=self.config.get("bg_color"))
        
        old_p = self.old_pwd.text()
        new_p = self.new_pwd.text()
        
        if old_p or new_p:
            user = self.parent_sys.active_user
            user_data = self.config.get("users", {}).get(user)
            current_hash = user_data["password"] if isinstance(user_data, dict) else user_data
            
            if hash_password(old_p) == current_hash:
                if new_p.strip():
                    if isinstance(user_data, dict):
                        self.config["users"][user]["password"] = hash_password(new_p)
                    else:
                        self.config["users"][user] = {
                            "password": hash_password(new_p),
                            "role": "User"
                        }
                    self.old_pwd.clear()
                    self.new_pwd.clear()
                    QMessageBox.information(self, "Security", "Password changed successfully!")
                else:
                    QMessageBox.warning(self, "Error", "New password cannot be empty!")
                    return
            else:
                QMessageBox.critical(self, "Error", "Incorrect current password!")
                return
        
        save_config(self.config)
        QMessageBox.information(self, "Saved", "Settings saved and applied successfully!")

    def create_user(self):
        if self.user_role != "Admin":
            QMessageBox.critical(self, "Permission Denied", "You do not have permission to perform this action.")
            return

        username = self.new_user_name.text().strip()
        password = self.new_user_pwd.text()
        selected_role = self.role_combo.currentText()
        
        if not username or not password:
            QMessageBox.warning(self, "Validation Error", "Username and Password cannot be empty!")
            return
            
        users = self.config.get("users", {})
        if username in users:
            QMessageBox.warning(self, "Error", f"User '{username}' already exists!")
            return
            
        self.config["users"][username] = {
            "password": hash_password(password),
            "role": selected_role
        }
        save_config(self.config)
        
        new_home = os.path.join("Home", username)
        os.makedirs(new_home, exist_ok=True)
        os.makedirs(os.path.join(new_home, "Desktop"), exist_ok=True)
        
        QMessageBox.information(self, "Success", f"User '{username}' successfully created with role '{selected_role}'!")
        
        self.new_user_name.clear()
        self.new_user_pwd.clear()

class TerminalApp(QWidget):
    def __init__(self, user_home, start_dir=None):
        super().__init__()
        self.user_home = os.path.abspath(user_home)
        self.curr_dir = os.path.abspath(start_dir) if start_dir and os.path.exists(start_dir) else self.user_home
        self.setWindowTitle("Terminal")
        self.resize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            background-color: #0c0c0c;
            color: #00ff00;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10pt;
            border: none;
        """)
        layout.addWidget(self.output)

        input_layout = QHBoxLayout()
        self.prompt_lbl = QLabel()
        self.prompt_lbl.setStyleSheet("""
            background-color: #0c0c0c;
            color: #00aaff;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10pt;
            padding-left: 5px;
        """)
        
        self.input = QLineEdit()
        self.input.setStyleSheet("""
            background-color: #0c0c0c;
            color: #ffffff;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10pt;
            border: none;
        """)
        self.input.returnPressed.connect(self.exec_cmd)

        input_layout.addWidget(self.prompt_lbl)
        input_layout.addWidget(self.input, 1)
        input_layout.setSpacing(0)
        input_layout.setContentsMargins(0, 0, 0, 0)

        input_bg = QWidget()
        input_bg.setStyleSheet("background-color: #0c0c0c;")
        input_bg.setLayout(input_layout)
        layout.addWidget(input_bg)

        self.update_prompt()
        self.write_output("Welcome to Python OS 2.0 Terminal v2.0\nType 'help' for a list of system commands.\n\n")

    def update_prompt(self):
        try:
            relative_path = os.path.relpath(self.curr_dir, self.user_home)
            path_str = "~" if relative_path == "." else f"~/{relative_path.replace(os.sep, '/')}"
        except ValueError:
            path_str = self.curr_dir
        self.prompt_lbl.setText(f"pythonos@localhost:{path_str}$ ")

    def write_output(self, text):
        self.output.insertPlainText(text)
        self.output.moveCursor(QTextCursor.End)

    def exec_cmd(self):
        cmd_raw = self.input.text()
        self.input.clear()
        if not cmd_raw.strip():
            return

        self.write_output(f"{self.prompt_lbl.text()}{cmd_raw}\n")
        parts = cmd_raw.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            self.write_output("Available commands:\n"
                              "  help               - Shows this message\n"
                              "  ls / dir           - List files in current directory\n"
                              "  cd <dir>           - Change directory\n"
                              "  pwd                - Print working directory\n"
                              "  mkdir <name>       - Create directory\n"
                              "  echo <text>        - Print text\n"
                              "  cat <file>         - Display file contents\n"
                              "  clear / cls        - Clear the terminal screen\n"
                              "  [Python Code]      - Run any Python code directly (e.g. 2+2)\n\n")
        elif cmd in ["ls", "dir"]:
            try:
                items = os.listdir(self.curr_dir)
                if items:
                    self.write_output("\n".join(items) + "\n\n")
                else:
                    self.write_output("(directory is empty)\n\n")
            except Exception as e:
                self.write_output(f"Error: {e}\n\n")
        elif cmd == "pwd":
            self.write_output(f"{self.curr_dir}\n\n")
        elif cmd == "cd":
            if not args:
                self.curr_dir = self.user_home
            else:
                target = os.path.normpath(os.path.join(self.curr_dir, args[0]))
                if os.path.exists(target) and os.path.isdir(target):
                    if os.path.commonpath([self.user_home, target]) == self.user_home:
                        self.curr_dir = target
                    else:
                        self.write_output("Access Denied: Cannot navigate outside home folder.\n\n")
                else:
                    self.write_output(f"cd: no such file or directory: {args[0]}\n\n")
            self.update_prompt()
        elif cmd == "mkdir":
            if not args:
                self.write_output("mkdir: missing operand\n\n")
            else:
                try:
                    os.makedirs(os.path.join(self.curr_dir, args[0]), exist_ok=True)
                    self.write_output(f"Directory '{args[0]}' created.\n\n")
                except Exception as e:
                    self.write_output(f"Error: {e}\n\n")
        elif cmd == "echo":
            self.write_output(" ".join(args) + "\n\n")
        elif cmd == "cat":
            if not args:
                self.write_output("cat: missing file operand\n\n")
            else:
                target = os.path.join(self.curr_dir, args[0])
                if os.path.exists(target) and os.path.isfile(target):
                    try:
                        with open(target, 'r', encoding='utf-8') as f:
                            self.write_output(f.read() + "\n\n")
                    except Exception as e:
                        self.write_output(f"Error reading file: {e}\n\n")
                else:
                    self.write_output(f"cat: {args[0]}: No such file\n\n")
        elif cmd in ["clear", "cls"]:
            self.output.clear()
        else:
            try:
                result = eval(cmd_raw, {"__builtins__": __builtins__}, {})
                if result is not None:
                    self.write_output(f"{result}\n\n")
            except:
                try:
                    import io
                    from contextlib import redirect_stdout
                    f = io.StringIO()
                    with redirect_stdout(f):
                        exec(cmd_raw, {"__builtins__": __builtins__}, {})
                    out_val = f.getvalue()
                    if out_val:
                        self.write_output(out_val + "\n")
                    else:
                        self.write_output("Python code executed successfully.\n\n")
                except Exception as py_err:
                    self.write_output(f"Command not recognized or Python Error:\n{py_err}\n\n")

class GeanyEditor(QWidget):
    def __init__(self, home):
        super().__init__()
        self.home, self.file = home, None
        self.setWindowTitle("Geany 2.0")
        layout = QVBoxLayout(self)
        self.edit = QTextEdit()
        self.edit.setStyleSheet("font-family: monospace; background: #1e1e1e; color: #dcdcdc;")
        self.lbl = QLabel("New Document")
        btn = QPushButton("💾 Save File")
        btn.clicked.connect(self.save)
        layout.addWidget(self.lbl)
        layout.addWidget(self.edit)
        layout.addWidget(btn)
        
    def open_f(self, p):
        try:
            with open(p, 'r', encoding='utf-8') as f: 
                self.edit.setPlainText(f.read())
            self.file = p
            self.lbl.setText(p)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open file:\n{e}")
            
    def save(self):
        if not self.file:
            n, ok = QInputDialog.getText(self, 'Save', 'Name:')
            self.file = os.path.join(self.home, n) if ok else None
        if self.file:
            with open(self.file, 'w', encoding='utf-8') as f: 
                f.write(self.edit.toPlainText())

class PaintApp(QWidget):
    def __init__(self, user_home):
        super().__init__()
        self.user_home = user_home
        self.setWindowTitle("Paint")
        self.image = QImage(800, 600, QImage.Format_RGB32)
        self.image.fill(Qt.white)
        self.drawing = False
        self.brush_color = Qt.black
        self.last_point = QPoint()
        
        l = QVBoxLayout(self)
        self.c = QLabel()
        self.c.setPixmap(QPixmap.fromImage(self.image))
        t = QHBoxLayout()
        b1 = QPushButton("🎨 Color")
        b1.clicked.connect(self.set_c)
        b2 = QPushButton("💾 Save")
        b2.clicked.connect(self.save)
        t.addWidget(b1)
        t.addWidget(b2)
        t.addStretch()
        l.addLayout(t)
        l.addWidget(self.c)
        
    def set_c(self): 
        c = QColorDialog.getColor()
        self.brush_color = c if c.isValid() else self.brush_color
        
    def open_img(self, p): 
        i = QImage(p)
        self.image = i.scaled(800, 600, Qt.KeepAspectRatio) if not i.isNull() else self.image
        self.upd()
        
    def save(self): 
        n, ok = QInputDialog.getText(self, 'Save', 'Name:')
        if ok and n:
            self.image.save(os.path.join(self.user_home, n))
            
    def upd(self): 
        self.c.setPixmap(QPixmap.fromImage(self.image))
        
    def mousePressEvent(self, e): 
        self.drawing = True
        self.last_point = e.pos() - self.c.pos()
        
    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.LeftButton) and self.drawing:
            p = QPainter(self.image)
            p.setPen(QPen(self.brush_color, 3, Qt.SolidLine, Qt.RoundCap))
            curr = e.pos() - self.c.pos()
            p.drawLine(self.last_point, curr)
            self.last_point = curr
            self.upd()

class Calculator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculator")
        l = QVBoxLayout(self)
        self.d = QLineEdit()
        l.addWidget(self.d)
        g = QGridLayout()
        btns = ['7','8','9','/','4','5','6','*','1','2','3','-','C','0','=','+']
        for i, b in enumerate(btns):
            btn = QPushButton(b)
            btn.clicked.connect(self.calc)
            g.addWidget(btn, i//4, i%4)
        l.addLayout(g)

    def calc(self):
        t = self.sender().text()
        if t == '=':
            try: 
                self.d.setText(str(eval(self.d.text())))
            except: 
                self.d.setText("Error")
        elif t == 'C': 
            self.d.clear()
        else: 
            self.d.setText(self.d.text() + t)

class GalleryApp(QWidget):
    def __init__(self, folder):
        super().__init__()
        self.setWindowTitle("Gallery")
        l = QVBoxLayout(self)
        s = QScrollArea()
        c = QWidget()
        self.g = QGridLayout(c)
        try:
            imgs = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.bmp'))]
        except:
            imgs = []
        r, col = 0, 0
        for i in imgs:
            lbl = QLabel()
            lbl.setPixmap(QPixmap(os.path.join(folder, i)).scaled(100, 100, Qt.KeepAspectRatio))
            self.g.addWidget(lbl, r, col)
            col += 1
            if col > 3: 
                col = 0
                r += 1
        s.setWidget(c)
        s.setWidgetResizable(True)
        l.addWidget(s)

# --- 5. NEMO FILE MANAGER ---

class NemoFileManager(QWidget):
    def __init__(self, home, vm, start_dir=None):
        super().__init__()
        self.home = os.path.abspath(home)
        self.curr = os.path.abspath(start_dir) if start_dir and os.path.exists(start_dir) else self.home
        self.vm = vm
        self.history = [] 
        
        user_info = self.vm.config.get("users", {}).get(self.vm.active_user, {})
        self.user_role = user_info.get("role", "User") if isinstance(user_info, dict) else "User"
        
        l = QVBoxLayout(self)
        nav = QHBoxLayout()
        self.btn_u = QPushButton("↑ Up")
        self.btn_u.clicked.connect(self.up)
        
        btn_f = QPushButton("+ File")
        btn_f.clicked.connect(self.new_f)
        
        btn_d = QPushButton("+ Folder")
        btn_d.clicked.connect(self.new_d)
        
        self.addr = QLineEdit(self.curr)
        self.addr.returnPressed.connect(self.manual_navigate)
        
        nav.addWidget(self.btn_u)
        nav.addWidget(btn_f)
        nav.addWidget(btn_d)
        nav.addWidget(self.addr)
        l.addLayout(nav)
        
        self.tab = QTableWidget(0, 2)
        self.tab.setHorizontalHeaderLabels(["Name", "Size"])
        self.tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tab.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self.menu)
        self.tab.itemDoubleClicked.connect(self.open_i)
        l.addWidget(self.tab)
        
        self.refresh()

    def refresh(self):
        self.tab.setRowCount(0)
        self.addr.setText(self.curr)
        
        if self.user_role != "Admin" and self.curr == self.home:
            self.btn_u.setEnabled(False)
        else:
            self.btn_u.setEnabled(True)
            
        try:
            for i in sorted(os.listdir(self.curr)):
                r = self.tab.rowCount()
                self.tab.insertRow(r)
                p = os.path.join(self.curr, i)
                d = os.path.isdir(p)
                self.tab.setItem(r, 0, QTableWidgetItem(("📁 " if d else "📄 ") + i))
                self.tab.setItem(r, 1, QTableWidgetItem("--" if d else f"{os.path.getsize(p)//1024} KB"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read directory:\n{e}")

        if hasattr(self.vm, 'mdi') and hasattr(self.vm.mdi, 'refresh_desktop'):
            self.vm.mdi.refresh_desktop()

    def manual_navigate(self):
        target_path = os.path.abspath(self.addr.text().strip())
        
        if self.user_role != "Admin":
            if os.path.commonpath([self.home, target_path]) != self.home:
                QMessageBox.critical(self, "Access Denied", "You are not allowed to access folders outside your Home folder!")
                self.refresh()
                return
                
        if os.path.exists(target_path) and os.path.isdir(target_path):
            self.curr = target_path
            self.refresh()
        else:
            QMessageBox.warning(self, "Error", "Directory does not exist.")
            self.refresh()

    def menu(self, pos):
        m = QMenu()
        it = self.tab.itemAt(pos)
        if it:
            name = self.tab.item(it.row(), 0).text()[2:]
            p = os.path.join(self.curr, name)
            if not os.path.isdir(p):
                m.addAction("📝 Edit in Geany", lambda: self.vm.open_geany(p))
            if os.path.isdir(p): 
                m.addAction("🖼️ Gallery", lambda: self.vm.open_gallery(p))
            
            m.addAction("📑 Copy", lambda: self.add_h(p, 'copy'))
            m.addAction("✂️ Cut", lambda: self.add_h(p, 'cut'))
            m.addAction("✏️ Rename", lambda: self.rename_i(p))
            m.addAction("🗑️ Delete", lambda: self.delete_i(p))
        
        if self.history:
            hv = m.addMenu("📋 Clipboard History (Win+V)")
            for e in self.history:
                act = hv.addAction(f"{'📑' if e['mode']=='copy' else '✂️'} {e['name']}")
                act.triggered.connect(lambda chk, x=e: self.paste_h(x))
        m.exec_(self.tab.viewport().mapToGlobal(pos))

    def add_h(self, p, m):
        self.history.insert(0, {'path': p, 'name': os.path.basename(p), 'mode': m})
        if len(self.history) > 10: 
            self.history.pop()

    def paste_h(self, e):
        dst = os.path.join(self.curr, e['name'])
        try:
            if e['mode'] == 'copy':
                if os.path.isdir(e['path']): 
                    shutil.copytree(e['path'], dst)
                else: 
                    shutil.copy2(e['path'], dst)
            else:
                shutil.move(e['path'], dst)
                self.history.remove(e)
            self.refresh()
        except Exception as err: 
            QMessageBox.critical(self, "Error", str(err))

    def new_f(self):
        n, ok = QInputDialog.getText(self, 'File', 'Name:')
        if ok and n: 
            open(os.path.join(self.curr, n), 'a').close()
            self.refresh()

    def new_d(self):
        n, ok = QInputDialog.getText(self, 'Folder', 'Name:')
        if ok and n: 
            os.makedirs(os.path.join(self.curr, n), exist_ok=True)
            self.refresh()

    def rename_i(self, p):
        n, ok = QInputDialog.getText(self, 'Rename', 'New Name:', text=os.path.basename(p))
        if ok and n: 
            os.rename(p, os.path.join(self.curr, n))
            self.refresh()

    def delete_i(self, p):
        if QMessageBox.question(self, 'Delete', 'Are you sure?') == QMessageBox.Yes:
            if os.path.isdir(p): 
                shutil.rmtree(p)
            else: 
                os.remove(p)
            self.refresh()

    def open_i(self, it):
        name = self.tab.item(it.row(), 0).text()[2:]
        p = os.path.join(self.curr, name)
        if os.path.isdir(p): 
            self.curr = p
            self.refresh()
        elif p.endswith(".py"): 
            self.vm.run_py(p)
        elif p.lower().endswith((".png", ".jpg", ".bmp")): 
            self.vm.open_paint(p)
        else: 
            self.vm.open_geany(p)

    def up(self): 
        parent_dir = os.path.abspath(os.path.dirname(self.curr))
        if self.user_role != "Admin":
            if os.path.commonpath([self.home, parent_dir]) != self.home:
                QMessageBox.warning(self, "Access Denied", "You cannot go higher than your Home folder!")
                return
        self.curr = parent_dir
        self.refresh()

# --- 6. DESKTOP AREA (WINDOWS-LIKE INTERACTIVE DESKTOP) ---




class DesktopSelectionOverlay(QWidget):
    """Transparent overlay used only to draw the selection rectangle."""
    def __init__(self, parent):
        super().__init__(parent)
        self.rect = QRect()
        self.active = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.hide()

    def set_rect(self, rect):
        self.rect = rect.normalized()
        self.active = self.rect.width() > 1 or self.rect.height() > 1
        if self.active:
            self.raise_()
            self.show()
            self.update()
        else:
            self.hide()

    def paintEvent(self, event):
        if not self.active:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect, QColor(0, 120, 215, 55))

        pen = QPen(QColor(0, 120, 215, 220))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRect(self.rect.adjusted(0, 0, -1, -1))
        p.end()


class DesktopIconButton(QToolButton):
    def __init__(self, canvas, name, path, icon):
        super().__init__(canvas)
        self.canvas = canvas
        self.name = name
        self.path = path

        self.setText(name)
        self.setIcon(icon)
        self.setIconSize(QSize(64, 64))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setFixedSize(96, 96)
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                color: white;
                padding: 4px;
                font-size: 9pt;
            }
            QToolButton:hover {
                background: rgba(255,255,255,35);
                border: 1px solid rgba(255,255,255,60);
            }
            QToolButton:checked {
                background: rgba(0,120,215,170);
                border: 1px solid rgba(255,255,255,140);
            }
        """)

        self._press_pos = QPoint()
        self._press_global = QPoint()
        self._dragging = False

    def set_selected(self, selected):
        self.setChecked(bool(selected))

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            # Right-click selects the item and immediately opens its menu.
            if self not in self.canvas.selected:
                self.canvas.icon_pressed(self, event.modifiers())
            self.canvas.show_item_menu(self, event.globalPos())
            event.accept()
            return

        if event.button() != Qt.LeftButton:
            event.ignore()
            return

        self._press_pos = event.pos()
        self._press_global = event.globalPos()
        self._dragging = False
        self.canvas.icon_pressed(self, event.modifiers())
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if not self._dragging:
                if (event.pos() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                    self._dragging = True
                    self.canvas.begin_icon_drag(self)

            if self._dragging:
                self.canvas.drag_selected(event.globalPos() - self._press_global)

            event.accept()
            return

        event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._dragging:
                self.canvas.end_icon_drag()
            self._dragging = False
            event.accept()
            return
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.canvas.open_icon(self)
            event.accept()
            return
        event.ignore()


class DesktopCanvas(QWidget):
    """Desktop canvas with Windows-like selection, drag and context menus."""

    GRID_W = 110
    GRID_H = 110
    LEFT = 8
    TOP = 8

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.main_win = manager.main_win if manager is not None else None

        self.icons = []
        self.selected = []
        self._drag_original = {}
        self._positions_changed = None

        self._selecting = False
        self._select_origin = QPoint()
        self._select_current = QPoint()
        self._select_ctrl = False

        self._overlay = DesktopSelectionOverlay(self)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setStyleSheet("background: transparent;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()
        for icon in self.icons:
            icon.raise_()

    def clear(self):
        self._selecting = False
        self._overlay.set_rect(QRect())
        for icon in self.icons:
            icon.deleteLater()
        self.icons.clear()
        self.selected.clear()
        self._drag_original.clear()

    def add_desktop_item(self, name, path, icon):
        item = DesktopIconButton(self, name, path, icon)
        self.icons.append(item)
        item.show()
        item.raise_()
        return item

    def _clear_selection(self):
        for icon in self.selected:
            icon.set_selected(False)
        self.selected.clear()

    def icon_pressed(self, icon, modifiers):
        ctrl = bool(modifiers & Qt.ControlModifier)

        if ctrl:
            if icon in self.selected:
                self.selected.remove(icon)
                icon.set_selected(False)
            else:
                self.selected.append(icon)
                icon.set_selected(True)
        else:
            if icon not in self.selected:
                self._clear_selection()
                self.selected = [icon]
                icon.set_selected(True)

    def begin_icon_drag(self, anchor):
        if anchor not in self.selected:
            self.icon_pressed(anchor, Qt.NoModifier)

        self._drag_original = {
            icon: icon.pos()
            for icon in self.selected
        }

    def drag_selected(self, delta):
        for icon, original in self._drag_original.items():
            pos = original + delta
            max_x = max(self.LEFT, self.width() - icon.width())
            max_y = max(self.TOP, self.height() - icon.height())
            pos.setX(max(self.LEFT, min(pos.x(), max_x)))
            pos.setY(max(self.TOP, min(pos.y(), max_y)))
            icon.move(pos)

        self._overlay.raise_()
        self.update()

    def end_icon_drag(self):
        for icon in self.selected:
            icon.move(self._snap(icon.pos()))

        self._drag_original.clear()
        if callable(self._positions_changed):
            self._positions_changed()

    def _snap(self, pos):
        x = self.LEFT + round(max(0, pos.x() - self.LEFT) / self.GRID_W) * self.GRID_W
        y = self.TOP + round(max(0, pos.y() - self.TOP) / self.GRID_H) * self.GRID_H
        return QPoint(
            max(self.LEFT, min(x, max(self.LEFT, self.width() - 96))),
            max(self.TOP, min(y, max(self.TOP, self.height() - 96)))
        )

    # ---- Selection rectangle ----

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._show_background_menu(event.globalPos())
            event.accept()
            return

        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        self.setFocus(Qt.MouseFocusReason)
        self._selecting = True
        self._select_origin = event.pos()
        self._select_current = event.pos()
        self._select_ctrl = bool(event.modifiers() & Qt.ControlModifier)

        if not self._select_ctrl:
            self._clear_selection()

        self.grabMouse()
        self._overlay.raise_()
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._selecting and (event.buttons() & Qt.LeftButton):
            self._select_current = event.pos()

            rect = QRect(self._select_origin, self._select_current).normalized()
            if rect.width() > 3 or rect.height() > 3:
                if not self._select_ctrl:
                    self._clear_selection()

                for icon in self.icons:
                    if rect.contains(icon.geometry().center()):
                        if icon not in self.selected:
                            self.selected.append(icon)
                        icon.set_selected(True)

                self._overlay.set_rect(rect)
                self._overlay.raise_()

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._select_current = event.pos()
            rect = QRect(self._select_origin, self._select_current).normalized()

            if rect.width() <= 3 and rect.height() <= 3 and not self._select_ctrl:
                self._clear_selection()

            self._selecting = False
            self._overlay.set_rect(QRect())

            if self.mouseGrabber() is self:
                self.releaseMouse()

            self.update()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ---- Context menus ----

    def show_item_menu(self, icon, global_pos):
        manager = self.manager
        if manager is None:
            return

        menu = QMenu(self)

        if not os.path.isdir(icon.path):
            menu.addAction(
                "📝 Edit in Geany",
                lambda p=icon.path: self.main_win.open_geany(p)
            )

        menu.addAction(
            "🗑️ Delete",
            lambda p=icon.path: manager.delete_desktop_item(p)
        )
        menu.addSeparator()
        menu.addAction("🔄 Refresh Desktop", manager.refresh_desktop)
        menu.addAction("🎨 Change Background Color", manager.change_wallpaper_color)
        menu.addSeparator()
        menu.addAction("📄 New File", manager.create_new_file)
        menu.addAction("📁 New Folder", manager.create_new_folder)

        menu.exec_(global_pos)

    def _show_background_menu(self, global_pos):
        manager = self.manager
        if manager is None:
            return

        menu = QMenu(self)
        menu.addAction("🔄 Refresh Desktop", manager.refresh_desktop)
        menu.addAction("🎨 Change Background Color", manager.change_wallpaper_color)
        menu.addSeparator()
        menu.addAction("📄 New File", manager.create_new_file)
        menu.addAction("📁 New Folder", manager.create_new_folder)
        menu.addAction(
            "💻 Open Terminal Here",
            lambda: self.main_win.open_terminal(start_dir=self.main_win.desktop_path)
        )
        menu.exec_(global_pos)

    def open_icon(self, icon):
        path = icon.path
        if not path or not os.path.exists(path):
            return

        if os.path.isdir(path):
            self.main_win.open_fm(start_dir=path)
        elif path.endswith(".py"):
            self.main_win.run_py(path)
        elif path.lower().endswith((".png", ".jpg", ".bmp")):
            self.main_win.open_paint(path)
        else:
            self.main_win.open_geany(path)

    def get_positions(self):
        return {icon.name: [icon.x(), icon.y()] for icon in self.icons}

    def restore_positions(self, positions):
        for index, icon in enumerate(self.icons):
            saved = positions.get(icon.name)

            if isinstance(saved, (list, tuple)) and len(saved) == 2:
                try:
                    icon.move(int(saved[0]), int(saved[1]))
                    continue
                except (ValueError, TypeError):
                    pass

            col = index // 5
            row = index % 5
            icon.move(
                self.LEFT + col * self.GRID_W,
                self.TOP + row * self.GRID_H
            )

        self._overlay.raise_()

class DesktopMdiArea(QMdiArea):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win

        self.desktop_list = DesktopCanvas(self, self.viewport())
        self.desktop_list._positions_changed = self.save_desktop_positions
        self.desktop_list.setGeometry(
            0, 0,
            self.viewport().width(),
            self.viewport().height()
        )
        self.desktop_list.lower()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.desktop_list.setGeometry(
            0, 0,
            self.viewport().width(),
            self.viewport().height()
        )
        self.desktop_list.lower()

    def update_theme(self, theme_pref, custom_bg=None):
        if custom_bg:
            bg_color = custom_bg
        else:
            bg_color = self.main_win.config.get("bg_color", "#696969")

        self.setBackground(QBrush(QColor(bg_color)))

    def _saved_desktop_positions(self):
        all_positions = self.main_win.config.get("desktop_positions", {})
        positions = all_positions.get(self.main_win.active_user, {})
        return positions if isinstance(positions, dict) else {}

    def save_desktop_positions(self):
        all_positions = self.main_win.config.setdefault(
            "desktop_positions", {}
        )
        all_positions[self.main_win.active_user] = (
            self.desktop_list.get_positions()
        )
        save_config(self.main_win.config)

    def refresh_desktop(self):
        self.desktop_list.clear()
        desktop_path = self.main_win.desktop_path

        if not os.path.exists(desktop_path):
            os.makedirs(desktop_path, exist_ok=True)

        try:
            for item_name in sorted(
                os.listdir(desktop_path),
                key=str.lower
            ):
                full_path = os.path.join(desktop_path, item_name)
                is_dir = os.path.isdir(full_path)

                if is_dir:
                    icon = self.style().standardIcon(QStyle.SP_DirIcon)
                elif item_name.lower().endswith(
                    (".png", ".jpg", ".bmp")
                ):
                    icon = QIcon(full_path)
                elif item_name.lower().endswith(".py"):
                    icon = self.style().standardIcon(
                        QStyle.SP_ComputerIcon
                    )
                else:
                    icon = self.style().standardIcon(QStyle.SP_FileIcon)

                self.desktop_list.add_desktop_item(
                    item_name,
                    full_path,
                    icon
                )

        except Exception as e:
            print(f"Error loading desktop items: {e}")

        saved = self._saved_desktop_positions()

        # Run after child widgets have been created.
        QTimer.singleShot(
            0,
            lambda positions=saved:
                self.desktop_list.restore_positions(positions)
        )

    def desktop_menu(self, pos):
        # Compatibility method kept for existing callers.
        self.desktop_list._context_menu(pos)

    def change_wallpaper_color(self):
        curr_hex = self.main_win.config.get(
            "bg_color",
            "#696969"
        )
        color = QColorDialog.getColor(
            QColor(curr_hex),
            self,
            "Select Desktop Background Color"
        )

        if color.isValid():
            hex_code = color.name()
            self.main_win.config["bg_color"] = hex_code
            save_config(self.main_win.config)
            self.update_theme(
                self.main_win.config.get("theme", "Light"),
                custom_bg=hex_code
            )

    def create_new_file(self):
        name, ok = QInputDialog.getText(
            self,
            "New Desktop File",
            "File Name:"
        )

        if ok and name:
            file_path = os.path.join(
                self.main_win.desktop_path,
                name
            )
            open(file_path, "a").close()
            self.refresh_desktop()

    def create_new_folder(self):
        name, ok = QInputDialog.getText(
            self,
            "New Desktop Folder",
            "Folder Name:"
        )

        if ok and name:
            folder_path = os.path.join(
                self.main_win.desktop_path,
                name
            )
            os.makedirs(folder_path, exist_ok=True)
            self.refresh_desktop()

    def delete_desktop_item(self, path):
        if QMessageBox.question(
            self,
            "Delete",
            f"Are you sure you want to delete "
            f"'{os.path.basename(path)}'?"
        ) == QMessageBox.Yes:

            name = os.path.basename(path)

            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except OSError as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Could not delete item:\n{e}"
                )
                return

            all_positions = self.main_win.config.get(
                "desktop_positions",
                {}
            )
            user_positions = all_positions.get(
                self.main_win.active_user,
                {}
            )

            if isinstance(user_positions, dict):
                user_positions.pop(name, None)
                save_config(self.main_win.config)

            self.refresh_desktop()

# --- 7. MAIN SYSTEM WITH TASKBAR AND WINDOW MINIMIZATION ---

class PythonOS(QMainWindow):
    def __init__(self, base, user, config):
        super().__init__()
        self.user_home = os.path.abspath(os.path.join(base, user))
        self.desktop_path = os.path.join(self.user_home, "Desktop")
        os.makedirs(self.desktop_path, exist_ok=True)
        
        self.active_user = user 
        self.config = config
        
        self.taskbar_buttons = {}
        
        self.mdi = DesktopMdiArea(self)
        self.setCentralWidget(self.mdi)
        self.mdi.subWindowActivated.connect(self.on_subwindow_activated)
        
        theme_pref = self.config.get("theme", "Light")
        self.mdi.update_theme(theme_pref)
        self.mdi.refresh_desktop()
        
        self.resize(1100, 750)
        self.setWindowTitle(f"Python OS 2.0 - User: {user}")
        self.init_tb()

    def init_tb(self):
        self.tb = QToolBar("Taskbar")
        self.addToolBar(Qt.BottomToolBarArea, self.tb)
        self.tb.setMovable(False)
        self.tb.setFloatable(False)
        
        self.start_btn = QPushButton(" 🪟 Menu ")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 3px;
            }
            QPushButton::menu-indicator { image: none; }
            QPushButton:hover { background-color: #005a9e; }
        """)
        
        m = QMenu(self)
        m.addAction("📁 Nemo Files", self.open_fm)
        m.addAction("🖥️ Desktop Folder", lambda: self.open_fm(start_dir=self.desktop_path))
        m.addAction("💻 Terminal", self.open_terminal)
        m.addAction("🎨 Paint", self.open_paint)
        m.addAction("🧮 Calculator", self.open_calc)
        m.addAction("📝 Geany 2.0", self.open_geany)
        m.addSeparator()
        m.addAction("⚙️ Settings", self.open_settings)
        m.addSeparator()
        m.addAction("❌ Log Out", self.close)
        self.start_btn.setMenu(m)
        self.tb.addWidget(self.start_btn)
        
        self.tb.addSeparator()
        
        self.taskbar_container = QWidget()
        self.taskbar_layout = QHBoxLayout(self.taskbar_container)
        self.taskbar_layout.setContentsMargins(5, 0, 5, 0)
        self.taskbar_layout.setSpacing(4)
        self.taskbar_layout.setAlignment(Qt.AlignLeft)
        
        self.tb.addWidget(self.taskbar_container)
        
        self.t_lbl = QLabel()
        self.t_lbl.setStyleSheet("padding-right: 10px; font-weight: bold;")
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tb.addWidget(spacer)
        self.tb.addWidget(self.t_lbl)
        
        t = QTimer(self)
        t.timeout.connect(self.upd)
        t.start(1000)

    def upd(self): 
        current_time = datetime.now().strftime("%H:%M:%S")
        self.t_lbl.setText(f"🕒 {current_time} | User: {self.active_user}")

    def add_win(self, w, t):
        sw = CustomSubWindow(self)
        sw.setWidget(w)
        sw.setWindowTitle(t)
        self.mdi.addSubWindow(sw)
        
        btn = QToolButton()
        btn.setText(t)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setMinimumWidth(100)
        btn.setMaximumWidth(160)
        btn.setStyleSheet("""
            QToolButton {
                background-color: #e1e1e1;
                border: 1px solid #b5b5b5;
                border-radius: 3px;
                padding: 4px;
                color: #000000;
            }
            QToolButton:hover {
                background-color: #d0d0d0;
            }
            QToolButton:checked {
                background-color: #0078d7;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        
        btn.clicked.connect(lambda checked, s=sw: self.toggle_window_state(s))
        
        self.taskbar_layout.addWidget(btn)
        self.taskbar_buttons[sw] = btn
        
        sw.show()
        self.mdi.setActiveSubWindow(sw)

    def toggle_window_state(self, sw):
        if sw.isHidden() or sw.isMinimized():
            sw.showNormal()
            self.mdi.setActiveSubWindow(sw)
        elif self.mdi.activeSubWindow() == sw:
            sw.hide()
        else:
            sw.showNormal()
            self.mdi.setActiveSubWindow(sw)

    def on_subwindow_activated(self, sw):
        dead_windows = [win for win in self.taskbar_buttons if not self.mdi.subWindowList().__contains__(win)]
        for dead_win in dead_windows:
            btn = self.taskbar_buttons.pop(dead_win)
            btn.deleteLater()

        for win, btn in self.taskbar_buttons.items():
            if win == sw and not win.isHidden() and not win.isMinimized():
                btn.setChecked(True)
            else:
                btn.setChecked(False)

    def sync_taskbar_button(self, sw):
        """Volané priamo z CustomSubWindow presne v momente minimalizácie,
        aby sa príslušné taskbar tlačidlo okamžite odznačilo bez čakania
        na subWindowActivated signál."""
        btn = self.taskbar_buttons.get(sw)
        if btn:
            btn.setChecked(False)

    def remove_taskbar_button(self, sw):
        """Volané priamo z CustomSubWindow.closeEvent pri zatvorení okna (klik na X),
        aby sa zodpovedajúce tlačidlo okamžite odstránilo z taskbaru namiesto
        čakania na subWindowActivated cleanup."""
        btn = self.taskbar_buttons.pop(sw, None)
        if btn:
            btn.deleteLater()

    def open_fm(self, start_dir=None): 
        self.add_win(NemoFileManager(self.user_home, self, start_dir), "📁 Nemo")
        
    def open_terminal(self, start_dir=None): 
        self.add_win(TerminalApp(self.user_home, start_dir), "💻 Terminal")
        
    def open_settings(self): 
        self.add_win(SettingsApp(self, self.user_home, self.config), "⚙️ Settings")
        
    def open_paint(self, p=None): 
        s = PaintApp(self.user_home)
        self.add_win(s, "🎨 Paint")
        if p: 
            s.open_img(p)
            
    def open_calc(self): 
        self.add_win(Calculator(), "🧮 Calculator")
        
    def open_geany(self, p=None): 
        g = GeanyEditor(self.user_home)
        self.add_win(g, "📝 Geany")
        if p: 
            g.open_f(p)
            
    def open_gallery(self, p): 
        self.add_win(GalleryApp(p), "🖼️ Gallery")
    
    def run_py(self, p):
        p = os.path.normpath(p)
        if sys.platform.startswith("win"):
            subprocess.Popen(['cmd.exe', '/k', sys.executable, p], creationflags=0x00000010)
        else:
            terminals = ['lxterminal', 'x-terminal-emulator', 'gnome-terminal', 'konsole', 'xterm']
            selected_term = None
            for term in terminals:
                if shutil.which(term):
                    selected_term = term
                    break
                    
            if selected_term:
                bash_cmd = f'{sys.executable} "{p}"; echo ""; read -p "Press Enter to close..."'
                if selected_term in ['lxterminal', 'xterm']:
                    subprocess.Popen([selected_term, '-e', f'bash -c \'{bash_cmd}\''])
                elif selected_term == 'gnome-terminal':
                    subprocess.Popen([selected_term, '--', 'bash', '-c', bash_cmd])
                else:
                    subprocess.Popen([selected_term, '-e', f'bash -c \'{bash_cmd}\''])
            else:
                QMessageBox.warning(self, "Error", "No terminal found to run the script.")

# --- 8. SECURE BOOTSTRAP ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion') 
    
    app.setStyleSheet("""
        QWidget {
            color: #000000;
        }
        QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView::section {
            background-color: #ffffff;
            color: #000000;
        }
        QMenuBar, QMenu, QToolBar, QInputDialog, QMessageBox, QDialog {
            background-color: #ffffff;
            color: #000000;
        }
        QMenu::item {
            background-color: #ffffff;
            color: #000000;
        }

        QMenu::item:selected {
            background-color: #0078d7;
            color: #ffffff;
        }
    """)

    home_base = os.path.abspath("Home")
    os.makedirs(home_base, exist_ok=True)

    config = load_config()

    if not config.get("oobe_completed"):
        oobe = OOBEDialog()
        if oobe.exec_() != QDialog.Accepted:
            sys.exit(0)
        config = load_config()

    login = LoginDialog(config)
    if login.exec_() == QDialog.Accepted:
        active_user = login.authenticated_user
        
        win = PythonOS(home_base, active_user, config)
        win.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)
