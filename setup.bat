@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo 🛠️  Setting up AI Agent Studio
echo ==============================================

:: 1. Copy .env if not exists
if not exist ".env" (
    echo [~] Creating .env from .env.example...
    copy ".env.example" ".env" >nul
    echo [ok] .env created. Don't forget to put your API keys in it.
) else (
    echo [ok] .env already exists. Skipping copy.
)

:: 2. Setup Python dependencies
echo.
echo [~] Setting up Python dependencies...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [error] Python is not installed or not in PATH. Please install Python.
    exit /b 1
)

echo [~] Running: python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements.txt
if %errorlevel% neq 0 (
    echo [error] Failed to install Python dependencies.
    exit /b 1
)
echo [ok] Python dependencies installed successfully.

:: 3. Setup Node.js dependencies
echo.
echo [~] Setting up Node.js dependencies...
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [error] Node.js / npm is not installed or not in PATH. Please install Node.js.
    exit /b 1
)

:: Frontend npm install
echo [~] Installing Next.js frontend dependencies (in /frontend)...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [error] Failed to install frontend dependencies.
    cd ..
    exit /b 1
)
cd ..
echo [ok] Frontend dependencies installed.

:: Backend npm install (just in case dotenv is needed there)
if exist "backend\package.json" (
    echo [~] Installing backend Node.js dependencies (in /backend)...
    cd backend
    call npm install
    if %errorlevel% neq 0 (
        echo [error] Failed to install backend Node.js dependencies.
        cd ..
        exit /b 1
    )
    cd ..
    echo [ok] Backend Node.js dependencies installed.
)

echo.
echo ==============================================
echo 🎉 Setup complete!
echo ==============================================
echo To start the AI Agent Studio, run:
echo   start.bat
echo ==============================================
pause
