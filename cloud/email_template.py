"""
Institutional Morning Note HTML Email Renderer (Investment-Bank Style)

Design principles (inspired by GS / UBS / MS Morning Research Notes):
  - BLUF (Bottom Line Up Front): 3-second scannable top KPI bar
  - Strictly privacy-safe: NEVER renders personal holdings, avg cost, grams, or PnL
  - Compact density: short bullet lines, 4-card price radar, 3-item action checklist,
    1-line committee vote summary, and 3 tagged risk bullets.
  - Responsive inline CSS compatible with QQ Mail, Gmail, Apple Mail (mobile + desktop).
"""

from __future__ import annotations

import html


def action_badge_style(action: str) -> tuple[str, str]:
    """Return (bg_color, short_cn_label) for a decision action."""
    return {
        "BUY_FULL": ("#0f766e", "全额分批买入"),
        "BUY_PARTIAL": ("#0369a1", "逢低分批买入"),
        "HOLD": ("#475569", "维持观望"),
        "TAKE_PROFIT_PARTIAL": ("#b45309", "部分止盈减仓"),
        "REDUCE_HEAVY": ("#b91c1c", "防守减仓"),
    }.get(action, ("#334155", action))


def render_institutional_morning_note(
    *,
    date_str: str,
    headline: str,
    action: str,
    recommended_amount_short: str,
    consensus_text: str,
    cny_price_str: str,
    xau_usd_short: str,
    monthly_budget_cny: int = 3000,
    min_single_buy_cny: int = 1200,
    outlook_bullets: list[tuple[str, str]],
    price_radar: list[tuple[str, str, str, str]],
    action_steps: list[tuple[str, str]],
    committee_rows: list[tuple[str, str, str, str]] | None = None,
    risk_bullets: list[tuple[str, str]] | None = None,
    footer_note: str = "",
) -> str:
    """
    Parameters:
      - outlook_bullets: [(tag, short_sentence), ...] (3 items: 宏观驱动 / 短线走向 / 长线走向)
      - price_radar: [(label, price_range, sub_note, accent_hex), ...] (4 cards)
      - action_steps: [(step_label, short_instruction), ...] (3 crisp items)
      - committee_rows: [(member_short_name, action_code, confidence_str, one_line_logic), ...]
      - risk_bullets: [(risk_tag, one_line_desc), ...] (3 crisp items)
    """
    esc = html.escape
    badge_bg, action_cn = action_badge_style(action)

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

    committee_section = ""
    if committee_rows:
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
            for name, vote, conf, logic in committee_rows
        )
        committee_section = f"""
        <div style="margin-top:20px;">
          <div style="font-size:13px;font-weight:800;letter-spacing:0.5px;color:#0f172a;text-transform:uppercase;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
            04 ｜ 投委会表决矩阵
          </div>
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
        """

    risks_section = ""
    if risk_bullets:
        r_items = "".join(
            f"""
            <li style="margin-bottom:6px;font-size:13px;color:#334155;line-height:1.5;">
              <strong style="color:#b91c1c;">[{esc(tag)}]</strong> {esc(desc)}
            </li>
            """
            for tag, desc in risk_bullets
        )
        risks_section = f"""
        <div style="margin-top:20px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 14px;">
          <div style="font-size:12.5px;font-weight:800;color:#991b1b;margin-bottom:6px;">05 ｜ 关键风险提示</div>
          <ul style="margin:0;padding-left:18px;">{r_items}</ul>
        </div>
        """

    footer_extra = f"<div>{esc(footer_note)}</div>" if footer_note else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:16px;background:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue','Microsoft YaHei',sans-serif;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.10);">

    <!-- Institutional Header Banner -->
    <div style="background:#0f172a;padding:20px 24px 18px;border-bottom:3px solid #d97706;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="font-size:11px;letter-spacing:1.4px;color:#f59e0b;font-weight:700;">
            GOLD RESEARCH · MORNING BRIEFING
          </td>
          <td style="text-align:right;font-size:12px;color:#94a3b8;">
            {esc(date_str)} · 盘前晨报
          </td>
        </tr>
      </table>
      <h1 style="margin:10px 0 12px;font-size:19px;line-height:1.4;color:#ffffff;font-weight:700;">
        {esc(headline)}
      </h1>
      <div>
        <span style="display:inline-block;padding:4px 11px;border-radius:4px;background:{badge_bg};color:#ffffff;font-size:12px;font-weight:700;letter-spacing:0.4px;">
          {esc(action)} · {esc(action_cn)}
        </span>
        <span style="display:inline-block;margin-left:8px;font-size:12px;color:#cbd5e1;">
          {esc(consensus_text)}
        </span>
      </div>
    </div>

    <!-- 3-Column KPI Summary Strip (BLUF) -->
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
            <div style="font-size:11px;color:#64748b;margin-top:2px;">按月度 {monthly_budget_cny:,} 元定投模型</div>
          </td>
          <td style="width:30%;padding-left:12px;vertical-align:top;">
            <div style="font-size:11px;color:#64748b;font-weight:600;">定投纪律参数</div>
            <div style="font-size:15px;font-weight:700;color:#0f172a;margin-top:5px;">月预算 {monthly_budget_cny:,} 元</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;">单笔起投 ≥ {min_single_buy_cny:,} 元</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Main Body -->
    <div style="padding:20px 24px 22px;">

      <!-- Section 01: Market Outlook -->
      <div>
        <div style="font-size:13px;font-weight:800;letter-spacing:0.5px;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
          01 ｜ 形势与走向速览
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <tbody>{outlook_html}</tbody>
        </table>
      </div>

      <!-- Section 02: Key Price Radar -->
      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;letter-spacing:0.5px;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:10px;">
          02 ｜ 关键价位雷达（RMB / 克）
        </div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
          <tr>{radar_cells}</tr>
        </table>
      </div>

      <!-- Section 03: Action Plan -->
      <div style="margin-top:20px;">
        <div style="font-size:13px;font-weight:800;letter-spacing:0.5px;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:6px;">
          03 ｜ 今日执行清单（月预算 {monthly_budget_cny:,} 元模型）
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <tbody>{actions_html}</tbody>
        </table>
      </div>

      {committee_section}
      {risks_section}

      <!-- Footer -->
      <div style="margin-top:20px;padding-top:12px;border-top:1px solid #e2e8f0;font-size:11.5px;color:#64748b;line-height:1.55;">
        {footer_extra}
        <div>免责声明：本晨报由多 Agent 投研系统自动生成，统一基于「月度 {monthly_budget_cny:,} 元 / 单笔起投 {min_single_buy_cny:,} 元」标准模型测算，不含个人持仓信息，仅供投研参考，不构成持牌金融投资建议。</div>
      </div>
    </div>

  </div>
</body>
</html>
"""
