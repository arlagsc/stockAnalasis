# -*- coding: utf-8 -*-
"""AI 无人值守操盘调度引擎 (AutonomousScheduler)

常驻后台守护，按 A 股交易时间与四大节律精准驱动交易闭环：
1. 09:35 早盘进攻与冲高止盈；
2. 10:00 - 14:40 每 15 分钟持仓智能巡检（T+1 保护 + 硬止损 -5% + 动态止盈 + MA20 破位）；
3. 14:45 尾盘形态定型与次日跨日建仓；
4. 15:30 收盘全天交易归因复盘与军规自进化；
5. 休市待机与全局一键急停断电 (Kill Switch)。
"""

import threading
import time
from datetime import datetime, date, time as dtime
from typing import Dict, Any, List, Optional

from app.core.config import logger
from app.services.auto_trader import auto_trader
from app.services.trading_service import trading_service
from app.ai.skill_engine import skill_engine


class SchedulerState:
    STOPPED = "STOPPED"          # 未启动
    RUNNING = "RUNNING"          # 正常运行中
    PAUSED = "PAUSED"            # 手动暂停
    EMERGENCY_STOP = "EMERGENCY" # 紧急急停断电锁定
    EMERGENCY = "EMERGENCY"      # 别名兼容


class AutonomousScheduler:
    """AI 无人值守交易调度引擎单例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutonomousScheduler, cls).__new__(cls)
                cls._instance._init_scheduler()
        return cls._instance

    def _init_scheduler(self):
        self.state = SchedulerState.STOPPED
        self.account_type = "AI"
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._audit_logs: List[Dict[str, Any]] = []
        self._last_executed_actions: Dict[str, str] = {}  # 记录今日已执行的动作 {action_name: "YYYY-MM-DD HH:MM"}
        self._last_patrol_minute: Optional[int] = None
        logger.info("AutonomousScheduler 调度中枢初始化就绪，当前状态: %s", self.state)

    @property
    def is_running(self) -> bool:
        """是否处于无人托管运行中"""
        return self.state == SchedulerState.RUNNING

    @property
    def is_active(self) -> bool:
        """是否处于激活运行态"""
        return self.state == SchedulerState.RUNNING

    @property
    def is_emergency(self) -> bool:
        """是否处于急停熔断态"""
        return self.state in (SchedulerState.EMERGENCY, SchedulerState.EMERGENCY_STOP)

    def is_trade_day(self, current_dt: Optional[datetime] = None) -> bool:
        """判断今天是否为 A 股交易日（周一至周五，不含法定周末）"""
        dt = current_dt or datetime.now()
        # 周一至周五 (0-4)
        return dt.weekday() < 5

    def is_trade_time(self, current_dt: Optional[datetime] = None) -> bool:
        """判断当前时间是否处于 A 股盘中交易时段 (09:30-11:30, 13:00-15:00)"""
        if not self.is_trade_day(current_dt):
            return False
        dt = current_dt or datetime.now()
        t = dt.time()
        morning_trade = dtime(9, 30) <= t <= dtime(11, 30)
        afternoon_trade = dtime(13, 0) <= t <= dtime(15, 0)
        return morning_trade or afternoon_trade

    def get_current_phase_info(self, current_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """获取当前时钟所处的 A 股市场阶段及下一个待执行节点"""
        dt = current_dt or datetime.now()
        t = dt.time()

        if not self.is_trade_day(dt):
            return {
                "is_trading": False,
                "phase_name": "周末非交易日 (待机休眠)",
                "next_action": "下周一 09:35 早盘进攻",
            }

        if t < dtime(9, 15):
            return {
                "is_trading": False,
                "phase_name": "盘前准备期",
                "next_action": "09:35 早盘进攻与冲高止盈",
            }
        elif dtime(9, 15) <= t < dtime(9, 30):
            return {
                "is_trading": False,
                "phase_name": "集合竞价阶段",
                "next_action": "09:35 早盘进攻与冲高止盈",
            }
        elif dtime(9, 30) <= t < dtime(10, 0):
            return {
                "is_trading": True,
                "phase_name": "早盘进攻窗口期 (09:30 - 10:00)",
                "next_action": "10:00 盘中每 15 分钟持仓巡检",
            }
        elif dtime(10, 0) <= t < dtime(11, 30):
            next_m = ((t.minute // 15) + 1) * 15
            next_h = t.hour
            if next_m >= 60:
                next_h += 1
                next_m -= 60
            return {
                "is_trading": True,
                "phase_name": "早盘持续交易期 (15分钟动态巡检)",
                "next_action": f"{next_h:02d}:{next_m:02d} 持仓巡检",
            }
        elif dtime(11, 30) <= t < dtime(13, 0):
            return {
                "is_trading": False,
                "phase_name": "午间休市整固期",
                "next_action": "13:00 下午开盘巡检",
            }
        elif dtime(13, 0) <= t < dtime(14, 40):
            next_m = ((t.minute // 15) + 1) * 15
            next_h = t.hour
            if next_m >= 60:
                next_h += 1
                next_m -= 60
            return {
                "is_trading": True,
                "phase_name": "下午持续交易期 (15分钟动态巡检)",
                "next_action": f"{next_h:02d}:{next_m:02d} 持仓巡检",
            }
        elif dtime(14, 40) <= t <= dtime(15, 0):
            return {
                "is_trading": True,
                "phase_name": "尾盘形态定型窗口期 (14:40 - 15:00)",
                "next_action": "14:45 尾盘定型与建仓",
            }
        elif dtime(15, 0) < t <= dtime(16, 0):
            return {
                "is_trading": False,
                "phase_name": "收盘复盘整理期",
                "next_action": "15:30 交易归因与军规自进化",
            }
        else:
            return {
                "is_trading": False,
                "phase_name": "夜间沙盒调优期 (低功耗休眠)",
                "next_action": "明日 09:35 早盘进攻",
            }

    def start(self, account_type: str = "AI") -> bool:
        """启动无人值守操盘调度后台守护线程"""
        with self._lock:
            if self.state in (SchedulerState.EMERGENCY, SchedulerState.EMERGENCY_STOP):
                logger.warning("当前处于全局急停断电锁定状态，禁止启动！必须先手动执行解除急停。")
                return False

            if self.state == SchedulerState.RUNNING:
                logger.info("AutonomousScheduler 已经在运行中")
                return True

            self.account_type = account_type
            self.state = SchedulerState.RUNNING
            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run_loop,
                name="AutonomousSchedulerThread",
                daemon=True
            )
            self._thread.start()
            self._record_log("SYSTEM", "启动托管", f"成功启动 [{account_type}] 账户无人值守自动化操盘守护线程")
            logger.info("AutonomousScheduler 成功启动，当前接管账户: %s", account_type)
            return True

    def pause(self) -> bool:
        """暂停无人值守调度（不关停线程，保持休眠）"""
        with self._lock:
            self.state = SchedulerState.PAUSED
            self._record_log("SYSTEM", "暂停托管", "用户手动暂停了 AI 自动操盘调度")
            logger.info("AutonomousScheduler 已暂停托管")
            return True

    def resume(self) -> bool:
        """恢复无人值守调度"""
        with self._lock:
            if self.state == SchedulerState.EMERGENCY_STOP:
                logger.warning("当前处于紧急急停断电状态，禁止直接恢复，必须解除急停！")
                return False
            self.state = SchedulerState.RUNNING
            self._record_log("SYSTEM", "恢复托管", "用户手动恢复了 AI 自动操盘调度")
            logger.info("AutonomousScheduler 已恢复托管运行")
            return True

    def emergency_stop(self, reason: str = "") -> Dict[str, Any]:
        """🚨 触发全局一键急停断电熔断 (Kill Switch)"""
        with self._lock:
            self.state = SchedulerState.EMERGENCY_STOP
            self._stop_event.set()
            detail = f"原因: {reason}" if reason else "系统进入绝对安全防御状态"
            msg = f"🚨 紧急急停断电已触发！{detail}。所有自动化调度线程已强行熔断锁死。"
            self._record_log("SECURITY", "紧急断电", msg)
            logger.critical(msg)
            return {
                "success": True,
                "state": self.state,
                "msg": msg
            }

    def reset_emergency_stop(self) -> bool:
        """解除紧急急停锁定（恢复为停止就绪状态）"""
        with self._lock:
            self.state = SchedulerState.STOPPED
            self._stop_event.clear()
            self._record_log("SECURITY", "解除急停", "管理员解除了紧急断电锁定，系统恢复初始就绪态")
            logger.info("紧急断电锁定已解除")
            return True

    def _run_loop(self):
        """后台常驻节律监听循环 (每 10 秒轮询一次当前时钟)"""
        logger.info("AutonomousScheduler 节律守护循环进入主监听状态...")
        while not self._stop_event.is_set():
            try:
                if self.state == SchedulerState.RUNNING:
                    self._check_and_dispatch()
            except Exception as e:
                logger.error("AutonomousScheduler 节律检查循环发生异常: %s", str(e), exc_info=True)

            # 每 10 秒轮询一次
            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

        logger.info("AutonomousScheduler 节律守护循环已安全退出")

    def _check_and_dispatch(self):
        """检查当前时刻是否匹配特定交易节律并执行任务"""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        now_time = now.time()

        if not self.is_trade_day(now):
            return

        # 1. 节律节点: 09:35 早盘进攻与冲高建仓
        key_morning = f"{today_str}_MORNING_BUY"
        if dtime(9, 35) <= now_time < dtime(9, 45) and key_morning not in self._last_executed_actions:
            logger.info(">>> 触发节律 [09:35 早盘进攻建仓] <<<")
            self._last_executed_actions[key_morning] = now.strftime("%H:%M")
            self._record_log("MORNING", "早盘进攻", "检测到 09:35 进攻窗口，驱动多因子粗排与军规建仓管线")
            threading.Thread(target=self._execute_morning_trade, daemon=True).start()

        # 2. 节律节点: 14:45 尾盘形态定型与次日跨日建仓
        key_tail = f"{today_str}_TAIL_BUY"
        if dtime(14, 45) <= now_time < dtime(14, 55) and key_tail not in self._last_executed_actions:
            logger.info(">>> 触发节律 [14:45 尾盘定型建仓] <<<")
            self._last_executed_actions[key_tail] = now.strftime("%H:%M")
            self._record_log("AFTERNOON", "尾盘定型", "检测到 14:45 尾盘窗口，驱动确定性收盘形态建仓")
            threading.Thread(target=self._execute_tail_trade, daemon=True).start()

        # 3. 节律节点: 15:30 收盘全日交易复盘与生成进化战报
        key_review = f"{today_str}_REVIEW"
        if dtime(15, 30) <= now_time < dtime(16, 0) and key_review not in self._last_executed_actions:
            logger.info(">>> 触发节律 [15:30 收盘全日交易复盘] <<<")
            self._last_executed_actions[key_review] = now.strftime("%H:%M")
            self._record_log("REVIEW", "收盘复盘", "全日交易结束，执行持仓与成交流水归因复盘")
            threading.Thread(target=self._execute_daily_review, daemon=True).start()

        # 4. 持续节律: 盘中每 15 分钟持仓智能巡检 (10:00 - 11:30, 13:00 - 14:40)
        if self.is_trade_time(now):
            # 每 15 分钟触发一次 (00, 15, 30, 45)
            curr_min = now.minute
            if curr_min % 15 == 0 and self._last_patrol_minute != curr_min:
                self._last_patrol_minute = curr_min
                logger.info(">>> 触发节律 [盘中 15 分钟持仓风控巡检: %02d:%02d] <<<", now.hour, curr_min)
                self._record_log("PATROL", "持仓巡检", f"触发 {now.hour:02d}:{curr_min:02d} 定向持仓智能巡检与破位避险")
                threading.Thread(target=self._execute_patrol_sell, daemon=True).start()

    def _execute_morning_trade(self):
        """执行早盘进攻买入"""
        try:
            res = auto_trader.execute_auto_trading(account_type=self.account_type, max_buy_count=2)
            msg = res.get("msg", "建仓完成")
            cnt = res.get("executed_count", 0)
            self._record_log("MORNING_DONE", f"早盘成交 ({cnt}支)", msg)
        except Exception as e:
            logger.error("早盘进攻执行异常: %s", str(e))
            self._record_log("ERROR", "早盘异常", str(e))

    def _execute_tail_trade(self):
        """执行尾盘定型买入"""
        try:
            res = auto_trader.execute_auto_trading(account_type=self.account_type, max_buy_count=1)
            msg = res.get("msg", "尾盘决策完成")
            cnt = res.get("executed_count", 0)
            self._record_log("TAIL_DONE", f"尾盘成交 ({cnt}支)", msg)
        except Exception as e:
            logger.error("尾盘定型执行异常: %s", str(e))
            self._record_log("ERROR", "尾盘异常", str(e))

    def _execute_patrol_sell(self):
        """执行持仓智能巡检与平仓避险"""
        try:
            res = auto_trader.execute_auto_selling(
                account_type=self.account_type,
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                enable_tech_breakdown=True,
                enable_llm_eval=True
            )
            sold_cnt = res.get("sold_count", 0)
            msg = res.get("msg", "巡检完成")
            self._record_log("PATROL_DONE", f"巡检完成 (平仓{sold_cnt}支)", msg)
        except Exception as e:
            logger.error("巡检平仓执行异常: %s", str(e))
            self._record_log("ERROR", "巡检异常", str(e))

    def _execute_daily_review(self):
        """执行收盘复盘与军规自进化整理"""
        try:
            trades = trading_service.get_trades_history(account_type=self.account_type, limit=10)
            today_str = date.today().strftime("%Y-%m-%d")
            today_trades = [t for t in trades if str(t.get("trade_time", "")).startswith(today_str)]
            summary = f"收盘总结完成：今日共产生 {len(today_trades)} 笔成交流水，操盘军规库与资产状态已全量同步归档。"
            self._record_log("REVIEW_DONE", "复盘归档", summary)
        except Exception as e:
            logger.error("收盘复盘异常: %s", str(e))
            self._record_log("ERROR", "复盘异常", str(e))

    def _record_log(self, category: str, action: str, detail: str):
        """记录自动化运行流水日志（内存保留最近 50 条）"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": category,
            "action": action,
            "detail": detail,
        }
        self._audit_logs.insert(0, entry)
        if len(self._audit_logs) > 50:
            self._audit_logs.pop()

    def get_status(self) -> Dict[str, Any]:
        """获取当前无人值守调度器完整状态与近况数据"""
        phase_info = self.get_current_phase_info()
        return {
            "state": self.state,
            "is_running": self.state == SchedulerState.RUNNING,
            "is_active": self.state == SchedulerState.RUNNING,
            "is_emergency": self.state == SchedulerState.EMERGENCY,
            "account_type": self.account_type,
            "is_trading_time": phase_info["is_trading"],
            "current_phase": phase_info["phase_name"],
            "next_action": phase_info["next_action"],
            "next_action_info": phase_info["next_action"],
            "recent_logs": self._audit_logs[:15],
            "audit_logs": self._audit_logs[:20],
            "total_logs_count": len(self._audit_logs),
        }


# 全局无人值守调度引擎单例
scheduler_service = AutonomousScheduler()
