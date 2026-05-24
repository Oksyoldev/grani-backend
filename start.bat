@echo off
chcp 65001
title Grani Backend Server

echo ===============================
echo   GRANI MESSENGER BACKEND
echo ===============================
echo.
echo Starting server...
echo.

python mongo_main.py

echo.
echo Server stopped.
pause