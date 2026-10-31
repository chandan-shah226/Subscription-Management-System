@echo off
setlocal
cd /d "%~dp0"

title Brightloop Subscription Management System
echo ========================================================
echo   Brightloop Software - Subscription Management System
echo ========================================================
echo.
echo [1/3] Starting Backend Server on port 5000...
start "Brightloop Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe app.py"

echo [2/3] Waiting for backend server to start...
timeout /t 3 /nobreak > nul

echo [3/3] Starting Frontend Server on port 8000...
start "Brightloop Frontend" cmd /k "cd /d "%~dp0frontend" && ..\backend\venv\Scripts\python.exe -m http.server 8000"

timeout /t 1 /nobreak > nul
echo.
echo Opening browser at http://localhost:8000...
start http://localhost:8000

echo.
echo ========================================================
echo   System is Running!
echo   - Frontend: http://localhost:8000
echo   - Backend:  http://127.0.0.1:5000
echo.
echo   Login Credentials:
echo   - Admin:    admin@brightloop.com    / Admin@123!
echo   - Staff:    staff@brightloop.com    / Staff@123!
echo   - Customer: customer@brightloop.com / Customer@123!
echo ========================================================
pause
