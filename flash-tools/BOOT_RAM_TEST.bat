@echo off
setlocal
cd /d "%~dp0"
title Samsung Galaxy S20+ - RAM-Boot Test (Fluechtig)
color 0b

echo =======================================================================
echo      SAMSUNG GALAXY S20+ (SM-G985F / y2slte) - RAM-BOOT TEST
echo      (100%% FLUECHTIGER TEST AUS DEM ARBEITSSPEICHER - KEIN FLASH)
echo =======================================================================
echo.
echo Dieses Skript sendet das Boot-Image temporaer in den Arbeitsspeicher.
echo Es werden KEINE Partitionen ueberschrieben oder dauerhaft veraendert.
echo.
set "IMAGE=..\imagesoot_community.img"
if not exist "%IMAGE%" set "IMAGE=boot_community.img"

if not exist "%IMAGE%" (
    echo [-] FEHLER: Boot-Image nicht gefunden: %IMAGE%
    pause
    exit /b 1
)

echo Image: %IMAGE%
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
echo [*] Sende Boot-Image in den RAM (fastboot boot)...
echo.
fastboot.exe boot "%IMAGE%"

if errorlevel 1 (
    echo.
    echo [-] FEHLER: fastboot boot fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo [+] IMAGE ERFOLGREICH IN DEN RAM GESENDET!
echo.
echo Das Handy startet jetzt in Linux:
echo 1. USB-Ethernet: Verbinde per USB-C. IP des Handys ist 10.42.0.2
echo 2. Web-Dashboard: Oeffne http://10.42.0.2 im Browser
echo 3. Web-Terminal:  Oeffne http://10.42.0.2:7681 (Port 7681)
echo 4. SSH-Zugang:    ssh root@10.42.0.2 (Kein Passwort erforderlich)
echo 5. WLAN verbinden: Im Terminal 'wifi-connect <SSID> <Passwort>' ausfuehren
echo.
pause
