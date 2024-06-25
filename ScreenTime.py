import platform
from datetime import datetime, timedelta
import os
import sys
import json
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QDateEdit, QLabel, QHBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class MainApp(QtWidgets.QApplication):
    def applicationSupportsSecureRestorableState(self):
        return True


if platform.system() == "Darwin":
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

    def get_focused_window_info():
        options = kCGWindowListOptionOnScreenOnly
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for window in window_list:
            if window.get('kCGWindowLayer') == 0:
                app_name = window.get('kCGWindowOwnerName', 'Unknown')
                return f"{app_name}"
        return "No focused window"

elif platform.system() == "Windows":
    import win32gui
    from elevate import elevate

    elevate()

    def get_focused_window_info():
        hwnd = win32gui.GetForegroundWindow()
        window_text = win32gui.GetWindowText(hwnd)
        return window_text if window_text else "No focused window"

elif platform.system() == "Linux":
    from ewmh import EWMH

    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo"] + ["python3"] + sys.argv)

    def get_focused_window_info():
        ewmh = EWMH()
        window = ewmh.getActiveWindow()
        if window:
            window_name = ewmh.getWmName(window)
            return window_name if window_name else "No focused window"
        return "No focused window"


def format_time_delta(td):
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds % 1) * 1000)

    if hours > 0:
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    elif seconds > 0:
        return f"{seconds}s"
    else:
        return f"{milliseconds}ms"


def ensure_data_file_exists(data_file):
    if not os.path.exists(data_file):
        with open(data_file, "w") as f:
            json.dump({}, f)


def read_data_from_file(data_file):
    with open(data_file, "r") as f:
        return json.load(f)


def write_data_to_file(data_file, data):
    with open(data_file, "w") as f:
        json.dump(data, f)


class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=8, height=6, dpi=100):
        plt.style.use('dark_background')
        fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#2E2E2E')
        self.ax.set_facecolor('#2E2E2E')
        super(MplCanvas, self).__init__(fig)


def main():
    data_file = "app_usage_data.json"
    ensure_data_file_exists(data_file)
    app_time_dict = read_data_from_file(data_file)

    prev_window = ""
    prev_time = datetime.now()

    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    window.setWindowTitle("Screen Time Tracker")
    layout = QtWidgets.QVBoxLayout()

    control_layout = QHBoxLayout()
    layout.addLayout(control_layout)

    start_date_edit = QDateEdit(calendarPopup=True)
    start_date_edit.setDate(QtCore.QDate.currentDate())
    end_date_edit = QDateEdit(calendarPopup=True)
    end_date_edit.setDate(QtCore.QDate.currentDate())
    today_button = QtWidgets.QPushButton("Today")

    control_layout.addWidget(QLabel("Start Date:"))
    control_layout.addWidget(start_date_edit)
    control_layout.addWidget(QLabel("End Date:"))
    control_layout.addWidget(end_date_edit)
    control_layout.addWidget(today_button)

    stop_button = QtWidgets.QPushButton("Stop Tracking")
    layout.addWidget(stop_button)

    canvas = MplCanvas(window, width=10, height=6, dpi=100)
    layout.addWidget(canvas)

    window.setLayout(layout)

    def stop_tracking():
        app.quit()

    stop_button.clicked.connect(stop_tracking)

    def update_log():
        nonlocal prev_window, prev_time
        window_info = get_focused_window_info()

        if window_info != prev_window:
            current_time = datetime.now()
            time_diff = current_time - prev_time

            if prev_window:
                day_key = datetime.now().strftime('%Y-%m-%d')
                if day_key not in app_time_dict:
                    app_time_dict[day_key] = {}
                if prev_window in app_time_dict[day_key]:
                    app_time_dict[day_key][prev_window] += time_diff.total_seconds()
                else:
                    app_time_dict[day_key][prev_window] = time_diff.total_seconds()

            prev_window = window_info
            prev_time = current_time

        write_data_to_file(data_file, app_time_dict)

        update_plot()
        QtCore.QTimer.singleShot(100, update_log)

    def update_plot():
        canvas.ax.clear()
        start_date = start_date_edit.date().toPyDate()
        end_date = end_date_edit.date().toPyDate()
        day_keys = sorted(
            key for key in app_time_dict.keys() if start_date <= datetime.strptime(key, '%Y-%m-%d').date() <= end_date)

        app_names = set()
        for day in day_keys:
            for app in app_time_dict[day].keys():
                app_names.add(app)

        app_names = sorted(app_names)
        data = {app: [0] * len(day_keys) for app in app_names}

        for i, day in enumerate(day_keys):
            for app in app_time_dict[day]:
                data[app][i] = app_time_dict[day][app]

        bars = []
        labels = []
        for i, day in enumerate(day_keys):
            bottom = 0
            for app in app_names:
                if data[app][i] > 0:
                    bar = canvas.ax.bar(i, data[app][i], bottom=bottom, label=app if i == 0 else "",
                                        color=plt.cm.tab20(app_names.index(app) / len(app_names)))
                    bars.append(bar)
                    bottom += data[app][i]
                    canvas.ax.text(i, bottom - data[app][i] / 2, format_time_delta(timedelta(seconds=data[app][i])),
                                   ha='center', va='center', color='white', fontsize=8)

        canvas.ax.set_xticks(range(len(day_keys)))
        canvas.ax.set_xticklabels(day_keys, rotation=45, ha='right', color='white')
        canvas.ax.set_xlabel('Days', color='white')
        canvas.ax.set_ylabel('Time Active', color='white')
        canvas.ax.set_title('Most Used Applications Over Days', color='white')
        canvas.ax.spines['bottom'].set_color('white')
        canvas.ax.spines['top'].set_color('white')
        canvas.ax.spines['left'].set_color('white')
        canvas.ax.spines['right'].set_color('white')
        canvas.ax.tick_params(axis='both', colors='white')

        canvas.draw()

        def on_hover(event):
            canvas.ax.texts.clear()
            if event.inaxes == canvas.ax:
                for i, bar in enumerate(bars):
                    if bar.contains(event)[0]:
                        idx = i % len(app_names)
                        app_name = app_names[idx]
                        canvas.ax.annotate(f'{app_name}',
                                           xy=(event.xdata, event.ydata),
                                           xytext=(event.xdata, event.ydata + 50),
                                           arrowprops=dict(facecolor='yellow', shrink=0.05),
                                           fontsize=12, color='yellow')
                        canvas.draw()
                        break

        canvas.mpl_connect('motion_notify_event', on_hover)

    def set_today():
        today = QtCore.QDate.currentDate()
        start_date_edit.setDate(today)
        end_date_edit.setDate(today)
        update_plot()

    today_button.clicked.connect(set_today)
    start_date_edit.dateChanged.connect(update_plot)
    end_date_edit.dateChanged.connect(update_plot)

    update_log()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()