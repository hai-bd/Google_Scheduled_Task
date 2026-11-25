#!/usr/bin/env python3
"""
Standalone Cloud Gold Investment Multi-Agent Workflow (Gemini 4 Interactions API)

Designed to run unattended on GitHub Actions every weekday at 06:00 Asia/Shanghai:
  - Phase 1 (Parallel, gemini-4-hydrogen + Google Search Grounding):
      Market/FX Collector, Macro/Policy Collector, Geopolitics/Sentiment Collector
  - Smart Two-Tier Gate (configurable in config/models.json):
      * Light Pre-Market Briefing on calm days (saves ~70-80% API cost)
      * Automatically escalates to Full 4-Member 2-Round Committee when:
          - Forced via --force-full or mode == "always_full"
          - Scheduled committee day (e.g., Monday, 1st/15th of month)
          - Price hits configured dip-buy / take-profit / defense watch levels
          - Sentinel detects >= trigger % overnight move or high-impact macro/geo event
  - Phase 2 (Parallel):
      Policy & Macro Analyst (gemini-4-neon)
      Short+Long Trend Analyst (gemini-4-neon)
      Personal Portfolio Analyst (gemini-4-hydrogen)
  - Phase 3 (2-Round Stateful Debate via previous_interaction_id):
      Trend & Swing Member (gemini-4-neon)
      Long-Term Allocation Member (gemini-4-argon)
      Contrarian Risk Officer / Red Team (gemini-4-carbon)
      Personal Portfolio CFO (gemini-4-argon)
  - Phase 4 (gemini-4-hydrogen):
      Committee Secretary synthesizes Markdown archives + mobile-friendly HTML email
      and writes records/latest_dispatch.json for the 08:00 CST email sender.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google import genai

# ------------------------------------------------------------------------------
# Paths & Constants
# ------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_PATH = REPO_ROOT / "config" / "portfolio.json"
MODELS_CONFIG_PATH = REPO_ROOT / "config" / "models.json"
RECORDS_DIR = REPO_ROOT / "records"
RUNS_DIR = RECORDS_DIR / "runs"
LEDGER_PATH = RECORDS_DIR / "ledger.md"
LATEST_DISPATCH_PATH = RECORDS_DIR / "latest_dispatch.json"

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

ACTION_LABELS = {
    "BUY_FULL": "全额买入（动用本月全部或绝大部分预算，可分笔执行）",
    "BUY_PARTIAL": "分批/部分买入（动用部分月度预算，保留弹药防回调）",
    "HOLD": "维持观望（暂不新增仓位也不减仓，等待触发价位）",
    "TAKE_PROFIT_PARTIAL": "部分止盈/减仓（落袋部分利润，保留长线底仓）",
    "REDUCE_HEAVY": "大幅减仓防守（显著降仓规避短期下行或利多出尽风险）",
}
ALLOWED_ACTIONS = list(ACTION_LABELS.keys())

# ------------------------------------------------------------------------------
# JSON Schemas (Structured Outputs via Interactions API response_format)
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

MARKET_INTEL_SCHEMA = {
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
        "recent_price_action_summary": {"type": "string"},
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
        "recent_price_action_summary",
        "sources",
    ],
}

MACRO_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "fed_policy_summary": {"type": "string"},
        "us_macro_data_summary": {"type": "string"},
        "pboc_and_central_banks_summary": {"type": "string"},
        "fiscal_and_tariff_policy_summary": {"type": "string"},
        "upcoming_key_events": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": SOURCE_ITEM_SCHEMA},
    },
    "required": [
        "fed_policy_summary",
        "us_macro_data_summary",
        "pboc_and_central_banks_summary",
        "fiscal_and_tariff_policy_summary",
        "upcoming_key_events",
        "sources",
    ],
}

GEO_INTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "geopolitics_summary": {"type": "string"},
        "etf_and_capital_flows_summary": {"type": "string"},
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
        "etf_and_capital_flows_summary",
        "market_sentiment_label",
        "institution_views_summary",
        "crowded_trade_signals",
        "sources",
    ],
}

SENTINEL_SCHEMA = {
    "type": "object",
    "properties": {
        "escalate_to_full_committee": {"type": "boolean"},
        "escalation_reasons": {"type": "array", "items": {"type": "string"}},
        "daily_headline": {"type": "string"},
        "suggested_stance": {"type": "string", "enum": ALLOWED_ACTIONS},
        "premarket_summary": {"type": "string"},
        "key_watchpoints_today": {"type": "array", "items": {"type": "string"}},
        "dip_buy_reminder": {"type": "string"},
        "take_profit_reminder": {"type": "string"},
        "top_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "escalate_to_full_committee",
        "escalation_reasons",
        "daily_headline",
        "suggested_stance",
        "premarket_summary",
        "key_watchpoints_today",
        "dip_buy_reminder",
        "take_profit_reminder",
        "top_risks",
    ],
}

POLICY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "macro_regime": {"type": "string"},
        "bullish_drivers": {"type": "array", "items": {"type": "string"}},
        "bearish_drivers": {"type": "array", "items": {"type": "string"}},
        "noise_vs_signal": {"type": "string"},
        "fundamental_bias": {
            "type": "string",
            "enum": ["bullish", "neutral_bullish", "neutral", "neutral_bearish", "bearish"],
        },
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "macro_regime",
        "bullish_drivers",
        "bearish_drivers",
        "noise_vs_signal",
        "fundamental_bias",
        "analysis_markdown",
    ],
}

TREND_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "short_term_view": {
            "type": "string",
            "enum": ["bullish", "range_bound", "overbought_pullback_risk", "bearish"],
        },
        "short_term_horizon_1_4w": {"type": "string"},
        "key_support_levels_cny_g": {"type": "array", "items": {"type": "string"}},
        "key_resistance_levels_cny_g": {"type": "array", "items": {"type": "string"}},
        "long_term_view": {
            "type": "string",
            "enum": ["bullish", "neutral_bullish", "neutral", "bearish"],
        },
        "long_term_horizon_3_12m": {"type": "string"},
        "scenario_summary": {"type": "string"},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "short_term_view",
        "short_term_horizon_1_4w",
        "key_support_levels_cny_g",
        "key_resistance_levels_cny_g",
        "long_term_view",
        "long_term_horizon_3_12m",
        "scenario_summary",
        "analysis_markdown",
    ],
}

PORTFOLIO_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "position_health_assessment": {"type": "string"},
        "buy_scenarios_summary": {"type": "string"},
        "take_profit_scenarios_summary": {"type": "string"},
        "risk_guardrails": {"type": "array", "items": {"type": "string"}},
        "analysis_markdown": {"type": "string"},
    },
    "required": [
        "position_health_assessment",
        "buy_scenarios_summary",
        "take_profit_scenarios_summary",
        "risk_guardrails",
        "analysis_markdown",
    ],
}

ROUND1_VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ALLOWED_ACTIONS},
        "recommended_amount_desc": {"type": "string"},
        "confidence_1_to_10": {"type": "integer", "minimum": 1, "maximum": 10},
        "short_term_stance": {"type": "string"},
        "long_term_stance": {"type": "string"},
        "core_rationale": {"type": "string"},
        "risk_veto": {"type": "boolean"},
        "risk_veto_reason": {"type": "string"},
        "question_for_committee": {"type": "string"},
    },
    "required": [
        "action",
        "recommended_amount_desc",
        "confidence_1_to_10",
        "short_term_stance",
        "long_term_stance",
        "core_rationale",
        "risk_veto",
        "risk_veto_reason",
        "question_for_committee",
    ],
}

ROUND2_VOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "changed_mind": {"type": "boolean"},
        "action": {"type": "string", "enum": ALLOWED_ACTIONS},
        "recommended_amount_desc": {"type": "string"},
        "confidence_1_to_10": {"type": "integer", "minimum": 1, "maximum": 10},
        "response_to_peers": {"type": "string"},
        "risk_veto": {"type": "boolean"},
        "risk_veto_reason": {"type": "string"},
        "trigger_conditions": {"type": "string"},
        "final_statement": {"type": "string"},
    },
    "required": [
        "changed_mind",
        "action",
        "recommended_amount_desc",
        "confidence_1_to_10",
        "response_to_peers",
        "risk_veto",
        "risk_veto_reason",
        "trigger_conditions",
        "final_statement",
    ],
}

DECISION_SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "recommended_amount_summary": {"type": "string"},
        "short_term_plan": {"type": "string"},
        "long_term_plan": {"type": "string"},
        "dip_buy_triggers": {"type": "string"},
        "take_profit_triggers": {"type": "string"},
        "top_risks": {"type": "array", "items": {"type": "string"}},
        "decision_markdown": {"type": "string"},
    },
    "required": [
        "headline",
        "recommended_amount_summary",
        "short_term_plan",
        "long_term_plan",
        "dip_buy_triggers",
        "take_profit_triggers",
        "top_risks",
        "decision_markdown",
    ],
}

# ------------------------------------------------------------------------------
# Gemini 4 Interactions API Helper
# ------------------------------------------------------------------------------


def call_gemini_json(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    schema: dict[str, Any],
    thinking_level: str = "high",
    system_instruction: str | None = None,
    use_search: bool = False,
    previous_interaction_id: str | None = None,
    max_retries: int = 3,
) -> tuple[dict[str, Any], str]:
    """Call Gemini 4 Interactions API with structured JSON output and retries."""
    kwargs: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "generation_config": {
            "thinking_level": thinking_level,
        },
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
    }
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if use_search:
        kwargs["tools"] = [{"type": "google_search"}]
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            interaction = client.interactions.create(**kwargs)
            text = (interaction.output_text or "").strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
            parsed = json.loads(text)
            return parsed, interaction.id
        except Exception as exc:
            last_err = exc
            wait_sec = 2 * attempt
            print(
                f"[WARN] model={model} attempt {attempt}/{max_retries} failed: {exc}. "
                f"Retrying in {wait_sec}s...",
                file=sys.stderr,
            )
            time.sleep(wait_sec)
    raise RuntimeError(f"Gemini call failed after {max_retries} attempts (model={model}): {last_err}")


# ------------------------------------------------------------------------------
# Quantitative Portfolio Math & Vote Resolution
# ------------------------------------------------------------------------------


def compute_portfolio_metrics(
    portfolio: dict[str, Any], current_price_cny: float | None, today_str: str = ""
) -> dict[str, Any]:
    pos = portfolio["position"]
    principal = float(pos["principal_cny"])
    avg_cost = float(pos["average_cost_cny_per_gram"])
    grams = principal / avg_cost
    budget = float(portfolio["monthly_disposable_budget_cny"])
    min_buy = float(portfolio.get("constraints", {}).get("min_single_buy_cny", 1200))

    tracker = portfolio.get("monthly_budget_tracker", {})
    current_ym = today_str[:7] if len(today_str) >= 7 else ""
    if current_ym and tracker.get("month") == current_ym:
        spent_month = float(tracker.get("spent_cny", 0))
        remaining_month = max(0.0, float(tracker.get("remaining_cny", budget - spent_month)))
    else:
        spent_month = 0.0
        remaining_month = budget

    metrics: dict[str, Any] = {
        "principal_cny": round(principal, 2),
        "average_cost_cny_per_gram": round(avg_cost, 2),
        "estimated_grams": round(grams, 4),
        "monthly_budget_cny": round(budget, 2),
        "spent_this_month_cny": round(spent_month, 2),
        "remaining_budget_this_month_cny": round(remaining_month, 2),
        "min_single_buy_cny": round(min_buy, 2),
        "current_price_cny_per_gram": current_price_cny,
    }

    if current_price_cny and current_price_cny > 0:
        market_value = grams * current_price_cny
        pnl_cny = market_value - principal
        pnl_pct = (pnl_cny / principal) * 100.0
        metrics.update(
            {
                "current_market_value_cny": round(market_value, 2),
                "unrealized_pnl_cny": round(pnl_cny, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "add_scenarios": {},
                "trim_scenarios": {},
            }
        )
        candidate_adds = sorted(
            {
                int(min_buy),
                int(remaining_month) if remaining_month >= min_buy else int(min_buy),
                int(budget),
            }
        )
        for add_amt in candidate_adds:
            if add_amt < min_buy:
                continue
            added_g = add_amt / current_price_cny
            new_principal = principal + add_amt
            new_grams = grams + added_g
            new_avg = new_principal / new_grams
            metrics["add_scenarios"][f"add_{add_amt}_cny"] = {
                "added_grams": round(added_g, 4),
                "new_total_principal_cny": round(new_principal, 2),
                "new_total_grams": round(new_grams, 4),
                "new_avg_cost_cny_per_gram": round(new_avg, 2),
                "avg_cost_change_cny": round(new_avg - avg_cost, 2),
            }
        for trim_pct in (20, 30, 50):
            ratio = trim_pct / 100.0
            sold_g = grams * ratio
            proceeds = sold_g * current_price_cny
            cost_part = principal * ratio
            realized_pnl = proceeds - cost_part
            metrics["trim_scenarios"][f"trim_{trim_pct}_pct"] = {
                "sold_grams": round(sold_g, 4),
                "cash_proceeds_cny": round(proceeds, 2),
                "realized_pnl_cny": round(realized_pnl, 2),
                "remaining_grams": round(grams - sold_g, 4),
                "remaining_principal_cny": round(principal - cost_part, 2),
            }
    return metrics


def resolve_committee_vote(round2_records: list[dict[str, Any]]) -> dict[str, Any]:
    actions = [r["vote"]["action"] for r in round2_records]
    counts = Counter(actions)
    most_common = counts.most_common()
    top_action, top_count = most_common[0]
    risk_veto_triggered = any(
        r["id"] == "risk_redteam" and r["vote"]["risk_veto"] for r in round2_records
    )
    any_veto_reasons = [
        f"{r['name']}: {r['vote']['risk_veto_reason']}"
        for r in round2_records
        if r["vote"]["risk_veto"]
    ]

    buy_side = {"BUY_FULL", "BUY_PARTIAL"}
    sell_side = {"TAKE_PROFIT_PARTIAL", "REDUCE_HEAVY"}
    is_tie = len(most_common) >= 2 and most_common[0][1] == most_common[1][1]
    has_buy = any(a in buy_side for a in actions)
    has_sell = any(a in sell_side for a in actions)

    if top_count >= 3:
        final_action = top_action
        resolution_rule = f"明显多数通过（{top_count}/4 票）"
    elif is_tie:
        tied_actions = {a for a, c in most_common if c == top_count}
        if (tied_actions & buy_side) and (tied_actions & sell_side):
            final_action = "HOLD"
            resolution_rule = "多空平票分歧，触发保守折中降级为观望并设双边触发价"
        elif tied_actions == {"BUY_FULL", "BUY_PARTIAL"}:
            final_action = "BUY_PARTIAL"
            resolution_rule = "全买与分批买平票，采用保守分批买入"
        elif tied_actions == {"BUY_PARTIAL", "HOLD"}:
            final_action = "HOLD" if risk_veto_triggered else "BUY_PARTIAL"
            resolution_rule = (
                "分批买与观望平票且触发风控预警，降级为观望"
                if risk_veto_triggered
                else "分批买与观望平票且无风控预警，采用小额分批定投"
            )
        elif tied_actions == {"HOLD", "TAKE_PROFIT_PARTIAL"}:
            final_action = "TAKE_PROFIT_PARTIAL" if risk_veto_triggered else "HOLD"
            resolution_rule = (
                "观望与部分止盈平票且触发风控预警，执行小比例部分止盈"
                if risk_veto_triggered
                else "观望与部分止盈平票，先观望并设定明确止盈触发线"
            )
        elif tied_actions == {"TAKE_PROFIT_PARTIAL", "REDUCE_HEAVY"}:
            final_action = "TAKE_PROFIT_PARTIAL"
            resolution_rule = "轻重减仓平票，先执行部分止盈/减仓"
        else:
            final_action = "HOLD"
            resolution_rule = "投票高度分散，默认采用观望并按触发条件执行"
    else:
        if has_buy and has_sell and top_action in {"BUY_FULL", "REDUCE_HEAVY"}:
            final_action = "BUY_PARTIAL" if top_action == "BUY_FULL" else "TAKE_PROFIT_PARTIAL"
            resolution_rule = "2-1-1 相对多数但存在反向异议，幅度降档执行"
        else:
            final_action = top_action
            resolution_rule = f"相对多数通过（{top_count}/4 票）"

    if risk_veto_triggered and final_action == "BUY_FULL":
        final_action = "BUY_PARTIAL"
        resolution_rule += "；但逆向风控红队触发风险预警，强制将全额买入降级为分批买入"

    avg_conf = round(
        sum(r["vote"]["confidence_1_to_10"] for r in round2_records) / len(round2_records), 1
    )
    return {
        "final_action": final_action,
        "final_action_label": ACTION_LABELS[final_action],
        "vote_counts": dict(counts),
        "avg_confidence": avg_conf,
        "risk_veto_triggered": risk_veto_triggered,
        "veto_reasons": any_veto_reasons,
        "resolution_rule": resolution_rule,
    }


def check_deterministic_escalation(
    now_cst: datetime,
    policy: dict[str, Any],
    cny_price: float | None,
    overnight_change_pct: float | None,
) -> list[str]:
    reasons: list[str] = []
    if now_cst.isoweekday() in policy.get("full_committee_weekdays", []):
        reasons.append(f"例行投委会周期日（周{now_cst.isoweekday()}）")
    if now_cst.day in policy.get("full_committee_monthdays", []):
        reasons.append(f"月度固定评估日（每月 {now_cst.day} 日）")

    move_limit = float(policy.get("price_move_trigger_pct", 1.5))
    if overnight_change_pct is not None and abs(overnight_change_pct) >= move_limit:
        reasons.append(f"隔夜金价波动达 {overnight_change_pct:+.2f}%（≥ ±{move_limit}% 阈值）")

    levels = policy.get("watch_price_levels_cny_g", {})
    if cny_price is not None:
        if levels.get("deep_dip") and cny_price <= float(levels["deep_dip"]):
            reasons.append(f"国内金价 {cny_price} 元/克 触及深跌防守观察位 ≤ {levels['deep_dip']}")
        elif levels.get("dip_buy_low") and cny_price <= float(levels["dip_buy_low"]):
            reasons.append(f"国内金价 {cny_price} 元/克 触及逢低加仓观察位 ≤ {levels['dip_buy_low']}")
        if levels.get("long_take_profit") and cny_price >= float(levels["long_take_profit"]):
            reasons.append(f"国内金价 {cny_price} 元/克 触及长线止盈观察位 ≥ {levels['long_take_profit']}")
        elif levels.get("short_take_profit") and cny_price >= float(levels["short_take_profit"]):
            reasons.append(f"国内金价 {cny_price} 元/克 触及短线止盈观察位 ≥ {levels['short_take_profit']}")
    return reasons


# ------------------------------------------------------------------------------
# HTML Email & Markdown Formatters
# ------------------------------------------------------------------------------


def format_sources(sources: list[dict[str, str]]) -> str:
    if not sources:
        return "- （未提供额外来源）"
    return "\n".join(
        f"- **{s['title']}**（{s['source']}，{s['date']}）：{s['key_fact']}" for s in sources
    )


def action_badge_color(action: str) -> str:
    return {
        "BUY_FULL": "#0f766e",
        "BUY_PARTIAL": "#0284c7",
        "HOLD": "#475569",
        "TAKE_PROFIT_PARTIAL": "#d97706",
        "REDUCE_HEAVY": "#dc2626",
    }.get(action, "#334155")


def render_email_html(
    *,
    date_str: str,
    run_mode: str,
    headline: str,
    action: str,
    action_desc: str,
    cny_price: float | None,
    xau_usd: str,
    portfolio_metrics: dict[str, Any],
    summary_rows: list[tuple[str, str]],
    risks: list[str],
    committee_table_rows: list[tuple[str, str, str, str]] | None = None,
    model_usage_note: str = "",
) -> str:
    esc = html.escape
    badge_bg = action_badge_color(action)
    pnl_cny = portfolio_metrics.get("unrealized_pnl_cny")
    pnl_pct = portfolio_metrics.get("unrealized_pnl_pct")
    pnl_text = f"{pnl_cny:+.2f} RMB ({pnl_pct:+.2f}%)" if pnl_cny is not None else "待核实"
    pnl_color = "#15803d" if (pnl_cny or 0) >= 0 else "#dc2626"
    mode_tag = "完整多 Agent 投委会决议" if run_mode == "full" else "盘前轻量哨兵盯盘简报"

    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#475569;font-weight:600;width:28%;vertical-align:top;">{esc(k)}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;line-height:1.6;">{esc(v)}</td>
        </tr>
        """
        for k, v in summary_rows
    )

    risks_html = "".join(
        f'<li style="margin-bottom:6px;line-height:1.6;color:#334155;">{esc(r)}</li>' for r in risks
    )

    committee_html = ""
    if committee_table_rows:
        c_rows = "".join(
            f"""
            <tr>
              <td style="padding:8px 10px;border-bottom:1px solid #e2e8f0;font-weight:600;color:#1e293b;">{esc(name)}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e2e8f0;"><span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{action_badge_color(vote)};color:#fff;font-size:12px;">{esc(vote)}</span></td>
              <td style="padding:8px 10px;border-bottom:1px solid #e2e8f0;color:#334155;">{esc(conf)}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e2e8f0;color:#334155;line-height:1.5;">{esc(note)}</td>
            </tr>
            """
            for name, vote, conf, note in committee_table_rows
        )
        committee_html = f"""
        <h3 style="margin:22px 0 10px;font-size:16px;color:#0f172a;border-left:4px solid #ca8a04;padding-left:10px;">四委员终投表决一览</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;">
          <thead>
            <tr style="background:#f8fafc;text-align:left;color:#475569;">
              <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">委员</th>
              <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">终投</th>
              <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">信心</th>
              <th style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">核心建议</th>
            </tr>
          </thead>
          <tbody>{c_rows}</tbody>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:16px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:720px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(15,23,42,0.08);">
    <div style="background:linear-gradient(135deg,#1e293b,#334155);padding:20px 24px;color:#f8fafc;">
      <div style="font-size:12px;letter-spacing:1px;color:#fbbf24;font-weight:700;">GOLD INVESTMENT COMMITTEE · {esc(date_str)} 盘前晨报</div>
      <h2 style="margin:8px 0 10px;font-size:20px;line-height:1.4;color:#ffffff;">{esc(headline)}</h2>
      <div>
        <span style="display:inline-block;padding:4px 12px;border-radius:999px;background:{badge_bg};color:#ffffff;font-size:13px;font-weight:700;">决议：{esc(action)}</span>
        <span style="display:inline-block;margin-left:8px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,0.14);color:#e2e8f0;font-size:12px;">{esc(mode_tag)}</span>
      </div>
    </div>

    <div style="padding:20px 24px;">
      <div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;">
        <div style="flex:1;min-width:140px;">
          <div style="font-size:12px;color:#64748b;">参考国内金价</div>
          <div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:2px;">{cny_price if cny_price is not None else '待核实'} <span style="font-size:12px;font-weight:400;">RMB/克</span></div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">国际：{esc(xau_usd[:40])}</div>
        </div>
        <div style="flex:1;min-width:160px;">
          <div style="font-size:12px;color:#64748b;">参考月度定投预算模型</div>
          <div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:2px;">{int(portfolio_metrics['monthly_budget_cny'])} <span style="font-size:12px;font-weight:400;">RMB/月</span></div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">单笔起投门槛：{int(portfolio_metrics['min_single_buy_cny'])} RMB</div>
        </div>
      </div>

      <p style="margin:0 0 14px;font-size:14px;color:#334155;line-height:1.6;"><strong>动作说明：</strong>{esc(action_desc)}</p>

      <h3 style="margin:18px 0 10px;font-size:16px;color:#0f172a;border-left:4px solid #ca8a04;padding-left:10px;">核心执行清单</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;border:1px solid #e2e8f0;border-radius:8px;">
        <tbody>{rows_html}</tbody>
      </table>

      {committee_html}

      <h3 style="margin:22px 0 10px;font-size:16px;color:#0f172a;border-left:4px solid #dc2626;padding-left:10px;">核心风险提示</h3>
      <ul style="margin:0;padding-left:20px;font-size:14px;">{risks_html}</ul>

      <div style="margin-top:24px;padding-top:14px;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;line-height:1.6;">
        <div>{esc(model_usage_note)}</div>
        <div>免责声明：本邮件由个人多 Agent 投研 Workflow 自动生成，仅作信息整理与交易纪律辅助参考，不构成持牌金融投资建议。实盘操作请以交易平台实时报价与个人风险承受能力为准。</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ------------------------------------------------------------------------------
# Main Workflow Pipeline
# ------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud Gold Investment Multi-Agent Daily Compute")
    parser.add_argument("--force-full", action="store_true", help="Force full 4-member committee run")
    parser.add_argument("--date", type=str, default=None, help="Override YYYY-MM-DD (Asia/Shanghai)")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("ERROR: GEMINI_API_KEY environment variable is not set.")

    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        portfolio = json.load(f)
    with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
        models_cfg = json.load(f)

    now_cst = datetime.now(SHANGHAI_TZ)
    today_str = args.date or now_cst.strftime("%Y-%m-%d")
    run_id = today_str
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    models = models_cfg["models"]
    thinking_level = models_cfg.get("default_thinking_level", "high")
    exec_policy = models_cfg["execution_policy"]
    client = genai.Client()

    print(
        f"[INFO] Starting Gold Daily Compute | date={today_str} | "
        f"time_cst={now_cst.strftime('%H:%M:%S')} | thinking_level={thinking_level}"
    )

    # ==========================================================================
    # PHASE 1: PARALLEL INFORMATION COLLECTION (Google Search Grounding)
    # ==========================================================================
    collector_jobs = [
        (
            "market",
            models["collectors"]["market"],
            MARKET_INTEL_SCHEMA,
            f"""你是【实时行情与汇率采集员】。今天是 {today_str}（北京时间清晨盘前）。
请通过 Google Search 搜索最新隔夜收盘及今晨的黄金与关联市场客观数据：
1. 国际现货黄金（XAU/USD）最新价格与隔夜涨跌幅（overnight_change_pct，纯数字如 -1.85 或 0.72）；
2. 中国国内人民币黄金参考克价（上海黄金交易所 AU9999 / 沪金夜盘收盘价 / 银行积存金克价），填入 cny_gold_price_per_gram（纯数字人民币/克；若仅有国际价可按汇率折算并在 cny_gold_price_note 注明）；
3. USD/CNY 汇率、美元指数 DXY、美国 10 年期国债收益率；
4. 近 1-2 周价格走势特征。
只汇报客观事实并附来源与日期，不得编造数据或给出买卖建议。""",
        ),
        (
            "macro",
            models["collectors"]["macro"],
            MACRO_INTEL_SCHEMA,
            f"""你是【宏观与央行政策采集员】。今天是 {today_str}（北京时间清晨盘前）。
请通过 Google Search 搜索隔夜及近期影响黄金定价的宏观经济与央行政策动态：
1. 美联储（Fed）最新利率预期、官员表态或议息动态；
2. 隔夜及近期美国核心宏观数据（CPI/PCE/非农/GDP）；
3. 中国央行（PBOC）及全球央行最新购金动态；
4. 财政赤字、关税贸易或汇率政策新闻；
5. 未来 1-2 周重要宏观事件日历。
只汇报客观事实并标注来源与日期。""",
        ),
        (
            "geo",
            models["collectors"]["geo"],
            GEO_INTEL_SCHEMA,
            f"""你是【地缘政治与市场情绪采集员】。今天是 {today_str}（北京时间清晨盘前）。
请通过 Google Search 搜索隔夜及近期影响黄金避险情绪与资金流向的新闻：
1. 重大地缘政治动态与避险催化；
2. 全球黄金 ETF（SPDR GLD）与国内黄金 ETF 资金流入/流出；
3. 主流投行/世界黄金协会最新观点；
4. 市场拥挤度与多空情绪特征。
保持客观中立，标注来源与日期。""",
        ),
    ]

    intel: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            key: pool.submit(
                call_gemini_json,
                client,
                model=model_name,
                prompt=prompt,
                schema=schema,
                thinking_level=thinking_level,
                use_search=True,
            )
            for key, model_name, schema, prompt in collector_jobs
        }
        for key, fut in futures.items():
            intel[key], _ = fut.result()

    cny_price = intel["market"].get("cny_gold_price_per_gram")
    overnight_chg = intel["market"].get("overnight_change_pct")
    portfolio_metrics = compute_portfolio_metrics(portfolio, cny_price, today_str)
    print(
        f"[INFO] Phase 1 done | XAU/USD={intel['market']['xau_usd_price']} | "
        f"CNY={cny_price} RMB/g | overnight={overnight_chg}% | sentiment={intel['geo']['market_sentiment_label']}"
    )

    # Write 01_intel.md immediately
    md_intel = f"""# 01 黄金投研客观情报档案（{run_id}）

- **采集日期**：{today_str}（北京时间 06:00 盘前）
- **行情基准时间**：{intel['market']['as_of_date']}

## 一、实时行情与关联指标

| 指标 | 最新读数 / 说明 |
| --- | --- |
| 国际现货黄金 (XAU/USD) | {intel['market']['xau_usd_price']}（隔夜变动：{overnight_chg if overnight_chg is not None else 'N/A'}%） |
| 国内参考人民币克价 | **{cny_price if cny_price is not None else '待核实'} RMB/克**（{intel['market']['cny_gold_price_note']}） |
| 美元兑人民币 (USD/CNY) | {intel['market']['usd_cny_rate']} |
| 美元指数 (DXY) | {intel['market']['dxy_index']} |
| 美债 10 年期收益率 | {intel['market']['us10y_yield']} |

**近期走势特征**：{intel['market']['recent_price_action_summary']}

### 行情信息来源
{format_sources(intel['market']['sources'])}

---

## 二、宏观经济与央行政策动态
- **美联储政策与预期**：{intel['macro']['fed_policy_summary']}
- **美国核心宏观数据**：{intel['macro']['us_macro_data_summary']}
- **中国央行及全球央行购金**：{intel['macro']['pboc_and_central_banks_summary']}
- **财政与关税政策**：{intel['macro']['fiscal_and_tariff_policy_summary']}

### 未来关键事件日历
""" + "\n".join(f"- {e}" for e in intel["macro"]["upcoming_key_events"]) + f"""

### 宏观政策来源
{format_sources(intel['macro']['sources'])}

---

## 三、地缘政治、资金流与市场情绪
- **市场情绪标签**：`{intel['geo']['market_sentiment_label']}`
- **地缘政治与避险催化**：{intel['geo']['geopolitics_summary']}
- **ETF 与资金流向**：{intel['geo']['etf_and_capital_flows_summary']}
- **主流机构观点**：{intel['geo']['institution_views_summary']}
- **交易拥挤度信号**：{intel['geo']['crowded_trade_signals']}

### 地缘与情绪来源
{format_sources(intel['geo']['sources'])}
"""
    (run_dir / "01_intel.md").write_text(md_intel, encoding="utf-8")

    # ==========================================================================
    # SMART TWO-TIER ESCALATION CHECK
    # ==========================================================================
    force_full = args.force_full or exec_policy.get("mode") == "always_full"
    det_reasons = check_deterministic_escalation(now_cst, exec_policy, cny_price, overnight_chg)

    intel_json = json.dumps(intel, ensure_ascii=False, indent=2)
    portfolio_metrics_json = json.dumps(portfolio_metrics, ensure_ascii=False, indent=2)
    portfolio_json = json.dumps(portfolio, ensure_ascii=False, indent=2)

    sentinel_result: dict[str, Any] | None = None
    run_full = force_full or bool(det_reasons)

    if not run_full:
        sentinel_prompt = f"""你是【黄金盘前哨兵 Agent】。今天是 {today_str}。
请基于最新情报与用户持仓数据，评估今天是否存在**重大突发宏观/地缘事件、关键支撑阻力位突破或显著异动**，决定是否需要紧急升级召开完整的 4 委员两轮投委会（escalate_to_full_committee）。
无论是否升级，都请同时输出一份精炼、可直接作为晨报发送的盘前盯盘摘要。

【账户与定量持仓】
{portfolio_metrics_json}

【预设观察价位】
{json.dumps(exec_policy.get("watch_price_levels_cny_g", {}), ensure_ascii=False)}

【Phase 1 客观情报】
{intel_json}
"""
        sentinel_result, _ = call_gemini_json(
            client,
            model=models["sentinel"],
            prompt=sentinel_prompt,
            schema=SENTINEL_SCHEMA,
            thinking_level=thinking_level,
        )
        if sentinel_result["escalate_to_full_committee"]:
            run_full = True
            det_reasons.extend(sentinel_result["escalation_reasons"])

    print(f"[INFO] Execution mode decision: {'FULL_COMMITTEE' if run_full else 'LIGHT_BRIEFING'} | reasons={det_reasons}")

    pnl_str = (
        f"{portfolio_metrics['unrealized_pnl_cny']:+.0f} RMB ({portfolio_metrics['unrealized_pnl_pct']:+.2f}%)"
        if "unrealized_pnl_cny" in portfolio_metrics
        else "N/A"
    )

    # ==========================================================================
    # BRANCH A: LIGHT DAILY BRIEFING (Calm Day)
    # ==========================================================================
    if not run_full and sentinel_result is not None:
        action = sentinel_result["suggested_stance"]
        subject = f"【黄金盘前简报 {today_str}】{action} | 国内参考 {cny_price or 'N/A'} 元/克"
        md_decision = f"""# 04 盘前轻量盯盘简报（{run_id}）

> **{sentinel_result['daily_headline']}**

- **运行模式**：盘前轻量哨兵模式（今日无重大触发阈值，未召开完整 4 委员会议以节省成本）
- **参考国内金价**：{cny_price if cny_price is not None else '待核实'} RMB/克
- **当前持仓状态**：本金 {portfolio_metrics['principal_cny']} RMB / 均价 {portfolio_metrics['average_cost_cny_per_gram']} RMB/克 / 浮亏盈 {pnl_str}
- **盘前建议姿态**：`{action}`（{ACTION_LABELS[action]}）

## 盘前摘要
{sentinel_result['premarket_summary']}

## 今日核心关注点
""" + "\n".join(f"- {x}" for x in sentinel_result["key_watchpoints_today"]) + f"""

## 关键价位提醒
- **逢低加仓观察**：{sentinel_result['dip_buy_reminder']}
- **逢高止盈观察**：{sentinel_result['take_profit_reminder']}

## 风险提示
""" + "\n".join(f"- {x}" for x in sentinel_result["top_risks"]) + "\n"

        (run_dir / "04_decision.md").write_text(md_decision, encoding="utf-8")
        email_html = render_email_html(
            date_str=today_str,
            run_mode="light",
            headline=sentinel_result["daily_headline"],
            action=action,
            action_desc=ACTION_LABELS[action],
            cny_price=cny_price,
            xau_usd=intel["market"]["xau_usd_price"],
            portfolio_metrics=portfolio_metrics,
            summary_rows=[
                ("盘前核心摘要", sentinel_result["premarket_summary"]),
                ("今日重点关注", "；".join(sentinel_result["key_watchpoints_today"])),
                ("逢低加仓观察", sentinel_result["dip_buy_reminder"]),
                ("逢高止盈观察", sentinel_result["take_profit_reminder"]),
            ],
            risks=sentinel_result["top_risks"],
            model_usage_note=f"模型分配：采集/哨兵均使用 {models['sentinel']}（thinking={thinking_level}，日常节能模式）",
        )
        (run_dir / "email.html").write_text(email_html, encoding="utf-8")
        (run_dir / "raw_result.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "mode": "light",
                    "portfolio_metrics": portfolio_metrics,
                    "intel": intel,
                    "sentinel": sentinel_result,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        ledger_row = (
            f"| {run_id} (轻量) | {cny_price if cny_price is not None else 'N/A'} | {pnl_str} | "
            f"`{action}` | 轻量盯盘无异动 | Sentinel | [查看档案](runs/{run_id}/04_decision.md) |\n"
        )
    else:
        # ======================================================================
        # BRANCH B: FULL MULTI-AGENT INVESTMENT COMMITTEE
        # ======================================================================
        # PHASE 2: PARALLEL SPECIALIST ANALYSIS
        analyst_jobs = [
            (
                "policy",
                models["analysts"]["policy"],
                POLICY_ANALYSIS_SCHEMA,
                f"""你是【政策与宏观基本面分析师】。今天是 {today_str}。
基于以下 Phase 1 客观情报包，拆解当前黄金宏观定价范式、核心利多与利空、区分短期噪音与中期主线，给出基本面偏向和中文分析正文。
【Phase 1 情报包】
{intel_json}""",
            ),
            (
                "trend",
                models["analysts"]["trend"],
                TREND_ANALYSIS_SCHEMA,
                f"""你是【短线波段与长线趋势分析师】。今天是 {today_str}。
用户同时接受短线波段与长线配置，且允许止盈减仓。
基于以下客观情报，同时从短线（1-4周）和长线（3-12月）分析金价走向，给出国内人民币金价关键支撑位与阻力/止盈位、多情景概率及中文正文。
【Phase 1 情报包】
{intel_json}""",
            ),
            (
                "portfolio",
                models["analysts"]["portfolio"],
                PORTFOLIO_ANALYSIS_SCHEMA,
                f"""你是【个人持仓与仓位管理分析师】。今天是 {today_str}。
基于用户真实账户配置、已算好的定量指标和最新行情，评估持仓健康度、对比可执行加仓方案（严格遵守单笔最低买入金额 min_single_buy_cny 与本月剩余预算 remaining_budget_this_month_cny）与减仓 20%/30%/50% 方案，提出风控护栏及中文正文。
【账户配置】
{portfolio_json}
【定量测算】
{portfolio_metrics_json}
【实时行情】
{json.dumps(intel["market"], ensure_ascii=False, indent=2)}""",
            ),
        ]

        analysis: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                key: pool.submit(
                    call_gemini_json,
                    client,
                    model=model_name,
                    prompt=prompt,
                    schema=schema,
                    thinking_level=thinking_level,
                )
                for key, model_name, schema, prompt in analyst_jobs
            }
            for key, fut in futures.items():
                analysis[key], _ = fut.result()

        print(
            f"[INFO] Phase 2 done | fundamental={analysis['policy']['fundamental_bias']} | "
            f"short={analysis['trend']['short_term_view']} | long={analysis['trend']['long_term_view']}"
        )

        md_analysis = f"""# 02 多维专业分析报告（{run_id}）

## 一、政策与宏观基本面分析（模型：`{models['analysts']['policy']}`）
- **宏观定价范式**：{analysis['policy']['macro_regime']}
- **基本面综合偏向**：`{analysis['policy']['fundamental_bias']}`
- **噪音 vs 主线**：{analysis['policy']['noise_vs_signal']}

**核心利多驱动**：
""" + "\n".join(f"- {x}" for x in analysis["policy"]["bullish_drivers"]) + """

**核心利空与压制**：
""" + "\n".join(f"- {x}" for x in analysis["policy"]["bearish_drivers"]) + f"""

{analysis['policy']['analysis_markdown']}

---

## 二、短线波段与长线趋势走向分析（模型：`{models['analysts']['trend']}`）
- **短线视角（1–4 周）**：`{analysis['trend']['short_term_view']}` — {analysis['trend']['short_term_horizon_1_4w']}
- **长线视角（3–12 个月）**：`{analysis['trend']['long_term_view']}` — {analysis['trend']['long_term_horizon_3_12m']}
- **国内金价关键支撑位**：{', '.join(analysis['trend']['key_support_levels_cny_g'])}
- **国内金价关键阻力/止盈位**：{', '.join(analysis['trend']['key_resistance_levels_cny_g'])}
- **情景概览**：{analysis['trend']['scenario_summary']}

{analysis['trend']['analysis_markdown']}

---

## 三、个人持仓与仓位管理分析（模型：`{models['analysts']['portfolio']}`）
- **持仓健康度评估**：{analysis['portfolio']['position_health_assessment']}
- **加仓方案对比**：{analysis['portfolio']['buy_scenarios_summary']}
- **止盈/减仓方案对比**：{analysis['portfolio']['take_profit_scenarios_summary']}

**风控护栏建议**：
""" + "\n".join(f"- {x}" for x in analysis["portfolio"]["risk_guardrails"]) + f"""

{analysis['portfolio']['analysis_markdown']}
"""
        (run_dir / "02_analysis.md").write_text(md_analysis, encoding="utf-8")

        # PHASE 3: 2-ROUND HETEROGENEOUS COMMITTEE VOTING (Stateful via previous_interaction_id)
        briefing_pack = json.dumps(
            {
                "date": today_str,
                "escalation_reasons": det_reasons,
                "portfolio": portfolio,
                "portfolio_metrics": portfolio_metrics,
                "market_intel": intel["market"],
                "policy_analysis": {k: v for k, v in analysis["policy"].items() if k != "analysis_markdown"},
                "trend_analysis": {k: v for k, v in analysis["trend"].items() if k != "analysis_markdown"},
                "portfolio_analysis": {k: v for k, v in analysis["portfolio"].items() if k != "analysis_markdown"},
                "upcoming_key_events": intel["macro"]["upcoming_key_events"],
                "market_sentiment": intel["geo"]["market_sentiment_label"],
                "crowded_trade_signals": intel["geo"]["crowded_trade_signals"],
            },
            ensure_ascii=False,
            indent=2,
        )

        committee_defs = [
            {
                "id": "trend_swing",
                "name": "委员A · 趋势波段委员",
                "model": models["committee"]["trend_swing"],
                "system": (
                    "你是黄金投委会【委员A · 趋势波段委员】。核心投资哲学：重视动量、波段赔率、"
                    "事件催化与右侧顺势；强支撑或突破初期敢于出击，超买/阻力位敢于主张短线部分止盈。坚守角色，不迎合他人。"
                ),
            },
            {
                "id": "long_term",
                "name": "委员B · 长线配置委员",
                "model": models["committee"]["long_term"],
                "system": (
                    "你是黄金投委会【委员B · 长线配置委员】。核心投资哲学：重视 6 个月至数年宏观大周期、"
                    "央行购金底盘、信用货币对冲与纪律性分批积累；厌恶追涨杀跌，长线逻辑破坏或严重透支时认可再平衡。"
                ),
            },
            {
                "id": "risk_redteam",
                "name": "委员C · 逆向风控委员 (Red Team)",
                "model": models["committee"]["risk_redteam"],
                "system": (
                    "你是黄金投委会【委员C · 逆向风控委员（红队）】。职责是专门挑战市场盲点、拥挤度、"
                    "汇率反向波动、高危事件与回撤风险。仅当存在显著追高/大幅回撤/重大事件冲击、绝不适合全额激进买入时将 risk_veto 设为 true。"
                ),
            },
            {
                "id": "portfolio_cfo",
                "name": "委员D · 个人财务与仓位官",
                "model": models["committee"]["portfolio_cfo"],
                "system": (
                    "你是黄金投委会【委员D · 个人财务与仓位官】。只忠于用户的真实财务约束"
                    "（当前持仓本金/均价、月预算 3000 元及本月剩余预算、单笔最低买入门槛 1200 元、兼容短长线与止盈减仓），"
                    "严禁给出低于单笔最低门槛或超出本月剩余预算的买入金额，重点权衡均价摊薄效率、现金留存弹性与利润锁定。"
                ),
            },
        ]

        round1_prompt = f"""现在开始【第 1 轮：独立盲评与初投】。
请仔细阅读投研简报，独立给出你的投票（可选动作：{ALLOWED_ACTIONS}）及 1 个想质询其他委员的核心问题。

【投研与持仓简报】
{briefing_pack}
"""
        round1_records: list[dict[str, Any]] = []
        r1_ids: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {
                c["id"]: pool.submit(
                    call_gemini_json,
                    client,
                    model=c["model"],
                    system_instruction=c["system"],
                    prompt=round1_prompt,
                    schema=ROUND1_VOTE_SCHEMA,
                    thinking_level=thinking_level,
                )
                for c in committee_defs
            }
            for c in committee_defs:
                vote, interaction_id = futs[c["id"]].result()
                r1_ids[c["id"]] = interaction_id
                round1_records.append(
                    {"id": c["id"], "name": c["name"], "model": c["model"], "vote": vote}
                )

        print(
            "[INFO] Round 1 done: "
            + ", ".join(f"{r['name']}={r['vote']['action']}({r['vote']['confidence_1_to_10']})" for r in round1_records)
        )

        r1_debate_json = json.dumps(round1_records, ensure_ascii=False, indent=2)

        def build_r2_prompt(member_name: str) -> str:
            return f"""现在进入【第 2 轮：交叉质询、辩论与最终表决】。
以下是全部 4 位委员（含你自己：{member_name}）在 Round 1 的独立意见和质询问题：

{r1_debate_json}

请直面回应与你观点分歧最大的委员或回答其质疑，评估是否改票（changed_mind），投出最终正式票并明确给出执行金额/比例与触发条件。"""

        round2_records: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {
                c["id"]: pool.submit(
                    call_gemini_json,
                    client,
                    model=c["model"],
                    system_instruction=c["system"],
                    prompt=build_r2_prompt(c["name"]),
                    schema=ROUND2_VOTE_SCHEMA,
                    thinking_level=thinking_level,
                    previous_interaction_id=r1_ids[c["id"]],
                )
                for c in committee_defs
            }
            for c in committee_defs:
                vote, _ = futs[c["id"]].result()
                round2_records.append(
                    {"id": c["id"], "name": c["name"], "model": c["model"], "vote": vote}
                )

        tally = resolve_committee_vote(round2_records)
        print(
            f"[INFO] Round 2 done: {tally['vote_counts']} -> {tally['final_action']} "
            f"(avg_conf={tally['avg_confidence']}, risk_veto={tally['risk_veto_triggered']})"
        )

        # Write 03_meeting.md
        r1_md = "".join(
            f"### {r['name']}（模型：`{r['model']}`）\n"
            f"- **初投**：`{r['vote']['action']}`（{r['vote']['recommended_amount_desc']}） | 信心：{r['vote']['confidence_1_to_10']}/10 | 风控预警：`{r['vote']['risk_veto']}`\n"
            f"- **短线**：{r['vote']['short_term_stance']}\n"
            f"- **长线**：{r['vote']['long_term_stance']}\n"
            f"- **论据**：{r['vote']['core_rationale']}\n"
            f"- **质询问题**：{r['vote']['question_for_committee']}\n\n"
            for r in round1_records
        )
        r2_md = "".join(
            f"### {r['name']}（模型：`{r['model']}`）\n"
            f"- **终投**：`{r['vote']['action']}`（{r['vote']['recommended_amount_desc']}） | 改票：`{r['vote']['changed_mind']}` | 信心：{r['vote']['confidence_1_to_10']}/10 | 风控预警：`{r['vote']['risk_veto']}`\n"
            f"- **回应与交锋**：{r['vote']['response_to_peers']}\n"
            f"- **触发条件**：{r['vote']['trigger_conditions']}\n"
            f"- **终投陈词**：{r['vote']['final_statement']}\n\n"
            for r in round2_records
        )
        md_meeting = f"""# 03 投资决策委员会投票会议纪要（{run_id}）

- **会议日期**：{today_str}
- **触发升级原因**：{', '.join(det_reasons) if det_reasons else '例行/手动完整投委会'}
- **最终裁定动作**：`{tally['final_action']}` — {tally['final_action_label']}
- **终投分布**：`{json.dumps(tally['vote_counts'], ensure_ascii=False)}`
- **平均信心**：{tally['avg_confidence']} / 10 | **风控红队预警**：`{tally['risk_veto_triggered']}`
- **裁定规则**：{tally['resolution_rule']}

---

## 第一轮：独立盲评与初投
{r1_md}
---

## 第二轮：交叉质询、辩论与最终表决
{r2_md}
"""
        (run_dir / "03_meeting.md").write_text(md_meeting, encoding="utf-8")

        # PHASE 4: SECRETARY SYNTHESIS
        secretary_prompt = f"""你是【黄金投委会会议秘书】。今天是 {today_str}。
请基于本次会议的行情、持仓测算、两轮辩论记录及最终计票决议，生成一份清晰、克制、可直接执行的一页纸【最终投资决策单】。
必须严格遵守最终裁定动作（{tally['final_action']} - {tally['final_action_label']}）与规则说明（{tally['resolution_rule']}），同时覆盖短线（1-4周）与长线（3-12月）计划、逢低加仓与逢高止盈触发价位以及前 3 大核心风险。

【持仓测算】
{portfolio_metrics_json}

【计票裁定】
{json.dumps(tally, ensure_ascii=False, indent=2)}

【Round 2 终投记录】
{json.dumps(round2_records, ensure_ascii=False, indent=2)}
"""
        decision, _ = call_gemini_json(
            client,
            model=models["secretary"],
            prompt=secretary_prompt,
            schema=DECISION_SYNTHESIS_SCHEMA,
            thinking_level=thinking_level,
        )

        action = tally["final_action"]
        subject = f"【黄金投委会决议 {today_str}】{action} | 国内参考 {cny_price or 'N/A'} 元/克"
        md_decision = f"""# 04 最终投资决策单（{run_id}）

> **{decision['headline']}**

| 决议维度 | 内容 |
| --- | --- |
| 最终动作 | `{action}`（{tally['final_action_label']}） |
| 建议金额 / 比例 | {decision['recommended_amount_summary']} |
| 参考国内金价 | {cny_price if cny_price is not None else '待核实'} RMB/克 |
| 当前持仓状态 | 本金 {portfolio_metrics['principal_cny']} RMB / 均价 {portfolio_metrics['average_cost_cny_per_gram']} RMB/克 / 浮亏盈 {pnl_str} |
| 终投分布 | {json.dumps(tally['vote_counts'], ensure_ascii=False)}（平均信心 {tally['avg_confidence']}/10，风控预警：{tally['risk_veto_triggered']}） |
| 短线计划（1–4周） | {decision['short_term_plan']} |
| 长线计划（3–12月） | {decision['long_term_plan']} |
| 逢低加仓触发位 | {decision['dip_buy_triggers']} |
| 逢高止盈触发位 | {decision['take_profit_triggers']} |

## 核心风险提示
""" + "\n".join(f"- {r}" for r in decision["top_risks"]) + f"""

---

{decision['decision_markdown']}
"""
        (run_dir / "04_decision.md").write_text(md_decision, encoding="utf-8")

        committee_rows = [
            (
                r["name"],
                r["vote"]["action"],
                f"{r['vote']['confidence_1_to_10']}/10" + (" ⚠️" if r["vote"]["risk_veto"] else ""),
                r["vote"]["recommended_amount_desc"],
            )
            for r in round2_records
        ]
        email_html = render_email_html(
            date_str=today_str,
            run_mode="full",
            headline=decision["headline"],
            action=action,
            action_desc=f"{tally['final_action_label']}（{tally['resolution_rule']}，平均信心 {tally['avg_confidence']}/10）",
            cny_price=cny_price,
            xau_usd=intel["market"]["xau_usd_price"],
            portfolio_metrics=portfolio_metrics,
            summary_rows=[
                ("建议执行金额/比例", decision["recommended_amount_summary"]),
                ("短线计划（1–4周）", decision["short_term_plan"]),
                ("长线计划（3–12月）", decision["long_term_plan"]),
                ("逢低加仓触发位", decision["dip_buy_triggers"]),
                ("逢高止盈触发位", decision["take_profit_triggers"]),
            ],
            risks=decision["top_risks"],
            committee_table_rows=committee_rows,
            model_usage_note=(
                f"Gemini 4 分级模型（全员 thinking={thinking_level}）：采集/仓位/秘书={models['secretary']}，"
                f"宏观/趋势/波段={models['analysts']['policy']}，"
                f"长线/财务={models['committee']['long_term']}，"
                f"红队风控={models['committee']['risk_redteam']}"
            ),
        )
        (run_dir / "email.html").write_text(email_html, encoding="utf-8")
        (run_dir / "raw_result.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "mode": "full",
                    "escalation_reasons": det_reasons,
                    "portfolio": portfolio,
                    "portfolio_metrics": portfolio_metrics,
                    "intel": intel,
                    "analysis": analysis,
                    "round1_votes": round1_records,
                    "round2_votes": round2_records,
                    "tally": tally,
                    "decision": decision,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        vote_compact = ", ".join(f"{k}:{v}" for k, v in tally["vote_counts"].items())
        short_amt = decision["recommended_amount_summary"].replace("\n", " ")[:80]
        ledger_row = (
            f"| {run_id} | {cny_price if cny_price is not None else 'N/A'} | {pnl_str} | "
            f"`{action}` | {short_amt} | {vote_compact} | [查看档案](runs/{run_id}/04_decision.md) |\n"
        )

    # Append to ledger.md
    if not LEDGER_PATH.exists():
        LEDGER_PATH.write_text(
            "# 黄金投资决策历史总台账（Decision Ledger）\n\n"
            "| 日期时间 | 参考国内金价 (RMB/克) | 持仓浮动盈亏 | 最终决议动作 | 建议金额 / 比例 | 投票分布 (终投) | 会议档案链接 |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    with open(LEDGER_PATH, "a", encoding="utf-8") as lf:
        lf.write(ledger_row)

    # Write dispatch manifest for the 08:00 CST email sender job
    dispatch_payload = {
        "date": today_str,
        "run_id": run_id,
        "computed_at_cst": datetime.now(SHANGHAI_TZ).isoformat(),
        "mode": "full" if run_full else "light",
        "subject": subject,
        "recipient": models_cfg["email"]["recipient"],
        "html_path": str((run_dir / "email.html").relative_to(REPO_ROOT)),
        "text_path": str((run_dir / "04_decision.md").relative_to(REPO_ROOT)),
        "sent": False,
        "sent_at_cst": None,
    }
    LATEST_DISPATCH_PATH.write_text(
        json.dumps(dispatch_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] Compute complete! Dispatch saved to {LATEST_DISPATCH_PATH}")


if __name__ == "__main__":
    main()
