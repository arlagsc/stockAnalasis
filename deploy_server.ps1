# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    StockAI Windows Server 一键部署与守护服务注册脚本
.DESCRIPTION
    适用于目标服务器 (172.16.9.28)，一键放行防火墙端口，
    创建并使用 NSSM 或 Windows 原生计划任务 (schtasks) 注册为开机自启常驻服务。
#>

param(
    [string]$Port = '8000',
    [string]$AuthUser = 'admin',
    [string]$AuthPass = 'StockAI@2026',
    [string]$Action = 'install'
)

$ServiceName = 'StockAIService'
$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogsDir = Join-Path $CurrentDir 'logs'
$VenvPython = Join-Path $CurrentDir '.venv\Scripts\python.exe'
$NssmExe = Join-Path $CurrentDir 'nssm.exe'
$StartBat = Join-Path $CurrentDir 'start_service.bat'

# 确保以管理员权限运行
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning '请右键选择「以管理员身份运行」执行本脚本！'
    exit 1
}

Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '[StockAI Windows 服务一键安装与运维脚本]' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ('服务名称: ' + $ServiceName)
Write-Host ('工作目录: ' + $CurrentDir)
Write-Host ('监听端口: ' + $Port + ' [公网映射: http://113.98.232.83:' + $Port + ']')
Write-Host ('安全认证: 用户名: ' + $AuthUser + ' / 密码: ' + $AuthPass)
Write-Host ('执行动作: ' + $Action)
Write-Host '--------------------------------------------------'

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

function Check-ServerRunning {
    param([string]$CheckPort)
    $conn = Get-NetTCPConnection -LocalPort $CheckPort -State Listen -ErrorAction SilentlyContinue
    return $conn
}

switch ($Action.ToLower()) {
    'firewall' {
        Write-Host ('[1/2] 正在配置 Windows 防火墙入站规则 (端口 ' + $Port + ')...') -ForegroundColor Yellow
        $existingRule = Get-NetFirewallRule -DisplayName ('StockAI Web Service ' + $Port) -ErrorAction SilentlyContinue
        if ($existingRule) {
            Remove-NetFirewallRule -DisplayName ('StockAI Web Service ' + $Port)
        }
        New-NetFirewallRule -DisplayName ('StockAI Web Service ' + $Port) -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow | Out-Null
        Write-Host ('[成功] 防火墙已成功放行 TCP ' + $Port + ' 端口！') -ForegroundColor Green
    }

    'nssm-download' {
        if (-not (Test-Path $NssmExe)) {
            Write-Host '未检测到本地 nssm.exe，尝试从镜像源下载...' -ForegroundColor Yellow
            $zipPath = Join-Path $env:TEMP 'nssm.zip'
            $nssmUrl = 'https://nssm.cc/release/nssm-2.24.zip'
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $nssmUrl -OutFile $zipPath -TimeoutSec 10 -UseBasicParsing
                Expand-Archive -Path $zipPath -DestinationPath (Join-Path $env:TEMP 'nssm_extracted') -Force
                Copy-Item (Join-Path $env:TEMP 'nssm_extracted\nssm-2.24\win64\nssm.exe') -Destination $NssmExe -Force
                Write-Host ('[成功] nssm.exe 已就绪: ' + $NssmExe) -ForegroundColor Green
            } catch {
                Write-Warning '公网下载 NSSM 超时（国外官方节点受限）。系统将自动切换为 Windows 原生任务计划引擎（无需外部文件）。'
            }
        }
    }

    'install' {
        # 1. 防火墙放行
        & $PSCommandPath -Port $Port -Action firewall

        # 2. 检查端口占用情况
        $conn = Check-ServerRunning -CheckPort $Port
        if ($conn) {
            $occupierPid = $conn[0].OwningProcess
            $procName = (Get-Process -Id $occupierPid -ErrorAction SilentlyContinue).ProcessName
            Write-Warning ('[注意] 端口 ' + $Port + ' 当前正被进程 [' + $procName + '] (PID: ' + $occupierPid + ') 监听中！')
        }

        # 3. 检查 Python 解释器
        $targetPython = 'python.exe'
        if (Test-Path $VenvPython) {
            $targetPython = $VenvPython
            Write-Host ('使用虚拟环境 Python: ' + $targetPython) -ForegroundColor Green
        } else {
            Write-Host '未找到 .venv 虚拟环境，将使用系统默认 python.exe' -ForegroundColor Yellow
        }

        # 4. 生成统一启动入口脚本 start_service.bat
        $stdoutLog = Join-Path $LogsDir 'service_stdout.log'
        $batLines = @(
            '@echo off',
            'chcp 65001 >nul',
            ('cd /d "' + $CurrentDir + '"'),
            ('"' + $targetPython + '" run_server.py --host 0.0.0.0 --port ' + $Port + ' --auth-user ' + $AuthUser + ' --auth-pass ' + $AuthPass + ' >> "' + $stdoutLog + '" 2>&1')
        )
        [System.IO.File]::WriteAllLines($StartBat, $batLines, [System.Text.Encoding]::ASCII)
        Write-Host ('已生成服务启动脚本: ' + $StartBat) -ForegroundColor Green

        # 5. 优先检测 NSSM，无 NSSM 则自动使用 Windows 原生 Task Scheduler (schtasks)
        if (-not (Test-Path $NssmExe)) {
            & $PSCommandPath -Action nssm-download
        }

        if (Test-Path $NssmExe) {
            Write-Host '>>> 采用 NSSM 服务模式进行部署...' -ForegroundColor Cyan
            & $NssmExe stop $ServiceName 2>$null | Out-Null
            & $NssmExe remove $ServiceName confirm 2>$null | Out-Null

            $runArgs = 'run_server.py --host 0.0.0.0 --port ' + $Port + ' --auth-user ' + $AuthUser + ' --auth-pass ' + $AuthPass
            & $NssmExe install $ServiceName $targetPython $runArgs
            & $NssmExe set $ServiceName AppDirectory $CurrentDir
            & $NssmExe set $ServiceName DisplayName 'StockAI Autonomous Trading Web Service'
            & $NssmExe set $ServiceName Description 'StockAI A 股自动化操盘终端 Web 接入与后台调度守护引擎'
            & $NssmExe set $ServiceName Start SERVICE_AUTO_START
            & $NssmExe set $ServiceName AppExit Default Restart
            & $NssmExe set $ServiceName AppRestartDelay 5000
            & $NssmExe set $ServiceName AppStdout $stdoutLog
            & $NssmExe set $ServiceName AppStderr (Join-Path $LogsDir 'service_stderr.log')
            & $NssmExe set $ServiceName AppRotateFiles 1
            & $NssmExe set $ServiceName AppRotateBytes 52428800

            Write-Host ('正在启动 ' + $ServiceName + ' NSSM 服务...') -ForegroundColor Yellow
            & $NssmExe start $ServiceName
        } else {
            Write-Host '>>> 采用 Windows 原生计划任务守护模式 (开机自启/系统特权/零依赖)...' -ForegroundColor Cyan
            schtasks /Delete /TN $ServiceName /F 2>$null | Out-Null
            schtasks /Create /TN $ServiceName /TR "`"$StartBat`"" /SC ONSTART /RU "SYSTEM" /RL HIGHEST /F | Out-Null
            Write-Host '[成功] 已注册 Windows 开机自启常驻任务！' -ForegroundColor Green

            # 停止可能已在运行的旧实例
            Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_server.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force 2>$null }

            Write-Host '正在启动 StockAI 后台服务进程...' -ForegroundColor Yellow
            schtasks /Run /TN $ServiceName | Out-Null
        }

        # 6. 等待服务就绪并探活
        Start-Sleep -Seconds 3
        $listen = Check-ServerRunning -CheckPort $Port
        Write-Host '==================================================' -ForegroundColor Green
        if ($listen) {
            Write-Host ('[成功] 服务已成功就绪并正在监听！PID: ' + $listen[0].OwningProcess) -ForegroundColor Green
        } else {
            Write-Host '[提示] 服务进程已启动，端口正在初始化中...' -ForegroundColor Yellow
        }
        Write-Host ('本地访问测试: http://127.0.0.1:' + $Port) -ForegroundColor Green
        Write-Host ('公网访问地址: http://113.98.232.83:' + $Port) -ForegroundColor Green
        Write-Host ('登录账号: ' + $AuthUser + ' / 密码: ' + $AuthPass) -ForegroundColor Green
        Write-Host ('日志监控文件: ' + $stdoutLog) -ForegroundColor Green
        Write-Host '==================================================' -ForegroundColor Green
    }

    'status' {
        Write-Host '>>> 正在检测服务运行状态...' -ForegroundColor Cyan
        $listen = Check-ServerRunning -CheckPort $Port
        if ($listen) {
            Write-Host ('[运行中] 端口 ' + $Port + ' 正在监听中，PID: ' + $listen[0].OwningProcess) -ForegroundColor Green
        } else {
            Write-Host ('[未运行] 端口 ' + $Port + ' 当前未在监听。') -ForegroundColor Yellow
        }

        if (Test-Path $NssmExe) {
            & $NssmExe status $ServiceName
        } else {
            schtasks /Query /TN $ServiceName /FO LIST 2>$null
        }
    }

    'start' {
        if (Test-Path $NssmExe) {
            & $NssmExe start $ServiceName
        } else {
            schtasks /Run /TN $ServiceName
        }
    }

    'stop' {
        Write-Host '正在停止 StockAI 服务...' -ForegroundColor Yellow
        if (Test-Path $NssmExe) {
            & $NssmExe stop $ServiceName 2>$null | Out-Null
        }
        schtasks /End /TN $ServiceName 2>$null | Out-Null
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_server.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force 2>$null }
        Write-Host '[成功] 服务已停止。' -ForegroundColor Green
    }

    'restart' {
        & $PSCommandPath -Port $Port -Action stop
        Start-Sleep -Seconds 2
        & $PSCommandPath -Port $Port -Action start
    }

    'uninstall' {
        Write-Host ('正在停止并卸载 ' + $ServiceName + ' ...') -ForegroundColor Yellow
        if (Test-Path $NssmExe) {
            & $NssmExe stop $ServiceName 2>$null | Out-Null
            & $NssmExe remove $ServiceName confirm 2>$null | Out-Null
        }
        schtasks /End /TN $ServiceName 2>$null | Out-Null
        schtasks /Delete /TN $ServiceName /F 2>$null | Out-Null
        Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_server.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force 2>$null }
        Write-Host '[成功] 服务已完整卸载！' -ForegroundColor Green
    }

    default {
        Write-Host ('未知动作: ' + $Action + '。支持的动作: install, status, start, stop, restart, uninstall, firewall') -ForegroundColor Red
    }
}
