import sys
import os
import subprocess
import shutil
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, 
                             QLineEdit, QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox)

# Automatically try to install PyQt5 using the safe -m pip method
try:
    import PyQt5
except ImportError:
    os.system(sys.executable + " -m pip install PyQt5")

class PythonSystemInstaller(QWidget):
    def __init__(self):
        super().__init__()
        self.installer_dir = os.path.dirname(os.path.abspath(__file__))
        self.archive_7z = os.path.join(self.installer_dir, "Python System.7z")
        
        # --- UNIVERSAL 7-ZIP DETECTION (WIN + LINUX) ---
        self.cmd_7z = None
        self.detect_7z()
        
        self.initUI()
        
    def detect_7z(self):
        """Attempts to locate 7z on any operating system."""
        # 1. Check if 7z is available in the global system PATH (Linux or well-configured Windows)
        for cmd in ["7z", "7zz"]:
            if shutil.which(cmd):
                self.cmd_7z = cmd
                return

        # 2. If on Windows and global command is missing, check typical installation paths
        if sys.platform.startswith("win"):
            possible_paths = [
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files\7-Zip\7-Zip\7z.exe",
                os.path.expandvars(r"%ProgramFiles%\7-Zip\7z.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\7-Zip\7z.exe")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    self.cmd_7z = f'"{path}"'
                    return

    def initUI(self):
        self.setWindowTitle("Python System 1.0 - Installer & Repair Tool")
        self.resize(500, 250)
        
        layout = QVBoxLayout()
        
        # Title
        self.title_lbl = QLabel("<b>Welcome to Python System 1.0 Installation Wizard</b>")
        self.title_lbl.setStyleSheet("font-size: 12pt; margin-bottom: 10px;")
        layout.addWidget(self.title_lbl)
        
        # Archive status check
        if not os.path.exists(self.archive_7z):
            self.status_lbl = QLabel("<font color='red'><b>Warning:</b> 'Python System.7z' archive not found in the current folder!</font>")
        elif self.cmd_7z is None:
            self.status_lbl = QLabel("<font color='orange'><b>Warning:</b> 7-Zip was not detected on your system. Please install it.</font>")
        else:
            self.status_lbl = QLabel("<font color='green'>System ready for installation or component repair.</font>")
        layout.addWidget(self.status_lbl)
        
        layout.addWidget(QLabel("<hr>"))
        
        # Path selection
        layout.addWidget(QLabel("Select Installation Destination Directory:"))
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(os.path.join(os.path.expanduser("~"), "PythonSystem"))
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.btn_browse)
        layout.addLayout(path_layout)
        
        layout.addStretch()
        
        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_install = QPushButton("🚀 Fresh Installation")
        self.btn_install.clicked.connect(self.run_install)
        
        self.btn_repair = QPushButton("🔧 Repair Core Files")
        self.btn_repair.clicked.connect(self.run_repair)
        
        if not os.path.exists(self.archive_7z) or self.cmd_7z is None:
            self.btn_install.setEnabled(False)
            self.btn_repair.setEnabled(False)
            
        btn_layout.addWidget(self.btn_install)
        btn_layout.addWidget(self.btn_repair)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.path_input.text())
        if folder:
            self.path_input.setText(os.path.normpath(folder))

    def run_install(self):
        target_dir = os.path.normpath(self.path_input.text().strip())
        if not target_dir:
            QMessageBox.warning(self, "Error", "Please select a valid destination folder.")
            return
            
        os.makedirs(target_dir, exist_ok=True)
        
        # Command: extract everything from the archive into the target directory
        install_command = f"{self.cmd_7z} x \"{self.archive_7z}\" -o\"{target_dir}\" -y"
        
        try:
            # shell=True handles quotes correctly on Windows paths
            res = subprocess.run(install_command, shell=True, capture_output=True, text=True, check=True)
            QMessageBox.information(
                self, 
                "Success", 
                f"Python System 1.0 has been successfully installed!\n\n"
                f"Location:\n{target_dir}\n\n"
                f"Python System will start automaticly."
            )
            os.chdir(target_dir)
            os.chdir("Python System")
            subprocess.Popen([sys.executable, "Python System.py"])
        except subprocess.CalledProcessError as e:
            error_details = e.stderr if e.stderr else e.stdout
            QMessageBox.critical(self, "Installation Error", f"Failed to extract the system archive.\n\nDetails:\n{error_details}")

    def run_repair(self):
        """Extracts and overwrites only the core system files if corrupted."""
        target_dir = os.path.normpath(self.path_input.text().strip())
        if not os.path.exists(target_dir):
            QMessageBox.warning(self, "Repair Error", "The target installation folder does not exist. Perform a fresh installation instead.")
            return

        # List files inside the archive to find the core python script
        list_command = f"{self.cmd_7z} l \"{self.archive_7z}\""
        try:
            res = subprocess.run(list_command, shell=True, capture_output=True, text=True, check=True)
            
            # Look for the main system file names (handles both case variants)
            target_filenames = ["pythonsystem.py", "pysys.py", "gui.py"]
            files_to_extract = []
            
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    internal_path = line.split(parts[2])[-1].strip()
                    normalized_path = internal_path.replace('\\', '/')
                    basename = os.path.basename(normalized_path).lower()
                    if basename in target_filenames:
                        files_to_extract.append(internal_path)
            
            if not files_to_extract:
                QMessageBox.warning(
                    self, 
                    "Repair Error", 
                    "Could not find any system core scripts inside the archive."
                )
                return
                
            # Extract only the identified target core files
            files_str = " ".join([f"\"{f}\"" for f in files_to_extract])
            repair_command = f"{self.cmd_7z} e \"{self.archive_7z}\" -o\"{target_dir}\" {files_str} -y"
            subprocess.run(repair_command, shell=True, capture_output=True, text=True, check=True)
            
            fixed_list_str = "\n".join(["- " + os.path.basename(f.replace('\\', '/')) for f in files_to_extract])
            
            QMessageBox.information(
                self, 
                "Repair Completed", 
                f"Core files were successfully restored from the archive!\n\n"
                f"The following files have been checked/overwritten:\n{fixed_list_str}"
            )
            
        except subprocess.CalledProcessError as e:
            error_details = e.stderr if e.stderr else e.stdout
            QMessageBox.critical(self, "Repair Error", f"Failed to extract files for repair.\n\nDetails:\n{error_details}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    installer = PythonSystemInstaller()
    installer.show()
    sys.exit(app.exec_())