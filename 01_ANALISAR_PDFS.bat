@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Organizador de Biblioteca PDF - Analise segura
echo.
echo === Organizador de Biblioteca PDF ===
echo Esta primeira etapa NAO move, renomeia ou apaga nenhum PDF.
echo Um seletor de pasta sera aberto em seguida.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m pip install --user -r requirements.txt
  if errorlevel 1 goto :erro_dependencia
  py -3 organizar_biblioteca_pdf.py analisar
) else (
  python -m pip install --user -r requirements.txt
  if errorlevel 1 goto :erro_dependencia
  python organizar_biblioteca_pdf.py analisar
)
echo.
pause
exit /b

:erro_dependencia
echo.
echo Nao foi possivel instalar a dependencia. Confirme que o Python 3 esta instalado.
echo Baixe-o em https://www.python.org/downloads/ e marque "Add Python to PATH".
echo Depois execute este arquivo novamente.
pause
