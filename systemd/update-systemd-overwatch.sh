#!/bin/bash
# update-systemd-overwatch.sh — Update and restart the Overwatch systemd service on the workstation
# Run from control machine:
#   bash ~/sovereign-ai-in-a-box/systemd/update-systemd-overwatch.sh
#
# Required environment variables or defaults:
#   SSH_KEY    — path to SSH private key (default: ~/.ssh/<YOUR_SSH_KEY>)
#   REMOTE_HOST — user@hostname of the workstation (default: <YOUR_USER>@<WORKSTATION_IP>)

set -euo pipefail

SSH_KEY="${SSH_KEY:-${HOME}/.ssh/<YOUR_SSH_KEY>}"
REMOTE_HOST="${REMOTE_HOST:-<YOUR_USER>@<WORKSTATION_IP>}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SSH_KEY}"

echo "=== Updating Overwatch systemd service ==="

# 1. Create data directory for incident store
echo "[1/5] Creating data directory..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "mkdir -p ~/workspace/data" || {
    echo "WARNING: Could not create data directory"
}

# 2. Copy updated systemd service file
echo "[2/5] Updating systemd service file..."
scp ${SSH_OPTS} \
    ~/sovereign-ai-in-a-box/systemd/overwatch-monitor.service \
    ${REMOTE_HOST}:/tmp/overwatch-monitor.service

ssh ${SSH_OPTS} ${REMOTE_HOST} "sudo cp /tmp/overwatch-monitor.service /etc/systemd/system/overwatch-monitor.service && sudo chmod 644 /etc/systemd/system/overwatch-monitor.service"

# 3. Reload systemd and restart service
echo "[3/5] Reloading systemd daemon..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "sudo systemctl daemon-reload"

echo "[4/5] Restarting overwatch-monitor service..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "sudo systemctl restart overwatch-monitor"

# 4. Check status
echo "[5/5] Verifying service status..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "sudo systemctl status overwatch-monitor --no-pager" || true

echo ""
echo "=== Service update complete ==="
echo ""
echo "To check logs:"
echo "  ssh ${REMOTE_HOST} 'tail -20 ~/workspace/logs/overwatch-monitor.log'"
echo ""
echo "To update the LLM cron job (overwatch-llm.py --watch):"
echo "  ssh ${REMOTE_HOST} 'crontab -l'  # Check current cron"
echo "  Then add/edit the line:"
echo "  PYTHONPATH=~/scripts /usr/bin/python3 ~/scripts/overwatch-llm.py --watch"