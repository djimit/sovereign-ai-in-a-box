#!/usr/bin/env python3
"""
Overwatch v7 — Self-healing AI Operations with incident deduplication.

Changes from v6:
- Incident tracking with stable evidence_hash (container:failure_class:exit_code:error_sig)
- occurrence_count for repeated detections instead of duplicate alerts
- Debounce: investigate events use same pipeline as other alerts
- Word-boundary truncation: never cut mid-word in Telegram messages
- Failure classification from exit code + log patterns
- Cosmetic warning suppression
- Structured alert format with incident_id and occurrence count
- UAMS storage error handling (422 validation failures)
- No auto-repair for exit code 1 restart loops

Usage:
  python overwatch.py                  # Full scan + LLM rapport
  python overwatch.py --watch          # Auto-heal loop
  python overwatch.py --local          # llama3.1:8b
  python overwatch.py --get-chat-id    # Fetch Telegram chat ID
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.parse

from incident_store import (
    IncidentStore,
    Incident,
    IncidentStatus,
    Severity,
    PolicyDecision,
    compute_evidence_hash,
    DebounceConfig,
)
from container_failure_classifier import (
    classify_failure,
    get_container_exit_code,
    get_container_log_lines,
    is_cosmetic_warning,
)
from known_warnings import all_cosmetic, classify_log_noise
from message_formatter import (
    format_incident_alert,
    format_resolve_alert,
    format_occurrence_update,
    truncate_safe,
    extract_primary_error_signature,
)

# ── Load env ────────────────────────────────────────────
ENV_FILE = os.path.expanduser("~/.overwatch.env")
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            if val:
                os.environ[key] = val

# ── Config ──────────────────────────────────────────────
USE_LOCAL = "--local" in sys.argv
WATCH_MODE = "--watch" in sys.argv
GET_CHAT_ID = "--get-chat-id" in sys.argv

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")
MODEL = "llama3.1:8b" if USE_LOCAL else "deepseek-v4-pro:cloud"

INCIDENT_STORE_PATH = Path(os.environ.get(
    "OVERWATCH_INCIDENT_STORE",
    "/opt/ai-in-a-box/data/incident_store.json"
))

from agents import Agent, Runner, function_tool, set_tracing_disabled

set_tracing_disabled(True)

# ── Incident store ───────────────────────────────────────
incident_store = IncidentStore(INCIDENT_STORE_PATH)


# ── Chat ID Fetch ───────────────────────────────────────

def fetch_chat_id():
    if not TELEGRAM_BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN not set in ~/.overwatch.env")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data.get("result"):
            print("No messages found. Send a message to your bot, then retry.")
            return
        for u in data["result"]:
            msg = u.get("message", u.get("channel_post", {}))
            chat = msg.get("chat", {})
            cid = chat.get("id")
            if cid:
                title = chat.get("title", "") or f"{chat.get('first_name','')} {chat.get('last_name','')}".strip()
                print(f"Chat ID: {cid} - {title} ({chat.get('type','')})")
                print(f"\nAdd to ~/.overwatch.env:")
                print(f"TELEGRAM_CHAT_ID={cid}")
                return
    except Exception as e:
        print(f"Error: {e}")


# ── Data Models ─────────────────────────────────────────

@dataclass
class Issue:
    container: str
    status: str
    detected_at: str
    exit_code: int = 0
    logs: list = field(default_factory=list)

@dataclass
class Diagnosis:
    agent_name: str
    root_cause: str
    confidence: float
    evidence: str
    suggested_fix: str
    failure_class: str = "unknown_failure"
    severity: str = "error"

@dataclass
class FixResult:
    agent_name: str
    action_taken: str
    success: bool
    output: str
    is_structural: bool

@dataclass
class IncidentReport:
    issue: Issue
    incident: Optional[Incident] = None
    diagnoses: list = field(default_factory=list)
    fix_results: list = field(default_factory=list)
    final_confidence: float = 0.0
    resolved: bool = False
    lessons_learned: str = ""


# ── Tools ───────────────────────────────────────────────

def detect_issues() -> list[Issue]:
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True, text=True, timeout=10
    )
    issues = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 1)
        name = parts[0]
        status = parts[1] if len(parts) > 1 else "unknown"
        is_down = not status.startswith("Up") or "Restarting" in status
        if not is_down:
            continue

        exit_code = get_container_exit_code(name) or 0
        logs = get_container_log_lines(name, tail=50)

        if all_cosmetic(logs) and exit_code == 0:
            continue

        issues.append(Issue(
            container=name, status=status,
            detected_at=datetime.now(timezone.utc).isoformat(),
            exit_code=exit_code, logs=logs,
        ))
    return issues


def get_docker_logs(container: str, tail: int = 30) -> str:
    try:
        r = subprocess.run(["docker", "logs", container, f"--tail={tail}"],
                           capture_output=True, text=True, timeout=10)
        return (r.stdout[-2000:] + "\n" + r.stderr[-500:]) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


def get_docker_inspect(container: str) -> str:
    try:
        r = subprocess.run(["docker", "inspect", container],
                           capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)[0]
        return json.dumps({
            "state": data.get("State", {}),
            "exit_code": data.get("State", {}).get("ExitCode"),
            "error": data.get("State", {}).get("Error", ""),
            "restart_policy": data.get("HostConfig", {}).get("RestartPolicy", {}),
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


def get_resource_usage() -> str:
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format",
                            "{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout if r.stdout else "No data"
    except Exception as e:
        return f"Error: {e}"


def restart_container(container: str) -> str:
    try:
        r = subprocess.run(["docker", "restart", container],
                           capture_output=True, text=True, timeout=30)
        return f"Restarted {container}: OK"
    except Exception as e:
        return f"Restart failed: {e}"


def send_telegram(message: str, silent: bool = False) -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "No token or chat ID"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
            "disable_notification": "true" if silent else "false",
        }).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return "OK"
    except Exception as e:
        return f"Failed: {e}"


def store_in_uams(incident_json: str) -> str:
    try:
        env_file = os.path.expanduser("~/.hermes/scripts/uams/.env")
        api_key = ""
        if os.path.exists(env_file):
            for line in open(env_file):
                if line.startswith("RESEARCH_AGENT_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not api_key:
            return "No UAMS key"
        content = incident_json
        if not content or not content.strip():
            content = "empty incident"
        data = json.dumps({
            "memory_type": "passive",
            "scope": "overwatch",
            "agent_id": "overwatch-agent-001",
            "content": content,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:8000/memory/entry", data=data,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                return "Stored"
            return f"UAMS returned {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 422:
            return "UAMS validation error (422) — incident stored locally only"
        return f"UAMS HTTP error: {e.code}"
    except Exception as e:
        return f"UAMS failed: {e}"


def query_uams_history(limit: int = 5) -> str:
    try:
        env_file = os.path.expanduser("~/.hermes/scripts/uams/.env")
        api_key = ""
        if os.path.exists(env_file):
            for line in open(env_file):
                if line.startswith("RESEARCH_AGENT_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not api_key:
            return "[]"
        params = urllib.parse.urlencode({"scope": "overwatch", "limit": str(limit)})
        url = f"http://localhost:8000/memory/search?{params}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        return f"[]"
    except Exception:
        return "[]"
        data = json.dumps({"scope": "overwatch", "limit": limit}).encode()
        req = urllib.request.Request(
            "http://localhost:8000/memory/search",
            data=data,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode()
    except Exception:
        return "[]"


# ── Agent Pipeline ──────────────────────────────────────

async def diagnose_with_classification(issue: Issue, history: str) -> tuple[Diagnosis, Incident]:
    """Classify the failure BEFORE sending to LLM. Use classification for incident tracking."""
    log_lines = issue.logs if issue.logs else get_container_log_lines(issue.container, tail=100)

    classification = classify_failure(
        exit_code=issue.exit_code,
        log_lines=log_lines,
        container_name=issue.container,
        status=issue.status,
    )

    primary_error = extract_primary_error_signature(log_lines)

    severity = classification.severity
    policy_decision = classification.policy_decision

    if issue.exit_code == 1 and policy_decision == PolicyDecision.AUTO_REPAIR:
        policy_decision = PolicyDecision.NEEDS_APPROVAL

    incident = incident_store.record_incident(
        container_name=issue.container,
        failure_class=classification.failure_class.value,
        exit_code=issue.exit_code,
        primary_error_signature=primary_error,
        severity=severity,
        confidence=classification.confidence,
        policy_decision=policy_decision,
        metadata={"status": issue.status, "evidence_lines": classification.evidence_lines[:5]},
    )

    logs_raw = get_docker_logs(issue.container)
    inspect_raw = get_docker_inspect(issue.container)
    resources_raw = get_resource_usage()

    context = f"""Container: {issue.container}
Status: {issue.status}
Exit code: {issue.exit_code}
Failure class: {classification.failure_class.value}
Primary error: {primary_error}
Confidence: {classification.confidence:.0%}
Policy: {policy_decision.value}

LOGS (last 30 lines):
{logs_raw[:1500]}

INSPECT:
{inspect_raw[:1000]}

RESOURCES:
{resources_raw[:800]}

PAST INCIDENTS:
{history[:1000]}

This container has been seen {incident.occurrence_count} time(s) before.
Incident ID: {incident.incident_id}
Evidence hash: {incident.evidence_hash[:16]}"""

    overwatch = Agent(
        name="Overwatch",
        instructions=f"""Analyze this container failure. The failure has been pre-classified as {classification.failure_class.value} with {classification.confidence:.0%} confidence.

Return JSON:
{{"root_cause": "<specific diagnosis>", "confidence": <0.0-1.0>, "severity": "critical|high|medium|low",
 "can_auto_fix": true/false, "fix_suggestion": "<action>"}}

Be specific. If uncertain, lower confidence. This is occurrence #{incident.occurrence_count}.""",
        model=MODEL
    )
    result = await Runner.run(overwatch, f"Analyze:\n{context}")
    try:
        d = json.loads(result.final_output)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', result.final_output, re.DOTALL)
        d = json.loads(m.group(0)) if m else {"root_cause": result.final_output, "confidence": 0.3}

    diagnosis = Diagnosis(
        agent_name="Overwatch",
        root_cause=truncate_safe(d.get("root_cause", "?"), 300),
        confidence=d.get("confidence", 0.5),
        evidence=primary_error,
        suggested_fix=truncate_safe(d.get("fix_suggestion", "Manual check"), 300),
        failure_class=classification.failure_class.value,
        severity=severity.value,
    )

    return diagnosis, incident


async def fix_issue(issue: Issue, diagnosis: Diagnosis, incident: Incident) -> FixResult:
    """Attempt fix only if policy allows auto-repair. Otherwise report only."""
    if incident.policy_decision == PolicyDecision.INVESTIGATE:
        return FixResult(
            agent_name="Overwatch",
            action_taken=f"Investigate only — {diagnosis.failure_class}, no auto-repair",
            success=False, output="Policy: investigate, not auto-repair",
            is_structural=False,
        )

    if incident.policy_decision == PolicyDecision.NEEDS_APPROVAL:
        return FixResult(
            agent_name="Overwatch",
            action_taken=f"Awaiting approval — {diagnosis.failure_class}",
            success=False, output="Policy: needs approval before repair",
            is_structural=False,
        )

    if issue.exit_code == 1:
        return FixResult(
            agent_name="Overwatch",
            action_taken="Skip restart-loop — exit code 1 restart loop is not auto-repairable",
            success=False, output="Policy: restart-loop containers need diagnosis, not restart",
            is_structural=False,
        )

    context = (f"Issue: {issue.container} is {issue.status}\n"
               f"Diagnosis: {diagnosis.root_cause}\n"
               f"Confidence: {diagnosis.confidence:.0%}\n"
               f"Fix: {diagnosis.suggested_fix}\n"
               f"Policy: {incident.policy_decision.value}\n"
               f"Occurrence: {incident.occurrence_count}")
    fixer = Agent(
        name="Fixer",
        instructions="""Execute the best fix. Call restart_container(name) if appropriate.
Return JSON: {"action": "<what>", "success": true/false, "is_structural": true/false, "explanation": "<why>"}
Only attempt fixes for: restart loops, OOM, config errors, port conflicts.
For unknown causes: report only. Never restart a container that is already in a restart loop.""",
        tools=[function_tool(restart_container), function_tool(get_docker_logs), function_tool(get_resource_usage)],
        model=MODEL
    )
    result = await Runner.run(fixer, context)
    try:
        d = json.loads(result.final_output)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', result.final_output, re.DOTALL)
        d = json.loads(m.group(0)) if m else {"action": result.final_output, "success": False, "is_structural": False}
    return FixResult(
        agent_name="Fixer",
        action_taken=truncate_safe(str(d.get("action", "?")), 300),
        success=d.get("success", False),
        output=d.get("explanation", ""),
        is_structural=d.get("is_structural", False),
    )


async def verify(issue: Issue) -> tuple[bool, str]:
    await asyncio.sleep(2)
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}",
         "--filter", f"name={issue.container}"],
        capture_output=True, text=True, timeout=10
    )
    if not result.stdout.strip():
        return False, "Not found"
    _, status = result.stdout.strip().split("\t", 1)
    ok = status.startswith("Up") and "Restarting" not in status
    return ok, status


# ── Main ────────────────────────────────────────────────

async def handle_issue(issue: Issue) -> IncidentReport:
    report = IncidentReport(issue=issue)
    history = query_uams_history(5)

    diagnosis, incident = await diagnose_with_classification(issue, history)
    report.diagnoses.append(diagnosis)
    report.incident = incident

    print(f"  Incident: {incident.incident_id} | {incident.failure_class} | "
          f"Confidence: {incident.confidence:.0%} | Policy: {incident.policy_decision.value} | "
          f"Occurrence: {incident.occurrence_count}")

    should_alert = incident_store.should_alert(incident)
    if should_alert:
        alert_msg = format_incident_alert(
            incident,
            primary_error=diagnosis.evidence,
        )
        send_telegram(alert_msg)
        incident_store.mark_alerted(incident.evidence_hash)
        print(f"  Alert sent (debounce: first or interval reached)")
    else:
        occurrence_msg = format_occurrence_update(incident)
        send_telegram(occurrence_msg, silent=True)
        print(f"  Silent update (occurrence {incident.occurrence_count}, debounce active)")

    if diagnosis.confidence > 0.3 and incident.policy_decision not in (
        PolicyDecision.INVESTIGATE, PolicyDecision.NEEDS_APPROVAL, PolicyDecision.SUPPRESSED
    ):
        print(f"  Fixer attempting fix (policy: {incident.policy_decision.value})...")
        f = await fix_issue(issue, diagnosis, incident)
        report.fix_results.append(f)
        print(f"  {truncate_safe(f.action_taken, 100)} | Success: {f.success} | Structural: {f.is_structural}")
    else:
        report.fix_results.append(FixResult(
            "Overwatch",
            f"Policy: {incident.policy_decision.value} — no auto-repair",
            False, "", False
        ))
        print(f"  No fix (policy: {incident.policy_decision.value})")

    resolved, state = await verify(issue)
    report.resolved = resolved
    report.final_confidence = max(diagnosis.confidence, 0.9) if resolved else diagnosis.confidence

    if resolved:
        incident_store.resolve(incident.evidence_hash)
        send_telegram(format_resolve_alert(incident, resolution=diagnosis.root_cause))

    report.lessons_learned = (
        f"{issue.container}: {diagnosis.root_cause[:100]} -> "
        f"{'resolved' if resolved else 'unresolved'}"
    )

    store_result = store_in_uams(json.dumps({
        "incident_id": incident.incident_id,
        "issue": {"container": issue.container, "status": issue.status, "exit_code": issue.exit_code},
        "diagnosis": {"cause": diagnosis.root_cause, "confidence": diagnosis.confidence,
                      "failure_class": diagnosis.failure_class},
        "fix": {"action": report.fix_results[-1].action_taken if report.fix_results else "none",
                "structural": report.fix_results[-1].is_structural if report.fix_results else False},
        "policy": incident.policy_decision.value,
        "occurrence_count": incident.occurrence_count,
        "resolved": resolved,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))
    print(f"  UAMS: {store_result}")

    return report


async def main():
    if GET_CHAT_ID:
        fetch_chat_id()
        return

    print("=" * 55)
    print(f"  Overwatch v7 | {datetime.now():%Y-%m-%d %H:%M} | {MODEL}")
    print(f"  Telegram: {'on' if TELEGRAM_CHAT_ID else 'off'} | Mode: {'WATCH' if WATCH_MODE else 'SCAN'}")
    print(f"  Incidents: {len(incident_store.get_active())} active")
    print("=" * 55)

    issues = detect_issues()
    if not issues:
        active = incident_store.get_active()
        if active:
            print(f"\n  No new issues, {len(active)} active incident(s):")
            for inc in active:
                print(f"    {inc.container_name}: {inc.failure_class} ({inc.occurrence_count}x) [{inc.policy_decision.value}]")
        else:
            print("\n  All containers healthy")
        print("=" * 55)
        incident_store.prune_resolved()
        return

    print(f"\n  {len(issues)} issue(s) detected:")
    for i in issues:
        print(f"    {i.container}: {i.status} (exit {i.exit_code})")

    for issue in issues:
        print(f"\n  -- {issue.container} --")
        report = await handle_issue(issue)

    incident_store.prune_resolved()
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())