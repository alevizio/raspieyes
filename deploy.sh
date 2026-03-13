#!/usr/bin/env bash
# Deploy raspieyes to Pi — handles passwords automatically
set -euo pipefail

PI_HOST="${1:-raspieyes.local}"
PI_USER="pi"
PI_PASS="raspberry"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Deploying raspieyes to $PI_USER@$PI_HOST ==="

# Check expect is available
if ! command -v expect &>/dev/null; then
    echo "ERROR: 'expect' not found" >&2
    exit 1
fi

# Step 1: Copy files
echo "[1/2] Copying files..."
expect -c "
set timeout 120
spawn scp -o StrictHostKeyChecking=no -o AddressFamily=inet -r $PROJECT_DIR $PI_USER@$PI_HOST:~/
expect {
    \"*password*\" { send \"$PI_PASS\r\"; exp_continue }
    \"*yes*no*\" { send \"yes\r\"; exp_continue }
    timeout { puts \"TIMEOUT\"; exit 1 }
    eof
}
catch wait result
exit [lindex \$result 3]
"
echo "  Files copied!"

# Step 2: Run setup
echo "[2/2] Running setup (Pi will reboot when done)..."
expect -c "
set timeout 300
spawn ssh -o StrictHostKeyChecking=no -o AddressFamily=inet $PI_USER@$PI_HOST {bash ~/raspieyes/setup.sh}
expect {
    \"*password*\" { send \"$PI_PASS\r\"; exp_continue }
    \"*yes*no*\" { send \"yes\r\"; exp_continue }
    timeout { puts \"TIMEOUT\"; exit 1 }
    eof
}
"
echo ""
echo "=== Done! Pi is rebooting. Video should play in ~30 seconds. ==="
