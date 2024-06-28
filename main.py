import platform
import sqlite3
import sys
from datetime import datetime, timedelta

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QPushButton,
    QSystemTrayIcon,
    QAction,
    QMenu,
    QVBoxLayout,
    QDialog,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

matplotlib.use("Qt5Agg")

detailed_view_active = False
DATABASE = "app_usage.db"
CATEGORY_COLORS = {
    "Uncategorized": "#606060",
    "Utility": "#3e2c4e",
    "Entertainment": "#929292",
    "Social": "#9B86BD",
}


class MyApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)


def check_dependencies():
    try:
        import psutil
    except ImportError:
        sys.exit(1)

    if platform.system() == "Linux":
        try:
            import ewmh
        except ImportError:
            sys.exit(1)


check_dependencies()

if platform.system() == "Darwin":
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
    )

    def get_focused_app():
        options = kCGWindowListOptionOnScreenOnly
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for window in window_list:
            if window.get("kCGWindowLayer") == 0:
                app_name = window.get("kCGWindowOwnerName", "Unknown")
                return f"{app_name}"
        return "No focused window"

elif platform.system() == "Windows":
    import win32gui
    import win32process
    import psutil

    def get_focused_app():
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                app_name = process.name()
                return app_name
            except psutil.NoSuchProcess:
                return "Unknown application"
        return "No focused window"

elif platform.system() == "Linux":
    from ewmh import EWMH

    def get_focused_app():
        ewmh = EWMH()
        window = ewmh.getActiveWindow()
        if window:
            window_name = ewmh.getWmName(window)
            return window_name if window_name else "No focused window"
        return "No focused window"


def setup_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS day_tables (day TEXT PRIMARY KEY)""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS app_categories (app_name TEXT PRIMARY KEY, category TEXT NOT NULL)"""
    )
    conn.commit()
    conn.close()


def get_table_name(date):
    return f"usage_{date.replace('-', '_')}"


def create_day_table(date):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    table_name = get_table_name(date)
    cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS {table_name} (app_name TEXT PRIMARY KEY, usage_seconds REAL NOT NULL)"""
    )
    cursor.execute("INSERT OR IGNORE INTO day_tables (day) VALUES (?)", (date,))
    conn.commit()
    conn.close()


def read_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT day FROM day_tables")
    days = cursor.fetchall()
    appdata = {}
    for day_tuple in days:
        day = day_tuple[0]
        table_name = get_table_name(day)
        cursor.execute(f"SELECT app_name, usage_seconds FROM {table_name}")
        data = cursor.fetchall()
        appdata[day] = {app_name: usage_seconds for app_name, usage_seconds in data}
    cursor.execute("SELECT app_name, category FROM app_categories")
    categories = cursor.fetchall()
    appcategories = {app_name: category for app_name, category in categories}
    conn.close()
    return appdata, appcategories


def write_db(date, app_name, usage_seconds):
    create_day_table(date)
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    table_name = get_table_name(date)
    cursor.execute(
        f"SELECT usage_seconds FROM {table_name} WHERE app_name = ?", (app_name,)
    )
    result = cursor.fetchone()
    if result:
        updated_usage_seconds = result[0] + usage_seconds
        cursor.execute(
            f"UPDATE {table_name} SET usage_seconds = ? WHERE app_name = ?",
            (updated_usage_seconds, app_name),
        )
    else:
        cursor.execute(
            f"INSERT INTO {table_name} (app_name, usage_seconds) VALUES (?, ?)",
            (app_name, usage_seconds),
        )
    conn.commit()
    conn.close()


def set_app_category(app_name, category):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO app_categories (app_name, category) VALUES (?, ?)",
        (app_name, category),
    )
    conn.commit()
    conn.close()


class PlotCanvas(FigureCanvas):
    def __init__(self, width=8, height=6, dpi=100):
        plt.style.use("dark_background")
        fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor("#1C1C1E")
        self.ax.set_facecolor("#1C1C1E")
        super(PlotCanvas, self).__init__(fig)


class DetailedViewWindow(QDialog):
    def __init__(self, day, apps_data):
        super().__init__()
        self.setWindowTitle(f"Details for {day}")
        self.setStyleSheet("background-color: #1C1C1E; color: white;")
        self.setModal(True)
        self.showMaximized()
        layout = QVBoxLayout()
        self.canvas = PlotCanvas(width=10, height=6, dpi=100)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        app_names = []
        app_values = []

        total_seconds = sum(apps_data.values())
        threshold = total_seconds * 0.01042

        for app, seconds in apps_data.items():
            if seconds >= threshold:
                app_names.append(app)
                app_values.append(seconds)

        if not app_values:
            return

        total_seconds = sum(app_values)
        app_values_hours = [value / 3600 for value in app_values]
        dark_colors = [
            "#7776B3",
            "#9B86BD",
            "#E2BBE9",
            "#606060",
            "#2a2a2c",
            "#6850cf",
            "#3b4b74",
            "#888888",
            "#929292",
            "#3e2c4e",
        ]
        colors = [dark_colors[i % len(dark_colors)] for i in range(len(app_names))]

        wedges, texts, autotexts = self.canvas.ax.pie(
            app_values_hours,
            labels=None,
            colors=colors,
            autopct=lambda p: "",
            startangle=140,
            wedgeprops=dict(width=0.5, edgecolor="#1c1e1e"),
        )

        for i, (wedge, app) in enumerate(zip(wedges, app_names)):
            angle = (wedge.theta2 + wedge.theta1) / 2
            x = wedge.r * np.cos(np.radians(angle))
            y = wedge.r * np.sin(np.radians(angle))
            arrow_x = wedge.r * 1.3 * np.cos(np.radians(angle))
            arrow_y = wedge.r * 1.3 * np.sin(np.radians(angle))
            self.canvas.ax.annotate(
                format_time(timedelta(seconds=app_values[i])),
                xy=(x, y),
                xytext=(arrow_x, arrow_y),
                arrowprops=dict(
                    facecolor="white", edgecolor="white", arrowstyle="-", linestyle="-"
                ),
                ha="center",
                va="center",
                color="white",
                fontsize=10,
            )

        total_time_str = format_time(timedelta(seconds=total_seconds))
        self.canvas.ax.text(
            0,
            0,
            f"{total_time_str}\nTotal time",
            ha="center",
            va="center",
            color="white",
            fontsize=16,
        )

        patches = [
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label=app_names[i],
                markersize=10,
                markerfacecolor=colors[i],
            )
            for i in range(len(app_names))
        ]
        if patches:
            self.canvas.ax.legend(
                handles=patches,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.1),
                fontsize=10,
                frameon=False,
                ncol=7
            )
        self.canvas.draw()


def detailed_view_on_click(event):
    global detailed_view_active, bars
    if detailed_view_active:
        return

    start_date = current_start
    end_date = current_end
    day_keys = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_date - start_date).days + 1)]

    if not detailed_view_active:
        for bar in bars:
            if bar.contains(event)[0]:
                dayindex = int(bar.get_x() + bar.get_width() / 2)
                day_str = day_keys[dayindex]
                detailed_view_window = DetailedViewWindow(day_str, app_data.get(day_str, {}))
                detailed_view_window.exec_()
                return


def update_plot():
    global detailed_view_active, bars
    if detailed_view_active:
        return

    canvas.ax.clear()
    start_date = current_start
    end_date = current_end
    day_keys = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_date - start_date).days + 1)]
    day_names = [(start_date + timedelta(days=i)).strftime('%A')[0] for i in range((end_date - start_date).days + 1)]
    category_totals = {category: [0] * len(day_keys) for category in set(app_categories.values())}
    category_totals['Uncategorized'] = [0] * len(day_keys)

    for day_index, day in enumerate(day_keys):
        if day in app_data:
            for app_name, usage_seconds in app_data[day].items():
                category = app_categories.get(app_name, 'Uncategorized')
                category_totals[category][day_index] += usage_seconds

    bottom_values = [0] * len(day_keys)
    bars = []
    for category, totals in category_totals.items():
        color = CATEGORY_COLORS.get(category, 'gray')
        totals_hours = [total / 3600 for total in totals]
        bar_container = canvas.ax.bar(range(len(day_keys)), totals_hours, bottom=bottom_values, label=category,
                                      color=color,
                                      edgecolor='#1c1e1e', linewidth=2, capstyle='round')
        bars.extend(bar_container)
        bottom_values = [sum(x) for x in zip(bottom_values, totals_hours)]

    canvas.ax.set_xticks(range(len(day_keys)))
    canvas.ax.set_xticklabels(day_names, ha='center', color='gray', fontsize=12)
    canvas.ax.set_xlabel('', fontsize=0)
    canvas.ax.set_ylabel('Total Time Active [h]', color='white', fontsize=12)
    canvas.ax.set_title('Total Screen Time Over Days', color='white', fontsize=14)
    canvas.ax.spines['bottom'].set_color('white')
    canvas.ax.spines['top'].set_color('white')
    canvas.ax.spines['left'].set_color('white')
    canvas.ax.spines['right'].set_color('white')
    canvas.ax.tick_params(axis='both', colors='white')
    canvas.ax.relim()
    canvas.ax.autoscale_view()

    canvas.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fontsize=10, frameon=False, ncol=4)

    date_range_lbl.setText(f"Viewing: {current_start} to {current_end}")
    back_to_week_btn.hide()
    canvas.draw()


def format_time(td):
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def set_date_range(start, end=None):
    global current_start, current_end, detailed_view_active
    detailed_view_active = False
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


def back_to_week():
    canvas.ax.clear()
    set_date_range(current_start - timedelta(days=current_start.weekday()), None)
    update_plot()


def stop_tracking():
    save_data_on_exit()
    QtWidgets.qApp.quit()


def save_data_on_exit():
    global prev_window, prev_time
    current_time = datetime.now()
    time_diff = current_time - prev_time
    if prev_window:
        day_key = datetime.now().strftime("%Y-%m-%d")
        if day_key not in app_data:
            app_data[day_key] = {}
        app_data[day_key][prev_window] = (
                app_data[day_key].get(prev_window, 0) + time_diff.total_seconds()
        )
        write_db(day_key, prev_window, time_diff.total_seconds())
    prev_window = ""
    prev_time = current_time


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Time Tracker")
        self.setStyleSheet("background-color: #1C1C1E; color: white;")
        self.showMaximized()
        layout = QtWidgets.QVBoxLayout()
        control_layout = QHBoxLayout()
        layout.addLayout(control_layout)
        prev_btn = QPushButton("< Week")
        next_btn = QPushButton("Week >")
        this_week_btn = QPushButton("This Week")
        prev_btn.setStyleSheet(
            "background-color: #3a3a3c; color: white; border-radius: 5px; padding: 5px;"
        )
        next_btn.setStyleSheet(
            "background-color: #3a3a3c; color: white; border-radius: 5px; padding: 5px;"
        )
        this_week_btn.setStyleSheet(
            "background-color: #3a3a3c; color: white; border-radius: 5px; padding: 5px;"
        )
        control_layout.addWidget(prev_btn)
        control_layout.addWidget(next_btn)
        control_layout.addWidget(this_week_btn)
        global date_range_lbl
        date_range_lbl = QLabel()
        date_range_lbl.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(date_range_lbl)
        global back_to_week_btn
        back_to_week_btn = QPushButton("Back to Week View")
        back_to_week_btn.setStyleSheet(
            "background-color: #3a3a3c; color: white; border-radius: 5px; padding: 5px;"
        )
        back_to_week_btn.clicked.connect(back_to_week)
        layout.addWidget(back_to_week_btn)
        back_to_week_btn.hide()
        stop_btn = QPushButton("Stop Tracking")
        stop_btn.setStyleSheet(
            "background-color: #3a3a3c; color: white; border-radius: 5px; padding: 5px;"
        )
        layout.addWidget(stop_btn)
        global canvas
        canvas = PlotCanvas(width=10, height=6, dpi=100)
        canvas.mpl_connect("button_press_event", detailed_view_on_click)
        scroll = QScrollArea()
        scroll.setWidget(canvas)
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        layout.addWidget(scroll)
        self.setLayout(layout)
        stop_btn.clicked.connect(stop_tracking)
        prev_btn.clicked.connect(prev_week)
        next_btn.clicked.connect(next_week)
        this_week_btn.clicked.connect(this_week)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.ico"))
        show_action = QAction("Show", self)
        quit_action = QAction("Exit", self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(stop_tracking)
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
            2000,
        )


def update_log():
    global prev_window, prev_time
    window_info = get_focused_app()
    if window_info != prev_window:
        current_time = datetime.now()
        time_diff = current_time - prev_time
        if prev_window:
            day_key = datetime.now().strftime("%Y-%m-%d")
            if day_key not in app_data:
                app_data[day_key] = {}
            app_data[day_key][prev_window] = (
                    app_data[day_key].get(prev_window, 0) + time_diff.total_seconds()
            )
            write_db(day_key, prev_window, time_diff.total_seconds())
        prev_window = window_info
        prev_time = current_time
    QtCore.QTimer.singleShot(500, update_log)


def main():
    global app_data, app_categories, current_start, current_end, prev_window, prev_time
    setup_db()
    app_data, app_categories = read_db()
    prev_window = ""
    prev_time = datetime.now()
    app = MyApplication(sys.argv)
    window = MainWindow()

    current_start = datetime.today().date() - timedelta(days=datetime.today().weekday())
    current_end = current_start + timedelta(days=6)
    update_plot()
    update_log()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
