@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Organizador de Biblioteca PDF - Copia segura
echo.
echo === Criar biblioteca organizada ===
echo Selecione a MESMA pasta usada na analise.
echo Seus originais nao serao alterados: serao feitas copias em Biblioteca_Organizada.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 organizar_biblioteca_pdf.py aplicar
) else (
  python organizar_biblioteca_pdf.py aplicar
)
echo.
pause
