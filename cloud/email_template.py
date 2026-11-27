"""
Plain-Chinese Institutional Morning Note HTML Renderer (v3 — 5-Specialist + 1-PM + 3-Bullet Quant)

Design principles:
  - 20-second scannable, ZERO finance jargon, ZERO personal holdings/avg cost/PnL/personal shot history
  - Highlights:
      * Top Banner + 3-Column KPI Strip (Domestic Gold Price | Composite Buy Score 0-100 | PM Final Action)
      * Plain-Chinese 1-sentence Takeaway Box ("💡 一句话看懂今天")
      * K-Line Price Thermometer + 3-Bullet Universal Trigger Ladder (第1颗≥65分 / 第2颗≥72分 / 第3颗≥80分)
      * 4 Non-Overlapping Plain-Language Price Cards (跌到这儿买 / 跌破这儿停买 / 短线赚点卖 / 长线大赚卖)
      * Steady vs Bold Dual-Track Reference ("🛡️ 稳健做法 vs 🔥 大胆做法")
      * 5 Independent Specialists' Sharpest 1-Line Signals & Scores
      * Top 3 Plain-Language Risks
"""

from __future__ import annotations

import html


def action_badge_style(action: str) -> tuple[str, str]:
    return {
        "BUY_SHOT": ("#0f766e", "触发买点 · 建议出手 1 笔 (1,200元)"),
        "BUY_PARTIAL": ("#0369a1", "建议逢低买 1 笔 (1,200元)"),
        "BUY_FULL": ("#0f766e", "强买点 · 建议果断出手"),
        "HOLD": ("#475569", "暂不扣扳机 · 留好子弹"),
        "TAKE_PROFIT_PARTIAL": ("#b45309", "偏贵过热 · 建议先卖出一笔落袋"),
        "REDUCE_HEAVY": ("#b91c1c", "风险偏高 · 建议减仓避险"),
    }.get(action, ("#334155", action))


def score_color(score: int | float) -> str:
    if score >= 75:
        return "#15803d"
    if score >= 65:
        return "#0369a1"
    if score <= 35:
        return "#b91c1c"
    return "#b45309"


def render_v3_morning_note(
    *,
    date_str: str,
    headline: str,
    plain_takeaway: str,
    action: str,
    recommended_amount_short: str,
    composite_score: int,
    score_zone_label: str,
    cny_price_str: str,
    xau_usd_short: str,
    kline_thermometer_text: str,
    shot_amount_cny: int = 1200,
    max_shots_per_month: int = 3,
    bullet_ladder: list[tuple[str, int, bool, str]],
    outlook_bullets: list[tuple[str, str]],
    price_radar: list[tuple[str, str, str, str]],
    steady_option: str,
    bold_option: str,
    specialist_rows: list[tuple[str, str, str]],
    risk_bullets: list[tuple[str, str]],
    footer_note: str = "",
) -> str:
    """
    Parameters:
      - bullet_ladder: [(shot_name, threshold, is_triggered, status_text), ...]
      - specialist_rows: [(role_name, score_badge, one_line_value_signal), ...] (5 rows)
    """
    esc = html.escape
    badge_bg, action_cn = action_badge_style(action)
    s_color = score_color(composite_score)

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

    footer_extra = f"<div>{esc(footer_note)}</div>" if footer_note else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:16px;background:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue','Microsoft YaHei',sans-serif;">
  <div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 20px rgba(15,23,42,0.10);">

    <!-- Header -->
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

    <!-- 3-Column KPI Strip -->
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

    <!-- Plain Takeaway -->
    <div style="margin:18px 24px 0;background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #d97706;border-radius:6px;padding:11px 14px;font-size:13.5px;color:#78350f;line-height:1.6;">
      <strong>💡 一句话看懂今天：</strong>{esc(plain_takeaway)}
    </div>

    <div style="padding:18px 24px 22px;">

      <!-- 01: 3-Bullet Quant Signal & K-Line Thermometer -->
      <div>
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
          01 ｜ 3 颗子弹算法触发灯（每月最多 {max_shots_per_month} 次 × {shot_amount_cny:,} 元）
        </div>
        <div style="font-size:12.5px;color:#334155;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:8px;line-height:1.5;">
          <strong>📊 K 线位置温度计：</strong>{esc(kline_thermometer_text)}
        </div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
          <tr>{ladder_cells}</tr>
        </table>
      </div>

      <!-- 02: Dual-Track Steady vs Bold -->
      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
          02 ｜ 稳健做法 vs 大胆做法（按自己性格选）
        </div>
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

      <!-- 03: 4 Price Zones -->
      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:10px;">
          03 ｜ 盯住这 4 个实用价格（单位：元 / 克）
        </div>
        <table style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>{radar_cells}</tr></table>
      </div>

      <!-- 04: Market Outlook -->
      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
          04 ｜ 现在黄金是什么行情？（人话版）
        </div>
        <table style="width:100%;border-collapse:collapse;"><tbody>{outlook_html}</tbody></table>
      </div>

      <!-- 05: 5 Specialists' Core Signals -->
      <div style="margin-top:18px;">
        <div style="font-size:13px;font-weight:800;color:#0f172a;border-bottom:2px solid #0f172a;padding-bottom:5px;margin-bottom:8px;">
          05 ｜ 5 位专业顾问各自最核心的 1 句话干货
        </div>
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

      <!-- 06: Risks -->
      <div style="margin-top:18px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 14px;">
        <div style="font-size:12.5px;font-weight:800;color:#991b1b;margin-bottom:6px;">06 ｜ 近期最需要注意的 3 个风险</div>
        <ul style="margin:0;padding-left:18px;">{r_items}</ul>
      </div>

      <div style="margin-top:18px;padding-top:12px;border-top:1px solid #e2e8f0;font-size:11.5px;color:#64748b;line-height:1.55;">
        {footer_extra}
        <div>免责声明：本晨报由多 Agent 量化投研系统自动整理，按「每月最多 {max_shots_per_month} 笔 × {shot_amount_cny:,} 元」通用算法模型测算，不含个人持仓或个人交易次数，仅供学习与决策参考，不构成持牌金融投资建议。</div>
      </div>
    </div>

  </div>
</body>
</html>
"""
