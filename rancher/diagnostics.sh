#!/usr/bin/env bash

# Vista3D Rancher diagnostics helper.
# Collects cluster, networking, storage, and Rancher status information for troubleshooting.

set -uo pipefail

SCRIPT_NAME=$(basename "$0")
OUT_DIR=${DIAG_OUTPUT_DIR:-}

header() {
  local title="$1"
  printf '\n==== %s ====\n' "$title"
}

run_cmd() {
  local title="$1"
  shift
  header "$title"
  if command -v "$1" >/dev/null 2>&1 || [[ "$1" == sudo ]]; then
    if ! "$@" 2>&1; then
      echo "[command failed]" >&2
    fi
  else
    echo "[command not available: $1]" >&2
  fi
}

# Ensure kubectl path for RKE2
RKE2_KUBECTL=/var/lib/rancher/rke2/bin/kubectl
if [[ ! -x "$RKE2_KUBECTL" ]]; then
  echo "Warning: expected kubectl at $RKE2_KUBECTL not found." >&2
fi

EXPORT_ENV=(
  "export KUBECONFIG=/etc/rancher/rke2/rke2.yaml"
)

header "Environment exports"
printf '%s\n' "${EXPORT_ENV[@]}"

run_cmd "systemctl status rke2-server" sudo systemctl status rke2-server
run_cmd "rke2-server journal (last 2h)" sudo journalctl -u rke2-server --since "2 hours ago"

run_cmd "kubectl contexts" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml config get-contexts
run_cmd "cluster nodes" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml get nodes -o wide

run_cmd "cluster pods (all namespaces)" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml get pods -A
run_cmd "cluster services (all namespaces)" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml get svc -A

run_cmd "storage classes" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml get storageclass
run_cmd "local-path-storage pods" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml -n local-path-storage get pods

run_cmd "resolvectl status" resolvectl status
run_cmd "/etc/resolv.conf" cat /etc/resolv.conf
if command -v dig >/dev/null 2>&1; then
  run_cmd "dig kubernetes.default.svc.cluster.local" dig @127.0.0.53 kubernetes.default.svc.cluster.local
else
  header "dig kubernetes.default.svc.cluster.local"
  echo "[command not available: dig]" >&2
fi

run_cmd "iptables-save (head)" sudo iptables-save | head -n 40
run_cmd "iptables-nft-save (head)" sudo iptables-nft-save | head -n 40
run_cmd "nft list ruleset (head)" sudo nft list ruleset | head -n 80

run_cmd "listening ports 8501/8888" sudo ss -tulpn | grep -E ':(8501|8888)' || true
run_cmd "Rancher ping" curl -k https://localhost:8443/ping

run_cmd "local-path provisioner logs" "$RKE2_KUBECTL" --kubeconfig /etc/rancher/rke2/rke2.yaml -n local-path-storage logs deploy/local-path-provisioner

