# GLaDOS 积分签到

Quantumult X 与 Surge 5 共用同一个脚本，默认每天 09:05 按设备时间签到。

## Quantumult X

1. 在「引用资源 → 重写」添加 [Cookie 获取重写](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/quantumultx.conf)，关闭该条目的「资源解析器」，保存并启用。`quantumultx.conf` 已采用 Quantumult X 的重写格式。
2. 在「计划任务 → 任务仓库」添加 [GLaDOS 任务库](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/quantumultx-gallery.json)，选中并添加「GLaDOS 积分签到」。如果先通过任务库添加了附加组件，只需确认相同的重写已启用。

如果添加资源时报 `Resource parser result is invalid`，先检查「资源路径」是否误填了 `glados-checkin.js`。请在「引用资源 → 重写」使用上面的 `.conf` 地址，并关闭该条目的解析器。`.js` 地址由定时任务和重写规则加载。

也可用下面的链接打开任务仓库。复制整行到 Safari 地址栏后打开。

```text
quantumult-x:///ui?module=gallery&type=task&action=add&content=%5B%22https%3A%2F%2Fraw.githubusercontent.com%2Fkuyvub%2FGlados-Railgun-checkin%2Frefs%2Fheads%2Fquantumultx-surge%2Fclients%2Fquantumultx-gallery.json%22%5D
```

手动编辑配置时，把下面两行分别加到现有的 `[rewrite_remote]` 和 `[task_local]`。若已经通过界面添加对应条目，使用现有条目即可。

```ini
[rewrite_remote]
https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/quantumultx.conf, tag=GLaDOS 获取 Cookie, enabled=true

[task_local]
5 9 * * * https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/glados-checkin.js, tag=GLaDOS 积分签到, enabled=true
```

## Surge 5

在「模块」通过 URL 安装并启用 [GLaDOS 签到模块](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/glados-checkin.sgmodule)。模块自带定时任务和登录信息获取规则。

## 首次运行

1. 开启相应客户端的代理和 MITM，并安装和信任该客户端的 MITM 证书。Quantumult X 还需要开启重写。
2. 在同一设备的浏览器登录 [GLaDOS](https://glados.cloud/console/checkin)，打开或刷新积分页。看到「已保存登录信息」后，在客户端手动运行一次任务。
3. Cookie 与浏览器 User-Agent 保存在客户端本地。定时任务可在关闭 MITM 的情况下运行。会话失效后，重新启用获取规则和 MITM，登录并刷新积分页。

脚本先获取一次性挑战，等待至少 2.5 秒，用 `SHA-256(nonce + ".glados-observe-v1")` 计算证明并提交。通知会显示当次获得的积分，以及服务端响应中包含的余额和连续签到天数。若官网要求 Cloudflare Turnstile，打开官网积分页完成验证并手动签到。

[签到脚本](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/glados-checkin.js) · [Quantumult X 配置参考](https://github.com/crossutility/Quantumult-X/blob/master/sample-task.js) · [Surge 脚本参考](https://manual.nssurge.com/scripting/overview.html)
