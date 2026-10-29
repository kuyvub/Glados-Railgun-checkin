"""离线回归：覆盖域名选择、隐私、兑换流程和各推送接口协议。"""
import base64
import hashlib
import hmac
import os
import unittest
from unittest.mock import MagicMock, patch

import requests
import checkin as app


class CheckinTests(unittest.TestCase):
    def config(self, **values):
        with patch.dict(os.environ, values, clear=True):
            return app.Config()

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
                self.assertIn("bi***e@gmail.com✅成功(+11积分)", text)
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


class PushTests(unittest.TestCase):
    payload = {"rows": [], "note": "ku***b@gmail.com"}

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
