# -*- coding: utf-8 -*-
"""验证数据库文件路径解析逻辑：开发环境与打包 exe 环境"""

import sys
import os
from unittest.mock import patch
from pathlib import Path

# 确保根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import config, AppConfig
from app.core.database import db_manager, StockBasic, VirtualPosition

def test_dev_environment_db_path():
    print("==================================================")
    print(">>> 1. 验证源码开发环境下的数据库路径 <<<")
    expected_root_db = PROJECT_ROOT / "stock_ai.db"
    print(f"当前 config.db_path: {config.db_path}")
    print(f"期望根目录路径: {expected_root_db}")
    assert config.db_path.resolve() == expected_root_db.resolve(), "开发环境下的 db_path 必须指向项目根目录下的 stock_ai.db"
    assert config.db_path.exists(), "项目根目录下的 stock_ai.db 文件必须存在"

    session = db_manager.get_session()
    stocks_count = session.query(StockBasic).count()
    pos_count = session.query(VirtualPosition).count()
    session.close()

    print(f"成功访问项目根目录数据库！全量股票数: {stocks_count}, 持仓数: {pos_count}")
    assert stocks_count >= 5000, f"股票基础数据应大于 5000 支，实际为 {stocks_count}"
    print(">>> [PASS] 源码开发环境数据库路径与读写验证通过！<<<")

def test_frozen_exe_db_path():
    print("\n==================================================")
    print(">>> 2. 模拟运行打包 exe (sys.frozen = True) 环境下的数据库路径 <<<")
    fake_exe_dir = Path("D:/Release/StockAI")
    fake_exe_path = fake_exe_dir / "StockAI.exe"

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", str(fake_exe_path)):
        # 实例化临时 AppConfig 测试路径解析
        base_dir = config._get_app_base_dir()
        expected_db_path = fake_exe_dir / "stock_ai.db"
        print(f"模拟 exe 路径: {fake_exe_path}")
        print(f"解析出的基准目录: {base_dir}")
        print(f"解析出的数据库路径: {base_dir / 'stock_ai.db'}")

        assert base_dir == fake_exe_dir, f"基准目录应为 exe 所在目录: {fake_exe_dir}"
        assert (base_dir / "stock_ai.db") == expected_db_path, f"数据库路径应为: {expected_db_path}"
    print(">>> [PASS] 打包 exe 环境下数据库链接到 exe 文件所在目录逻辑验证通过！<<<")

if __name__ == "__main__":
    test_dev_environment_db_path()
    test_frozen_exe_db_path()
