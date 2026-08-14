@echo off
echo ==============================================
echo KABAR SAHAM V6 - TEST TELEGRAM LOCAL
echo ==============================================
echo.
echo Pastikan .env V5.4 tersedia atau environment
echo TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_IDS sudah ada.
echo.
python scan_once.py --mode test_telegram
pause
