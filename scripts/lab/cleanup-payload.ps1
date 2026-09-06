# 实验室载荷清理脚本(Issue #50)。
# 只识别并清理本仓库自己的 clipper 载荷(python/pythonw + '-m clipper watch')。
# 默认 dry-run 仅列出;-Kill 执行进程清理;-Deep 额外清理持久化产物(需与 -Kill 同用)。
# 定位特征与载荷形态同步维护:载荷新增隐蔽/持久化形态时,必须同 PR 更新 $MatchName/
# $MatchCmd/$PersistTasks/$PersistFiles 并补 test-cleanup-payload.ps1 同步用例(见 #50)。
param(
    [switch]$Kill,
    [switch]$Deep
)
# 原生命令的 stderr 不作为终止错误(schtasks 查询不存在的任务会写 stderr)
$ErrorActionPreference = 'Continue'

# --- 定位特征(同步维护区) ---
$MatchName = '^python(w)?\.exe$'                 # 只匹配 python/pythonw,根除查询命令自匹配
$MatchCmd  = '-m\s+clipper\s+watch'              # 载荷命令行特征
# 持久化产物清单(--deep 清理;载荷新增持久化形态时同步维护)
$PersistFiles = @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\ClipperSvc.lnk')
)
$PersistTasks = @('ClipperLab', 'ClipperScan', 'ClipperSet', )
# -------------------------------

$found = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $PID -and
    $_.Name -match $MatchName -and
    $_.CommandLine -match $MatchCmd
}

if (-not $found) {
    Write-Output "[cleanup] 未发现载荷进程"
} else {
    foreach ($p in $found) {
        Write-Output ("[cleanup] 载荷进程 PID={0} Name={1}" -f $p.ProcessId, $p.Name)
        Write-Output ("           CommandLine: {0}" -f $p.CommandLine)
        if ($Kill) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
                Write-Output ("           → 已终止")
            } catch {
                Write-Output ("           → 终止失败: {0}" -f $_.Exception.Message)
            }
        }
    }
}
if (-not $Kill) { Write-Output "[cleanup] (dry-run,未做任何变更;加 -Kill 执行)" }

if ($Deep) {
    if (-not $Kill) {
        Write-Output "[cleanup] -Deep 需要 -Kill,本次跳过持久化清理"
    } else {
        foreach ($f in $PersistFiles) {
            if (Test-Path $f) {
                Remove-Item $f -Force
                Write-Output "[cleanup] 已删除持久化文件: $f"
            } else {
                Write-Output "[cleanup] 持久化文件不存在: $f"
            }
        }
        foreach ($t in $PersistTasks) {
            & cmd.exe /c "schtasks /Query /TN $t 2>nul" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                schtasks /Delete /TN $t /F | Out-Null
                Write-Output "[cleanup] 已删除计划任务: $t"
            } else {
                Write-Output "[cleanup] 计划任务不存在: $t"
            }
        }
    }
}
exit 0
