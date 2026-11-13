// GLaDOS 积分签到，适用于 Quantumult X 和 Surge 5。
(() => {
  'use strict';

  const host = 'glados.cloud';
  const origin = `https://${host}`;
  const page = `${origin}/console/checkin`;
  const checkinPath = '/api/user/checkin';
  const challengePath = `${checkinPath}/challenge`;
  const sessionKey = 'glados-cloud-checkin-session';
  const quantumult = typeof $task !== 'undefined';
  const turnstileMessage = 'GLaDOS 要求 Cloudflare 人机验证，请在官网积分页完成验证并签到。';

  function notify(title, message) {
    console.log(`GLaDOS ${title}：${message}`);
    if (quantumult) $notify('GLaDOS 积分签到', title, message);
    else $notification.post('GLaDOS 积分签到', title, message);
  }

  function parseResult(body) {
    const result = JSON.parse(body);
    if (!result || typeof result.code !== 'number') throw new Error('响应格式异常');
    return result;
  }

  function readSession() {
    const saved = quantumult ? $prefs.valueForKey(sessionKey) : $persistentStore.read(sessionKey);
    return saved ? JSON.parse(saved) : null;
  }

  function captureSession() {
    // 仅保存官网已接受的登录会话。定时请求带查询参数，不匹配抓取规则。
    if ($request.url !== origin + challengePath || $request.method !== 'GET') return;
    let result;
    try {
      result = parseResult($response.body);
    } catch (_) {
      return;
    }
    if (result.code !== 0 || !result.nonce) return;

    const headers = $request.headers;
    const header = name => {
      const key = Object.keys(headers).find(key => key.toLowerCase() === name);
      return key && typeof headers[key] === 'string' ? headers[key].trim() : '';
    };
    const cookie = header('cookie');
    const userAgent = header('user-agent');
    if (!cookie || !userAgent) return;

    const previous = readSession();
    if (previous && previous.cookie === cookie && previous.userAgent === userAgent) return;
    const saved = JSON.stringify({ cookie, userAgent });
    const ok = quantumult ? $prefs.setValueForKey(saved, sessionKey) : $persistentStore.write(saved, sessionKey);
    if (!ok) throw new Error('无法写入客户端本地存储，请重试。');
    notify('已保存登录信息', '可手动运行定时任务。登录失效时重新打开官网积分页。');
  }

  async function requestJSON(session, path, payload) {
    const method = payload ? 'POST' : 'GET';
    const options = {
      url: origin + path,
      headers: {
        Accept: 'application/json, text/plain, */*',
        'Cache-Control': 'no-cache',
        Cookie: session.cookie,
        Referer: page,
        'User-Agent': session.userAgent,
      },
    };
    if (payload) {
      options.headers.Origin = origin;
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(payload);
    }

    let response;
    try {
      if (quantumult) {
        response = await $task.fetch({ ...options, method, opts: { redirection: false, 'auto-cookie': false } });
      } else {
        response = await new Promise((resolve, reject) => {
          $httpClient[method.toLowerCase()]({ ...options, timeout: 8, 'auto-redirect': false, 'auto-cookie': false },
            (error, res, body) => error ? reject(error) : resolve({ statusCode: res.status, body }));
        });
      }
    } catch (error) {
      const timeout = /timed?\s*out|timeout|超时/i.test(String(error && (error.error || error.message || error)));
      const failure = new Error(timeout ? '请求超时，请稍后再试。' : '无法连接 GLaDOS，请检查网络后重试。');
      failure.timeout = timeout;
      throw failure;
    }

    const status = response.statusCode;
    if (status === 401 || (status >= 300 && status < 400)) {
      throw new Error('登录状态失效，请重新登录并打开官网积分页。');
    }
    if (status === 403) throw new Error('请求被拒绝，请打开官网积分页检查登录及人机验证。');
    if (status < 200 || status >= 300) throw new Error(`GLaDOS 请求失败（HTTP ${status}）。`);
    try {
      return parseResult(response.body);
    } catch (_) {
      throw new Error('GLaDOS 响应格式异常，请打开官网积分页检查登录及人机验证。');
    }
  }

  function checkinError(result, fallback) {
    if (result.reason === 'turnstile') return new Error(turnstileMessage);
    if (result.reason === 'device-mismatch') {
      return new Error('登录设备不匹配，请在同一浏览器退出并重新登录，再打开官网积分页。');
    }
    if (result.message === '没有权限') {
      return new Error('登录状态失效，请重新登录并打开官网积分页。');
    }
    return new Error(fallback + `（代码 ${result.code}）。请到官网积分页查看详情。`);
  }

  async function prepareChallenge(session) {
    const challenge = await requestJSON(session, `${challengePath}?source=client-task`);
    const receivedAt = Date.now();
    if (challenge.code !== 0) throw checkinError(challenge, '获取签到挑战失败');
    if (challenge.turnstile) throw new Error(turnstileMessage);

    const nonce = challenge.nonce;
    const ttl = Number(challenge.ttl == null ? 300000 : challenge.ttl);
    const waitMs = 2600;
    const marginMs = 15000;
    if (typeof nonce !== 'string' || !nonce.trim() || !Number.isFinite(ttl) || ttl <= waitMs + marginMs) {
      throw new Error('签到挑战缺少有效 nonce 或有效期，请稍后再试。');
    }
    await new Promise(resolve => setTimeout(resolve, waitMs));
    if (Date.now() - receivedAt >= ttl - marginMs) throw new Error('签到挑战已过期，请重新运行任务。');
    return { token: host, nonce, proof: sha256(`${nonce}.glados-observe-v1`), tsState: 'off' };
  }

  async function submitCheckin(session) {
    for (let attempt = 0; ; attempt++) {
      const payload = await prepareChallenge(session);
      try {
        return await requestJSON(session, checkinPath, payload);
      } catch (error) {
        if (!error.timeout || attempt !== 0) throw error;
        console.log('GLaDOS 签到提交超时，重新获取挑战后重试一次。');
      }
    }
  }

  function numeric(value) {
    if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  async function run() {
    const session = readSession();
    if (!session || !session.cookie || !session.userAgent) {
      throw new Error('请启用 Cookie 获取配置，用浏览器登录并打开官网积分页。');
    }

    const result = await submitCheckin(session);
    if (/please checkin via/i.test(result.message || '')) {
      throw new Error('签到域名不匹配，请在 glados.cloud 重新登录并获取 Cookie。');
    }
    if (result.code !== 0) throw checkinError(result, '签到被拒绝');

    const title = result.repeated ? '今日已签到' : '签到成功';
    const lines = [];
    const earned = numeric(result.points) ?? numeric(result.breakdown && result.breakdown.points);
    const balance = numeric(result.list && result.list[0] && result.list[0].balance);
    const streak = numeric(result.streak);
    if (!result.repeated && earned !== null) lines.push(`本次积分 +${earned}`);
    if (balance !== null) lines.push(`积分余额 ${balance}`);
    if (streak !== null) lines.push(`连续签到 ${streak} 天`);
    notify(title, lines.join('\n') || '签到结果已确认。');
  }

  // FIPS 180-4 SHA-256。两款客户端的 JavaScript 引擎都可以直接运行。
  function sha256(input) {
    const constants = [
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];
    const hash = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]);
    const bytes = encodeURIComponent(input).replace(/%([0-9A-F]{2})/g,
      (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    const blocks = new DataView(new ArrayBuffer(Math.ceil((bytes.length + 9) / 64) * 64));
    for (let i = 0; i < bytes.length; i++) blocks.setUint8(i, bytes.charCodeAt(i));
    blocks.setUint8(bytes.length, 0x80);
    blocks.setUint32(blocks.byteLength - 8, Math.floor(bytes.length / 0x20000000));
    blocks.setUint32(blocks.byteLength - 4, bytes.length * 8);

    const words = new Uint32Array(64);
    const rotate = (x, n) => (x >>> n) | (x << (32 - n));
    for (let offset = 0; offset < blocks.byteLength; offset += 64) {
      for (let i = 0; i < 16; i++) words[i] = blocks.getUint32(offset + i * 4);
      for (let i = 16; i < 64; i++) {
        const x = words[i - 15];
        const y = words[i - 2];
        const sigma0 = rotate(x, 7) ^ rotate(x, 18) ^ (x >>> 3);
        const sigma1 = rotate(y, 17) ^ rotate(y, 19) ^ (y >>> 10);
        words[i] = words[i - 16] + sigma0 + words[i - 7] + sigma1;
      }

      let [a, b, c, d, e, f, g, h] = hash;
      for (let i = 0; i < 64; i++) {
        const sum1 = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
        const choose = (e & f) ^ (~e & g);
        const t1 = h + sum1 + choose + constants[i] + words[i];
        const sum0 = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
        const majority = (a & b) ^ (a & c) ^ (b & c);
        const t2 = sum0 + majority;
        h = g;
        g = f;
        f = e;
        e = (d + t1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (t1 + t2) >>> 0;
      }
      const state = [a, b, c, d, e, f, g, h];
      for (let i = 0; i < hash.length; i++) hash[i] += state[i];
    }
    return Array.from(hash, word => word.toString(16).padStart(8, '0')).join('');
  }

  // 请求重写与定时任务共享脚本和存储键。
  const capturing = typeof $request !== 'undefined' && typeof $response !== 'undefined';
  Promise.resolve().then(capturing ? captureSession : run).catch(error => {
    notify(capturing ? '保存登录信息失败' : '签到失败', error.message || '脚本运行失败。');
  }).finally(() => {
    if (capturing) $done({});
    else $done();
  });
})();
