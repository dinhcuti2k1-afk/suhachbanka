@echo off
chcp 65001 >nul
echo === TAO APP THE TIEN (co server rieng) ===
python --version >nul 2>&1
if errorlevel 1 (
  echo Chua cai Python hoac chua tick Add Python to PATH
  pause
  exit /b
)
python -m pip install flask pyinstaller
if errorlevel 1 (
  echo Cai thu vien that bai, kiem tra mang
  pause
  exit /b
)
python -m PyInstaller --noconfirm --onefile --windowed --name TheTien --add-data "static;static" app.py
if errorlevel 1 (
  echo Tao app that bai
  pause
  exit /b
)
echo.
echo XONG! App nam o: dist\TheTien.exe
echo Gui file TheTien.exe cho nguoi khac, ho bam dup la chay (khong can cai Python).
pause
