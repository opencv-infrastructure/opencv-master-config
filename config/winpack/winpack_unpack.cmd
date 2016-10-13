@echo off
md distrib
pushd distrib || goto :error
7z x ..\distrib.7z.exe || (sleep 20 && 7z x ..\distrib.7z.exe || echo.Extract failed >&2 && exit /B 1 )
popd || goto :error

exit /B 0

:error
echo Failed with error #%errorlevel%.
exit /B %errorlevel%
