@echo off
title Odoo Telegram Bot (24/7)
echo Eski bot jarayonlari tozalanmoqda...
taskkill /F /IM python.exe 2>nul

:loop
echo ==============================================
echo Bot ishga tushirilmoqda... %date% %time%
echo ==============================================
python main.py
echo.
echo ⚠️ Bot qandaydir xatolik bilan o'chib qoldi! 
echo 5 soniyadan so'ng avtomatik qayta ishga tushadi...
timeout /t 5
goto loop
