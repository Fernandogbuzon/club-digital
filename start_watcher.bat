@echo off
title ADESA 80 - Watcher de Resultados
cd /d "%~dp0"
echo ============================================
echo  ADESA 80 - Scraper automatico de resultados
echo  Se ejecuta cada 5 min en horario de partidos
echo  Cierra esta ventana para detenerlo
echo ============================================
echo.
.venv\Scripts\python.exe scraper_resultados.py --watch
pause
