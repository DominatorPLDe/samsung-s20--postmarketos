@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Samsung Galaxy S20+ - Permanenter Flash
color 0e

echo =======================================================================
echo      SAMSUNG GALAXY S20+ (SM-G985F / y2slte) - PERMANENTER FLASH
echo      (DAUERHAFTE INSTALLATION AUF DIE INTERNE BOOT-PARTITION)
echo =======================================================================
echo.
echo WARNUNG: Dieses Skript flasht das Boot-Image dauerhaft auf die
echo interne Boot-Partition (/dev/sda33) des Geraets.
echo.
echo Voraussetzung: lk3rd Bootloader muss auf dem Geraet installiert sein.
echo lk3rd (/dev/sda13) bleibt voellig unberuehrt.
echo.

set "IMAGE=%~dp0..\images\boot_community.img"
if not exist "%IMAGE%" set "IMAGE=%~dp0boot_community.img"
if not exist "%IMAGE%" set "IMAGE=%~dp0..\boot_community.img"
if not exist "%IMAGE%" set "IMAGE=%~dp0..\boot.img"
if not exist "%IMAGE%" set "IMAGE=%~dp0..\boot_PRODUCTION_FLASH.img"

if not exist "%IMAGE%" (
    echo [-] FEHLER: Boot-Image nicht gefunden!
    echo     Gepruefte Pfade:
    echo     - %~dp0..\images\boot_community.img
    echo     - %~dp0boot_community.img
    echo     - %~dp0..\boot_community.img
    echo     - %~dp0..\boot.img
    echo.
    pause
    exit /b 1
)

echo [+] Verwende Image: %IMAGE%
echo.
set /p CONFIRM="Moechtest du jetzt dauerhaft flashen? (J/N): "
if /i not "%CONFIRM%"=="J" (
    echo.
    echo [*] Vorgang durch Benutzer abgebrochen.
    pause
    exit /b 0
)

echo.
echo Warte auf Fastboot-Geraet am USB-Port...
echo (Halte am ausgeschalteten Handy LEISER gedrueckt und schliesse das USB-Kabel an)
echo.

:wait_device
fastboot.exe devices 2>nul | findstr /i "fastboot" >nul
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_device
)

echo [+] Fastboot-Geraet erkannt!
echo [*] Flasht Boot-Partition in einem Stueck (fastboot flash boot)...
echo.
fastboot.exe flash boot "%IMAGE%"

if errorlevel 1 (
    echo.
    echo [-] FEHLER: Flash-Vorgang fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo [+] FLASH ERFOLGREICH ABGESCHLOSSEN!
echo [*] Starte das Geraet neu (fastboot reboot)...
echo.
fastboot.exe reboot

echo.
echo =======================================================================
echo Das Galaxy S20+ startet jetzt selbstaendig vom internen Speicher!
echo Kuenftig bootet das Handy bei jedem Einschalten oder Stromausfall
echo vollkommen autark ohne PC und ohne Kabel direkt in Linux.
echo.
echo Erstkontakt ueber USB-C-Kabel:
echo - Dashboard:    http://10.42.0.2
echo - Web-Terminal: http://10.42.0.2:7681
echo - SSH:          ssh root@10.42.0.2
echo.
echo Nach Verbindung per Terminal:
echo 'wifi-connect <SSID> <Passwort>' speichert dein WLAN dauerhaft ab.
echo =======================================================================
echo.
pause
