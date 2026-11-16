// egress-proxy.mjs - tiny allowlisting HTTP/HTTPS forward proxy for MXC sandboxes.
//
// MXC ProcessContainer can only filter direct egress by IP/CIDR. Hostname
// filtering (api.anthropic.com, github.com, ...) is done by a caller-owned
// loopback proxy: MXC blocks every direct connection from the container and
// points HTTP(S)_PROXY at this process. This proxy decides which hosts are
// reachable and logs every decision.
//
// Usage: node egress-proxy.mjs <port> <allowlist.txt> <logfile.jsonl>
// No dependencies; Node 20+.

import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';

const [port = '18080', allowFile = './allowlist.txt', logFile = './egress.jsonl'] =
  process.argv.slice(2);

function loadAllowlist(file) {
  return fs
    .readFileSync(file, 'utf8')
    .split(/\r?\n/)
    .map((l) => l.replace(/#.*/, '').trim().toLowerCase())
    .filter(Boolean)
    .map((entry) => {
      // "host[:port]" or "*.domain[:port]"; port defaults to 443
      const [host, p] = entry.split(':');
      return { host, port: p ? Number(p) : 443 };
    });
}

let allow = loadAllowlist(allowFile);
fs.watchFile(allowFile, { interval: 2000 }, () => {
  allow = loadAllowlist(allowFile);
  log({ event: 'allowlist-reloaded', entries: allow.length });
});

const logStream = fs.createWriteStream(logFile, { flags: 'a' });
function log(obj) {
  logStream.write(JSON.stringify({ ts: new Date().toISOString(), ...obj }) + '\n');
}

function isAllowed(host, port) {
  host = host.toLowerCase().replace(/^\[|\]$/g, '');
  if (net.isIP(host)) return false; // never allow raw IPs - forces DNS names on the allowlist
  return allow.some((a) => {
    if (a.port !== port) return false;
    if (a.host.startsWith('*.')) {
      const base = a.host.slice(2);
      return host === base || host.endsWith('.' + base);
    }
    return host === a.host;
  });
}

const server = http.createServer((req, res) => {
  // Plain-HTTP forward proxy requests arrive with an absolute URL.
  let target;
  try {
    target = new URL(req.url);
  } catch {
    res.writeHead(400).end('absolute URL required');
    return;
  }
  const tport = Number(target.port || 80);
  if (target.protocol !== 'http:' || !isAllowed(target.hostname, tport)) {
    log({ decision: 'deny', method: req.method, host: target.hostname, port: tport });
    res.writeHead(403, { 'content-type': 'text/plain' }).end(`egress to ${target.hostname}:${tport} blocked by sandbox policy\n`);
    return;
  }
  log({ decision: 'allow', method: req.method, host: target.hostname, port: tport });
  const upstream = http.request(
    { host: target.hostname, port: tport, method: req.method, path: target.pathname + target.search, headers: req.headers },
    (up) => {
      res.writeHead(up.statusCode ?? 502, up.headers);
      up.pipe(res);
    },
  );
  upstream.on('error', () => res.destroy());
  req.pipe(upstream);
});

// HTTPS goes through CONNECT tunnels; we see only host:port (no TLS interception).
server.on('connect', (req, clientSocket, head) => {
  const [host, p] = req.url.split(':');
  const tport = Number(p || 443);
  if (!isAllowed(host, tport)) {
    log({ decision: 'deny', method: 'CONNECT', host, port: tport });
    clientSocket.end('HTTP/1.1 403 Forbidden\r\n\r\n');
    return;
  }
  log({ decision: 'allow', method: 'CONNECT', host, port: tport });
  const upstream = net.connect(tport, host, () => {
    clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    if (head?.length) upstream.write(head);
    upstream.pipe(clientSocket);
    clientSocket.pipe(upstream);
  });
  const close = () => { upstream.destroy(); clientSocket.destroy(); };
  upstream.on('error', close);
  clientSocket.on('error', close);
});

// Bind ONLY the exact loopback endpoint handed to MXC (runtimeConfig.networkProxy).
server.listen(Number(port), '127.0.0.1', () => {
  log({ event: 'listening', port: Number(port), entries: allow.length });
  console.log(`egress-proxy listening on 127.0.0.1:${port}`);
});
