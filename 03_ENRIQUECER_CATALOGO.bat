@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Organizador de Biblioteca PDF - Catalogos publicos
echo.
echo === Enriquecer catalogo por bases publicas ===
echo Selecione a mesma pasta usada na analise.
echo Serão enviados apenas titulo, autor e DOI detectado; nunca o PDF.
echo.
echo A busca pode levar bastante tempo para milhares de livros.
echo Ela grava um cache e pode ser interrompida com Ctrl+C e retomada depois.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 organizar_biblioteca_pdf.py enriquecer --pausa 0.55
) else (
  python organizar_biblioteca_pdf.py enriquecer --pausa 0.55
)
echo.
pause
