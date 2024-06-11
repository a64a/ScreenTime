import platform
import keyboard
from datetime import datetime, timedelta
import re
import time

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

    def get_focused_window_info():
        hwnd = win32gui.GetForegroundWindow()
        window_text = win32gui.GetWindowText(hwnd)
        return window_text if window_text else "No focused window"

elif platform.system() == "Linux":
    from ewmh import EWMH

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

def read_existing_log(file_path):
    app_time_dict = {}
    try:
        with open(file_path, "r") as f:
            for line in f:
                match = re.match(r"<p>(\d+h )?(\d+m )?(\d+s )?(\d+ms): (.+)</p>", line.strip())
                if match:
                    hours = int(match.group(1).replace('h', '')) if match.group(1) else 0
                    minutes = int(match.group(2).replace('m', '')) if match.group(2) else 0
                    seconds = int(match.group(3).replace('s', '')) if match.group(3) else 0
                    milliseconds = int(match.group(4).replace('ms', '')) if match.group(4) else 0
                    app = match.group(5)
                    time_spent = timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)
                    app_time_dict[app] = time_spent
    except FileNotFoundError:
        pass
    return app_time_dict

def main():
    log_file = "window_focus_log.html"
    app_time_dict = read_existing_log(log_file)

    prev_window = ""
    prev_time = datetime.now()
    
    while not keyboard.is_pressed('esc'): 
        window_info = get_focused_window_info()
        
        if window_info != prev_window:
            current_time = datetime.now()
            time_diff = current_time - prev_time

            if prev_window:
                if prev_window in app_time_dict:
                    app_time_dict[prev_window] += time_diff
                else:
                    app_time_dict[prev_window] = time_diff
            
            with open(log_file, "w") as f:
                for app, total_time in app_time_dict.items():
                    formatted_time_diff = format_time_delta(total_time)
                    f.write(f"<p>{formatted_time_diff}: {app}</p>\n")

            print(f"{prev_window} - {time_diff}")

            prev_window = window_info
            prev_time = current_time

if __name__ == "__main__":
    main()