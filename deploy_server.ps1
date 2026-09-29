# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    StockAI Windows Server 一键部署与 NSSM 系统服务注册脚本
.DESCRIPTION
    适用于目标服务器 (172.16.9.28)，一键放行防火墙 2222 端口，
    创建 Python 虚拟环境，并使用 NSSM 注册为开机自启系统服务。
#>

param(
    [string]$Port = '2222',
    [string]$AuthUser = 'admin',
    [string]$AuthPass = 'StockAI@2026',
    [string]$Action = 'install'
)

$ServiceName = 'StockAIService'
$CurrentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogsDir = Join-Path $CurrentDir 'logs'
$VenvPython = Join-Path $CurrentDir '.venv\Scripts\python.exe'
$NssmExe = Join-Path $CurrentDir 'nssm.exe'

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

switch ($Action.ToLower()) {
    'firewall' {
        Write-Host ('[1/2] 正在配置 Windows 防火墙入站规则 (端口 ' + $Port + ')...') -ForegroundColor Yellow
        $existingRule = Get-NetFirewallRule -DisplayName 'StockAI Web Service' -ErrorAction SilentlyContinue
        if ($existingRule) {
            Remove-NetFirewallRule -DisplayName 'StockAI Web Service'
        }
        New-NetFirewallRule -DisplayName 'StockAI Web Service' -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow | Out-Null
        Write-Host ('[成功] 防火墙已成功放行 TCP ' + $Port + ' 端口！') -ForegroundColor Green
    }

    'nssm-download' {
        if (-not (Test-Path $NssmExe)) {
            Write-Host '未检测到 nssm.exe，尝试从官方源下载 NSSM 64 位版本...' -ForegroundColor Yellow
            $zipPath = Join-Path $env:TEMP 'nssm.zip'
            $nssmUrl = 'https://nssm.cc/release/nssm-2.24.zip'
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $nssmUrl -OutFile $zipPath -TimeoutSec 30
                Expand-Archive -Path $zipPath -DestinationPath (Join-Path $env:TEMP 'nssm_extracted') -Force
                Copy-Item (Join-Path $env:TEMP 'nssm_extracted\nssm-2.24\win64\nssm.exe') -Destination $NssmExe -Force
                Write-Host ('[成功] nssm.exe 已就绪: ' + $NssmExe) -ForegroundColor Green
            } catch {
                Write-Warning ('自动下载 NSSM 失败: ' + $_)
                Write-Host ('请手动将 64 位的 nssm.exe 复制到项目目录: ' + $CurrentDir) -ForegroundColor Red
            }
        }
    }

    'install' {
        # 1. 防火墙放行
        & $PSCommandPath -Port $Port -Action firewall

        # 2. 检查端口占用情况
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $occupierPid = $conn[0].OwningProcess
            $procName = (Get-Process -Id $occupierPid -ErrorAction SilentlyContinue).ProcessName
            Write-Warning ('[注意] 端口 ' + $Port + ' 当前正被进程 [' + $procName + '] (PID: ' + $occupierPid + ') 监听中！')
            Write-Warning '如果该端口为正在运行的 IIS/HTTP 服务，需先停止或换用未被占用的端口。'
        }

        # 3. 检查 Python 解释器
        $targetPython = 'python.exe'
        if (Test-Path $VenvPython) {
            $targetPython = $VenvPython
            Write-Host ('使用虚拟环境 Python: ' + $targetPython) -ForegroundColor Green
        } else {
            Write-Host '未找到 .venv 虚拟环境，将使用系统默认 python.exe' -ForegroundColor Yellow
        }

        # 4. 检查 NSSM
        if (-not (Test-Path $NssmExe)) {
            & $PSCommandPath -Action nssm-download
        }
        if (-not (Test-Path $NssmExe)) {
            Write-Error '找不到 nssm.exe，无法安装 Windows 服务！'
            exit 1
        }

        # 5. 停止并移除旧服务
        Write-Host '正在停止并清理旧服务 (若已存在)...' -ForegroundColor Yellow
        & $NssmExe stop $ServiceName 2>$null | Out-Null
        & $NssmExe remove $ServiceName confirm 2>$null | Out-Null

        # 6. 安装新服务
        Write-Host ('正在注册 Windows 系统服务: ' + $ServiceName + ' ...') -ForegroundColor Yellow
        $runArgs = 'run_server.py --host 0.0.0.0 --port ' + $Port + ' --auth-user ' + $AuthUser + ' --auth-pass ' + $AuthPass
        & $NssmExe install $ServiceName $targetPython $runArgs
        & $NssmExe set $ServiceName AppDirectory $CurrentDir
        & $NssmExe set $ServiceName DisplayName 'StockAI Autonomous Trading Web Service'
        & $NssmExe set $ServiceName Description 'StockAI A 股自动化操盘终端 Web 接入与后台调度守护引擎'
        & $NssmExe set $ServiceName Start SERVICE_AUTO_START
        & $NssmExe set $ServiceName AppExit Default Restart
        & $NssmExe set $ServiceName AppRestartDelay 5000

        # 配置日志重定向与自动轮转
        $stdoutLog = Join-Path $LogsDir 'service_stdout.log'
        $stderrLog = Join-Path $LogsDir 'service_stderr.log'
        & $NssmExe set $ServiceName AppStdout $stdoutLog
        & $NssmExe set $ServiceName AppStderr $stderrLog
        & $NssmExe set $ServiceName AppRotateFiles 1
        & $NssmExe set $ServiceName AppRotateBytes 52428800

        # 7. 启动服务
        Write-Host ('正在启动 ' + $ServiceName + ' 服务...') -ForegroundColor Yellow
        & $NssmExe start $ServiceName

        Start-Sleep -Seconds 3
        $status = & $NssmExe status $ServiceName
        Write-Host '==================================================' -ForegroundColor Green
        Write-Host ('[成功] 服务部署并启动完成！当前运行状态: ' + $status) -ForegroundColor Green
        Write-Host ('本地访问测试: http://127.0.0.1:' + $Port) -ForegroundColor Green
        Write-Host ('公网访问地址: http://113.98.232.83:' + $Port) -ForegroundColor Green
        Write-Host ('登录账号: ' + $AuthUser + ' / 密码: ' + $AuthPass) -ForegroundColor Green
        Write-Host ('日志监控文件: ' + $stdoutLog) -ForegroundColor Green
        Write-Host '==================================================' -ForegroundColor Green
    }

    'status' {
        if (Test-Path $NssmExe) {
            & $NssmExe status $ServiceName
        } else {
            Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        }
    }

    'start' {
        & $NssmExe start $ServiceName
    }

    'stop' {
        & $NssmExe stop $ServiceName
    }

    'restart' {
        & $NssmExe restart $ServiceName
    }

    'uninstall' {
        Write-Host ('正在停止并卸载 ' + $ServiceName + ' ...') -ForegroundColor Yellow
        & $NssmExe stop $ServiceName 2>$null | Out-Null
        & $NssmExe remove $ServiceName confirm
        Write-Host '[成功] 服务已卸载！' -ForegroundColor Green
    }

    default {
        Write-Host ('未知动作: ' + $Action + '。支持的动作: install, status, start, stop, restart, uninstall, firewall') -ForegroundColor Red
    }
}
