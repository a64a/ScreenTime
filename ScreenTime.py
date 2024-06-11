import platform
import keyboard
from datetime import datetime, timedelta
import re
import time
import os
import sys
import tkinter as tk
from tkinter import messagebox
import webbrowser

if platform.system() == "Darwin":
    import objc
    from Cocoa import NSWorkspace, NSApplication, NSApp, NSRunningApplication
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

    formatted_time_diff = ""
    if hours > 0:
        formatted_time_diff += f"{hours}h "
    if minutes > 0 or hours > 0:
        formatted_time_diff += f"{minutes}m "
    if seconds > 0 or minutes > 0 or hours > 0:
        formatted_time_diff += f"{seconds}s "
    formatted_time_diff += f"{milliseconds}ms"
    return formatted_time_diff.strip()

def ensure_log_file_exists(log_file):
    # Create the file if it does not exist
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("<html><body>\n</body></html>")

def main():
    log_file = "window_focus_log.html"
    ensure_log_file_exists(log_file)

    app_time_dict = {}
    prev_window = ""
    prev_time = datetime.now()
    app_id = 0
    app_ids = {}

    # Open the log file in the default web browser
    webbrowser.open('file://' + os.path.realpath(log_file))

    root = tk.Tk()
    root.title("Screen Time Tracker")

    def stop_tracking():
        root.quit()

    stop_button = tk.Button(root, text="Stop Tracking", command=stop_tracking)
    stop_button.pack(pady=20)

    def update_log():
        nonlocal prev_window, prev_time, app_id
        window_info = get_focused_window_info()

        if window_info != prev_window:
            current_time = datetime.now()
            time_diff = current_time - prev_time

            if prev_window:
                if prev_window in app_time_dict:
                    app_time_dict[prev_window] += time_diff
                else:
                    app_time_dict[prev_window] = time_diff

            if prev_window:
                with open(log_file, "r+") as f:
                    content = f.read()
                    pattern = re.compile(f"<p id='{prev_window}'>.*?</p>")
                    formatted_time_diff = format_time_delta(app_time_dict[prev_window])
                    new_entry = f"<p id='{prev_window}'>{formatted_time_diff}: {prev_window}</p>"

                    if pattern.search(content):
                        content = pattern.sub(new_entry, content)
                    else:
                        content = content.replace("</body>", new_entry + "\n</body>")

                    f.seek(0)
                    f.write(content)
                    f.truncate()

            prev_window = window_info
            prev_time = current_time

        root.after(100, update_log)

    root.after(100, update_log)
    root.mainloop()

if __name__ == "__main__":
    main()