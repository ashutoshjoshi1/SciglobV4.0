import serial, cv2
import numpy as np
from serial.tools import list_ports
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QGraphicsRectItem
from PyQt5.QtGui import QImage, QPixmap
import pyqtgraph as pg

from drivers.imu import start_imu_read_thread

class IMUController(QObject):
    status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groupbox = QGroupBox("IMU")
        self.groupbox.setObjectName("imuGroup")
        v = QVBoxLayout()

        self.data_label = QLabel("Not connected")
        v.addWidget(self.data_label)

        # Motion view: rectangle that rotates/tilts with IMU
        self.motion_view = pg.GraphicsLayoutWidget()
        self.plot_item = self.motion_view.addPlot()
        self.plot_item.setAspectLocked(True)
        self.plot_item.setRange(xRange=[-2, 2], yRange=[-2, 2])
        self.rect_item = QGraphicsRectItem(-0.5, -0.5, 1, 1)
        self.rect_item.setPen(pg.mkPen('b', width=2))
        self.plot_item.addItem(self.rect_item)
        v.addWidget(self.motion_view)

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

        # Auto-connect from config
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

        # Apply roll (x-rotation) and pitch (y-tilt) to rectangle
        roll = np.deg2rad(r)
        pitch = np.deg2rad(p)
        cos_r, sin_r = np.cos(roll), np.sin(roll)

        # You can also include pitch as a scaling or y-offset for realism
        transform = QtGui.QTransform(
            cos_r, -sin_r,
            sin_r, cos_r,
            0, -pitch  # vertical shift simulating tilt
        )
        self.rect_item.setTransform(transform)

    def is_connected(self):
        return self._connected
