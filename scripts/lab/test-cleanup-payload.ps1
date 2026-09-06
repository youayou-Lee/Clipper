# cleanup-payload.ps1 的配套测试(Issue #50 同步测试载体)。
# 在目标机(you-win)上实机运行:构造真载荷/误杀对照/持久化产物,断言脚本行为。
# 用法: powershell -NoProfile -File scripts\lab\test-cleanup-payload.ps1
# 退出码 0 = 全部通过。测试自清理,不留痕。
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$cleanup = Join-Path $PSScriptRoot 'cleanup-payload.ps1'
$results = @()

function Assert($name, $cond) {
    $script:results += @{ name = $name; ok = [bool]$cond }
    if ($cond) { Write-Output ("PASS  {0}" -f $name) } else { Write-Output ("FAIL  {0}" -f $name) }
}

function Get-PayloadCount {
    return (Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '-m\s+clipper\s+watch' -and $_.ProcessId -ne $PID
    } | Measure-Object).Count
}

# 用例 1:真载荷定位与清理
Start-Process -FilePath (Join-Path $repo '.venv\Scripts\pythonw.exe') -ArgumentList '-m','clipper','watch' -WorkingDirectory $repo
Start-Sleep 2
Assert "真载荷已启动(前置)" ((Get-PayloadCount) -ge 1)
$out = & $cleanup 2>&1 | Out-String
Assert "dry-run 定位到载荷" ($out -match '载荷进程')
Assert "dry-run 未杀进程" ((Get-PayloadCount) -ge 1)
$out = & $cleanup -Kill 2>&1 | Out-String
Start-Sleep 1
Assert "-Kill 后载荷清零" ((Get-PayloadCount) -eq 0)
Assert "-Kill 输出已终止" ($out -match '已终止')

# 用例 2:误杀防护——普通 python(无 clipper)不被杀
$ordinary = Start-Process -FilePath (Join-Path $repo '.venv\Scripts\python.exe') -ArgumentList '-c','import time; time.sleep(60)' -PassThru
Start-Sleep 1
& $cleanup -Kill 2>&1 | Out-Null
Start-Sleep 1
$stillAlive = Get-Process -Id $ordinary.Id -ErrorAction SilentlyContinue
Assert "普通 python 进程不被误杀" ($null -ne $stillAlive)
Stop-Process -Id $ordinary.Id -Force -ErrorAction SilentlyContinue

# 用例 3:自匹配防护——命令行含载荷特征的 cmd 不被杀,脚本自身正常完成
$decoy = Start-Process cmd -ArgumentList '/k','echo -m clipper watch' -PassThru -WindowStyle Hidden
Start-Sleep 1
$out = & $cleanup -Kill 2>&1 | Out-String
Start-Sleep 1
$decoyAlive = Get-Process -Id $decoy.Id -ErrorAction SilentlyContinue
Assert "含特征的 cmd 不被误杀(自匹配防护)" ($null -ne $decoyAlive)
Stop-Process -Id $decoy.Id -Force -ErrorAction SilentlyContinue

# 用例 4:--deep 清理持久化产物
$fakeLnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\ClipperSvc.lnk'
$ws = New-Object -ComObject WScript.Shell
$ws.CreateShortcut($fakeLnk).TargetPath = 'C:\Windows\System32\notepad.exe'
$ws.CreateShortcut($fakeLnk).Save()
schtasks /Create /TN ClipperLab /TR 'cmd /c exit' /SC ONCE /ST 23:59 /F | Out-Null
Assert "假持久化产物已布置(前置)" ((Test-Path $fakeLnk) -and ((schtasks /Query /TN ClipperLab 2>&1) -match 'ClipperLab'))
& $cleanup -Kill -Deep 2>&1 | Out-Null
Assert "--deep 删除 Startup LNK" (-not (Test-Path $fakeLnk))
Assert "--deep 删除计划任务" (-not ((schtasks /Query /TN ClipperLab 2>&1) -match 'ClipperLab'))

# 汇总
$failed = @($results | Where-Object { -not $_.ok })
Write-Output ("---- {0}/{1} 通过 ----" -f ($results.Count - $failed.Count), $results.Count)
if ($failed.Count -gt 0) { exit 1 }
exit 0
