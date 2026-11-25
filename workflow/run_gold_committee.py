import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

# ==============================================================================
# Gold Investment Multi-Agent Decision Workflow
# Phases:
#   1. Parallel Information Collection (Market/FX, Macro/Policy, Geopolitics/Sentiment)
#   2. Parallel Multi-Dimensional Analysis (Policy/Macro, Short+Long Trend, Portfolio Math)
#   3. 2-Round Heterogeneous Investment Committee Voting & Debate (4 persistent agents)
#   4. Committee Secretary Synthesis & Archive Persistence
# ==============================================================================

BASE_DIR = Path(args.get("base_dir", "/Users/bytedance/Desktop/Investment/Gold"))
FALLBACK_ROOT = Path(
    args.get(
        "fallback_dir",
        "/Users/bytedance/.gemini/antigravity/brain/350233f9-1c03-48a6-b385-3eeb87f67010/scratch/gold_runs",
    )
)
TODAY_STR = args.get("date_str") or datetime.now().strftime("%Y-%m-%d")
RUN_ID = args.get("run_id") or datetime.now().strftime("%Y-%m-%d_%H%M")
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
    "BUY_FULL": "全额买入（动用本月全部或绝大部分 3,000 元预算，可分笔执行）",
    "BUY_PARTIAL": "分批/部分买入（动用部分月度预算，保留弹药防回调）",
    "HOLD": "维持观望（本月暂不新增仓位，也暂不减仓，等待触发价位）",
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
# Helper: Quantitative Portfolio Math
# ------------------------------------------------------------------------------

def compute_portfolio_metrics(portfolio: dict, current_price_cny: float | None) -> dict:
    pos = portfolio["position"]
    principal = float(pos["principal_cny"])
    avg_cost = float(pos["average_cost_cny_per_gram"])
    grams = principal / avg_cost
    budget = float(portfolio["monthly_disposable_budget_cny"])

    metrics = {
        "principal_cny": round(principal, 2),
        "average_cost_cny_per_gram": round(avg_cost, 2),
        "estimated_grams": round(grams, 4),
        "monthly_budget_cny": round(budget, 2),
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
        for add_amt in (1000, 1500, 2000, 3000):
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
            rem_g = grams - sold_g
            rem_principal = principal - cost_part
            metrics["trim_scenarios"][f"trim_{trim_pct}_pct"] = {
                "sold_grams": round(sold_g, 4),
                "cash_proceeds_cny": round(proceeds, 2),
                "realized_pnl_cny": round(realized_pnl, 2),
                "remaining_grams": round(rem_g, 4),
                "remaining_principal_cny": round(rem_principal, 2),
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

    resolution_rule = "多数票通过"
    final_action = top_action

    # Tie or high dispersion handling
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
                else "分批买与观望平票且无风控一票否决，采用小额分批定投"
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
        # 2-1-1 plurality
        if has_buy and has_sell and top_action in {"BUY_FULL", "REDUCE_HEAVY"}:
            final_action = "BUY_PARTIAL" if top_action == "BUY_FULL" else "TAKE_PROFIT_PARTIAL"
            resolution_rule = "2-1-1 相对多数但存在反向异议，幅度降档执行"
        else:
            final_action = top_action
            resolution_rule = f"相对多数通过（{top_count}/4 票）"

    # Risk officer veto cap on aggressive full buy
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
你是【实时行情与汇率采集员】。今天是 {TODAY_STR}。
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
请使用 search_web 搜索近期（过去2-4周及最新动态）影响黄金定价的宏观经济与央行政策新闻：
1. 美联储（Fed）最新利率决议、官员表态、市场对未来降息/加息路径的预期；
2. 美国最新通胀（CPI/PCE）、就业（非农）及经济数据；
3. 中国央行（PBOC）及全球央行最新黄金储备增持/暂停动态；
4. 重要财政政策、赤字、关税贸易政策或汇率政策新闻；
5. 未来2-4周即将公布的关键宏观日历事件（如 FOMC、CPI、非农等）。

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
1. 近期重大地缘政治局势与避险催化（中东、俄乌、大国博弈或其他突发风险事件）；
2. 全球黄金 ETF（如 SPDR Gold Shares / GLD）及中国国内黄金 ETF 资金流入/流出情况；
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
intel = {
    collector_specs[i]["key"]: collector_results_list[i]
    for i in range(len(collector_specs))
}

cny_price = intel["market"].get("cny_gold_price_per_gram")
portfolio_metrics = compute_portfolio_metrics(PORTFOLIO, cny_price)
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
        "schema": POLICY_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【政策与宏观基本面分析师】。今天是 {TODAY_STR}。
请严格基于下方 Phase 1 采集到的最新客观情报，进行深度政策与宏观基本面拆解：
1. 判断当前黄金所处的宏观定价范式（实际利率驱动、央行去美元化驱动、滞胀/赤字驱动还是避险溢价驱动）；
2. 分别列举最核心的利多驱动（bullish_drivers）与利空压制/风险点（bearish_drivers）；
3. 区分哪些消息是“短期情绪噪音”，哪些是“中期决定方向的真主线”；
4. 给出整体基本面偏向判断，并撰写结构清晰的分析正文（analysis_markdown，中文）。

【Phase 1 客观情报包】
{intel_bundle_json}
""",
    },
    {
        "key": "trend",
        "role": "短线波段与长线趋势分析师",
        "schema": TREND_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【短线波段与长线趋势分析师】。今天是 {TODAY_STR}。
用户明确表示：**同时接受短线波段操作与长线配置，且允许止盈减仓**。
请严格基于下方客观情报，同时从“短线（1–4周）”和“长线（3–12个月）”两个维度分析金价走向：
1. 短线视角：判断当前是主升延续、高位震荡、超买回调风险还是下行趋势；给出国内人民币金价（RMB/克）的关键支撑区间与阻力/止盈参考区间；
2. 长线视角：判断中长期大趋势结构是否完好，给出乐观/中性/悲观三种情景的定性与大致概率分布；
3. 撰写清晰的走向分析正文（analysis_markdown，中文）。

【Phase 1 客观情报包】
{intel_bundle_json}
""",
    },
    {
        "key": "portfolio",
        "role": "个人持仓与仓位管理分析师",
        "schema": PORTFOLIO_ANALYSIS_SCHEMA,
        "prompt": f"""{ISOLATION_GUARD}
你是【个人持仓与仓位管理分析师】。今天是 {TODAY_STR}。
请结合用户的真实账户配置、已算好的定量指标和最新行情，做严谨的资金管理与仓位评估：
1. 评估用户当前持仓（本金 7,500 RMB，均价 850 RMB/克，约 8.8235 克）相对现价的健康度与安全垫（盈亏状态）；
2. 对比不同买入方案（1,000 / 1,500 / 2,000 / 3,000 RMB）对拉高或拉低持仓均价、仓位集中度的影响；
3. 对比不同止盈/减仓方案（减仓 20% / 30% / 50%）的落袋收益与剩余底仓保护效果；
4. 提出适合“月度 3,000 元现金流 + 短长线结合”的仓位风控护栏（risk_guardrails）；
5. 撰写包含清晰表格的中文分析正文（analysis_markdown）。

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
    lambda s: agent(s["prompt"], schema=s["schema"], role=s["role"], model="inherit"),
)
analysis = {
    analyst_specs[i]["key"]: analyst_results_list[i]
    for i in range(len(analyst_specs))
}
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
        "policy_analysis": {
            k: v for k, v in analysis["policy"].items() if k != "analysis_markdown"
        },
        "trend_analysis": {
            k: v for k, v in analysis["trend"].items() if k != "analysis_markdown"
        },
        "portfolio_analysis": {
            k: v for k, v in analysis["portfolio"].items() if k != "analysis_markdown"
        },
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
你的核心投资哲学：重视动量、波段赔率、事件催化与右侧顺势；价格处于强支撑或突破初期敢于出击，处于短期超买/阻力位或利多兑现期敢于主张短线部分止盈（TAKE_PROFIT_PARTIAL）。
请坚守你的角色视角，不要迎合他人。""",
    },
    {
        "id": "long_term",
        "name": "委员B · 长线配置委员",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员B · 长线配置委员】。
你的核心投资哲学：重视 6 个月至数年维度的宏观大周期、央行购金底盘、信用货币对冲与纪律性分批积累；厌恶频繁追涨杀跌，但当长线估值明显透支或逻辑破坏时也认可适度再平衡。
请坚守你的角色视角，不要迎合他人。""",
    },
    {
        "id": "risk_redteam",
        "name": "委员C · 逆向风控委员 (Red Team)",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员C · 逆向风控委员（红军/挑刺者）】。
你的职责是专门审视市场盲点、多头拥挤度、汇率反向波动、短期回调回撤和重大数据公布前的事件风险。
你拥有风险预警权（risk_veto）：只有当你认为当前存在显著追高/大幅回撤/高危事件风险、绝不适合全额激进买入时，才将 risk_veto 设为 true 并给出充分依据；若风险可控则设为 false。""",
    },
    {
        "id": "portfolio_cfo",
        "name": "委员D · 个人财务与仓位官",
        "standing": f"""{ISOLATION_GUARD}
你是黄金投委会【委员D · 个人财务与仓位官】。
你只忠于用户的真实财务约束：现有持仓本金 7,500 RMB（均价 850 RMB/克），月度可支配预算 3,000 RMB，用户同时接受短线与长线以及止盈减仓。
你重点权衡：加仓对成本均价的抬升/摊薄效应、现金留存弹性、已有浮盈是否需要锁定部分利润、分批执行的纪律性。""",
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
请仔细阅读以下完整投研简报，独立给出你的判断与投票（可选动作：{ALLOWED_ACTIONS}）：
- BUY_FULL: 当月预算全额买入（最高 3,000 元，可分笔）
- BUY_PARTIAL: 当月预算部分买入（如 1,000-2,000 元），留现金等回调
- HOLD: 观望，不动用本月预算也不减仓
- TAKE_PROFIT_PARTIAL: 部分止盈/减仓（如减持 20%-40% 仓位锁定利润）
- REDUCE_HEAVY: 大幅减仓防守（如减持 50%+）

同时请提出 1 个你最想在下一轮质询其他委员的核心问题（question_for_committee）。

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
以下是全部 4 位委员（包括你自己：{member_name}）在 Round 1 的独立意见和相互质询问题：

{round1_summary_for_debate}

请认真审视其他委员的论点与质疑（特别是与你相反的立场以及逆向风控委员指出的风险）：
1. 在 response_to_peers 中直接回应与你意见分歧最大的委员或回答他们提出的问题；
2. 冷静评估是否需要维持原票或修正立场（changed_mind）；
3. 投出你的最终正式票（action）、具体金额/减仓比例建议（recommended_amount_desc）、明确的价格/事件触发条件（trigger_conditions）以及总结陈词（final_statement）。
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
你是【黄金投委会会议秘书】。今天是 {TODAY_STR}。
请基于本次会议的客观行情、持仓测算、两轮投票讨论记录以及最终计票决议，生成一份清晰、可直接执行、风格克制专业的一页纸【最终投资决策单】。

要求：
1. 严格尊重最终计票决议（{tally['final_action']} - {tally['final_action_label']}）与决议规则说明（{tally['resolution_rule']}）；
2. 同时明确给出「短线操作建议（1-4周）」与「长线配置建议（3-12个月）」；
3. 明确列出具体金额/克数建议、逢低加仓触发价位（RMB/克）、逢高止盈触发价位（RMB/克）以及前 3 大核心风险；
4. decision_markdown 用规范中文 Markdown 撰写，文末注明“本报告为多 Agent 投研辅助记录，不构成持牌金融投资建议”。

【持仓与测算】
{portfolio_metrics_json}

【最终计票与规则裁定】
{json.dumps(tally, ensure_ascii=False, indent=2)}

【两轮投票记录】
Round 1:
{json.dumps(round1_records, ensure_ascii=False, indent=2)}

Round 2:
{json.dumps(round2_records, ensure_ascii=False, indent=2)}
"""

decision = await agent(
    secretary_prompt,
    schema=DECISION_SYNTHESIS_SCHEMA,
    role="投委会会议秘书",
    model="inherit",
)

# ------------------------------------------------------------------------------
# Render 4 Structured Markdown Archive Documents
# ------------------------------------------------------------------------------

def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "- （未提供额外来源）"
    lines = []
    for s in sources:
        lines.append(f"- **{s['title']}**（{s['source']}，{s['date']}）：{s['key_fact']}")
    return "\n".join(lines)


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
- **情景概率概览**：{analysis['trend']['scenario_summary']}

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

r1_blocks = []
for r in round1_records:
    v = r["vote"]
    r1_blocks.append(
        f"### {r['name']}\n"
        f"- **初投动作**：`{v['action']}`（{v['recommended_amount_desc']}） | **信心分**：{v['confidence_1_to_10']}/10 | **风控预警**：`{v['risk_veto']}`\n"
        f"- **短线观点**：{v['short_term_stance']}\n"
        f"- **长线观点**：{v['long_term_stance']}\n"
        f"- **核心论据**：{v['core_rationale']}\n"
        f"- **风控预警说明**：{v['risk_veto_reason']}\n"
        f"- **向委员会提出的质询问题**：{v['question_for_committee']}\n"
    )

r2_blocks = []
for r in round2_records:
    v = r["vote"]
    r2_blocks.append(
        f"### {r['name']}\n"
        f"- **最终投票**：`{v['action']}`（{v['recommended_amount_desc']}） | **是否改票**：`{v['changed_mind']}` | **信心分**：{v['confidence_1_to_10']}/10 | **风控预警**：`{v['risk_veto']}`\n"
        f"- **回应质疑与交锋**：{v['response_to_peers']}\n"
        f"- **触发条件**：{v['trigger_conditions']}\n"
        f"- **终投陈词**：{v['final_statement']}\n"
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

{"".join(r1_blocks)}

---

## 第二轮：交叉质询、辩论与最终表决

{"".join(r2_blocks)}
"""

md_decision = f"""# 04 最终投资决策单（{RUN_ID}）

> **{decision['headline']}**

| 决议维度 | 内容 |
| --- | --- |
| 最终动作 | `{tally['final_action']}`（{tally['final_action_label']}） |
| 建议金额 / 比例 | {decision['recommended_amount_summary']} |
| 当前参考国内金价 | {cny_price if cny_price is not None else '待核实'} RMB/克 |
| 当前持仓状态 | 本金 {portfolio_metrics['principal_cny']} RMB / 均价 {portfolio_metrics['average_cost_cny_per_gram']} RMB/克 / 浮动盈亏 {portfolio_metrics.get('unrealized_pnl_cny', 'N/A')} RMB ({portfolio_metrics.get('unrealized_pnl_pct', 'N/A')}%) |
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

# ------------------------------------------------------------------------------
# Persist Files (Primary: BASE_DIR, Fallback: FALLBACK_ROOT if sandbox blocks)
# ------------------------------------------------------------------------------

pnl_str = (
    f"{portfolio_metrics['unrealized_pnl_cny']:+.0f} RMB ({portfolio_metrics['unrealized_pnl_pct']:+.2f}%)"
    if "unrealized_pnl_cny" in portfolio_metrics
    else "N/A"
)
vote_compact = ", ".join(f"{k}:{v}" for k, v in tally["vote_counts"].items())
ledger_row = (
    f"| {RUN_ID} | {cny_price if cny_price is not None else 'N/A'} | {pnl_str} | "
    f"`{tally['final_action']}` | {decision['recommended_amount_summary']} | "
    f"{vote_compact} | [查看档案](file://{BASE_DIR}/records/runs/{RUN_ID}/04_decision.md) |\n"
)

def write_archive(target_run_dir: Path, update_ledger_path: Path | None):
    target_run_dir.mkdir(parents=True, exist_ok=True)
    (target_run_dir / "01_intel.md").write_text(md_intel, encoding="utf-8")
    (target_run_dir / "02_analysis.md").write_text(md_analysis, encoding="utf-8")
    (target_run_dir / "03_meeting.md").write_text(md_meeting, encoding="utf-8")
    (target_run_dir / "04_decision.md").write_text(md_decision, encoding="utf-8")
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

saved_mode = "primary"
saved_dir = BASE_DIR / "records" / "runs" / RUN_ID
try:
    write_archive(saved_dir, BASE_DIR / "records" / "ledger.md")
    log(f"档案已直接写入目标目录: {saved_dir}")
except PermissionError:
    saved_mode = "fallback"
    saved_dir = FALLBACK_ROOT / RUN_ID
    write_archive(saved_dir, None)
    (saved_dir / "ledger_row.txt").write_text(ledger_row, encoding="utf-8")
    log(f"主目录受沙箱限制，档案已写入暂存目录: {saved_dir}")

print(
    json.dumps(
        {
            "run_id": RUN_ID,
            "saved_mode": saved_mode,
            "saved_dir": str(saved_dir),
            "cny_gold_price_per_gram": cny_price,
            "portfolio_metrics": portfolio_metrics,
            "tally": tally,
            "decision_headline": decision["headline"],
            "recommended_amount_summary": decision["recommended_amount_summary"],
            "short_term_plan": decision["short_term_plan"],
            "long_term_plan": decision["long_term_plan"],
            "dip_buy_triggers": decision["dip_buy_triggers"],
            "take_profit_triggers": decision["take_profit_triggers"],
            "top_risks": decision["top_risks"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
