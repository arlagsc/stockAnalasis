# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 跨平台全依赖打包规格文件 (stock_ai.spec)

自动适配 Windows 与 macOS：
- Windows 平台：生成完全自包含的独立免安装目录 (dist/StockAI/StockAI.exe)
- macOS 平台：生成标准 macOS 应用捆绑包 (dist/StockAI.app)
包含所有 Python 运行时、PySide6 动态链接库、Qt 平台插件与 SSL 根证书，
可在未安装 Python 的任意其他电脑上双击直接运行。
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# 1. 收集关键运行数据文件（特别是 SSL 根证书与全市场股票基础池索引）
datas = []
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except Exception:
    pass

universe_file = os.path.join('app', 'data', 'stocks_universe.json')
if os.path.exists(universe_file):
    datas.append((universe_file, os.path.join('app', 'data')))

# 2. 收集全量关键库隐式依赖，防止动态加载丢失
hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'pyqtgraph',
    'pyqtgraph.graphicsItems',
    'pandas',
    'numpy',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'pydantic',
    'pydantic_core',
    'openai',
    'cryptography',
    'cryptography.fernet',
    'platformdirs',
    'requests',
    'urllib3',
    'certifi',
    'akshare',
    'curl_cffi',
]

# 3. 排除体积庞大且完全未使用的 Qt 扩展模块以控制体积
excludes = [
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtQuick',
    'PySide6.QtQml',
    'PySide6.Qt3DCore',
    'PySide6.QtDesigner',
    'PySide6.QtSensors',
    'PySide6.QtPositioning',
    'tkinter',
    'matplotlib',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StockAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 禁用黑窗口控制台，提供纯粹 GUI 体验
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StockAI',
)

# 如果在 macOS 上构建，则额外生成标准 .app 捆绑包
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='StockAI.app',
        icon=None,
        bundle_identifier='com.stockai.app',
        info_plist={
            'CFBundleName': 'StockAI',
            'CFBundleDisplayName': 'StockAI 股票智能分析',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': 'True',
            'LSMinimumSystemVersion': '11.0.0',
        },
    )
