"use strict";

const $ = (sel) => document.querySelector(sel);
const api = async (path, body) => {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
};

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 4000);
}

const fmtPct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const signed = (x, d = 2) => (x >= 0 ? "+" : "") + x.toFixed(d);
const actionClass = (a) => ({ BUY: "buy", SELL: "sell", HOLD: "hold" }[a] || "");

/* ---------- Tabs ---------- */
document.querySelectorAll(".tab[data-tab]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab[data-tab]").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#tab-${tab.dataset.tab}`).classList.add("active");
  });
});

/* ---------- Config + strategies bootstrap ---------- */
async function boot() {
  try {
    const cfg = await api("/api/config");
    $("#pill-version").textContent = `v${cfg.version}`;
    $("#pill-mode").textContent = cfg.offline ? "offline" : `live: ${cfg.llm_provider}`;
    $("#pill-data").textContent = cfg.data_source;
  } catch (e) {
    /* non-fatal */
  }
  try {
    const strategies = await api("/api/strategies");
    const wrap = $("#strategy-chips");
    const defaults = new Set(["multi_agent", "ensemble", "buy_and_hold"]);
    strategies.forEach((s) => {
      const chip = document.createElement("span");
      chip.className = "chip" + (defaults.has(s.name) ? " on" : "");
      chip.dataset.name = s.name;
      chip.title = s.description;
      chip.textContent = s.name;
      chip.addEventListener("click", () => chip.classList.toggle("on"));
      wrap.appendChild(chip);
    });
  } catch (e) {
    /* non-fatal */
  }
}

/* ---------- Analyze ---------- */
$("#analyze-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = $("#a-run");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Analysing…';
  try {
    const news = $("#a-news").value.split("\n").map((s) => s.trim()).filter(Boolean);
    const data = await api("/api/analyze", {
      symbol: $("#a-symbol").value.trim() || "AAPL",
      lookback_days: +$("#a-days").value,
      debate_rounds: +$("#a-rounds").value,
      news,
    });
    renderAnalysis(data);
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run analysis";
  }
});

function renderAnalysis(data) {
  $("#analyze-results").classList.remove("hidden");
  const d = data.decision;
  const cls = actionClass(d.action);
  $("#decision-card").className = `decision-card card bd-${cls}`;
  $("#decision-card").innerHTML = `
    <div class="decision-action ${cls}">${d.action}</div>
    <div class="decision-stats">
      <div class="stat"><div class="stat-label">${data.symbol}</div><div class="stat-val">${d.symbol}</div></div>
      <div class="stat"><div class="stat-label">Target weight</div><div class="stat-val">${fmtPct(d.target_weight)}</div></div>
      <div class="stat"><div class="stat-label">Confidence</div><div class="stat-val">${d.confidence.toFixed(2)}</div></div>
      <div class="stat"><div class="stat-label">Stop / Target</div><div class="stat-val">${fmtPct(d.stop_loss_pct, 0)} / ${fmtPct(d.take_profit_pct, 0)}</div></div>
    </div>
    <p class="decision-rationale">${d.rationale}</p>`;

  // Reports with signal bars
  $("#reports").innerHTML = data.reports
    .map((r) => {
      const pos = r.signal >= 0;
      const w = Math.abs(r.signal) * 50;
      const color = pos ? "var(--green)" : "var(--red)";
      const left = pos ? 50 : 50 - w;
      return `<div class="report">
        <div class="report-head">
          <span class="report-name">${r.agent.replace(/_/g, " ")}</span>
          <span class="report-signal" style="color:${color}">${signed(r.signal)} · ${r.confidence.toFixed(2)}</span>
        </div>
        <div class="bar"><div class="bar-mid"></div><div class="bar-fill" style="left:${left}%;width:${w}%;background:${color}"></div></div>
        <p class="report-rationale">${r.rationale}</p>
      </div>`;
    })
    .join("");

  // Debate
  if (data.debate) {
    const db = data.debate;
    $("#debate").innerHTML = `
      <div class="thesis bull"><h4>Bull</h4><p>${db.bull_thesis}</p></div>
      <div class="thesis bear"><h4>Bear</h4><p>${db.bear_thesis}</p></div>
      <div class="thesis judge"><h4>Judge · conviction ${signed(db.conviction)}</h4><p>${db.judge_summary}</p></div>`;
  } else {
    $("#debate").innerHTML = '<p class="muted">No debate produced.</p>';
  }

  // Risk
  if (data.risk) {
    const rk = data.risk;
    const flags = (rk.flags || []).map((f) => `<div class="flag">${f}</div>`).join("");
    $("#risk").innerHTML = `
      <span class="risk-verdict ${rk.approved ? "approved" : "vetoed"}">${rk.approved ? "APPROVED" : "VETOED"}</span>
      <p class="report-rationale" style="margin-top:0">${rk.rationale}</p>${flags}`;
  } else {
    $("#risk").innerHTML = '<p class="muted">No risk assessment.</p>';
  }

  // Indicators
  const ind = data.indicators || {};
  const keys = ["last_close", "trend", "momentum", "rsi_14", "macd_hist", "annualised_vol", "atr_pct", "volume_ratio", "obv_trend", "bb_pct"];
  $("#indicators").innerHTML = keys
    .filter((k) => k in ind)
    .map((k) => `<div class="indi"><span>${k.replace(/_/g, " ")}</span><span>${ind[k]}</span></div>`)
    .join("");
}

/* ---------- Backtest ---------- */
let equityChart = null;
const PALETTE = ["#5b8cff", "#9b6bff", "#2fd47a", "#ffcc55", "#ff5d6c", "#41d6e0", "#ff9f55"];

$("#backtest-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const btn = $("#b-run");
  const selected = [...document.querySelectorAll("#strategy-chips .chip.on")].map((c) => c.dataset.name);
  if (selected.length === 0) return toast("Select at least one strategy.");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Running…';
  try {
    const data = await api("/api/backtest", {
      symbol: $("#b-symbol").value.trim() || "MSFT",
      days: +$("#b-days").value,
      rebalance_every: +$("#b-rebal").value,
      strategies: selected,
    });
    renderBacktest(data);
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Run backtest";
  }
});

function renderBacktest(data) {
  $("#backtest-results").classList.remove("hidden");
  const results = data.results;

  // All strategies share the same dates/sampling, so use the longest curve's
  // dates as a shared category axis and align each dataset by index.
  const longest = results.reduce((a, b) => (b.equity_curve.length > a.equity_curve.length ? b : a));
  const labels = longest.equity_curve.map((p) => p.date);
  const datasets = results.map((r, i) => ({
    label: r.strategy,
    data: r.equity_curve.map((p) => p.value),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: PALETTE[i % PALETTE.length] + "22",
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.25,
    fill: false,
  }));

  if (equityChart) equityChart.destroy();
  equityChart = new Chart($("#equity-chart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#e6ebf5", usePointStyle: true, font: { size: 12 } } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: $${Number(c.parsed.y).toLocaleString()}` } },
      },
      scales: {
        x: { type: "category", ticks: { color: "#8b97b3", maxTicksLimit: 8, autoSkip: true }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#8b97b3", callback: (v) => "$" + (v / 1000).toFixed(0) + "k" }, grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });

  // Metrics table — highlight best total return.
  const best = results.reduce((b, r) => (r.metrics.total_return > b ? r.metrics.total_return : b), -Infinity);
  const cols = [
    ["total_return", "Total", true],
    ["cagr", "CAGR", true],
    ["sharpe", "Sharpe", false],
    ["sortino", "Sortino", false],
    ["max_drawdown", "Max DD", true],
    ["calmar", "Calmar", false],
    ["win_rate", "Win", true],
  ];
  const head = `<tr><th>Strategy</th>${cols.map((c) => `<th>${c[1]}</th>`).join("")}<th>Trades</th></tr>`;
  const rows = results
    .map((r) => {
      const m = r.metrics;
      const cells = cols
        .map(([key, , pct]) => {
          const v = m[key];
          const txt = pct ? fmtPct(v) : v.toFixed(2);
          const cls = key === "max_drawdown" ? "neg" : v > 0 ? "pos" : v < 0 ? "neg" : "";
          return `<td class="mono ${cls}">${txt}</td>`;
        })
        .join("");
      const rowCls = m.total_return === best ? "best" : "";
      return `<tr class="${rowCls}"><td class="strat">${r.strategy}</td>${cells}<td class="mono">${r.num_trades}</td></tr>`;
    })
    .join("");
  $("#metrics-table").innerHTML = head + rows;
}

boot();
