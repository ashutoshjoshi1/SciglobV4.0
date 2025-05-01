import sys
import os
import json
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QGridLayout, QSplitter,
    QLabel, QPushButton, QStatusBar
)
from PyQt5.QtCore import QTimer, Qt, QDateTime

from controllers.motor_controller import MotorController
from controllers.filterwheel_controller import FilterWheelController
from controllers.imu_controller import IMUController
from controllers.spectrometer_controller import SpectrometerController
from controllers.temp_controller import TempController
from controllers.thp_controller import THPController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spectrometer, Motor, IMU & Temperature Control")
        self.setMinimumSize(1920, 1000)

        # Load hardware configuration
        self.config = {}
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "hardware_config.json")
            with open(config_path, 'r') as cfg_file:
                self.config = json.load(cfg_file)
        except Exception as e:
            print(f"Config load error: {e}")

        # in-memory stores
        self.latest_data = {}   # IMU/Temp/GPS raw data dict
        self.wavelengths = []   # Spectrometer wavelengths
        self.intensities = []   # Spectrometer intensities

        # THP sensor
        thp_port = self.config.get("thp_sensor", "COM8")
        self.thp_ctrl = THPController(port=thp_port, parent=self)
        self.thp_ctrl.status_signal.connect(self.statusBar().showMessage)


        # status bar
        # self.statusBar() = QStatusBar()
        self.setStatusBar(QStatusBar())

        # central layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # controllers and their UI widgets
        self.temp_ctrl = TempController(parent=self)
        self.temp_ctrl.status_signal.connect(self.statusBar().showMessage)
        self.temp_ctrl.status_signal.connect(self.handle_status_message)

        self.spec_ctrl = SpectrometerController(parent=self)
        self.spec_ctrl.status_signal.connect(self.statusBar().showMessage)
        self.spec_ctrl.status_signal.connect(self.handle_status_message)

        self.motor_ctrl = MotorController(parent=self)
        self.motor_ctrl.status_signal.connect(self.statusBar().showMessage)
        self.motor_ctrl.status_signal.connect(self.handle_status_message)

        self.filter_ctrl = FilterWheelController(parent=self)
        self.filter_ctrl.status_signal.connect(self.statusBar().showMessage)
        self.filter_ctrl.status_signal.connect(self.handle_status_message)

        self.imu_ctrl = IMUController(parent=self)
        self.imu_ctrl.status_signal.connect(self.statusBar().showMessage)
        self.imu_ctrl.status_signal.connect(self.handle_status_message)

        # add widgets to main layout
        main_layout.addWidget(self.temp_ctrl.widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.spec_ctrl.groupbox)

        right_panel = QWidget()
        grid = QGridLayout(right_panel)
        grid.addWidget(self.thp_ctrl.groupbox, 2, 0, 1, 2)
        grid.addWidget(self.motor_ctrl.groupbox, 0, 0)
        grid.addWidget(self.filter_ctrl.groupbox, 0, 1)
        # Span IMU groupbox across both columns in the second row
        grid.addWidget(self.imu_ctrl.groupbox, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        splitter.addWidget(right_panel)
        # Adjust splitter ratios to expand spectrometer display
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # status indicators update timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_indicators)
        self.status_timer.start(1000)
        self._update_indicators()

        # data directories and file handles
        self.csv_dir = "data"
        self.log_dir = "data"
        os.makedirs(self.csv_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        self.csv_file = None
        self.log_file = None
        self.continuous_saving = False

        # timer for continuous data saving
        self.save_data_timer = QTimer(self)
        self.save_data_timer.timeout.connect(self.save_continuous_data)
        # (Spectrometer measurement is started in SpectrometerController when connected)

    def toggle_data_saving(self):
        if not self.continuous_saving:
            # --- START LOGGING ---
            # Close any existing files
            if self.csv_file:
                self.csv_file.close()
            if self.log_file:
                self.log_file.close()
            ts = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
            self.csv_file_path = os.path.join(self.csv_dir, f"log_{ts}.csv")
            self.log_file_path = os.path.join(self.log_dir, f"log_{ts}.txt")
            try:
                self.csv_file = open(self.csv_file_path, "w", encoding="utf-8", newline="")
                self.log_file = open(self.log_file_path, "w", encoding="utf-8")
            except Exception as e:
                self.statusBar().showMessage(f"Cannot open files: {e}")
                return
            # Write CSV header
            headers = [
                "Timestamp",
                "MotorPos_steps", "MotorSpeed_steps_s", "MotorCurrent_pct",
                "MotorAlarmCode", "MotorTemp_C", "MotorAngle_deg",
                "FilterPos",
                "Roll_deg", "Pitch_deg", "Yaw_deg",
                "AccelX_g", "AccelY_g", "AccelZ_g",
                "GyroX_dps", "GyroY_dps", "GyroZ_dps",
                "MagX_uT", "MagY_uT", "MagZ_uT",
                "Pressure_hPa", "Temperature_C",  # Environmental pressure & temperature
                "TempCtrl_curr", "TempCtrl_set",  # Temperature controller current & setpoint
                "Latitude_deg", "Longitude_deg",
                "IntegrationTime_us"
            ]
            headers.extend(["THP_Temp_C", "THP_Humidity_pct", "THP_Pressure_hPa"])

            # If wavelengths are known (spectrometer connected), add intensity columns for each wavelength
            for wl in self.wavelengths:
                headers.append(f"I_{wl:.1f}nm")
            self.csv_file.write(",".join(headers) + "\n")
            self.csv_file.flush()
            os.fsync(self.csv_file.fileno())

            # Start continuous saving
            self.save_data_timer.start(1000)
            self.continuous_saving = True
            # Update UI button text
            self.spec_ctrl.toggle_btn.setText("Pause Saving")
            self.statusBar().showMessage("Saving started…")
            # Log this event
            self.handle_status_message("Saving started")
        else:
            # --- STOP LOGGING ---
            self.continuous_saving = False
            self.save_data_timer.stop()
            if self.csv_file:
                self.csv_file.close()
            if self.log_file:
                self.log_file.close()
            # Reset UI button text
            self.spec_ctrl.toggle_btn.setText("Start Saving")
            self.statusBar().showMessage("Saving stopped.")
            # Log this event
            self.handle_status_message("Saving stopped")

    def save_continuous_data(self):
        """Poll every controller for its current data, then write a CSV row."""
        if not (self.csv_file and self.log_file):
            return
        try:
            now = QDateTime.currentDateTime()
            ts_csv = now.toString("yyyy-MM-dd hh:mm:ss.zzz")
            ts_txt = now.toString("yyyy-MM-dd hh:mm:ss")

            # 1) Motor data
            motor_pos = getattr(self.motor_ctrl, "current_angle", 0)  # steps or angle
            motor_speed = getattr(self.motor_ctrl, "current_speed", 0)
            motor_current_pct = getattr(self.motor_ctrl, "current_percent", 0)
            motor_alarm = getattr(self.motor_ctrl, "alarm_code", 0)
            motor_temp = getattr(self.motor_ctrl, "temperature", 0)
            motor_angle = getattr(self.motor_ctrl, "current_angle_deg", 0)

            # 2) Filter wheel position
            filter_pos = self.filter_ctrl.get_position()
            if filter_pos is None:
                filter_pos = getattr(self.filter_ctrl, "current_position", 0)

            # 3) IMU / GPS / pressure (environmental)
            imu = getattr(self.imu_ctrl, "latest", {})
            r, p, y = imu.get("rpy", (0, 0, 0))
            ax, ay, az = imu.get("accel", (0, 0, 0))
            gx, gy, gz = imu.get("gyro", (0, 0, 0))
            mx, my, mz = imu.get("mag", (0, 0, 0))
            pres = imu.get("pressure", 0)
            temp_env = imu.get("temperature", 0)
            lat = imu.get("latitude", 0)
            lon = imu.get("longitude", 0)

            # 4) Temperature controller
            tc_curr = getattr(self.temp_ctrl, "current_temp", 0)    # current temperature (°C)
            tc_set = getattr(self.temp_ctrl, "setpoint", 0)         # setpoint temperature (°C)

            # 5) Spectrometer data (latest intensities and integration time)
            wavelengths = self.wavelengths
            intensities = self.intensities
            integ_us = getattr(self, "current_integration_time_us", 0)

            # 6) THP Sensor data
            thp = self.thp_ctrl.get_latest()
            thp_temp = thp.get("temperature", 0)
            thp_hum = thp.get("humidity", 0)
            thp_pres = thp.get("pressure", 0)


            # Build CSV row
            row = [
                ts_csv,
                str(motor_pos), str(motor_speed), f"{motor_current_pct:.1f}",
                str(motor_alarm), str(motor_temp), str(motor_angle),
                str(filter_pos),
                f"{r:.2f}", f"{p:.2f}", f"{y:.2f}",
                f"{ax:.2f}", f"{ay:.2f}", f"{az:.2f}",
                f"{gx:.2f}", f"{gy:.2f}", f"{gz:.2f}",
                f"{mx:.2f}", f"{my:.2f}", f"{mz:.2f}",
                f"{pres:.2f}", f"{temp_env:.2f}",
                f"{tc_curr:.2f}", f"{tc_set:.2f}",
                f"{lat:.6f}", f"{lon:.6f}",
                str(integ_us),
                f"{thp_temp:.2f}", f"{thp_hum:.2f}", f"{thp_pres:.2f}"
            ]
            # Append intensity values (only non-zero intensities to save space, if desired)
            for inten in intensities:
                # If recording only non-zero intensities, uncomment next line:
                # if inten == 0: continue
                row.append(f"{inten:.4f}")
            line = ",".join(row) + "\n"
            self.csv_file.write(line)
            self.csv_file.flush()
            os.fsync(self.csv_file.fileno())

            # For log file, log peak intensity value for reference (could be considered an event)
            if intensities:
                peak = max(intensities)
            else:
                peak = 0
            txt_line = f"{ts_txt} | Peak {peak:.1f}\n"
            # We will treat this as informational data rather than a hardware event
            self.log_file.write(txt_line)
            self.log_file.flush()
            os.fsync(self.log_file.fileno())
        except Exception as e:
            print("save_continuous_data error:", e)
            self.statusBar().showMessage(f"Save error: {e}")

    def _update_indicators(self):
        # Update groupbox titles with connection status (green if connected, red if not)
        for ctrl, title, ok_fn in [
            (self.motor_ctrl, "Motor", self.motor_ctrl.is_connected),
            (self.filter_ctrl, "Filter Wheel", self.filter_ctrl.is_connected),
            (self.imu_ctrl, "IMU", self.imu_ctrl.is_connected),
            (self.spec_ctrl, "Spectrometer", self.spec_ctrl.is_ready)
        ]:
            col = "green" if ok_fn() else "red"
            gb = ctrl.groupbox
            gb.setTitle(f"● {title}")
            gb.setStyleSheet(f"QGroupBox#{gb.objectName()}::title {{ color: {col}; }}")

    def handle_status_message(self, message: str):
        """Log hardware state changes with level tags."""
        if not self.log_file:
            return
        msg_lower = message.lower()
        # Determine severity level
        if ("fail" in msg_lower or "error" in msg_lower or "no response" in msg_lower or "cannot" in msg_lower):
            level = "ERROR"
        elif ("no ack" in msg_lower or "invalid" in msg_lower or "not connected" in msg_lower or "not ready" in msg_lower):
            level = "WARNING"
        else:
            level = "INFO"
        ts = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        log_line = f"{ts} [{level}] {message}\n"
        try:
            self.log_file.write(log_line)
            self.log_file.flush()
            os.fsync(self.log_file.fileno())
        except Exception as e:
            print(f"Log write error: {e}")
