"""
ClaimsCo Document Tools - Main entry point.
Launches the three-tab app (Document Renamer, Privacy Redaction, Claude Extraction Pack).
"""
import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.core.settings import Settings, APP_VERSION
from src.ui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ClaimsCo Document Tools")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ClaimsCo")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    settings = Settings()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
