@echo off
REM Uninstall script for MCSM-Launcher (Windows)
REM This will permanently delete the MCSM-Launcher folder in Documents and the Telltale Games folder.

setlocal
set "DOCS=%USERPROFILE%\Documents"
set "MCSM=%DOCS%\MCSM-Launcher"
set "TELLTALE=%DOCS%\Telltale Games"

:: Ask the user for confirmation via a PowerShell MessageBox (Yes/No)
powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $msg = '%MCSM%' + [System.Environment]::NewLine + '%TELLTALE%' + [System.Environment]::NewLine + [System.Environment]::NewLine + 'This will permanently delete the above folders and ALL files inside (including saves). Back up any saves you want to keep. Continue?'; $r = [System.Windows.Forms.MessageBox]::Show($msg,'Uninstall MCSM-Launcher',[System.Windows.Forms.MessageBoxButtons]::YesNo,[System.Windows.Forms.MessageBoxIcon]::Warning); if ($r -ne [System.Windows.Forms.DialogResult]::Yes) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo Uninstall cancelled by user.
    pause
    exit /b 1
)

REM Proceed to delete the folders (PowerShell handles recursion/force)
powershell -NoProfile -Command "try { Remove-Item -LiteralPath '%MCSM%' -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '%TELLTALE%' -Recurse -Force -ErrorAction SilentlyContinue; $msg2 = 'Uninstall complete. The selected folders have been deleted.'; [System.Windows.Forms.MessageBox]::Show($msg2,'Uninstall', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) } catch { $err = $_.Exception.Message; [System.Windows.Forms.MessageBox]::Show('Uninstall encountered an error: ' + $err,'Uninstall', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error); exit 1 }"

echo.
echo Done.
echo You can delete the uninstall.bat and launcher.exe files if you want.
echo.
pause
endlocal
