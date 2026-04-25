#!/bin/bash
set -ex

echo "=== Updating packages ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ufw git curl tar

echo "=== Configuring Firewall (UFW) ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

echo "=== Installing Docker ==="
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi
apt-get install -y docker-compose-plugin

echo "=== Configuring Swap ==="
if [ ! -f /swapfile ] && [ `free -m | awk '/Mem:/ {print $2}'` -lt 2500 ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== SETUP STEP 1 COMPLETE ==="
