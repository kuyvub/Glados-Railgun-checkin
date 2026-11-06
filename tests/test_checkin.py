import hashlib
import json
import unittest
from unittest.mock import Mock, patch

import requests

import checkin as app


def response(data):
    result = Mock()
    result.ok = True
    result.json.return_value = data
    return result


class CheckinTests(unittest.TestCase):
    def setUp(self):
        self.api = app.API('glados.cloud', 'koa:sess=test')
        self.addCleanup(self.api.close)
        self.now = 100.0
        self.clock = patch.object(app.time, 'monotonic', side_effect=lambda: self.now)
        self.sleep = patch.object(app.time, 'sleep', side_effect=self.advance)
        self.clock.start()
        self.sleep_mock = self.sleep.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.sleep.stop)

    def advance(self, seconds):
        self.now += seconds

    def challenge(self, nonce='first', **extra):
        return response(dict(code=0, nonce=nonce, ttl=300000, **extra))

    def test_challenge_wait_proof_and_json_payload(self):
        self.api.session.get = Mock(return_value=self.challenge())
        self.api._no_retry_session.post = Mock(return_value=response({'code': 0, 'points': 3.5}))
        result = self.api.checkin()
        self.assertEqual(result.points, 3.5)
        self.assertGreaterEqual(self.now - 100, 2.5)
        request = self.api._no_retry_session.post.call_args
        self.assertEqual(request.args[0], 'https://glados.cloud/api/user/checkin')
        self.assertEqual(request.kwargs['json'], {
            'token': 'glados.cloud', 'nonce': 'first',
            'proof': hashlib.sha256(b'first.glados-observe-v1').hexdigest(),
        })
        self.assertNotIn('data', request.kwargs)
        self.assertNotIn('content-type', self.api.session.get.call_args.kwargs['headers'])
        self.assertEqual(self.api._no_retry_session.get_adapter('https://').max_retries.total, 0)
        self.assertNotIn('POST', self.api.session.get_adapter('https://').max_retries.allowed_methods)
        self.assertIs(self.api.session.cookies, self.api._no_retry_session.cookies)

    def test_invalid_challenge_never_posts_or_waits(self):
        for data in ({'code': -2}, {'code': 4, 'reason': 'device-mismatch'},
                     {'code': 0}, {'code': 0, 'nonce': 'x', 'ttl': 1000}, [], None):
            with self.subTest(data=data):
                self.api.session.get = Mock(return_value=response(data))
                self.api._no_retry_session.post = Mock()
                self.assertEqual(self.api.checkin().code, app.CheckinStatus.FAILURE)
                self.api._no_retry_session.post.assert_not_called()
        self.sleep_mock.assert_not_called()

    def test_timeout_uses_new_nonce_and_repeat_flag(self):
        self.api.session.get = Mock(side_effect=[self.challenge('first'), self.challenge('second')])
        self.api._no_retry_session.post = Mock(side_effect=[
            requests.ReadTimeout(), response({'code': 0, 'repeated': True, 'points': 4.5, 'streak': 9})])
        result = self.api.checkin()
        self.assertEqual(result.code, app.CheckinStatus.REPEAT)
        self.assertEqual(result.points, 0)
        self.assertEqual(result.streak, 9)
        payloads = [call.kwargs['json'] for call in self.api._no_retry_session.post.call_args_list]
        self.assertEqual([p['nonce'] for p in payloads], ['first', 'second'])
        self.assertNotEqual(payloads[0]['proof'], payloads[1]['proof'])

    def test_two_timeouts_stop(self):
        self.api.session.get = Mock(return_value=self.challenge())
        self.api._no_retry_session.post = Mock(side_effect=requests.ReadTimeout())
        self.assertEqual(self.api.checkin().code, app.CheckinStatus.FAILURE)
        self.assertEqual(self.api._no_retry_session.post.call_count, 2)

    def test_device_recovery_gets_fresh_challenge_with_same_ua(self):
        self.api.session.get = Mock(side_effect=[self.challenge('one'), self.challenge('two')])
        self.api._no_retry_session.post = Mock(side_effect=[
            response({'code': 4, 'reason': 'device-mismatch', 'loginDevice': 'iOS'}),
            response({'code': 0, 'points': 2}),
        ])
        self.assertEqual(self.api.checkin().code, app.CheckinStatus.SUCCESS)
        for get_call, post_call in zip(self.api.session.get.call_args_list, self.api._no_retry_session.post.call_args_list):
            self.assertEqual(get_call.kwargs['headers']['user-agent'], post_call.kwargs['headers']['user-agent'])
        self.assertEqual(self.api.session.get.call_args.kwargs['headers']['user-agent'], app.PLATFORM_UA['iOS'])

    def test_custom_ua_not_overridden(self):
        self.api.user_agent = 'custom'
        self.api.session.get = Mock(return_value=self.challenge())
        self.api._no_retry_session.post = Mock(return_value=response({'code': 4, 'reason': 'device-mismatch', 'loginDevice': 'iOS'}))
        self.assertEqual(self.api.checkin().code, app.CheckinStatus.FAILURE)
        self.assertEqual(self.api._no_retry_session.post.call_count, 1)

    def test_expired_challenge_not_submitted(self):
        self.api.session.get = Mock(return_value=self.challenge())
        self.api._no_retry_session.post = Mock()
        with patch.object(app.time, 'sleep', side_effect=lambda _: self.advance(300)):
            self.assertEqual(self.api.checkin().code, app.CheckinStatus.FAILURE)
        self.api._no_retry_session.post.assert_not_called()

    def test_points_preserved_and_no_message_dependency(self):
        result = app.parse_checkin({'code': 0, 'points': 3.5, 'streak': 15,
                                    'list': [{'change': 1, 'balance': 80.5}]}, 'glados.cloud', Mock())
        self.assertEqual((result.points, result.points_total, result.streak), (3.5, 80.5, 15))
        self.assertEqual(app.earned_points({'list': [{'change': '2.5'}]}), 2.5)
        for value in (True, 'NaN', 'inf', {}, None):
            self.assertIsNone(app.to_points(value))
        self.assertEqual(app.format_points(80.5), '80.5 积分')
        self.assertEqual(app.format_points(80), '80 积分')

    def test_legacy_repeat_and_domain_rejection(self):
        for data, expected in [({'code': 1}, app.CheckinStatus.REPEAT),
                               ({'code': 0, 'message': 'please checkin via https://other'}, app.CheckinStatus.FAILURE)]:
            self.assertEqual(app.parse_checkin(data, 'glados.cloud', Mock()).code, expected)

    def test_points_failure_keeps_checkin_balance(self):
        entry = app.CookieEntry.build(1, 'koa:sess=test')
        api = Mock()
        api.checkin.return_value = app.CheckinResult(code=app.CheckinStatus.SUCCESS, points=3.5, points_total=80.5, streak=8)
        api.fetch_points_summary.return_value = None
        api.fetch_status.return_value = {'code': 0, 'data': {'vip': 41, 'leftDays': 20}}
        result = entry._sign_in(api, 'glados.cloud', 19, Mock(exchange_plans={}))
        self.assertEqual((result.points_total, result.streak, result.plan, result.days), (80.5, 8, 'Team', 20))

    def test_points_endpoint_checks_business_code(self):
        self.api._no_retry_session.get = Mock(return_value=response({'code': -2, 'points': 99}))
        self.assertIsNone(self.api.fetch_points_summary())

    def test_cookie_cleanup_and_rejection(self):
        accounts = app.Accounts.parse(json.dumps([{'cookie': 'Cookie: "koa:sess=test;\n koa:sess.sig=sig"'}]))
        self.assertEqual(accounts.entries[0].cookie, 'koa:sess=test; koa:sess.sig=sig')
        with self.assertRaises(ValueError):
            app.Accounts.parse(json.dumps([{'cookie': 'koa:sess=中文'}]))

    def test_schedule_only_jitter(self):
        for event, called in [('workflow_dispatch', False), ('push', False), ('schedule', True)]:
            self.sleep_mock.reset_mock()
            with patch.dict(app.os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_NAME': event}):
                app.maybe_sleep_schedule_jitter()
            self.assertEqual(self.sleep_mock.called, called)

    def test_failure_exits_after_push(self):
        entry = app.CookieEntry.build(1, 'koa:sess=test')
        report = app.Report(app.Accounts([entry]))
        with patch.object(app, 'Config'), patch.object(app.CheckinRunner, 'run', return_value=report), \
             patch.object(app.PushService, 'send') as send, patch.object(app, 'init_logger'), \
             patch.object(app, 'maybe_sleep_schedule_jitter'):
            with self.assertRaises(SystemExit) as exited:
                app.main()
            self.assertEqual(exited.exception.code, 1)
            send.assert_called_once_with(report)


if __name__ == '__main__':
    unittest.main()
