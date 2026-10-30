# Glados自动签到

> 基于 GitHub Actions 的 GLaDOS 自动签到工具，支持多账号与多通道推送（PushDeer / Server酱 / Telegram / 飞书 / 钉钉 / 企业微信 / PushPlus / 云湖机器人）。

## 文件结构

```shell
│  checkin.py          # 签到主脚本
│  logging_config.py   # 日志配置（北京时间、[I/W/E] 短标签）
│  requirements.txt    # Python 依赖
│
├─.github
│  └─workflows
│          gladosCheck.yml   # Actions 配置文件
```

## 食用方式

### 注册 GLaDOS 账号

注册地址：<https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG>

- 我的邀请码：[`0A58E-NV28S-6U3QV-33VMG`](https://0a58e-nv28s-6u3qv-33vmg.glados.space)
- 我的优惠码（9 折）：[`DEVILSTORE`](https://0a58e-nv28s-6u3qv-33vmg.glados.space)

### Fork 本仓库

![图片加载失败](imgs/1.png)

### 配置 Secrets

跳转至自己仓库的 `Settings` → `Secrets and variables` → `Action`，按需添加以下 `repository secret`：

#### 3.1 GLADOS_COOKIES（必填）

对应 GLaDOS 账号 Cookie 中的有效部分，获取方式：

- 在 GLaDOS 签到页面按 `F12`，切换到 `Network` 页面下，刷新
- 点击第一个请求，在 `Request Headers` 下找到 `Cookie`，右键复制其值即可

  > 参考格式：`koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;`

- 多账号请在 `GLADOS_COOKIES` 中添加多个 Cookie，支持 `&`、`|||` 或换行分隔，也可以混合使用。空行、连续分隔符和每项首尾空白会被忽略；Cookie 内部的分号保持不变。以下三种写法等效：

  ```text
  c1&c2&c3
  ```

  ```text
  c1|||c2|||c3
  ```

  ```text
  c1
  c2
  c3
  ```

![图片加载失败](imgs/2.png)
![图片加载失败](imgs/3.png)

#### 3.2 GLADOS_EXCHANGE_PLAN（非必填）

配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 |

> 不配置时默认不进行自动兑换；如需兑换，设置 `GLADOS_EXCHANGE_PLAN` 为 `plan100` / `plan200` / `plan500`。

#### 3.3 手机推送（非必填）

以下名称均为 `Settings` → `Secrets and variables` → `Actions` 下的 repository secrets。只配置需要的渠道即可，支持同时配置多个，所有已配置渠道都会发送。

| 渠道 | 必填 Secrets | 可选 Secrets |
|---|---|---|
| PushDeer | `PUSHDEER_SENDKEY`（[获取 Key](https://www.pushdeer.com/product.html)） | 无 |
| Server酱 | `SERVERCHAN_SENDKEY`（[获取 SendKey](https://sct.ftqq.com/)） | 无 |
| Telegram | `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` | 无 |
| 飞书应用机器人（单聊） | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_RECEIVE_ID` | `FEISHU_RECEIVE_ID_TYPE`（默认 `open_id`） |
| 钉钉应用机器人（单聊） | `DINGTALK_APP_KEY`、`DINGTALK_APP_SECRET`、`DINGTALK_ROBOT_CODE`、`DINGTALK_USER_ID` | 无 |
| 企业微信自建应用（指定成员） | `WECOM_CORP_ID`、`WECOM_CORP_SECRET`、`WECOM_AGENT_ID`、`WECOM_TO_USER` | 无 |
| 飞书机器人（Webhook） | `FEISHU_WEBHOOK`（完整 Webhook URL） | `FEISHU_SECRET`（开启签名校验时必填） |
| 钉钉机器人（Webhook） | `DINGTALK_WEBHOOK`（完整 Webhook URL，含 access_token） | `DINGTALK_SECRET`（开启加签时必填） |
| 企业微信机器人（Webhook） | `WECOM_WEBHOOK`（完整 Webhook URL，含 key） | 无 |
| PushPlus（推送加） | `PUSHPLUS_TOKEN`（[获取 Token](https://www.pushplus.plus/)） | 无 |
| 云湖机器人 | `YUNHU_BOT_TOKEN`、`YUNHU_RECV_ID` | `YUNHU_RECV_TYPE`（默认 `user`） |

- **Telegram**：通过 BotFather 创建机器人获取 Token；先向机器人发送 `/start`，使用目标会话的 Chat ID。可通过官方 `getUpdates` 接口查看会话 ID，不要将 Token 发给第三方。两个 Secrets 必须同时配置。
- **飞书应用机器人**：在飞书开发者后台创建企业自建应用，启用机器人，开通「以应用的身份发消息」权限（`im:message:send_as_bot`），发布应用并确保接收用户在可用范围内。填写应用的 App ID、App Secret 和接收用户的 Open ID，即可单聊接收。若使用其他 ID，将 `FEISHU_RECEIVE_ID_TYPE` 设为匹配的 `user_id` / `union_id` / `email` / `chat_id`；使用 User ID 还需相应权限。
- **钉钉应用机器人**：在钉钉开发者后台创建企业内部应用并启用机器人，开通「企业内机器人发送消息权限」并发布。填写 AppKey（Client ID）、AppSecret（Client Secret）、机器人 RobotCode 和接收成员的 User ID；确保接收成员在应用可见范围内，并先打开机器人单聊会话。
- **企业微信自建应用**：在管理后台创建应用，填写企业 ID、应用 Secret、数字 AgentId 和接收成员 UserID（多成员用 `|` 分隔）。接收成员需在应用可见范围内，并按平台要求配置企业可信 IP；GitHub 托管运行器的出口 IP 可能变动，此场景可使用具有固定出口 IP 的自托管运行器。这是应用消息接入方式。
- **飞书 / 钉钉 / 企业微信 Webhook 机器人**：创建自定义机器人并复制 Webhook。飞书和钉钉启用签名校验时，另填对应 Secret。使用关键词校验时可设置关键词 `GLaDOS`；若同时启用 IP 白名单，还需确保运行环境符合白名单要求。原有 Webhook 配置继续有效；同一平台同时配置应用和 Webhook 时，两种方式都会发送。
- **PushPlus**：登录推送加获取 Token，配置 `PUSHPLUS_TOKEN`，默认向自己发送，使用 `txt` 纯文本模板保留邮箱星号和换行。接口返回成功表示消息已提交，实际投递结果以平台记录为准。
- **云湖机器人**：创建机器人获取 Token，关注机器人，配置接收用户 ID 到 `YUNHU_RECV_ID`，默认 `YUNHU_RECV_TYPE=user`。发送到其他目标会话时可设为 `group`，并填入对应会话 ID，机器人需已加入该会话。
- Telegram、飞书、钉钉、企业微信、云湖使用纯文本，保留邮箱中的 `***` 和换行；多账号消息过长会自动分片。接口的 HTTP 状态及业务返回码均会检查，单个渠道发送失败仍会继续发送其他渠道。应用凭证不完整、接收 ID 类型或 AgentId 无效时，跳过对应应用推送。
- 本地运行时使用同名环境变量；安装依赖：`pip install -r requirements.txt`，运行：`python checkin.py`。

接口说明：[Telegram](https://core.telegram.org/bots/api#sendmessage)、[飞书应用机器人](https://open.feishu.cn/document/server-docs/im-v1/message/create)、[飞书 Webhook](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)、[钉钉应用机器人](https://open.dingtalk.com/document/orgapp/robots-send-one-on-one-chat-messages-in-batches)、[钉钉 Webhook](https://open.dingtalk.com/document/robots/customize-robot-security-settings)、[企业微信应用消息](https://developer.work.weixin.qq.com/document/path/90236)、[企业微信 Webhook](https://developer.work.weixin.qq.com/document/path/91770)、[PushPlus](https://www.pushplus.plus/doc/guide/api.html)、[云湖](https://www.yhchat.com/document/1-3)。

#### 3.4 RAILGUN（非必填）

添加名为 `RAILGUN` 的 repository secret：

| 值 | 行为 |
|---|---|
| `0` | 仅执行 `glados.cloud` 签到；不请求、不统计、不展示 `railgun.info` |
| `1` | 执行并展示 `glados.cloud` 和 `railgun.info` 两站签到 |
| 未设置或空值 | 默认 `1`，兼容原有双站行为 |

仅接受 `0` / `1`，其他值会报配置错误。开关对全部账号生效；当前仍会将每个 Cookie 用于每个启用站点，请提供相应站点可用的 Cookie。

### 签到结果示例与邮箱脱敏

邮箱取自账号状态接口，只在结果、日志摘要和推送中显示脱敏版本。用户名长度大于 3 时保留前两位及末位（例如 `kuyvub@gmail.com` → `ku***b@gmail.com`）；2–3 位仅保留首位，1 位全部隐藏。接口失败或未返回有效邮箱时显示 `邮箱未知`，仍保留序号以定位对应 Cookie。

单站示例（`RAILGUN=0`，`GLADOS_EXCHANGE_PLAN=plan500`）：

```text
GLaDOS 签到完成✅1❌0🔄2

1.ha***o@gmail.com🔄重复签到 | 总积分:59 积分 | 剩余:352 天 | 兑换:⏭️积分不足(59/500)
2.do***n@gmail.com✅签到成功(+11积分) | 总积分:2 积分 | 剩余:171 天 | 兑换:🎁兑换成功(+100天)
3.gx***i@gmail.com🔄重复签到 | 总积分:328 积分 | 剩余:123 天 | 兑换:⏭️积分不足(328/500)
```

标题统计实际执行的账号 × 站点任务数，分别为签到成功、失败、重复签到次数。双站启用时，每行额外显示域名以区分同一邮箱。兑换成功后重新查询积分和天数，示例中的 502 积分兑换后显示 2 积分，71 天增加后显示 171 天。未配置兑换计划时提示跳过自动兑换。

### 开发验证

```shell
python -m unittest discover -s tests -v
```

测试使用模拟 HTTP 响应，不需要真实 Cookie 或推送密钥，不会实际签到、兑换或发送通知。

### Star 本仓库

![图片加载失败](imgs/4.png)

## 更新日志

- **2026-10（dev）**：签到邮箱脱敏展示；新增 `RAILGUN` 双站开关；支持 Telegram、飞书、钉钉、企业微信推送及可选加签，新增飞书/钉钉应用机器人单聊、企业微信自建应用、PushPlus 和云湖机器人；统一使用「签到成功」「重复签到」文案；修复签到所得积分显示，积分不足跳过兑换，兑换后刷新余额与天数。

- **2026-01**: 重构代码，添加日志输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑与日志输出，支持[新版域名](https://railgun.info)，在 `GLADOS_COOKIES` 中添加新版域名下的 cookies 即可使用。
- **2026-09**: 设备平台自适应重试（无需手动配置 UA 即可自动恢复签到）；网络层自动重试与退避，降低 CI 网络抖动导致的误报失败；日志时间统一为北京时间，定时任务调整为北京时间每天 2 次并避开整点高峰；默认关闭自动兑换，需显式配置后才启用。
- **2026-10**: 日志级别短标签 `[I]/[W]/[E]` ；推送兼容 Server酱（策略模式多后端「都发」），新增 `requirements.txt` 。

## 问题排查与定位

大家可以通过查询 Actions 中的 running checkin 日志快速定位问题，有其他问题提交 issue。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新，因 GitHub 相关规定可能会删库，请注意备份。
