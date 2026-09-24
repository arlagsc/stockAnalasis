# 股票智能分析终端 (StockAI) — 代码逻辑图谱与速查文档 (walkthrough.md)

> 版本：v1.1.0  
> 技术栈：Python 3.13 + PySide6 (Qt) + PyQtGraph + AkShare + 大模型统一客户端 + PyInstaller  
> 最后更新：2026-09-20  

---

## 1. 项目概述
基于 **PySide6 (Qt) 与 PyQtGraph** 构建的跨平台股票智能分析与推荐桌面软件，深度融合**本地量化多因子高速初筛**与**大语言模型（LLM）可解释性深度研报推理**，提供低延迟、沉浸式的证券分析辅助。

---

## 2. 系统核心架构与数据流图

```mermaid
graph TD
    UI[PySide6 表现层 MainWindow] -->|选择/切换页面| Pages[Pages: 大盘看板 / 自选池 / 筛选器 / 推荐榜 / 个股研判 / 设置]
    Pages -->|用户点击/查询| ThreadPool[Qt 异步线程池 QThreadPool / AIStreamWorker]
    
    ThreadPool -->|1. 获取股票全景与K线| DataService[业务中枢 DataService]
    ThreadPool -->|2. 执行两阶段筛选| ScreenerService[两阶段漏斗 ScreenerService]
    ThreadPool -->|3. 生成综合推荐理由| RecommendService[智能推荐 RecommendService]
    ThreadPool -->|4. 流式问答与诊断| LLMClient[大模型客户端 LLMClient]

    DataService --> Cache[本地缓存管理器 CacheManager]
    Cache --> SQLite[(本地 SQLite 数据库 stock_ai.db)]
    Cache --> Fetcher[AkShare / 东方财富数据采集器 DataFetcher]
    
    ScreenerService --> LocalFilter[本地 Pandas 向量化矩阵初筛]
    ScreenerService --> NLCompiler[NL-to-Filter 语义编译器]
    NLCompiler --> LLMClient

    LLMClient --> OpenAIAPI[OpenAI 兼容协议端点: DeepSeek / 通义千问 / 本地 Ollama]
    LLMClient --> SafeKey[安全加密凭据管理器 SecurityManager]
```

---

## 3. 核心模块与关键函数速查

### 3.1 基础设施层 (`app/core/`)
| 文件路径 | 核心类 / 关键函数 | 功能说明 |
| :--- | :--- | :--- |
| [`app/core/config.py`](file:///d:/AI/stockAnalasis/app/core/config.py) | `AppConfig` | 跨平台路径管理（`platformdirs`）、日志配置、默认大模型厂商预设字典。 |
| [`app/core/security.py`](file:///d:/AI/stockAnalasis/app/core/security.py) | `SecurityManager.save_api_keys()`<br>`SecurityManager.load_api_keys()` | 基于本地 Fernet 对称密钥安全加解密各大模型 API Key，杜绝明文落盘。 |
| [`app/core/database.py`](file:///d:/AI/stockAnalasis/app/core/database.py) | `DatabaseManager`<br>`StockBasic`, `Watchlist`, `AnalysisReport` | SQLAlchemy ORM 模型定义与 SQLite 连接池，提供自选股与历史研报持久化。 |

### 3.2 数据与指标引擎 (`app/data/`)
| 文件路径 | 核心类 / 关键函数 | 功能说明 |
| :--- | :--- | :--- |
| [`app/data/fetcher.py`](file:///d:/AI/stockAnalasis/app/data/fetcher.py) | `DataFetcher.fetch_all_stock_basics()`<br>`DataFetcher.fetch_stock_daily_kline()` | 封装 AkShare 接口，拉取全市场行情、分时日 K、财务指标与新闻，内置离线 Mock 保护。 |
| [`app/data/indicators.py`](file:///d:/AI/stockAnalasis/app/data/indicators.py) | `IndicatorEngine.calculate_all_indicators()` | Pandas 向量化计算 MA5/10/20/60、MACD、RSI6/12/24、布林线 BOLL、KDJ 等指标。 |
| [`app/data/cache_manager.py`](file:///d:/AI/stockAnalasis/app/data/cache_manager.py) | `CacheManager.get_stocks_dataframe()`<br>`CacheManager.sync_stocks_from_source()` | 控制 4 小时缓存过期策略，维护本地 SQLite 与内存 DataFrame 缓存。 |

### 3.3 大模型与业务服务层 (`app/ai/`, `app/services/`)
| 文件路径 | 核心类 / 关键函数 | 功能说明 |
| :--- | :--- | :--- |
| [`app/ai/llm_client.py`](file:///d:/AI/stockAnalasis/app/ai/llm_client.py) | `LLMClient.stream_chat()`<br>`LLMClient.chat_complete()` | 统一基于 OpenAI SDK 调用，支持流式打字生成、一次性结构化 JSON 交互与智能离线兜底。 |
| [`app/ai/prompts.py`](file:///d:/AI/stockAnalasis/app/ai/prompts.py) | `STOCK_ANALYSIS_SYSTEM_PROMPT`<br>`TRADE_REFLECTION_SYSTEM_PROMPT`<br>`AUTO_TRADE_SYSTEM_PROMPT` | 个股深度研报、自然语言选股、精选推荐、平仓归因反思与 AI 自动建仓决策提示词模板。 |
| [`app/ai/skill_engine.py`](file:///d:/AI/stockAnalasis/app/ai/skill_engine.py) | `SkillEngine.reflect_on_trade()`<br>`SkillEngine.get_active_skills_prompt_block()` | 操盘技能演进中枢：平仓触发 LLM 归因反思沉淀军规战则，并在后续推荐决策时动态提取 Few-Shot 注入。 |
| [`app/services/trading_service.py`](file:///d:/AI/stockAnalasis/app/services/trading_service.py) | `TradingService.reset_account()`<br>`TradingService.buy_stock()`<br>`TradingService.sell_stock()`<br>`TradingService.refresh_positions_quotes()` | A 股仿真撮合引擎：支持自定义初始本金、100 股整数倍买入、T+1 纪律锁定/跨日解冻、真实印花税与佣金扣减。 |
| [`app/services/auto_trader.py`](file:///d:/AI/stockAnalasis/app/services/auto_trader.py) | `AutoTrader.execute_auto_trading()` | AI 智能建仓决策中枢：双层风控核验、全市场 5565 支多因子粗选、操盘军规 (SKILL) 注入深度裁决、动态分仓计算与合规撮合。 |
| [`app/services/screener_service.py`](file:///d:/AI/stockAnalasis/app/services/screener_service.py) | `ScreenerService.screen_by_natural_language()`<br>`ScreenerService.execute_filter_plan()` | 两阶段漏斗筛选：本地量化粗排将 5000+ 只降至 20~50 候选池 + 自然语言选股。 |
| [`app/services/recommend_service.py`](file:///d:/AI/stockAnalasis/app/services/recommend_service.py) | `RecommendService.generate_recommendations()` | 复合因子综合评分 + 动态注入活跃操盘军规 + 大模型深度精选。 |
| [`app/services/watchlist_service.py`](file:///d:/AI/stockAnalasis/app/services/watchlist_service.py) | `WatchlistService.add_to_watchlist()`<br>`WatchlistService.get_watchlist_with_quotes()` | 自选股池增删改查、自定义分组及与实时量价行情合并。 |
| [`app/services/scheduler_service.py`](file:///d:/AI/stockAnalasis/app/services/scheduler_service.py) | `AutonomousScheduler.start()`<br>`AutonomousScheduler.pause()`<br>`AutonomousScheduler.emergency_stop()`<br>`AutonomousScheduler.reset_emergency_stop()` | A 股交易节律后台守护引擎：精准驱动 09:35 进攻建仓、盘中 15 分钟巡检风控、14:45 尾盘定型与 15:30 收盘复盘，内置全局急停熔断。 |

### 3.4 表现层 (`app/ui/`)
| 文件路径 | 核心类 / 关键控件 | 功能说明 |
| :--- | :--- | :--- |
| [`app/ui/theme.py`](file:///d:/AI/stockAnalasis/app/ui/theme.py) | `DARK_THEME_QSS` | 现代深色金融终端样式表，高分屏 DPI 自适应。 |
| [`app/ui/components/chart_widget.py`](file:///d:/AI/stockAnalasis/app/ui/components/chart_widget.py) | `StockChartWidget`<br>`CandlestickItem` | 基于 PyQtGraph 的 60 FPS 股票 K 线蜡烛图、均线族、成交量柱与联动十字光标。 |
| [`app/ui/pages/dashboard.py`](file:///d:/AI/stockAnalasis/app/ui/pages/dashboard.py) | `DashboardPage` | 全市场股票大盘概览网格、涨跌分布卡片、模糊检索与穿透联动。 |
| [`app/ui/pages/stock_detail.py`](file:///d:/AI/stockAnalasis/app/ui/pages/stock_detail.py) | `StockDetailPage`<br>`AIStreamWorker` | 个股深度研判，新增【💼 模拟买入】一键建仓对话框，异步流式打字渲染 AI 结构化研报。 |
| [`app/ui/pages/virtual_trading.py`](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py) | `VirtualTradingPage`<br>`BuyDialog`<br>`ResetCapitalDialog`<br>`AutoTradeWorker`<br>`AutoTradeResultDialog` | 虚拟操盘主工作台：人机双轨资产概况卡片、持仓明细、成交流水、PyQtGraph PK 走势曲线、Skill 军规卡片管理与【🤖 AI 一键自动建仓】异步管线。 |
| [`app/ui/pages/screener.py`](file:///d:/AI/stockAnalasis/app/ui/pages/screener.py) | `ScreenerPage` | 自然语言选股指令执行面板与预设量化策略库。 |
| [`app/ui/pages/recommend.py`](file:///d:/AI/stockAnalasis/app/ui/pages/recommend.py) | `RecommendPage`<br>`RecommendCard` | 推荐看板，瀑布流卡片展示综合评分、推荐理由与风险点。 |
| [`app/ui/pages/settings.py`](file:///d:/AI/stockAnalasis/app/ui/pages/settings.py) | `SettingsPage` | 模型接入配置、API Key 加密保存、缓存维护与免责声明展示。 |
| [`app/ui/main_window.py`](file:///d:/AI/stockAnalasis/app/ui/main_window.py) | `MainWindow` | 侧边栏导航控制中心，管理页面堆栈与跨页面跳转信号（包含虚拟操盘联动）。 |

---

## 4. 关键验证与构建日志
- **2026-09-20 [架构与实现]**：完成系统核心架构搭建，PySide6 与 AkShare 依赖安装就绪，全套数据、AI、量化指标计算引擎及 6 大业务页面编码完成。
- **2026-09-20 [核心逻辑验证]**：
  - `IndicatorEngine`：成功计算 30 根 K 线的 MA5/10/20/60、MACD、RSI6/12/24、布林带等 24 项指标矩阵。
  - `ScreenerService`：自然语言（NL-to-Filter）成功编译为结构化过滤规则并在本地内存矩阵执行筛选。
  - `RecommendService`：多因子打分与推荐引擎成功生成 Top 3 推荐标的与可解释归因理由。
  - `DataFetcher`：验证三级重试与网络抖动下的离线拟真股票池降级保护机制，系统具备高抗风险韧性。
- **2026-09-20 [Git 仓库托管与 GitHub Actions 云端打包触发]**：
  - 代码全量初始化并绑定远程仓库：`https://github.com/arlagsc/stockAnalasis.git`。
  - 配置专业 `.gitignore` 过滤构建缓存与私钥，成功推送至 `main` 主分支。
  - GitHub Actions 跨平台 CI/CD 流水线 ([build_release.yml](file:///d:/AI/stockAnalasis/.github/workflows/build_release.yml)) 已自动触发，云端正在使用真实的 macOS 与 Windows 虚拟机编译全依赖应用包并生成 Artifacts。
- **2026-09-20 [全量 A 股数据源故障排查与高速通道重构]**：
  - **问题根因**：东方财富接口近期实施 WAF 策略阻断（返回 502 Bad Gateway / Connection Reset），导致原采集器在 3 次重试失败后触发兜底逻辑；原内置兜底股票池仅定义了 15 支代表性标的，导致强制全量同步后看板仅展示 15 支。
  - **全量代码池索引建立**：从上交所主板、科创板、深交所及北交所提取完整证券名录，生成全量 5,565 支 A 股基础池索引文件 [`app/data/stocks_universe.json`](file:///d:/AI/stockAnalasis/app/data/stocks_universe.json)，并纳入 [`stock_ai.spec`](file:///d:/AI/stockAnalasis/stock_ai.spec) 打包资源。
  - **接入腾讯高速金融通道**：在 [`app/data/fetcher.py`](file:///d:/AI/stockAnalasis/app/data/fetcher.py) 中实现 `_fetch_tencent_realtime_basics`，采用 80 股批量分组与 12 线程并发查询，10 秒内即可拉取全市场 5,565 支股票的实时价格、涨跌幅、成交量、换手率、PE、PB 与总市值。
  - **兜底方案升级**：重构 `_generate_fallback_basics`，若处于完全离线状态，基于全量 5,565 支标的代码池生成一致性拟真数据，彻底消除股票数量缩水问题。
  - **实测验证**：本地 SQLite 数据库 [`StockBasic`](file:///d:/AI/stockAnalasis/app/core/database.py) 成功同步落盘 5,565 条真实记录；大盘看板顶部卡片准确显示覆盖标的总数 5,565 支，全市场股票表格分页与排序运作正常。
- **2026-09-20 [自选股多级研判联动与真实日 K 线高速通道]**：
  - **问题根因**：
    1. 个股日 K 线此前通过 `akshare.stock_zh_a_hist` 依赖东财接口，受 WAF 阻断后转入兜底逻辑；旧版 `_generate_fallback_kline` 存在 `pd.date_range` 越界异常 (`IndexError`)，导致页面渲染在中断后停滞于默认标的（贵州茅台）。
    2. 自选股页面仅在双击事件绑定了信号，当用户单击某行再通过侧边栏导航点击【个股研判】时，未将当前选中标的向后传递。
    3. 个股研判搜索框仅响应回车事件，未配置显式提交按钮，易造成输入未触发提交的交互假象。
  - **腾讯前复权日 K 线通道**：在 [`app/data/fetcher.py`](file:///d:/AI/stockAnalasis/app/data/fetcher.py) 新增 `_fetch_tencent_daily_kline` 毫秒级直连通道，修复兜底索引边界。
  - **全链路交互升级**：
    1. [`app/ui/pages/watchlist.py`](file:///d:/AI/stockAnalasis/app/ui/pages/watchlist.py)：自选表格操作列新增高亮【研判】按钮，点击直达；新增当前选中标的行记忆 `get_selected_symbol()`。
    2. [`app/ui/main_window.py`](file:///d:/AI/stockAnalasis/app/ui/main_window.py)：侧边栏切至【个股研判】时，自动探测并同步载入自选股列表中当前选中的标的。
    3. [`app/ui/pages/stock_detail.py`](file:///d:/AI/stockAnalasis/app/ui/pages/stock_detail.py)：顶部搜索栏新增显式【切换】按钮，支持 6 位代码自动规范化与回车/点击双重触发。
- **2026-09-20 [Windows 全依赖可执行程序重新打包完成]**：
  - 执行 `pyinstaller --clean -y stock_ai.spec` 完成打包构建，内嵌全量 5,565 支股票静态索引与 SSL 根证书。
  - 生成免安装绿色程序目录 [`dist/StockAI/StockAI.exe`](file:///d:/AI/stockAnalasis/dist/StockAI/StockAI.exe)（66.21 MB），并打包为 [`dist/StockAI-Windows-x64.zip`](file:///d:/AI/stockAnalasis/dist/StockAI-Windows-x64.zip)（316.91 MB）。
  - 执行独立进程启动校验，程序正常启动且无任何缺失动态库或证书报错。
- **2026-09-20 [虚拟建仓仿真交易系统与 AI 操盘技能库 (SKILL) 深度集成]**：
  - **人机双轨独立账户体系**：
    1. 在 [`app/core/database.py`](file:///d:/AI/stockAnalasis/app/core/database.py) 新增 `VirtualAccount`、`VirtualPosition`、`VirtualTrade`、`TraderSkill` 4 张 ORM 表结构，支持人类主观账户 (MANUAL) 与 AI 智能账户 (AI) 并行核算。
    2. 支持用户自由设定初始本金（如 10 万、30 万、100 万元），并提供一键重置清空历史持仓与流水功能。
  - **A 股仿真撮合规则落地**：
    1. 严格约束买入数量为 100 股整数倍（非标手数实时拦截）。
    2. 严格执行 A 股 T+1 交易纪律：当日买入持仓 `available_amount` 锁定为 0，当日尝试卖出立即告警拦截；跨交易日或调用 `refresh_positions_quotes()` 时自动解冻恢复为全部可卖。
    3. 真实交易摩擦成本：卖出计提 0.05% 印花税，买卖双向计提万分之二券商佣金（保底 5 元）。
  - **操盘技能库 (SKILL) 闭环演化机制**：
    1. 平仓结清盈亏后，自动触发 [`app/ai/skill_engine.py`](file:///d:/AI/stockAnalasis/app/ai/skill_engine.py) 的 `reflect_on_trade`，大模型结合技术指标快照与实盘盈亏深度归因，提炼出结构化操盘军规（如【破位果断截断亏损纪律】）。
    2. 军规持久化存入 `TraderSkill`，并在 [`app/services/recommend_service.py`](file:///d:/AI/stockAnalasis/app/services/recommend_service.py) 生成选股推荐时，通过 `get_active_skills_prompt_block()` 将高胜率军规作为 Few-Shot 动态注入提示词，达成“操盘经验越丰富，AI 选股与择时能力越强”的自我演进闭环。
  - **集成验证与实机渲染**：
    1. 编写自动化集成测试脚本 [`tests/test_virtual_trading.py`](file:///d:/AI/stockAnalasis/tests/test_virtual_trading.py)，覆盖自定义本金重置、非 100 股拦截、T+1 锁定、次日解锁、摩擦扣费、流水核对与大模型反思入库，所有 8 项核心逻辑自动化测试全部 PASS。
    2. 完成主界面集成与实机渲染截图校验，双账户资产卡片、持仓明细、成交流水与技能知识库展示正常。
  - **缺陷修复 (BuyDialog 信号参数防御)**：
    - **问题表现**：点击【➕ 模拟买入建仓】按钮时抛出 `TypeError: QLineEdit.__init__(bool)` 异常。
    - **根因分析**：PyQt/PySide6 的 `QPushButton.clicked` 信号会默认向槽函数传递一个 `checked: bool = False` 布尔值，当被 `_open_buy_dialog(symbol: str = "")` 捕获后，导致 `default_symbol` 变为 `False`，传给 `QLineEdit(False)` 触发类型匹配失败。
    - **修复措施**：在 [`BuyDialog`](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py) 构造函数与 `_open_buy_dialog` 中对 `default_symbol` 实施类型防护（强制清洗为字符串），并将按钮点击信号绑定改为无参 lambda 调用，彻底杜绝类型污染。
- **2026-09-20 [AI 自动计算建仓系统 (AutoTrader) 落地与闭环]**：
  - **前置风控与标的选拔管线**：
    1. 在 [`app/services/auto_trader.py`](file:///d:/AI/stockAnalasis/app/services/auto_trader.py) 构建 `AutoTrader` 决策服务，实现双层风控前置校验：AI 账户可用现金低于 2000 元安全拦截，持仓已达 5 支上限时拦截。
    2. 全市场 5565 支股票 Pandas 向量化多因子粗筛，自动剔除已持仓标的、ST 股与极端涨跌停标的，选拔量价齐升的 Top 10 候选池。
    3. 提取历史实战操盘军规 (Few-Shot) 注入大模型进行形态裁决与战术归因，内建本地多因子评分引擎作为离线平滑降级兜底。
  - **动态加权分仓与合规撮合**：
    1. 动态头寸测算：高置信度（$\ge 88$ 分）标的分配当前现金的 28% 目标资金，次优标的分配 18%，单票资金严格受控在 30% 上限之内。
    2. 资金向下取整换算为 100 股整数倍（一手）调用 `trading_service.buy_stock` 撮合，自动归档成交流水并执行 T+1 交易纪律冻结。
  - **表现层异步交互与弹窗报告**：
    1. 在 [`app/ui/pages/virtual_trading.py`](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py) 顶部操作栏新增深紫色高亮【🤖 AI 一键自动建仓】按钮。
    2. 通过后台 `AutoTradeWorker(QThread)` 异步执行计算与推理，展示运行状态，避免阻塞 Qt 事件循环。
    3. 任务完成后呼出卡片式 `AutoTradeResultDialog` 执行报告弹窗，详细展示成交价、股数、成交额以及 AI 决策归因与契合军规，并触发资产走势与持仓全量刷新。
  - **集成验证与实机渲染**：
    1. 编写自动化集成测试脚本 [`tests/test_auto_trader.py`](file:///d:/AI/stockAnalasis/tests/test_auto_trader.py)，覆盖低现金拦截、正常多因子自动建仓、100 股取整测算、T+1 冻结与流水核实、避开已有持仓去重建仓以及 5 支持仓上限风控拦截，所有 5 项测试全部 PASS。
- **2026-09-20 [全系统深色金融终端高对比度与表格交替行白底白字根除]**：
  - **问题根因定位**：
    1. 在 Windows 操作系统默认亮色调色板环境下，当 `QTableWidget` 或 `QTableView` 开启 `setAlternatingRowColors(True)` 时，若 QSS 中未显式指定 `alternate-background-color`，Qt 引擎会自动继承 Windows 系统的亮白底色 (`#FFFFFF`) 填充偶数行。
    2. 深色金融主题下的单元格文本颜色为浅白/浅灰色（`#E2E8F0`、`#F1F5F9` 等），导致偶数行产生极严重的“白底白字”对比度缺失，股票代码、名称、指标数值完全无法辨识。
  - **三层立体防护修复方案**：
    1. **系统底层调色板锁定 ([main.py](file:///d:/AI/stockAnalasis/main.py))**：显式应用 `app.setStyle("Fusion")` 跨平台渲染引擎，并构建全量深色 `QPalette` 注入 `QApplication`。将 `QPalette.AlternateBase` 强制锁定为深色 `#181C26`，`QPalette.Base` 锁定为 `#12141B`，从系统底层彻底杜绝操作系统亮白画刷泄漏。
    2. **全局样式表深度重构 ([app/ui/theme.py](file:///d:/AI/stockAnalasis/app/ui/theme.py))**：
       - 为 `QTableWidget, QTableView` 显式设置 `background-color: #0F1218` 与 `alternate-background-color: #171B24`；
       - 显式声明 `QTableWidget::item` 文本色为高对比度 `#F1F5F9`，`QTableWidget::item:alternate` 背景为 `#171B24`，选中态背景为 `#1E3A8A`，选中文字纯白；
       - 统一优化表头 `QHeaderView::section` 背景为 `#161922`，文字为 `#CBD5E1`。
    3. **业务页面单元格渲染前景色显式加固**：
       - [`app/ui/pages/dashboard.py`](file:///d:/AI/stockAnalasis/app/ui/pages/dashboard.py)：常规列单元格显式绑定 `QColor("#F1F5F9")`，涨跌幅采用深色底优化的高饱和亮红 (`#F87171`)、亮绿 (`#34D399`) 与平盘亮灰 (`#CBD5E1`)。
       - [`app/ui/pages/watchlist.py`](file:///d:/AI/stockAnalasis/app/ui/pages/watchlist.py)：自选股代码、名称、最新价、成交量等全量单元格显式配置高对比度前景色。
       - [`app/ui/pages/screener.py`](file:///d:/AI/stockAnalasis/app/ui/pages/screener.py)：多因子与自然语言筛选结果表格单元格显式前景色加固。
       - [`app/ui/pages/virtual_trading.py`](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py)：持仓明细、成交流水、操盘军规知识库表格全量单元格显式高对比度前景色加固。
       - [`app/ui/components/stat_card.py`](file:///d:/AI/stockAnalasis/app/ui/components/stat_card.py)：提升指标卡片标题（`#CBD5E1`）与副标题（`#94A3B8`）对比度，保证弱光与强光环境下数据清晰醒目。
  - **实机截图与验证**：
    - 大盘看板偶数行白底彻底清除，所有行列信息清晰锐利；
    - 自选股、智能筛选、虚拟操盘持仓与流水表格在深色主题下均呈现统一、高对比度的专业金融终端视觉效果。
- **2026-09-20 [虚拟操盘 0 延迟秒开性能重构与定向高速行情流水线]**：
  - **卡顿根因剖析**：
    1. 切换至虚拟操盘页面时，Qt 主 UI 线程同步调用 `trading_service.refresh_positions_quotes()`，其内部调用 `fetch_all_stock_basics()`，触发全市场 5,565 支股票的并发网络请求与大数据遍历，导致主事件循环卡死冻结数秒。
    2. 缺乏针对持仓特定标的（通常仅 0~10 支）的极简单次 HTTP 定向拉取通道。
  - **性能重构方案实施**：
    1. **数据采集层定向通道 ([app/data/fetcher.py](file:///d:/AI/stockAnalasis/app/data/fetcher.py))**：
       - 实现 `fetch_specific_quotes(symbols: List[str]) -> Dict[str, Dict[str, Any]]`，构造极简 URL 参数（如 `q=sh600519,sz000001`），单次 HTTP GET 请求直连腾讯接口，单次查询由全市场数秒大幅缩短至数十毫秒。
    2. **撮合服务层定向更新 ([app/services/trading_service.py](file:///d:/AI/stockAnalasis/app/services/trading_service.py))**：
       - 重构 `refresh_positions_quotes()`：仅提取当前实际持仓的股票代码集合进行定向查询更新，若持仓为空则立即退出，杜绝全市场 5,565 支无意义扫描；
       - 优化 `buy_stock()`：买入股票若未指定现价，优先调用定向接口获取单股盘口现价。
    3. **表现层双阶段秒开流水线 ([app/ui/pages/virtual_trading.py](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py))**：
       - **第一阶段（本地 0 延迟秒开）**：`load_local_data()` 纯从本地 SQLite 读取资产卡片与持仓明细，首屏加载耗时由数秒降至约 12~14 毫秒，点击侧边栏立即可见，无任何鼠标卡死或界面冻结；
       - **第二阶段（后台异步静默刷新）**：新增 `PositionsQuoteWorker(QThread)`，在后台线程中异步定向拉取持仓标的盘口，通过 Qt 信号在主线程平滑刷新卡片与持仓现价，实现无感平滑更新；
       - 优化顶部【🔄 刷新盘口行情】按钮反馈态（“⏳ 正在刷新...”）。
  - **验证与基准测试**：
    - 编写自动化测试 [`tests/test_fast_quote_refresh.py`](file:///d:/AI/stockAnalasis/tests/test_fast_quote_refresh.py)，验证定向查询结构、空持仓保护、持仓价格更新以及本地首屏读取性能（实测耗时 1.41 ms，远低于 50 ms 阈值）；
    - 实机主界面切换测试：从侧边栏点击【虚拟操盘】首屏渲染耗时仅 **13.66 ms**，后台定向拉取平滑静默交付，视觉呈现深色金融高对比度统一标准。
- **2026-09-20 [大语言模型设置持久化存储与活跃服务商跨会话自动恢复]**：
  - **问题根因定位**：
    1. 内存与磁盘割裂：旧版 `AppConfig` 仅在内存中维护 `current_provider_name` 与各服务商的 `base_url`、`model_name`，未实现 `settings.json` 的读写持久化。
    2. 保存逻辑不完整：在 [`app/ui/pages/settings.py`](file:///d:/AI/stockAnalasis/app/ui/pages/settings.py) 中点击【安全保存模型配置】时，虽然使用 AES 加密将 Key 保存到了 `api_keys.enc`，但未将用户当前选中的活跃服务商及自定义端点参数写入 `settings.json`；
    3. 界面初始化无回显：设置页面启动时下拉框默认硬编码加载首项（DeepSeek），重新启动软件后用户先前配置的其他模型（如通义千问、Kimi、GLM、Ollama 等）不会被自动选中。
  - **修复实施方案**：
    1. **配置层实现完整持久化通道 ([app/core/config.py](file:///d:/AI/stockAnalasis/app/core/config.py))**：
       - 实现 `save_settings()`：将 `current_provider_name`、`cache_expiry_hours` 以及各厂商自定义的 `base_url`、`model_name` 全量格式化写入标准路径下的 `settings.json`；
       - 实现 `load_settings()`：在应用启动及 `AppConfig` 实例化时自动反序列化 `settings.json`，无缝恢复用户上次保存的活跃服务商与所有模型参数。
    2. **表现层双向闭环交互 ([app/ui/pages/settings.py](file:///d:/AI/stockAnalasis/app/ui/pages/settings.py))**：
       - 在页面初始化时调用 `combo_provider.findText(config.current_provider_name)`，自动高亮并定位用户上次保存的服务商；
       - 在 `_on_save_llm_clicked()` 中，同步更新 `config.current_provider_name` 并执行 `config.save_settings()` 写入磁盘；
       - 新增 `provider_configured = Signal(str)` 信号，在服务商切换或保存时触发。
    3. **主窗口状态栏联动 ([app/ui/main_window.py](file:///d:/AI/stockAnalasis/app/ui/main_window.py))**：
       - 主窗口监听 `provider_configured` 信号，实时联动更新底部状态栏展示的模型名称（如 `当前模型后端: Kimi (Moonshot)`）。
  - **验证与效果**：
    - 运行配置持久化测试：将活跃服务商修改为 `Kimi (Moonshot)` 并配置模型为 `moonshot-v1-32k`，重载验证 100% 通过；
    - 实机 UI 启动截图验证：主界面启动即自动高亮 `Kimi (Moonshot)`，对应 Base URL、Model ID 及 API Key 全部精准回填，底部状态栏实时同步。
- **2026-09-20 [个股研判操作栏集成自选股极速下拉切换与双向状态联动]**：
  - **业务背景与交互需求**：
    - 用户在【个股研判】页面深度分析某标的时，此前需手动输入 6 位代码或通过侧边栏返回自选股列表再行点击。为进一步提升投研工作流效率，需要在个股研判顶部操作栏直接提供【自选股下拉选择框】，支持用户一键展开并极速切换所关注的自选标的。
  - **模块设计与实现方案**：
    1. **极速自选查询接口 ([app/services/watchlist_service.py](file:///d:/AI/stockAnalasis/app/services/watchlist_service.py))**：
       - 新增 `get_watchlist_simple()` 方法，通过一条轻量 SQL 联合查询 `Watchlist` 与 `StockBasic`，仅提取代码与股票简称，查询耗时趋近于 0 毫秒。
    2. **操作栏新增下拉控件与事件响应 ([app/ui/pages/stock_detail.py](file:///d:/AI/stockAnalasis/app/ui/pages/stock_detail.py))**：
       - 在顶部操作栏增加 `combo_watchlist (QComboBox)` 下拉控件；
       - 实现 `refresh_watchlist_combo()` 方法：空自选时展示“⭐ 自选池为空”并禁用，有自选时格式化展示 `002429 兆驰股份` 等项，并在初始化与自选状态切换时自动刷新；
       - 监听 `currentIndexChanged` 信号，用户选中项后自动提取股票代码并无缝触发 `load_stock()` 加载日 K 线与基本面；
       - 双向高亮同步：在 `load_stock()` 中，若当前展示的标的属于自选池，自动高亮选中下拉框对应项；若非自选标的则重置为默认提示项。
    3. **主窗口切换生命周期保障 ([app/ui/main_window.py](file:///d:/AI/stockAnalasis/app/ui/main_window.py))**：
       - 在侧边栏导航切换至【个股研判】（index == 4）时，主动触发 `page_stock_detail.refresh_watchlist_combo()`，确保自选股列表在其他页面被增删改后，切至研判页面始终保持最新。
  - **实机测试与验证**：
    - 自动化测试用例验证下拉项装载与切换联动，选中项正确驱动页面加载对应标的；
    - 实机 UI 截图验证：自选下拉框与现有搜索框、按钮排布协调，深色主题对比度锐利，切换后 K 线图与指标秒级刷新。
- **2026-09-20 [虚拟建仓仿真下单对话框集成自选股快捷点选与双向同步]**：
  - **交互升级诉求**：
    - 用户在【虚拟建仓仿真下单】对话框（`BuyDialog`）手动输入股票代码操作较为繁琐。为提升下单效率，在弹窗中增加自选股快速下拉列表，支持直接选择自选池中的标的一键回填买入。
  - **实现方案与双向联动机制 ([app/ui/pages/virtual_trading.py](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py))**：
    1. 在 `BuyDialog` 表单中新增 `combo_watchlist (QComboBox)` 下拉控件，放置于操作账户之后；
    2. 实现 `_load_watchlist_options()` 方法：调用 `watchlist_service.get_watchlist_simple()` 极速填充自选列表（展示为 `002429 兆驰股份` 等格式）；若外部传入了默认代码，自动精准定位；
    3. 下拉框选择事件 `_on_watchlist_selected`：用户选择自选股后，自动将 6 位股票代码回填到 `input_symbol` 中；
    4. 输入框文本事件 `_on_symbol_text_changed`：用户在代码框手动输入时，反向同步高亮下拉框中匹配的自选标的，若无匹配则恢复默认提示项；
    5. 弹窗尺寸适配至 400x360 px，深色金融终端样式协调统一。
  - **实机测试与验证**：
    - 编写自动化测试脚本，验证下拉框选项加载、正向点选自动回填、反向输入文本同步高亮逻辑全部正常；
    - 实机渲染截图验证：深色金融底色下标签与下拉框对比度锐利，回填即时生效。
- **2026-09-20 [修复表格操作列按钮显示不全与行高挤压缺陷]**：
  - **缺陷背景与根因定位**：
    - 用户反馈【我的自选股票池】与【虚拟操盘】持仓明细表格中，最后一列操作按钮（“研判”、“移出”、“平仓”）文字严重被上下和左右挤压，呈现扁平条状且文字只露出一半。
    - 经深入排查，根本原因包括：
      1. 全局 `QPushButton` 默认样式内边距较大（`padding: 7px 16px`），而 `QTableWidget` 默认行高仅 24~28 px，单元格可用垂直空间严重不足，导致按钮被强行上下裁切；
      2. 表格表头所有列均默认使用 `QHeaderView.Stretch` 等比缩放，窗口稍窄或列数较多时，最后一列分配到的像素不足 100 px，横向容纳两个带内边距的按钮时发生叠压挤扁；
      3. 按钮未显式限制固定尺寸与布局居中对齐方式。
  - **优化与修复方案**：
    1. **主题样式层精确覆盖 ([app/ui/theme.py](file:///d:/AI/stockAnalasis/app/ui/theme.py))**：
       - 在深色金融主题 QSS 中增加 `QTableWidget QPushButton, QTableView QPushButton` 专项规则，设置 `min-height: 24px; max-height: 28px; padding: 2px 8px; font-size: 12px; border-radius: 4px;`，彻底解除全局大按钮内边距对表格嵌入按钮的样式污染。
    2. **自选股表格布局规范 ([app/ui/pages/watchlist.py](file:///d:/AI/stockAnalasis/app/ui/pages/watchlist.py))**：
       - 提高表格默认行高：`verticalHeader().setDefaultSectionSize(40)`；
       - 操作列显式锁定宽度：`horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)` 并设为 140 px，避免被其他列压缩；
       - 操作容器内按钮显式设置 `setFixedSize(54, 26)`，内边距设为 0，水平垂直居中对齐。
    3. **虚拟操盘持仓明细与军规表优化 ([app/ui/pages/virtual_trading.py](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py))**：
       - 持仓明细表行高设为 40 px，操作列锁定宽度 140 px；
       - “平仓”与“研判”按钮显式设置 `setFixedSize(54, 26)`，文字居中饱满呈现；
       - 操盘军规激活状态列锁定宽度 100 px，行高设为 42 px，激活按钮设为固定尺寸 `setFixedSize(70, 26)`；
       - 历史成交流水表行高同步优化为 36 px。
    4. **大盘看板与智能筛选表格一致性 ([app/ui/pages/dashboard.py](file:///d:/AI/stockAnalasis/app/ui/pages/dashboard.py), [app/ui/pages/screener.py](file:///d:/AI/stockAnalasis/app/ui/pages/screener.py))**：
       - 统一将数据行高设定为 36 px，彻底规避因默认行高不足导致的文本垂直挤压问题。
  - **实机测试与视觉核验**：
    - 实机截图捕获自选股列表与虚拟操盘持仓表，核验操作列按钮在深色金融终端下居中对齐、字号适中、左右留白充裕、文字 100% 完整显示无裁切；
    - 执行全量自动化测试用例，所有测试 100% 通过。
- **2026-09-20 [建立系统版本管理规范与首个正式版本 v1.0.0 发布]**：
  - **规范建设背景**：
    - 为保证客户端多模块持续演进的严谨性、可回溯性与团队协作标准化，正式将软件版本管理机制纳入系统设计与工程基建。
  - **核心方案与落地工作**：
    1. **系统设计文档增加第 7 章 ([项目设计文档.md](file:///d:/AI/stockAnalasis/%E9%A1%B9%E7%9B%AE%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md))**：
       - 制定严格的语义化版本号标准（SemVer 2.0.0）：明确 `MAJOR.MINOR.PATCH` 的递增原则与判定场景；
       - 确立单一可信数据源（SSOT）机制：以 `app/core/config.py` 中的 `APP_VERSION` 作为全局唯一版本标识常量，统一供给主窗口 Title、系统设置、日志与打包脚本；
       - 制定标准更新日志（Keep a Changelog）归档流程与 Git Tag 标签发布流水线。
    2. **创建项目标准变更日志 ([CHANGELOG.md](file:///d:/AI/stockAnalasis/CHANGELOG.md))**：
       - 详细分类归档 `[1.0.0] - 2026-09-20` 首个稳定发布里程碑的全部特性：
         - `Added`：涵盖大盘看板、自选股池、智能筛选、精选推荐、个股研判（含自选下拉联动）、双轨虚拟操盘（含自选买入联动与军规知识库）、本地模型与设置持久化等；
         - `Performance`：虚拟操盘 0 延迟秒开流水线（$< 30$ ms 首屏）；
         - `Fixed`：深色模式高对比度校准、表格操作按钮挤压修复、模型选择持久化修复。
    3. **Git 版本标签归档与远程发布**：
       - 创建正式带注释标签 `v1.0.0`，并同步推送至 GitHub 远程仓库。
- **2026-09-20 [修复精选推荐 Prompt 占位符解析引发的 KeyError 缺陷]**：
  - **缺陷背景与堆栈分析**：
    - 用户点击【AI 智能精选推荐看板】中的“生成最新推荐”按钮时报错崩溃：
      ```text
      KeyError: '\n  "market_summary"'
      ```
    - 根本原因：`app/ai/prompts.py` 中的 `RECOMMEND_SYSTEM_PROMPT` 内置了结构化 JSON 输出示例，其中未经转义的单花括号 `{...}` 被 Python 的 `str.format()` 机制错误识别为格式化参数占位符，从而引发 `KeyError`。
  - **修复措施与架构强化**：
    1. **Prompt 模板规范转义 ([app/ai/prompts.py](file:///d:/AI/stockAnalasis/app/ai/prompts.py))**：
       - 将 `RECOMMEND_SYSTEM_PROMPT` 内 JSON 示例模板的所有花括号严格转义为 `{{` 与 `}}`，杜绝任何调用 `.format()` 时的语义歧义。
    2. **安全替换机制 ([app/services/recommend_service.py](file:///d:/AI/stockAnalasis/app/services/recommend_service.py))**：
       - 将 `RECOMMEND_SYSTEM_PROMPT.format(learned_skills_block=skills_block)` 改用安全的字符串定向替换 `replace("{learned_skills_block}", skills_block)`。
    3. **页面异常防御性捕获 ([app/ui/pages/recommend.py](file:///d:/AI/stockAnalasis/app/ui/pages/recommend.py))**：
       - 在 `refresh_recommendations()` 增加 `except Exception as e` 捕获块，记录结构化错误日志并在界面优雅展示状态提示，避免静默挂起。
  - **实机运行与截图核验**：
    - 实机触发“生成最新推荐”，服务正常完成复合量化打分与大模型语义归因，界面成功渲染推荐卡片列表（包含综合评分、核心推荐理由、风险提示与深度研判入口）；
    - 全量自动化测试保持 100% 通过。
- **2026-09-20 [软件版本号正式升级至 v1.1.0 并发布对应 Git Tag]**：
  - **升级原因与范畴划分**：
    - 针对近期连续完成的【个股研判自选股下拉联动】、【仿真下单自选股快速点选】、【虚拟操盘 0 延迟秒开性能架构重构】等向下兼容的重大交互与架构增强，以及多项视觉与语法缺陷修复，严格遵循 SemVer 2.0.0 规范，将客户端次版本号（MINOR）由 `1.0.0` 递增至 `1.1.0`。
  - **落地工作**：
    1. **全局版本常量对齐 ([app/core/config.py](file:///d:/AI/stockAnalasis/app/core/config.py))**：
       - 将 `APP_VERSION` 升级为 `"1.1.0"`，主界面与系统元数据自动同步展示 `智能分析终端 v1.1.0`；
    2. **更新日志版本归档 ([CHANGELOG.md](file:///d:/AI/stockAnalasis/CHANGELOG.md))**：
       - 正式划定 `[1.1.0] - 2026-09-20` 发行版节点，详尽归档新增能力、性能优化与修复列表；
    3. **Git 版本标签打标与远程推送**：
       - 创建正式带注释标签 `v1.1.0`，并同步推送至 GitHub 远程仓库。
- **2026-09-20 [iPhone 移动端适配与 PWA 架构头脑风暴设计落地]**：
  - **背景与方案选型**：
    - 用户提出在 iPhone 上使用 StockAI 并考虑 Sideloadly 侧载；经系统性头脑风暴深入探讨 iOS 封闭沙盒对桌面 PySide6 的限制及免费个人证书 7 天掉签痛点，最终锁定“方案 A：FastAPI 嵌入式服务 + 移动端响应式 PWA（添加到主屏幕）”。
  - **设计归档与架构规范 ([项目设计文档.md](file:///d:/AI/stockAnalasis/%E9%A1%B9%E7%9B%AE%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md))**：
    - 正式追加第 8 章，明确单页移动端 UI、4 选项卡流式交互、ECharts 触控 K 线图表、FastAPI 接口与静态 PWA 资产一体化托管、局域网自发现与二维码扫码连接机制。
- **2026-09-20 [iPhone 移动端 PWA 适配与局域网服务全套落地]**：
  - **模块定位与架构复用**：
    - 为满足用户在 iPhone 上无缝监控行情、研判自选与操盘建仓的诉求，在 `master` 分支全面落地 B/S 架构与 iOS PWA（添加到主屏幕）技术方案，彻底免除个人证书签名与 7 天掉签烦恼。
  - **核心模块与编码实现**：
    1. **后端 RESTful 异步服务 ([app/web/api.py](file:///d:/AI/stockAnalasis/app/web/api.py))**：
       - 基于 FastAPI 构建，直接复用底层数据池、自选股、K 线计算与虚拟操盘；
       - 包含四大核心指数与全市场涨跌统计（`/api/market/overview`）、自选股增删（`/api/watchlist`）、精选推荐（`/api/recommend`）、K 线指标（`/api/stock/{symbol}/kline`）、账户概况（`/api/trading/summary`）与市价买入、一键平仓（`/api/trading/buy`, `/api/trading/close`）；
       - 挂载静态资源目录 `app/web/static/`。
    2. **局域网探针与二维码服务 ([app/web/server.py](file:///d:/AI/stockAnalasis/app/web/server.py))**：
       - 自动探查本机真实活跃局域网 IP，生成终端 ASCII 二维码与供桌面渲染的 Base64 PNG 图片；
       - 提供独立主进程阻塞启动与非阻塞后台守护线程双启动模式。
    3. **移动端 PWA 前端单页 ([app/web/static/](file:///d:/AI/stockAnalasis/app/web/static/))**：
       - 视口深度适配 iPhone 刘海、灵动岛与底部 Home Indicator 安全区（`safe-area-inset`）；
       - 4 大 Tab 流式触控切换（大盘自选、智能推荐、个股研判、虚拟操盘）；
       - 高性能 HTML5 Canvas 自绘 50 日交互式 K 线（红涨绿跌蜡烛图 + MA5 均线）；
       - 底部呼出式买入建仓抽屉，支持从自选股快捷下拉点选并自动联动回填代码；
       - 包含标准 `manifest.json` 与 192x192 / 512x512 高清深色金融图标。
    4. **启动引导与桌面客户端无缝联动**：
       - 根目录提供命令行独立启动入口 [`run_mobile_server.py`](file:///d:/AI/stockAnalasis/run_mobile_server.py)；
       - 在桌面端系统设置 ([app/ui/pages/settings.py](file:///d:/AI/stockAnalasis/app/ui/pages/settings.py)) 中新增移动端服务控制卡片，一键启停并在界面展示高清专属二维码与局域网 IP。
  - **测试与实机视觉核验**：
    - 编写并执行自动化测试套件 `tests/test_mobile_api.py`，涵盖系统状态、大盘多空、自选股、操盘账户与 PWA 静态资源，10 项自动化测试全量通过；
    - 使用 Playwright 模拟 iPhone 14 Pro 视口（393 x 852），对市场自选、智能推荐、个股研判与虚拟操盘 4 个页面全部完成实机渲染截图核验，界面优雅饱满、交互流畅无溢出。
- **2026-09-20 [iPhone 移动端全景大盘看板与拼音首字母模糊查询落地]**：
  - **背景与方案选型**：
    - 针对移动端监控全市场全貌与极速寻股诉求，完成头脑风暴讨论：
      1. 底部导航栏扩展为 5 大 Tab 布局（全景大盘、我的自选、精选推荐、个股研判、虚拟操盘）；
      2. 顶部搜索框键入拼音首字母即刻在下方浮动展示 Top 8 匹配联想面板，支持一键加自选与点击穿透个股研判；
      3. 架构上采用轻量预计算拼音索引（`GET /api/stock/search-index`，约 80 KB），前端首屏一次性加载后在内存中毫秒级（$< 2$ ms）零网络往返正则匹配；全景大盘提供 4 大多因子排行榜（`GET /api/market/rankings`，涵盖涨幅榜、跌幅榜、成交额榜、换手率榜，每榜切片前 50 支）。
  - **架构交互流图**：
    ```mermaid
    graph LR
        User[用户在搜索框键入拼音简拼 如 PAYH] --> Event[前端 input 实时防抖监听]
        Event --> LocalIndex[(前端内存 searchIndex 5565 支标的三元组)]
        LocalIndex --> Match[正则零往返快速匹配 < 2ms]
        Match --> Dropdown[浮出 Top 8 联想面板: 000001 平安银行]
        Dropdown -->|点击加自选| AddWL[POST /api/watchlist]
        Dropdown -->|点击整行| JumpDetail[切换至 Tab 4 个股研判加载 50 日 K 线]
    ```
  - **核心编码落地**：
    1. **后端索引与排行榜 API ([app/web/api.py](file:///d:/AI/stockAnalasis/app/web/api.py))**：
       - 基于 `pypinyin` 库提取全市场 5,565 支 A 股中文简称拼音首字母，支持 `ST`、英文后缀及多音字分词；
       - 实现 `_search_index_cache` 单例缓存，对外暴露 `GET /api/stock/search-index`；
       - 实现 `GET /api/market/rankings`，支持 `gainers`、`losers`、`volume`、`turnover` 4 大多因子排行榜切片与金额格式化（亿/万）。
    2. **前端 5-Tab 布局与全景大盘看板 ([app/web/static/index.html](file:///d:/AI/stockAnalasis/app/web/static/index.html))**：
       - 导航栏扩展为 5 个 Tab；
       - 新增全景大盘独立视图，集成四大核心指数、全市场多空对比条与 4 大排行榜药丸胶囊切换栏（Pills）；
       - 独立我的自选视图。
    3. **视觉风格与微交互 ([app/web/static/css/style.css](file:///d:/AI/stockAnalasis/app/web/static/css/style.css))**：
       - 新增顶部搜索输入框与毛玻璃悬浮联想下拉面板样式（`.search-dropdown`）；
       - 新增药丸切换胶囊样式（`.ranking-pill`、`.ranking-pill.active`）；
       - 新增金银铜排名前三名渐变徽章（`.rank-badge.rank-1/2/3`）。
    4. **前端交互逻辑与搜索过滤引擎 ([app/web/static/js/app.js](file:///d:/AI/stockAnalasis/app/web/static/js/app.js))**：
       - 启动时异步预取全量拼音索引 `state.searchIndex`；
       - 防抖监听搜索框，支持 6 位数字代码、拼音首字母简拼与汉字简称模糊过滤；
       - 联想卡片支持一键加自选/取消自选与点击直达个股研判；
       - 全景大盘 4 大榜单药丸一键切换。
    5. **控制台编码保护与服务稳健性升级 ([run_mobile_server.py](file:///d:/AI/stockAnalasis/run_mobile_server.py), [app/web/server.py](file:///d:/AI/stockAnalasis/app/web/server.py))**：
       - 移除控制台打印语句中的 Emoji，并对 `print_ascii` 增加 GBK 终端异常保护，彻底杜绝 Windows 控制台 `UnicodeEncodeError` 崩溃。
  - **测试与验证结果**：
    - 执行 `pytest tests/test_mobile_api.py`，全量 8 项测试用例全部 PASSED；
    - 使用 Playwright 模拟真实 iPhone 14 Pro 视口（393 x 852），完成 5 组全量实机交互核验并截图归档：
      - 全景大盘与今日涨幅榜 (`iphone_pwa_market_rankings.png`)；
      - 全景大盘成交额排行榜 (`iphone_pwa_volume_rankings.png`)；
      - 拼音首字母输入 `PAYH` 悬浮联想面板 (`iphone_pwa_pinyin_search_payh.png`)；
      - 点击联想结果穿透跳转至个股深度研判及 K 线加载 (`iphone_pwa_detail_jump.png`)；
      - 独立自选股池列表与一键操作 (`iphone_pwa_watchlist_tab.png`)。
- **2026-09-20 [iPhone 移动端虚拟操盘 AI 模块全面落地 (人机 PK / 自动建仓 / 军规库)]**：
  - **背景与问题定位**：
    - 用户反馈在移动端虚拟操盘页面中无法看到 AI 相关的操盘模块（原先仅单向展示人类主观操盘账户）；
    - 需将桌面端成熟的“人机双轨操盘体系”、“AI 一键自动建仓 (AutoTrader)”与“AI 实战反思操盘军规经验库 (Skills)”无缝移植至移动端。
  - **架构交互流图**：
    ```mermaid
    graph LR
        User[用户点击顶部药丸] -->|切换为 AI 智能操盘| State[state.currentTradeAccount = AI]
        State --> Banner[资产卡片转为紫色科技霓虹主题 + 展示 AI 自动建仓入口]
        State --> PKBar[更新人机收益 PK 战报: 人类 +0.08% VS AI +2.94%]
        State --> Positions[展示 AI 5 支量化持仓明细]
        State --> Skills[拉取 GET /api/trading/skills 渲染实战军规卡片]
        
        ClickAuto[点击 AI 一键全自动计算建仓] --> PostAuto[POST /api/trading/auto-trade]
        PostAuto --> AutoEngine[AutoTrader: 风控门槛校验 + 5565 支多因子粗排 + 军规注入裁决]
        AutoEngine --> Modal[弹出 AI 自动建仓决策执行报告抽屉]
    ```
  - **核心编码落地**：
    1. **后端 API 扩展 ([app/web/api.py](file:///d:/AI/stockAnalasis/app/web/api.py))**：
       - `GET /api/trading/comparison`：返回人类与 AI 账户的总资产、累计收益率、持仓数与可用现金对比数据；
       - `GET /api/trading/skills`：调用 `skill_engine.list_all_skills()` 返回从实战平仓中反思沉淀的实战军规；
       - `POST /api/trading/auto-trade`：驱动 `auto_trader.execute_auto_trading(account_type="AI")` 执行自动建仓管线并返回报告；
       - 订单实体与买卖接口全面支持 `account_type: str = "MANUAL" | "AI"`，并修复 `refresh_positions_quotes` 方法调用。
    2. **前端结构扩展 ([app/web/static/index.html](file:///d:/AI/stockAnalasis/app/web/static/index.html))**：
       - 在 `tab-trade` 顶部集成人机双轨药丸切换栏（`[ 👤 人类主观操盘 ] [ 🤖 AI 智能操盘 ]`）；
       - 新增人机收益率 PK 战报条（`.pk-battle-bar`）；
       - 新增 AI 模式下的自动建仓操作条（`.ai-action-bar`）与 AI 实战反思军规经验库展示区（`.ai-skills-section`）；
       - 新增 AI 自动建仓决策报告抽屉组件（`#auto-trade-modal`）。
    3. **科技感金融样式 ([app/web/static/css/style.css](file:///d:/AI/stockAnalasis/app/web/static/css/style.css))**：
       - 增加 AI 科技渐变紫主题（`.portfolio-banner.ai-theme`）；
       - 增加人机切换 Pill 动画、PK 战报对比样式、军规卡片（`.skill-card`）及自动建仓卡片样式。
    4. **前端交互与状态机 ([app/web/static/js/app.js](file:///d:/AI/stockAnalasis/app/web/static/js/app.js))**：
       - 实现 `switchTradeAccount(accountType)` 状态切换与卡片主题切换；
       - 实现 `loadTradingSkills()` 异步拉取并渲染军规；
       - 实现 `triggerAutoTrade()` 异步执行 AI 决策并在抽屉中高亮展示买入标的、评分与军规归因；
       - 修复持仓卡片中 `total_amount` 与 `floating_pnl_pct` 字段读取与平仓股数绑定。
    5. **自动化测试与实机验证 ([tests/test_mobile_api.py](file:///d:/AI/stockAnalasis/tests/test_mobile_api.py), [tests/test_iphone_ai_trading.py](file:///d:/AI/stockAnalasis/tests/test_iphone_ai_trading.py))**：
       - 新增 `test_ai_trading_and_skills_api` 自动化用例，9 项测试 100% 通过；
       - 使用 Playwright 模拟真实 iPhone 14 Pro 视口（393 x 852），截取人类主观操盘与 PK 战报、AI 智能操盘模式与 AI 自动建仓决策报告弹窗，全流程验证通过。
- **2026-09-21 [修复桌面端数据表格涨跌幅与最新价文字被 QSS 强制覆盖为白色的缺陷]**：
  - **缺陷现象与根因剖析**：
    - 用户反馈大盘看板等数据表格中，“涨跌幅”及“最新价”未能按照中国股市标准显示红（涨）绿（跌）文字，所有数值均呈现单一白色。
    - 经排查定位，在 [`app/ui/pages/dashboard.py`](file:///d:/AI/stockAnalasis/app/ui/pages/dashboard.py)、[`app/ui/pages/watchlist.py`](file:///d:/AI/stockAnalasis/app/ui/pages/watchlist.py) 及 [`app/ui/pages/screener.py`](file:///d:/AI/stockAnalasis/app/ui/pages/screener.py) 代码中，均已显式根据涨跌正负调用了 `item.setForeground(QColor("#F87171"))`（明亮红）与 `item.setForeground(QColor("#34D399"))`（翡翠绿）。
    - 根本原因在于全局样式表 [`app/ui/theme.py`](file:///d:/AI/stockAnalasis/app/ui/theme.py) 的 `QTableWidget::item, QTableView::item` 和 `QTableWidget::item:alternate, QTableView::item:alternate` 选择器中硬编码了 `color: #F1F5F9;` 以及 `:hover` 中的 `color: #FFFFFF;`。在 Qt 样式引擎（QStyledItemDelegate）渲染规则中，子选择器 `::item` 上的 CSS `color` 会强制覆盖数据项的 `Qt.ForegroundRole`，导致所有正负着色逻辑被全量刷白。
  - **修复方案**：
    1. **样式表解耦 ([app/ui/theme.py](file:///d:/AI/stockAnalasis/app/ui/theme.py))**：
       - 从 `QTableWidget::item` 和 `QTableWidget::item:alternate` 选择器中移除硬编码的 `color` 属性，保留单元格内边距 `padding: 6px 8px;` 及深色交替行背景；
       - 从 `:hover` 和 `:selected` 伪类中移除硬编码的 `color: #FFFFFF;`，仅保留背景色渐变过渡（`#222836` 与 `#1E3A8A`），避免鼠标悬浮或选中时文字闪烁覆盖；
       - 由父级 `QTableWidget` 保留基准 `color: #F8FAFC;` 作为默认文本颜色（应用于代码、简称、成交量等无涨跌属性的列）。
    2. **全页面联动收益**：
       - **市场全景看板 (Dashboard)**：最新价与涨跌幅恢复明亮红（涨）、翡翠绿（跌）、浅冷灰（平）；
       - **自选股票池 (Watchlist)**：最新价与涨跌幅恢复红绿显示；
       - **智能选股 (Screener)**：筛选结果涨跌幅与价格恢复红绿显示；
       - **虚拟操盘 (Virtual Trading)**：浮动盈亏（金额及比例）恢复红绿显示，可卖锁定期展示明黄提示。
- **2026-09-21 [AI 自动操盘、双层策略自进化与实盘分级接管系统架构设计]**：
  - **战略目标与需求沉淀**：
    - 面向最终“AI 接管真实股票账号操作”的终极目标，基于头脑风暴（Brainstorming）完成系统全生命周期的顶层设计与技术路线锁定；
    - 确立“盘中节律执行 + 盘后沙盒多因子遗传调优 + 实战军规淘汰晋级”的双循环进化机制。
  - **四级实盘演进路线 (L0 -> L1 -> L2 -> L3)**：
    - `L0 虚拟盘双轨`：人手主观与 AI 智能账户并行，执行严格 A 股交易制度（T+1、整手、印花税佣金）；
    - `L1 自主达标考核`：连续 30 个交易日实盘模拟，要求夏普比率 > 1.5 且最大回撤 < 8%；
    - `L2 实盘人机半自动`：AI 生成交易信号与仓位，推送到移动端/桌面端一键授权后报单券商；
    - `L3 实盘全自动托管`：接入 QMT/MiniQMT，配置大盘暴跌熔断、单日账户回撤熔断与全局急停断电开关。
  - **架构成果归档**：
    - 完整架构设计说明书已持久化保存至 [`docs/autonomous_trading_architecture.md`](file:///d:/AI/stockAnalasis/docs/autonomous_trading_architecture.md)。
- **2026-09-21 [自主操盘常驻调度引擎驱动、双端状态监控与全局急停断电熔断 (Milestone 1)]**：
  - **业务背景与核心诉求**：
    - 实现 AI 自主操盘无人值守接管，必须摆脱人工点击单次触发的限制，建立常驻后台交易时钟驱动机制。
    - 必须精确对齐 A 股盘中交易节律，并在桌面端与移动端提供实时的托管状态感知、一键启停和全局物理级急停断电熔断（Kill Switch）。
  - **核心调度引擎落地 ([app/services/scheduler_service.py](file:///d:/AI/stockAnalasis/app/services/scheduler_service.py))**：
    - 实现单例 `AutonomousScheduler` 与状态机 `SchedulerState`（`STOPPED` / `RUNNING` / `PAUSED` / `EMERGENCY`）；
    - 实现 A 股交易日与盘中时段精确裁决（`is_trade_day`、`is_trade_time`、`get_current_phase_info`）；
    - 守护线程按 10 秒时钟轮询四大节律事件：
      1. `09:35`：早盘进攻与冲高止盈，驱动多因子粗排与军规建仓管线；
      2. `10:00 - 14:40`：每 15 分钟轻量巡检硬止损（-5%）与 MA20 破位平仓；
      3. `14:45`：尾盘形态定型与次日跨日建仓；
      4. `15:30`：收盘全天交易归因复盘与军规自进化整理；
    - 建立全局急停断电机制（`emergency_stop()` 与 `reset_emergency_stop()`），在熔断状态下强行锁死所有自动化线程并阻断启动，内存维护最近 50 条审计流水日志。
  - **后端 API 路由扩展 ([app/web/api.py](file:///d:/AI/stockAnalasis/app/web/api.py))**：
    - 挂载 4 个交易调度管理端点：
      - `GET /api/trading/scheduler/status`：获取当前所处交易节律、下一预定动作、运行状态与审计日志；
      - `POST /api/trading/scheduler/toggle`：开启或暂停 AI 无人值守交易托管；
      - `POST /api/trading/scheduler/emergency-stop`：一键触发全局紧急急停断电熔断；
      - `POST /api/trading/scheduler/reset-emergency`：人工确认解除急停锁定。
  - **移动端 PWA 交互与视觉实现 ([app/web/static/](file:///d:/AI/stockAnalasis/app/web/static/))**：
    - 在 `index.html` 的 AI 操盘操作区顶部新增 `.scheduler-card` 状态卡片；
    - 在 `style.css` 中引入状态呼吸灯动效（`.dot-running` 绿色脉冲、`.dot-emergency` 红色闪烁警示、`.dot-stopped` 冷灰待机）；
    - 在 `app.js` 中实现 `loadSchedulerStatus()`、`toggleAutonomousScheduler()` 与 `triggerEmergencyKill()`，在急停状态下动态切换按钮文案与响应事件。
  - **桌面端 PySide6 联动 ([app/ui/pages/virtual_trading.py](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py))**：
    - 顶部操作栏挂载【开启无人托管】与【急停】按键；
    - 在 `load_local_data` 与交易刷新生命周期中绑定 `_update_scheduler_ui`；
    - 实现 `_on_toggle_scheduler` 与 `_on_emergency_kill`，提供二次高危确认弹窗与状态持久同步。
  - **自动化测试与实机验证**：
    - 新增单元测试套件 [`tests/test_scheduler.py`](file:///d:/AI/stockAnalasis/tests/test_scheduler.py)，涵盖状态机转换、交易时间判定、阶段描述提取与 4 个 API 路由端点验证，8 项测试 100% 通过；
    - 联合回归运行 `test_auto_sell.py` 与 `test_mobile_api.py`，累计 23 项测试全量通过；
    - 借助 Playwright 截取 iPhone 14 Pro 视口真实运行截图：
      - 待机就绪状态：[`iphone_scheduler_standby.png`](file:///C:/Users/Administrator/.gemini/antigravity-ide/brain/5e5def10-41bd-4e75-af5e-5503515c3964/iphone_scheduler_standby.png)
      - 运行中脉冲状态：[`iphone_scheduler_running.png`](file:///C:/Users/Administrator/.gemini/antigravity-ide/brain/5e5def10-41bd-4e75-af5e-5503515c3964/iphone_scheduler_running.png)
      - 全局急停断电熔断状态：[`iphone_scheduler_emergency.png`](file:///C:/Users/Administrator/.gemini/antigravity-ide/brain/5e5def10-41bd-4e75-af5e-5503515c3964/iphone_scheduler_emergency.png)
- **2026-09-21 [修复桌面端开启无人托管 AttributeError: 'str' object has no attribute 'value' 缺陷]**：
  - **问题根因**：桌面端 `virtual_trading.py` 中对 `SchedulerState.RUNNING.value` 进行属性取值，而 `scheduler_service.py` 中的 `SchedulerState` 原为纯类字符串常量定义，未继承 `Enum`，导致字符串对象调用 `.value` 抛出 AttributeError。
  - **修复措施**：
    1. 将 [`app/services/scheduler_service.py`](file:///d:/AI/stockAnalasis/app/services/scheduler_service.py) 中的 `SchedulerState` 继承自 `str, Enum`，使其既作为字符串值直接参与逻辑比较，又兼容 `.value` 属性读取；
    2. 在 [`app/ui/pages/virtual_trading.py`](file:///d:/AI/stockAnalasis/app/ui/pages/virtual_trading.py) 中规范状态判断逻辑，直接与枚举对象比对（`state == SchedulerState.RUNNING`），增强代码健壮性；
    3. 执行单元测试验证通过，状态切换正常。
- **2026-09-21 [增加移动端 Web 服务 8000 端口占用预检与防冲突优雅提示]**：
  - **问题根因**：用户在桌面端【设置】点击“启动移动端服务”或再次在终端运行 `run_mobile_server.py` 时，若后台已有正在运行的 StockAI 实例或其他程序占用了 `8000` 端口，Uvicorn 在尝试 `bind` 时将抛出 `[Errno 10048] [winerror 10048] 每个套接字地址只允许使用一次`。
  - **优化方案**：
    1. 在 [`app/web/server.py`](file:///d:/AI/stockAnalasis/app/web/server.py) 的 `MobileServerManager.start()` 中增加 `socket` 端口预检；
    2. 检测到 8000 端口被占用时，避免抛出崩溃性异常，而是输出温和告警，并提示用户服务可能已经在后台运行，可直接通过浏览器或局域网访问；
    3. 若为桌面端后台守护线程模式，自动同步更新 UI 状态为已连接，避免弹窗打断用户操作。
- **2026-09-23 [修复 AI 托管自动建仓在模型超时时本地量化兜底失效且空仓观望缺陷]**：
  - **故障现象**：AI 接管运行期间剩余资金充足，但一直没有新建仓。调度日志显示 09:35 进攻建仓调用大模型 `qwen3.8-vllm` 出现 `Request timed out`，系统随后切换为“启用本地多因子量化评选引擎进行自动建仓决策...”，但后续并未产生任何买入撮合，直接跳过并进入后续风控巡检。
  - **排查与根因分析**：
    1. **核心缺陷**：[`app/services/auto_trader.py`](file:///d:/AI/stockAnalasis/app/services/auto_trader.py) 中的 `_fallback_local_evaluation()` 方法在完成多因子评分前 2 支候选标的字典构建后，**缺失了 `return res` 语句**，导致该函数默认隐式返回 `None`；
    2. **降级击穿**：当大模型因网络延迟或并发导致一次性请求超时时，建仓管线试图调用本地量化兜底，但由于返回了 `None`，触发了 `if not decisions:` 条件，被系统判定为“候选标的均未通过操盘军规胜率检验，系统决定空仓观望”，导致整轮建仓直接退出；
    3. **时钟节律限制**：根据 [`AutonomousScheduler`](file:///d:/AI/stockAnalasis/app/services/scheduler_service.py) 节律设定，自动建仓仅在 `09:35` 早盘和 `14:45` 尾盘各触发一次，其余盘中每 15 分钟均为“持仓风控巡检（仅负责平仓避险）”。因此 09:35 遭遇该缺陷退出后，整个上午均处于巡检状态，不会再次尝试建仓，导致资金持续闲置。
  - **修复措施**：
    1. 在 `_fallback_local_evaluation()` 末尾显式添加 `return res`，并在函数内增加兜底选股结果的关键 Debug 日志；
    2. 在 `execute_auto_trading()` 裁决决策判断点补充 Warning 与 Info 级别日志，增强决策链路的可观察性；
    3. 编写回归测试用例 [`tests/test_fallback_buying.py`](file:///d:/AI/stockAnalasis/tests/test_fallback_buying.py)，模拟大模型超时场景，全链路验证本地多因子量化选股与 A 股仿真撮合买入，测试 100% 通过。
- **2026-09-23 [大模型实操调用实测、耗时瓶颈分析与超时窗口专项优化]**：
  - **实测执行与连通性验证**：
    1. 连通性诊断：目标端点 `http://172.16.154.242:11434/v1`，模型 `qwen3.8-vllm`，三项诊断指标（Latency、Streaming、JSON 解析）全部通过；
    2. 实战 Prompt 耗时测量：首字用时（TTFT）为 11.09 秒，带军规与候选池的建仓推理生成总耗时为 33.34 秒；
    3. 真实建仓端到端撮合：成功在 34 秒内完成 10 支标的裁决，成功提取结构化 JSON 并撮合买入 2 支优质标的（上海瀚讯 600 股、唯科科技 800 股），均符合操盘军规突破战则。
  - **超时参数瓶颈与调优**：
    1. 原配置中大模型客户端超时绑定为普通数据请求的 3 倍（`config.request_timeout_seconds * 3` 即 30 秒），而私有部署 `qwen3.8-vllm` 在推理 10 支标的与操盘军规时的耗时处于 30~45 秒区间，极易触碰 30 秒硬超时红线；
    2. 在 [`app/core/config.py`](file:///d:/AI/stockAnalasis/app/core/config.py) 中新增大模型专用超时时长配置 `llm_timeout_seconds = 120`；
    3. 在 [`app/ai/llm_client.py`](file:///d:/AI/stockAnalasis/app/ai/llm_client.py) 中解耦普通网络请求与 LLM 超时，统一使用 120 秒安全窗口，彻底消除网络与长推理阶段的偶发性超时问题。
- **2026-09-23 [修复仿真撮合买入时股票简称缺失导致显示为“标的代码”缺陷]**：
  - **问题分析**：在 `trading_service.py` 的 `buy_stock` 函数中，若外部传入自定义成交价格 `custom_price`，原逻辑会直接跳过标的真实名称获取分支，导致持仓表与成交流水表中股票名称存为占位符“标的+代码”（例如“标的301057”）；
  - **修复实现**：
    1. 为 `buy_stock` 补充 `name` 入参并在 `auto_trader.py` 撮合调用时直接透传标的真实名称；
    2. 在缺少名称或名称为占位符时，不论是否传入 `custom_price` 均通过定向盘口接口或基础数据源补充真实中文简称；
    3. 在 `refresh_positions_quotes()` 批量刷新盘口时，增加对存量占位名称的自动修正逻辑；
    4. 存量持仓与成交流水已全量刷新为规范中文名称（唯科科技、腾景科技）。


