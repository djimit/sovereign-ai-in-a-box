#!/bin/bash
# deploy-overwatch.sh — Deploy Overwatch v7 modules to Linux workstation
# Run this script on the control machine to sync modules to the workstation
#
# Usage: bash deploy-overwatch.sh
#
# Prerequisites:
#   - SSH key at ~/.ssh/<YOUR_SSH_KEY>
#   - SSH access to <YOUR_USER>@<WORKSTATION_IP>
#   - Python 3.10+ on workstation (for overwatch-llm.py)
#
# Environment variables (override defaults):
#   SSH_KEY     — path to SSH private key
#   REMOTE_HOST — user@hostname of the workstation
#   REMOTE_USER — username on the workstation (used for paths)

set -euo pipefail

SSH_KEY="${SSH_KEY:-${HOME}/.ssh/<YOUR_SSH_KEY>}"
REMOTE_HOST="${REMOTE_HOST:-<YOUR_USER>@<WORKSTATION_IP>}"
REMOTE_USER="${REMOTE_USER:-<YOUR_USER>}"
REMOTE_DIR="/home/${REMOTE_USER}/scripts"
LOCAL_DIR="${HOME}/sovereign-ai-in-a-box/scripts"

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ${SSH_KEY}"

echo "=== Overwatch v7 Deployment ==="
echo "Target: ${REMOTE_HOST}:${REMOTE_DIR}"
echo ""

# 1. Create remote directory if needed
echo "[1/5] Creating remote directory..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "mkdir -p ${REMOTE_DIR}" || {
    echo "ERROR: Cannot connect to ${REMOTE_HOST}. Check SSH key and connectivity."
    exit 1
}

# 2. Sync core modules
echo "[2/5] Syncing core modules..."
rsync -az -e "ssh ${SSH_OPTS}" \
    "${LOCAL_DIR}/incident_store.py" \
    "${LOCAL_DIR}/container_failure_classifier.py" \
    "${LOCAL_DIR}/known_warnings.py" \
    "${LOCAL_DIR}/message_formatter.py" \
    "${REMOTE_HOST}:${REMOTE_DIR}/"

# 3. Sync new monitoring modules
echo "[3/5] Syncing monitoring modules..."
rsync -az -e "ssh ${SSH_OPTS}" \
    "${LOCAL_DIR}/service_health.py" \
    "${LOCAL_DIR}/config_monitor.py" \
    "${LOCAL_DIR}/overwatch_learning.py" \
    "${REMOTE_HOST}:${REMOTE_DIR}/"

# 4. Sync updated overwatch scripts
echo "[4/5] Syncing updated overwatch scripts..."
rsync -az -e "ssh ${SSH_OPTS}" \
    "${LOCAL_DIR}/overwatch-monitor.py" \
    "${LOCAL_DIR}/overwatch-llm.py" \
    "${REMOTE_HOST}:${REMOTE_DIR}/"

# 5. Verify deployment
echo "[5/5] Verifying deployment..."
ssh ${SSH_OPTS} ${REMOTE_HOST} "ls -la ${REMOTE_DIR}/" || {
    echo "WARNING: Could not verify remote files. Check manually."
}

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Next steps on the workstation:"
echo "  1. Stop the current overwatch service:"
echo "     ssh ${REMOTE_HOST} 'sudo systemctl stop overwatch-monitor'"
echo ""
echo "  2. Update the systemd service file if needed:"
echo "     The service should point to ${REMOTE_DIR}/overwatch-monitor.py"
echo "     and set PYTHONPATH to include ${REMOTE_DIR}"
echo ""
echo "  3. Start the updated service:"
echo "     ssh ${REMOTE_HOST} 'sudo systemctl start overwatch-monitor'"
echo ""
echo "  4. For the LLM pipeline (overwatch-llm.py), update the cron job:"
echo "     The crontab entry should use:"
echo "     PYTHONPATH=${REMOTE_DIR} python3 ${REMOTE_DIR}/overwatch-llm.py --watch"
echo ""
echo "  5. Verify logs:"
echo "     ssh ${REMOTE_HOST} 'tail -20 ~/workspace/logs/overwatch-monitor.log'"