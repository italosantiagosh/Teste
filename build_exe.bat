@echo off
setlocal enabledelayedexpansion

rem Garante que os comandos rodem NESTA pasta (onde este .bat esta),
rem nao importa de onde ele foi chamado (atalho, "Executar como
rem administrador" etc. podem abrir com outra pasta atual, ex.: System32).
cd /d "%~dp0"

echo ============================================================
echo  Gerando o executavel da Automacao Transportadora (Windows)
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
%PYTHON% -m pip install -r requirements-build.txt
if errorlevel 1 goto erro

echo.
echo Gerando o executavel (isso pode demorar alguns minutos)...
%PYTHON% -m PyInstaller --noconfirm --onefile --windowed ^
    --name AutomacaoTransportadora ^
    --collect-all selenium ^
    --collect-all pyautogui ^
    interface_grafica.py
if errorlevel 1 goto erro

echo.
echo Copiando o executavel para a pasta do projeto...
copy /Y "dist\AutomacaoTransportadora.exe" "AutomacaoTransportadora.exe" >nul
if errorlevel 1 goto erro

echo.
echo ============================================================
echo  Pronto! Use o arquivo AutomacaoTransportadora.exe
echo  (aqui nesta mesma pasta, ao lado de config\, entrada\,
echo  saida\, logs\ e do .env - NAO mova o .exe para outra
echo  pasta sozinho, ou ele nao vai achar essas pastas).
echo.
echo  Pode criar um atalho deste .exe na Area de Trabalho.
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
