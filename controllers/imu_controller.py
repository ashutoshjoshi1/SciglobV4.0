import serial, cv2
from serial.tools import list_ports
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt5.QtGui import QImage, QPixmap

from drivers.imu import start_imu_read_thread
import utils

class IMUController(QObject):
    status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groupbox = QGroupBox("IMU")
        self.groupbox.setObjectName("imuGroup")
        v = QVBoxLayout()
        h = QHBoxLayout()
        h.addWidget(QLabel("COM:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        ports = [p.device for p in list_ports.comports()]
        self.port_combo.addItems(ports or [f"COM{i}" for i in range(1, 10)])
        h.addWidget(self.port_combo)
        h.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "57600", "115200"])
        h.addWidget(self.baud_combo)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect)
        h.addWidget(self.connect_btn)
        v.addLayout(h)
        self.data_label = QLabel("Not connected")
        v.addWidget(self.data_label)

        # 3D orientation plot (disabled per requirements)
        # self.fig = plt.figure(); self.ax = self.fig.add_subplot(111, projection='3d')
        # utils.draw_device_orientation(self.ax, 0, 0, 0, 0, 0)
        # v.addWidget(FigureCanvas(self.fig))

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
        self.latest = {'rpy': (0, 0, 0), 'latitude': 0, 'longitude': 0, 'temperature': 0, 'pressure': 0}

        # Auto-connect if configured
        if parent is not None and hasattr(parent, 'config'):
            cfg_port = parent.config.get("imu")
            cfg_baud = parent.config.get("imu_baud")
            if cfg_port:
                self.port_combo.setCurrentText(cfg_port)
            if cfg_baud:
                self.baud_combo.setCurrentText(str(cfg_baud))
            if cfg_port:
                self.connect()

    def connect(self):
        if self._connected:
            return self.status_signal.emit("Already connected")
        port = self.port_combo.currentText().strip()
        baud = int(self.baud_combo.currentText())
        try:
            self.serial = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            return self.status_signal.emit(f"Fail: {e}")
        self._connected = True
        self.status_signal.emit(f"IMU on {port}@{baud}")
        # Start background IMU read thread
        self.stop_evt = start_imu_read_thread(self.serial, self.latest)
        # Start timer to refresh displayed values
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
        self.data_label.setText(f"R={r:.1f}°, P={p:.1f}°, Y={y:.1f}°\n"
                                 f"T={t:.1f}°C, P={pres:.1f}hPa\n"
                                 f"Lat={lat:.5f}, Lon={lon:.5f}")

    def is_connected(self):
        return self._connected
