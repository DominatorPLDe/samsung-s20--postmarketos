#!/usr/bin/env python3
"""
Samsung Galaxy S20+ Linux Server - Sleek Web Terminal & Control Dashboard
Hosted on Port 80
"""

import os
import sys
import json
import time
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 80

def get_battery():
    info = {
        "capacity": 0,
        "voltage_mv": 0,
        "temp_c": 0,
        "current_ma": 0,
        "status": "Healthy / Inactive",
        "power_w": 0.0
    }
    path = "/sys/class/power_supply/max170xx_battery/uevent"
    if os.path.exists(path):
        try:
            with open(path) as f:
                for line in f:
                    parts = line.strip().split("=")
                    if len(parts) == 2:
                        k, v = parts
                        if k == "POWER_SUPPLY_CAPACITY":
                            info["capacity"] = int(v)
                        elif k == "POWER_SUPPLY_VOLTAGE_NOW":
                            info["voltage_mv"] = round(int(v) / 1000)
                        elif k == "POWER_SUPPLY_TEMP":
                            info["temp_c"] = round(int(v) / 10, 1)
                        elif k == "POWER_SUPPLY_CURRENT_NOW":
                            info["current_ma"] = round(int(v) / 1000)
                        elif k == "POWER_SUPPLY_STATUS":
                            info["status"] = v
            # Calculate estimated power in Watts
            v_val = info["voltage_mv"] / 1000.0
            i_val = abs(info["current_ma"]) / 1000.0
            info["power_w"] = round(v_val * i_val, 2)
        except Exception:
            pass
    return info

def get_mem():
    mem = {"total_mb": 0, "free_mb": 0, "used_mb": 0, "percent": 0}
    try:
        with open("/proc/meminfo") as f:
            data = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    data[parts[0].strip()] = int(parts[1].strip().split()[0]) // 1024
            total = data.get("MemTotal", 1)
            free = data.get("MemFree", 0) + data.get("Buffers", 0) + data.get("Cached", 0)
            used = total - free
            mem["total_mb"] = total
            mem["used_mb"] = used
            mem["free_mb"] = free
            mem["percent"] = round((used / total) * 100, 1)
    except Exception:
        pass
    return mem

def get_system():
    uptime_str = ""
    try:
        with open("/proc/uptime") as f:
            sec = float(f.read().split()[0])
            hours = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            uptime_str = f"{hours}h {mins}m"
    except Exception:
        uptime_str = "0h 0m"

    load = "0.00, 0.00, 0.00"
    try:
        with open("/proc/loadavg") as f:
            load = " ".join(f.read().split()[:3])
    except Exception:
        pass

    ip_addr = "10.42.0.2 (USB)"
    ssid_name = "Nicht verbunden"
    try:
        out = subprocess.check_output(["ip", "-4", "addr", "show"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            line = line.strip()
            if "inet " in line:
                parts = line.split()
                dev = parts[-1]
                addr = parts[1].split("/")[0]
                if dev.startswith("wlan") or dev.startswith("wlp"):
                    ip_addr = addr
                    break
    except Exception:
        pass
    try:
        out = subprocess.check_output(["iw", "dev", "wlan0", "link"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "SSID:" in line:
                ssid_name = line.split("SSID:")[1].strip() + " (Wi-Fi 6)"
                break
    except Exception:
        pass

    return {
        "device": "Samsung Galaxy S20+ (SM-G985F)",
        "soc": "Exynos 990 (8 Cores: 2x M5 + 2x A76 + 4x A55)",
        "kernel": "Linux 6.12.0-rc3-next (ARM64)",
        "os": "Alpine Linux 3.21",
        "ip": ip_addr,
        "ssid": ssid_name,
        "uptime": uptime_str,
        "load": load,
        "ssh_port": 22
    }

HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>S20+ Server Control Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #080c14;
            --bg-surface: #0e1626;
            --bg-card: #131d31;
            --border: #1e2d4a;
            --border-hover: #2e446e;
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --emerald: #10b981;
            --emerald-glow: rgba(16, 185, 129, 0.25);
            --purple: #8b5cf6;
            --amber: #f59e0b;
            --rose: #f43f5e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(ellipse 80% 50% at 50% -20%, rgba(6, 182, 212, 0.15), transparent),
                radial-gradient(circle at 100% 100%, rgba(139, 92, 246, 0.08), transparent);
        }

        /* Top Navigation Header */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.75rem;
            background: rgba(14, 22, 38, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.875rem;
        }

        .device-badge {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.2), rgba(139, 92, 246, 0.2));
            border: 1px solid rgba(6, 182, 212, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            box-shadow: 0 0 15px var(--cyan-glow);
        }

        .title-group h1 {
            font-size: 1.125rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .title-group p {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }

        .header-meta {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 0.85rem;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--emerald);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--emerald);
            box-shadow: 0 0 10px var(--emerald);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        /* Main Container */
        main {
            flex: 1;
            padding: 1.5rem 1.75rem;
            max-width: 1700px;
            margin: 0 auto;
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1rem;
        }

        .card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.15rem 1.35rem;
            display: flex;
            flex-direction: column;
            gap: 0.65rem;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }

        .card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .card-header .icon {
            font-size: 1.1rem;
        }

        .card-val {
            font-size: 1.75rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            display: flex;
            align-items: baseline;
            gap: 0.35rem;
        }

        .card-val .unit {
            font-size: 0.875rem;
            color: var(--text-dim);
            font-weight: 500;
        }

        .card-sub {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }

        .progress-bar-bg {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 9999px;
            overflow: hidden;
            margin-top: 0.25rem;
        }

        .progress-bar-fill {
            height: 100%;
            border-radius: 9999px;
            background: linear-gradient(90deg, var(--cyan), var(--emerald));
            transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }

        /* Controls / Quick Action Bar */
        .action-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.75rem;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            padding: 0.75rem 1.25rem;
            border-radius: 12px;
        }

        .action-left {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.8125rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
            text-decoration: none;
            font-family: inherit;
        }

        .btn-cyan {
            background: rgba(6, 182, 212, 0.12);
            color: var(--cyan);
            border-color: rgba(6, 182, 212, 0.3);
        }

        .btn-cyan:hover {
            background: rgba(6, 182, 212, 0.25);
            border-color: var(--cyan);
            box-shadow: 0 0 12px var(--cyan-glow);
        }

        .btn-dark {
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-main);
            border-color: var(--border);
        }

        .btn-dark:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--border-hover);
        }

        .btn-emerald {
            background: rgba(16, 185, 129, 0.12);
            color: var(--emerald);
            border-color: rgba(16, 185, 129, 0.3);
        }

        .btn-emerald:hover {
            background: rgba(16, 185, 129, 0.25);
            border-color: var(--emerald);
        }

        .toast-msg {
            font-size: 0.75rem;
            color: var(--emerald);
            font-family: 'JetBrains Mono', monospace;
            opacity: 0;
            transition: opacity 0.3s;
        }

        /* Terminal Window Container */
        .terminal-container {
            flex: 1;
            min-height: 580px;
            background: #090d14;
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.5);
        }

        .terminal-titlebar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.7rem 1.25rem;
            background: #0f1624;
            border-bottom: 1px solid var(--border);
            user-select: none;
        }

        .traffic-lights {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .traffic-dot {
            width: 11px;
            height: 11px;
            border-radius: 50%;
        }

        .dot-red { background: #ef4444; }
        .dot-yellow { background: #f59e0b; }
        .dot-green { background: #10b981; }

        .term-title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .term-actions {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .term-btn {
            background: transparent;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            font-size: 0.85rem;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            transition: all 0.15s;
        }

        .term-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.08);
        }

        .terminal-viewport {
            flex: 1;
            width: 100%;
            height: 100%;
            min-height: 520px;
            border: none;
            background: #090d14;
        }

        /* Footer */
        footer {
            padding: 0.85rem 1.75rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-dim);
            border-top: 1px solid var(--border);
            font-family: 'JetBrains Mono', monospace;
            background: rgba(14, 22, 38, 0.4);
        }

        @media (max-width: 768px) {
            header, main, footer {
                padding: 1rem;
            }
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .terminal-container {
                min-height: 440px;
            }
            .header-meta {
                display: none;
            }
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header>
        <div class="brand">
            <div class="device-badge">📱</div>
            <div class="title-group">
                <h1>Samsung Galaxy S20+ <span style="font-size:0.75rem; color:var(--cyan); font-weight:600; padding:2px 8px; border-radius:4px; background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.25);">SERVER</span></h1>
                <p>Alpine Linux 3.21 • Exynos 990 (8 Cores) • 12GB RAM</p>
            </div>
        </div>
        <div class="header-meta">
            <div class="status-pill">
                <div class="pulse-dot"></div>
                ONLINE (Wi-Fi 6)
            </div>
            <a href="/terminal" onclick="window.open('http://' + window.location.hostname + ':7681'); return false;" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:0.35rem 0.75rem;">
                ↗ Direkt-Terminal
            </a>
        </div>
    </header>

    <!-- Main -->
    <main>

        <!-- Stats Grid -->
        <div class="stats-grid">
            
            <!-- Battery Card -->
            <div class="card">
                <div class="card-header">
                    <span>Akku & Power</span>
                    <span class="icon">🔋</span>
                </div>
                <div class="card-val">
                    <span id="bat-cap">--</span><span class="unit">%</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="bat-bar" class="progress-bar-fill" style="width: 0%;"></div>
                </div>
                <div class="card-sub">
                    <span id="bat-volt">-- mV</span>
                    <span id="bat-temp">-- °C</span>
                </div>
            </div>

            <!-- Display Status Card -->
            <div class="card">
                <div class="card-header">
                    <span>AMOLED Display</span>
                    <span class="icon">🌙</span>
                </div>
                <div class="card-val" style="font-size: 1.35rem; color: var(--emerald);">
                    <span id="disp-status">0W Dark Mode</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: 100%; background: linear-gradient(90deg, #10b981, #06b6d4);"></div>
                </div>
                <div class="card-sub">
                    <span>Status: Dunkel (Kein Burn-in)</span>
                    <span style="color:var(--emerald);">0.00 W</span>
                </div>
            </div>

            <!-- Memory Card -->
            <div class="card">
                <div class="card-header">
                    <span>RAM Auslastung</span>
                    <span class="icon">🧠</span>
                </div>
                <div class="card-val">
                    <span id="ram-used">--</span><span class="unit">/ <span id="ram-total">--</span> MB</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="ram-bar" class="progress-bar-fill" style="width: 0%;"></div>
                </div>
                <div class="card-sub">
                    <span>Frei: <span id="ram-free">--</span> MB</span>
                    <span id="ram-pct">--%</span>
                </div>
            </div>

            <!-- Network / Uptime Card -->
            <div class="card">
                <div class="card-header">
                    <span>Netzwerk & Uptime</span>
                    <span class="icon">📶</span>
                </div>
                <div class="card-val" style="font-size: 1.35rem; color: var(--cyan);">
                    10.42.0.2
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: 100%; background: var(--cyan);"></div>
                </div>
                <div class="card-sub">
                    <span>SSID: Wi-Fi 6</span>
                    <span>Uptime: <span id="sys-uptime">--</span></span>
                </div>
            </div>

        </div>

        <!-- Controls Toolbar -->
        <div class="action-bar">
            <div class="action-left">
                <button class="btn btn-cyan" onclick="runAction('display-off')">
                    🌙 Display Ausschalten (0W)
                </button>
                <button class="btn btn-dark" onclick="sendCmd('battery')">
                    🔋 Akku-Diagnose
                </button>
                <button class="btn btn-dark" onclick="sendCmd('htop || top')">
                    📊 Top / Prozesse
                </button>
                <button class="btn btn-dark" onclick="sendCmd('ip -br addr; iw dev wlan0 info 2>/dev/null')">
                    🌐 WLAN-Info
                </button>
                <button class="btn btn-dark" onclick="sendCmd('clear')">
                    🧹 Terminal Leeren
                </button>
            </div>
            <div>
                <span id="toast" class="toast-msg">Aktion ausgeführt!</span>
            </div>
        </div>

        <!-- Interactive Web Terminal Frame -->
        <div class="terminal-container" id="term-box">
            <div class="terminal-titlebar">
                <div class="traffic-lights">
                    <div class="traffic-dot dot-red"></div>
                    <div class="traffic-dot dot-yellow"></div>
                    <div class="traffic-dot dot-green"></div>
                </div>
                <div class="term-title">
                    <span>●</span> root@galaxy-s20plus: ~ (ash)
                </div>
                <div class="term-actions">
                    <button class="term-btn" title="Neu laden" onclick="reloadTerm()">🔄</button>
                    <button class="term-btn" title="Vollbild" onclick="toggleFullscreen()">🗖</button>
                </div>
            </div>
            <iframe id="term-iframe" class="terminal-viewport" src=""></iframe>
        </div>

    </main>

    <!-- Footer -->
    <footer>
        <div>Samsung Galaxy S20+ 4G (SM-G985F / y2slte) • Headless Alpine Server</div>
        <div>SSH: root@10.42.0.2:22 • Web: Port 80 / 7681</div>
    </footer>

    <script>
        // Set dynamic iframe host matching the current browser URL
        const host = window.location.hostname || '10.42.0.2';
        const termIframe = document.getElementById('term-iframe');
        termIframe.src = 'http://' + host + ':7681';

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.opacity = '1';
            setTimeout(() => { t.style.opacity = '0'; }, 2500);
        }

        async function updateStats() {
            try {
                const res = await fetch('/api/status');
                if (!res.ok) return;
                const d = await res.json();

                // Battery
                if (d.battery) {
                    const cap = d.battery.capacity || 0;
                    document.getElementById('bat-cap').innerText = cap;
                    document.getElementById('bat-bar').style.width = cap + '%';
                    document.getElementById('bat-volt').innerText = d.battery.voltage_mv + ' mV';
                    document.getElementById('bat-temp').innerText = d.battery.temp_c + ' °C';
                    
                    if (cap <= 15) {
                        document.getElementById('bat-bar').style.background = 'linear-gradient(90deg, #f43f5e, #f59e0b)';
                    } else {
                        document.getElementById('bat-bar').style.background = 'linear-gradient(90deg, #06b6d4, #10b981)';
                    }
                }

                // RAM
                if (d.mem) {
                    document.getElementById('ram-used').innerText = d.mem.used_mb;
                    document.getElementById('ram-total').innerText = d.mem.total_mb;
                    document.getElementById('ram-free').innerText = d.mem.free_mb;
                    document.getElementById('ram-pct').innerText = d.mem.percent + '%';
                    document.getElementById('ram-bar').style.width = d.mem.percent + '%';
                }

                // System
                if (d.system) {
                    document.getElementById('sys-uptime').innerText = d.system.uptime || '--';
                }

            } catch (err) {
                console.error("Telemetry fetch failed", err);
            }
        }

        async function runAction(action) {
            try {
                showToast("Ausführen: " + action + "...");
                const res = await fetch('/api/action/' + action, { method: 'POST' });
                const json = await res.json();
                showToast(json.message || "Erfolgreich!");
                updateStats();
            } catch (err) {
                showToast("Fehler bei " + action);
            }
        }

        function sendCmd(cmd) {
            showToast("Befehl an Terminal: " + cmd);
            // Focus iframe so keyboard can type or open direct
            termIframe.contentWindow?.focus();
        }

        function reloadTerm() {
            termIframe.src = termIframe.src;
            showToast("Terminal neu verbunden");
        }

        function toggleFullscreen() {
            const box = document.getElementById('term-box');
            if (!document.fullscreenElement) {
                box.requestFullscreen().catch(err => alert("Fullscreen error: " + err.message));
            } else {
                document.exitFullscreen();
            }
        }

        // Poll telemetry every 3 seconds
        setInterval(updateStats, 3000);
        updateStats();
    </script>
</body>
</html>
"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/status":
            data = {
                "battery": get_battery(),
                "mem": get_mem(),
                "system": get_system()
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/action/display-off":
            try:
                subprocess.run(["/usr/bin/display-off"], timeout=5)
                res = {"status": "ok", "message": "Display auf 0W geschaltet!"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif parsed.path == "/api/action/display-on":
            try:
                subprocess.run(["/usr/bin/display-on"], timeout=5)
                res = {"status": "ok", "message": "Display eingeschaltet"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence standard HTTP access log
        return

class S20HTTPServer(HTTPServer):
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)
        self.server_name = "10.42.0.2"
        self.server_port = self.server_address[1]

def main():
    print(f"[*] Starting S20+ Server Control Center on Port {PORT}...")
    server = S20HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
