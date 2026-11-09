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
from urllib.parse import urlparse, parse_qs

PORT = 80
DISPLAY_STATE_FILE = "/var/run/display_blank"

def get_display_state():
    if os.path.exists(DISPLAY_STATE_FILE):
        try:
            with open(DISPLAY_STATE_FILE) as f:
                return f.read().strip()
        except Exception:
            pass
    return "off"  # Default after boot is 0W dark mode

def set_display_state(state):
    try:
        os.makedirs(os.path.dirname(DISPLAY_STATE_FILE), exist_ok=True)
        with open(DISPLAY_STATE_FILE, "w") as f:
            f.write(state)
    except Exception:
        pass

def action_display_off():
    # Try dedicated script first
    if os.path.isfile("/usr/bin/display-off") and os.access("/usr/bin/display-off", os.X_OK):
        try:
            subprocess.run(["/usr/bin/display-off"], timeout=5)
            set_display_state("off")
            return True, "Display auf 0W geschaltet (Panel geblankt)"
        except Exception:
            pass

    # Direct fallback in Python
    try:
        # 1. Backlight to 0
        bl_dirs = "/sys/class/backlight"
        if os.path.isdir(bl_dirs):
            for b in os.listdir(bl_dirs):
                b_path = os.path.join(bl_dirs, b, "brightness")
                if os.path.isfile(b_path):
                    with open(b_path, "w") as f:
                        f.write("0")

        # 2. Framebuffer blanking
        fb_blank = "/sys/class/graphics/fb0/blank"
        if os.path.isfile(fb_blank):
            try:
                with open(fb_blank, "w") as f:
                    f.write("4")
            except Exception:
                with open(fb_blank, "w") as f:
                    f.write("1")

        # 3. Decon trigger if available
        if os.path.isfile("/usr/bin/decon-tool") and os.access("/usr/bin/decon-tool", os.X_OK):
            subprocess.run(["/usr/bin/decon-tool", "0x1281"], timeout=2)

        set_display_state("off")
        return True, "Display auf 0W geschaltet (Panel geblankt)"
    except Exception as e:
        return False, f"Fehler beim Abschalten: {e}"

def action_display_on():
    # Try dedicated script first
    if os.path.isfile("/usr/bin/display-on") and os.access("/usr/bin/display-on", os.X_OK):
        try:
            subprocess.run(["/usr/bin/display-on"], timeout=5)
            set_display_state("on")
            return True, "Display eingeschaltet"
        except Exception:
            pass

    # Direct fallback in Python
    try:
        fb_blank = "/sys/class/graphics/fb0/blank"
        if os.path.isfile(fb_blank):
            with open(fb_blank, "w") as f:
                f.write("0")

        bl_dirs = "/sys/class/backlight"
        if os.path.isdir(bl_dirs):
            for b in os.listdir(bl_dirs):
                max_path = os.path.join(bl_dirs, b, "max_brightness")
                b_path = os.path.join(bl_dirs, b, "brightness")
                target_val = "128"
                if os.path.isfile(max_path):
                    try:
                        with open(max_path) as mf:
                            target_val = mf.read().strip()
                    except Exception:
                        pass
                if os.path.isfile(b_path):
                    with open(b_path, "w") as f:
                        f.write(target_val)

        set_display_state("on")
        return True, "Display eingeschaltet"
    except Exception as e:
        return False, f"Fehler beim Einschalten: {e}"

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
            v_val = info["voltage_mv"] / 1000.0
            i_val = abs(info["current_ma"]) / 1000.0
            info["power_w"] = round(v_val * i_val, 2)
        except Exception:
            pass
    return info

def get_cpu_info():
    freqs = {"a55_mhz": 0, "a76_mhz": 0, "m5_mhz": 0}
    try:
        p0 = "/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq"
        if os.path.isfile(p0):
            with open(p0) as f:
                freqs["a55_mhz"] = int(f.read().strip()) // 1000
    except Exception:
        pass
    try:
        p4 = "/sys/devices/system/cpu/cpufreq/policy4/scaling_cur_freq"
        if os.path.isfile(p4):
            with open(p4) as f:
                freqs["a76_mhz"] = int(f.read().strip()) // 1000
    except Exception:
        pass
    try:
        p6 = "/sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq"
        if os.path.isfile(p6):
            with open(p6) as f:
                freqs["m5_mhz"] = int(f.read().strip()) // 1000
    except Exception:
        pass

    # Read dynamic thermal zones
    temps = {}
    max_t = 0
    tz_base = "/sys/class/thermal"
    if os.path.isdir(tz_base):
        for z in sorted(os.listdir(tz_base)):
            if not z.startswith("thermal_zone"):
                continue
            z_path = os.path.join(tz_base, z)
            t_type = "unknown"
            type_f = os.path.join(z_path, "type")
            temp_f = os.path.join(z_path, "temp")
            if os.path.isfile(type_f):
                try:
                    with open(type_f) as f:
                        t_type = f.read().strip()
                except Exception:
                    pass
            if "battery" in t_type or "max170xx" in t_type:
                continue
            if os.path.isfile(temp_f):
                try:
                    with open(temp_f) as f:
                        raw_t = int(f.read().strip())
                        val_c = round(raw_t / 1000, 1)
                        if 10 <= val_c <= 125:
                            temps[t_type] = val_c
                            if val_c > max_t:
                                max_t = val_c
                except Exception:
                    pass

    # Thermal guard level & operating mode
    guard_lvl = "0"
    if os.path.isfile("/data/guard_level"):
        try:
            with open("/data/guard_level") as f:
                guard_lvl = f.read().strip()
        except Exception:
            pass

    cur_mode = "auto"
    if os.path.isfile("/data/modus"):
        try:
            with open("/data/modus") as f:
                cur_mode = f.read().strip()
        except Exception:
            pass

    return {
        "freqs": freqs,
        "temps": temps,
        "max_temp": max_t if max_t > 0 else 45.0,
        "guard_level": guard_lvl,
        "modus": cur_mode
    }

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

        .card-val {
            font-size: 1.6rem;
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

        /* CPU Badges */
        .cluster-badges {
            display: flex;
            gap: 0.4rem;
            margin-top: 0.2rem;
            flex-wrap: wrap;
        }

        .badge-chip {
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
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
            padding: 0.85rem 1.25rem;
            border-radius: 12px;
        }

        .action-left {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.45rem 0.85rem;
            border-radius: 8px;
            font-size: 0.78rem;
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

        .btn-emerald {
            background: rgba(16, 185, 129, 0.12);
            color: var(--emerald);
            border-color: rgba(16, 185, 129, 0.3);
        }
        .btn-emerald:hover {
            background: rgba(16, 185, 129, 0.25);
            border-color: var(--emerald);
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

        .btn-amber {
            background: rgba(245, 158, 11, 0.12);
            color: var(--amber);
            border-color: rgba(245, 158, 11, 0.3);
        }
        .btn-amber:hover {
            background: rgba(245, 158, 11, 0.25);
        }

        .btn-rose {
            background: rgba(244, 63, 94, 0.12);
            color: var(--rose);
            border-color: rgba(244, 63, 94, 0.3);
        }
        .btn-rose:hover {
            background: rgba(244, 63, 94, 0.25);
        }

        .toast-msg {
            font-size: 0.75rem;
            color: var(--emerald);
            font-family: 'JetBrains Mono', monospace;
            opacity: 0;
            transition: opacity 0.3s;
        }

        /* Diagnostic Console Box */
        .diag-box {
            background: #090d14;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
        }

        .diag-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-muted);
        }

        .diag-output {
            background: #05080f;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 0.85rem 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #38bdf8;
            max-height: 240px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }

        .cmd-input-bar {
            display: flex;
            gap: 0.5rem;
        }

        .cmd-input {
            flex: 1;
            background: #05080f;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.45rem 0.75rem;
            color: var(--text-main);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            outline: none;
        }
        .cmd-input:focus {
            border-color: var(--cyan);
        }

        /* Terminal Window Container */
        .terminal-container {
            flex: 1;
            min-height: 520px;
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
            min-height: 480px;
            border: none;
            background: #090d14;
        }

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
            header, main, footer { padding: 1rem; }
            .stats-grid { grid-template-columns: 1fr; }
            .terminal-container { min-height: 400px; }
            .header-meta { display: none; }
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header>
        <div class="brand">
            <div class="device-badge">S20+</div>
            <div class="title-group">
                <h1>Samsung Galaxy S20+ <span style="font-size:0.75rem; color:var(--cyan); font-weight:600; padding:2px 8px; border-radius:4px; background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.25);">SERVER</span></h1>
                <p>Alpine Linux 3.21 • Exynos 990 Tri-Cluster • 8GB LPDDR5</p>
            </div>
        </div>
        <div class="header-meta">
            <div class="status-pill">
                <div class="pulse-dot"></div>
                ONLINE
            </div>
            <a href="/terminal" onclick="window.open('http://' + window.location.hostname + ':7681'); return false;" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:0.35rem 0.75rem;">
                Direkt-Terminal (7681)
            </a>
        </div>
    </header>

    <!-- Main -->
    <main>

        <!-- Stats Grid (6 Cards) -->
        <div class="stats-grid">
            
            <!-- Battery Card -->
            <div class="card">
                <div class="card-header">
                    <span>Akku & Power</span>
                    <span>BAT</span>
                </div>
                <div class="card-val">
                    <span id="bat-cap">--</span><span class="unit">%</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="bat-bar" class="progress-bar-fill" style="width: 0%;"></div>
                </div>
                <div class="card-sub">
                    <span id="bat-volt">-- mV</span>
                    <span id="bat-pwr">-- W</span>
                </div>
            </div>

            <!-- CPU Frequency Card -->
            <div class="card">
                <div class="card-header">
                    <span>CPU Taktfrequenzen</span>
                    <span>DVFS</span>
                </div>
                <div class="card-val" style="font-size: 1.35rem; color: var(--cyan);">
                    <span id="cpu-load">Load: --</span>
                </div>
                <div class="cluster-badges">
                    <div class="badge-chip" style="color:var(--emerald);">A55: <span id="f-a55">--</span> MHz</div>
                    <div class="badge-chip" style="color:var(--cyan);">A76: <span id="f-a76">--</span> MHz</div>
                    <div class="badge-chip" style="color:var(--purple);">M5: <span id="f-m5">--</span> MHz</div>
                </div>
                <div class="card-sub">
                    <span>Governor: schedutil</span>
                    <span id="cur-modus" style="font-weight:700; color:var(--cyan);">Modus: auto</span>
                </div>
            </div>

            <!-- Thermal & Guard Card -->
            <div class="card">
                <div class="card-header">
                    <span>CPU Temperatur</span>
                    <span>TMU</span>
                </div>
                <div class="card-val">
                    <span id="cpu-temp">--</span><span class="unit">°C</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="temp-bar" class="progress-bar-fill" style="width: 40%; background: linear-gradient(90deg, #10b981, #06b6d4);"></div>
                </div>
                <div class="card-sub">
                    <span>Thermal Guard: <strong id="guard-lvl" style="color:var(--emerald);">Level 0</strong></span>
                    <span id="temp-status">Normal</span>
                </div>
            </div>

            <!-- AMOLED Display Card -->
            <div class="card">
                <div class="card-header">
                    <span>AMOLED Display</span>
                    <span>PANEL</span>
                </div>
                <div class="card-val" style="font-size: 1.35rem; color: var(--emerald);">
                    <span id="disp-status">0W Dark Mode</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="disp-bar" class="progress-bar-fill" style="width: 100%; background: linear-gradient(90deg, #10b981, #06b6d4);"></div>
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
                    <span>MEM</span>
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
                    <span>NET</span>
                </div>
                <div class="card-val" style="font-size: 1.3rem; color: var(--cyan);" id="sys-ip">
                    10.42.0.2
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: 100%; background: var(--cyan);"></div>
                </div>
                <div class="card-sub">
                    <span id="sys-ssid">Wi-Fi 6</span>
                    <span>Up: <span id="sys-uptime">--</span></span>
                </div>
            </div>

        </div>

        <!-- Controls Toolbar -->
        <div class="action-bar">
            <div class="action-left">
                <!-- Display Toggles -->
                <button class="btn btn-cyan" onclick="runAction('display-off')">
                    Display Aus (0W)
                </button>
                <button class="btn btn-dark" onclick="runAction('display-on')">
                    Display An
                </button>

                <!-- Mode Selectors -->
                <span style="color:var(--border); margin:0 4px;">|</span>
                <button class="btn btn-emerald" onclick="setMode('auto')">
                    Modus: Auto
                </button>
                <button class="btn btn-amber" onclick="setMode('sparsam')">
                    Modus: Sparsam
                </button>
                <button class="btn btn-rose" onclick="setMode('boost')">
                    Modus: Boost
                </button>

                <!-- Quick Diag -->
                <span style="color:var(--border); margin:0 4px;">|</span>
                <button class="btn btn-dark" onclick="execCmd('top -b -n 1 | head -n 18')">
                    Top Prozesse
                </button>
                <button class="btn btn-dark" onclick="execCmd('ip -br addr; echo \"---\"; iw dev wlan0 info 2>/dev/null; iw dev wlan0 link 2>/dev/null')">
                    WLAN Details
                </button>
                <button class="btn btn-dark" onclick="execCmd('df -h / /data; echo \"---\"; free -m')">
                    Speicher (df/free)
                </button>
                <button class="btn btn-dark" onclick="execCmd('dmesg | tail -n 20')">
                    Kernel Log
                </button>
            </div>
            <div>
                <span id="toast" class="toast-msg">Aktion ausgefuehrt!</span>
            </div>
        </div>

        <!-- Live Diagnostic Console -->
        <div class="diag-box">
            <div class="diag-header">
                <span>DIAGNOSE & BEFEHLS-AUSGABE</span>
                <div style="display:flex; gap:0.5rem;">
                    <button class="term-btn" onclick="copyDiag()">Kopieren</button>
                    <button class="term-btn" onclick="clearDiag()">Leeren</button>
                </div>
            </div>
            <div class="diag-output" id="diag-out">Waehle oben eine Diagnose-Aktion oder gib unten einen Befehl ein...</div>
            <div class="cmd-input-bar">
                <input type="text" id="custom-cmd" class="cmd-input" placeholder="Befehl eingeben (z.B. ps aux, uptime, date, cat /proc/cpuinfo)..." onkeydown="if(event.key==='Enter') sendCustomCmd()">
                <button class="btn btn-cyan" onclick="sendCustomCmd()">Senden</button>
            </div>
        </div>

        <!-- Interactive Web Terminal Frame (ttyd) -->
        <div class="terminal-container" id="term-box">
            <div class="terminal-titlebar">
                <div class="traffic-lights">
                    <div class="traffic-dot dot-red"></div>
                    <div class="traffic-dot dot-yellow"></div>
                    <div class="traffic-dot dot-green"></div>
                </div>
                <div class="term-title">
                    <span>●</span> root@galaxy-s20plus: ~ (ash via ttyd)
                </div>
                <div class="term-actions">
                    <button class="term-btn" title="Neu laden" onclick="reloadTerm()">Reload</button>
                    <button class="term-btn" title="Vollbild" onclick="toggleFullscreen()">Fullscreen</button>
                </div>
            </div>
            <iframe id="term-iframe" class="terminal-viewport" src=""></iframe>
        </div>

    </main>

    <!-- Footer -->
    <footer>
        <div>Samsung Galaxy S20+ (SM-G985F / y2slte) • Headless Linux Server</div>
        <div>SSH: root@10.42.0.2:22 • Web: Port 80 / Terminal: Port 7681</div>
    </footer>

    <script>
        const host = window.location.hostname || '10.42.0.2';
        const termIframe = document.getElementById('term-iframe');
        termIframe.src = 'http://' + host + ':7681';

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.opacity = '1';
            setTimeout(() => { t.style.opacity = '0'; }, 3000);
        }

        function reloadTerm() {
            termIframe.src = termIframe.src;
            showToast("Terminal neu geladen");
        }

        function toggleFullscreen() {
            const box = document.getElementById('term-box');
            if (!document.fullscreenElement) {
                box.requestFullscreen().catch(err => alert("Fullscreen error: " + err.message));
            } else {
                document.exitFullscreen();
            }
        }

        function clearDiag() {
            document.getElementById('diag-out').innerText = "Bereit...";
        }

        function copyDiag() {
            const text = document.getElementById('diag-out').innerText;
            navigator.clipboard.writeText(text).then(() => showToast("In Zwischenablage kopiert!"));
        }

        async function execCmd(cmd) {
            const outBox = document.getElementById('diag-out');
            outBox.innerText = "[*] Führe aus: " + cmd + "...";
            try {
                const res = await fetch('/api/action/exec', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cmd: cmd })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    outBox.innerText = "$ " + cmd + "\\n\\n" + (data.output || "(Keine Ausgabe)");
                } else {
                    outBox.innerText = "[-] Fehler: " + (data.message || "Unbekannt");
                }
            } catch (err) {
                outBox.innerText = "[-] Netzwerkfehler: " + err.message;
            }
        }

        function sendCustomCmd() {
            const input = document.getElementById('custom-cmd');
            const cmd = input.value.trim();
            if (cmd) {
                execCmd(cmd);
                input.value = '';
            }
        }

        async function runAction(action) {
            try {
                showToast("Führe " + action + " aus...");
                const res = await fetch('/api/action/' + action, { method: 'POST' });
                const json = await res.json();
                showToast(json.message || "Aktion abgeschlossen");
                updateStats();
            } catch (err) {
                showToast("Fehler bei " + action);
            }
        }

        async function setMode(mode) {
            try {
                showToast("Setze Modus: " + mode + "...");
                const res = await fetch('/api/action/set-mode?mode=' + encodeURIComponent(mode), { method: 'POST' });
                const json = await res.json();
                showToast(json.message || ("Modus gesetzt: " + mode));
                updateStats();
            } catch (err) {
                showToast("Fehler beim Setzen von " + mode);
            }
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
                    document.getElementById('bat-pwr').innerText = d.battery.power_w + ' W';
                    if (cap <= 15) {
                        document.getElementById('bat-bar').style.background = 'linear-gradient(90deg, #f43f5e, #f59e0b)';
                    } else {
                        document.getElementById('bat-bar').style.background = 'linear-gradient(90deg, #06b6d4, #10b981)';
                    }
                }

                // CPU
                if (d.cpu) {
                    const f = d.cpu.freqs || {};
                    document.getElementById('f-a55').innerText = f.a55_mhz || '--';
                    document.getElementById('f-a76').innerText = f.a76_mhz || '--';
                    document.getElementById('f-m5').innerText = f.m5_mhz || '--';

                    const temp = d.cpu.max_temp || '--';
                    document.getElementById('cpu-temp').innerText = temp;
                    const tempPct = Math.min(100, Math.max(10, ((temp - 25) / (90 - 25)) * 100));
                    document.getElementById('temp-bar').style.width = tempPct + '%';

                    if (temp >= 85) {
                        document.getElementById('temp-bar').style.background = 'linear-gradient(90deg, #f59e0b, #ef4444)';
                        document.getElementById('temp-status').innerText = 'Drosselung!';
                        document.getElementById('temp-status').style.color = '#ef4444';
                    } else if (temp >= 70) {
                        document.getElementById('temp-bar').style.background = 'linear-gradient(90deg, #10b981, #f59e0b)';
                        document.getElementById('temp-status').innerText = 'Erhoeht';
                        document.getElementById('temp-status').style.color = '#f59e0b';
                    } else {
                        document.getElementById('temp-bar').style.background = 'linear-gradient(90deg, #10b981, #06b6d4)';
                        document.getElementById('temp-status').innerText = 'Kuehl';
                        document.getElementById('temp-status').style.color = '#10b981';
                    }

                    document.getElementById('guard-lvl').innerText = 'Level ' + (d.cpu.guard_level || '0');
                    document.getElementById('cur-modus').innerText = 'Modus: ' + (d.cpu.modus || 'auto');
                }

                // Display
                if (d.display) {
                    const isOff = d.display.state === 'off';
                    const dispEl = document.getElementById('disp-status');
                    if (isOff) {
                        dispEl.innerText = '0W Dark Mode';
                        dispEl.style.color = 'var(--emerald)';
                    } else {
                        dispEl.innerText = 'Display Aktiv';
                        dispEl.style.color = 'var(--cyan)';
                    }
                }

                // Memory
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
                    document.getElementById('sys-ip').innerText = d.system.ip || '10.42.0.2';
                    document.getElementById('sys-ssid').innerText = d.system.ssid || 'Wi-Fi';
                    document.getElementById('cpu-load').innerText = 'Load: ' + (d.system.load || '--');
                }

            } catch (err) {
                console.error("Telemetry fetch failed", err);
            }
        }

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
                "cpu": get_cpu_info(),
                "mem": get_mem(),
                "system": get_system(),
                "display": {"state": get_display_state()}
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
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8", errors="ignore") if content_len > 0 else ""

        if parsed.path == "/api/action/display-off":
            ok, msg = action_display_off()
            res = {"status": "ok" if ok else "error", "message": msg}
            self._send_json(res)

        elif parsed.path == "/api/action/display-on":
            ok, msg = action_display_on()
            res = {"status": "ok" if ok else "error", "message": msg}
            self._send_json(res)

        elif parsed.path == "/api/action/set-mode":
            query = parse_qs(parsed.query)
            mode = query.get("mode", ["auto"])[0]
            if mode not in ["auto", "sparsam", "boost"]:
                mode = "auto"
            try:
                os.makedirs("/data", exist_ok=True)
                with open("/data/modus", "w") as f:
                    f.write(mode)
                # Trigger thermal guard limit update
                if os.path.isfile("/data/thermal_guard.sh"):
                    subprocess.run(["/bin/sh", "/data/thermal_guard.sh", "force"], timeout=3)
                elif os.path.isfile("/data/scripts/thermal_guard.sh"):
                    subprocess.run(["/bin/sh", "/data/scripts/thermal_guard.sh", "force"], timeout=3)
                res = {"status": "ok", "message": f"Modus auf '{mode}' gesetzt"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self._send_json(res)

        elif parsed.path == "/api/action/exec":
            cmd = ""
            if post_body:
                try:
                    body_json = json.loads(post_body)
                    cmd = body_json.get("cmd", "").strip()
                except Exception:
                    cmd = post_body.strip()
            if not cmd:
                self._send_json({"status": "error", "message": "Kein Befehl angegeben"})
                return

            try:
                # Execute in shell with 6 second timeout
                proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=6)
                res = {"status": "ok", "cmd": cmd, "output": proc.stdout}
            except subprocess.TimeoutExpired:
                res = {"status": "error", "message": "Befehls-Timeout (6s ueberschritten)"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self._send_json(res)

        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        return

class S20HTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        import socketserver
        import socket
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
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
