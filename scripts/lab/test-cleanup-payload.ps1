# cleanup-payload.ps1 的配套测试(Issue #50 同步测试载体)。
# 在目标机(you-win)实机运行:构造真载荷/误杀对照/持久化产物,断言脚本行为。
# 关键约束(P3 实测):ssh 派生的 python 子进程在该机器存活不过数秒,
# 因此所有测试进程经计划任务 /IT 投射到用户交互会话启动(与真实载荷同路径)。
# 用法: powershell -NoProfile -File scripts\lab\test-cleanup-payload.ps1
# 退出码 0 = 全部通过。测试自清理。
param(
    [string]$Repo = "C:\Users\16121\Clipper"   # 实验室默认;其他机器运行时显式传入
)
$ErrorActionPreference = 'Continue'
$cleanup = Join-Path $Repo 'scripts\lab\cleanup-payload.ps1'
$results = @()
$spawnTasks = @()

function Assert($name, $cond) {
    $script:results += @{ name = $name; ok = [bool]$cond }
    if ($cond) { Write-Output ("PASS  {0}" -f $name) } else { Write-Output ("FAIL  {0}" -f $name) }
}

# 经计划任务在用户交互会话启动进程(ssh 直接启动的 python 会立即退出)
function Start-UserProcess($taskTag, $exe, $argString) {
    $tn = "CleanupTest-$taskTag"
    $tr = '"' + $exe + '" ' + $argString
    & cmd.exe /c "schtasks /Create /TN $tn /TR `"$tr`" /SC ONCE /ST 23:59 /F /IT" | Out-Null
    schtasks /Run /TN $tn | Out-Null
    $script:spawnTasks += $tn
    Start-Sleep 3
}

function Get-PayloadCount {
    return (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '-m\s+clipper\s+watch' -and $_.ProcessId -ne $PID
    } | Measure-Object).Count
}

# 用例 1:真载荷定位与清理
Start-UserProcess 'Payload' (Join-Path $Repo '.venv\Scripts\pythonw.exe') '-m clipper watch'
Assert "真载荷已启动(前置)" ((Get-PayloadCount) -ge 1)
$out = & $cleanup 2>&1 | Out-String
Assert "dry-run 定位到载荷" ($out -match '载荷进程')
Assert "dry-run 未杀进程" ((Get-PayloadCount) -ge 1)
$out = & $cleanup -Kill 2>&1 | Out-String
Start-Sleep 1
Assert "-Kill 后载荷清零" ((Get-PayloadCount) -eq 0)
Assert "-Kill 输出已终止" ($out -match '已终止')

# 用例 2:误杀防护——普通 pythonw(无 clipper 特征)不被杀
$ordinary = Start-Process -FilePath (Join-Path $Repo '.venv\Scripts\pythonw.exe') -ArgumentList '-c','import time; time.sleep(120)' -PassThru
Start-Sleep 1
& $cleanup -Kill 2>&1 | Out-Null
Start-Sleep 1
$stillAlive = Get-Process -Id $ordinary.Id -ErrorAction SilentlyContinue
Assert "普通 pythonw 进程不被误杀" ($null -ne $stillAlive)
if ($stillAlive) { Stop-Process -Id $ordinary.Id -Force -ErrorAction SilentlyContinue }

# 用例 3:自匹配防护——命令行含载荷特征的 cmd 不被杀,脚本自身正常完成
$decoy = Start-Process cmd -ArgumentList '/k','echo -m clipper watch' -PassThru -WindowStyle Hidden
Start-Sleep 1
$out = & $cleanup -Kill 2>&1 | Out-String
Start-Sleep 1
$decoyAlive = Get-Process -Id $decoy.Id -ErrorAction SilentlyContinue
Assert "含特征的 cmd 不被误杀(自匹配防护)" ($null -ne $decoyAlive)
if ($decoyAlive) { Stop-Process -Id $decoy.Id -Force -ErrorAction SilentlyContinue }

# 用例 4:--deep 清理持久化产物
$fakeLnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\ClipperSvc.lnk'
$ws = New-Object -ComObject WScript.Shell
$ws.CreateShortcut($fakeLnk).TargetPath = 'C:\Windows\System32\notepad.exe'
$ws.CreateShortcut($fakeLnk).Save()
& cmd.exe /c "schtasks /Create /TN ClipperLab /TR 'cmd /c exit' /SC ONCE /ST 23:59 /F"
Assert "假持久化产物已布置(前置)" ((Test-Path $fakeLnk) -and ($LASTEXITCODE -eq 0))
& $cleanup -Kill -Deep 2>&1 | Out-Null
Assert "--deep 删除 Startup LNK" (-not (Test-Path $fakeLnk))
& cmd.exe /c "schtasks /Query /TN ClipperLab 2>nul" | Out-Null
Assert "--deep 删除计划任务" ($LASTEXITCODE -ne 0)

# 收尾:清理本测试创建的计划任务
foreach ($tn in $spawnTasks) {
    & cmd.exe /c "schtasks /Delete /TN $tn /F 2>nul" | Out-Null
}

$failed = @($results | Where-Object { -not $_.ok })
Write-Output ("---- {0}/{1} 通过 ----" -f ($results.Count - $failed.Count), $results.Count)
if ($failed.Count -gt 0) { exit 1 }
exit 0
