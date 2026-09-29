@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Organizador de Biblioteca PDF - Buscar mais metadados
echo.
echo === Buscar mais metadados nos itens ainda sem resultado ===
echo Selecione a mesma pasta usada nas etapas anteriores.
echo.
echo Esta etapa revisita somente as lacunas do cache com novas variacoes
echo de titulo e autor. Se configurou GOOGLE_BOOKS_API_KEY, ela tambem
echo usa essa chave para ampliar a cobertura do Google Books.
echo.
echo A operacao pode levar bastante tempo e pode ser interrompida com Ctrl+C.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 organizar_biblioteca_pdf.py enriquecer --refazer-lacunas --pausa 0.55
) else (
  python organizar_biblioteca_pdf.py enriquecer --refazer-lacunas --pausa 0.55
)
echo.
pause
