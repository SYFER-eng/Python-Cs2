import webbrowser
from PyQt6.QtWidgets import QMessageBox
import sys
import time
import threading
import json
import os
import math
import struct
import requests
import pymem
import pymem.process
import win32api
import win32con
import win32gui
import psutil
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QApplication


def get_offsets_and_client_dll():
    try:
        offsets_url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/offsets.json"
        client_dll_url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/client_dll.json"

        offsets_response = requests.get(offsets_url, timeout=10)
        client_dll_response = requests.get(client_dll_url, timeout=10)

        return offsets_response.json(), client_dll_response.json()
    except:
        return {}, {}


def w2s_batch(view_matrix, positions, width, height):
    results = []
    for x, y, z in positions:
        w = view_matrix[12] * x + view_matrix[13] * y + view_matrix[14] * z + view_matrix[15]
        if w < 0.01:
            results.append((-999, -999))
            continue

        screen_x = (view_matrix[0] * x + view_matrix[1] * y + view_matrix[2] * z + view_matrix[3]) / w
        screen_y = (view_matrix[4] * x + view_matrix[5] * y + view_matrix[6] * z + view_matrix[7]) / w

        x = (width / 2.0) + (0.5 * screen_x * width + 0.5)
        y = (height / 2.0) - (0.5 * screen_y * height + 0.5)

        results.append((int(x), int(y)))
    return results


def load_settings():
    try:
        with open("Default.json", "r") as f:
            return json.load(f)
    except:
        return {
            "aim_active": True,
            "aim_key": "CTRL",
            "aim_radius": 80,
            "aim_smooth": 3.0,
            "fov_show": True,
            "fov_color": (255, 255, 255, 100),
            "esp_active": True,
            "esp_color": (255, 255, 255, 255),
            "esp_show_box": True,
            "esp_show_health": True,
            "esp_show_name": True,
            "esp_show_weapon": True,
            "esp_box_color": (0, 255, 0, 255),
            "esp_health_color": (255, 0, 0, 255),
            "esp_name_color": (255, 255, 255, 255),
            "esp_weapon_color": (255, 255, 0, 255),
        }


def save_settings(settings):
    try:
        with open("Default.json", "w") as f:
            json.dump(settings, f, indent=2)
    except:
        pass


current_settings = load_settings()


def get_current_settings():
    return current_settings


class AnimatedSlider(QtWidgets.QSlider):
    def __init__(self, orientation):
        super().__init__(orientation)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 2px solid #666;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(30,30,30,255), stop:1 rgba(60,60,60,255));
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(220,220,220,255), stop:1 rgba(255,255,255,255));
                border: 2px solid #fff;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,255), stop:1 rgba(240,240,240,255));
                border: 2px solid #ddd;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(180,180,180,255), stop:1 rgba(220,220,220,255));
                border: 1px solid #fff;
                height: 8px;
                border-radius: 4px;
            }
        """)


class ColorPicker(QtWidgets.QPushButton):
    colorChanged = QtCore.pyqtSignal()

    def __init__(self, color):
        super().__init__()
        self.color = color
        self.setFixedSize(40, 30)
        self.update_style()
        self.clicked.connect(self.pick_color)

    def update_style(self):
        r, g, b = self.color[:3]
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #fff;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border: 2px solid #ccc;
            }}
        """)

    def pick_color(self):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(*self.color[:3]))
        if color.isValid():
            self.color = (color.red(), color.green(), color.blue(), self.color[3] if len(self.color) > 3 else 255)
            self.update_style()
            self.colorChanged.emit()


class KeyPicker(QtWidgets.QPushButton):
    keyChanged = QtCore.pyqtSignal()

    def __init__(self, key):
        super().__init__()
        self.current_key = key
        self.setText(key)
        self.setFixedSize(80, 30)
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(60,60,60,255), stop:1 rgba(80,80,80,255));
                color: #fff;
                border: 2px solid #fff;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(80,80,80,255), stop:1 rgba(100,100,100,255));
            }
        """)
        self.clicked.connect(self.pick_key)

    def pick_key(self):
        keys = ["CTRL", "SHIFT", "ALT", "SPACE", "X", "C", "V", "F", "G", "H"]
        key, ok = QtWidgets.QInputDialog.getItem(self, "Select Key", "Choose aim key:", keys, keys.index(self.current_key), False)
        if ok:
            self.current_key = key
            self.setText(key)
            self.keyChanged.emit()


class SettingsMenu(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.settings = get_current_settings()
        self.init_ui()
        self.setup_animations()

    def init_ui(self):
        self.setWindowTitle("Syfer-eng")
        self.setFixedSize(800, 420)  
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15,15,15,250), stop:0.5 rgba(25,25,25,250), stop:1 rgba(15,15,15,250));
                color: #fff;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                border-radius: 15px;
                border: 2px solid #444;
            }
            QCheckBox {
                color: #fff;
                font-size: 13px;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #fff;
                border-radius: 3px;
                background: rgba(40,40,40,255);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(200,200,200,255), stop:1 rgba(255,255,255,255));
            }
            QLabel {
                color: #fff;
                font-size: 12px;
                font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #666;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                color: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #fff;
                font-size: 14px;
            }
        """)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("Syfer-eng")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #fff;
                padding: 8px 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(60,60,60,200), stop:0.5 rgba(80,80,80,200), stop:1 rgba(60,60,60,200));
                border-radius: 8px;
                border: 1px solid #888;
            }
        """)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        close_btn = QtWidgets.QPushButton("\u2715")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(80,80,80,255), stop:1 rgba(60,60,60,255));
                color: #fff;
                border: 2px solid #888;
                border-radius: 15px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(120,120,120,255), stop:1 rgba(100,100,100,255));
            }
        """)
        close_btn.clicked.connect(self.hide)

        title_layout.addWidget(title_label)
        title_layout.addWidget(close_btn)
        main_layout.addLayout(title_layout)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(20)

        aimbot_group = QtWidgets.QGroupBox("Aiming things")
        aimbot_layout = QtWidgets.QVBoxLayout()
        aimbot_layout.setSpacing(12)

        self.aim_active = QtWidgets.QCheckBox("Enable Aimbot")
        self.aim_active.setChecked(self.settings["aim_active"])
        self.aim_active.toggled.connect(self.update_settings)
        aimbot_layout.addWidget(self.aim_active)

        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(QtWidgets.QLabel("Aim Key:"))
        self.aim_key = KeyPicker(self.settings["aim_key"])
        self.aim_key.keyChanged.connect(self.update_settings)
        key_layout.addWidget(self.aim_key)
        key_layout.addStretch()
        aimbot_layout.addLayout(key_layout)

        radius_layout = QtWidgets.QVBoxLayout()
        radius_header = QtWidgets.QHBoxLayout()
        radius_header.addWidget(QtWidgets.QLabel("FOV Radius:"))
        self.radius_label = QtWidgets.QLabel(str(self.settings["aim_radius"]))
        self.radius_label.setStyleSheet("color: #fff; font-weight: bold;")
        radius_header.addWidget(self.radius_label)
        radius_header.addStretch()
        radius_layout.addLayout(radius_header)

        self.aim_radius = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.aim_radius.setRange(10, 200)
        self.aim_radius.setValue(self.settings["aim_radius"])
        self.aim_radius.valueChanged.connect(self.update_settings)
        radius_layout.addWidget(self.aim_radius)
        aimbot_layout.addLayout(radius_layout)

        smooth_layout = QtWidgets.QVBoxLayout()
        smooth_header = QtWidgets.QHBoxLayout()
        smooth_header.addWidget(QtWidgets.QLabel("Smoothing:"))
        self.smooth_label = QtWidgets.QLabel(str(self.settings["aim_smooth"]))
        self.smooth_label.setStyleSheet("color: #fff; font-weight: bold;")
        smooth_header.addWidget(self.smooth_label)
        smooth_header.addStretch()
        smooth_layout.addLayout(smooth_header)

        self.aim_smooth = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.aim_smooth.setRange(1, 100)
        self.aim_smooth.setValue(int(self.settings["aim_smooth"] * 10))
        self.aim_smooth.valueChanged.connect(self.update_settings)
        smooth_layout.addWidget(self.aim_smooth)
        aimbot_layout.addLayout(smooth_layout)


        aimbot_group.setLayout(aimbot_layout)

        content_layout.addWidget(aimbot_group)

        fov_group = QtWidgets.QGroupBox("FOV stuff")
        fov_layout = QtWidgets.QVBoxLayout()
        fov_layout.setSpacing(12)

        self.fov_show = QtWidgets.QCheckBox("Show FOV Circle")
        self.fov_show.setChecked(self.settings["fov_show"])
        self.fov_show.toggled.connect(self.update_settings)
        fov_layout.addWidget(self.fov_show)

        fov_color_layout = QtWidgets.QHBoxLayout()
        fov_color_layout.addWidget(QtWidgets.QLabel("FOV Color:"))
        self.fov_color = ColorPicker(self.settings["fov_color"])
        self.fov_color.colorChanged.connect(self.update_settings)
        fov_color_layout.addWidget(self.fov_color)
        fov_color_layout.addStretch()
        fov_layout.addLayout(fov_color_layout)

        fov_layout.addStretch()
        fov_group.setLayout(fov_layout)
        content_layout.addWidget(fov_group)

        esp_group = QtWidgets.QGroupBox("ESP Shit")
        esp_layout = QtWidgets.QVBoxLayout()
        esp_layout.setSpacing(12)

        self.esp_active = QtWidgets.QCheckBox("Enable ESP")
        self.esp_active.setChecked(self.settings["esp_active"])
        self.esp_active.toggled.connect(self.update_settings)
        esp_layout.addWidget(self.esp_active)

        esp_color_layout = QtWidgets.QHBoxLayout()
        esp_color_layout.addWidget(QtWidgets.QLabel("ESP Color (Bones):"))
        self.esp_color = ColorPicker(self.settings["esp_color"])
        self.esp_color.colorChanged.connect(self.update_settings)
        esp_color_layout.addWidget(self.esp_color)
        esp_color_layout.addStretch()
        esp_layout.addLayout(esp_color_layout)

        self.esp_show_box = QtWidgets.QCheckBox("Show Box ESP")
        self.esp_show_box.setChecked(self.settings.get("esp_show_box", True))
        self.esp_show_box.toggled.connect(self.update_settings)
        esp_layout.addWidget(self.esp_show_box)

        esp_box_color_layout = QtWidgets.QHBoxLayout()
        esp_box_color_layout.addWidget(QtWidgets.QLabel("Box Color:"))
        self.esp_box_color = ColorPicker(self.settings.get("esp_box_color", (0, 255, 0, 255)))
        self.esp_box_color.colorChanged.connect(self.update_settings)
        esp_box_color_layout.addWidget(self.esp_box_color)
        esp_box_color_layout.addStretch()
        esp_layout.addLayout(esp_box_color_layout)

        self.esp_show_health = QtWidgets.QCheckBox("Show Health Bar")
        self.esp_show_health.setChecked(self.settings.get("esp_show_health", True))
        self.esp_show_health.toggled.connect(self.update_settings)
        esp_layout.addWidget(self.esp_show_health)

        esp_health_color_layout = QtWidgets.QHBoxLayout()
        esp_health_color_layout.addWidget(QtWidgets.QLabel("Health Bar Color:"))
        self.esp_health_color = ColorPicker(self.settings.get("esp_health_color", (255, 0, 0, 255)))
        self.esp_health_color.colorChanged.connect(self.update_settings)
        esp_health_color_layout.addWidget(self.esp_health_color)
        esp_health_color_layout.addStretch()
        esp_layout.addLayout(esp_health_color_layout)

        self.esp_show_name = QtWidgets.QCheckBox("Show Player Name")
        self.esp_show_name.setChecked(self.settings.get("esp_show_name", True))
        self.esp_show_name.toggled.connect(self.update_settings)
        esp_layout.addWidget(self.esp_show_name)

        esp_name_color_layout = QtWidgets.QHBoxLayout()
        esp_name_color_layout.addWidget(QtWidgets.QLabel("Name Color:"))
        self.esp_name_color = ColorPicker(self.settings.get("esp_name_color", (255, 255, 255, 255)))
        self.esp_name_color.colorChanged.connect(self.update_settings)
        esp_name_color_layout.addWidget(self.esp_name_color)
        esp_name_color_layout.addStretch()
        esp_layout.addLayout(esp_name_color_layout)

        self.esp_show_weapon = QtWidgets.QCheckBox("Show Weapon Name")
        self.esp_show_weapon.setChecked(self.settings.get("esp_show_weapon", True))
        self.esp_show_weapon.toggled.connect(self.update_settings)
        esp_layout.addWidget(self.esp_show_weapon)

        esp_weapon_color_layout = QtWidgets.QHBoxLayout()
        esp_weapon_color_layout.addWidget(QtWidgets.QLabel("Weapon Color:"))
        self.esp_weapon_color = ColorPicker(self.settings.get("esp_weapon_color", (255, 255, 0, 255)))
        self.esp_weapon_color.colorChanged.connect(self.update_settings)
        esp_weapon_color_layout.addWidget(self.esp_weapon_color)
        esp_weapon_color_layout.addStretch()
        esp_layout.addLayout(esp_weapon_color_layout)

        esp_layout.addStretch()
        esp_group.setLayout(esp_layout)
        content_layout.addWidget(esp_group)

        info_group = QtWidgets.QGroupBox("INFO")
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(8)

        info_text = QtWidgets.QLabel("Controls:\n\u2022 insert too toggle the menu\n\u2022 Developed by syfer-eng\n\u2022 selected key for the aimbot\n\nStatus: Active")
        info_text.setStyleSheet("""
            QLabel {
                color: #ccc;
                font-size: 11px;
                padding: 5px;
                background: rgba(40,40,40,100);
                border-radius: 5px;
            }
        """)
        info_layout.addWidget(info_text)

        info_layout.addStretch()
        info_group.setLayout(info_layout)
        content_layout.addWidget(info_group)

        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)

        self.old_pos = self.pos()

    def setup_animations(self):
        self.fade_effect = QtWidgets.QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.fade_effect)

        self.fade_animation = QtCore.QPropertyAnimation(self.fade_effect, b"opacity")
        self.fade_animation.setDuration(300)

    def showEvent(self, event):
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        super().showEvent(event)

    def mousePressEvent(self, event):
        self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos'):
            delta = QtCore.QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def update_settings(self):
        self.settings["aim_active"] = self.aim_active.isChecked()
        self.settings["aim_key"] = self.aim_key.current_key
        self.settings["aim_radius"] = self.aim_radius.value()
        self.settings["aim_smooth"] = self.aim_smooth.value() / 10.0
        self.settings["fov_show"] = self.fov_show.isChecked()
        self.settings["fov_color"] = self.fov_color.color
        self.settings["esp_active"] = self.esp_active.isChecked()
        self.settings["esp_color"] = self.esp_color.color
        self.settings["esp_show_box"] = self.esp_show_box.isChecked()
        self.settings["esp_box_color"] = self.esp_box_color.color
        self.settings["esp_show_health"] = self.esp_show_health.isChecked()
        self.settings["esp_health_color"] = self.esp_health_color.color
        self.settings["esp_show_name"] = self.esp_show_name.isChecked()
        self.settings["esp_name_color"] = self.esp_name_color.color
        self.settings["esp_show_weapon"] = self.esp_show_weapon.isChecked()
        self.settings["esp_weapon_color"] = self.esp_weapon_color.color

        self.radius_label.setText(str(self.aim_radius.value()))
        self.smooth_label.setText(str(self.aim_smooth.value() / 10.0))

        save_settings(self.settings)


def aimbot_thread(pm, client, offsets, client_dll):
    key_map = {
        "CTRL": win32con.VK_CONTROL,
        "SHIFT": win32con.VK_SHIFT,
        "ALT": win32con.VK_MENU,
        "SPACE": win32con.VK_SPACE,
        "X": ord('X'),
        "C": ord('C'),
        "V": ord('V'),
        "F": ord('F'),
        "G": ord('G'),
        "H": ord('H')
    }

    dwEntityList = offsets['client.dll']['dwEntityList']
    dwLocalPlayerPawn = offsets['client.dll']['dwLocalPlayerPawn']
    dwViewMatrix = offsets['client.dll']['dwViewMatrix']
    m_iTeamNum = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_iTeamNum']
    m_lifeState = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_lifeState']
    m_pGameSceneNode = client_dll['client.dll']['classes']['C_BaseEntity']['fields']['m_pGameSceneNode']
    m_modelState = client_dll['client.dll']['classes']['CSkeletonInstance']['fields']['m_modelState']
    m_hPlayerPawn = client_dll['client.dll']['classes']['CCSPlayerController']['fields']['m_hPlayerPawn']

    ccs_player_class = client_dll['client.dll']['classes'].get('CCSPlayer', None)
    if ccs_player_class is not None:
        fields = ccs_player_class.get('fields', {})
        m_iShotsFired = fields.get('m_iShotsFired', 0xA2C)
        m_aimPunchAngle = fields.get('m_aimPunchAngle', 0x300)
    else:
        m_iShotsFired = 0xA2C
        m_aimPunchAngle = 0x300

    dwClientState = offsets.get('engine.dll', {}).get('dwClientState', 0)
    dwClientState_ViewAngles = offsets.get('engine.dll', {}).get('dwClientState_ViewAngles', 0)

    while True:
        settings = get_current_settings()

        if not settings["aim_active"]:
            time.sleep(0.1)
            continue

        aim_key = key_map.get(settings["aim_key"], win32con.VK_CONTROL)

        if not win32api.GetAsyncKeyState(aim_key):
            time.sleep(0.005)
            continue

        try:
            view_matrix = [pm.read_float(client + dwViewMatrix + i * 4) for i in range(16)]
            local = pm.read_longlong(client + dwLocalPlayerPawn)
            local_team = pm.read_int(local + m_iTeamNum)
            entity_list = pm.read_longlong(client + dwEntityList)
            base = pm.read_longlong(entity_list + 0x10)

            width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

            crosshair_x, crosshair_y = width // 2, height // 2

            if dwClientState != 0 and dwClientState_ViewAngles != 0:
                client_state = pm.read_int(dwClientState)
                if client_state:
                    pitch = pm.read_float(client_state + dwClientState_ViewAngles)
                    yaw = pm.read_float(client_state + dwClientState_ViewAngles + 0x4)

                    pitch_rad = math.radians(pitch)
                    yaw_rad = math.radians(yaw)

                    forward_x = math.cos(pitch_rad) * math.cos(yaw_rad)
                    forward_y = math.cos(pitch_rad) * math.sin(yaw_rad)
                    forward_z = math.sin(pitch_rad)

                    camera_pos = (0, 0, 0)

                    world_pos = (
                        camera_pos[0] + forward_x * 1000,
                        camera_pos[1] + forward_y * 1000,
                        camera_pos[2] + forward_z * 1000,
                    )

                    proj_x, proj_y = w2s_batch(view_matrix, [world_pos], width, height)[0]
                    if 0 <= proj_x <= width and 0 <= proj_y <= height:
                        crosshair_x, crosshair_y = proj_x, proj_y

            fov_center_x = crosshair_x
            fov_center_y = crosshair_y

            fov_radius = settings["aim_radius"] / 100 * min(width, height) / 2

            closest_dist = float('inf')
            best_target = None

            for i in range(1, 64):
                try:
                    ctrl = pm.read_longlong(base + 0x78 * (i & 0x1FF))
                    if not ctrl:
                        continue
                    pawn = pm.read_longlong(ctrl + m_hPlayerPawn)
                    if not pawn:
                        continue
                    entry = pm.read_longlong(entity_list + 0x8 * ((pawn & 0x7FFF) >> 9) + 0x10)
                    if not entry:
                        continue
                    ent = pm.read_longlong(entry + 0x78 * (pawn & 0x1FF))
                    if not ent or ent == local:
                        continue

                    if pm.read_int(ent + m_iTeamNum) == local_team:
                        continue
                    if pm.read_int(ent + m_lifeState) != 256:
                        continue

                    scene = pm.read_longlong(ent + m_pGameSceneNode)
                    if not scene:
                        continue
                    bone_matrix = pm.read_longlong(scene + m_modelState + 0x80)
                    if not bone_matrix:
                        continue

                    x = pm.read_float(bone_matrix + 6 * 0x20)
                    y = pm.read_float(bone_matrix + 6 * 0x20 + 4)
                    z = pm.read_float(bone_matrix + 6 * 0x20 + 8)

                    sx, sy = w2s_batch(view_matrix, [(x, y, z)], width, height)[0]
                    if sx <= 0 or sy <= 0:
                        continue

                    dist = math.sqrt((sx - fov_center_x) ** 2 + (sy - fov_center_y) ** 2)

                    if dist < closest_dist and dist < fov_radius:
                        closest_dist = dist
                        best_target = (sx, sy)
                except:
                    continue

            if best_target is not None:
                dx = best_target[0] - fov_center_x
                dy = best_target[1] - fov_center_y

                smoothing_factor = 1 / settings["aim_smooth"]
                move_x = int(dx * smoothing_factor)
                move_y = int(dy * smoothing_factor)

                if abs(move_x) < 1 and dx != 0:
                    move_x = 1 if dx > 0 else -1
                if abs(move_y) < 1 and dy != 0:
                    move_y = 1 if dy > 0 else -1

                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)


        except:
            pass

        time.sleep(0.001)


class FastBoneESPWindow(QtWidgets.QWidget):
    def __init__(self, pm, offsets, client_dll):
        super().__init__()
        self.pm = pm
        self.offsets = offsets
        self.client_dll = client_dll
        self.client = pymem.process.module_from_name(self.pm.process_handle, "client.dll").lpBaseOfDll
        self.window_width, self.window_height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        self.setGeometry(0, 0, self.window_width, self.window_height)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.Tool)

        hwnd = self.winId()
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW)

        self.cache_offsets()

        self.bone_path = QtGui.QPainterPath()

        self.esp_pen = None
        self.box_pen = None

        self.font = QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold)
        self.small_font = QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Bold)

        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.esp_fps = 0
        self.game_fps = 0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_esp)
        self.timer.start(0)

    def cache_offsets(self):
        o = self.offsets['client.dll']
        c = self.client_dll['client.dll']['classes']

        self.dwEntityList = o['dwEntityList']
        self.dwLocalPlayerPawn = o['dwLocalPlayerPawn']
        self.dwViewMatrix = o['dwViewMatrix']

        self.m_iTeamNum = c['C_BaseEntity']['fields']['m_iTeamNum']
        self.m_lifeState = c['C_BaseEntity']['fields']['m_lifeState']
        self.m_pGameSceneNode = c['C_BaseEntity']['fields']['m_pGameSceneNode']
        self.m_modelState = c['CSkeletonInstance']['fields']['m_modelState']
        self.m_hPlayerPawn = c['CCSPlayerController']['fields']['m_hPlayerPawn']

        self.m_iHealth = c['C_BaseEntity']['fields'].get('m_iHealth', 0x100)
        self.m_szPlayerName = c['C_BaseEntity']['fields'].get('m_szPlayerName', 0x600)
        self.m_currentWeapon = c['C_BaseEntity']['fields'].get('m_currentWeapon', 0x700)

        self.bone_connections = [
            (6, 5), (5, 4), (4, 2), (2, 0),
            (4, 8), (8, 9), (9, 10),
            (4, 13), (13, 14), (14, 15),
            (0, 22), (22, 23), (23, 24),
            (0, 25), (25, 26), (26, 27),
        ]

        self.dwGameFPS = o.get('dwGameFPS', None)
        self.dwClientState = self.offsets.get('engine.dll', {}).get('dwClientState', 0)
        self.dwClientState_ViewAngles = self.offsets.get('engine.dll', {}).get('dwClientState_ViewAngles', 0)

    def read_string(self, address, max_length=32):
        try:
            data = self.pm.read_bytes(address, max_length)
            s = data.split(b'\x00', 1)[0]
            return s.decode(errors='ignore')
        except:
            return ""

    def update_esp(self):
        settings = get_current_settings()
        self.bone_path = QtGui.QPainterPath()

        self.fps_counter += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.esp_fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_time = current_time

        if self.dwGameFPS:
            try:
                fps_bytes = self.pm.read_bytes(self.client + self.dwGameFPS, 4)
                self.game_fps = struct.unpack('f', fps_bytes)[0]
                self.game_fps = max(0, min(self.game_fps, 1000))
            except:
                self.game_fps = 0
        else:
            self.game_fps = 0

        if not settings["esp_active"]:
            self.update()
            return

        players_to_draw = []

        try:
            view_matrix_bytes = self.pm.read_bytes(self.client + self.dwViewMatrix, 64)
            view_matrix = list(struct.unpack('16f', view_matrix_bytes))

            local = self.pm.read_longlong(self.client + self.dwLocalPlayerPawn)
            if not local:
                self.update()
                return

            local_team = self.pm.read_int(local + self.m_iTeamNum)
            entity_list = self.pm.read_longlong(self.client + self.dwEntityList)
            base = self.pm.read_longlong(entity_list + 0x10)

            for i in range(1, 64):
                try:
                    ctrl = self.pm.read_longlong(base + 0x78 * (i & 0x1FF))
                    if not ctrl:
                        continue

                    pawn = self.pm.read_longlong(ctrl + self.m_hPlayerPawn)
                    if not pawn:
                        continue

                    entry = self.pm.read_longlong(entity_list + 0x8 * ((pawn & 0x7FFF) >> 9) + 0x10)
                    if not entry:
                        continue

                    ent = self.pm.read_longlong(entry + 0x78 * (pawn & 0x1FF))
                    if not ent or ent == local:
                        continue

                    team_num = self.pm.read_int(ent + self.m_iTeamNum)
                    life_state = self.pm.read_int(ent + self.m_lifeState)

                    if team_num == local_team or life_state != 256:
                        continue

                    scene = self.pm.read_longlong(ent + self.m_pGameSceneNode)
                    if not scene:
                        continue

                    bone_matrix = self.pm.read_longlong(scene + self.m_modelState + 0x80)
                    if not bone_matrix:
                        continue

                    health = 0
                    if self.m_iHealth != 0:
                        try:
                            health = self.pm.read_int(ent + self.m_iHealth)
                            if health < 0:
                                health = 0
                            elif health > 100:
                                health = 100
                        except:
                            health = 0

                    player_name = ""
                    if self.m_szPlayerName != 0:
                        try:
                            player_name = self.read_string(ent + self.m_szPlayerName, 32)
                        except:
                            player_name = ""

                    weapon_name = ""
                    if self.m_currentWeapon != 0:
                        try:
                            weapon_ptr = self.pm.read_longlong(ent + self.m_currentWeapon)
                            if weapon_ptr:
                                weapon_name = self.read_string(weapon_ptr + 0x30, 32)
                        except:
                            weapon_name = ""

                    bone_positions = []
                    read_bytes = self.pm.read_bytes(bone_matrix, 28 * 0x20)
                    for bone_id in range(28):
                        offset = bone_id * 0x20
                        try:
                            x = struct.unpack_from('f', read_bytes, offset)[0]
                            y = struct.unpack_from('f', read_bytes, offset + 4)[0]
                            z = struct.unpack_from('f', read_bytes, offset + 8)[0]
                            bone_positions.append((x, y, z))
                        except:
                            bone_positions.append((0.0, 0.0, 0.0))

                    screen_positions = w2s_batch(view_matrix, bone_positions, self.window_width, self.window_height)

                    for b1, b2 in self.bone_connections:
                        if (b1 < len(screen_positions) and b2 < len(screen_positions)):
                            x1, y1 = screen_positions[b1]
                            x2, y2 = screen_positions[b2]
                            if (-999 < x1 < self.window_width and -999 < y1 < self.window_height and
                                    -999 < x2 < self.window_width and -999 < y2 < self.window_height and
                                    0 <= x1 <= self.window_width and 0 <= y1 <= self.window_height and
                                    0 <= x2 <= self.window_width and 0 <= y2 <= self.window_height):
                                self.bone_path.moveTo(x1, y1)
                                self.bone_path.lineTo(x2, y2)

                    xs = [p[0] for p in screen_positions if p[0] > 0 and p[1] > 0]
                    ys = [p[1] for p in screen_positions if p[0] > 0 and p[1] > 0]
                    if xs and ys:
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        width = max_x - min_x
                        height = max_y - min_y

                        players_to_draw.append({
                            "bbox": (min_x, min_y, width, height),
                            "health": health,
                            "name": player_name,
                            "weapon": weapon_name,
                            "center_bottom": ((min_x + max_x) / 2, max_y),
                        })

                except:
                    continue

        except:
            players_to_draw = []
            pass

        self.players_to_draw = players_to_draw

        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        settings = get_current_settings()

        fps_to_show = int(self.game_fps) if self.game_fps > 0 else self.esp_fps

        watermark_text = f"FPS: {fps_to_show} | Made by Syfer-eng"

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 1))
        painter.setFont(self.font)
        painter.drawText(15, 25, watermark_text)

        if settings["esp_active"]:
            if not self.bone_path.isEmpty() and settings.get("esp_color"):
                esp_color = QtGui.QColor(*settings["esp_color"])
                if self.esp_pen is None or self.esp_pen.color() != esp_color:
                    self.esp_pen = QtGui.QPen(esp_color, 2)
                painter.setPen(self.esp_pen)
                painter.drawPath(self.bone_path)

            if hasattr(self, "players_to_draw"):
                for player in self.players_to_draw:
                    if settings.get("esp_show_box", True):
                        bx, by, bw, bh = player["bbox"]
                        box_color = QtGui.QColor(*settings.get("esp_box_color", (0, 255, 0, 255)))
                        if self.box_pen is None or self.box_pen.color() != box_color:
                            self.box_pen = QtGui.QPen(box_color, 2)
                        painter.setPen(self.box_pen)
                        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                        painter.drawRect(int(bx), int(by), int(bw), int(bh))

                    if settings.get("esp_show_health", True):
                        health = player["health"]
                        if health > 0:
                            bx, by, bw, bh = player["bbox"]
                            bar_height = int(bh * (health / 100))
                            bar_width = 5
                            bar_x = int(bx) - bar_width - 2
                            bar_y = int(by + bh - bar_height)
                            health_color = QtGui.QColor(*settings.get("esp_health_color", (255, 0, 0, 255)))
                            painter.setPen(QtCore.Qt.PenStyle.NoPen)
                            painter.setBrush(health_color)
                            painter.drawRect(bar_x, bar_y, bar_width, bar_height)
                            painter.setBrush(QtGui.QColor(50, 50, 50, 150))
                            painter.drawRect(bar_x, int(by), bar_width, bh - bar_height)

                    if settings.get("esp_show_name", True) and player.get("name"):
                        name = player["name"]
                        bx, by, bw, bh = player["bbox"]
                        name_color = QtGui.QColor(*settings.get("esp_name_color", (255, 255, 255, 255)))
                        painter.setPen(QtGui.QPen(name_color, 1))
                        painter.setFont(self.small_font)
                        text_rect = painter.boundingRect(0, 0, 150, 20, QtCore.Qt.AlignmentFlag.AlignCenter, name)
                        text_x = int(bx + bw / 2 - text_rect.width() / 2)
                        text_y = int(by) - 20
                        painter.drawText(text_x, text_y + text_rect.height(), name)

                    if settings.get("esp_show_weapon", True) and player.get("weapon"):
                        weapon = player["weapon"]
                        bx, by, bw, bh = player["bbox"]
                        weapon_color = QtGui.QColor(*settings.get("esp_weapon_color", (255, 255, 0, 255)))
                        painter.setPen(QtGui.QPen(weapon_color, 1))
                        painter.setFont(self.small_font)
                        text_rect = painter.boundingRect(0, 0, 150, 20, QtCore.Qt.AlignmentFlag.AlignCenter, weapon)
                        text_x = int(bx + bw / 2 - text_rect.width() / 2)
                        text_y = int(by + bh)
                        painter.drawText(text_x, text_y + text_rect.height(), weapon)

        if settings["fov_show"] and settings["aim_active"]:
            width, height = self.window_width, self.window_height
            crosshair_x, crosshair_y = width // 2, height // 2

            if self.dwClientState != 0 and self.dwClientState_ViewAngles != 0:
                try:
                    client_state = self.pm.read_int(self.dwClientState)
                    if client_state:
                        pitch = self.pm.read_float(client_state + self.dwClientState_ViewAngles)
                        yaw = self.pm.read_float(client_state + self.dwClientState_ViewAngles + 0x4)

                        pitch_rad = math.radians(pitch)
                        yaw_rad = math.radians(yaw)

                        forward_x = math.cos(pitch_rad) * math.cos(yaw_rad)
                        forward_y = math.cos(pitch_rad) * math.sin(yaw_rad)
                        forward_z = math.sin(pitch_rad)

                        camera_pos = (0, 0, 0)
                        world_pos = (camera_pos[0] + forward_x * 1000,
                                     camera_pos[1] + forward_y * 1000,
                                     camera_pos[2] + forward_z * 1000)

                        view_matrix = [self.pm.read_float(self.client + self.dwViewMatrix + i * 4) for i in range(16)]
                        proj_x, proj_y = w2s_batch(view_matrix, [world_pos], width, height)[0]

                        if 0 <= proj_x <= width and 0 <= proj_y <= height:
                            crosshair_x, crosshair_y = proj_x, proj_y
                except:
                    pass

            radius = settings["aim_radius"] / 100 * min(width, height) / 2

            for i in range(3):
                alpha = 30 - (i * 10)
                glow_color = QtGui.QColor(*settings["fov_color"][:3], alpha)
                glow_pen = QtGui.QPen(glow_color, 3 - i)
                painter.setPen(glow_pen)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawEllipse(
                    int(crosshair_x - radius - i),
                    int(crosshair_y - radius - i),
                    int((radius + i) * 2),
                    int((radius + i) * 2),
                )

            fov_color = QtGui.QColor(*settings["fov_color"])
            fov_pen = QtGui.QPen(fov_color, 1)
            painter.setPen(fov_pen)
            painter.drawEllipse(
                int(crosshair_x - radius),
                int(crosshair_y - radius),
                int(radius * 2),
                int(radius * 2),
            )

        painter.end()


class MenuToggleHandler:
    def __init__(self, settings_menu):
        self.settings_menu = settings_menu
        self.insert_pressed = False
        self.last_insert_time = 0

    def check_toggle(self):
        current_time = time.time()
        insert_state = win32api.GetAsyncKeyState(win32con.VK_INSERT) & 0x8000

        if insert_state and not self.insert_pressed:
            if current_time - self.last_insert_time > 0.3:
                self.toggle_menu()
                self.last_insert_time = current_time
            self.insert_pressed = True
        elif not insert_state:
            self.insert_pressed = False

    def toggle_menu(self):
        if self.settings_menu.isVisible():
            self.settings_menu.hide()
        else:
            self.settings_menu.show()
            self.settings_menu.raise_()
            self.settings_menu.activateWindow()

CURRENT_VERSION = "1.0.1"

def check_for_update_decision():
    try:
        url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/Versions.json"
        response = requests.get(url, timeout=5)
        data = response.json()

        latest = data.get("latest_version", CURRENT_VERSION)
        links = data.get("download_links", {})
        download_url = links.get(latest)

        if latest != CURRENT_VERSION and download_url:
            box = QMessageBox()
            box.setWindowTitle("Update Available")
            box.setText(f"A new version ({latest}) is available.\nDo you want to update?")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.Yes)
            result = box.exec()

            if result == QMessageBox.StandardButton.Yes:
                webbrowser.open(download_url)
                sys.exit(0)
    except Exception as e:
        print(f"[Update Check] Error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    check_for_update_decision()

    print("Waiting for cs2.exe...")
    while True:
        try:
            pm = pymem.Pymem("cs2.exe")
            client = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
            break
        except:
            time.sleep(1)

    print("Downloading offsets...")
    offsets, client_dll = get_offsets_and_client_dll()

    if not offsets or not client_dll:
        print("Failed to download offsets.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("Syfer-eng")

    def monitor_process():
        while True:
            if not any(p.name().lower() == "cs2.exe" for p in psutil.process_iter(['name'])):
                print("cs2 not running. Exiting.")
                os._exit(0)
            time.sleep(2)

    threading.Thread(target=monitor_process, daemon=True).start()
    threading.Thread(target=aimbot_thread, args=(pm, client, offsets, client_dll), daemon=True).start()

    try:
        settings_menu = SettingsMenu()
        esp_window = FastBoneESPWindow(pm, offsets, client_dll)
        esp_window.show()
        settings_menu.show()

        menu_handler = MenuToggleHandler(settings_menu)
        menu_timer = QtCore.QTimer()
        menu_timer.timeout.connect(menu_handler.check_toggle)
        menu_timer.start(50)

        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting: {e}")
        input("Press Enter to exit...")
        sys.exit(1)