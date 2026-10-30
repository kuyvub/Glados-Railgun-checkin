"""离线回归：覆盖域名选择、隐私、兑换流程和各推送接口协议。"""
import base64
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import requests
import checkin as app


class CheckinTests(unittest.TestCase):
    def config(self, **values):
        with patch.dict(os.environ, values, clear=True):
            return app.Config()

    def test_cookie_separators(self):
        cookies = ["koa:sess=first; koa:sess.sig=a;", "koa:sess=second; koa:sess.sig=b;", "koa:sess=third;"]
        for separator in ("&", "|||", "\n", "\r\n", "\r"):
            with self.subTest(separator=repr(separator)):
                self.assertEqual(self.config(GLADOS_COOKIES=separator.join(cookies)).cookies_list, cookies)
        mixed = f" & ||| \r\n {cookies[0]} & \n {cookies[1]} ||| {cookies[2]} \n&||| "
        self.assertEqual(self.config(GLADOS_COOKIES=mixed).cookies_list, cookies)
        # 单个竖线和分号属于 Cookie 内容，不能当作分隔符。
        single = "koa:sess=a|b; koa:sess.sig=c;"
        self.assertEqual(self.config(GLADOS_COOKIES=single).cookies_list, [single])
        self.assertEqual(self.config(GLADOS_COOKIES="").cookies_list, [])
        with self.assertRaises(ValueError):
            self.config(GLADOS_COOKIES=" & ||| \r\n ")

    def test_mask_email(self):
        for email, masked in [("kuyvub@gmail.com", "ku***b@gmail.com"),
                              ("abc@test.com", "a***@test.com"),
                              ("ab@test.com", "a***@test.com"),
                              ("a@test.com", "***@test.com"),
                              (None, "邮箱未知"), ("invalid", "邮箱未知")]:
            self.assertEqual(app.mask_email(email), masked)

    def test_railgun_switch_controls_requests_and_report(self):
        for flag, domains in [("0", ["glados.cloud"]), ("1", app.Config.DOMAINS), ("", app.Config.DOMAINS)]:
            config = self.config(RAILGUN=flag, GLADOS_COOKIES="one&two")
            checker = app.Checker(config)
            with patch.object(checker, "_checkin_on_domain", side_effect=lambda cookie, index, domain:
                              app.CheckinResult(index, domain, status="重复签到", code=app.CheckinStatus.REPEAT)) as run:
                checker.checkin_all()
            self.assertEqual([call.args[2] for call in run.call_args_list], domains * 2)
            report = checker.format_results()
            self.assertEqual(report["repeat"], len(domains) * 2)
            if flag == "0":
                self.assertNotIn("railgun.info", app.render_payload(report))
        with self.assertRaises(ValueError):
            self.config(RAILGUN="invalid")

    def test_status_masks_email_before_storing(self):
        with app.API("glados.cloud") as api:
            response = MagicMock()
            response.json.return_value = {"code": 0, "data": {"email": "kuyvub@gmail.com", "leftDays": "71.5"}}
            with patch.object(api, "_make_request", return_value=response):
                self.assertEqual(api.get_status("cookie"), ("71 天", 0))
            self.assertEqual(api.email, "ku***b@gmail.com")

    def test_exchange_and_display(self):
        config = self.config(RAILGUN="0", GLADOS_EXCHANGE_PLAN="plan500")
        for points, expected_calls in [(59, 0), (502, 1)]:
            with patch.object(app, "API") as factory:
                api = factory.return_value.__enter__.return_value
                api.email = "bi***e@gmail.com"
                api.get_status.side_effect = [("71 天", 0), ("171 天", 0)]
                api.checkin.return_value = {"status": "签到成功", "points": "11", "code": app.CheckinStatus.SUCCESS}
                api.get_points.side_effect = [(f"{points} 积分", points), ("2 积分", 2)]
                api.exchange.return_value = "🎁兑换成功(+100天)"
                checker = app.Checker(config)
                result = checker._checkin_on_domain("cookie", 1, "glados.cloud")
                self.assertEqual(api.exchange.call_count, expected_calls)
                checker.results = [result]
                report = checker.format_results()
                text = app.render_payload(report)
                self.assertEqual(report["title"], "GLaDOS 签到完成✅1❌0🔄0")
                self.assertIn("bi***e@gmail.com✅签到成功(+11积分)", text)
                self.assertIn("⏭️积分不足(59/500)" if points == 59 else "总积分:2 积分 | 剩余:171 天", text)

    def test_failed_checkin_never_exchanges(self):
        config = self.config(GLADOS_EXCHANGE_PLAN="plan500")
        with patch.object(app, "API") as factory:
            api = factory.return_value.__enter__.return_value
            api.get_status.return_value = ("None 天", -2)
            api.get_points.return_value = ("502 积分", 502)
            api.checkin.return_value = {"status": "签到失败"}
            result = app.Checker(config)._checkin_on_domain("cookie", 1, "glados.cloud")
            api.exchange.assert_not_called()
            self.assertEqual(result.code, app.CheckinStatus.FAILURE)

    def test_requested_notification_example_matches_readme(self):
        from pathlib import Path

        checker = app.Checker(self.config(RAILGUN="0"))
        checker.results = [
            app.CheckinResult(1, "glados.cloud", email="ha***o@gmail.com", status="重复签到",
                              points_total="59 积分", days="352 天", exchange="⏭️积分不足(59/500)",
                              code=app.CheckinStatus.REPEAT),
            app.CheckinResult(2, "glados.cloud", email="do***n@gmail.com", status="签到成功", points="11",
                              points_total="2 积分", days="171 天", exchange="🎁兑换成功(+100天)",
                              code=app.CheckinStatus.SUCCESS),
            app.CheckinResult(3, "glados.cloud", email="gx***i@gmail.com", status="重复签到",
                              points_total="328 积分", days="123 天", exchange="⏭️积分不足(328/500)",
                              code=app.CheckinStatus.REPEAT),
        ]
        payload = checker.format_results()
        expected = (
            "GLaDOS 签到完成✅1❌0🔄2\n\n"
            "1.ha***o@gmail.com🔄重复签到 | 总积分:59 积分 | 剩余:352 天 | 兑换:⏭️积分不足(59/500)\n"
            "2.do***n@gmail.com✅签到成功(+11积分) | 总积分:2 积分 | 剩余:171 天 | 兑换:🎁兑换成功(+100天)\n"
            "3.gx***i@gmail.com🔄重复签到 | 总积分:328 积分 | 剩余:123 天 | 兑换:⏭️积分不足(328/500)"
        )
        self.assertEqual(payload["title"] + "\n\n" + app.render_payload(payload), expected)
        self.assertIn(expected, (Path(__file__).resolve().parents[1] / "README.md").read_text())


class PushTests(unittest.TestCase):
    payload = {"rows": [], "note": "ku***b@gmail.com"}

    def application_config(self, **overrides):
        values = {
            "FEISHU_APP_ID": "app", "FEISHU_APP_SECRET": "secret", "FEISHU_RECEIVE_ID": "ou_user",
            "DINGTALK_APP_KEY": "app", "DINGTALK_APP_SECRET": "secret",
            "DINGTALK_ROBOT_CODE": "robot", "DINGTALK_USER_ID": "user",
            "WECOM_CORP_ID": "corp", "WECOM_CORP_SECRET": "secret",
            "WECOM_AGENT_ID": "1000001", "WECOM_TO_USER": "user",
        }
        values.update(overrides)
        with patch.dict(os.environ, values, clear=True):
            return app.Config()

    @patch("checkin.requests.post")
    def test_pushplus_and_yunhu_protocols(self, post):
        post.return_value.json.return_value = {"code": 200}
        self.assertTrue(app.PushPlusBackend("private").send("title", self.payload))
        self.assertEqual(post.call_args.args[0], "https://www.pushplus.plus/send")
        self.assertEqual(post.call_args.kwargs["json"], {
            "token": "private", "title": "title", "content": self.payload["note"], "template": "txt",
        })
        post.return_value.json.return_value = {"code": 1}
        for recv_type in ("user", "group"):
            self.assertTrue(app.YunhuBackend("private", "id", recv_type).send("title", self.payload))
            self.assertEqual(post.call_args.args[0], "https://chat-go.jwzhd.com/open-apis/v1/bot/send")
            self.assertEqual(post.call_args.kwargs["params"], {"token": "private"})
            self.assertEqual(post.call_args.kwargs["json"], {
                "recvId": "id", "recvType": recv_type, "contentType": "text",
                "content": {"text": "title\n\n" + self.payload["note"]},
            })
        post.return_value.json.return_value = {"code": 0}
        self.assertFalse(app.PushPlusBackend("private").send("title", self.payload))
        self.assertFalse(app.YunhuBackend("private", "id").send("title", self.payload))

    @patch("checkin.requests.get")
    @patch("checkin.requests.post")
    def test_application_authentication_and_message_protocols(self, post, get):
        config = self.application_config(FEISHU_RECEIVE_ID_TYPE="email", FEISHU_RECEIVE_ID="a@example.test")
        for platform in ("feishu", "dingtalk", "wecom"):
            with self.subTest(platform=platform):
                post.reset_mock()
                auth = MagicMock()
                auth.json.return_value = {"code": 0, "tenant_access_token": "token", "accessToken": "token"}
                sent = MagicMock()
                sent.json.return_value = {"code": 0, "errcode": 0, "processQueryKey": "key"}
                post.side_effect = [auth, sent] if platform != "wecom" else [sent]
                get.return_value.json.return_value = {"errcode": 0, "access_token": "token"}
                self.assertTrue(app.ApplicationBackend(platform, config).send("title", self.payload))
                kwargs = post.call_args.kwargs
                text = "title\n\n" + self.payload["note"]
                if platform == "feishu":
                    self.assertEqual(post.call_args_list[0].kwargs["json"], {"app_id": "app", "app_secret": "secret"})
                    self.assertEqual(kwargs["headers"], {"Authorization": "Bearer token"})
                    self.assertEqual(kwargs["params"], {"receive_id_type": "email"})
                    self.assertEqual(kwargs["json"]["receive_id"], "a@example.test")
                    self.assertEqual(json.loads(kwargs["json"]["content"]), {"text": text})
                elif platform == "dingtalk":
                    self.assertEqual(post.call_args_list[0].kwargs["json"], {"appKey": "app", "appSecret": "secret"})
                    self.assertEqual(kwargs["headers"], {"x-acs-dingtalk-access-token": "token"})
                    self.assertEqual(kwargs["json"]["userIds"], ["user"])
                    self.assertEqual(kwargs["json"]["robotCode"], "robot")
                    self.assertEqual(kwargs["json"]["msgKey"], "sampleText")
                    self.assertEqual(json.loads(kwargs["json"]["msgParam"]), {"content": text})
                else:
                    self.assertEqual(get.call_args.kwargs["params"], {"corpid": "corp", "corpsecret": "secret"})
                    self.assertEqual(kwargs["params"], {"access_token": "token"})
                    self.assertEqual(kwargs["json"], {"touser": "user", "agentid": 1000001,
                                                    "msgtype": "text", "text": {"content": text}})

    @patch("checkin.requests.get")
    @patch("checkin.requests.post")
    def test_auth_failure_stops_application_send_without_leaking_secrets(self, post, get):
        for platform in ("feishu", "dingtalk", "wecom"):
            with self.subTest(platform=platform):
                post.reset_mock()
                get.reset_mock()
                post.side_effect = requests.RequestException("private-token secret")
                get.return_value.json.return_value = {"errcode": 40013, "errmsg": "private-token secret"}
                with self.assertLogs(level="ERROR") as logs:
                    self.assertFalse(app.ApplicationBackend(platform, self.application_config()).send("title", self.payload))
                self.assertNotIn("private-token", "".join(logs.output))
                self.assertNotIn("secret", "".join(logs.output))
                self.assertEqual(post.call_count, 0 if platform == "wecom" else 1)

    @patch("checkin.requests.get")
    @patch("checkin.requests.post")
    def test_partial_recipient_failures_are_not_reported_as_success(self, post, get):
        config = self.application_config()
        auth = MagicMock()
        auth.json.return_value = {"accessToken": "token"}
        sent = MagicMock()
        for field in ("invalidStaffIdList", "flowControlledStaffIdList"):
            sent.json.return_value = {"processQueryKey": "key", field: ["user"]}
            post.side_effect = [auth, sent]
            self.assertFalse(app.ApplicationBackend("dingtalk", config).send("title", self.payload))
        get.return_value.json.return_value = {"errcode": 0, "access_token": "token"}
        for field in ("invaliduser", "unlicenseduser"):
            sent.json.return_value = {"errcode": 0, field: "user"}
            post.side_effect = [sent]
            self.assertFalse(app.ApplicationBackend("wecom", config).send("title", self.payload))

    @patch("checkin.requests.post")
    def test_application_chunks_share_one_token_and_continue_after_failure(self, post):
        config = self.application_config()
        auth = MagicMock()
        auth.json.return_value = {"code": 0, "tenant_access_token": "token"}
        success, failure = MagicMock(), MagicMock()
        success.json.return_value = {"code": 0}
        failure.json.return_value = {"code": 999}
        post.side_effect = [auth, failure] + [success] * 100
        payload = {"note": "签到✅" * 2000}
        self.assertFalse(app.ApplicationBackend("feishu", config).send("GLaDOS", payload))
        calls = post.call_args_list
        self.assertGreater(len(calls), 3)
        self.assertEqual(sum("tenant_access_token/internal" in c.args[0] for c in calls), 1)
        chunks = [json.loads(c.kwargs["json"]["content"])["text"] for c in calls[1:]]
        self.assertEqual("".join(c.removeprefix("GLaDOS\n\n") for c in chunks), payload["note"])
        self.assertTrue(all(len(c.encode()) <= 2048 for c in chunks))

    def test_application_and_webhook_can_coexist(self):
        config = self.application_config(FEISHU_WEBHOOK="url", DINGTALK_WEBHOOK="url", WECOM_WEBHOOK="url",
                                         PUSHPLUS_TOKEN="token", YUNHU_BOT_TOKEN="token", YUNHU_RECV_ID="id")
        service = app.PushService(config)
        self.assertEqual(len(service.backends), 8)
        for i, backend in enumerate(service.backends):
            backend.send = MagicMock(return_value=i != 0)
        self.assertTrue(service.send("title", self.payload))
        for backend in service.backends:
            backend.send.assert_called_once()

    def test_invalid_optional_channel_config_is_skipped(self):
        for values in ({"FEISHU_APP_ID": "app"}, {"WECOM_AGENT_ID": "invalid"},
                       {"YUNHU_BOT_TOKEN": "token"},
                       {"YUNHU_BOT_TOKEN": "token", "YUNHU_RECV_ID": "id", "YUNHU_RECV_TYPE": "invalid"}):
            with patch.dict(os.environ, values, clear=True):
                self.assertEqual(app.PushService(app.Config()).backends, [])
        for values in ({"FEISHU_RECEIVE_ID_TYPE": "invalid"}, {"WECOM_AGENT_ID": "-1"},
                       {"WECOM_AGENT_ID": "0"}, {"WECOM_AGENT_ID": "１２"}):
            self.assertEqual(len(app.PushService(self.application_config(**values)).backends), 2)

    @patch("checkin.requests.post")
    @patch("checkin.time.time", return_value=1700000000)
    def test_protocols_and_signatures(self, clock, post):
        response = post.return_value
        response.json.return_value = {"ok": True, "code": 0, "errcode": 0}
        tg = app.TelegramBackend("token", "-123")
        self.assertTrue(tg.send("GLaDOS", self.payload))
        self.assertEqual(post.call_args.kwargs["json"], {"chat_id": "-123", "text": "GLaDOS\n\nku***b@gmail.com"})
        for platform in ("feishu", "dingtalk", "wecom"):
            backend = app.WebhookBackend(platform, "https://example.test/hook?key=private", "secret")
            self.assertTrue(backend.send("GLaDOS", self.payload))
            body = post.call_args.kwargs["json"]
            if platform == "feishu":
                expected = base64.b64encode(hmac.new(b"1700000000\nsecret", b"", hashlib.sha256).digest()).decode()
                self.assertEqual(body["sign"], expected)
                self.assertEqual(body["content"]["text"], "GLaDOS\n\nku***b@gmail.com")
            elif platform == "dingtalk":
                expected = base64.b64encode(hmac.new(b"secret", b"1700000000000\nsecret", hashlib.sha256).digest()).decode()
                self.assertEqual(post.call_args.kwargs["params"], {"timestamp": "1700000000000", "sign": expected})
            else:
                self.assertEqual(body["text"]["content"], "GLaDOS\n\nku***b@gmail.com")

    @patch("checkin.requests.post")
    def test_errors_do_not_leak_credentials(self, post):
        backend = app.TelegramBackend("private-token", "123")
        for error in [requests.RequestException("private-token"), ValueError("private-token")]:
            post.side_effect = error
            with self.assertLogs(level="ERROR") as logs:
                self.assertFalse(backend.send("title", self.payload))
            self.assertNotIn("private-token", "".join(logs.output))
        post.side_effect = None
        post.return_value.json.return_value = {"ok": False}
        self.assertFalse(backend.send("title", self.payload))

    @patch("checkin.requests.post")
    def test_webhook_chunks_repeat_keyword_and_check_business_status(self, post):
        backend = app.WebhookBackend("wecom", "https://example.test/hook")
        post.return_value.json.return_value = {"errcode": 0}
        self.assertTrue(backend.send("GLaDOS", {"note": "签到✅" * 2000}))
        self.assertGreater(post.call_count, 1)
        for call in post.call_args_list:
            text = call.kwargs["json"]["text"]["content"]
            self.assertTrue(text.startswith("GLaDOS"))
            self.assertLessEqual(len(text.encode()), 2048)
        post.return_value.json.return_value = {"errcode": 93000}
        self.assertFalse(backend.send("GLaDOS", self.payload))

    def test_chunking_keeps_all_unicode_text(self):
        text = "签到✅ku***b@gmail.com\n" * 1000
        chunks = app.split_message(text)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk.encode()) <= 1800 for chunk in chunks))

    def test_all_configured_channels_send_after_failure(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123",
                                   "FEISHU_WEBHOOK": "url", "DINGTALK_WEBHOOK": "url", "WECOM_WEBHOOK": "url"}, clear=True):
            service = app.PushService(app.Config())
        self.assertEqual(len(service.backends), 4)
        for i, backend in enumerate(service.backends):
            backend.send = MagicMock(return_value=i != 0)
        self.assertTrue(service.send("title", self.payload))
        for backend in service.backends:
            backend.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
