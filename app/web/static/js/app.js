/**
 * StockAI 移动端 PWA 前端交互引擎 (原生 JavaScript 无框架驱动)
 */

// 1. 全局状态
const state = {
  currentTab: 'tab-market',
  currentSymbol: '002429',
  currentStockName: '兆驰股份',
  watchlist: [],
};

// 2. 辅助工具函数
function formatPrice(val) {
  return Number(val || 0).toFixed(2);
}

function formatChange(val) {
  const num = Number(val || 0);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

function getChangeClass(val) {
  const num = Number(val || 0);
  if (num > 0) return 'color-up';
  if (num < 0) return 'color-down';
  return 'color-flat';
}

function getBadgeClass(val) {
  const num = Number(val || 0);
  if (num > 0) return 'badge-up';
  if (num < 0) return 'badge-down';
  return 'badge-flat';
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'block';
  toast.style.opacity = '1';
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => { toast.style.display = 'none'; }, 300);
  }, 2200);
}

// 3. Tab 导航切换
function switchTab(tabId) {
  state.currentTab = tabId;
  
  // 更新导航高亮
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tabId);
  });

  // 更新面板展示
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.toggle('active', el.id === tabId);
  });

  // 触发当前 Tab 数据刷新
  if (tabId === 'tab-market') {
    loadMarketOverview();
    loadWatchlist();
  } else if (tabId === 'tab-recommend') {
    loadRecommendations();
  } else if (tabId === 'tab-detail') {
    loadStockDetail(state.currentSymbol);
  } else if (tabId === 'tab-trade') {
    loadTradingData();
  }
}

// 4. 大盘与自选逻辑
async function loadMarketOverview() {
  try {
    const res = await fetch('/api/market/overview');
    if (!res.ok) return;
    const data = await res.json();
    
    // 渲染四大指数
    const grid = document.getElementById('indices-grid');
    if (grid && data.indices) {
      grid.innerHTML = data.indices.map(idx => {
        const chg = Number(idx.change_pct || 0);
        const colorCls = getChangeClass(chg);
        return `
          <div class="index-card">
            <div class="index-name">${idx.name}</div>
            <div class="index-price ${colorCls}">${formatPrice(idx.close_price)}</div>
            <div class="index-change ${colorCls}">${formatChange(chg)}</div>
          </div>
        `;
      }).join('');
    }

    // 渲染全市场多空统计
    const stats = data.market_stats;
    if (stats) {
      document.getElementById('stat-up').textContent = `${stats.up} 涨`;
      document.getElementById('stat-down').textContent = `${stats.down} 跌`;
      document.getElementById('stat-avg').textContent = `全市场平均: ${formatChange(stats.avg_change)}`;
      
      const total = stats.up + stats.down + stats.flat || 1;
      const upPct = (stats.up / total) * 100;
      const downPct = (stats.down / total) * 100;
      document.getElementById('bar-up').style.width = `${upPct}%`;
      document.getElementById('bar-down').style.width = `${downPct}%`;
    }
  } catch (err) {
    console.error('加载大盘概览失败', err);
  }
}

async function loadWatchlist() {
  try {
    const res = await fetch('/api/watchlist');
    if (!res.ok) return;
    const list = await res.json();
    state.watchlist = list;

    // 同步更新个股研判与买入建仓的自选下拉框
    updateWatchlistDropdowns(list);

    const container = document.getElementById('watchlist-container');
    if (!container) return;

    if (!list || list.length === 0) {
      container.innerHTML = '<div class="empty-state">自选股票池为空，可点击上方「+加自选」输入代码</div>';
      return;
    }

    container.innerHTML = list.map(item => {
      const sym = item.symbol;
      const chg = Number(item.change_pct || 0);
      return `
        <div class="stock-card" onclick="openStockDetail('${sym}', '${item.name}')">
          <div class="stock-info">
            <div class="stock-name">${item.name}</div>
            <div class="stock-code">${sym} · ${item.group_name || '默认自选'}</div>
            <div class="stock-extra">换手: ${Number(item.turnover_rate || 0).toFixed(2)}%</div>
          </div>
          <div class="stock-price-block">
            <div class="stock-price ${getChangeClass(chg)}">${formatPrice(item.price)}</div>
            <div class="badge-change ${getBadgeClass(chg)}">${formatChange(chg)}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('加载自选股失败', err);
  }
}

function updateWatchlistDropdowns(list) {
  const selects = [document.getElementById('detail-watchlist-select'), document.getElementById('buy-watchlist-select')];
  selects.forEach(sel => {
    if (!sel) return;
    const curVal = sel.value;
    sel.innerHTML = '<option value="">-- 从自选股中快速选择 --</option>' + 
      list.map(s => `<option value="${s.symbol}">${s.symbol} ${s.name}</option>`).join('');
    if (curVal) sel.value = curVal;
  });
}

function openStockDetail(symbol, name) {
  state.currentSymbol = symbol;
  state.currentStockName = name || symbol;
  switchTab('tab-detail');
}

// 5. 智能精选推荐
async function loadRecommendations() {
  const container = document.getElementById('recommend-container');
  if (!container) return;

  try {
    container.innerHTML = '<div class="empty-state">正在调度模型与量化漏斗生成精选推荐...</div>';
    const res = await fetch('/api/recommend');
    if (!res.ok) throw new Error('网络异常');
    const data = await res.json();

    document.getElementById('recommend-summary').textContent = data.market_summary || '多因子量化模型已就绪';

    if (!data.stocks || data.stocks.length === 0) {
      container.innerHTML = '<div class="empty-state">暂无可推荐的标的</div>';
      return;
    }

    container.innerHTML = data.stocks.map(s => `
      <div class="recommend-card">
        <div class="recommend-header">
          <div>
            <span class="stock-name" style="font-size: 16px;">${s.name}</span>
            <span class="stock-code">(${s.symbol})</span>
          </div>
          <div class="recommend-score">综合评分: ${s.score}分</div>
        </div>
        <div class="recommend-reasons">
          ${(s.reasons || []).map(r => `<div class="reason-item">${r}</div>`).join('')}
        </div>
        ${s.risk_warnings ? `<div class="risk-box">⚠️ 风险关注: ${s.risk_warnings}</div>` : ''}
        <div style="display: flex; gap: 8px; margin-top: 6px;">
          <button class="btn-cyan-sm" style="flex:1;" onclick="openStockDetail('${s.symbol}', '${s.name}')">进入深度研判</button>
          <button class="btn-cyan-sm" style="flex:1;" onclick="quickBuyFromCard('${s.symbol}')">快捷建仓</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">推荐加载异常: ${err.message}</div>`;
  }
}

// 6. 个股研判与 Canvas 自绘 K 线
async function loadStockDetail(symbol) {
  if (!symbol) symbol = state.currentSymbol || '002429';
  state.currentSymbol = symbol;
  
  // 更新标题
  document.getElementById('detail-title').textContent = `${state.currentStockName || symbol} (${symbol})`;
  const sel = document.getElementById('detail-watchlist-select');
  if (sel) sel.value = symbol;

  try {
    const res = await fetch(`/api/stock/${symbol}/kline?count=50`);
    if (!res.ok) return;
    const data = await res.json();
    // 延迟 50ms 确保 Tab 布局完全生效后绘制 Canvas
    setTimeout(() => {
      drawKlineChart(data.klines || []);
    }, 50);
  } catch (err) {
    console.error('加载 K 线失败', err);
  }
}

function drawKlineChart(klines) {
  const canvas = document.getElementById('kline-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  const W = rect.width > 0 ? rect.width : (canvas.parentElement ? canvas.parentElement.clientWidth : 350);
  const H = rect.height > 0 ? rect.height : 220;

  canvas.width = W * dpr;
  canvas.height = H * dpr;
  ctx.scale(dpr, dpr);

  // 清空画布
  ctx.fillStyle = '#161B2A';
  ctx.fillRect(0, 0, W, H);

  if (klines.length === 0) {
    ctx.fillStyle = '#64748B';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无 K 线行情数据', W / 2, H / 2);
    return;
  }

  // 计算极值
  let minP = Infinity, maxP = -Infinity;
  klines.forEach(k => {
    if (k.low < minP) minP = k.low;
    if (k.high > maxP) maxP = k.high;
    if (k.ma5 < minP) minP = k.ma5;
    if (k.ma5 > maxP) maxP = k.ma5;
  });
  const pad = (maxP - minP) * 0.1 || 1;
  minP -= pad;
  maxP += pad;

  const getY = (p) => H - 20 - ((p - minP) / (maxP - minP)) * (H - 35);
  const n = klines.length;
  const colW = (W - 20) / n;
  const barW = Math.max(2, colW * 0.7);

  // 绘制网格参考线
  ctx.strokeStyle = '#232D42';
  ctx.lineWidth = 1;
  [0.25, 0.5, 0.75].forEach(r => {
    const y = (H - 20) * r;
    ctx.beginPath();
    ctx.moveTo(10, y);
    ctx.lineTo(W - 10, y);
    ctx.stroke();
  });

  // 绘制蜡烛柱
  klines.forEach((k, i) => {
    const x = 10 + i * colW + colW / 2;
    const isUp = k.close >= k.open;
    const color = isUp ? '#EF4444' : '#10B981';

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1.2;

    // 影线
    ctx.beginPath();
    ctx.moveTo(x, getY(k.high));
    ctx.lineTo(x, getY(k.low));
    ctx.stroke();

    // 实体
    const yOpen = getY(k.open);
    const yClose = getY(k.close);
    const topY = Math.min(yOpen, yClose);
    const bodyH = Math.max(2, Math.abs(yClose - yOpen));
    ctx.fillRect(x - barW / 2, topY, barW, bodyH);
  });

  // 绘制 MA5 折线
  ctx.strokeStyle = '#38BDF8';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  klines.forEach((k, i) => {
    const x = 10 + i * colW + colW / 2;
    const y = getY(k.ma5);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 标出最新价与 MA5 标签
  const lastK = klines[klines.length - 1];
  ctx.fillStyle = '#38BDF8';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(`MA5: ${lastK.ma5.toFixed(2)}`, 14, 18);
  ctx.fillStyle = lastK.close >= lastK.open ? '#EF4444' : '#10B981';
  ctx.fillText(`最新收盘: ${lastK.close.toFixed(2)}`, W - 110, 18);
}

// 7. 虚拟操盘逻辑
async function loadTradingData() {
  try {
    // 账户概况
    const sumRes = await fetch('/api/trading/summary?account_type=MANUAL');
    if (sumRes.ok) {
      const s = await sumRes.json();
      document.getElementById('trade-total-asset').textContent = `${formatPrice(s.total_asset)} 元`;
      
      const pnl = Number(s.float_pnl || 0);
      const pnlEl = document.getElementById('trade-float-pnl');
      pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${formatPrice(pnl)} (${formatChange(s.total_return_pct)})`;
      pnlEl.className = `sub-stat-val ${getChangeClass(pnl)}`;

      document.getElementById('trade-cash').textContent = `${formatPrice(s.available_cash)} 元`;
      document.getElementById('trade-holding-val').textContent = `${formatPrice(s.holding_market_val)} 元`;
    }

    // 持仓列表
    const posRes = await fetch('/api/trading/positions?account_type=MANUAL');
    if (posRes.ok) {
      const positions = await posRes.json();
      const container = document.getElementById('positions-container');
      if (!container) return;

      if (!positions || positions.length === 0) {
        container.innerHTML = '<div class="empty-state">当前账户暂无持仓，点击右下角「+模拟买入」快速建仓</div>';
        return;
      }

      container.innerHTML = positions.map(p => {
        const pnl = Number(p.float_pnl || 0);
        const pnlPct = Number(p.pnl_pct || 0);
        return `
          <div class="stock-card">
            <div class="stock-info">
              <div class="stock-name">${p.name} <span class="stock-code">(${p.symbol})</span></div>
              <div class="stock-extra">持仓: ${p.total_amount} 股 · 成本: ${formatPrice(p.cost_price)}</div>
              <div class="stock-extra ${getChangeClass(pnl)}">浮盈: ${pnl >= 0 ? '+' : ''}${formatPrice(pnl)} (${formatChange(pnlPct)})</div>
            </div>
            <div class="stock-price-block">
              <div class="stock-price">${formatPrice(p.current_price)}</div>
              <button class="btn-danger-sm" onclick="closePosition('${p.symbol}', ${p.total_amount})">一键平仓</button>
            </div>
          </div>
        `;
      }).join('');
    }
  } catch (err) {
    console.error('加载操盘数据失败', err);
  }
}

async function closePosition(symbol, amount) {
  if (!confirm(`确认要将持仓标的 [${symbol}] 全额平仓 (${amount} 股) 吗？`)) return;

  try {
    const res = await fetch('/api/trading/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, amount, reason: '手机端一键平仓' })
    });
    const data = await res.json();
    if (data.success) {
      showToast('平仓撮合成功');
      loadTradingData();
    } else {
      alert(`平仓失败: ${data.message}`);
    }
  } catch (err) {
    alert(`平仓请求异常: ${err.message}`);
  }
}

// 8. 模拟买入建仓弹窗
function openBuyModal(defaultSymbol) {
  const modal = document.getElementById('buy-modal');
  if (defaultSymbol) {
    document.getElementById('buy-symbol-input').value = defaultSymbol;
    const sel = document.getElementById('buy-watchlist-select');
    if (sel) sel.value = defaultSymbol;
  }
  modal.classList.add('active');
}

function closeBuyModal() {
  document.getElementById('buy-modal').classList.remove('active');
}

function quickBuyFromCard(symbol) {
  switchTab('tab-trade');
  openBuyModal(symbol);
}

async function submitBuyOrder() {
  const symbol = document.getElementById('buy-symbol-input').value.trim();
  const amount = parseInt(document.getElementById('buy-amount-input').value, 10);
  const reason = document.getElementById('buy-reason-input').value.trim();

  if (!symbol || symbol.length < 6) {
    alert('请输入 6 位有效股票代码');
    return;
  }
  if (!amount || amount <= 0 || amount % 100 !== 0) {
    alert('买入股数必须为 100 的整数倍');
    return;
  }

  try {
    const res = await fetch('/api/trading/buy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, amount, reason })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || '建仓买入成功');
      closeBuyModal();
      loadTradingData();
    } else {
      alert(data.message || '建仓失败');
    }
  } catch (err) {
    alert(`建仓异常: ${err.message}`);
  }
}

// 9. 添加自选弹窗
function openAddWatchlistPrompt() {
  const code = prompt('请输入要加入自选池的 6 位股票代码 (如 600519):');
  if (!code) return;
  const sym = code.trim().padStart(6, '0');
  
  fetch('/api/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol: sym, group_name: '默认自选' })
  }).then(r => r.json()).then(res => {
    showToast(res.message || '操作完成');
    loadWatchlist();
  }).catch(e => alert(`添加失败: ${e.message}`));
}

// 10. 初始化绑定
document.addEventListener('DOMContentLoaded', () => {
  // Tab 绑定
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // 买入弹窗自选股联动
  const buySel = document.getElementById('buy-watchlist-select');
  if (buySel) {
    buySel.addEventListener('change', (e) => {
      if (e.target.value) {
        document.getElementById('buy-symbol-input').value = e.target.value;
      }
    });
  }

  // 研判自选股下拉联动
  const detailSel = document.getElementById('detail-watchlist-select');
  if (detailSel) {
    detailSel.addEventListener('change', (e) => {
      if (e.target.value) {
        loadStockDetail(e.target.value);
      }
    });
  }

  // 窗口缩放重绘 K 线
  window.addEventListener('resize', () => {
    if (state.currentTab === 'tab-detail') {
      loadStockDetail(state.currentSymbol);
    }
  });

  // 默认进入市场自选
  switchTab('tab-market');
});
