import serial, cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PyQt5.QtGui import QImage, QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from drivers.imu import start_imu_read_thread
import utils

class IMUController(QObject):
    status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groupbox = QGroupBox("IMU")
        self.groupbox.setObjectName("imuGroup")
        v = QVBoxLayout()

        self.data_label = QLabel("Not connected")
        v.addWidget(self.data_label)

        # 3D orientation plot
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection='3d')
        utils.draw_device_orientation(self.ax, 0, 0, 0, 0, 0)
        self.canvas = FigureCanvas(self.fig)
        v.addWidget(self.canvas)

        # Camera feed
        self.cam_label = QLabel()
        self.cam_label.setFixedHeight(200)
        self.cam_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.cam_label)
        self.cam = cv2.VideoCapture(0)
        self.cam_timer = QTimer(self)
        self.cam_timer.timeout.connect(self._update_cam)
        self.cam_timer.start(30)

        self.groupbox.setLayout(v)
        self._connected = False
        self.serial = None
        self.latest = {
            'rpy': (0, 0, 0),
            'latitude': 0,
            'longitude': 0,
            'temperature': 0,
            'pressure': 0
        }

        # Auto-connect using config
        if parent is not None and hasattr(parent, 'config'):
            cfg_port = parent.config.get("imu")
            cfg_baud = parent.config.get("imu_baud", 115200)
            if cfg_port:
                self.connect(cfg_port, int(cfg_baud))

    def connect(self, port, baud):
        if self._connected:
            return self.status_signal.emit("IMU already connected.")
        try:
            self.serial = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            return self.status_signal.emit(f"IMU connection failed: {e}")
        self._connected = True
        self.status_signal.emit(f"IMU connected on {port}@{baud}")
        self.stop_evt = start_imu_read_thread(self.serial, self.latest)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh)
        self.update_timer.start(100)

    def _update_cam(self):
        if self.cam.isOpened():
            ret, frame = self.cam.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                img = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
                self.cam_label.setPixmap(QPixmap.fromImage(img))

    def _refresh(self):
        r, p, y = self.latest['rpy']
        lat, lon = self.latest['latitude'], self.latest['longitude']
        t, pres = self.latest['temperature'], self.latest['pressure']
        self.data_label.setText(
            f"R={r:.1f}°, P={p:.1f}°, Y={y:.1f}°\n"
            f"T={t:.1f}°C, P={pres:.1f}hPa\n"
            f"Lat={lat:.5f}, Lon={lon:.5f}"
        )

        self.ax.cla()
        utils.draw_device_orientation(self.ax, r, p, y, lat, lon)
        self.canvas.draw()

    def is_connected(self):
        return self._connected
