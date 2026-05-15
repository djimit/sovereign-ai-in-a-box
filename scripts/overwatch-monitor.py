#!/usr/bin/env python3
"""
Overwatch Monitor — Container health + self-healing + Telegram alerts.

Draait als long-running process (systemd service) op de workstation.
Checkt elke 60s alle Docker containers, probeert unhealthy containers
te herstellen, en stuurt Telegram alerts bij persistente failures.

Daily health summary om 07:00 via Telegram.
"""

import json
import os
import subprocess
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuratie ───────────────────────────────────────

CHECK_INTERVAL = 60                # seconden tussen health checks
MAX_REPAIR_ATTEMPTS = 2            # bij 2+ failed repairs → alert
HEALTH_SUMMARY_HOUR = 7            # dagelijkse summary om 07:00
HEALTH_SUMMARY_MINUTE = 0

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
LOG_FILE = Path(os.environ.get("OVERWATCH_LOG", "/opt/ai-in-a-box/logs/overwatch.log"))

# Containers die genegeerd worden (niet kritiek of extern beheerd)
IGNORED_CONTAINERS = {
    "suna-build", "suna-setup",  # bouw containers
}

# Herstelcommando's per container (name → shell commando)
REPAIR_COMMANDS: dict[str, str] = {
    "hermes":            "docker restart hermes",
    "openclaw":          "docker restart openclaw",
    "ag2-core":          "cd ~/workspace/ag2 && docker compose up -d ag2-core",
    "ag2-gateway":       "cd ~/workspace/ag2 && docker compose up -d ag2-gateway",
    "litellm-proxy":     "cd ~/workspace/litellm && docker compose up -d",
    "qdrant":            "docker restart qdrant",
    "prometheus":        "docker restart prometheus",
    "grafana":           "docker restart grafana",
    "n8n":               "cd ~/workspace/n8n && docker compose up -d",
    "searxng":           "docker restart searxng",
    "research-agent":    "docker restart research-agent",
    "agentic-reports":   "cd ~/workspace/agentic-reports && docker compose up -d",
    "marimo-notebooks":  "docker restart marimo-notebooks",
    "langgraph-postgres":"docker restart langgraph-postgres",
    "ruvector-postgres": "docker restart ruvector-postgres",
}

# ─── Telegram integratie ────────────────────────────────

def telegram_send(message: str) -> bool:
    """Stuur een Markdown-bericht via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_notification": False,
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def telegram_send_silent(message: str) -> bool:
    """Stuur een stil bericht (geen notificatie)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_notification": True,
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False

# ─── Docker health ──────────────────────────────────────

def get_container_states() -> dict[str, dict]:
    """Geeft {container_name: {status, healthy, uptime, ...}} via docker ps."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--all", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
            capture_output=True, text=True, timeout=15
        )
    except Exception:
        return {}

    states = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, status, image = parts[0], parts[1], parts[2]

        is_running = status.startswith("Up")
        is_healthy = "healthy" not in status.lower() or "(healthy)" in status

        # Docker native health check
        health = "unknown"
        if "(healthy)" in status:
            health = "healthy"
        elif "(unhealthy)" in status:
            health = "unhealthy"
            is_healthy = False
        elif "(health: starting)" in status:
            health = "starting"

        states[name] = {
            "status": status,
            "running": is_running,
            "health": health,
            "image": image,
        }

    return states


def is_critical(container_name: str) -> bool:
    """Bepaal of een container kritiek is (moet draaien)."""
    if container_name in IGNORED_CONTAINERS:
        return False
    return True


def attempt_repair(container_name: str) -> bool:
    """Probeer een container te herstellen. Geeft True als herstel gelukt is."""
    cmd = REPAIR_COMMANDS.get(container_name)
    if not cmd:
        cmd = f"docker restart {container_name}"

    log(f"  🔧 Repair attempt: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        success = result.returncode == 0
        if success:
            log(f"  ✅ Repair OK: {container_name}")
        else:
            log(f"  ❌ Repair failed: {container_name} — {result.stderr.strip()[:200]}")
        return success
    except Exception as e:
        log(f"  ❌ Repair exception: {container_name} — {e}")
        return False


# ─── Disk check ─────────────────────────────────────────

def get_disk_usage(mount: str = "/") -> dict:
    """Geeft disk usage percentages voor kritieke mounts."""
    try:
        result = subprocess.run(
            ["df", "-h", mount, "/home", "/opt"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        disks = {}
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks[parts[5]] = {"size": parts[1], "used_pct": parts[4]}
        return disks
    except Exception:
        return {}


# ─── Logging ────────────────────────────────────────────

def log(message: str):
    """Log met timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {message}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ─── Health summary ─────────────────────────────────────

def build_health_summary(repair_counts: dict[str, int]) -> str:
    """Bouw een Telegram-ready health summary."""
    containers = get_container_states()
    disk = get_disk_usage()

    running = sum(1 for c in containers.values() if c["running"])
    total = len(containers)
    unhealthy = [n for n, c in containers.items() if c["health"] == "unhealthy"]
    stopped = [n for n, c in containers.items() if not c["running"] and is_critical(n)]

    now = datetime.now(timezone.utc)
    lines = [
        f"*Overwatch Health — {now.strftime('%d %b %Y %H:%M')} UTC*",
        "",
        f"📦 Containers: *{running}/{total}* running",
    ]

    if unhealthy:
        lines.append(f"⚠️  Unhealthy: {', '.join(f'`{n}`' for n in unhealthy)}")
    if stopped:
        lines.append(f"🔴 Stopped: {', '.join(f'`{n}`' for n in stopped)}")

    # Repairs
    if repair_counts:
        repaired = [f"`{n}`" for n, c in repair_counts.items() if c > 0]
        if repaired:
            lines.append(f"🔧 Repairs (24h): {', '.join(repaired)}")

    # Disk
    lines.append("")
    for mount, info in disk.items():
        pct = info["used_pct"].rstrip("%")
        icon = "🟢" if int(pct) < 80 else ("🟡" if int(pct) < 95 else "🔴")
        lines.append(f"{icon} {mount}: {info['used_pct']} used ({info['size']})")

    # Emergent Communication
    try:
        req = urllib.request.Request("http://localhost:8008/stats")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            concepts = data.get("concepts", "?")
            lines.append(f"🧠 Concepts: {concepts}")
    except Exception:
        lines.append("🧠 Concepts: API offline")

    # Ollama modellen
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = len(data.get("models", []))
            lines.append(f"🤖 Ollama modellen: {models}")
    except Exception:
        lines.append("🤖 Ollama: API offline")

    return "\n".join(lines)


# ─── Main loop ──────────────────────────────────────────

def main():
    log("🚀 Overwatch Monitor starting...")

    global TELEGRAM_CHAT_ID

    # Repair tracking: container_name → count (reset na succesvolle repair)
    repair_counts: dict[str, int] = defaultdict(int)
    # Track laatste summary dag zodat we niet dubbel sturen
    last_summary_date: str = ""

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_send_silent("🟢 *Overwatch Monitor* started — watching containers...")
    elif TELEGRAM_BOT_TOKEN:
        log("⚠️  TELEGRAM_CHAT_ID niet geset — probeer auto-discovery...")
        # Auto-discover: haal chat_id uit recente Telegram updates
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?limit=1"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("ok") and data["result"]:
                    msg = data["result"][-1].get("message", {})
                    chat = msg.get("chat", {})
                    discovered_id = str(chat.get("id", ""))
                    if discovered_id:
                        TELEGRAM_CHAT_ID = discovered_id
                        log(f"✅ Chat ID auto-discovered: {discovered_id}")
                        telegram_send_silent("🟢 *Overwatch Monitor* started — watching containers...")
                    else:
                        log("⚠️  Kon chat ID niet ontdekken — stuur een bericht naar @OverwatchDjimit_bot en restart")
                else:
                    log("⚠️  Geen Telegram updates gevonden — stuur een bericht naar de bot")
        except Exception as e:
            log(f"⚠️  Auto-discovery mislukt: {e}")
    else:
        log("⚠️  TELEGRAM_BOT_TOKEN niet geset — Telegram uitgeschakeld")

    while True:
        loop_start = time.time()
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        try:
            # ─── Container health check ───────────────────
            containers = get_container_states()
            issues_found = 0

            for name, state in containers.items():
                if not is_critical(name):
                    continue

                needs_repair = False
                reason = ""

                if not state["running"]:
                    needs_repair = True
                    reason = "stopped"
                elif state["health"] == "unhealthy":
                    needs_repair = True
                    reason = "unhealthy"

                if not needs_repair:
                    # Container is OK — reset repair counter
                    if repair_counts[name] > 0:
                        log(f"✅ {name} recovered — resetting counter (was {repair_counts[name]})")
                    repair_counts[name] = 0
                    continue

                issues_found += 1
                repair_counts[name] += 1
                attempt_num = repair_counts[name]

                log(f"⚠️  {name} is {reason} (attempt {attempt_num}/{MAX_REPAIR_ATTEMPTS})")

                # Altijd proberen te herstellen
                repaired = attempt_repair(name)

                if repaired:
                    repair_counts[name] = 0
                    telegram_send_silent(f"🔧 *{name}* gerepareerd — `docker restart` succesvol")
                elif attempt_num >= MAX_REPAIR_ATTEMPTS:
                    # Escalatie: >2 failed repairs → Telegram alert
                    alert_msg = (
                        f"🚨 *CRITICAL: {name} niet te herstellen!*\n"
                        f"Status: _{reason}_\n"
                        f"Pogingen: {attempt_num}\n"
                        f"Laatste actie: `{REPAIR_COMMANDS.get(name, f'docker restart {name}')}`\n\n"
                        f"Handmatige interventie nodig:\n"
                        f"`ssh djimit@192.168.1.28 'docker logs {name} --tail 50'`"
                    )
                    telegram_send(alert_msg)
                    log(f"  🚨 CRITICAL alert sent for {name}")
                    # Reset counter na alert — voorkomt spam
                    repair_counts[name] = 0

            if issues_found == 0:
                pass  # Alles OK — stil

            # ─── Daily health summary ──────────────────
            target_hour = HEALTH_SUMMARY_HOUR
            target_minute = HEALTH_SUMMARY_MINUTE
            if (now.hour == target_hour and now.minute < 5 and today != last_summary_date):
                summary = build_health_summary(dict(repair_counts))
                telegram_send(summary)
                last_summary_date = today
                log("📊 Daily health summary sent")

            # ─── Disk check (alleen alerteren bij >95%) ──
            disk = get_disk_usage()
            for mount, info in disk.items():
                pct = info["used_pct"].rstrip("%")
                if int(pct) >= 95:
                    telegram_send(f"🔴 *Disk alert:* {mount} = {info['used_pct']} ({info['size']})")

        except Exception as e:
            log(f"❌ Main loop error: {e}")
            # Kort wachten bij fout, dan doorgaan
            time.sleep(10)

        # ─── Wacht tot volgende check ──────────────────
        elapsed = time.time() - loop_start
        sleep_time = max(0, CHECK_INTERVAL - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    main()
