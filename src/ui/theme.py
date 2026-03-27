"""
Dark and light theme stylesheets for the application.
"""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
}
QMenuBar::item:selected {
    background-color: #313244;
}
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
}
QMenu::item:selected {
    background-color: #313244;
}
QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    border: 1px solid #313244;
}
QTableView::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #181825;
    color: #cdd6f4;
    padding: 6px;
    border: 1px solid #313244;
    font-weight: bold;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton#primaryButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #74c7ec;
}
QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#dangerButton:hover {
    background-color: #eba0ac;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #cdd6f4;
    padding: 8px 16px;
    border: 1px solid #313244;
}
QTabBar::tab:selected {
    background-color: #313244;
    border-bottom: 2px solid #89b4fa;
}
QScrollBar:vertical {
    background-color: #181825;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar:horizontal {
    background-color: #181825;
    height: 12px;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 4px;
    min-width: 20px;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel#subtitleLabel {
    font-size: 14px;
    color: #a6adc8;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QSplitter::handle {
    background-color: #313244;
}
"""

LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #eff1f5;
    color: #4c4f69;
}
QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #e6e9ef;
    color: #4c4f69;
}
QMenuBar::item:selected {
    background-color: #ccd0da;
}
QMenu {
    background-color: #eff1f5;
    color: #4c4f69;
    border: 1px solid #ccd0da;
}
QMenu::item:selected {
    background-color: #ccd0da;
}
QTableView {
    background-color: #eff1f5;
    alternate-background-color: #e6e9ef;
    color: #4c4f69;
    gridline-color: #ccd0da;
    selection-background-color: #bcc0cc;
    selection-color: #4c4f69;
    border: 1px solid #ccd0da;
}
QTableView::item {
    padding: 4px 8px;
}
QHeaderView::section {
    background-color: #e6e9ef;
    color: #4c4f69;
    padding: 6px;
    border: 1px solid #ccd0da;
    font-weight: bold;
}
QPushButton {
    background-color: #ccd0da;
    color: #4c4f69;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 8px 16px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #bcc0cc;
}
QPushButton#primaryButton {
    background-color: #1e66f5;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#primaryButton:hover {
    background-color: #2a6ff7;
}
QPushButton#dangerButton {
    background-color: #d20f39;
    color: #ffffff;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #1e66f5;
}
QProgressBar {
    background-color: #ccd0da;
    border: 1px solid #bcc0cc;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 3px;
}
QTabWidget::pane {
    border: 1px solid #ccd0da;
    background-color: #eff1f5;
}
QTabBar::tab {
    background-color: #e6e9ef;
    color: #4c4f69;
    padding: 8px 16px;
    border: 1px solid #ccd0da;
}
QTabBar::tab:selected {
    background-color: #ccd0da;
    border-bottom: 2px solid #1e66f5;
}
QScrollBar:vertical {
    background-color: #e6e9ef;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #bcc0cc;
    border-radius: 4px;
    min-height: 20px;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #1e66f5;
}
QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
"""
