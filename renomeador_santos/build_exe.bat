@echo off
setlocal enabledelayedexpansion

rem Garante que os comandos rodem NESTA pasta (onde este .bat esta),
rem nao importa de onde ele foi chamado.
cd /d "%~dp0"

echo ============================================================
echo  Gerando o executavel do Renomeador de Imagens de Santos
echo ============================================================
echo  Pasta do projeto: %cd%
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    set PYTHON=py
) else (
    set PYTHON=python
)

echo Instalando as bibliotecas do programa...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo.
echo Instalando o PyInstaller (usado so para gerar o .exe)...
%PYTHON% -m pip install pyinstaller
if errorlevel 1 goto erro

echo.
echo Gerando o executavel (isso pode demorar alguns minutos)...
%PYTHON% -m PyInstaller --noconfirm --onefile --windowed ^
    --name RenomeadorDeSantos ^
    renomeador_santos.py
if errorlevel 1 goto erro

echo.
echo Copiando o executavel para esta pasta...
copy /Y "dist\RenomeadorDeSantos.exe" "RenomeadorDeSantos.exe" >nul
if errorlevel 1 goto erro

echo.
echo ============================================================
echo  Pronto! Use o arquivo RenomeadorDeSantos.exe
echo  Pode criar um atalho dele na Area de Trabalho.
echo ============================================================
pause
exit /b 0

:erro
echo.
echo Algo deu errado ao gerar o executavel. Veja a mensagem de erro acima.
echo Se for a primeira vez, confira se o Python esta instalado e se o
echo comando "python" (ou "py") funciona num terminal comum.
pause
exit /b 1
