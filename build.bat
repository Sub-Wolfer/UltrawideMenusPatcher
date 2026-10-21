@echo off
rem Builds dist\UltrawideMenusPatcher.exe (Windows, Python 3.10+).
python -m pip install pyinstaller==6.22.3
python -m PyInstaller --onefile --console --name UltrawideMenusPatcher --exclude-module numpy --exclude-module PIL --exclude-module tkinter --paths src src\uw_patcher.py
