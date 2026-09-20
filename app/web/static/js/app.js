/**
 * StockAI 移动端 PWA 前端交互引擎 (原生 JavaScript 无框架驱动)
 * 支持 5-Tab 布局、全景大盘 4 大排行榜与客户端拼音首字母零往返秒级搜索
 */

// 1. 全局状态
const state = {
  currentTab: 'tab-market',
  currentSymbol: '002429',
  currentStockName: '兆驰股份',
  currentRankingCategory: 'gainers',
  currentTradeAccount: 'MANUAL', // 'MANUAL' | 'AI'
  watchlist: [],
  searchIndex: [],     // 格式: [{s: '000001', n: '平安银行', p: 'PAYH'}, ...]
  quotesMap: {},       // 代码 -> {price, change_pct} 快照缓存
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

// 3. Tab 导航切换 (5 大 Tab)
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
  } else if (tabId === 'tab-watchlist') {
    loadWatchlist();
  } else if (tabId === 'tab-recommend') {
    loadRecommendations();
  } else if (tabId === 'tab-detail') {
    loadStockDetail(state.currentSymbol);
  } else if (tabId === 'tab-trade') {
    loadTradingData();
  }
}

// 4. 全景大盘与排行榜逻辑
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

  // 加载当前选中的排行榜
  loadMarketRankings(state.currentRankingCategory);
}

function switchRankingCategory(category) {
  state.currentRankingCategory = category;
  document.querySelectorAll('.ranking-pill').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.category === category);
  });
  loadMarketRankings(category);
}

async function loadMarketRankings(category = 'gainers') {
  const container = document.getElementById('rankings-container');
  if (!container) return;
  
  container.innerHTML = '<div class="empty-state">排行榜加载中...</div>';
  try {
    const res = await fetch(`/api/market/rankings?category=${category}&limit=50`);
    if (!res.ok) throw new Error('网络响应异常');
    const list = await res.json();
    
    if (!list || list.length === 0) {
      container.innerHTML = '<div class="empty-state">暂无排行数据</div>';
      return;
    }

    // 同步写入缓存
    list.forEach(item => {
      state.quotesMap[item.symbol] = {
        price: item.price,
        change_pct: item.change_pct
      };
    });

    container.innerHTML = list.map(item => {
      const chg = Number(item.change_pct || 0);
      const colorCls = getChangeClass(chg);
      let rankCls = '';
      if (item.rank === 1) rankCls = 'rank-1';
      else if (item.rank === 2) rankCls = 'rank-2';
      else if (item.rank === 3) rankCls = 'rank-3';

      let extraInfo = '';
      if (category === 'volume') {
        extraInfo = `额: ${item.amount_str}`;
      } else if (category === 'turnover') {
        extraInfo = `换手: ${Number(item.turnover_rate || 0).toFixed(2)}%`;
      } else {
        extraInfo = `换手: ${Number(item.turnover_rate || 0).toFixed(1)}%`;
      }

      return `
        <div class="ranking-item" onclick="openStockDetail('${item.symbol}', '${item.name}')">
          <div class="ranking-left">
            <div class="rank-badge ${rankCls}">${item.rank}</div>
            <div class="ranking-stock-info">
              <span class="ranking-stock-name">${item.name}</span>
              <span class="ranking-stock-sub">${item.symbol}</span>
            </div>
          </div>
          <div class="ranking-right">
            <div class="ranking-price-col">
              <div class="ranking-price ${colorCls}">${formatPrice(item.price)}</div>
              <div class="ranking-extra">${extraInfo}</div>
            </div>
            <div class="badge-change ${getBadgeClass(chg)}">${formatChange(chg)}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('加载大盘排行榜失败', err);
    container.innerHTML = '<div class="empty-state">排行数据加载失败，请重试</div>';
  }
}

// 5. 自选股池逻辑
async function loadWatchlist() {
  try {
    const res = await fetch('/api/watchlist');
    if (!res.ok) return;
    const list = await res.json();
    state.watchlist = list;

    // 同步写入缓存
    list.forEach(item => {
      state.quotesMap[item.symbol] = {
        price: item.price,
        change_pct: item.change_pct
      };
    });

    // 同步更新个股研判与买入建仓的自选下拉框
    updateWatchlistDropdowns(list);

    const container = document.getElementById('watchlist-container');
    if (!container) return;

    if (!list || list.length === 0) {
      container.innerHTML = '<div class="empty-state">自选股票池为空，可使用上方搜索框添加</div>';
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
    sel.innerHTML = '<option value="">-- 点击选择自选标的 --</option>' +
      list.map(s => `<option value="${s.symbol}">${s.symbol} ${s.name}</option>`).join('');
    if (curVal) sel.value = curVal;
  });
}

// 6. 拼音首字母轻量搜索与联想浮层引擎
async function loadSearchIndex() {
  try {
    const res = await fetch('/api/stock/search-index');
    if (!res.ok) return;
    const data = await res.json();
    if (Array.isArray(data)) {
      state.searchIndex = data;
      console.log(`[SearchEngine] 已成功预加载 ${data.length} 支标的拼音搜索索引`);
    }
  } catch (err) {
    console.warn('[SearchEngine] 预取搜索索引失败', err);
  }
}

let searchTimer = null;
function handleSearchInput(e) {
  const query = (e.target.value || '').trim();
  const clearBtn = document.getElementById('search-clear-btn');
  const dropdown = document.getElementById('search-dropdown');
  const listEl = document.getElementById('search-dropdown-list');
  const countEl = document.getElementById('search-match-count');

  if (clearBtn) clearBtn.style.display = query ? 'block' : 'none';

  if (!query) {
    if (dropdown) dropdown.style.display = 'none';
    return;
  }

  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const upperQuery = query.toUpperCase();
    // 毫秒级内存正则过滤 (代码前缀/包含, 拼音首字母前缀/包含, 中文包含)
    const matches = [];
    const index = state.searchIndex;
    for (let i = 0; i < index.length; i++) {
      const item = index[i];
      // 1. 匹配代码 (前缀优先)
      if (item.s.startsWith(upperQuery) || item.s.includes(upperQuery)) {
        matches.push(item);
      }
      // 2. 匹配拼音简拼 (首字母前缀优先)
      else if (item.p && (item.p.startsWith(upperQuery) || item.p.includes(upperQuery))) {
        matches.push(item);
      }
      // 3. 匹配汉字简称
      else if (item.n && item.n.includes(query)) {
        matches.push(item);
      }
      if (matches.length >= 8) break; // 限制展示前 8 项
    }

    if (countEl) countEl.textContent = matches.length;

    if (matches.length === 0) {
      listEl.innerHTML = '<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:12px;">未检索到匹配标的</div>';
      dropdown.style.display = 'block';
      return;
    }

    const watchlistSymbols = new Set(state.watchlist.map(w => w.symbol));

    listEl.innerHTML = matches.map(item => {
      const isAdded = watchlistSymbols.has(item.s);
      const quote = state.quotesMap[item.s];
      let quoteHtml = '';
      if (quote) {
        const colorCls = getChangeClass(quote.change_pct);
        quoteHtml = `
          <div class="search-item-quotes">
            <div class="search-item-price ${colorCls}">${formatPrice(quote.price)}</div>
            <div class="search-item-chg ${colorCls}">${formatChange(quote.change_pct)}</div>
          </div>
        `;
      }

      return `
        <div class="search-item" onclick="selectSearchStock('${item.s}', '${item.n}')">
          <div class="search-item-info">
            <div class="search-item-name-row">
              <span class="search-item-name">${item.n}</span>
              ${item.p ? `<span class="search-item-pinyin">${item.p}</span>` : ''}
            </div>
            <span class="search-item-code">${item.s}</span>
          </div>
          <div class="search-item-actions">
            ${quoteHtml}
            <button class="search-btn-add ${isAdded ? 'added' : ''}" onclick="toggleWatchlistFromSearch(event, '${item.s}')">
              ${isAdded ? '✓ 已自选' : '+ 自选'}
            </button>
          </div>
        </div>
      `;
    }).join('');

    dropdown.style.display = 'block';
  }, 120);
}

function clearSearch() {
  const input = document.getElementById('global-search-input');
  if (input) {
    input.value = '';
    input.focus();
  }
  const clearBtn = document.getElementById('search-clear-btn');
  if (clearBtn) clearBtn.style.display = 'none';
  const dropdown = document.getElementById('search-dropdown');
  if (dropdown) dropdown.style.display = 'none';
}

function selectSearchStock(symbol, name) {
  const dropdown = document.getElementById('search-dropdown');
  if (dropdown) dropdown.style.display = 'none';
  openStockDetail(symbol, name);
}

async function toggleWatchlistFromSearch(e, symbol) {
  e.stopPropagation();
  const btn = e.currentTarget;
  const isAdded = btn.classList.contains('added');
  
  if (isAdded) {
    // 移除
    try {
      const res = await fetch(`/api/watchlist/${symbol}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        btn.classList.remove('added');
        btn.textContent = '+ 自选';
        showToast(`已将 ${symbol} 移出自选池`);
        loadWatchlist();
      }
    } catch (err) {
      showToast('操作失败');
    }
  } else {
    // 添加
    try {
      const res = await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, group_name: '移动搜索' })
      });
      const data = await res.json();
      if (data.success) {
        btn.classList.add('added');
        btn.textContent = '✓ 已自选';
        showToast(`已成功将 ${symbol} 加入自选`);
        loadWatchlist();
      }
    } catch (err) {
      showToast('添加自选失败');
    }
  }
}

// 7. 智能推荐逻辑
async function loadRecommendations() {
  const container = document.getElementById('recommend-container');
  if (!container) return;
  container.innerHTML = '<div class="empty-state">AI 推荐引擎计算中...</div>';

  try {
    const res = await fetch('/api/recommend');
    if (!res.ok) return;
    const data = await res.json();

    const summaryEl = document.getElementById('recommend-summary');
    if (summaryEl && data.market_summary) {
      summaryEl.textContent = data.market_summary;
    }

    if (!data.stocks || data.stocks.length === 0) {
      container.innerHTML = '<div class="empty-state">暂无精选标的推荐</div>';
      return;
    }

    container.innerHTML = data.stocks.map(stk => {
      const reasonsHtml = stk.reasons && stk.reasons.length > 0
        ? stk.reasons.map(r => `<div>• ${r}</div>`).join('')
        : '<div>• 多因子综合评分高位</div>';

      const risksHtml = stk.risk_warnings && stk.risk_warnings.length > 0
        ? stk.risk_warnings.map(rw => `<div>⚠ ${rw}</div>`).join('')
        : '';

      return `
        <div class="recommend-card">
          <div class="recommend-card-header">
            <div>
              <div class="recommend-name">${stk.name}</div>
              <div class="recommend-code">${stk.symbol}</div>
            </div>
            <div class="recommend-score">AI 得分: ${stk.score || '--'}</div>
          </div>
          <div class="recommend-reasons">
            ${reasonsHtml}
            ${risksHtml ? `<div style="color:var(--up-red); margin-top:4px;">${risksHtml}</div>` : ''}
          </div>
          <div class="recommend-actions">
            <button class="btn-cyan-sm" onclick="openStockDetail('${stk.symbol}', '${stk.name}')">深度研判</button>
            <button class="btn-primary" style="padding:4px 12px; font-size:12px;" onclick="quickBuyFromCard('${stk.symbol}')">模拟建仓</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('加载推荐失败', err);
    container.innerHTML = '<div class="empty-state">获取推荐数据失败</div>';
  }
}

// 8. 个股深度研判与交互 K 线
function openStockDetail(symbol, name) {
  state.currentSymbol = symbol;
  state.currentStockName = name || symbol;
  switchTab('tab-detail');
}

async function loadStockDetail(symbol) {
  const titleEl = document.getElementById('detail-title');
  if (titleEl) {
    titleEl.textContent = `${state.currentStockName || ''} (${symbol}) 深度研判`;
  }

  // 联动更新下拉框
  const sel = document.getElementById('detail-watchlist-select');
  if (sel && sel.value !== symbol) {
    sel.value = symbol;
  }

  // 获取近期日 K 线
  try {
    const res = await fetch(`/api/stock/${symbol}/kline?count=50`);
    if (!res.ok) return;
    const data = await res.json();
    renderKLineChart(data.klines || []);
  } catch (err) {
    console.error('加载 K 线失败', err);
  }
}

function renderKLineChart(klines) {
  const canvas = document.getElementById('kline-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  // 高清 Retina 适配
  const dpr = window.devicePixelRatio || 2;
  const rect = canvas.getBoundingClientRect();
  const width = rect.width || 340;
  const height = 220;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, width, height);

  if (!klines || klines.length === 0) {
    ctx.fillStyle = '#64748B';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无近 50 日 K 线数据', width / 2, height / 2);
    return;
  }

  // 计算价格极值
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  klines.forEach(k => {
    if (k.low < minPrice) minPrice = k.low;
    if (k.high > maxPrice) maxPrice = k.high;
  });

  const padding = { top: 20, bottom: 25, left: 10, right: 48 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const priceRange = (maxPrice - minPrice) || 1;

  function getY(price) {
    return padding.top + plotHeight - ((price - minPrice) / priceRange) * plotHeight;
  }

  // 绘制背景水平参考线与价格标签
  ctx.strokeStyle = '#1E293B';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#64748B';
  ctx.font = '10px monospace';
  ctx.textAlign = 'left';

  const steps = 3;
  for (let i = 0; i <= steps; i++) {
    const p = minPrice + (priceRange / steps) * i;
    const y = getY(p);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(p.toFixed(2), width - padding.right + 4, y + 3);
  }

  // 绘制每根蜡烛与影线
  const count = klines.length;
  const candleW = Math.max(2, (plotWidth / count) * 0.7);
  const stepX = plotWidth / count;

  klines.forEach((k, i) => {
    const x = padding.left + i * stepX + stepX / 2;
    const isUp = k.close >= k.open;
    const color = isUp ? '#EF4444' : '#10B981';

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1.2;

    // 最高与最低影线
    ctx.beginPath();
    ctx.moveTo(x, getY(k.high));
    ctx.lineTo(x, getY(k.low));
    ctx.stroke();

    // 蜡烛实体
    const yOpen = getY(k.open);
    const yClose = getY(k.close);
    const top = Math.min(yOpen, yClose);
    const bodyH = Math.max(1.5, Math.abs(yOpen - yClose));

    ctx.fillRect(x - candleW / 2, top, candleW, bodyH);
  });

  // 绘制 MA5 均线
  ctx.beginPath();
  ctx.strokeStyle = '#38BDF8';
  ctx.lineWidth = 1.5;
  let ma5Started = false;
  klines.forEach((k, i) => {
    if (k.ma5) {
      const x = padding.left + i * stepX + stepX / 2;
      const y = getY(k.ma5);
      if (!ma5Started) {
        ctx.moveTo(x, y);
        ma5Started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();

  // 底部图例
  ctx.fillStyle = '#38BDF8';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('— MA5 均线', padding.left + 5, 14);
}

// 9. 虚拟操盘逻辑 (人机双轨操盘、AI自动建仓与技能军规库)
function switchTradeAccount(accountType) {
  state.currentTradeAccount = accountType;
  const isAI = accountType === 'AI';

  // 药丸切换高亮
  const btnManual = document.getElementById('btn-acc-manual');
  const btnAi = document.getElementById('btn-acc-ai');
  if (btnManual && btnAi) {
    btnManual.classList.toggle('active', !isAI);
    btnAi.classList.toggle('active', isAI);
    btnAi.classList.toggle('ai-active', isAI);
  }

  // 资产卡片科技主题切换
  const banner = document.getElementById('portfolio-banner-card');
  const labelEl = document.getElementById('portfolio-account-label');
  const tagEl = document.getElementById('portfolio-tag');
  const aiActionBar = document.getElementById('ai-action-bar');
  const posTitle = document.getElementById('positions-title');
  const fabText = document.getElementById('fab-trade-text');

  if (banner) {
    banner.classList.toggle('ai-theme', isAI);
  }
  if (labelEl) {
    labelEl.textContent = isAI ? 'AI 智能自动操盘账户总资产' : '人类主观操盘账户总资产';
  }
  if (tagEl) {
    tagEl.textContent = isAI ? 'AI 量化' : '主观实战';
  }
  if (aiActionBar) {
    aiActionBar.style.display = isAI ? 'block' : 'none';
  }
  if (posTitle) {
    posTitle.textContent = isAI ? '🤖 AI 当前持仓明细' : '💼 当前持仓明细';
  }
  if (fabText) {
    fabText.textContent = isAI ? '🤖 自动建仓' : '➕ 模拟买入';
  }

  // 重新加载数据
  loadTradingData();
}

async function loadTradingData() {
  const currentAcc = state.currentTradeAccount || 'MANUAL';

  try {
    // 1. 获取人机双轨 PK 对比战报
    fetch('/api/trading/comparison').then(r => r.json()).then(cmp => {
      if (cmp && cmp.manual && cmp.ai) {
        const mRet = Number(cmp.manual.total_return_pct || 0);
        const aiRet = Number(cmp.ai.total_return_pct || 0);

        const mEl = document.getElementById('pk-manual-return');
        if (mEl) {
          mEl.textContent = `${mRet > 0 ? '+' : ''}${mRet.toFixed(2)}%`;
          mEl.className = `pk-val ${getChangeClass(mRet)}`;
        }

        const aiEl = document.getElementById('pk-ai-return');
        if (aiEl) {
          aiEl.textContent = `${aiRet > 0 ? '+' : ''}${aiRet.toFixed(2)}%`;
          aiEl.className = `pk-val ${getChangeClass(aiRet)}`;
        }
      }
    }).catch(e => console.warn('获取人机对比战报异常', e));

    // 2. 获取当前账户资金总览
    const sumRes = await fetch(`/api/trading/summary?account_type=${currentAcc}`);
    if (sumRes.ok) {
      const sum = await sumRes.json();
      document.getElementById('trade-total-asset').textContent = `${formatPrice(sum.total_equity || sum.total_asset)} 元`;
      
      const pnl = Number(sum.floating_pnl || sum.float_pnl || 0);
      const pnlEl = document.getElementById('trade-float-pnl');
      pnlEl.textContent = `${pnl > 0 ? '+' : ''}${formatPrice(pnl)}`;
      pnlEl.className = `sub-stat-val ${getChangeClass(pnl)}`;

      document.getElementById('trade-cash').textContent = `${formatPrice(sum.available_cash)} 元`;
      document.getElementById('trade-holding-val').textContent = `${formatPrice(sum.market_value || sum.holding_market_val)} 元`;
    }

    // 3. 定向高速刷新价格
    fetch(`/api/trading/refresh-quotes?account_type=${currentAcc}`, { method: 'POST' });

    // 4. 读取当前账户持仓明细
    const posRes = await fetch(`/api/trading/positions?account_type=${currentAcc}`);
    if (posRes.ok) {
      const positions = await posRes.json();
      const container = document.getElementById('positions-container');
      if (!container) return;

      if (!positions || positions.length === 0) {
        const emptyTip = currentAcc === 'AI' 
          ? 'AI 账户当前空仓，可点击上方「AI 一键全自动计算建仓」'
          : '当前无任何持仓标的，点击右下角「+ 模拟买入」建仓';
        container.innerHTML = `<div class="empty-state">${emptyTip}</div>`;
      } else {
        container.innerHTML = positions.map(pos => {
          const pnl = Number(pos.floating_pnl || 0);
          const pnlPct = Number(pos.floating_pnl_pct != null ? pos.floating_pnl_pct : (pos.return_pct || 0));
          const colorCls = getChangeClass(pnl);
          const totalShares = pos.total_amount != null ? pos.total_amount : (pos.amount || 0);
          const name = pos.name || pos.symbol;

          return `
            <div class="position-card">
              <div class="position-row">
                <span class="position-name">${name} (${pos.symbol})</span>
                <span class="position-pnl ${colorCls}">${pnl > 0 ? '+' : ''}${formatPrice(pnl)} (${formatChange(pnlPct)})</span>
              </div>
              <div class="position-detail">
                <span>持仓: ${totalShares} 股</span>
                <span>成本: ${formatPrice(pos.cost_price)}</span>
                <span>现价: ${formatPrice(pos.current_price)}</span>
              </div>
              <div class="position-actions">
                <button class="btn-cyan-sm" onclick="openStockDetail('${pos.symbol}', '${name}')">研判</button>
                <button class="btn-danger-sm" onclick="closePosition('${pos.symbol}', ${totalShares})">一键平仓</button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // 5. 渲染 AI 实战反思操盘军规经验库
    loadTradingSkills();

  } catch (err) {
    console.error('加载操盘交易数据失败', err);
  }
}

// 加载 AI 操盘实战军规知识库
async function loadTradingSkills() {
  const container = document.getElementById('skills-container');
  if (!container) return;

  try {
    const res = await fetch('/api/trading/skills');
    if (!res.ok) return;
    const skills = await res.json();

    if (!skills || skills.length === 0) {
      container.innerHTML = '<div class="empty-state">尚未沉淀实战反思军规，平仓交易后将自动提炼</div>';
      return;
    }

    container.innerHTML = skills.map(s => {
      const score = Number(s.win_rate_score || 75).toFixed(1);
      return `
        <div class="skill-card">
          <div class="skill-header">
            <div class="skill-title-row">
              <span class="skill-category">${s.category || '综合战法'}</span>
              <span class="skill-title">${s.rule_title}</span>
            </div>
            <span class="skill-score">置信 ${score} 分</span>
          </div>
          <div class="skill-body">${s.rule_markdown}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.warn('加载操盘技能库失败', err);
  }
}

// 触发 AI 一键自动建仓
async function triggerAutoTrade() {
  const btn = document.querySelector('.btn-ai-autotrade');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳ AI 正在分析全市场 5565 支多因子模型与军规...</span>';
  }

  showToast('AI 正在执行多因子粗选与军规深度裁决...');

  try {
    const res = await fetch('/api/trading/auto-trade?max_buy_count=2', { method: 'POST' });
    const data = await res.json();
    
    // 打开结果汇报模态框
    const modal = document.getElementById('auto-trade-modal');
    const msgEl = document.getElementById('auto-trade-msg');
    const listEl = document.getElementById('auto-trade-results-list');

    if (msgEl) msgEl.textContent = data.msg || '决策执行完成';
    
    if (listEl) {
      const items = data.bought_items || [];
      if (items.length === 0) {
        listEl.innerHTML = '<div style="padding:20px; text-align:center; color:var(--text-muted); font-size:12px;">本次未达到建仓买入阈值或触发风控门槛限制</div>';
      } else {
        listEl.innerHTML = items.map(item => `
          <div class="auto-bought-card">
            <div class="auto-bought-top">
              <span class="auto-bought-name">${item.name} (${item.symbol})</span>
              <span class="auto-bought-score">置信评分: ${Number(item.score || 0).toFixed(1)}分</span>
            </div>
            <div class="auto-bought-detail">
              均价: ${formatPrice(item.price)} 元 | 数量: ${item.amount} 股 | 总额: ${formatPrice(item.total_value)} 元
            </div>
            <div class="auto-bought-reason">💡 军规归因: ${item.reason}</div>
          </div>
        `).join('');
      }
    }

    if (modal) modal.classList.add('active');

    // 重新刷新操盘数据
    loadTradingData();
  } catch (err) {
    alert(`AI 自动建仓失败: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span>🤖 AI 一键全自动计算建仓</span>';
    }
  }
}

function closeAutoTradeModal() {
  const modal = document.getElementById('auto-trade-modal');
  if (modal) modal.classList.remove('active');
}

function handleFabClick() {
  if (state.currentTradeAccount === 'AI') {
    triggerAutoTrade();
  } else {
    openBuyModal();
  }
}

async function closePosition(symbol, amount) {
  const currentAcc = state.currentTradeAccount || 'MANUAL';
  const accName = currentAcc === 'AI' ? 'AI 账户' : '主观账户';
  if (!confirm(`确认在 [${accName}] 中以当前最新市价全额平仓 ${symbol} (${amount}股) 吗？`)) return;

  try {
    const res = await fetch('/api/trading/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_type: currentAcc,
        symbol: symbol,
        amount: amount,
        reason: `${accName}手机端平仓了结`
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || '平仓操作成功');
      loadTradingData();
    } else {
      alert(data.message || '平仓失败');
    }
  } catch (err) {
    alert(`平仓请求异常: ${err.message}`);
  }
}

// 10. 买入建仓模态框
function openBuyModal(prefillSymbol = '') {
  const modal = document.getElementById('buy-modal');
  if (!modal) return;
  
  if (prefillSymbol) {
    document.getElementById('buy-symbol-input').value = prefillSymbol;
    const buySel = document.getElementById('buy-watchlist-select');
    if (buySel) buySel.value = prefillSymbol;
  }
  
  modal.classList.add('active');
}

function closeBuyModal() {
  const modal = document.getElementById('buy-modal');
  if (modal) modal.classList.remove('active');
}

function quickBuyFromCard(symbol) {
  openBuyModal(symbol);
}

async function submitBuyOrder() {
  const symbol = (document.getElementById('buy-symbol-input').value || '').trim();
  const amount = parseInt(document.getElementById('buy-amount-input').value, 10);
  const reason = document.getElementById('buy-reason-input').value || '手机端伏击建仓';
  const currentAcc = state.currentTradeAccount || 'MANUAL';

  if (!symbol || symbol.length !== 6) {
    alert('请输入规范的 6 位数字股票代码');
    return;
  }
  if (isNaN(amount) || amount <= 0 || amount % 100 !== 0) {
    alert('买入股数必须为 100 的整数倍');
    return;
  }

  try {
    const res = await fetch('/api/trading/buy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_type: currentAcc,
        symbol: symbol,
        amount: amount,
        reason: reason
      })
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

// 11. 初始化事件绑定
document.addEventListener('DOMContentLoaded', () => {
  // 底部 Tab 切换监听
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // 搜索输入监听与防抖
  const searchInput = document.getElementById('global-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', handleSearchInput);
    searchInput.addEventListener('focus', handleSearchInput);
  }

  // 点击外部收起搜索下拉面板
  document.addEventListener('click', (e) => {
    const wrap = document.querySelector('.search-bar-wrap');
    const dropdown = document.getElementById('search-dropdown');
    if (wrap && dropdown && !wrap.contains(e.target)) {
      dropdown.style.display = 'none';
    }
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

  // 预取全市场拼音搜索轻量索引
  loadSearchIndex();

  // 默认激活全景大盘
  switchTab('tab-market');
});
