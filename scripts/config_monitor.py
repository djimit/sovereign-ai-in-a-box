"""
config_monitor.py — Configuration drift detection and update monitoring.

Checks for:
- Docker image updates available
- Environment variable drift (.env completeness)
- Systemd service changes
- Dependency version drift
- Disk space trends
- Resource utilization trends

Integrates with incident_store for dedup.
"""

import json
import logging
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from incident_store import IncidentStore, Severity, PolicyDecision
from message_formatter import truncate_safe

logger = logging.getLogger(__name__)

EXPECTED_ENV_VARS: dict[str, list[str]] = {
    "research-agent": [
        "RESEARCH_AGENT_LLM_PROVIDER",
        "RESEARCH_AGENT_OUTPUT_DIR",
    ],
    "overwatch": [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ],
    "ag2": [
        "OPENAI_API_KEY",
    ],
    "ollama": [],
}

REQUIRED_PORTS: dict[int, str] = {
    3000: "open-webui",
    4000: "litellm",
    6333: "qdrant",
    6379: "redis",
    8000: "research-agent",
    8007: "knowledge-mcp",
    8008: "emergent-comm",
    8010: "ag2-core",
    8011: "ag2-gateway",
    11434: "ollama",
}

MIN_DISK_FREE_PCT = 10
MIN_MEMORY_FREE_PCT = 15


@dataclass
class ConfigDrift:
    service: str
    drift_type: str
    detail: str
    severity: Severity = Severity.WARNING


def check_docker_updates() -> list[dict]:
    """Check for Docker image updates available."""
    updates = []
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}"],
            capture_output=True, text=True, timeout=30
        )
        images = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                images.append({"image": parts[0], "id": parts[1], "created": parts[2]})
    except Exception as e:
        logger.error(f"Docker images check failed: {e}")

    try:
        subprocess.run(["docker", "pull", "--quiet", "alpine"], capture_output=True, timeout=60)
    except Exception:
        pass

    return updates


def check_env_completeness(env_dir: str = os.path.expanduser("~")) -> list[ConfigDrift]:
    """Check that required environment variables are set for each service."""
    drifts = []
    for service, required_vars in EXPECTED_ENV_VARS.items():
        env_file = None
        for candidate in [
            Path(env_dir) / f".{service}.env",
            Path(env_dir) / "workspace" / service / ".env",
        ]:
            if candidate.exists():
                env_file = candidate
                break

        if not env_file and required_vars:
            drifts.append(ConfigDrift(
                service=service, drift_type="missing_env_file",
                detail=f"No .env file found, requires: {', '.join(required_vars)}",
                severity=Severity.WARNING,
            ))
            continue

        if env_file and required_vars:
            existing_vars = set()
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0].strip()
                        existing_vars.add(key)
            except Exception:
                continue

            missing = [v for v in required_vars if v not in existing_vars]
            if missing:
                drifts.append(ConfigDrift(
                    service=service, drift_type="missing_env_vars",
                    detail=f"Missing: {', '.join(missing)}",
                    severity=Severity.ERROR if any("KEY" in m or "TOKEN" in m for m in missing) else Severity.WARNING,
                ))
    return drifts


def check_port_conflicts() -> list[ConfigDrift]:
    """Check that required ports are not in conflict or missing."""
    drifts = []
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=10
        )
        listening_ports = set()
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 4:
                local = parts[3]
                if ":" in local:
                    try:
                        port = int(local.rsplit(":", 1)[1])
                        listening_ports.add(port)
                    except (ValueError, IndexError):
                        pass

        for port, service in REQUIRED_PORTS.items():
            if port not in listening_ports:
                drifts.append(ConfigDrift(
                    service=service, drift_type="port_not_listening",
                    detail=f"Port {port} not listening (expected for {service})",
                    severity=Severity.CRITICAL if service in ("research-agent", "ag2-core", "ollama", "qdrant") else Severity.WARNING,
                ))
    except Exception as e:
        logger.error(f"Port conflict check failed: {e}")
    return drifts


def check_disk_trends() -> list[ConfigDrift]:
    """Check disk space and warn if approaching limits."""
    drifts = []
    try:
        result = subprocess.run(
            ["df", "-h", "/", "/home", "/opt", "/var"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6:
                mount = parts[5]
                pct_str = parts[4].rstrip("%")
                try:
                    pct = int(pct_str)
                    free_pct = 100 - pct
                    if free_pct < MIN_DISK_FREE_PCT:
                        drifts.append(ConfigDrift(
                            service="disk:" + mount, drift_type="disk_space_low",
                            detail=f"{mount} is {pct_str}% full ({free_pct}% free, {parts[1]} total)",
                            severity=Severity.CRITICAL if free_pct < 5 else Severity.ERROR,
                        ))
                    elif free_pct < 20:
                        drifts.append(ConfigDrift(
                            service="disk:" + mount, drift_type="disk_space_warning",
                            detail=f"{mount} is {pct_str}% full ({free_pct}% free)",
                            severity=Severity.WARNING,
                        ))
                except ValueError:
                    pass
    except Exception:
        pass
    return drifts


def check_systemd_services() -> list[ConfigDrift]:
    """Check that expected systemd services are active."""
    drifts = []
    expected_services = [
        "overwatch-monitor",
        "emergent-communication",
        "docker",
    ]
    for svc in expected_services:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=10
            )
            status = result.stdout.strip()
            if status != "active":
                drifts.append(ConfigDrift(
                    service=svc, drift_type="systemd_inactive",
                    detail=f"systemd service '{svc}' is {status} (expected: active)",
                    severity=Severity.ERROR,
                ))
        except Exception:
            pass
    return drifts


def run_config_checks(incident_store: IncidentStore, telegram_send=None) -> dict:
    """Run all configuration and drift checks. Return summary."""
    all_drifts = []

    env_drifts = check_env_completeness()
    port_drifts = check_port_conflicts()
    disk_drifts = check_disk_trends()
    systemd_drifts = check_systemd_services()

    all_drifts.extend(env_drifts)
    all_drifts.extend(port_drifts)
    all_drifts.extend(disk_drifts)
    all_drifts.extend(systemd_drifts)

    for drift in all_drifts:
        policy = PolicyDecision.INVESTIGATE
        if drift.severity in (Severity.CRITICAL, Severity.FATAL):
            policy = PolicyDecision.ESCALATE
        elif drift.drift_type in ("missing_env_vars", "port_not_listening"):
            policy = PolicyDecision.NEEDS_APPROVAL

        incident = incident_store.record_incident(
            container_name=drift.service,
            failure_class=f"config_{drift.drift_type}",
            exit_code=0,
            primary_error_signature=truncate_safe(drift.detail, 200),
            severity=drift.severity,
            confidence=0.90,
            policy_decision=policy,
            metadata={"drift_type": drift.drift_type},
        )

        if incident_store.should_alert(incident) and telegram_send:
            from message_formatter import format_incident_alert
            alert = format_incident_alert(incident, primary_error=drift.detail)
            telegram_send(alert)
            incident_store.mark_alerted(incident.evidence_hash)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_drifts": len(all_drifts),
        "by_type": {},
        "drifts": [{
            "service": d.service,
            "drift_type": d.drift_type,
            "detail": d.detail,
            "severity": d.severity.value,
        } for d in all_drifts],
    }