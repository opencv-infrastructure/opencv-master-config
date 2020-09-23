@echo off
cls

7z x -y -oconfiguration_packs metapack.7z || (sleep 20 && 7z x -y -oconfiguration_packs metapack.7z || goto :error)
md distrib\opencv\build
pushd configuration_packs || goto :error
for %%x in (*) do (
    IF NOT %%~zx==0 (
        7z x -y -o..\distrib\opencv\build %%x || ( echo.Extract failed >&2 && exit /B 1 )
    ) ELSE (
        echo.%%x is EMPTY >&2
    )
)
popd || goto :error

:PACK
rm distrib.7z 2>nul
pushd distrib || goto :error
mklink /J opencv\sources ..\..\opencv

unix2dos -n opencv\sources\3rdparty\ffmpeg\license.txt opencv\LICENSE_FFMPEG.txt
unix2dos -n opencv\build\LICENSE opencv\LICENSE.txt
unix2dos -n opencv\sources\README.md opencv\README.md.txt

7z a -sfx..\7z_opencv.sfx -bd -t7z -y -mx9 -xr!.git* ..\distrib.7z.exe .\
popd || goto :error

exit /B 0

:error
echo Failed with error #%errorlevel%.
exit /B %errorlevel%
