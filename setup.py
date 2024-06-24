import sys
from cx_Freeze import setup, Executable

base = None
includes = ["PyQt5", "matplotlib", "platform", "datetime", "os", "sys", "json"]
include_files = ["icon.ico"]

if sys.platform == "win32":
    base = "Win32GUI"
    includes.extend(["win32gui", "elevate"])
elif sys.platform == "darwin":
    includes.extend(["objc", "Cocoa", "Quartz"])
elif sys.platform == "linux":
    includes.extend(["ewmh"])

build_exe_options = {
    "packages": ["os", "sys", "json", "datetime", "platform"],
    "includes": includes,
    "include_files": include_files,
}

setup(
    name="ScreenTimeTracker",
    version="0.1",
    description="Screen Time Tracker Application",
    options={"build_exe": build_exe_options},
    executables=[Executable("ScreenTime.py", base=base, icon="icon.ico")],
)

