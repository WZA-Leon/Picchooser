# bootstrap_runtime.ps1
# 为 Picchooser 准备轻量运行环境：下载 Python 嵌入式运行时 + pip 安装依赖。
# 相比 PyInstaller 单文件打包，体积更小，且运行时自带 Tkinter（GUI 需要）。
$ErrorActionPreference = 'Stop'
$WORK_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$RUNTIME = Join-Path $WORK_DIR 'runtime'
$PY_ZIP = Join-Path $RUNTIME 'python_embed.zip'
# Picchooser 运行依赖：exifread（主程序）+ Pillow（精细筛片 GUI）
$PACKAGES = @('exifread', 'pillow')
$MIRRORS = @('https://mirrors.aliyun.com/pypi/simple', 'https://pypi.tuna.tsinghua.edu.cn/simple', 'https://mirrors.ustc.edu.cn/pypi/web/simple')

# 自动测速选最快镜像源
function Select-FastestMirror {
    param([string[]]$Mirrors)
    $results = @()
    foreach ($m in $Mirrors) {
        try {
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $testUrl = $m.TrimEnd('/') + '/pip/'
            $resp = Invoke-WebRequest -Uri $testUrl -UseBasicParsing -TimeoutSec 10
            $sw.Stop()
            $speed = if ($resp.RawContentLength -gt 0) { $resp.RawContentLength / $sw.Elapsed.TotalSeconds } else { 0 }
            Write-Host ("测速 {0}  ->  {1:N0} KB/s" -f $m, ($speed / 1KB))
            $results += [PSCustomObject]@{ Url = $m; Speed = $speed }
        } catch {
            Write-Host ("测速 {0}  ->  不可用" -f $m)
        }
    }
    if ($results.Count -eq 0) { return $Mirrors }
    return ($results | Sort-Object Speed -Descending | ForEach-Object { $_.Url })
}
Write-Host '正在测速选择最快镜像源...'
$MIRRORS = @(Select-FastestMirror $MIRRORS)
Write-Host ("最快镜像源: {0}" -f $MIRRORS[0])

$pyExe = Join-Path $RUNTIME 'python.exe'
if (-not (Test-Path $pyExe)) {
    Write-Host 'Step 1: 下载 Python 嵌入式运行时 (国内镜像)'
    New-Item -ItemType Directory -Force -Path $RUNTIME | Out-Null
    $pyUrls = @('https://mirrors.huaweicloud.com/python/3.11.9/python-3.11.9-embed-amd64.zip', 'https://registry.npmmirror.com/-/binary/python/3.11.9/python-3.11.9-embed-amd64.zip', 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip')
    $downloaded = $false
    foreach ($url in $pyUrls) {
        try { Write-Host "尝试下载: $url"; Invoke-WebRequest -Uri $url -OutFile $PY_ZIP -UseBasicParsing -TimeoutSec 300; $downloaded = $true; break } catch { Write-Host '下载失败，尝试下一个源...' }
    }
    if (-not $downloaded) { Write-Host 'ERROR: Python 下载失败'; Read-Host '按回车退出'; exit 1 }
    Write-Host 'Step 2: 解压 Python'
    Expand-Archive -Path $PY_ZIP -DestinationPath $RUNTIME -Force
    Remove-Item $PY_ZIP -Force
    Write-Host 'Step 3: 启用 site 模块'
    $pth = Join-Path $RUNTIME 'python311._pth'
    if (Test-Path $pth) { (Get-Content $pth) -replace '#import site', 'import site' | Set-Content $pth }
    Write-Host 'Step 4: 安装 pip 并升级'
    $gp = Join-Path $RUNTIME 'get-pip.py'
    foreach ($url in @('https://mirrors.aliyun.com/pypi/get-pip.py', 'https://bootstrap.pypa.io/get-pip.py')) { try { Invoke-WebRequest -Uri $url -OutFile $gp -UseBasicParsing; break } catch { } }
    if (Test-Path $gp) { & $pyExe $gp --no-setuptools --no-wheel -i $MIRRORS[0]; Remove-Item $gp -Force }
    & $pyExe -m pip install --upgrade pip -i $MIRRORS[0]
}

Write-Host '检查并安装依赖包:'
Write-Host $PACKAGES
$installed = $false
try { & $pyExe -c "import exifread, PIL" 2>$null; if ($LASTEXITCODE -eq 0) { $installed = $true } } catch { }
if (-not $installed) {
    Write-Host '部分包缺失，开始安装...'
    $ok = $false
    foreach ($mirror in $MIRRORS) { Write-Host "尝试镜像: $mirror"; & $pyExe -m pip install $PACKAGES -i $mirror --progress-bar on; if ($LASTEXITCODE -eq 0) { $ok = $true; break } }
    if (-not $ok) { Write-Host 'WARNING: 依赖安装失败，请手动执行:'; Write-Host "$pyExe -m pip install $PACKAGES"; Read-Host '按回车退出'; exit 1 }
} else { Write-Host '所有依赖包已安装。' }

# 配置 tkinter
# 嵌入式运行时本身不含 Tcl/Tk，本项目的 runtime 目录已随包附带提取好的
# tkinter 组件（_tkinter.pyd、tcl86t.dll、tk86t.dll、tcl/、tkinter/），
# 这里只需设置 Tcl/Tk 库路径并验证可用性。
Write-Host '配置 tkinter...'
$env:TCL_LIBRARY = Join-Path $RUNTIME 'tcl\tcl8.6'
$env:TK_LIBRARY = Join-Path $RUNTIME 'tcl\tk8.6'
try { & $pyExe -c "import tkinter" 2>$null; if ($LASTEXITCODE -ne 0) { throw 'tkinter import failed' } } catch { Write-Host 'tkinter 配置失败'; Read-Host '按回车退出'; exit 1 }
Write-Host '所有依赖安装并配置成功。'
Write-Host '正在启动程序: Picchooser.py'
# 设置 tkinter 所需环境变量后启动 GUI
$env:TCL_LIBRARY = Join-Path $RUNTIME 'tcl\tcl8.6'
$env:TK_LIBRARY = Join-Path $RUNTIME 'tcl\tk8.6'
Start-Process -FilePath $pyExe -ArgumentList (Join-Path $WORK_DIR 'Picchooser.py') -WorkingDirectory $WORK_DIR
Write-Host '程序已启动，本窗口可关闭。'
Start-Sleep -Seconds 3
