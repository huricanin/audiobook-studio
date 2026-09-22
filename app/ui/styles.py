from __future__ import annotations

STYLESHEET = """
QMainWindow, QWidget {
    background: #12161c;
    color: #e8e4dc;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
}
QLabel#hero {
    font-size: 22px;
    font-weight: 600;
    color: #f4f1ea;
}
QLabel#muted {
    color: #9aa3ad;
}
QGroupBox {
    border: 1px solid #2a333d;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 12px 8px 12px;
    background: #171d24;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #d4a373;
}
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {
    background: #0f1419;
    border: 1px solid #2a333d;
    border-radius: 8px;
    padding: 6px 8px;
    color: #e8e4dc;
    selection-background-color: #3d4f3a;
}
QComboBox QAbstractItemView {
    background: #0f1419;
    color: #e8e4dc;
    selection-background-color: #2c3a48;
}
QPushButton {
    background: #2a333d;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    color: #f4f1ea;
}
QPushButton:hover {
    background: #36424e;
}
QPushButton#primary {
    background: #c08552;
    color: #14110d;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #d4a373;
}
QPushButton#danger {
    background: #5a2e2e;
}
QPushButton:disabled {
    background: #232a31;
    color: #6b7380;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #2a333d;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #d4a373;
}
QProgressBar {
    border: 1px solid #2a333d;
    border-radius: 8px;
    background: #0f1419;
    text-align: center;
    color: #e8e4dc;
    height: 18px;
}
QProgressBar::chunk {
    background: #c08552;
    border-radius: 7px;
}
QCheckBox {
    spacing: 8px;
}
"""
