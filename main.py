"""
Claim File Renamer - Main entry point.
A local-first bulk PDF renaming application for insurance claim documents.
"""
import sys
import os

# Ensure src package is importable when running from project root or as frozen exe
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    _base = sys._MEIPASS
else:
    _base = os.path.dirname(os.path.abspath(__file__))
if _base not in sys.path:
    sys.path.insert(0, _base)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from src.core.settings import Settings
from src.ui.main_window import MainWindow


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Claim File Renamer")
    app.setApplicationVersion("1.2.0")
    app.setOrganizationName("ClaimFileRenamer")

    # Set icon if available
    icon_path = os.path.join(_base, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = Settings()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
