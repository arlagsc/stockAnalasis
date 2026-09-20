# -*- coding: utf-8 -*-
"""基于 PyQtGraph 的高性能金融图表组件

提供 60 FPS 原生金融 K 线交互体验：
1. 主图：蜡烛线（红涨绿跌）、MA5/10/20/60 均线层叠；
2. 副图：成交量柱状图（Volume）与联动缩放；
3. 动态交互：双图联动十字光标（Crosshair）与鼠标悬停量价浮动信息看板。
"""

from typing import Optional
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPicture
import pyqtgraph as pg

# 配置 pyqtgraph 全局暗色属性
pg.setConfigOptions(antialias=True, background="#16181F", foreground="#94A3B8")

class CandlestickItem(pg.GraphicsObject):
    """基于 QPicture 高速批处理绘制的蜡烛线组件"""

    def __init__(self, data):
        super().__init__()
        self.data = data  # List of (t, open, close, min, max)
        self.picture = QPicture()
        self._generate_picture()

    def _generate_picture(self):
        p = QPainter(self.picture)
        pen_up = pg.mkPen("#EF4444", width=1.0)
        brush_up = pg.mkBrush("#EF4444")
        pen_down = pg.mkPen("#10B981", width=1.0)
        brush_down = pg.mkBrush("#10B981")
        w = 0.35

        for t, op, cl, low, high in self.data:
            if cl >= op:
                p.setPen(pen_up)
                p.setBrush(brush_up)
            else:
                p.setPen(pen_down)
                p.setBrush(brush_down)

            # 画上下影线
            p.drawLine(QPointF(t, low), QPointF(t, high))
            # 画实体柱
            p.drawRect(pg.QtCore.QRectF(t - w, op, w * 2, cl - op))

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return pg.QtCore.QRectF(self.picture.boundingRect())

class StockChartWidget(QWidget):
    """专业股票 K 线与指标联动图表控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: Optional[pd.DataFrame] = None
        self._date_strings = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 顶部悬浮信息标签栏
        self.info_panel = QFrame()
        self.info_panel.setStyleSheet("background-color: #1A1D24; border-radius: 4px; padding: 4px;")
        info_layout = QHBoxLayout(self.info_panel)
        info_layout.setContentsMargins(8, 2, 8, 2)
        
        self.lbl_info = QLabel("鼠标悬停查看量价指标")
        self.lbl_info.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: bold;")
        self.lbl_mas = QLabel("")
        self.lbl_mas.setStyleSheet("font-size: 12px;")
        
        info_layout.addWidget(self.lbl_info)
        info_layout.addSpacing(16)
        info_layout.addWidget(self.lbl_mas)
        info_layout.addStretch()
        layout.addWidget(self.info_panel)

        # pyqtgraph GraphicsLayoutWidget
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.glw.ci.layout.setSpacing(0)
        layout.addWidget(self.glw)

        # 主图：K 线与均线 (比例 3)
        self.p_main = self.glw.addPlot(row=0, col=0)
        self.p_main.showGrid(x=True, y=True, alpha=0.15)
        self.p_main.hideAxis("bottom")  # 底部时间轴隐藏，由副图显示

        # 副图：成交量 (比例 1)
        self.glw.nextRow()
        self.p_vol = self.glw.addPlot(row=1, col=0)
        self.p_vol.showGrid(x=True, y=True, alpha=0.15)
        self.p_vol.setMaximumHeight(140)

        # 联动 X 轴
        self.p_vol.setXLink(self.p_main)

        # 十字光标设置
        self.vLine_main = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#64748B", style=Qt.DashLine))
        self.hLine_main = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#64748B", style=Qt.DashLine))
        self.vLine_vol = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#64748B", style=Qt.DashLine))

        self.p_main.addItem(self.vLine_main, ignoreBounds=True)
        self.p_main.addItem(self.hLine_main, ignoreBounds=True)
        self.p_vol.addItem(self.vLine_vol, ignoreBounds=True)

        # 鼠标移动事件监听
        self.p_main.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def load_kline_data(self, df: pd.DataFrame):
        """加载带指标的日 K 线数据并绘制"""
        if df.empty or len(df) < 2:
            return

        self._df = df.reset_index(drop=True)
        self._date_strings = self._df["date"].astype(str).tolist() if "date" in self._df.columns else []

        # 清除旧图元
        self.p_main.clear()
        self.p_vol.clear()
        self.p_main.addItem(self.vLine_main, ignoreBounds=True)
        self.p_main.addItem(self.hLine_main, ignoreBounds=True)
        self.p_vol.addItem(self.vLine_vol, ignoreBounds=True)

        n = len(self._df)
        x = np.arange(n)

        # 1. 组装并添加 K 线
        candle_data = []
        for i in range(n):
            row = self._df.iloc[i]
            candle_data.append((
                i,
                float(row["open"]),
                float(row["close"]),
                float(row["low"]),
                float(row["high"]),
            ))
        candles = CandlestickItem(candle_data)
        self.p_main.addItem(candles)

        # 2. 绘制均线 (MA5/10/20/60)
        ma_configs = [
            ("ma5", "#FACC15", "MA5"),
            ("ma10", "#38BDF8", "MA10"),
            ("ma20", "#C084FC", "MA20"),
            ("ma60", "#4ADE80", "MA60"),
        ]
        for col, color, name in ma_configs:
            if col in self._df.columns:
                valid_mask = ~self._df[col].isna()
                self.p_main.plot(
                    x[valid_mask],
                    self._df[col][valid_mask].values,
                    pen=pg.mkPen(color, width=1.2),
                    name=name,
                )

        # 3. 绘制成交量副图
        vol_colors = []
        for i in range(n):
            cl = self._df["close"].iloc[i]
            op = self._df["open"].iloc[i]
            vol_colors.append(pg.mkBrush("#EF4444" if cl >= op else "#10B981"))

        vol_bars = pg.BarGraphItem(
            x=x,
            height=self._df["volume"].values,
            width=0.7,
            brushes=vol_colors,
            pen=None,
        )
        self.p_vol.addItem(vol_bars)

        # 设置自定义 X 轴刻度
        step = max(1, n // 6)
        ticks = [(i, self._date_strings[i]) for i in range(0, n, step) if i < len(self._date_strings)]
        ax = self.p_vol.getAxis("bottom")
        ax.setTicks([ticks])

        # 自适应视野至最近 80 根 K 线
        start_x = max(0, n - 80)
        self.p_main.setXRange(start_x, n + 2, padding=0.02)
        self.p_main.enableAutoRange(axis=pg.ViewBox.YAxis)
        self.p_vol.enableAutoRange(axis=pg.ViewBox.YAxis)

    def _on_mouse_moved(self, pos):
        """十字光标与量价面板动态联动"""
        if self._df is None or self._df.empty:
            return

        mouse_point = self.p_main.vb.mapSceneToView(pos)
        index = int(round(mouse_point.x()))

        if 0 <= index < len(self._df):
            # 更新十字光标位置
            self.vLine_main.setPos(mouse_point.x())
            self.hLine_main.setPos(mouse_point.y())
            self.vLine_vol.setPos(mouse_point.x())

            # 提取当前 K 线数据
            row = self._df.iloc[index]
            dt = str(row.get("date", ""))
            op = float(row.get("open", 0.0))
            cl = float(row.get("close", 0.0))
            hi = float(row.get("high", 0.0))
            lo = float(row.get("low", 0.0))
            vol = float(row.get("volume", 0.0))
            chg = ((cl - op) / op * 100) if op > 0 else 0.0

            color_hex = "#EF4444" if cl >= op else "#10B981"
            self.lbl_info.setText(
                f"日期: <span style='color:#94A3B8'>{dt}</span> | "
                f"开: <span style='color:#E2E8F0'>{op:.2f}</span> | "
                f"高: <span style='color:#E2E8F0'>{hi:.2f}</span> | "
                f"低: <span style='color:#E2E8F0'>{lo:.2f}</span> | "
                f"收: <span style='color:{color_hex}'>{cl:.2f} ({chg:+.2f}%)</span> | "
                f"量: <span style='color:#E2E8F0'>{vol:,.0f}手</span>"
            )

            # 均线数值
            ma5 = float(row.get("ma5", 0.0))
            ma10 = float(row.get("ma10", 0.0))
            ma20 = float(row.get("ma20", 0.0))
            ma60 = float(row.get("ma60", 0.0))
            self.lbl_mas.setText(
                f"<span style='color:#FACC15'>MA5: {ma5:.2f}</span>  "
                f"<span style='color:#38BDF8'>MA10: {ma10:.2f}</span>  "
                f"<span style='color:#C084FC'>MA20: {ma20:.2f}</span>  "
                f"<span style='color:#4ADE80'>MA60: {ma60:.2f}</span>"
            )
