# Copilot Instructions — sovereign-ai-in-a-box

> See root `.github/copilot-instructions.md` for global conventions.

AI workstation deployment playbook en Overwatch monitoring configuratie. Bevat systemd units, deploy scripts, self-healing modules, en incident tracking voor de Linux workstation (192.168.1.28).

## Structure

```
systemd/                                    # Systemd unit files
├── overwatch-monitor.service               # Main Overwatch Telegram bot service
└── update-systemd-overwatch.sh             # Systemd updater script
scripts/
├── deploy-overwatch.sh                     # Deployment orchestrator
├── overwatch-monitor.py                    # Main monitoring entry point
├── config_monitor.py                       # Config drift detection
├── container_failure_classifier.py         # Docker failure classification
├── incident_store.py                       # Incident persistence (SQLite)
├── known_warnings.py                       # Warning filter / deduplication
├── message_formatter.py                    # Telegram message formatting
├── orchestrator.py                         # Multi-service orchestration
├── overwatch-llm.py                        # LLM-based diagnostic assistant
├── overwatch_learning.py                   # Failure pattern learning
├── service_health.py                       # Per-service health probes
└── test_overwatch_incident.py              # Incident pipeline tests
docs/
├── overwatch-self-healing-roadmap.md       # Self-healing capability roadmap
└── research-agent-investigate-loop-analysis.md  # Research agent loop analysis
DEPLOY-STATUS.md                            # Huidige deploy status en open taken
```

## Deployment Commands

```bash
# Overwatch service deployen naar workstation
./scripts/deploy-overwatch.sh

# Service file kopiëren
scp -i ~/.ssh/workstation_hermes systemd/overwatch-monitor.service djimit@192.168.1.28:/tmp/

# Op workstation:
sudo cp /tmp/overwatch-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable overwatch-monitor
sudo systemctl restart overwatch-monitor

# Logs checken
tail -20 /home/djimit/workspace/logs/overwatch-monitor.log

# Incident store inspecteren (op workstation)
python3 scripts/incident_store.py --list
python3 scripts/service_health.py --check
```

## Overwatch Configuratie

Overwatch vereist `~/.overwatch.env` op de workstation:

```env
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_CHAT_ID=<chat_id>
```

Instellen:
```bash
chmod 600 ~/.overwatch.env
```

## Known Issues

- `sudo` op workstation vereist wachtwoord (geen passwordless sudo)
- `TELEGRAM_CHAT_ID` auto-discovery faalt — bot moet eerst een bericht ontvangen
- Bij "TELEGRAM_CHAT_ID not set": verifieer `.overwatch.env` en herstart service

## Related

- `ai-workstation-bootstrap/` — Ansible provisioning en hardware context
- `DEPLOY-STATUS.md` — Laatste deploy: 2026-05-22, open taken gedocumenteerd
