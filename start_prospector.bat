@echo off
title Prospector - Scraping de Negócios
echo.
echo ============================================
echo  Iniciando Prospector - Scraping de Negócios
echo ============================================
echo.
chcp 65001 >nul
cd C:\Users\pedro\Desktop\scraping pro
echo.
echo [1/3] Verificando dependências do Python...
echo.
pip install -r requirements.txt 2>&1 | find "Successfully" >nul
if %errorlevel% equ 0 (
    echo [OK] Dependências instaladas.
) else (
    echo [ERRO] Falha ao instalar dependências.
    pause
    exit /b 1
)
echo.
echo [2/3] Instalando navegador Playwright...
python -m playwright install chromium 2>&1 | find "downloaded" >nul
if %errorlevel% equ 0 (
    echo [OK] Playwright Chromium instalado.
) else (
    echo [ERRO] Falha ao instalar Playwright.
    pause
    exit /b 1
)
echo.
echo [3/3] Verificando arquivos do sistema...
if not exist app.py (
    echo [ERRO] Arquivo app.py não encontrado.
    pause
    exit /b 1
)
if not exist run.py (
    echo [ERRO] Arquivo run.py não encontrado.
    pause
    exit /b 1
)
echo [OK] Todos os arquivos necessários encontrados.
echo.
echo ============================================
echo  Iniciando o servidor Prospector...
echo ============================================
echo.
timeout /t 3 /nobreak >nul
python run.py
echo.
echo Servidor finalizado.
pause