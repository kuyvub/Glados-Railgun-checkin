# GLaDOS 积分签到

Quantumult X 与 Surge 5 共用同一个脚本，默认每天 09:05 按设备时间签到。

## Quantumult X

在「任务配置」添加 [远程任务库](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/quantumultx-gallery.json)，从中添加 GLaDOS 任务，并启用随任务导入的重写。如果需要单独添加重写，使用 [重写配置](https://raw.githubusercontent.com/kuyvub/Glados-Railgun-checkin/refs/heads/quantumultx-surge/clients/quantumultx.conf)。

也可把下面的任务行放入现有的 `[task_local]`。

```ini
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
