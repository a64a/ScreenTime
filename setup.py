from setuptools import setup

APP = ['ScreenTime.py']
OPTIONS = {
    'iconfile':'icon.ico',
    'argv_emulation': True,
    'packages': ['platform', 'datetime', 'os', 'sys', 'json', 'PyQt5', 'matplotlib'],
}

setup(
    app=APP,
    name='Screen Time',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

