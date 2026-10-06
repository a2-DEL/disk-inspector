# -*- coding: utf-8 -*-
"""主题样式：浅色 / 深色，主色调浅蓝，小白友好。"""
from __future__ import annotations

LIGHT_QSS = """
QWidget{font-family:"Microsoft YaHei";font-size:13px;color:#1F2328;}
QMainWindow,QWidget#root{background:#F3F6FB;}
QFrame#card{background:#FFFFFF;border:1px solid #E4E8EE;border-radius:12px;}
QFrame#cardDark{background:#FFFFFF;border:1px solid #E4E8EE;border-radius:12px;}
QLabel#h1{font-size:22px;font-weight:700;color:#1F2328;}
QLabel#h2{font-size:16px;font-weight:700;color:#1F2328;}
QLabel#sub{color:#8B949E;font-size:12px;}
QLabel#bigNum{font-size:26px;font-weight:700;color:#2D7FF9;}
QLabel#warn{color:#E5484D;font-weight:600;}
QLabel#good{color:#30A46C;font-weight:600;}
QLabel#org{color:#F5A524;font-weight:600;}
QPushButton{background:#FFFFFF;border:1px solid #D7DDE5;border-radius:8px;padding:8px 16px;color:#1F2328;}
QPushButton:hover{border-color:#2D7FF9;color:#2D7FF9;background:#F0F6FF;}
QPushButton:pressed{background:#E3EEFF;}
QPushButton:disabled{color:#B7BEC9;background:#F6F7F9;border-color:#EAECEF;}
QPushButton#primary{background:#2D7FF9;color:#FFFFFF;border:none;font-weight:600;}
QPushButton#primary:hover{background:#1B6FE0;color:#FFFFFF;}
QPushButton#big{font-size:16px;font-weight:700;padding:14px 22px;border-radius:12px;}
QPushButton#bigPrimary{font-size:16px;font-weight:700;padding:14px 22px;border-radius:12px;background:#2D7FF9;color:#FFFFFF;border:none;}
QPushButton#bigPrimary:hover{background:#1B6FE0;color:#FFFFFF;}
QPushButton#danger{background:#E5484D;color:#FFFFFF;border:none;font-weight:600;}
QPushButton#danger:hover{background:#D13438;color:#FFFFFF;}
QPushButton#ghost{background:transparent;border:1px solid #D7DDE5;color:#57606A;}
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTextEdit{background:#FFFFFF;border:1px solid #D7DDE5;border-radius:8px;padding:7px 10px;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus{border-color:#2D7FF9;}
QProgressBar{background:#E9EDF3;border:none;border-radius:8px;height:16px;text-align:center;color:#1F2328;font-size:11px;}
QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6FB1FF,stop:1 #2D7FF9);border-radius:8px;}
QTreeWidget,QTableWidget,QListWidget{background:#FFFFFF;border:1px solid #E4E8EE;border-radius:10px;alternate-background-color:#F8FAFD;}
QTreeWidget::item,QTableWidget::item{padding:4px 6px;}
QTreeWidget::item:selected,QTableWidget::item:selected{background:#E3EEFF;color:#1F2328;}
QHeaderView::section{background:#F0F4FA;border:none;border-bottom:1px solid #E4E8EE;border-right:1px solid #EDF0F4;padding:8px;font-weight:600;color:#424A53;}
QScrollBar:vertical{background:#F3F6FB;width:10px;border-radius:5px;}
QScrollBar::handle:vertical{background:#C6CDD6;border-radius:5px;min-height:30px;}
QScrollBar::handle:vertical:hover{background:#A9B2BE;}
QScrollBar:horizontal{background:#F3F6FB;height:10px;border-radius:5px;}
QScrollBar::handle:horizontal{background:#C6CDD6;border-radius:5px;min-width:30px;}
QTabWidget::pane{border:1px solid #E4E8EE;border-radius:10px;background:#FFFFFF;top:-1px;}
QTabBar::tab{background:#E9EDF3;padding:8px 18px;border-top-left-radius:8px;border-top-right-radius:8px;margin-right:2px;}
QTabBar::tab:selected{background:#2D7FF9;color:#FFFFFF;}
QCheckBox{spacing:6px;}
QGroupBox{border:1px solid #E4E8EE;border-radius:10px;margin-top:12px;padding-top:10px;font-weight:600;}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;color:#424A53;}
QSplitter::handle{background:#E4E8EE;border-radius:2px;}
"""

DARK_QSS = """
QWidget{font-family:"Microsoft YaHei";font-size:13px;color:#E6EAF0;}
QMainWindow,QWidget#root{background:#14181F;}
QFrame#card,QFrame#cardDark{background:#1D232C;border:1px solid #2A323D;border-radius:12px;}
QLabel#h1{font-size:22px;font-weight:700;color:#F0F4F8;}
QLabel#h2{font-size:16px;font-weight:700;color:#F0F4F8;}
QLabel#sub{color:#8B949E;font-size:12px;}
QLabel#bigNum{font-size:26px;font-weight:700;color:#6FB1FF;}
QLabel#warn{color:#FF6369;font-weight:600;}
QLabel#good{color:#56C28B;font-weight:600;}
QLabel#org{color:#FFB454;font-weight:600;}
QPushButton{background:#232B36;border:1px solid #37404D;border-radius:8px;padding:8px 16px;color:#E6EAF0;}
QPushButton:hover{border-color:#6FB1FF;color:#6FB1FF;background:#1D2836;}
QPushButton:pressed{background:#15202E;}
QPushButton:disabled{color:#5C6672;background:#1A2028;border-color:#2A323D;}
QPushButton#primary{background:#2D7FF9;color:#FFFFFF;border:none;font-weight:600;}
QPushButton#primary:hover{background:#4A93FA;color:#FFFFFF;}
QPushButton#big{font-size:16px;font-weight:700;padding:14px 22px;border-radius:12px;}
QPushButton#bigPrimary{font-size:16px;font-weight:700;padding:14px 22px;border-radius:12px;background:#2D7FF9;color:#FFFFFF;border:none;}
QPushButton#bigPrimary:hover{background:#1B6FE0;color:#FFFFFF;}
QPushButton#danger{background:#C93A3F;color:#FFFFFF;border:none;font-weight:600;}
QPushButton#danger:hover{background:#E5484D;color:#FFFFFF;}
QPushButton#ghost{background:transparent;border:1px solid #37404D;color:#9AA4B0;}
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTextEdit{background:#1A2028;border:1px solid #37404D;border-radius:8px;padding:7px 10px;color:#E6EAF0;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus{border-color:#2D7FF9;}
QComboBox QAbstractItemView{background:#1D232C;color:#E6EAF0;selection-background-color:#2D7FF9;}
QProgressBar{background:#2A323D;border:none;border-radius:8px;height:16px;text-align:center;color:#E6EAF0;font-size:11px;}
QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4A93FA,stop:1 #2D7FF9);border-radius:8px;}
QTreeWidget,QTableWidget,QListWidget{background:#1A2028;border:1px solid #2A323D;border-radius:10px;alternate-background-color:#1D232C;}
QTreeWidget::item,QTableWidget::item{padding:4px 6px;}
QTreeWidget::item:selected,QTableWidget::item:selected{background:#1D3A5F;color:#F0F4F8;}
QHeaderView::section{background:#232B36;border:none;border-bottom:1px solid #2A323D;border-right:1px solid #2A323D;padding:8px;font-weight:600;color:#9AA4B0;}
QScrollBar:vertical{background:#14181F;width:10px;border-radius:5px;}
QScrollBar::handle:vertical{background:#3A4350;border-radius:5px;min-height:30px;}
QScrollBar::handle:vertical:hover{background:#4A5563;}
QScrollBar:horizontal{background:#14181F;height:10px;border-radius:5px;}
QScrollBar::handle:horizontal{background:#3A4350;border-radius:5px;min-width:30px;}
QTabWidget::pane{border:1px solid #2A323D;border-radius:10px;background:#1D232C;top:-1px;}
QTabBar::tab{background:#232B36;padding:8px 18px;border-top-left-radius:8px;border-top-right-radius:8px;margin-right:2px;color:#9AA4B0;}
QTabBar::tab:selected{background:#2D7FF9;color:#FFFFFF;}
QCheckBox{spacing:6px;}
QGroupBox{border:1px solid #2A323D;border-radius:10px;margin-top:12px;padding-top:10px;font-weight:600;}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;color:#9AA4B0;}
QSplitter::handle{background:#2A323D;border-radius:2px;}
"""


def get_qss(theme: str) -> str:
    return DARK_QSS if theme == "dark" else LIGHT_QSS
