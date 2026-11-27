import html
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ==============================================================================
# Gold Investment Multi-Agent Quant Decision Workflow (v3)
# Architecture: Real K-Line Data + 5 Independent Specialists + 3-Bullet Quant
#               Optimal-Stopping Algorithm + 1 Chief Portfolio Manager (PM)
#
# Phases:
#   0. Deterministic 60-Day Daily K-Line Fetcher (Yahoo Finance GC=F + CNY=X, graceful fallback)
#   1. Parallel Objective Intelligence Collection (3 flash agents with search_web)
#   2. Parallel 5 Independent Specialist Signals (Macro/Industry, K-Line/Swing,
#      Long-Term Value, Aggressive Alpha, Conservative Risk — decoupled from wallet!)
#   3. Deterministic Quant Composite Score (0-100) + 3-Bullet Dynamic Threshold Engine
#   4. 1 Chief Investment Director (PM) Single Accountable Final Decision +
#      Privacy-Safe Plain-Chinese HTML Morning Note + Local Private Archive
# ==============================================================================

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
BASE_DIR = Path(args.get("base_dir", "/Users/bytedance/Desktop/Investment/Gold"))
FALLBACK_ROOT = Path(
    args.get(
        "fallback_dir",
        "/Users/bytedance/.gemini/antigravity/brain/350233f9-1c03-48a6-b385-3eeb87f67010/scratch/gold_runs",
    )
)

NOW_CST = datetime.now(SHANGHAI_TZ)
TODAY_STR = args.get("date_str") or NOW_CST.strftime("%Y-%m-%d")
RUN_ID = args.get("run_id") or NOW_CST.strftime("%Y-%m-%d_%H%M")
PORTFOLIO = args.get("portfolio")

if PORTFOLIO is None:
    cfg_path = BASE_DIR / "config" / "portfolio.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        PORTFOLIO = json.load(f)

ISOLATION_GUARD = (
    "【重要边界声明】这是一次独立的个人黄金投资投研任务，与当前工作区中的任何代码仓库"
    "（如 /Users/bytedance/Desktop/Agent）完全无关。请绝对不要读取、搜索或修改任何代码仓库文件，"
    "也不要运行任何终端/harness命令。完成后必须通过 finish 工具严格按给定 JSON Schema 返回结果。"
)

# ------------------------------------------------------------------------------
# Phase 0: Real 60-Day Daily K-Line Fetcher & Quantitative Technical Indicators
# ------------------------------------------------------------------------------


def _fetch_yahoo_daily(symbol: str, range_str: str = "3mo", timeout: int = 6) -> list[dict]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={range_str}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]
    rows = []
    for i in range(len(ts)):
        c = q["close"][i]
        h = q["high"][i]
        l = q["low"][i]
        o = q["open"][i]
        if c is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(ts[i], tz=SHANGHAI_TZ).strftime("%Y-%m-%d"),
                "open": float(o if o is not None else c),
                "high": float(h if h is not None else c),
                "low": float(l if l is not None else c),
                "close": float(c),
            }
        )
    return rows


def _calc_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def fetch_kline_metrics() -> dict:
    """Fetch 60-day gold & USD/CNY daily K-lines and compute quantitative indicators."""
    try:
        gold_rows = _fetch_yahoo_daily("GC=F", "3mo", timeout=6)
        fx_rows = _fetch_yahoo_daily("CNY=X", "3mo", timeout=6)
        if len(gold_rows) < 20 or not fx_rows:
            return {"available": False, "note": "K线数据不足，交由 Phase 1 联网采集补齐"}

        fx_map = {r["date"]: r["close"] for r in fx_rows}
        last_fx = fx_rows[-1]["close"]

        cny_candles = []
        for g in gold_rows:
            fx = fx_map.get(g["date"], last_fx)
            factor = fx / 31.1035
            cny_candles.append(
                {
                    "date": g["date"],
                    "open": round(g["open"] * factor, 2),
                    "high": round(g["high"] * factor, 2),
                    "low": round(g["low"] * factor, 2),
                    "close": round(g["close"] * factor, 2),
                    "usd_close": round(g["close"], 2),
                }
            )

        closes = [c["close"] for c in cny_candles]
        last = cny_candles[-1]
        prev = cny_candles[-2]
        overnight_pct = round(((last["close"] - prev["close"]) / prev["close"]) * 100.0, 2)

        ma5 = round(sum(closes[-5:]) / min(5, len(closes)), 2)
        ma20 = round(sum(closes[-20:]) / min(20, len(closes)), 2)
        ma60 = round(sum(closes[-60:]) / min(60, len(closes)), 2)
        rsi14 = _calc_rsi(closes, 14)

        w20 = cny_candles[-20:]
        high20 = max(c["high"] for c in w20)
        low20 = min(c["low"] for c in w20)
        pct20 = round(((last["close"] - low20) / (high20 - low20)) * 100.0, 1) if high20 > low20 else 50.0

        w60 = cny_candles[-60:]
        high60 = max(c["high"] for c in w60)
        low60 = min(c["low"] for c in w60)
        pct60 = round(((last["close"] - low60) / (high60 - low60)) * 100.0, 1) if high60 > low60 else 50.0

        trs = []
        for i in range(max(1, len(cny_candles) - 14), len(cny_candles)):
            h, l, pc = cny_candles[i]["high"], cny_candles[i]["low"], cny_candles[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = round(sum(trs) / len(trs), 2) if trs else None

        # Quantitative K-line value score (0-100): lower percentile & cooler RSI => higher buy value
        rsi_val = rsi14 if rsi14 is not None else 50.0
        rsi_score = max(0.0, min(100.0, (70.0 - rsi_val) * 2.5))
        pct_score = max(0.0, min(100.0, 100.0 - (0.65 * pct20 + 0.35 * pct60)))
        objective_kline_score = round(0.60 * pct_score + 0.40 * rsi_score, 1)

        return {
            "available": True,
            "source": "Yahoo Finance Daily K-Line (GC=F & CNY=X converted to RMB/g)",
            "latest_candle_date": last["date"],
            "latest_close_usd": last["usd_close"],
            "latest_close_cny_g": last["close"],
            "overnight_change_pct": overnight_pct,
            "usdcny_used": round(last_fx, 4),
            "ma5_cny": ma5,
            "ma20_cny": ma20,
            "ma60_cny": ma60,
            "rsi14": rsi14,
            "high_20d_cny": high20,
            "low_20d_cny": low20,
            "percentile_20d": pct20,
            "high_60d_cny": high60,
            "low_60d_cny": low60,
            "percentile_60d": pct60,
            "atr14_cny": atr14,
            "objective_kline_value_score": objective_kline_score,
            "recent_5_candles": cny_candles[-5:],
        }
    except Exception as exc:
        return {
            "available": False,
            "note": f"直连拉取K线暂不可用（{type(exc).__name__}），改由 Phase 1 联网搜索补齐近30/60日K线区间与均线。",
        }


# ------------------------------------------------------------------------------
# JSON Schemas
# ------------------------------------------------------------------------------

SOURCE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source": {"type": "string"},
        "date": {"type": "string"},
        "key_fact": {"type": "string"},
    },
    "required": ["title", "source", "date", "key_fact"],
}

MARKET_KLINE_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "as_of_date": {"type": "string"},
        "xau_usd_price": {"type": "string"},
        "overnight_change_pct": {"type": ["number", "null"]},
        "cny_gold_price_per_gram": {"type": ["number", "null"]},
        "cny_gold_price_note": {"type": "string"},
        "usd_cny_rate": {"type": "string"},
        "dxy_index": {"type": "string"},
        "us10y_yield": {"type": "string"},
        "kline_30d_range_cny": {"type": "string"},
        "kline_technical_summary": {"type": "string"},
        "sources": {"type": "array", "items": SOURCE_ITEM_SCHEMA},
    },
    "required": [
        "as_of_date",
        "xau_usd_price",
        "overnight_change_pct",
        "cny_gold_price_per_gram",
        "cny_gold_price_note",
        "usd_cny_rate",
        "dxy_index",
        "us10y_yield",
        "kline_30d_range_cny",
        "kline_technical_summary",
        "sources",
    ],
}

MACRO_INDUSTRY_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "fed_and_rates_summary": {"type": "string"},
        "us_macro_data_summary": {"type": "string"},
        "central_banks_and_industry_demand": {"type": "string"},
        "fiscal_fx_policy_summary": {"type": "string"},
        "upcoming_key_events": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": SOURCE_ITEM_SCHEMA},
    },
    "required": [
        "fed_and_rates_summary",
        "us_macro_data_summary",
        "central_banks_and_industry_demand",
        "fiscal_fx_policy_summary",
        "upcoming_key_events",
        "sources",
    ],
}

SENTIMENT_FLOWS_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "geopolitics_summary": {"type": "string"},
        "etf_and_institution_flows": {"type": "string"},
        "market_sentiment_label": {
            "type": "string",
            "enum": ["extreme_fear", "fear", "neutral", "greed", "extreme_greed"],
        },
        "institution_views_summary": {"type": "string"},
        "crowded_trade_signals": {"type": "string"},
        "sources": {"type": "array", "items": SOURCE_ITEM_SCHEMA},
    },
    "required": [
        "geopolitics_summary",
        "etf_and_institution_flows",
        "market_sentiment_label",
        "institution_views_summary",
        "crowded_trade_signals",
        "sources",
    ],
}

SPECIALIST_MACRO_SCHEMA = {
    "type": "object",
    "properties": {
        "score_0_to_100": {"type": "integer", "minimum": 0, "maximum": 100},
        "regime_plain": {"type": "string"},
        "sharpest_signal_plain": {"type": "string"},
        "bullish_points": {"type": "array", "items": {"type": "string"}},
        "bearish_points": {"type": "array", "items": {"type": "string"}},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "score_0_to_100",
        "regime_plain",
        "sharpest_signal_plain",
        "bullish_points",
        "bearish_points",
        "analysis_markdown",
    ],
}

SPECIALIST_KLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "score_0_to_100": {"type": "integer", "minimum": 0, "maximum": 100},
        "estimated_30d_percentile": {"type": "integer", "minimum": 0, "maximum": 100},
        "realistic_dip_buy_zone_cny": {"type": "string"},
        "defense_break_line_cny": {"type": "string"},
        "short_tp_zone_cny": {"type": "string"},
        "sharpest_signal_plain": {"type": "string"},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "score_0_to_100",
        "estimated_30d_percentile",
        "realistic_dip_buy_zone_cny",
        "defense_break_line_cny",
        "short_tp_zone_cny",
        "sharpest_signal_plain",
        "analysis_markdown",
    ],
}

SPECIALIST_LONGTERM_SCHEMA = {
    "type": "object",
    "properties": {
        "score_0_to_100": {"type": "integer", "minimum": 0, "maximum": 100},
        "long_tp_zone_cny": {"type": "string"},
        "sharpest_signal_plain": {"type": "string"},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "score_0_to_100",
        "long_tp_zone_cny",
        "sharpest_signal_plain",
        "analysis_markdown",
    ],
}

SPECIALIST_AGGRESSIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "score_0_to_100": {"type": "integer", "minimum": 0, "maximum": 100},
        "bold_proposal_plain": {"type": "string"},
        "cost_of_waiting_plain": {"type": "string"},
        "sharpest_signal_plain": {"type": "string"},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "score_0_to_100",
        "bold_proposal_plain",
        "cost_of_waiting_plain",
        "sharpest_signal_plain",
        "analysis_markdown",
    ],
}

SPECIALIST_RISK_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_deduction_0_to_20": {"type": "integer", "minimum": 0, "maximum": 20},
        "steady_proposal_plain": {"type": "string"},
        "sharpest_signal_plain": {"type": "string"},
        "top_3_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "desc": {"type": "string"},
                },
                "required": ["tag", "desc"],
            },
        },
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "risk_deduction_0_to_20",
        "steady_proposal_plain",
        "sharpest_signal_plain",
        "top_3_risks",
        "analysis_markdown",
    ],
}

RADAR_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "price_range": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["price_range", "note"],
}

PM_FINAL_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "universal_action": {
            "type": "string",
            "enum": ["BUY_SHOT", "HOLD", "TAKE_PROFIT_PARTIAL", "REDUCE_HEAVY"],
        },
        "personal_action": {
            "type": "string",
            "enum": ["BUY_SHOT", "HOLD", "TAKE_PROFIT_PARTIAL", "REDUCE_HEAVY"],
        },
        "headline": {"type": "string"},
        "plain_takeaway": {"type": "string"},
        "recommended_amount_short": {"type": "string"},
        "kline_thermometer_plain": {"type": "string"},
        "steady_option_plain": {"type": "string"},
        "bold_option_plain": {"type": "string"},
        "macro_one_liner": {"type": "string"},
        "short_term_one_liner": {"type": "string"},
        "long_term_one_liner": {"type": "string"},
        "radar_dip_buy": RADAR_ITEM_SCHEMA,
        "radar_defense": RADAR_ITEM_SCHEMA,
        "radar_short_tp": RADAR_ITEM_SCHEMA,
        "radar_long_tp": RADAR_ITEM_SCHEMA,
        "specialist_email_lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "score_badge": {"type": "string"},
                    "signal": {"type": "string"},
                },
                "required": ["role", "score_badge", "signal"],
            },
        },
        "risk_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "desc": {"type": "string"},
                },
                "required": ["tag", "desc"],
            },
        },
        "personal_private_note_markdown": {"type": "string"},
        "public_decision_markdown": {"type": "string"},
    },
    "required": [
        "universal_action",
        "personal_action",
        "headline",
        "plain_takeaway",
        "recommended_amount_short",
        "kline_thermometer_plain",
        "steady_option_plain",
        "bold_option_plain",
        "macro_one_liner",
        "short_term_one_liner",
        "long_term_one_liner",
        "radar_dip_buy",
        "radar_defense",
        "radar_short_tp",
        "radar_long_tp",
        "specialist_email_lines",
        "risk_items",
        "personal_private_note_markdown",
        "public_decision_markdown",
    ],
}

# ------------------------------------------------------------------------------
# Quantitative 3-Bullet Optimal-Stopping Engine & Portfolio Math
# ------------------------------------------------------------------------------


def compute_quant_and_bullets(
    *,
    portfolio: dict,
    cny_price: float | None,
    overnight_chg: float | None,
    today_str: str,
    kline_data: dict,
    specialists: dict,
) -> dict:
    pos = portfolio["position"]
    principal = float(pos["principal_cny"])
    avg_cost = float(pos["average_cost_cny_per_gram"])
    grams = principal / avg_cost

    algo = portfolio.get("allocation_algorithm", {})
    shot_amt = int(algo.get("shot_amount_cny", 1200))
    max_shots = int(algo.get("max_shots_per_month", 3))
    th = algo.get("shot_thresholds", {"shot_1": 65, "shot_2": 72, "shot_3": 80})
    t1 = int(th.get("shot_1", 65))
    t2 = int(th.get("shot_2", 72))
    t3 = int(th.get("shot_3", 80))
    decay_day = int(algo.get("mid_month_decay_day", 15))
    decay_t1 = int(algo.get("mid_month_shot1_threshold", 60))
    tp_th = int(algo.get("take_profit_score_threshold", 30))
    min_cooldown = int(algo.get("min_cooldown_days", 2))
    emerg_drop = float(algo.get("emergency_drop_override_pct", -2.0))

    tracker = portfolio.get("monthly_shot_tracker", {})
    cur_ym = today_str[:7]
    cur_day = int(today_str[8:10])
    if tracker.get("month") == cur_ym:
        shots_used = int(tracker.get("shots_used", 0))
        last_buy_date = tracker.get("last_buy_date")
        last_buy_price = tracker.get("last_buy_price_cny_per_gram")
    else:
        # New month auto-reset!
        shots_used = 0
        last_buy_date = None
        last_buy_price = None

    remaining_shots = max(0, max_shots - shots_used)

    # Cooldown check
    days_since_last_buy = None
    cooldown_active = False
    if last_buy_date:
        try:
            d_last = datetime.strptime(last_buy_date, "%Y-%m-%d").date()
            d_now = datetime.strptime(today_str, "%Y-%m-%d").date()
            days_since_last_buy = (d_now - d_last).days
            if days_since_last_buy < min_cooldown and not (
                overnight_chg is not None and overnight_chg <= emerg_drop
            ):
                cooldown_active = True
        except Exception:
            pass

    # Compute deterministic composite buy-value score (0-100)
    s_macro = float(specialists["macro"]["score_0_to_100"])
    s_kline = float(specialists["kline"]["score_0_to_100"])
    s_long = float(specialists["long_term"]["score_0_to_100"])
    s_aggr = float(specialists["aggressive"]["score_0_to_100"])
    r_deduct = float(specialists["risk"]["risk_deduction_0_to_20"])

    if kline_data.get("available") and kline_data.get("objective_kline_value_score") is not None:
        s_obj_kline = float(kline_data["objective_kline_value_score"])
        raw_alpha = 0.25 * s_kline + 0.20 * s_macro + 0.20 * s_long + 0.20 * s_aggr + 0.15 * s_obj_kline
    else:
        # Use K-line specialist's estimated 30d percentile as objective anchor
        est_pct = float(specialists["kline"]["estimated_30d_percentile"])
        s_obj_kline = round(100.0 - est_pct, 1)
        raw_alpha = 0.25 * s_kline + 0.20 * s_macro + 0.20 * s_long + 0.20 * s_aggr + 0.15 * s_obj_kline

    risk_penalty_applied = round(0.60 * r_deduct, 1)
    composite_score = int(round(max(0.0, min(100.0, raw_alpha - risk_penalty_applied))))

    if composite_score >= 80:
        score_zone = "黄金深坑区（极划算）"
    elif composite_score >= 72:
        score_zone = "高性价比区（值得增强）"
    elif composite_score >= 65:
        score_zone = "偏划算区（适合建仓）"
    elif composite_score > tp_th:
        score_zone = "中性震荡区（可观察或小步试探）"
    else:
        score_zone = "偏贵过热区（适合止盈落袋）"

    # Effective shot 1 threshold (mid-month anti-miss-out decay)
    eff_t1 = decay_t1 if (cur_day >= decay_day and shots_used == 0) else t1

    # Universal 3-bullet ladder (for shared privacy-safe email)
    bullet_ladder = [
        (
            "第 1 颗 · 底仓弹",
            t1,
            composite_score >= t1,
            "已达买点 · 可出手" if composite_score >= t1 else f"差 {t1 - composite_score} 分达标",
        ),
        (
            "第 2 颗 · 增强弹",
            t2,
            composite_score >= t2,
            "已达买点 · 可出手" if composite_score >= t2 else f"差 {t2 - composite_score} 分达标",
        ),
        (
            "第 3 颗 · 深坑弹",
            t3,
            composite_score >= t3,
            "已达深坑 · 重手买" if composite_score >= t3 else f"差 {t3 - composite_score} 分达标",
        ),
    ]

    if composite_score <= tp_th:
        universal_signal = "TAKE_PROFIT_PARTIAL"
    elif composite_score >= t1:
        universal_signal = "BUY_SHOT"
    else:
        universal_signal = "HOLD"

    # Personal next-shot trigger (for local private 04_decision.md ONLY)
    if remaining_shots == 0:
        personal_next_shot = None
        personal_threshold = None
        personal_signal = "TAKE_PROFIT_PARTIAL" if composite_score <= tp_th else "HOLD"
        personal_reason = "本月 3 颗子弹已全部用完，等下月 1 日自动刷新。"
    else:
        personal_next_shot = shots_used + 1
        personal_threshold = {1: eff_t1, 2: t2, 3: t3}.get(personal_next_shot, t3)
        if composite_score <= tp_th:
            personal_signal = "TAKE_PROFIT_PARTIAL"
            personal_reason = f"综合买点分降至 {composite_score}（≤ {tp_th}），进入过热区建议部分止盈。"
        elif cooldown_active:
            personal_signal = "HOLD"
            personal_reason = f"距上次买入仅 {days_since_last_buy} 天，处于冷却期（除非单日暴跌 ≥ 2%）。"
        elif composite_score >= personal_threshold:
            personal_signal = "BUY_SHOT"
            personal_reason = f"综合分 {composite_score} ≥ 第 {personal_next_shot} 颗子弹门槛 {personal_threshold}，触发买入 {shot_amt} 元！"
        else:
            personal_signal = "HOLD"
            personal_reason = (
                f"综合分 {composite_score}，距你本月第 {personal_next_shot} 颗子弹门槛 {personal_threshold} "
                f"还差 {personal_threshold - composite_score} 分。"
            )

    pnl_cny = None
    pnl_pct = None
    market_value = None
    if cny_price and cny_price > 0:
        market_value = round(grams * cny_price, 2)
        pnl_cny = round(market_value - principal, 2)
        pnl_pct = round((pnl_cny / principal) * 100.0, 2)

    return {
        "composite_score": composite_score,
        "score_zone_label": score_zone,
        "score_breakdown": {
            "macro_industry": s_macro,
            "kline_swing": s_kline,
            "long_term_value": s_long,
            "aggressive_alpha": s_aggr,
            "objective_kline_percentile_score": s_obj_kline,
            "raw_alpha": round(raw_alpha, 1),
            "risk_deduction_raw": r_deduct,
            "risk_penalty_applied": risk_penalty_applied,
        },
        "shot_amount_cny": shot_amt,
        "max_shots_per_month": max_shots,
        "bullet_ladder": bullet_ladder,
        "universal_signal": universal_signal,
        "personal_state": {
            "month": cur_ym,
            "shots_used": shots_used,
            "remaining_shots": remaining_shots,
            "next_shot_number": personal_next_shot,
            "active_threshold": personal_threshold,
            "cooldown_active": cooldown_active,
            "last_buy_date": last_buy_date,
            "last_buy_price_cny": last_buy_price,
            "personal_signal": personal_signal,
            "personal_reason": personal_reason,
            "principal_cny": round(principal, 2),
            "average_cost_cny_per_gram": round(avg_cost, 2),
            "estimated_grams": round(grams, 4),
            "current_market_value_cny": market_value,
            "unrealized_pnl_cny": pnl_cny,
            "unrealized_pnl_pct": pnl_pct,
        },
    }


# ------------------------------------------------------------------------------
# HTML Email Renderer (v3 Plain-Chinese Institutional Morning Note)
# ------------------------------------------------------------------------------


def action_badge_style(action: str) -> tuple[str, str]:
    return {
        "BUY_SHOT": ("#0f766e", "触发买点 · 建议买 1 笔 (1,200元)"),
        "HOLD": ("#475569", "暂不扣扳机 · 留好子弹"),
        "TAKE_PROFIT_PARTIAL": ("#b45309", "偏贵过热 · 建议先卖出一笔落袋"),
        "REDUCE_HEAVY": ("#b91c1c", "风险偏高 · 建议减仓避险"),
    }.get(action, ("#334155", action))


def score_color(score: int) -> str:
    if score >= 75:
        return "#15803d"
    if score >= 65:
        return "#0369a1"
    if score <= 35:
        return "#b91c1c"
    return "#b45309"


def render_v3_email_html(
    *,
    date_str: str,
    headline: str,
    plain_takeaway: str,
    action: str,
    recommended_amount_short: str,
    composite_score: int,
    score_zone_label: str,
    cny_price: float | None,
    xau_usd_short: str,
    kline_thermometer_text: str,
    shot_amount_cny: int,
    max_shots_per_month: int,
    bullet_ladder: list[tuple[str, int, bool, str]],
    outlook_bullets: list[tuple[str, str]],
    price_radar: list[tuple[str, str, str, str]],
    steady_option: str,
    bold_option: str,
    specialist_rows: list[tuple[str, str, str]],
    risk_bullets: list[tuple[str, str]],
) -> str:
    """Privacy-safe plain-Chinese Morning Note HTML (NEVER exposes personal holdings/cost/PnL/shots)."""
    esc = html.escape
    badge_bg, action_cn = action_badge_style(action)
    s_color = score_color(composite_score)
    cny_price_str = f"{cny_price} 元/克" if cny_price is not None else "待核实"

    ladder_cells = "".join(
        f"""
        <td style="width:33.3%;padding:4px;vertical-align:top;">
          <div style="background:{'#ecfdf5' if triggered else '#f8fafc'};border:1px solid {'#86efac' if triggered else '#e2e8f0'};border-radius:6px;padding:9px 8px;text-align:center;">
            <div style="font-size:11px;font-weight:700;color:{'#166534' if triggered else '#475569'};">{esc(name)}</div>
            <div style="font-size:14px;font-weight:800;color:#0f172a;margin:3px 0;">门槛 ≥ {threshold} 分</div>
            <div style="font-size:11px;font-weight:700;color:{'#15803d' if triggered else '#64748b'};">{esc(status)}</div>
          </div>
        </td>
        """
        for name, threshold, triggered, status in bullet_ladder
    )

    outlook_html = "".join(
        f"""
        <tr>
          <td style="padding:7px 0;vertical-align:top;width:96px;">
            <span style="display:inline-block;padding:3px 8px;border-radius:4px;background:#f1f5f9;color:#334155;font-size:12px;font-weight:700;white-space:nowrap;">{esc(tag)}</span>
          </td>
          <td style="padding:7px 0 7px 10px;color:#1e293b;font-size:13.5px;line-height:1.6;">{esc(desc)}</td>
        </tr>
        """
        for tag, desc in outlook_bullets
    )

    radar_cells = "".join(
        f"""
        <td style="width:25%;padding:4px;vertical-align:top;">
          <div style="background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {accent};border-radius:6px;padding:10px 6px;text-align:center;">
            <div style="font-size:11px;color:#475569;font-weight:700;line-height:1.35;">{esc(label)}</div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin:6px 0 4px;">{esc(price_range)}</div>
            <div style="font-size:11px;color:#64748b;line-height:1.4;">{esc(note)}</div>
          </div>
        </td>
        """
        for label, price_range, note, accent in price_radar
    )

    spec_html = "".join(
        f"""
        <tr>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;font-weight:700;color:#1e293b;white-space:nowrap;">{esc(role)}</td>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;white-space:nowrap;">
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;background:#f1f5f9;color:#0f172a;font-size:11.5px;font-weight:700;">{esc(score_txt)}</span>
          </td>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;color:#334155;line-height:1.5;">{esc(signal)}</td>
        </tr>
        """
        for role, score_txt, signal in specialist_rows
    )

    r_items = "".join(
        f"""
        <li style="margin-bottom:6px;font-size:13px;color:#334155;line-height:1.55;">
          <strong style="color:#b91c1c;">【{esc(tag)}】</strong>{esc(desc)}
        </li>
        """
        for tag, desc in risk_bullets
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:16px;background:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue','Microsoft YaHei',sans-serif;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.10);">
    <div style="background:#0f172a;padding:20px 24px 18px;border-bottom:3px solid #d97706;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="font-size:11px;letter-spacing:1.2px;color:#f59e0b;font-weight:700;">黄金投研晨报 · 5专家供弹 + 总监拍板版</td>
          <td style="text-align:right;font-size:12px;color:#94a3b8;">{esc(date_str)}</td>
        </tr>
      </table>
      <h1 style="margin:10px 0 12px;font-size:19px;line-height:1.4;color:#ffffff;font-weight:700;">{esc(headline)}</h1>
      <div>
        <span style="display:inline-block;padding:4px 11px;border-radius:4px;background:{badge_bg};color:#ffffff;font-size:12px;font-weight:700;">总监拍板：{esc(action_cn)}</span>
        <span style="display:inline-block;margin-left:8px;font-size:12px;color:#cbd5e1;">今日买点分：{composite_score}/100（{esc(score_zone_label)}）</span>
      </div>
    </div>

    <div style="background:#f8fafc;border-bottom:1px solid #e2e8f0;padding:14px 20px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:34%;padding-right:10px;border-right:1px solid #e2e8f0;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">今日参考国内金价</div>
            <div style="font-size:20px;font-weight:800;color:#0f172a;margin-top:3px;">{esc(cny_price_str)}</div>
            <div style="font-size:11px;color:#64748b;margin-top:2px;">国际：{esc(xau_usd_short)}</div>
          </td>
          <td style="width:33%;padding:0 12px;border-right:1px solid #e2e8f0;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">今日入场性价比分</div>
            <div style="font-size:22px;font-weight:800;color:{s_color};margin-top:2px;">{composite_score} <span style="font-size:12px;font-weight:600;color:#64748b;">/ 100</span></div>
            <div style="font-size:11px;color:#64748b;margin-top:2px;">{esc(score_zone_label)}</div>
          </td>
          <td style="width:33%;padding-left:12px;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">总监建议动作</div>
            <div style="font-size:17px;font-weight:800;color:{badge_bg};margin-top:4px;">{esc(recommended_amount_short)}</div>
            <div style="font-size:11px;color:#64748b;margin-top:3px;">模型：每月最多{max_shots_per_month}笔×{shot_amount_cny:,}元</div>
          </td>
        </tr>
      </table>
    </div>

    <div style="margin:18px 24px 0;background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #d97706;border-radius:6px;padding:11px 14px;font-size:13.5px;color:#78350f;line-height:1.6;">
      <strong>💡 一句话看懂今天：</strong>{esc(plain_takeaway)}
    </div>

    <div style="padding:18px 24px 22px;">
      <div>
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">01 ｜ 3 颗子弹算法触发灯（每月最多 {max_shots_per_month} 次 × {shot_amount_cny:,} 元）</div>
        <div style="font-size:12.5px;color:#334155;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:8px;line-height:1.5;">
          <strong>📊 K 线位置温度计：</strong>{esc(kline_thermometer_text)}
        </div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>{ladder_cells}</tr></table>
      </div>

      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">02 ｜ 稳健做法 vs 大胆做法（按自己性格选）</div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
          <tr>
            <td style="width:50%;padding:0 5px 0 0;vertical-align:top;">
              <div style="background:#f8fafc;border:1px solid #cbd5e1;border-left:4px solid #475569;border-radius:6px;padding:10px 12px;font-size:13px;color:#1e293b;line-height:1.55;">
                <div style="font-weight:800;color:#334155;margin-bottom:4px;">🛡️ 稳健做法</div>
                {esc(steady_option)}
              </div>
            </td>
            <td style="width:50%;padding:0 0 0 5px;vertical-align:top;">
              <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-left:4px solid #15803d;border-radius:6px;padding:10px 12px;font-size:13px;color:#14532d;line-height:1.55;">
                <div style="font-weight:800;color:#166534;margin-bottom:4px;">🔥 大胆做法</div>
                {esc(bold_option)}
              </div>
            </td>
          </tr>
        </table>
      </div>

      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:10px;">03 ｜ 盯住这 4 个实用价格（单位：元 / 克）</div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>{radar_cells}</tr></table>
      </div>

      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">04 ｜ 现在黄金是什么行情？（人话版）</div>
        <table style="width:100%;border-collapse:collapse;"><tbody>{outlook_html}</tbody></table>
      </div>

      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">05 ｜ 5 位专业顾问各自最核心的 1 句话干货</div>
        <table style="width:100%;border-collapse:collapse;font-size:12.5px;">
          <thead>
            <tr style="background:#f8fafc;color:#64748b;text-align:left;">
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">专业角色</th>
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">信号打分</th>
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">最有价值的一句话</th>
            </tr>
          </thead>
          <tbody>{spec_html}</tbody>
        </table>
      </div>

      <div style="margin-top:18px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 14px;">
        <div style="font-size:12.5px;font-weight:800;color:#991b1b;margin-bottom:6px;">06 ｜ 近期最需要注意的 3 个风险</div>
        <ul style="margin:0;padding-left:18px;">{r_items}</ul>
      </div>

      <div style="margin-top:18px;padding-top:12px;border-top:1px solid #e2e8f0;font-size:11.5px;color:#64748b;line-height:1.55;">
        <div>免责声明：本晨报由多 Agent 量化投研系统自动整理，按「每月最多 {max_shots_per_month} 笔 × {shot_amount_cny:,} 元」通用算法模型测算，不含个人持仓或个人交易次数，仅供学习与决策参考，不构成持牌金融投资建议。</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# PHASE 0 & 1: REAL K-LINE FETCH + PARALLEL INFORMATION COLLECTION
# ==============================================================================

phase("Phase 1: 真K线数据与并发信息采集")
log(f"启动黄金投研算法 Workflow v3 | Run ID: {RUN_ID} | 日期: {TODAY_STR}")

kline_data = fetch_kline_metrics()
log(
    f"K线量化模块状态: available={kline_data['available']} | "
    + (
        f"收盘折算={kline_data['latest_close_cny_g']} RMB/g, MA20={kline_data['ma20_cny']}, "
        f"RSI14={kline_data['rsi14']}, 20日分位={kline_data['percentile_20d']}%, 客观K线分={kline_data['objective_kline_value_score']}"
        if kline_data["available"]
        else kline_data["note"]
    )
)

collector_specs = [
    {
        "key": "market",
        "role": "实时行情与K线采集员",
        "schema": MARKET_KLINE_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【实时行情与K线采集员】。今天是 {TODAY_STR}（北京时间）。
请使用 search_web 搜索今天（或最近一个交易日）最新的黄金行情与 K 线技术面客观数据：
1. 国际现货黄金（XAU/USD）价格与日内/隔夜涨跌幅（overnight_change_pct 纯数字）；
2. 中国国内人民币黄金参考克价（上海黄金交易所 AU9999 / 沪金主力 / 银行积存金克价），纯数字填入 cny_gold_price_per_gram；
3. USD/CNY 汇率、美元指数 DXY、美国10年期国债收益率；
4. 近 30 个交易日国内黄金 K 线高低区间（kline_30d_range_cny）及当前均线/超买超卖等技术形态客观摘要（kline_technical_summary）。
严格只汇报客观数据与来源，不做买卖建议。
""",
    },
    {
        "key": "macro",
        "role": "宏观与行业基本面采集员",
        "schema": MACRO_INDUSTRY_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【宏观与行业基本面采集员】。今天是 {TODAY_STR}。
请使用 search_web 搜索近期影响黄金走势的宏观经济、央行政策与黄金行业供需新闻：
1. 美联储利率政策、官员表态与市场利率预期；
2. 最新美国通胀、就业、经济数据；
3. 中国央行（PBOC）及全球央行最新购金动态 + 黄金行业实物/金饰/工业供需动态；
4. 财政赤字、关税或汇率政策新闻；
5. 未来 2–4 周重要宏观日历事件。
只输出客观事实与来源日期，不做交易建议。
""",
    },
    {
        "key": "sentiment",
        "role": "地缘情绪与机构资金采集员",
        "schema": SENTIMENT_FLOWS_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【地缘情绪与机构资金采集员】。今天是 {TODAY_STR}。
请使用 search_web 搜索近期地缘局势、机构资金流向与市场情绪动态：
1. 重大地缘政治与避险事件；
2. 全球黄金 ETF（SPDR GLD）与中国国内黄金 ETF 资金流入/流出；
3. 主流投行（高盛、瑞银、世界黄金协会等）最新观点与目标价；
4. 期货多空拥挤度与散户/机构情绪冷暖特征。
保持中立客观并标注来源日期。
""",
    },
]

collector_results_list = await parallel(
    collector_specs,
    lambda s: agent(s["prompt"], schema=s["schema"], role=s["role"], model="flash"),
)
intel = {collector_specs[i]["key"]: collector_results_list[i] for i in range(len(collector_specs))}
cny_price = intel["market"].get("cny_gold_price_per_gram") or kline_data.get("latest_close_cny_g")
overnight_chg = intel["market"].get("overnight_change_pct")
if overnight_chg is None and kline_data.get("available"):
    overnight_chg = kline_data.get("overnight_change_pct")

log(
    f"Phase 1 完成 | 国内参考克价: {cny_price} RMB/g | 国际: {intel['market']['xau_usd_price'][:40]} | "
    f"情绪: {intel['sentiment']['market_sentiment_label']}"
)

objective_data_bundle = json.dumps(
    {
        "date": TODAY_STR,
        "cny_gold_price_per_gram": cny_price,
        "quant_kline_metrics": kline_data,
        "market_kline_intel": intel["market"],
        "macro_industry_intel": intel["macro"],
        "sentiment_flows_intel": intel["sentiment"],
    },
    ensure_ascii=False,
    indent=2,
)

# ==============================================================================
# PHASE 2: 5 INDEPENDENT SPECIALISTS (PARALLEL, DECOUPLED FROM USER WALLET!)
# ==============================================================================

phase("Phase 2: 5位专家独立供弹与客观打分")

specialist_specs = [
    {
        "key": "macro",
        "role": "① 宏观与行业专家",
        "schema": SPECIALIST_MACRO_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是顶级投行投研组的【① 宏观与行业专家】。今天是 {TODAY_STR}。
【核心要求】不要考虑任何个人钱包或预算限制，只纯粹从宏观经济、央行购金、利率汇率与黄金行业供需出发，给出客观、锋利的判断：
1. 打出 `score_0_to_100`（50=中性，65+=宏观行业支持逢低买入，80+=强顺风，35以下=显著逆风过热）；
2. 用普通人秒懂的大白话提炼 1 句最有价值的核心信号（`sharpest_signal_plain`，≤ 26 字，禁用英文缩写）；
3. 列出核心利多/利空并写清分析正文（analysis_markdown）。

【今日客观行情、K线与情报包】
{objective_data_bundle}
""",
    },
    {
        "key": "kline",
        "role": "② K线与短线波段专家",
        "schema": SPECIALIST_KLINE_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是顶级投行投研组的【② K线与短线波段专家】。今天是 {TODAY_STR}。
【核心要求】完全独立于个人钱包，严格基于日 K 线价格区间、均线、波动与超买超卖状态做客观技术评估：
1. 打出 `score_0_to_100`（当前位置买入的短线性价比：价格处于近30日低位企稳/超跌则给高分 68–88；半山腰震荡给 45–62；高位超买给 20–38）；
2. 给出 `estimated_30d_percentile`（0=近30天最便宜，100=近30天最贵）；
3. 给出 **白天上班族真实能买得到的实用区间**（不要只画半夜瞬间插针买不到的纸面最低价！）：
   - `realistic_dip_buy_zone_cny`（温和回踩即可成交的实用买点区间，如 `748–758`）
   - `defense_break_line_cny`（有效跌破则停买观望的防守线，**必须低于加仓区下沿至少 15 元以上**，绝不重叠！）
   - `short_tp_zone_cny`（短线波段止盈区间）
4. 用大白话提炼 1 句核心信号（`sharpest_signal_plain`，≤ 26 字，禁用英文缩写）。

【今日客观行情、K线与情报包】
{objective_data_bundle}
""",
    },
    {
        "key": "long_term",
        "role": "③ 长线价值定投派",
        "schema": SPECIALIST_LONGTERM_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是顶级投行投研组的【③ 长线价值定投派】。今天是 {TODAY_STR}。
【核心要求】专注 3–12 个月大周期估值与定投性价比。你的职责是防止投资人因为死等一个“永远不来的完美最低点”而错失长期建仓窗口！
1. 打出 `score_0_to_100`（只要大逻辑未破、价格已较前期高点显著回调进入合理积累区，就应诚实给出 65–85 分，不要因为下周有短期宏观数据就偷懒给低分！如果已泡沫过热再给低分）；
2. 给出长线大赚后的分批止盈区间 `long_tp_zone_cny`；
3. 用大白话提炼 1 句核心信号（`sharpest_signal_plain`，≤ 26 字，禁用英文缩写）。

【今日客观行情、K线与情报包】
{objective_data_bundle}
""",
    },
    {
        "key": "aggressive",
        "role": "④ 激进机会派（进攻前锋）",
        "schema": SPECIALIST_AGGRESSIVE_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是顶级投行投研组的【④ 激进机会派（进攻前锋）】。今天是 {TODAY_STR}。
【核心使命】你是整个投研组专门负责**挖掘高收益进攻机会与评估踏空代价**的锋线专家！
- **绝对禁止拿“下周有数据/再等等更安全”当借口躺平**！
- 请尖锐地评估：当前市场恐慌/回调/反弹结构里，是否存在值得大胆出击的买点（或高抛做差价机会）？如果今天不出手，未来 2 周踏空的代价有多大？
1. 给出客观的 `score_0_to_100`（进攻吸引力：只要存在明显错杀、反弹动能或高赔率回调就敢给 68–90；只有真正严重过热追高无肉吃才给低分）；
2. 用大白话给出 `bold_proposal_plain`（≤ 38 字，如“盘中回踩 758 下方可先买一笔 1,200 元，弹到 805 做波段”）；
3. 写清 `cost_of_waiting_plain`（继续死等可能错过的机会）及 1 句核心信号 `sharpest_signal_plain`（≤ 26 字，禁用英文缩写）。

【今日客观行情、K线与情报包】
{objective_data_bundle}
""",
    },
    {
        "key": "risk",
        "role": "⑤ 保守风控派（红队盾牌）",
        "schema": SPECIALIST_RISK_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是顶级投行投研组的【⑤ 保守风控派（红队盾牌）】。今天是 {TODAY_STR}。
【核心使命】你的职责是**客观量化真实下行风险与追高陷阱**，给投资总监提供安全带，但不要为了免责动不动把风险拉满！
1. 给出 `risk_deduction_0_to_20`（风险扣分，0–20 分）：
   - `0–5`：风险低，回调充分、安全边际高；
   - `6–12`：中等常规波动风险（如普通数据日、常规震荡）；
   - `13–20`：高危陷阱（如明显高位追涨过热、大机构疯狂抛售叠加重大黑天鹅、银行加价离谱）。
2. 用大白话给出 `steady_proposal_plain`（≤ 38 字，稳健投资人今天该怎么执行）；
3. 用大白话列出最值得警惕的 3 个风险 `top_3_risks`（每条 `tag` 4–6字 + `desc` ≤ 34字，禁用 `PCE/CPI/FOMC/ETF/ATR/DXY` 等英文缩写！）及 1 句核心信号 `sharpest_signal_plain`（≤ 26 字）。

【今日客观行情、K线与情报包】
{objective_data_bundle}
""",
    },
]

specialist_results = await parallel(
    specialist_specs,
    lambda s: agent(s["prompt"], schema=s["schema"], role=s["role"], model="inherit"),
)
specialists = {specialist_specs[i]["key"]: specialist_results[i] for i in range(len(specialist_specs))}

# ==============================================================================
# PHASE 3: DETERMINISTIC QUANT SCORE & 3-BULLET OPTIMAL STOPPING ENGINE
# ==============================================================================

phase("Phase 3: 量化得分合成与 3 颗子弹算法计算")

quant = compute_quant_and_bullets(
    portfolio=PORTFOLIO,
    cny_price=cny_price,
    overnight_chg=overnight_chg,
    today_str=TODAY_STR,
    kline_data=kline_data,
    specialists=specialists,
)
log(
    f"量化合成完成 | 综合买点分: {quant['composite_score']}/100 ({quant['score_zone_label']}) | "
    f"通用算法信号: {quant['universal_signal']} | "
    f"个人信号(本月剩余{quant['personal_state']['remaining_shots']}颗): {quant['personal_state']['personal_signal']}"
)

# ==============================================================================
# PHASE 4: 1 CHIEF PORTFOLIO MANAGER (PM) FINAL DECISION & ARCHIVE
# ==============================================================================

phase("Phase 4: 投资总监(PM)唯一拍板与大白话晨报生成")

pm_briefing = json.dumps(
    {
        "date": TODAY_STR,
        "cny_gold_price_per_gram": cny_price,
        "xau_usd": intel["market"]["xau_usd_price"],
        "quant_kline_metrics": kline_data,
        "quant_algorithm_result": quant,
        "specialists_summary": {
            "macro": {k: v for k, v in specialists["macro"].items() if k != "analysis_markdown"},
            "kline": {k: v for k, v in specialists["kline"].items() if k != "analysis_markdown"},
            "long_term": {k: v for k, v in specialists["long_term"].items() if k != "analysis_markdown"},
            "aggressive": {k: v for k, v in specialists["aggressive"].items() if k != "analysis_markdown"},
            "risk": {k: v for k, v in specialists["risk"].items() if k != "analysis_markdown"},
        },
    },
    ensure_ascii=False,
    indent=2,
)

pm_prompt = f"""{ISOLATION_GUARD}
你是顶级多策略基金的【唯一拍板官：首席投资总监（Chief Portfolio Manager）】。今天是 {TODAY_STR}。
下面 5 位专业顾问已经各自独立提交了最锋利的情报和打分，Python 算法引擎也已经算出了**今日入场性价比综合分（{quant['composite_score']}/100）**和**3 颗子弹（每次 1,200 元，每月最多 3 次）动态门槛结果**。

现在由你做**最终唯一拍板**，同时生成两套严格区分受众的输出：
- **对外共享邮件字段**（`universal_action`, `headline`, `plain_takeaway`, `recommended_amount_short`, `kline_thermometer_plain`, `steady_option_plain`, `bold_option_plain`, `macro_one_liner`, `short_term_one_liner`, `long_term_one_liner`, `radar_*`, `specialist_email_lines`, `risk_items`, `public_decision_markdown`）：
  1. **严格隐私脱敏**：绝不允许出现任何个人持仓金额、个人均价（如 840.31）、个人克数、个人浮亏，**也不要暴露“你这个月已经用了几颗子弹”**！只按「通用每月最多 3 笔 × 1,200 元（第 1 颗 ≥ 65 分 / 第 2 颗 ≥ 72 分 / 第 3 颗 ≥ 80 分）」和客观综合分（{quant['composite_score']} 分）给出清晰结论。
  2. **彻底大白话，禁用金融黑话与英文缩写**：绝对禁止出现 `PCE`、`CPI`、`GDP`、`FOMC`、`ATR`、`DXY`、`ETF`、`RSI`、`MA20`、`赔率`、`收破`、`滞涨`、`去杠杆`、`右侧`、`左侧`、`点阵图` 等词！全部用普通人 20 秒秒懂的大白话表达（比如把 RSI/分位翻译成“当前价格处于近一个月偏低位置，比过去 30 天里大多数日子便宜”）。
  3. **稳胆平衡，不偏不倚**：`universal_action` 严格尊重通用算法信号（`{quant['universal_signal']}`）；同时在 `steady_option_plain`（≤ 44字）和 `bold_option_plain`（≤ 44字）里分别把「稳健做法」和「大胆做法」的实用白天价位说清楚！
  4. **4 个价位卡必须清晰分开不重叠**：`radar_defense` 必须严格低于 `radar_dip_buy` 下沿至少 15 元以上；`note` 每条 ≤ 12 字。
  5. `specialist_email_lines` 恰好 5 条，对应 5 位专家（`宏观与行业` / `K线短线派` / `长线定投派` / `激进机会派` / `保守风控派`），`score_badge` 写如 `72分` 或 `扣10分`，`signal` ≤ 26 字大白话。
  6. `risk_items` 恰好 3 条大白话。
- **本地私密记录字段**（`personal_action`, `personal_private_note_markdown`）：
  - 仅写入用户本机档案 `04_decision.md`，这里可以结合用户的真实本月子弹进度（`personal_state`：本月已用 {quant['personal_state']['shots_used']}/3 颗、剩余 {quant['personal_state']['remaining_shots']} 颗、下次是第 {quant['personal_state']['next_shot_number']} 颗门槛 {quant['personal_state']['active_threshold']} 分，下月 1 日自动重置为 0/3 颗）给出精准个人执行备忘！

【5 专家汇总 + 量化算法状态包】
{pm_briefing}
"""

pm_decision = await agent(
    pm_prompt,
    schema=PM_FINAL_DECISION_SCHEMA,
    role="首席投资总监 (PM · 唯一拍板)",
    model="inherit",
)

# ------------------------------------------------------------------------------
# Render Archives & Privacy-Safe v3 Morning Note HTML
# ------------------------------------------------------------------------------


def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "- （未提供额外来源）"
    return "\n".join(
        f"- **{s['title']}**（{s['source']}，{s['date']}）：{s['key_fact']}" for s in sources
    )


ps = quant["personal_state"]
pnl_str = (
    f"{ps['unrealized_pnl_cny']:+.2f} RMB ({ps['unrealized_pnl_pct']:+.2f}%)"
    if ps["unrealized_pnl_cny"] is not None
    else "N/A"
)

md_intel = f"""# 01 黄金投研客观情报与 K 线档案（{RUN_ID}）

- **采集日期**：{TODAY_STR}
- **行情基准时间**：{intel['market']['as_of_date']}
- **国内参考克价**：**{cny_price if cny_price is not None else '待核实'} RMB/克**（{intel['market']['cny_gold_price_note']}）
- **国际现货金价**：{intel['market']['xau_usd_price']}
- **USD/CNY**：{intel['market']['usd_cny_rate']} ｜ **DXY**：{intel['market']['dxy_index']} ｜ **美债10Y**：{intel['market']['us10y_yield']}

## 一、K 线量化指标快照
```json
{json.dumps(kline_data, ensure_ascii=False, indent=2)}
```
- **近 30 日国内区间**：{intel['market']['kline_30d_range_cny']}
- **技术面客观摘要**：{intel['market']['kline_technical_summary']}

### 行情来源
{format_sources(intel['market']['sources'])}

---

## 二、宏观经济与黄金行业基本面
- **美联储与利率**：{intel['macro']['fed_and_rates_summary']}
- **美国核心数据**：{intel['macro']['us_macro_data_summary']}
- **央行购金与行业供需**：{intel['macro']['central_banks_and_industry_demand']}
- **财政与汇率政策**：{intel['macro']['fiscal_fx_policy_summary']}

### 关键事件日历
""" + "\n".join(f"- {e}" for e in intel["macro"]["upcoming_key_events"]) + f"""

### 宏观来源
{format_sources(intel['macro']['sources'])}

---

## 三、地缘政治、机构资金流与情绪
- **情绪标签**：`{intel['sentiment']['market_sentiment_label']}`
- **地缘局势**：{intel['sentiment']['geopolitics_summary']}
- **ETF 与机构资金流**：{intel['sentiment']['etf_and_institution_flows']}
- **主流投行观点**：{intel['sentiment']['institution_views_summary']}
- **拥挤度信号**：{intel['sentiment']['crowded_trade_signals']}

### 情绪来源
{format_sources(intel['sentiment']['sources'])}
"""

md_specialists = f"""# 02 五位专业顾问独立研判与量化打分（{RUN_ID}）

## 量化得分总览
- **今日综合入场性价比分**：**{quant['composite_score']} / 100**（{quant['score_zone_label']}）
- **因子明细**：`{json.dumps(quant['score_breakdown'], ensure_ascii=False)}`

---

## ① 宏观与行业专家（{specialists['macro']['score_0_to_100']} / 100）
- **一句话信号**：{specialists['macro']['sharpest_signal_plain']}
{specialists['macro']['analysis_markdown']}

---

## ② K 线与短线波段专家（{specialists['kline']['score_0_to_100']} / 100）
- **一句话信号**：{specialists['kline']['sharpest_signal_plain']}
- **实用买点**：{specialists['kline']['realistic_dip_buy_zone_cny']} ｜ **防守线**：{specialists['kline']['defense_break_line_cny']} ｜ **短线止盈**：{specialists['kline']['short_tp_zone_cny']}
{specialists['kline']['analysis_markdown']}

---

## ③ 长线价值定投派（{specialists['long_term']['score_0_to_100']} / 100）
- **一句话信号**：{specialists['long_term']['sharpest_signal_plain']}
- **长线止盈目标**：{specialists['long_term']['long_tp_zone_cny']}
{specialists['long_term']['analysis_markdown']}

---

## ④ 激进机会派（{specialists['aggressive']['score_0_to_100']} / 100）
- **一句话信号**：{specialists['aggressive']['sharpest_signal_plain']}
- **大胆建议**：{specialists['aggressive']['bold_proposal_plain']}
- **踏空代价评估**：{specialists['aggressive']['cost_of_waiting_plain']}
{specialists['aggressive']['analysis_markdown']}

---

## ⑤ 保守风控派（风险扣分 -{specialists['risk']['risk_deduction_0_to_20']} / 20）
- **一句话信号**：{specialists['risk']['sharpest_signal_plain']}
- **稳健建议**：{specialists['risk']['steady_proposal_plain']}
{specialists['risk']['analysis_markdown']}
"""

md_decision = f"""# 04 首席投资总监最终决策单（{RUN_ID}）

> **{pm_decision['headline']}**

## 一、通用市场与 3 颗子弹算法结论（对应邮件对外版，已脱敏）
- **今日参考国内金价**：{cny_price if cny_price is not None else '待核实'} RMB/克
- **今日综合入场性价比分**：**{quant['composite_score']} / 100**（{quant['score_zone_label']}）
- **通用算法拍板**：`{pm_decision['universal_action']}` — {pm_decision['recommended_amount_short']}
- **一句话看懂今天**：{pm_decision['plain_takeaway']}
- **🛡️ 稳健做法**：{pm_decision['steady_option_plain']}
- **🔥 大胆做法**：{pm_decision['bold_option_plain']}

{pm_decision['public_decision_markdown']}

---

## 二、仅限本地查看 · 个人账户与当月子弹备忘（绝不发进邮件）
- **当前持仓**：本金 {ps['principal_cny']} RMB / 均价 {ps['average_cost_cny_per_gram']} RMB/克 / 浮亏盈 {pnl_str}
- **本月子弹进度（{ps['month']}）**：已用 **{ps['shots_used']} / {quant['max_shots_per_month']} 颗**，剩余 **{ps['remaining_shots']} 颗**（下次为第 {ps['next_shot_number']} 颗，门槛 **{ps['active_threshold']} 分**；次月 1 日自动刷新为 0/3 颗）
- **个人精准拍板**：`{pm_decision['personal_action']}` — {ps['personal_reason']}

{pm_decision['personal_private_note_markdown']}
"""

xau_short = intel["market"]["xau_usd_price"].split("（")[0].split("(")[0].strip()[:28]
price_radar = [
    ("跌到这儿考虑买", pm_decision["radar_dip_buy"]["price_range"], pm_decision["radar_dip_buy"]["note"], "#16a34a"),
    ("跌破这儿先停买", pm_decision["radar_defense"]["price_range"], pm_decision["radar_defense"]["note"], "#dc2626"),
    ("短线涨到这儿卖", pm_decision["radar_short_tp"]["price_range"], pm_decision["radar_short_tp"]["note"], "#d97706"),
    ("长线涨到这儿卖", pm_decision["radar_long_tp"]["price_range"], pm_decision["radar_long_tp"]["note"], "#0284c7"),
]
spec_rows = [(s["role"], s["score_badge"], s["signal"]) for s in pm_decision["specialist_email_lines"]]
risk_bullets = [(r["tag"], r["desc"]) for r in pm_decision["risk_items"]]

email_subject = (
    f"【黄金晨报 {TODAY_STR}】买点分 {quant['composite_score']}/100 · "
    f"{pm_decision['recommended_amount_short']} | 国内 {cny_price or 'N/A'} 元/克"
)
email_html = render_v3_email_html(
    date_str=TODAY_STR,
    headline=pm_decision["headline"],
    plain_takeaway=pm_decision["plain_takeaway"],
    action=pm_decision["universal_action"],
    recommended_amount_short=pm_decision["recommended_amount_short"],
    composite_score=quant["composite_score"],
    score_zone_label=quant["score_zone_label"],
    cny_price=cny_price,
    xau_usd_short=xau_short,
    kline_thermometer_text=pm_decision["kline_thermometer_plain"],
    shot_amount_cny=quant["shot_amount_cny"],
    max_shots_per_month=quant["max_shots_per_month"],
    bullet_ladder=quant["bullet_ladder"],
    outlook_bullets=[
        ("为啥这么走", pm_decision["macro_one_liner"]),
        ("近几周怎么看", pm_decision["short_term_one_liner"]),
        ("放长半年看", pm_decision["long_term_one_liner"]),
    ],
    price_radar=price_radar,
    steady_option=pm_decision["steady_option_plain"],
    bold_option=pm_decision["bold_option_plain"],
    specialist_rows=spec_rows,
    risk_bullets=risk_bullets,
)

raw_payload = {
    "version": "v3_quant_5specialist_1pm",
    "run_id": RUN_ID,
    "date": TODAY_STR,
    "kline_data": kline_data,
    "intel": intel,
    "specialists": specialists,
    "quant": quant,
    "pm_decision": pm_decision,
}

ledger_row = (
    f"| {RUN_ID} (v3) | {cny_price if cny_price is not None else 'N/A'} | {pnl_str} | "
    f"`{pm_decision['personal_action']}` (市场分 {quant['composite_score']}/100) | "
    f"{pm_decision['recommended_amount_short']} | 5专家+PM | [查看档案](runs/{RUN_ID}/04_decision.md) |\n"
)


def write_archive(target_run_dir: Path, update_ledger_path: Path | None, dispatch_path: Path | None):
    target_run_dir.mkdir(parents=True, exist_ok=True)
    (target_run_dir / "01_intel.md").write_text(md_intel, encoding="utf-8")
    (target_run_dir / "02_specialists.md").write_text(md_specialists, encoding="utf-8")
    (target_run_dir / "04_decision.md").write_text(md_decision, encoding="utf-8")
    (target_run_dir / "email.html").write_text(email_html, encoding="utf-8")
    (target_run_dir / "raw_result.json").write_text(
        json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if update_ledger_path is not None:
        if not update_ledger_path.exists():
            update_ledger_path.write_text(
                "# 黄金投资决策历史总台账（Decision Ledger）\n\n"
                "| 日期时间 | 参考国内金价 (RMB/克) | 持仓浮动盈亏 | 最终决议动作 | 建议金额 / 比例 | 模式 | 会议档案链接 |\n"
                "| --- | --- | --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
        with open(update_ledger_path, "a", encoding="utf-8") as lf:
            lf.write(ledger_row)
    if dispatch_path is not None:
        dispatch_payload = {
            "date": TODAY_STR,
            "run_id": RUN_ID,
            "computed_at_cst": datetime.now(SHANGHAI_TZ).isoformat(),
            "mode": "local_v3_quant",
            "subject": email_subject,
            "recipient": "3518109978@qq.com",
            "html_path": str(target_run_dir / "email.html"),
            "text_path": str(target_run_dir / "04_decision.md"),
            "sent": False,
        }
        dispatch_path.write_text(json.dumps(dispatch_payload, ensure_ascii=False, indent=2), encoding="utf-8")


saved_mode = "primary"
saved_dir = BASE_DIR / "records" / "runs" / RUN_ID
try:
    write_archive(saved_dir, BASE_DIR / "records" / "ledger.md", BASE_DIR / "records" / "latest_dispatch.json")
    log(f"v3 档案与 HTML 邮件已写入: {saved_dir}")
except PermissionError:
    saved_mode = "fallback"
    saved_dir = FALLBACK_ROOT / RUN_ID
    write_archive(saved_dir, None, saved_dir / "latest_dispatch.json")
    log(f"主目录受沙箱限制，档案已写入暂存目录: {saved_dir}")

print(
    json.dumps(
        {
            "run_id": RUN_ID,
            "saved_mode": saved_mode,
            "saved_dir": str(saved_dir),
            "kline_available": kline_data["available"],
            "cny_gold_price_per_gram": cny_price,
            "composite_score": quant["composite_score"],
            "score_zone_label": quant["score_zone_label"],
            "score_breakdown": quant["score_breakdown"],
            "universal_action": pm_decision["universal_action"],
            "personal_action": pm_decision["personal_action"],
            "personal_shots_remaining": ps["remaining_shots"],
            "email_subject": email_subject,
            "email_html_path": str(saved_dir / "email.html"),
            "decision_md_path": str(saved_dir / "04_decision.md"),
        },
        ensure_ascii=False,
        indent=2,
    )
)
