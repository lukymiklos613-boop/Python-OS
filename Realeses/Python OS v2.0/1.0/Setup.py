import sys
import os
import subprocess
import shutil
import zipfile
from PyQt5.QtWidgets import (QApplication, QWizard, QWizardPage, QLabel, 
                             QPushButton, QLineEdit, QFileDialog, QVBoxLayout, 
                             QHBoxLayout, QMessageBox, QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal, Qt

# Automatically try to install PyQt5
try:
    import PyQt5
except ImportError:
    os.system(sys.executable + " -m pip install PyQt5")

# --- BACKGROUND WORKER FOR EXTRACTION ---
class InstallWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd_7z, archive_path, target_dir, archive_type="7z", is_repair=False):
        super().__init__()
        self.cmd_7z = cmd_7z
        self.archive_path = archive_path
        self.target_dir = target_dir
        self.archive_type = archive_type
        self.is_repair = is_repair

    def run(self):
        try:
            os.makedirs(self.target_dir, exist_ok=True)
            if self.archive_type == "zip":
                with zipfile.ZipFile(self.archive_path, "r") as archive:
                    archive.extractall(self.target_dir)
            else:
                if not self.is_repair:
                    cmd = [self.cmd_7z, "x", self.archive_path, f"-o{self.target_dir}", "-y"]
                else:
                    cmd = [self.cmd_7z, "e", self.archive_path, f"-o{self.target_dir}", "Python OS 2.0.py", "-r", "-y"]

                subprocess.run(cmd, capture_output=True, text=True, check=True)

            self.finished.emit(True, "Success")
        except subprocess.CalledProcessError as e:
            error_details = e.stderr if e.stderr else e.stdout
            self.finished.emit(False, error_details)


# --- WIZARD PAGES ---
class WelcomePage(QWizardPage):
    def __init__(self, archive_exists, cmd_7z_exists):
        super().__init__()
        self.setTitle("Welcome to the Python OS 2.0 Setup Wizard")
        
        layout = QVBoxLayout()
        label = QLabel("This wizard will guide you through the installation or repair of Python OS 2.0.\n\n"
                       "It is recommended that you close all other applications before starting Setup. "
                       "This will make it possible to update relevant system files without having to reboot your computer.\n\n"
                       "The installer accepts OS.7z or Python OS 2.0.zip.\n\n"
                       "Click Next to continue.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addSpacing(20)

        # Status Check
        if not archive_exists:
            status = "<font color='red'><b>Error:</b> 'OS.7z' not found!</font>"
        elif (not cmd_7z_exists
              and self.wizard().archive_path is not None
              and os.path.basename(self.wizard().archive_path) == "OS.7z"):
            status = "<font color='red'><b>Error:</b> 7-Zip is not installed on your system!</font>"
        else:
            status = "<font color='green'>✔ System requirements met.</font>"
            
        layout.addWidget(QLabel(status))
        self.setLayout(layout)

    def isComplete(self):
        # Only allow Next if requirements are met
        installer = self.wizard()
        installer = self.wizard()
        if installer.archive_path is None:
            return False
        if installer.archive_type == "7z":
            return installer.cmd_7z is not None
        return True


class DestinationPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Choose Install Location")
        self.setSubTitle("Choose the folder in which to install Python OS 2.0.")
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Setup will install Python OS 2.0 in the following folder. "
                                "To install in a different folder, click Browse and select another folder."))
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(os.path.join(os.path.expanduser("~"), "Python OS 2.0"))
        
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_folder)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.btn_browse)
        layout.addLayout(path_layout)
        
        # Register the field so other pages can access the path
        self.registerField("install_path", self.path_input)
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.path_input.text())
        if folder:
            self.path_input.setText(os.path.normpath(folder))


class InstallPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installing")
        self.setSubTitle("Please wait while Python OS 2.0 is being installed.")
        
        layout = QVBoxLayout()
        self.status_label = QLabel("Ready to install...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100) # Setting to (0,0) makes it a continuous bouncing bar
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        self.is_finished = False

    def initializePage(self):
        self.status_label.setText("Extracting files...")
        self.progress_bar.setRange(0, 0) # Infinite loading animation during extraction
        
        wizard = self.wizard()
        target_dir = self.field("install_path")
        
        # Start the background thread
        self.worker = InstallWorker(
            wizard.cmd_7z,
            wizard.archive_path,
            target_dir,
            archive_type=wizard.archive_type,
            is_repair=False
        )
        self.worker.finished.connect(self.on_installation_finished)
        self.worker.start()

    def on_installation_finished(self, success, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.is_finished = True
        
        if success:
            self.status_label.setText("<font color='green'>Installation Complete!</font>")
            self.wizard().button(QWizard.NextButton).setEnabled(True)
            self.completeChanged.emit()
            
            # Launch the app automatically
            target_dir = self.field("install_path")
            # The archive is expected to place the application directly in the install folder.
            app_path = os.path.join(target_dir, "Python OS", "Python OS.py")
            if os.path.exists(app_path):
                subprocess.Popen([sys.executable, app_path], cwd=os.path.dirname(app_path))
            else:
                QMessageBox.warning(
                    self,
                    "Python OS 2.0",
                    "Installation completed, but 'Python OS.py' was not found in the 'Python OS' folder."
                )
        else:
            self.status_label.setText("<font color='red'>Installation Failed.</font>")
            QMessageBox.critical(self, "Error", f"Extraction failed:\n{message}")
            self.completeChanged.emit()

    def isComplete(self):
        return self.is_finished


# --- MAIN WIZARD APPLICATION ---
class PythonOSSetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.installer_dir = os.path.dirname(os.path.abspath(__file__))
        self.archive_7z = os.path.join(self.installer_dir, "OS.7z")
        self.archive_zip = os.path.join(self.installer_dir, "Python OS 2.0.zip")
        self.archive_path = None
        self.archive_type = None
        self.cmd_7z = None
        
        self.setWindowTitle("Python OS 2.0 Setup")
        self.resize(550, 400)
        self.setWizardStyle(QWizard.ModernStyle)
        
        self.detect_7z()
        
        if os.path.exists(self.archive_7z):
            self.archive_path = self.archive_7z
            self.archive_type = "7z"
        elif os.path.exists(self.archive_zip):
            self.archive_path = self.archive_zip
            self.archive_type = "zip"

        archive_exists = self.archive_path is not None

        # Add Pages
        self.addPage(WelcomePage(archive_exists, self.cmd_7z is not None))
        self.addPage(DestinationPage())
        self.addPage(InstallPage())

    def detect_7z(self):
        for cmd in ["7z", "7zz"]:
            if shutil.which(cmd):
                self.cmd_7z = cmd
                return

        if sys.platform.startswith("win"):
            possible_paths = [
                r"C:\Program Files\7-Zip\7z.exe",
                os.path.expandvars(r"%ProgramFiles%\7-Zip\7z.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\7-Zip\7z.exe")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    self.cmd_7z = path
                    return


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    wizard = PythonOSSetupWizard()
    wizard.show()
    sys.exit(app.exec_())
