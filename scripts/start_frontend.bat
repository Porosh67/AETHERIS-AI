@echo off
REM AETHERIS AI — Start frontend dev server (Windows)
REM Requires Node.js on PATH
cd frontend
set PATH=C:\Program Files\nodejs;%PATH%
echo Starting AETHERIS AI frontend on http://localhost:5173
npm run dev
