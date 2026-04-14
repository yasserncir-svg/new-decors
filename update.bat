@echo off
echo ========================================
echo   MISE A JOUR NEW DECORS
echo ========================================
echo.

echo 1. Sauvegarde de la base de données...
python backup_db.py

echo.
echo 2. Pull des modifications GitHub...
git pull origin main

echo.
echo 3. Application des migrations...
python migrate.py

echo.
echo 4. Redémarrage de l'application...
taskkill /F /IM python.exe 2>nul
start python ecommerce_complet.py

echo.
echo ✅ Mise à jour terminée !
pause
