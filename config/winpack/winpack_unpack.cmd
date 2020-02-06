@echo off
md distrib
pushd distrib || goto :error
7z x ..\distrib.7z.exe
if "%ERRORLEVEL%"=="0" goto :unpacked
sleep 20
7z x ..\distrib.7z.exe
if "%ERRORLEVEL%"=="0" goto :unpacked
sleep 60
7z x ..\distrib.7z.exe
if "%ERRORLEVEL%"=="0" goto :unpacked
sleep 120
7z x ..\distrib.7z.exe
if "%ERRORLEVEL%"=="0" goto :unpacked
sleep 300
7z x ..\distrib.7z.exe
if "%ERRORLEVEL%"=="0" goto :unpacked

echo.Extract failed >&2
exit /B 1

:unpacked
popd || goto :error

exit /B 0

:error
echo Failed with error #%errorlevel%.
exit /B %errorlevel%
