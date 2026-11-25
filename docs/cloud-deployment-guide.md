# 黄金投委会云端自动化部署指南（方案 A：GitHub Actions + Gemini 4）

> 电脑完全关机、合盖休眠也照常在云端运行：**每个交易日 06:00 计算归档 → 08:00:00 准点发送 HTML 邮件至 `3518109978@qq.com`**。

---

## 一、开盘时间与 06:00 / 08:00 两阶段设计说明

- **国内黄金市场核心交易时段（北京时间）**：
  - 上海黄金交易所（AU9999 / 沪金期货）：日盘 **09:00–11:30、13:30–15:30**；夜盘 **20:00–次日 02:30**。
  - 国内黄金 ETF（如 518880）：**09:30–11:30、13:00–15:00**。
  - 美盘收盘及美国重磅宏观数据（PCE / CPI / 非农 / FOMC）：均在北京时间 **凌晨 02:00–05:00** 全部落地。
- **为什么 06:00 计算 + 08:00 发邮件是黄金节奏**：
  1. **06:00 计算（`gold_0600_compute.yml`）**：隔夜美盘与重磅数据刚尘埃落定，计算完直接把档案提交进你的私有仓库，留足 2 小时容错空间。
  2. **07:45 启动 → 08:00:00 精准发信（`gold_0800_send_email.yml`）**：提前 15 分钟启动以消除 GitHub Actions 免费队列的几分钟抖动，脚本内部精准等待到 **08:00:00 北京时间**立即投递至 `3518109978@qq.com`（若 06:00 偶发失败，还会自动兜底重算或发告警邮件）。

---

## 二、Gemini 4 分级模型配置（`config/models.json`）

当前系统使用官方 `google-genai >= 3.5.0` 的 **Interactions API** + 原生 **Google Search Grounding**，各 Agent 模型分配均可在 `config/models.json` 一键修改：

| 角色 | 默认模型 | 说明 |
| :--- | :--- | :--- |
| Phase 1：3 位联网信息采集员 | `gemini-4-hydrogen` | 快速均衡 + 原生 Google Search，检索提取性价比最高 |
| 盘前哨兵 Agent | `gemini-4-hydrogen` | 日常轻量检查是否触发异动/价位/重大事件 |
| Phase 2：政策宏观 & 短长线趋势分析师 | `gemini-4-neon` | 旗舰智能 + 端到端快速推理，把控核心投研逻辑 |
| Phase 2：个人持仓与仓位分析师 | `gemini-4-hydrogen` | 解读 Python 精确算好的加减仓表格 |
| Phase 3：逆向风控委员（Red Team） | `gemini-4-carbon` | 最强深度推理，专门挑漏洞与防极端回撤 |
| Phase 3：趋势波段委员 | `gemini-4-neon` | 敏锐捕捉动量与波段赔率 |
| Phase 3：长线配置委员 & 个人财务官 | `gemini-4-argon` | 高效前沿推理，适合高频生产循环与纪律核算 |
| Phase 4：投委会会议秘书 | `gemini-4-hydrogen` | 汇总排版决策单与 HTML 邮件 |

> 默认启用 `smart_two_tier`（日常轻量盯盘，遇 **每周一 / 每月 1 日与 15 日 / 隔夜涨跌 ≥ 1.5% / 触及预设加仓止盈位 / 重大宏观地缘事件** 时自动升级为 4 委员两轮完整投委会）。如果你想**每天都开完整投委会**，只需把 `config/models.json` 中的 `"mode"` 改为 `"always_full"`。

---

## 三、5 分钟完成云端部署（一次性配置）

### 第 1 步：把本地目录推送到你的私有仓库 `hai-bd/Google_Scheduled_Task`
在终端执行以下命令（已替换为你建好的仓库地址）：
```bash
cd /Users/bytedance/Desktop/Investment/Gold
git init -b main
git add .
git commit -m "feat: initialize cloud gold investment multi-agent workflow"
git remote add origin https://github.com/hai-bd/Google_Scheduled_Task.git
git push -u origin main
```

### 第 2 步：在 GitHub 仓库配置秘钥（Secrets）
直接打开你的仓库秘钥配置页：
https://github.com/hai-bd/Google_Scheduled_Task/settings/secrets/actions

点击右上角绿色按钮 **New repository secret**，按下面逐条添加：

| Secret 名称 | 必填 | 填写说明 |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | 必填 | 打开 https://aistudio.google.com/apikey → 登录 Google → 点 **Create API key** → 复制 `AIza...` |
| `SMTP_USER` | 必填 | 发件邮箱（QQ 邮箱填 `3518109978@qq.com`；Gmail 填 `hushihai321@gmail.com`） |
| `SMTP_PASSWORD` | 必填 | **16 位 SMTP 授权码 / 应用专用密码**（不是邮箱登录密码！见下方获取步骤） |
| `SMTP_HOST` | 选填 | 用 QQ 邮箱发信**必填** `smtp.qq.com`；用 Gmail 发信可不填（默认 `smtp.gmail.com`） |
| `SMTP_PORT` | 选填 | 默认 `465`（QQ 与 Gmail 均适用，可不填） |
| `EMAIL_TO` | 选填 | 默认已设为 `3518109978@qq.com`，可不填 |

**获取 `SMTP_PASSWORD`（任选一种）**：
- **推荐方式一（QQ 邮箱自发自收，最省事）**：
  1. 网页登录 https://mail.qq.com → 顶部点 **设置** → **账号**（或收发信设置）。
  2. 下滑找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务** → 开启 **POP3/SMTP 服务** → 点击 **生成授权码**。
  3. 按页面提示扫码/短信验证，复制弹出的 **16 位授权码（去掉空格）** → 填入 `SMTP_PASSWORD`，并同时添加 `SMTP_HOST`=`smtp.qq.com`、`SMTP_USER`=`3518109978@qq.com`。
- **方式二（用 Gmail 发到 QQ 邮箱）**：
  1. 先确认 Google 账号已开启两步验证：https://myaccount.google.com/signinoptions/two-step-verification
  2. 打开应用专用密码页：https://myaccount.google.com/apppasswords → 应用名填 `GoldWorkflow` → 点 **创建** → 复制 **16 位密码（去掉空格）** → 填入 `SMTP_PASSWORD`，并添加 `SMTP_USER`=`hushihai321@gmail.com`。

### 第 3 步：在 Actions 页面一键手动测试全流程
（注意：必须先完成第 1 步 `git push` 后，Actions 左侧才会出现这两个任务！）
1. 打开你的仓库 Actions 页面：https://github.com/hai-bd/Google_Scheduled_Task/actions
2. **先测算报告**：
   - 在左侧列表点击 **`Gold 06:00 Pre-Market Compute`**。
   - 在右侧灰蓝色提示条上点击 **`Run workflow`** 下拉按钮 → 保持勾选 `force_full` → 点击绿色 **`Run workflow`**。
   - 等待约 1–2 分钟，列表里黄色转圈变成绿色对勾 ✅ 即计算成功。
3. **再测发邮件**：
   - 在左侧列表点击 **`Gold 08:00 Exact Email Dispatch`**。
   - 点击右侧 **`Run workflow`** → 保持勾选 `no_wait`（立即发送）→ 点击绿色 **`Run workflow`**。
   - 等待约 30 秒变绿对勾 ✅ 后，检查 `3518109978@qq.com` 收件箱即可！

---

## 四、日常维护：调仓后如何更新持仓？

每次你实盘买入或止盈后，只需更新仓库里的 `config/portfolio.json`（直接在 GitHub 网页或手机 App 点编辑保存，或本地修改后 `git push`）：
- 更新 `principal_cny`（最新总本金）
- 更新 `average_cost_cny_per_gram`（最新持仓均价）
- 按需调整 `config/models.json` 里的 `watch_price_levels_cny_g`（最新加仓/止盈盯盘价位）

次日早上 06:00 云端计算就会自动按你的最新仓位重新测算并在 08:00 准时发信！
