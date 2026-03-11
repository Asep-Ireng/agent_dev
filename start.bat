@echo off
echo ==============================================
echo 🚀 Booting AI Agent Studio
echo ==============================================

:: Start FastAPI Backend in a new hidden/minimized terminal window
echo [~] Starting FastAPI Backend (Port 8000)...
start "FastAPI Backend" /MIN cmd /c "cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

:: Start Next.js Frontend in this main terminal window
echo [~] Starting Next.js Frontend (Port 3000)...
cd frontend
npm run dev
