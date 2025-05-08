SciglobV4.0 Code Updates
Motor Reset and Angle Logging
On startup, send the motor-reset command and initialize an internal angle variable (e.g. self.current_motor_angle = 0). For example, in the main initialization code:
python
Copy
Edit
# In main application initialization (e.g. __init__)
self.current_motor_angle = 0
# Send reset-to-zero command to the motor controller
self.motor_controller.reset_to_zero()    # or use the appropriate command/method from the motor driver
# Optionally update a GUI display for the angle
self.angleLabel.setText(f"Angle: {self.current_motor_angle}°")
Then, wherever the motor is moved, update self.current_motor_angle immediately. For example:
python
Copy
Edit
def rotate_motor(self, new_angle):
    # Existing code that sends the rotation command...
    self.motor_controller.move_to_angle(new_angle)
    # Update internal angle tracking
    self.current_motor_angle = new_angle  
    # (Re)display or log the updated angle
    self.angleLabel.setText(f"Angle: {self.current_motor_angle}°")
Finally, ensure that whenever data is logged to CSV, the current angle is included. For instance, using Python’s csv.writer:
python
Copy
Edit
# When writing a data row, include MotorAngle_deg
timestamp = datetime.now().isoformat()
self.data_writer.writerow([timestamp, self.current_motor_angle, ...other fields...])
This uses Python’s standard CSV writer, which produces delimited rows in the output file
docs.python.org
. After startup reset and after every movement, the MotorAngle_deg field in the CSV will accurately reflect self.current_motor_angle.
Dynamic Integration Time for Spectroscope
In the spectrometer acquisition loop, evaluate the peak intensity and set the integration time accordingly. For example:
python
Copy
Edit
# In the loop or callback that reads spectra
spectrum = self.spectrometer.read_spectrum()
peak_intensity = max(spectrum)

# Adjust integration time based on peak intensity thresholds
if peak_intensity > 800:
    itime_ms = 50
elif peak_intensity > 300:
    itime_ms = 400
else:
    itime_ms = 4000

# Apply the new integration time to the spectrometer
self.spectrometer.set_integration_time(itime_ms)  

# Also adjust the data-acquisition timer if needed
self.acquisition_timer.setInterval(itime_ms)
This logic ensures the spectrometer’s integration time changes dynamically (shorter for bright peaks, longer for dim signals). The set_integration_time() call must use the spectrometer driver’s API (for example, SeaBreeze’s set_integration_time_micros()
python-seabreeze.readthedocs.io
, converting ms to μs if required). The acquisition timer interval is also updated so that data is read only after each exposure completes.
Filter Wheel Logging
In the command-processing section for filter-wheel commands, update and log the wheel position. For example, if commands like "F1*" arrive:
python
Copy
Edit
def process_filter_command(self, cmd):
    if cmd.startswith("F1"):
        if cmd == "F1r":
            self.filter_wheel_position = 1
        else:
            # Extract numeric position from command, e.g. "F15" -> 5
            pos = int(cmd[2:])
            self.filter_wheel_position = pos
        # Log or display the updated filter wheel position
        self.log_file.write(f"Filter wheel set to position {self.filter_wheel_position}\n")
        # Optionally update GUI
        self.filterLabel.setText(f"Filter Position: {self.filter_wheel_position}")
For the reset command F1r, we explicitly set the position to 1. Each time a valid "F1*" command is received, we overwrite self.filter_wheel_position and append a line to the log file. This ensures the plain-text log always shows the current filter position.
GUI Improvements
Square Camera Display: Ensure the camera widget maintains a 1:1 aspect ratio. For example, if the camera feed is shown in a QLabel named self.cameraLabel, set fixed dimensions and enable scaled contents:
python
Copy
Edit
# In the GUI layout setup:
size = 400  # set desired pixel size
self.cameraLabel.setFixedSize(size, size)
self.cameraLabel.setScaledContents(True)
This makes the label square (equal width and height) and scales the video image to fit without altering the captured resolution.
Add Static Logo: Insert a QLabel at the top of the GUI and load the SciGlob logo. For example:
python
Copy
Edit
from PyQt5.QtGui import QPixmap

# In the GUI initialization (before adding other widgets):
logo_label = QtWidgets.QLabel(self)
logo_pixmap = QPixmap("assets/image/sciglob.png")
logo_label.setPixmap(logo_pixmap)
logo_label.setAlignment(QtCore.Qt.AlignCenter)
# Optionally, enable scaledContents if you want it to stretch to the layout
logo_label.setScaledContents(True)
# Add it to the top of the main layout
self.mainLayout.addWidget(logo_label, alignment=QtCore.Qt.AlignTop)
This uses a QLabel with setPixmap() to display the image
pythonguis.com
. The logo appears statically above the other controls.
THP Sensor Integration
Add a new tab (or tabs) for real-time Temperature, Humidity, and Pressure plots, and set up logging:
Create THP Plots: Use three plotting widgets (e.g. Matplotlib or PyQtGraph canvases) in the GUI. Place them in a new tab (or three tabs) similar to existing charts. In code, you might have something like:
python
Copy
Edit
# Example using a QTabWidget named self.chartsTabWidget
thpTab = QtWidgets.QWidget()
thpLayout = QtWidgets.QVBoxLayout(thpTab)

self.tempPlot = MatplotlibCanvas(title="Temperature (°C)")
self.humPlot = MatplotlibCanvas(title="Humidity (%)")
self.pressurePlot = MatplotlibCanvas(title="Pressure (hPa)")

thpLayout.addWidget(self.tempPlot)
thpLayout.addWidget(self.humPlot)
thpLayout.addWidget(self.pressurePlot)

self.chartsTabWidget.addTab(thpTab, "THP Sensors")
Read and Plot THP Data: Use a QTimer to periodically read the THP sensor and update plots. For example:
python
Copy
Edit
# Set up THP sensor and CSV log
self.thp_sensor = THPSensor()  # hypothetical sensor interface
self.thp_log_file = open('thp_log.csv', 'w', newline='')
self.thp_log_writer = csv.writer(self.thp_log_file)
self.thp_log_writer.writerow(['Timestamp','Temperature','Humidity','Pressure'])

# Timer to poll THP sensor (e.g., once per second)
self.thp_timer = QtCore.QTimer(self)
self.thp_timer.timeout.connect(self.update_thp_data)
self.thp_timer.start(1000)  # 1000 ms = 1 second
The QTimer calls update_thp_data() every second
doc.qt.io
. In that callback:
python
Copy
Edit
def update_thp_data(self):
    temp, hum, pres = self.thp_sensor.read_data()
    timestamp = datetime.now().isoformat()
    # Update plots (appending to data series and redrawing)
    self.tempPlot.append_point(temp)
    self.humPlot.append_point(hum)
    self.pressurePlot.append_point(pres)
    # Log the readings
    self.thp_log_writer.writerow([timestamp, temp, hum, pres])
Each time through update_thp_data, the new THP readings are plotted and immediately written to the thp_log.csv file. Over time, this creates a real-time log of temperature, humidity, and pressure. The QTimer mechanism (with start(1000)) ensures periodic updates
doc.qt.io
. These code segments integrate the new functionality into the existing SciglobV4.0 codebase. Existing architecture and libraries (PyQt, csv module, sensor APIs) are preserved while adding the reset-on-start, dynamic integration logic, logging updates, GUI layout changes, and THP sensor plotting/logging. References: We use Python’s built-in csv.writer for outputting rows (see Python docs
docs.python.org
), Qt’s QLabel.setPixmap() for images
pythonguis.com
, and QTimer for periodic updates
doc.qt.io
. These demonstrate the methods used for logging and GUI updates.
