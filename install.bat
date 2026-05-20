@echo off
echo Setting up RealityScanFlow...
python -m venv .venv
.venv\Scripts\pip install rich beautifulsoup4
echo Done. You can now use rsflow.bat
pause