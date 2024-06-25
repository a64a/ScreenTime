import platform
from datetime import datetime, timedelta
import os
import sys
import sqlite3
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QScrollArea, QSizePolicy, QPushButton, QSystemTrayIcon, QAction, QMenu
from PyQt5.QtGui import QIcon
import matplotlib

matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np

detailed_view_active = False
DATABASE = "app_usage.db"

if platform.system() == "Darwin":
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

    def get_focused_app():
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

    def get_focused_app():
        hwnd = win32gui.GetForegroundWindow()
        window_text = win32gui.GetWindowText(hwnd)
        return window_text if window_text else "No focused window"

elif platform.system() == "Linux":
    from ewmh import EWMH

    if os.geteuid() != 0:
        os.execvp("sudo", ["sudo"] + ["python3"] + sys.argv)

    def get_focused_app():
        ewmh = EWMH()
        window = ewmh.getActiveWindow()
        if window:
            window_name = ewmh.getWmName(window)
            return window_name if window_name else "No focused window"
        return "No focused window"

def format_time(td):
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

def setup_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS app_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        app_name TEXT NOT NULL,
                        usage_seconds REAL NOT NULL)''')
    conn.commit()
    conn.close()

def read_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT date, app_name, SUM(usage_seconds) FROM app_usage GROUP BY date, app_name")
    data = cursor.fetchall()
    conn.close()
    app_data = {}
    for date, app_name, usage_seconds in data:
        if date not in app_data:
            app_data[date] = {}
        app_data[date][app_name] = usage_seconds
    return app_data

def write_db(date, app_name, usage_seconds):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO app_usage (date, app_name, usage_seconds) VALUES (?, ?, ?)",
                   (date, app_name, usage_seconds))
    conn.commit()
    conn.close()

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        plt.style.use('dark_background')
        fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#2E2E2E')
        self.ax.set_facecolor('#2E2E2E')
        super(PlotCanvas, self).__init__(fig)

def show_day(day, apps_data):
    global detailed_view_active
    detailed_view_active = True
    canvas.ax.clear()
    fig = canvas.figure
    ax = canvas.ax
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#2E2E2E')
    bottom = 0
    app_names = sorted(apps_data.keys())
    for app in app_names:
        if apps_data[app] > 0:
            ax.bar(app, apps_data[app], width=0.5, bottom=bottom, label=app,
                   color=plt.cm.tab20(app_names.index(app) / len(app_names)))
            bottom += apps_data[app]
            ax.text(app, bottom - apps_data[app] / 2, format_time(timedelta(seconds=apps_data[app])),
                    ha='center', va='center', color='white', fontsize=8)
    ax.set_xticks([])
    ax.set_xticklabels([])
    ax.set_xlabel('', fontsize=0)
    ax.set_ylabel('Time Active', color='white', fontsize=12, fontweight='bold')
    ax.set_title(f'Details for {day}', color='white', fontsize=14, fontweight='bold')
    ax.spines['bottom'].set_color('white')
    ax.spines['top'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.tick_params(axis='both', colors='white')
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='lower right', bbox_to_anchor=(1, 0), fontsize=10)
    back_to_week_btn.show()
    canvas.draw()

def update_plot():
    global detailed_view_active
    if detailed_view_active:
        return  # Skip updating the plot if detailed view is active

    canvas.ax.clear()
    start_date = current_start
    end_date = current_end
    day_keys = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_date - start_date).days + 1)]
    day_names = [(start_date + timedelta(days=i)).strftime('%A') for i in range((end_date - start_date).days + 1)]
    app_names = set()
    for day in day_keys:
        if day in app_data:
            app_names.update(app_data[day].keys())
    app_names = sorted(app_names)
    colors = plt.cm.tab20(np.linspace(0, 1, len(app_names)))
    bottom_values = {day: 0 for day in day_keys}
    for app_name, color in zip(app_names, colors):
        values = [app_data.get(day, {}).get(app_name, 0) for day in day_keys]
        canvas.ax.bar(range(len(day_keys)), values, bottom=[bottom_values[day] for day in day_keys],
                      color='gray', label=app_name)
        for day, value in zip(day_keys, values):
            bottom_values[day] += value

    def on_click(event):
        for bar in canvas.ax.patches:
            if bar.contains(event)[0]:
                day_index = int(bar.get_x() + bar.get_width() / 2)
                day_str = day_keys[day_index]
                show_day(day_str, app_data.get(day_str, {}))
                return

    canvas.mpl_connect("button_press_event", on_click)
    canvas.ax.set_xticks(range(len(day_keys)))
    canvas.ax.set_xticklabels(day_names, ha='center', color='white', fontsize=10, fontweight='bold', rotation=45)
    canvas.ax.set_xlabel('', fontsize=0)
    canvas.ax.set_ylabel('Total Time Active', color='white', fontsize=12, fontweight='bold')
    canvas.ax.set_title('Total Screen Time Over Days', color='white', fontsize=14, fontweight='bold')
    canvas.ax.spines['bottom'].set_color('white')
    canvas.ax.spines['top'].set_color('white')
    canvas.ax.spines['left'].set_color('white')
    canvas.ax.spines['right'].set_color('white')
    canvas.ax.tick_params(axis='both', colors='white')
    date_range_lbl.setText(f"Viewing: {current_start} to {current_end}")
    back_to_week_btn.hide()
    canvas.draw()

def set_date_range(start, end=None):
    global current_start, current_end, detailed_view_active
    detailed_view_active = False  # Reset detailed view flag when changing date range
    current_start = start
    current_end = start + timedelta(days=6) if end is None else end
    update_plot()

def prev_week():
    global current_start, current_end
    current_start -= timedelta(days=7)
    current_end -= timedelta(days=7)
    update_plot()

def next_week():
    global current_start, current_end
    current_start += timedelta(days=7)
    current_end += timedelta(days=7)
    update_plot()

def this_week():
    today = datetime.today().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    set_date_range(start_of_week, end_of_week)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Time Tracker")
        layout = QtWidgets.QVBoxLayout()
        control_layout = QHBoxLayout()
        layout.addLayout(control_layout)
        prev_btn = QPushButton("< Week")
        next_btn = QPushButton("Week >")
        this_week_btn = QPushButton("This Week")
        control_layout.addWidget(prev_btn)
        control_layout.addWidget(next_btn)
        control_layout.addWidget(this_week_btn)
        global date_range_lbl
        date_range_lbl = QLabel()
        date_range_lbl.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(date_range_lbl)
        global back_to_week_btn
        back_to_week_btn = QPushButton("Back to Week View")
        back_to_week_btn.clicked.connect(self.back_to_week)
        layout.addWidget(back_to_week_btn)
        back_to_week_btn.hide()
        stop_btn = QPushButton("Stop Tracking")
        layout.addWidget(stop_btn)
        global canvas
        canvas = PlotCanvas(self, width=10, height=6, dpi=100)
        scroll = QScrollArea()
        scroll.setWidget(canvas)
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        layout.addWidget(scroll)
        self.setLayout(layout)
        stop_btn.clicked.connect(self.stop_tracking)
        prev_btn.clicked.connect(prev_week)
        next_btn.clicked.connect(next_week)
        this_week_btn.clicked.connect(this_week)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.ico"))
        show_action = QAction("Show", self)
        quit_action = QAction("Exit", self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QtWidgets.qApp.quit)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Screen Time Tracker",
            "Application minimized to tray",
            QSystemTrayIcon.Information,
            2000
        )

    def stop_tracking(self):
        QtWidgets.qApp.quit()

    def back_to_week(self):
        set_date_range(current_start - timedelta(days=current_start.weekday()), None)

def main():
    global app_data, current_start, current_end
    setup_db()
    app_data = read_db()
    prev_window = ""
    prev_time = datetime.now()
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()

    def update_log():
        nonlocal prev_window, prev_time
        window_info = get_focused_app()
        if window_info != prev_window:
            current_time = datetime.now()
            time_diff = current_time - prev_time
            if prev_window:
                day_key = datetime.now().strftime('%Y-%m-%d')
                if day_key not in app_data:
                    app_data[day_key] = {}
                app_data[day_key][prev_window] = app_data[day_key].get(prev_window, 0) + time_diff.total_seconds()
                write_db(day_key, prev_window, time_diff.total_seconds())
            prev_window = window_info
            prev_time = current_time
        update_plot()
        QtCore.QTimer.singleShot(100, update_log)

    current_start = datetime.today().date() - timedelta(days=datetime.today().weekday())
    current_end = current_start + timedelta(days=6)
    update_log()
    window.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()