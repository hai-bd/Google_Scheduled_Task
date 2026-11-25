import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ==============================================================================
# Local Antigravity Multi-Agent Gold Investment Decision Workflow
# Runs on Antigravity flagship models (0 extra API billing) with native search_web.
#
# Phases:
#   1. Parallel Information Collection (Market/FX, Macro/Policy, Geopolitics/Sentiment) [flash]
#   2. Parallel Multi-Dimensional Analysis (Policy, Short+Long Trend [inherit], Portfolio [flash])
#   3. 2-Round Heterogeneous Investment Committee Voting & Debate (4 persistent agents) [inherit]
#   4. Committee Secretary Synthesis [flash] + Markdown Archive + HTML Email + Ledger Update
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

ACTION_LABELS = {
    "BUY_FULL": "全额买入（动用本月全部或绝大部分剩余预算，可分笔执行）",
    "BUY_PARTIAL": "分批/部分买入（动用部分月度预算，保留弹药防回调）",
    "HOLD": "维持观望（暂不新增仓位也不减仓，等待触发价位）",
    "TAKE_PROFIT_PARTIAL": "部分止盈/减仓（落袋部分利润，保留长线底仓）",
    "REDUCE_HEAVY": "大幅减仓防守（显著降仓规避短期下行或利多出尽风险）",
}

ALLOWED_ACTIONS = list(ACTION_LABELS.keys())

# ------------------------------------------------------------------------------
# Schemas
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

RADAR_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "price_range": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["price_range", "note"],
}

DECISION_SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "recommended_amount_short": {"type": "string"},
        "recommended_amount_summary": {"type": "string"},
        "macro_one_liner": {"type": "string"},
        "short_term_one_liner": {"type": "string"},
        "long_term_one_liner": {"type": "string"},
        "radar_dip_buy": RADAR_ITEM_SCHEMA,
        "radar_defense": RADAR_ITEM_SCHEMA,
        "radar_short_tp": RADAR_ITEM_SCHEMA,
        "radar_long_tp": RADAR_ITEM_SCHEMA,
        "action_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["label", "text"],
            },
        },
        "committee_one_liners": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "action": {"type": "string"},
                    "confidence": {"type": "string"},
                    "logic": {"type": "string"},
                },
                "required": ["member", "action", "confidence", "logic"],
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
        "short_term_plan": {"type": "string"},
        "long_term_plan": {"type": "string"},
        "dip_buy_triggers": {"type": "string"},
        "take_profit_triggers": {"type": "string"},
        "top_risks": {"type": "array", "items": {"type": "string"}},
        "decision_markdown": {"type": "string"},
    },
    "required": [
        "headline",
        "recommended_amount_short",
        "recommended_amount_summary",
        "macro_one_liner",
        "short_term_one_liner",
        "long_term_one_liner",
        "radar_dip_buy",
        "radar_defense",
        "radar_short_tp",
        "radar_long_tp",
        "action_steps",
        "committee_one_liners",
        "risk_items",
        "short_term_plan",
        "long_term_plan",
        "dip_buy_triggers",
        "take_profit_triggers",
        "top_risks",
        "decision_markdown",
    ],
}

# ------------------------------------------------------------------------------
# Helper: Quantitative Portfolio Math (Respects min_single_buy & monthly tracker)
# ------------------------------------------------------------------------------


def compute_portfolio_metrics(portfolio: dict, current_price_cny: float | None, today_str: str) -> dict:
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

    metrics = {
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


def resolve_committee_vote(round2_records: list[dict]) -> dict:
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
            resolution_rule = "多空平票分歧，触发保守折中规则降级为观望并设双边触发价"
        elif tied_actions == {"BUY_FULL", "BUY_PARTIAL"}:
            final_action = "BUY_PARTIAL"
            resolution_rule = "全买与分批买平票，采用保守分批买入"
        elif tied_actions == {"BUY_PARTIAL", "HOLD"}:
            final_action = "HOLD" if risk_veto_triggered else "BUY_PARTIAL"
            resolution_rule = (
                "分批买与观望平票且触发风控预警，降级为观望"
                if risk_veto_triggered
                else "分批买与观望平票且无风控一票否决，采用最小合规手数分批定投"
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
        resolution_rule += "；但逆向风控委员触发风险预警，强制将全额买入降级为分批买入"

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


def action_badge_style(action: str) -> tuple[str, str]:
    return {
        "BUY_FULL": ("#0f766e", "全额分批买入"),
        "BUY_PARTIAL": ("#0369a1", "逢低分批买入"),
        "HOLD": ("#475569", "维持观望"),
        "TAKE_PROFIT_PARTIAL": ("#b45309", "部分止盈减仓"),
        "REDUCE_HEAVY": ("#b91c1c", "防守减仓"),
    }.get(action, ("#334155", action))


def render_email_html(
    *,
    date_str: str,
    headline: str,
    action: str,
    recommended_amount_short: str,
    consensus_text: str,
    cny_price: float | None,
    xau_usd_short: str,
    monthly_budget_cny: float,
    min_single_buy_cny: float,
    outlook_bullets: list[tuple[str, str]],
    price_radar: list[tuple[str, str, str, str]],
    action_steps: list[tuple[str, str]],
    committee_table_rows: list[tuple[str, str, str, str]],
    risk_bullets: list[tuple[str, str]],
) -> str:
    """Institutional Morning Note HTML (privacy-safe: NEVER exposes personal holdings/cost/PnL)."""
    esc = html.escape
    badge_bg, action_cn = action_badge_style(action)
    cny_price_str = f"{cny_price} 元/克" if cny_price is not None else "待核实"

    outlook_html = "".join(
        f"""
        <tr>
          <td style="padding:7px 0;vertical-align:top;width:88px;">
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;background:#f1f5f9;color:#334155;font-size:12px;font-weight:700;white-space:nowrap;">{esc(tag)}</span>
          </td>
          <td style="padding:7px 0 7px 10px;color:#1e293b;font-size:13.5px;line-height:1.55;">{esc(desc)}</td>
        </tr>
        """
        for tag, desc in outlook_bullets
    )
    radar_cells = "".join(
        f"""
        <td style="width:25%;padding:4px;vertical-align:top;">
          <div style="background:#f8fafc;border:1px solid #e2e8f0;border-top:3px solid {accent};border-radius:6px;padding:10px 8px;text-align:center;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">{esc(label)}</div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin:4px 0 2px;">{esc(price_range)}</div>
            <div style="font-size:11px;color:#64748b;line-height:1.35;">{esc(note)}</div>
          </div>
        </td>
        """
        for label, price_range, note, accent in price_radar
    )
    actions_html = "".join(
        f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top;width:24px;">
            <span style="display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;border-radius:50%;background:#1e293b;color:#fbbf24;font-size:11px;font-weight:700;">{idx}</span>
          </td>
          <td style="padding:8px 10px 8px 4px;border-bottom:1px solid #f1f5f9;font-size:13.5px;color:#0f172a;line-height:1.55;">
            <strong style="color:#0f172a;">{esc(label)}：</strong>{esc(text)}
          </td>
        </tr>
        """
        for idx, (label, text) in enumerate(action_steps, start=1)
    )
    c_rows = "".join(
        f"""
        <tr>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;font-weight:600;color:#1e293b;white-space:nowrap;">{esc(name)}</td>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;white-space:nowrap;">
            <span style="display:inline-block;padding:2px 7px;border-radius:4px;background:{action_badge_style(vote)[0]};color:#ffffff;font-size:11px;font-weight:700;">{esc(vote)}</span>
          </td>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;color:#475569;white-space:nowrap;">{esc(conf)}</td>
          <td style="padding:7px 8px;border-bottom:1px solid #f1f5f9;color:#334155;line-height:1.45;">{esc(logic)}</td>
        </tr>
        """
        for name, vote, conf, logic in committee_table_rows
    )
    r_items = "".join(
        f"""
        <li style="margin-bottom:6px;font-size:13px;color:#334155;line-height:1.5;">
          <strong style="color:#b91c1c;">[{esc(tag)}]</strong> {esc(desc)}
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
          <td style="font-size:11px;letter-spacing:1.4px;color:#f59e0b;font-weight:700;">GOLD RESEARCH · MORNING BRIEFING</td>
          <td style="text-align:right;font-size:12px;color:#94a3b8;">{esc(date_str)} · 盘前晨报</td>
        </tr>
      </table>
      <h1 style="margin:10px 0 12px;font-size:19px;line-height:1.4;color:#ffffff;font-weight:700;">{esc(headline)}</h1>
      <div>
        <span style="display:inline-block;padding:4px 11px;border-radius:4px;background:{badge_bg};color:#ffffff;font-size:12px;font-weight:700;">{esc(action)} · {esc(action_cn)}</span>
        <span style="display:inline-block;margin-left:8px;font-size:12px;color:#cbd5e1;">{esc(consensus_text)}</span>
      </div>
    </div>

    <div style="background:#f8fafc;border-bottom:1px solid #e2e8f0;padding:14px 20px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:34%;padding-right:10px;border-right:1px solid #e2e8f0;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">国内参考金价</div>
            <div style="font-size:20px;font-weight:800;color:#0f172a;margin-top:3px;">{esc(cny_price_str)}</div>
            <div style="font-size:11px;color:#64748b;margin-top:2px;">国际：{esc(xau_usd_short)}</div>
          </td>
          <td style="width:36%;padding:0 12px;border-right:1px solid #e2e8f0;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">建议操作金额</div>
            <div style="font-size:18px;font-weight:800;color:{badge_bg};margin-top:4px;">{esc(recommended_amount_short)}</div>
            <div style="font-size:11px;color:#64748b;margin-top:2px;">按月度 {int(monthly_budget_cny):,} 元定投模型</div>
          </td>
          <td style="width:30%;padding-left:12px;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">定投纪律参数</div>
            <div style="font-size:15px;font-weight:700;color:#0f172a;margin-top:5px;">月预算 {int(monthly_budget_cny):,} 元</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;">单笔起投 ≥ {int(min_single_buy_cny):,} 元</div>
          </td>
        </tr>
      </table>
    </div>

    <div style="padding:20px 24px 22px;">
      <div>
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">01 ｜ 形势与走向速览</div>
        <table style="width:100%;border-collapse:collapse;"><tbody>{outlook_html}</tbody></table>
      </div>

      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:10px;">02 ｜ 关键价位雷达（RMB / 克）</div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>{radar_cells}</tr></table>
      </div>

      <div style="margin-top:20px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:6px;">03 ｜ 今日执行清单（月预算 {int(monthly_budget_cny):,} 元模型）</div>
        <table style="width:100%;border-collapse:collapse;"><tbody>{actions_html}</tbody></table>
      </div>

      <div style="margin-top:20px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">04 ｜ 投委会表决矩阵</div>
        <table style="width:100%;border-collapse:collapse;font-size:12.5px;">
          <thead>
            <tr style="background:#f8fafc;color:#64748b;text-align:left;">
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">委员</th>
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">投票</th>
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">信心</th>
              <th style="padding:6px 8px;border-bottom:1px solid #e2e8f0;">核心逻辑</th>
            </tr>
          </thead>
          <tbody>{c_rows}</tbody>
        </table>
      </div>

      <div style="margin-top:20px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 14px;">
        <div style="font-size:12.5px;font-weight:800;color:#991b1b;margin-bottom:6px;">05 ｜ 关键风险提示</div>
        <ul style="margin:0;padding-left:18px;">{r_items}</ul>
      </div>

      <div style="margin-top:20px;padding-top:12px;border-top:1px solid #e2e8f0;font-size:11.5px;color:#64748b;line-height:1.55;">
        <div>免责声明：本晨报由多 Agent 投研系统自动生成，统一基于「月度 {int(monthly_budget_cny):,} 元 / 单笔起投 {int(min_single_buy_cny):,} 元」标准模型测算，不含个人持仓信息，仅供投研参考，不构成持牌金融投资建议。</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ==============================================================================
# PHASE 1: PARALLEL INFORMATION COLLECTION
# ==============================================================================

phase("Phase 1: 并发信息采集")
log(f"启动黄金投委会 Workflow | Run ID: {RUN_ID} | 日期: {TODAY_STR}")

collector_specs = [
    {
        "key": "market",
        "role": "实时行情与汇率采集员",
        "schema": MARKET_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【实时行情与汇率采集员】。今天是 {TODAY_STR}（北京时间）。
请使用 search_web 搜索今天（或最近一个交易日）最新的黄金与关联市场客观行情数据：
1. 国际现货黄金（XAU/USD）价格与近期走势；
2. 中国国内人民币黄金克价（上海黄金交易所 AU9999 / 沪金主力 / 银行积存金克价），请务必核实并以纯数字填入 cny_gold_price_per_gram（单位：人民币/克；若网页未给出精确数字可根据 XAU/USD 与 USD/CNY 换算并在 cny_gold_price_note 中明确注明“按国际金价与汇率折算”）；
3. 美元兑人民币汇率（USD/CNY）、美元指数（DXY）、美国10年期国债收益率；
4. 近1-2周金价波动特征。
严格要求：只汇报客观事实与数据，标注来源与日期，不得编造数据，不要给出买卖建议。
""",
    },
    {
        "key": "macro",
        "role": "宏观与央行政策采集员",
        "schema": MACRO_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【宏观与央行政策采集员】。今天是 {TODAY_STR}。
请使用 search_web 搜索近期（过去2-4周及隔夜最新动态）影响黄金定价的宏观经济与央行政策新闻：
1. 美联储（Fed）最新利率决议、官员表态、市场对未来降息/加息路径的预期；
2. 美国最新通胀（CPI/PCE）、就业（非农）及经济数据；
3. 中国央行（PBOC）及全球央行最新黄金储备增持/暂停动态；
4. 重要财政政策、赤字、关税贸易政策或汇率政策新闻；
5. 未来2-4周即将公布的关键宏观日历事件。
严格要求：只输出有据可查的客观政策与新闻事实，标注来源和日期，不做主观交易建议。
""",
    },
    {
        "key": "geo",
        "role": "地缘政治与市场情绪采集员",
        "schema": GEO_INTEL_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【地缘政治与市场情绪采集员】。今天是 {TODAY_STR}。
请使用 search_web 搜索近期影响黄金避险情绪与资金面的动态：
1. 近期重大地缘政治局势与避险催化；
2. 全球黄金 ETF（如 SPDR GLD）及中国国内黄金 ETF 资金流入/流出情况；
3. 投行/主流机构（如高盛、瑞银、世界黄金协会等）近期对金价的最新观点或目标价调整；
4. 市场拥挤度、散户/投机多头情绪是否过热或恐慌。
严格要求：保持中立客观，所有事实标注来源和日期，不要输出买卖建议。
""",
    },
]

collector_results_list = await parallel(
    collector_specs,
    lambda s: agent(s["prompt"], schema=s["schema"], role=s["role"], model="flash"),
)
intel = {collector_specs[i]["key"]: collector_results_list[i] for i in range(len(collector_specs))}

cny_price = intel["market"].get("cny_gold_price_per_gram")
portfolio_metrics = compute_portfolio_metrics(PORTFOLIO, cny_price, TODAY_STR)
log(
    f"Phase 1 完成 | 国际金价: {intel['market']['xau_usd_price']} | "
    f"国内参考克价: {cny_price} RMB/g | 情绪: {intel['geo']['market_sentiment_label']}"
)

intel_bundle_json = json.dumps(intel, ensure_ascii=False, indent=2)
portfolio_metrics_json = json.dumps(portfolio_metrics, ensure_ascii=False, indent=2)
portfolio_raw_json = json.dumps(PORTFOLIO, ensure_ascii=False, indent=2)

# ==============================================================================
# PHASE 2: PARALLEL MULTI-DIMENSIONAL ANALYSIS
# ==============================================================================

phase("Phase 2: 多维专业分析")

analyst_specs = [
    {
        "key": "policy",
        "role": "政策与宏观基本面分析师",
        "model": "inherit",
        "schema": POLICY_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【政策与宏观基本面分析师】。今天是 {TODAY_STR}。
请严格基于下方 Phase 1 采集到的最新客观情报，进行深度政策与宏观基本面拆解：
1. 判断当前黄金所处的宏观定价范式；
2. 分别列举最核心的利多驱动与利空压制/风险点；
3. 区分“短期情绪噪音”与“中期决定方向的真主线”；
4. 给出整体基本面偏向判断，并撰写中文分析正文（analysis_markdown）。

【Phase 1 客观情报包】
{intel_bundle_json}
""",
    },
    {
        "key": "trend",
        "role": "短线波段与长线趋势分析师",
        "model": "inherit",
        "schema": TREND_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【短线波段与长线趋势分析师】。今天是 {TODAY_STR}。
用户明确表示：**同时接受短线波段操作与长线配置，且允许止盈减仓**。
请严格基于下方客观情报，同时从“短线（1–4周）”和“长线（3–12个月）”两个维度分析金价走向，给出国内人民币金价（RMB/克）的关键支撑位与阻力/止盈区间、多情景概率及中文正文（analysis_markdown）。

【Phase 1 客观情报包】
{intel_bundle_json}
""",
    },
    {
        "key": "portfolio",
        "role": "个人持仓与仓位管理分析师",
        "model": "flash",
        "schema": PORTFOLIO_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【个人持仓与仓位管理分析师】。今天是 {TODAY_STR}。
请结合用户的真实账户配置、已算好的定量指标和最新行情，做严谨的资金管理与仓位评估：
1. 评估用户当前持仓健康度与安全垫；
2. 严格遵守**单笔最低买入金额 min_single_buy_cny（{portfolio_metrics['min_single_buy_cny']} 元）**与**本月剩余可用预算 remaining_budget_this_month_cny（{portfolio_metrics['remaining_budget_this_month_cny']} 元）**，对比可执行加仓方案与减仓 20%/30%/50% 方案；
3. 提出风控护栏建议并撰写包含清晰表格的中文正文（analysis_markdown）。

【用户账户配置】
{portfolio_raw_json}

【定量持仓与加减仓测算结果】
{portfolio_metrics_json}

【实时行情摘要】
{json.dumps(intel["market"], ensure_ascii=False, indent=2)}
""",
    },
]

analyst_results_list = await parallel(
    analyst_specs,
    lambda s: agent(s["prompt"], schema=s["schema"], role=s["role"], model=s["model"]),
)
analysis = {analyst_specs[i]["key"]: analyst_results_list[i] for i in range(len(analyst_specs))}
log(
    f"Phase 2 完成 | 基本面: {analysis['policy']['fundamental_bias']} | "
    f"短线: {analysis['trend']['short_term_view']} | 长线: {analysis['trend']['long_term_view']}"
)

briefing_pack = json.dumps(
    {
        "date": TODAY_STR,
        "portfolio": PORTFOLIO,
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

# ==============================================================================
# PHASE 3: 2-ROUND HETEROGENEOUS INVESTMENT COMMITTEE VOTING & DEBATE
# ==============================================================================

phase("Phase 3: 投委会两轮讨论与投票会议")

committee_defs = [
    {
        "id": "trend_swing",
        "name": "委员A · 趋势波段委员",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员A · 趋势波段委员】。
核心投资哲学：重视动量、波段赔率、事件催化与右侧顺势；强支撑或突破初期敢于出击，超买/阻力位敢于主张短线部分止盈。坚守角色，不迎合他人。""",
    },
    {
        "id": "long_term",
        "name": "委员B · 长线配置委员",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员B · 长线配置委员】。
核心投资哲学：重视 6 个月至数年宏观大周期、央行购金底盘、信用货币对冲与纪律性分批积累；厌恶追涨杀跌，长线逻辑破坏或严重透支时认可再平衡。""",
    },
    {
        "id": "risk_redteam",
        "name": "委员C · 逆向风控委员 (Red Team)",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员C · 逆向风控委员（红军/挑刺者）】。
职责是专门审视市场盲点、多头拥挤度、汇率反向波动、短期回调回撤和重大数据公布前的事件风险。
只有当存在显著追高/大幅回撤/高危事件风险、绝不适合全额激进买入时，才将 risk_veto 设为 true 并给出充分依据。""",
    },
    {
        "id": "portfolio_cfo",
        "name": "委员D · 个人财务与仓位官",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员D · 个人财务与仓位官】。
你只忠于用户的真实财务约束：单笔最低买入门槛 {portfolio_metrics['min_single_buy_cny']} RMB，本月剩余可用预算 {portfolio_metrics['remaining_budget_this_month_cny']} RMB（月总预算 {portfolio_metrics['monthly_budget_cny']} RMB），严禁建议低于最低起投额或超出本月剩余预算的买入金额。""",
    },
]

committee_members = [
    {
        "id": c["id"],
        "name": c["name"],
        "agent": agent(c["standing"], role=c["name"], model="inherit"),
    }
    for c in committee_defs
]

round1_prompt = f"""现在开始【第 1 轮：独立盲评与初投】。
请仔细阅读投研简报，独立给出投票（可选动作：{ALLOWED_ACTIONS}）及 1 个想质询其他委员的核心问题。
注意硬性约束：平台单笔最低买入金额为 **{portfolio_metrics['min_single_buy_cny']} RMB**，本月剩余可用预算为 **{portfolio_metrics['remaining_budget_this_month_cny']} RMB**。若建议买入，金额必须 ≥ {portfolio_metrics['min_single_buy_cny']} 且 ≤ {portfolio_metrics['remaining_budget_this_month_cny']}（若本月剩余预算不足起投额，则只能选 HOLD 或止盈减仓）。

【投研与持仓简报】
{briefing_pack}
"""

log("投委会 Round 1（独立初评）开始...")
round1_votes_list = await parallel(
    committee_members,
    lambda m: m["agent"](round1_prompt, ROUND1_VOTE_SCHEMA),
)
round1_records = [
    {"id": committee_members[i]["id"], "name": committee_members[i]["name"], "vote": round1_votes_list[i]}
    for i in range(len(committee_members))
]
log(
    "Round 1 结果: "
    + ", ".join(f"{r['name']}={r['vote']['action']}({r['vote']['confidence_1_to_10']}/10)" for r in round1_records)
)

round1_summary_for_debate = json.dumps(round1_records, ensure_ascii=False, indent=2)


def build_round2_prompt(member_name: str) -> str:
    return f"""现在进入【第 2 轮：交叉质询、辩论与最终表决】。
以下是全部 4 位委员（包括你自己：{member_name}）在 Round 1 的独立意见和质询问题：

{round1_summary_for_debate}

请直面回应与你意见分歧最大的委员或回答他们的问题，冷静评估是否维持或修正投票（changed_mind），投出最终正式票并明确给出合规金额（买入须 ≥ {portfolio_metrics['min_single_buy_cny']} RMB 且 ≤ {portfolio_metrics['remaining_budget_this_month_cny']} RMB）/减仓比例及触发条件。
"""


log("投委会 Round 2（交叉辩论与终投）开始...")
round2_votes_list = await parallel(
    committee_members,
    lambda m: m["agent"](build_round2_prompt(m["name"]), ROUND2_VOTE_SCHEMA),
)
round2_records = [
    {"id": committee_members[i]["id"], "name": committee_members[i]["name"], "vote": round2_votes_list[i]}
    for i in range(len(committee_members))
]

tally = resolve_committee_vote(round2_records)
log(
    f"Round 2 终投结果: {tally['vote_counts']} -> 最终决议: {tally['final_action']} "
    f"| 平均信心: {tally['avg_confidence']}/10 | 风控预警: {tally['risk_veto_triggered']}"
)

# ==============================================================================
# PHASE 4: SECRETARY SYNTHESIS & ARCHIVE PERSISTENCE
# ==============================================================================

phase("Phase 4: 会议秘书归档与决策单生成")

secretary_prompt = f"""{ISOLATION_GUARD}
你是【高盛/瑞银投行晨会风格的黄金投委会会议秘书】。今天是 {TODAY_STR}。
请基于本次会议的行情、两轮辩论记录及最终计票决议，输出一份**极致精炼、30秒扫完、结构化分明**的投行晨报 JSON。

【最高铁律 — 违反即不合格】
1. **严格隐私脱敏**：所有字段（含 decision_markdown 之外的全部邮件字段）**严禁出现任何个人真实持仓金额、本金、均价（如 840.31）、克数或账面浮亏/浮盈数字**！统一按「月度 3,000 元定投预算（单笔起投 1,200 元）」表述。
2. **投行级极简字数控制（严禁长段废话）**：
   - `headline`：≤ 22 字，直给核心结论（例：`PCE偏热金价破3500，今日观望等725–745低吸`）
   - `recommended_amount_short`：极短数字标签（例：`0 元 · 暂缓加仓` / `1,200 元 · 逢低分批`）
   - `macro_one_liner` / `short_term_one_liner` / `long_term_one_liner`：每条严格 **20–35 字**，只讲核心因果与数字！
   - `radar_dip_buy` / `radar_defense` / `radar_short_tp` / `radar_long_tp`：`price_range` 写纯数字区间（如 `725–745`），`note` 严格 **≤ 12 字**！
   - `action_steps`：**恰好 3 条**，每条 `label`（4–6 字）+ `text`（**≤ 36 字**，直接写触发条件与金额）！
   - `committee_one_liners`：**恰好 4 条**，对应 4 位委员（简称：`趋势波段` / `长线配置` / `逆向风控` / `财务仓位`），`logic` 严格 **≤ 22 字**！
   - `risk_items`：**恰好 3 条**，每条 `tag`（4–6 字）+ `desc`（**≤ 34 字**）！
3. 严格尊重最终计票决议（{tally['final_action']} - {tally['final_action_label']}）与裁定说明（{tally['resolution_rule']}）。

【最终计票与规则裁定】
{json.dumps(tally, ensure_ascii=False, indent=2)}

【市场形势与趋势摘要】
{json.dumps({"policy": {k: v for k, v in analysis["policy"].items() if k != "analysis_markdown"}, "trend": {k: v for k, v in analysis["trend"].items() if k != "analysis_markdown"}}, ensure_ascii=False, indent=2)}

【Round 2 终投记录】
{json.dumps(round2_records, ensure_ascii=False, indent=2)}
"""

decision = await agent(
    secretary_prompt,
    schema=DECISION_SYNTHESIS_SCHEMA,
    role="投委会会议秘书",
    model="flash",
)


def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "- （未提供额外来源）"
    return "\n".join(
        f"- **{s['title']}**（{s['source']}，{s['date']}）：{s['key_fact']}" for s in sources
    )


pnl_str = (
    f"{portfolio_metrics['unrealized_pnl_cny']:+.2f} RMB ({portfolio_metrics['unrealized_pnl_pct']:+.2f}%)"
    if "unrealized_pnl_cny" in portfolio_metrics
    else "N/A"
)

md_intel = f"""# 01 黄金投研客观情报档案（{RUN_ID}）

- **采集日期**：{TODAY_STR}
- **行情基准时间**：{intel['market']['as_of_date']}

## 一、实时行情与关联指标

| 指标 | 最新读数 / 说明 |
| --- | --- |
| 国际现货黄金 (XAU/USD) | {intel['market']['xau_usd_price']} |
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
- **财政与关税/贸易政策**：{intel['macro']['fiscal_and_tariff_policy_summary']}

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

md_analysis = f"""# 02 多维专业分析报告（{RUN_ID}）

## 一、政策与宏观基本面分析
- **宏观定价范式**：{analysis['policy']['macro_regime']}
- **基本面综合偏向**：`{analysis['policy']['fundamental_bias']}`
- **噪音 vs 主线**：{analysis['policy']['noise_vs_signal']}

**核心利多驱动**：
""" + "\n".join(f"- {x}" for x in analysis["policy"]["bullish_drivers"]) + """

**核心利空与压制**：
""" + "\n".join(f"- {x}" for x in analysis["policy"]["bearish_drivers"]) + f"""

{analysis['policy']['analysis_markdown']}

---

## 二、短线波段与长线趋势走向分析
- **短线视角（1–4 周）**：`{analysis['trend']['short_term_view']}` — {analysis['trend']['short_term_horizon_1_4w']}
- **长线视角（3–12 个月）**：`{analysis['trend']['long_term_view']}` — {analysis['trend']['long_term_horizon_3_12m']}
- **国内金价关键支撑位**：{', '.join(analysis['trend']['key_support_levels_cny_g'])}
- **国内金价关键阻力/止盈位**：{', '.join(analysis['trend']['key_resistance_levels_cny_g'])}
- **情景概览**：{analysis['trend']['scenario_summary']}

{analysis['trend']['analysis_markdown']}

---

## 三、个人持仓与仓位管理分析
- **持仓健康度评估**：{analysis['portfolio']['position_health_assessment']}
- **加仓方案对比**：{analysis['portfolio']['buy_scenarios_summary']}
- **止盈/减仓方案对比**：{analysis['portfolio']['take_profit_scenarios_summary']}

**风控护栏建议**：
""" + "\n".join(f"- {x}" for x in analysis["portfolio"]["risk_guardrails"]) + f"""

{analysis['portfolio']['analysis_markdown']}
"""

r1_blocks = "".join(
    f"### {r['name']}\n"
    f"- **初投动作**：`{r['vote']['action']}`（{r['vote']['recommended_amount_desc']}） | **信心分**：{r['vote']['confidence_1_to_10']}/10 | **风控预警**：`{r['vote']['risk_veto']}`\n"
    f"- **短线观点**：{r['vote']['short_term_stance']}\n"
    f"- **长线观点**：{r['vote']['long_term_stance']}\n"
    f"- **核心论据**：{r['vote']['core_rationale']}\n"
    f"- **风控预警说明**：{r['vote']['risk_veto_reason']}\n"
    f"- **向委员会提出的质询问题**：{r['vote']['question_for_committee']}\n\n"
    for r in round1_records
)
r2_blocks = "".join(
    f"### {r['name']}\n"
    f"- **最终投票**：`{r['vote']['action']}`（{r['vote']['recommended_amount_desc']}） | **是否改票**：`{r['vote']['changed_mind']}` | **信心分**：{r['vote']['confidence_1_to_10']}/10 | **风控预警**：`{r['vote']['risk_veto']}`\n"
    f"- **回应质疑与交锋**：{r['vote']['response_to_peers']}\n"
    f"- **触发条件**：{r['vote']['trigger_conditions']}\n"
    f"- **终投陈词**：{r['vote']['final_statement']}\n\n"
    for r in round2_records
)

md_meeting = f"""# 03 投资决策委员会投票会议纪要（{RUN_ID}）

- **会议日期**：{TODAY_STR}
- **最终裁定动作**：`{tally['final_action']}` — {tally['final_action_label']}
- **终投分布**：`{json.dumps(tally['vote_counts'], ensure_ascii=False)}`
- **委员会平均信心**：{tally['avg_confidence']} / 10
- **逆向风控预警触发**：`{tally['risk_veto_triggered']}`
- **计票规则裁定说明**：{tally['resolution_rule']}

---

## 第一轮：独立盲评与初投
{r1_blocks}
---

## 第二轮：交叉质询、辩论与最终表决
{r2_blocks}
"""

md_decision = f"""# 04 最终投资决策单（{RUN_ID}）

> **{decision['headline']}**

| 决议维度 | 内容 |
| --- | --- |
| 最终动作 | `{tally['final_action']}`（{tally['final_action_label']}） |
| 建议金额 / 比例 | {decision['recommended_amount_summary']} |
| 当前参考国内金价 | {cny_price if cny_price is not None else '待核实'} RMB/克 |
| 当前持仓状态 | 本金 {portfolio_metrics['principal_cny']} RMB / 均价 {portfolio_metrics['average_cost_cny_per_gram']} RMB/克 / 浮亏盈 {pnl_str} |
| 本月剩余预算 | {portfolio_metrics['remaining_budget_this_month_cny']} RMB（单笔起投 {portfolio_metrics['min_single_buy_cny']} RMB） |
| 终投分布 | {json.dumps(tally['vote_counts'], ensure_ascii=False)}（平均信心 {tally['avg_confidence']}/10） |
| 短线计划（1–4周） | {decision['short_term_plan']} |
| 长线计划（3–12月） | {decision['long_term_plan']} |
| 逢低加仓触发位 | {decision['dip_buy_triggers']} |
| 逢高止盈触发位 | {decision['take_profit_triggers']} |

## 核心风险提示
""" + "\n".join(f"- {r}" for r in decision["top_risks"]) + f"""

---

{decision['decision_markdown']}
"""

committee_rows = [
    (item["member"], item["action"], item["confidence"], item["logic"])
    for item in decision["committee_one_liners"]
]
risk_bullets = [(item["tag"], item["desc"]) for item in decision["risk_items"]]
action_steps = [(item["label"], item["text"]) for item in decision["action_steps"]]
price_radar = [
    ("逢低加仓区", decision["radar_dip_buy"]["price_range"], decision["radar_dip_buy"]["note"], "#16a34a"),
    ("破位防守线", decision["radar_defense"]["price_range"], decision["radar_defense"]["note"], "#dc2626"),
    ("短线止盈区", decision["radar_short_tp"]["price_range"], decision["radar_short_tp"]["note"], "#d97706"),
    ("长线止盈区", decision["radar_long_tp"]["price_range"], decision["radar_long_tp"]["note"], "#0284c7"),
]
xau_short = intel["market"]["xau_usd_price"].split("（")[0].split("(")[0].strip()[:26]

email_subject = f"【黄金晨报 {TODAY_STR}】{tally['final_action']} · {decision['recommended_amount_short']} | 国内 {cny_price or 'N/A'} 元/克"
email_html = render_email_html(
    date_str=TODAY_STR,
    headline=decision["headline"],
    action=tally["final_action"],
    recommended_amount_short=decision["recommended_amount_short"],
    consensus_text=f"{tally['resolution_rule']} · 平均信心 {tally['avg_confidence']}/10" + (" · 红队风控预警" if tally["risk_veto_triggered"] else ""),
    cny_price=cny_price,
    xau_usd_short=xau_short,
    monthly_budget_cny=portfolio_metrics["monthly_budget_cny"],
    min_single_buy_cny=portfolio_metrics["min_single_buy_cny"],
    outlook_bullets=[
        ("宏观驱动", decision["macro_one_liner"]),
        ("短线 1–4周", decision["short_term_one_liner"]),
        ("长线 3–12月", decision["long_term_one_liner"]),
    ],
    price_radar=price_radar,
    action_steps=action_steps,
    committee_table_rows=committee_rows,
    risk_bullets=risk_bullets,
)

raw_payload = {
    "run_id": RUN_ID,
    "date": TODAY_STR,
    "portfolio": PORTFOLIO,
    "portfolio_metrics": portfolio_metrics,
    "intel": intel,
    "analysis": analysis,
    "round1_votes": round1_records,
    "round2_votes": round2_records,
    "tally": tally,
    "decision": decision,
}

vote_compact = ", ".join(f"{k}:{v}" for k, v in tally["vote_counts"].items())
short_amt = decision["recommended_amount_summary"].replace("\n", " ")[:80]
ledger_row = (
    f"| {RUN_ID} | {cny_price if cny_price is not None else 'N/A'} | {pnl_str} | "
    f"`{tally['final_action']}` | {short_amt} | {vote_compact} | [查看档案](runs/{RUN_ID}/04_decision.md) |\n"
)


def write_archive(target_run_dir: Path, update_ledger_path: Path | None, dispatch_path: Path | None):
    target_run_dir.mkdir(parents=True, exist_ok=True)
    (target_run_dir / "01_intel.md").write_text(md_intel, encoding="utf-8")
    (target_run_dir / "02_analysis.md").write_text(md_analysis, encoding="utf-8")
    (target_run_dir / "03_meeting.md").write_text(md_meeting, encoding="utf-8")
    (target_run_dir / "04_decision.md").write_text(md_decision, encoding="utf-8")
    (target_run_dir / "email.html").write_text(email_html, encoding="utf-8")
    (target_run_dir / "raw_result.json").write_text(
        json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if update_ledger_path is not None:
        if not update_ledger_path.exists():
            update_ledger_path.write_text(
                "# 黄金投资决策历史总台账（Decision Ledger）\n\n"
                "| 日期时间 | 参考国内金价 (RMB/克) | 持仓浮动盈亏 | 最终决议动作 | 建议金额 / 比例 | 投票分布 (终投) | 会议档案链接 |\n"
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
            "mode": "local_full",
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
    log(f"档案与 HTML 邮件已写入: {saved_dir}")
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
            "email_subject": email_subject,
            "email_html_path": str(saved_dir / "email.html"),
            "decision_md_path": str(saved_dir / "04_decision.md"),
            "cny_gold_price_per_gram": cny_price,
            "tally": tally,
            "decision_headline": decision["headline"],
            "recommended_amount_summary": decision["recommended_amount_summary"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
