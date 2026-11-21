@echo off
setlocal EnableExtensions
set "APK=%~1"
if "%APK%"=="" (
  echo Usage: drag an old TANG TV APK onto this BAT file.
  set /p APK=Or enter the full APK path: 
)
if not exist "%APK%" (
  echo [ERROR] APK file not found: %APK%
  pause
  exit /b 1
)
set "SIGNER="
for /d %%D in ("%LOCALAPPDATA%\Android\Sdk\build-tools\*") do (
  if exist "%%~fD\apksigner.bat" set "SIGNER=%%~fD\apksigner.bat"
  if exist "%%~fD\apksigner.exe" set "SIGNER=%%~fD\apksigner.exe"
)
if not defined SIGNER (
  echo [ERROR] Cannot find Android SDK Build Tools apksigner.
  echo Install Android SDK Build-Tools using Android Studio SDK Manager.
  pause
  exit /b 1
)
echo.
echo [INFO] APK: %APK%
echo [INFO] apksigner: %SIGNER%
echo.
"%SIGNER%" verify --print-certs "%APK%"
if errorlevel 1 (
  echo [ERROR] APK signature verification failed.
  pause
  exit /b 1
)
echo.
echo Copy the value after: Signer #1 certificate SHA-256 digest:
echo Add it to custom/config.env as EXPECTED_RELEASE_CERT_SHA256="..."
pause
