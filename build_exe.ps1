# Murimi Fara - build the one-click Windows app
#
# Run from the project folder, in PowerShell:
#     .\build_exe.ps1
#
# What it does:
#   1. runs the two quick tests (stops if either fails)
#   2. checks the knowledge base has 55 entries (the old 18-entry file was
#      once bundled by mistake)
#   3. closes any running copy of the app, so Windows doesn't lock the files
#   4. builds dist\MurimiFara\MurimiFara.exe with PyInstaller, from a clean
#      'buildenv' that holds only the libraries the app uses (keeps it small)
#   5. copies in everything the exe needs beside it (corpus, page, model,
#      llama-server, photo model)
#   6. checks the finished folder
#
# Result: the whole folder dist\MurimiFara is the app. Copy that folder (or
# build the installer from it) - the .exe alone will not work.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$LlamaSource = "C:\llama.cpp"          # where your working llama-server.exe is
$ModelFile   = "model\qwen2.5-1.5b-instruct-q4_k_m.gguf"
$Dist        = "dist\MurimiFara"

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nBUILD STOPPED: $text" -ForegroundColor Red; exit 1 }

# ---- 0. Python environment ----
Step "Using the project's Python environment"
if (Test-Path ".\venv\Scripts\Activate.ps1") { . .\venv\Scripts\Activate.ps1 }
else { Fail "venv not found in $PWD" }
python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not installed - installing it now..."
    pip install pyinstaller pywebview
    if ($LASTEXITCODE -ne 0) { Fail "could not install PyInstaller" }
}

# ---- 1. Tests ----
Step "Running the quick tests"
python test_output_guard.py
if ($LASTEXITCODE -ne 0) { Fail "test_output_guard.py failed - fix before building" }
python test_rag_gate.py | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { Fail "test_rag_gate.py failed - fix before building" }

# ---- 2. Knowledge base ----
Step "Checking the knowledge base"
$entries = python -c "import rag; print(len(rag.load_chunks(rag.CORPUS_PATH)))"
Write-Host "corpus_livestock_crops.md has $entries entries"
if ($entries -ne "55") {
    Write-Host "WARNING: expected 55 entries. If you added entries on purpose, ignore this." -ForegroundColor Yellow
    $answer = Read-Host "Continue anyway? (y/n)"
    if ($answer -ne "y") { Fail "wrong knowledge base file" }
}

# ---- 3. Files the app needs ----
Step "Checking the files the app needs"
foreach ($f in @("desktop_app.py", "app.py", "rag.py", "index.html", "corpus_livestock_crops.md",
                 "murimifara.ico", $ModelFile, "challenge_agent\server.py", "murimi_plus\router.py")) {
    if (-not (Test-Path $f)) { Fail "missing $f" }
}
if (-not (Test-Path "vendor")) { Fail "missing the vendor folder (React files for the page)" }
$HasPhotoModel = Test-Path "faw_classifier.onnx"
if (-not $HasPhotoModel) {
    Write-Host "WARNING: faw_classifier.onnx not found - the photo check will be off in this build." -ForegroundColor Yellow
}
$LlamaHere = Test-Path ".\llama\llama-server.exe"
if (-not $LlamaHere -and -not (Test-Path "$LlamaSource\llama-server.exe")) {
    Fail "llama-server.exe not found in .\llama or $LlamaSource"
}

# ---- 4. Close running copies ----
Step "Closing any running copy of the app"
Get-Process MurimiFara, llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# ---- 5. Build ----
Step "Preparing a clean build environment (buildenv)"
# The everyday venv also holds big libraries the app never uses (torch,
# pyarrow, huggingface...). PyInstaller packs whatever it can find, which
# added ~400 MB (torch_cpu.dll alone was 292 MB). So the app is built from a
# separate environment with ONLY what app.py, rag.py and desktop_app.py import.
$BuildPython = ".\buildenv\Scripts\python.exe"
$Needed = @("fastapi", "uvicorn", "python-multipart", "scikit-learn", "numpy",
            "opencv-python-headless", "pywebview", "pyinstaller",
            # Officer review (MCP agent)
            "mcp==1.29.0", "langgraph==1.2.15", "httpx")
if (-not (Test-Path $BuildPython)) {
    Write-Host "Creating buildenv (first time only, needs internet)..."
    python -m venv buildenv
    if ($LASTEXITCODE -ne 0) { Fail "could not create buildenv" }
    & $BuildPython -m pip install --upgrade pip
    & $BuildPython -m pip install @Needed
    if ($LASTEXITCODE -ne 0) { Fail "could not install the build libraries into buildenv" }
}
& $BuildPython -c "import fastapi, uvicorn, multipart, sklearn, numpy, cv2, webview, PyInstaller, mcp, langgraph, httpx; print('buildenv OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "buildenv is incomplete - installing the missing libraries..."
    & $BuildPython -m pip install @Needed
    & $BuildPython -c "import fastapi, uvicorn, multipart, sklearn, numpy, cv2, webview, PyInstaller, mcp, langgraph, httpx"
    if ($LASTEXITCODE -ne 0) { Fail "buildenv still incomplete - delete the buildenv folder and run again" }
}

Step "Building with PyInstaller (takes a few minutes)"
# The exclude list is a second safety net, in case one of these ever gets
# installed into buildenv as a side effect.
$Exclude = @("torch", "torchvision", "torchaudio", "tensorflow", "pyarrow", "pandas", "datasets",
             "transformers", "huggingface_hub", "hf_xet", "matplotlib", "IPython", "jupyter",
             "notebook", "onnx", "onnxscript", "llama_cpp", "tkinter") |
           ForEach-Object { "--exclude-module=$_" }
& $BuildPython -m PyInstaller --onedir --noconsole --noconfirm --icon=murimifara.ico `
    --collect-all cv2 --hidden-import multipart --hidden-import multipart.multipart `
    --hidden-import murimi_plus.router --hidden-import murimi_plus.hardware `
    --hidden-import challenge_agent.server --hidden-import challenge_agent.review_app `
    --hidden-import mcp.server.fastmcp --hidden-import mcp.client.stdio --collect-submodules langgraph `
    @Exclude --name MurimiFara desktop_app.py
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed - see the messages above" }

# ---- 6. Copy what the exe needs beside it ----
Step "Copying the app's files into $Dist"
Copy-Item index.html, rag.py, corpus_livestock_crops.md -Destination $Dist -Force
if ($HasPhotoModel) { Copy-Item faw_classifier.onnx -Destination $Dist -Force }
Copy-Item vendor -Destination $Dist -Recurse -Force
# Extras (murimi_plus): hand-edited data, recorded audio, extra photo checks.
foreach ($sub in @("data", "audio", "models")) {
    if (Test-Path $sub) { Copy-Item $sub -Destination $Dist -Recurse -Force }
}
# Pictures the page uses (logo etc.). The page is served by the app, so any
# image index.html refers to must sit in the app folder.
Get-ChildItem -File -Include *.png, *.jpg, *.jpeg, *.svg, *.gif, *.webp, *.ico -Path .\* |
    Copy-Item -Destination $Dist -Force
foreach ($sub in @("images", "img", "assets", "static")) {
    if (Test-Path $sub) { Copy-Item $sub -Destination $Dist -Recurse -Force }
}

New-Item -ItemType Directory -Force "$Dist\llama" | Out-Null
if ($LlamaHere) {
    Copy-Item ".\llama\*" -Destination "$Dist\llama" -Recurse -Force
} else {
    # Only the server and its DLLs - not every llama.cpp tool.
    Copy-Item "$LlamaSource\llama-server.exe" -Destination "$Dist\llama" -Force
    Copy-Item "$LlamaSource\*.dll" -Destination "$Dist\llama" -Force
}

New-Item -ItemType Directory -Force "$Dist\model" | Out-Null
$target = Join-Path $Dist $ModelFile
if (-not (Test-Path $target) -or (Get-Item $target).Length -ne (Get-Item $ModelFile).Length) {
    Write-Host "Copying the model (about 1 GB)..."
    Copy-Item $ModelFile -Destination "$Dist\model" -Force
} else {
    Write-Host "Model already in place - not copied again."
}

# OpenCV's video plugin (~29 MB): the app only reads still photos, which
# don't use it. If the photo check ever fails, delete this block and rebuild.
Get-ChildItem $Dist -Recurse -Filter "opencv_videoio_ffmpeg*.dll" | Remove-Item -Force

# ---- 7. Check the finished folder ----
Step "Checking the finished app folder"
$distEntries = python -c "import rag; print(len(rag.load_chunks(r'$Dist\corpus_livestock_crops.md')))"
foreach ($f in @("MurimiFara.exe", "index.html", "corpus_livestock_crops.md", "llama\llama-server.exe",
                 $ModelFile, "vendor")) {
    if (-not (Test-Path (Join-Path $Dist $f))) { Fail "$f is missing from $Dist" }
}
$pageImages = Select-String -Path index.html -Pattern '[\w./-]+\.(png|jpg|jpeg|svg|gif|webp)' -AllMatches |
    ForEach-Object { $_.Matches.Value } | Sort-Object -Unique
foreach ($img in $pageImages) {
    if ($img -match '^(https?:|data:)') { continue }
    if (-not (Test-Path (Join-Path $Dist $img.TrimStart('/', '.')))) {
        Write-Host "WARNING: index.html uses $img but it is not in $Dist" -ForegroundColor Yellow
    }
}
if ($distEntries -ne $entries) { Fail "the app folder has $distEntries entries, the project has $entries" }

# Officer review: the agent starts its MCP server as "MurimiFara.exe --mcp-server".
# Prove that works in this build by drafting one advisory (no model needed).
Step "Testing officer review (MCP agent) in the built app"
$selftest = Join-Path ($env:LOCALAPPDATA + "\MurimiFara") "murimifara_selftest.txt"
Remove-Item $selftest -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "$Dist\MurimiFara.exe" -ArgumentList "--mcp-selftest" -PassThru
if (-not $p.WaitForExit(120000)) { $p.Kill(); Write-Host "WARNING: officer review self-test timed out" -ForegroundColor Yellow }
if (Test-Path $selftest) {
    $result = Get-Content $selftest -Raw
    if ($result.StartsWith("OK")) { Write-Host "Officer review works in the exe." -ForegroundColor Green }
    else { Write-Host "WARNING: officer review does not work in this build:`n$result" -ForegroundColor Yellow }
} else {
    Write-Host "WARNING: officer review self-test wrote no result (expected $selftest)" -ForegroundColor Yellow
}

$size = "{0:N1}" -f ((Get-ChildItem $Dist -Recurse | Measure-Object Length -Sum).Sum / 1GB)
Write-Host "`nBUILD DONE" -ForegroundColor Green
Write-Host "App folder : $PWD\$Dist  ($size GB)"
Write-Host "Start it   : $PWD\$Dist\MurimiFara.exe"
Write-Host "Knowledge  : $distEntries entries"
Write-Host "If it does not open, look in $env:LOCALAPPDATA\MurimiFara\murimifara_error.log"
