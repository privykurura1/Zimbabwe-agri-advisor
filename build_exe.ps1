# Murimi Fara 2.0 - build the small one-click Windows app (no AI model)
#
# Run from the project folder, in PowerShell:
#     .\build_exe.ps1
#
# What it does:
#   1. runs the tests (stops if any fail)
#   2. checks the farm book and Murimi Fara's own model are there
#   3. closes any running copy of the app, so Windows doesn't lock the files
#   4. builds dist\MurimiFara\MurimiFara.exe with PyInstaller, from a clean
#      'buildenv' that holds ONLY what the app needs (keeps it small)
#   5. copies in the files the exe needs beside it
#   6. checks the finished folder, runs a self-test, and checks the size
#      (target: under 50 MB)
#
# Result: the whole folder dist\MurimiFara is the app. Copy that folder (or
# build the installer from it) - the .exe alone will not work.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Dist      = "dist\MurimiFara"
$TargetMB  = 50

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nBUILD STOPPED: $text" -ForegroundColor Red; exit 1 }

# ---- 0. Python environment ----
Step "Using the project's Python environment"
if (Test-Path ".\venv\Scripts\Activate.ps1") { . .\venv\Scripts\Activate.ps1 }
else { Fail "venv not found in $PWD" }

# ---- 1. Tests ----
Step "Running the tests"
python test_rag_gate.py | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { Fail "test_rag_gate.py failed - fix before building" }
python -m unittest test_core
if ($LASTEXITCODE -ne 0) { Fail "test_core failed - fix before building" }
python -m unittest discover -s challenge_agent/tests -t .
if ($LASTEXITCODE -ne 0) { Fail "officer review tests failed - fix before building" }

# ---- 2. Knowledge and model ----
Step "Checking the farm book and Murimi Fara's model"
$entries = python -c "import rag; print(len(rag.load_chunks(rag.CORPUS_PATH)))"
Write-Host "corpus_livestock_crops.md has $entries entries"
if ($entries -ne "55") {
    Write-Host "WARNING: expected 55 entries. If you added entries on purpose, ignore this." -ForegroundColor Yellow
    $answer = Read-Host "Continue anyway? (y/n)"
    if ($answer -ne "y") { Fail "wrong farm book file" }
}
if (-not (Test-Path "models\murimi_model.json")) {
    Fail "models\murimi_model.json missing - run: python tools\train_model.py --seed"
}
python -c "import matcher; m = matcher.load('models/murimi_model.json'); print('model version', m.info.get('version'), '-', len(m.examples), 'examples')"
foreach ($f in @("desktop_app.py", "app.py", "advisor.py", "matcher.py", "tinytfidf.py", "rag.py", "index.html",
                 "corpus_livestock_crops.md", "murimifara.ico", "murimifara.png", "challenge_agent\review_app.py",
                 "murimi_plus\router.py")) {
    if (-not (Test-Path $f)) { Fail "missing $f" }
}
if (-not (Test-Path "vendor")) { Fail "missing the vendor folder (React files for the page)" }

# ---- 3. Close running copies ----
Step "Closing any running copy of the app"
Get-Process MurimiFara, llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# ---- 4. Build ----
Step "Preparing a clean build environment (buildenv)"
# PyInstaller packs whatever it finds, so the app is built from a separate
# environment with ONLY the libraries Murimi Fara 2.0 uses. A buildenv left over
# from version 1 (with OpenCV, scikit-learn, LangGraph...) is replaced.
$BuildPython = ".\buildenv\Scripts\python.exe"
$Needed = @("fastapi", "uvicorn", "python-multipart", "pywebview", "pyinstaller")
if (Test-Path $BuildPython) {
    & $BuildPython -c "import cv2" 2>$null
    $hasOld = ($LASTEXITCODE -eq 0)
    & $BuildPython -c "import sklearn" 2>$null
    if ($hasOld -or $LASTEXITCODE -eq 0) {
        Write-Host "Old version-1 buildenv found (OpenCV / scikit-learn) - making a new one..."
        Remove-Item -Recurse -Force buildenv
    }
}
if (-not (Test-Path $BuildPython)) {
    Write-Host "Creating buildenv (needs internet once)..."
    python -m venv buildenv
    if ($LASTEXITCODE -ne 0) { Fail "could not create buildenv" }
    & $BuildPython -m pip install --upgrade pip
    & $BuildPython -m pip install @Needed
    if ($LASTEXITCODE -ne 0) { Fail "could not install the build libraries into buildenv" }
}
& $BuildPython -c "import fastapi, uvicorn, multipart, webview, PyInstaller; print('buildenv OK')"
if ($LASTEXITCODE -ne 0) {
    & $BuildPython -m pip install @Needed
    & $BuildPython -c "import fastapi, uvicorn, multipart, webview, PyInstaller"
    if ($LASTEXITCODE -ne 0) { Fail "buildenv incomplete - delete the buildenv folder and run again" }
}

Step "Building with PyInstaller"
# Second safety net: never pack these, even if something installs them into buildenv.
$Exclude = @("torch", "tensorflow", "numpy", "scipy", "sklearn", "cv2", "pandas", "pyarrow", "matplotlib",
             "langgraph", "langchain_core", "langsmith", "mcp", "httpx", "llama_cpp", "IPython",
             "jupyter", "notebook", "tkinter") |
           ForEach-Object { "--exclude-module=$_" }
& $BuildPython -m PyInstaller --onedir --noconsole --noconfirm --icon=murimifara.ico `
    --hidden-import multipart --hidden-import multipart.multipart `
    --hidden-import murimi_plus.router --hidden-import challenge_agent.tools `
    --hidden-import challenge_agent.review_app `
    @Exclude --name MurimiFara desktop_app.py
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed - see the messages above" }

# ---- 5. Copy what the exe needs beside it ----
Step "Copying the app's files into $Dist"
Copy-Item index.html, corpus_livestock_crops.md, murimifara.png, murimifara.ico -Destination $Dist -Force
Copy-Item vendor -Destination $Dist -Recurse -Force
foreach ($sub in @("data", "audio", "models")) {
    if (Test-Path $sub) { Copy-Item $sub -Destination $Dist -Recurse -Force }
}
# Left over from version 1 builds: never ship them.
foreach ($old in @("llama", "model", "faw_classifier.onnx", "models\photo")) {
    $p = Join-Path $Dist $old
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}

# ---- 6. Check the finished folder ----
Step "Checking the finished app folder"
foreach ($f in @("MurimiFara.exe", "index.html", "corpus_livestock_crops.md", "models\murimi_model.json", "vendor")) {
    if (-not (Test-Path (Join-Path $Dist $f))) { Fail "$f is missing from $Dist" }
}

Step "Self-test: one farmer answer and one officer draft, in the built app"
$selftest = Join-Path ($env:LOCALAPPDATA + "\MurimiFara") "murimifara_selftest.txt"
Remove-Item $selftest -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "$Dist\MurimiFara.exe" -ArgumentList "--officer-selftest" -PassThru
if (-not $p.WaitForExit(60000)) { $p.Kill(); Fail "self-test timed out" }
if (-not (Test-Path $selftest)) { Fail "self-test wrote no result (expected $selftest)" }
$result = Get-Content $selftest -Raw
if (-not $result.StartsWith("OK")) { Fail "the built app does not work:`n$result" }
Write-Host "The built app answers questions and drafts for officers." -ForegroundColor Green

$sizeMB = [math]::Round((Get-ChildItem $Dist -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "`nBUILD DONE" -ForegroundColor Green
Write-Host "App folder : $PWD\$Dist  ($sizeMB MB)"
if ($sizeMB -gt $TargetMB) {
    Write-Host "WARNING: bigger than the $TargetMB MB target. Look in $Dist\_internal for large folders" -ForegroundColor Yellow
}
Write-Host "Start it   : $PWD\$Dist\MurimiFara.exe"
Write-Host "Web only   : $PWD\$Dist\MurimiFara.exe --server   (phones/computers open http://<this computer>:8000)"
Write-Host "If it does not open, look in $env:LOCALAPPDATA\MurimiFara\murimifara_error.log"