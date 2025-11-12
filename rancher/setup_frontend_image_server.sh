#!/usr/bin/env bash

# shellcheck disable=SC1090

if [[ -z "${BASH_VERSION:-}" ]]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULTS_FILE="$SCRIPT_DIR/bootstrap_defaults.env"
RENDER_SCRIPT="$SCRIPT_DIR/render_vista3d_manifest.sh"
LOCAL_PATH_MANIFEST="$SCRIPT_DIR/local-path-storage.yaml"

usage() {
  cat <<'EOF'
Usage: setup_frontend_image_server.sh [options]

Provision the Vista3D frontend and image server on a Rancher-managed "local"
cluster, ensuring local-path storage is available.

Options:
  --rancher-url URL         Rancher server URL (default: https://localhost:8443)
  --rancher-token TOKEN     Rancher API token (required)
  --rancher-context ID      Rancher project context (e.g. local:p-abc12)
  --cluster ID              Rancher cluster ID (default: local)
  --namespace NAME          Kubernetes namespace to deploy into (default: vista3d)
  --kubeconfig PATH         Kubeconfig output path (default: ~/.kube/vista3d-rancher.yaml)
  --kubectl PATH            kubectl binary to use (default: kubectl in PATH)
  --storage-class NAME      StorageClass for PVCs (default: local-path)
  --install-storage         Install/repair local-path-provisioner (default)
  --no-install-storage      Skip applying local-path storage manifest
  --render-output PATH      Path for rendered manifest output
                             (default: ./rancher/vista3d-frontend-image.yaml)
  --values FILE             Additional Helm values file (repeatable)
  --set key=val             Helm --set override (repeatable)
  --set-string key=val      Helm --set-string override (repeatable)
  --render-only             Render manifest but do not apply
  --apply-only              Assume manifest already rendered; skip rendering
  --skip-deps               Skip Helm dependency update during render
  --skip-tls-verify         Skip Rancher server TLS verification
  --non-interactive         Fail instead of prompting for missing values
  --debug                   Print executed commands
  --help                    Show this help message and exit

Environment overrides (via ./rancher/bootstrap_defaults.env or exported vars):
  DEFAULT_RANCHER_URL, DEFAULT_RANCHER_TOKEN, DEFAULT_RANCHER_CONTEXT,
  DEFAULT_CLUSTER_ID, DEFAULT_NAMESPACE, DEFAULT_KUBECONFIG_PATH,
  DEFAULT_KUBECTL_BIN, DEFAULT_STORAGE_CLASS, DEFAULT_RENDER_OUTPUT,
  DEFAULT_SKIP_TLS_VERIFY, DEFAULT_INSTALL_STORAGE,
  DEFAULT_HELM_VALUES (comma-separated list of files)

Example:
  ./rancher/setup_frontend_image_server.sh \
    --rancher-url https://localhost:8443 \
    --skip-tls-verify \
    --rancher-token token-xxxxx:yyyyy \
    --rancher-context local:p-abc12 \
    --kubectl /var/lib/rancher/rke2/bin/kubectl \
    --install-storage \
    --non-interactive
EOF
}

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

error() {
  echo "Error: $*" >&2
}

die() {
  error "$*"
  exit 1
}

ensure_cmd() {
  local binary=$1
  if ! command -v "$binary" >/dev/null 2>&1; then
    die "Required command '$binary' not found in PATH"
  fi
}

source_defaults() {
  if [[ -f "$DEFAULTS_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$DEFAULTS_FILE"
  fi
}

source_defaults

RANCHER_URL=${RANCHER_URL:-${DEFAULT_RANCHER_URL:-https://localhost:8443}}
RANCHER_TOKEN=${DEFAULT_RANCHER_TOKEN:-${RANCHER_TOKEN:-}}
RANCHER_CONTEXT=${DEFAULT_RANCHER_CONTEXT:-${RANCHER_CONTEXT:-}}
CLUSTER_ID=${CLUSTER_ID:-${DEFAULT_CLUSTER_ID:-local}}
NAMESPACE=${DEFAULT_NAMESPACE:-${NAMESPACE:-vista3d}}
KUBECONFIG_PATH=${DEFAULT_KUBECONFIG_PATH:-${KUBECONFIG_PATH:-$HOME/.kube/vista3d-rancher.yaml}}
KUBECTL_BIN=${DEFAULT_KUBECTL_BIN:-${KUBECTL_BIN:-kubectl}}
STORAGE_CLASS=${DEFAULT_STORAGE_CLASS:-${STORAGE_CLASS:-local-path}}
RENDER_OUTPUT=${DEFAULT_RENDER_OUTPUT:-${RENDER_OUTPUT:-$SCRIPT_DIR/vista3d-frontend-image.yaml}}
SKIP_TLS_VERIFY=${DEFAULT_SKIP_TLS_VERIFY:-${SKIP_TLS_VERIFY:-false}}
INSTALL_STORAGE=${DEFAULT_INSTALL_STORAGE:-${INSTALL_STORAGE:-true}}
SKIP_DEPS=false
RENDER_ONLY=false
APPLY_ONLY=false
NON_INTERACTIVE=false
DEBUG_MODE=false

VALUES_FILES=()
SET_ARGS=(--set backend.enabled=false)
SET_STRING_ARGS=()

if [[ -n "${DEFAULT_HELM_VALUES:-}" ]]; then
  IFS=',' read -r -a default_values_array <<<"$DEFAULT_HELM_VALUES"
  for val_file in "${default_values_array[@]}"; do
    [[ -n "$val_file" ]] && VALUES_FILES+=("$val_file")
  done
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rancher-url) RANCHER_URL="$2"; shift 2 ;;
    --rancher-token) RANCHER_TOKEN="$2"; shift 2 ;;
    --rancher-context) RANCHER_CONTEXT="$2"; shift 2 ;;
    --cluster) CLUSTER_ID="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --kubeconfig) KUBECONFIG_PATH="$2"; shift 2 ;;
    --kubectl) KUBECTL_BIN="$2"; shift 2 ;;
    --storage-class) STORAGE_CLASS="$2"; shift 2 ;;
    --install-storage) INSTALL_STORAGE=true; shift ;;
    --no-install-storage) INSTALL_STORAGE=false; shift ;;
    --render-output) RENDER_OUTPUT="$2"; shift 2 ;;
    --values) VALUES_FILES+=("$2"); shift 2 ;;
    --set) SET_ARGS+=(--set "$2"); shift 2 ;;
    --set-string) SET_STRING_ARGS+=(--set-string "$2"); shift 2 ;;
    --render-only) RENDER_ONLY=true; shift ;;
    --apply-only) APPLY_ONLY=true; shift ;;
    --skip-deps) SKIP_DEPS=true; shift ;;
    --skip-tls-verify) SKIP_TLS_VERIFY=true; shift ;;
    --non-interactive) NON_INTERACTIVE=true; shift ;;
    --debug) DEBUG_MODE=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ "$RENDER_ONLY" == true && "$APPLY_ONLY" == true ]]; then
  die "Cannot use --render-only and --apply-only together"
fi

if [[ "$DEBUG_MODE" == true ]]; then
  set -x
fi

[[ -n "$RANCHER_URL" ]] || die "Missing --rancher-url (or DEFAULT_RANCHER_URL)"
[[ -n "$RANCHER_TOKEN" ]] || die "Missing --rancher-token (or DEFAULT_RANCHER_TOKEN)"
[[ -n "$RANCHER_CONTEXT" ]] || die "Missing --rancher-context (or DEFAULT_RANCHER_CONTEXT)"

ensure_cmd rancher
ensure_cmd "$KUBECTL_BIN"
ensure_cmd helm

if [[ ! -x "$RENDER_SCRIPT" ]]; then
  die "Render script not found or not executable: $RENDER_SCRIPT"
fi

mkdir -p "$(dirname "$KUBECONFIG_PATH")"

login_args=(login "$RANCHER_URL" --token "$RANCHER_TOKEN" --context "$RANCHER_CONTEXT")
if [[ "$SKIP_TLS_VERIFY" == true ]]; then
  login_args+=(--skip-verify)
fi

log "Logging into Rancher CLI for context '$RANCHER_CONTEXT'"
rancher "${login_args[@]}" >/dev/null

tmp_kubeconfig=$(mktemp)
trap 'rm -f "$tmp_kubeconfig"' EXIT

log "Retrieving kubeconfig for cluster '$CLUSTER_ID'"
rancher clusters kubeconfig --cluster "$CLUSTER_ID" >"$tmp_kubeconfig"
mv "$tmp_kubeconfig" "$KUBECONFIG_PATH"
trap - EXIT

export KUBECONFIG="$KUBECONFIG_PATH"

kubectl_cmd=("$KUBECTL_BIN" --kubeconfig "$KUBECONFIG_PATH")

if [[ "$INSTALL_STORAGE" == true ]]; then
  if [[ ! -f "$LOCAL_PATH_MANIFEST" ]]; then
    die "Local-path manifest not found at $LOCAL_PATH_MANIFEST"
  fi
  log "Applying local-path storage manifest"
  "${kubectl_cmd[@]}" apply -f "$LOCAL_PATH_MANIFEST"
  log "Waiting for local-path-provisioner deployment to become ready"
  "${kubectl_cmd[@]}" -n local-path-storage rollout status deployment/local-path-provisioner --timeout=180s
else
  log "Skipping local-path storage installation per user request"
fi

if ! "${kubectl_cmd[@]}" get namespace "$NAMESPACE" >/dev/null 2>&1; then
  log "Creating namespace '$NAMESPACE'"
  "${kubectl_cmd[@]}" create namespace "$NAMESPACE"
else
  log "Namespace '$NAMESPACE' already exists"
fi

render_values=("${SET_ARGS[@]}")
if [[ ${#SET_STRING_ARGS[@]} -gt 0 ]]; then
  render_values+=("${SET_STRING_ARGS[@]}")
fi

if [[ "$APPLY_ONLY" == false ]]; then
  render_args=(--namespace "$NAMESPACE" --storage-class "$STORAGE_CLASS" --output "$RENDER_OUTPUT" --non-interactive)
  [[ "$SKIP_DEPS" == true ]] && render_args+=(--skip-deps)

  for vf in "${VALUES_FILES[@]}"; do
    render_args+=(--values "$vf")
  done

  render_args+=("${render_values[@]}")

  log "Rendering Vista3D manifest (frontend + image server only) to $RENDER_OUTPUT"
  "$RENDER_SCRIPT" "${render_args[@]}"
else
  log "Skipping render step due to --apply-only"
fi

if [[ "$RENDER_ONLY" == true ]]; then
  log "Render complete; skipping apply per --render-only"
  exit 0
fi

if [[ ! -f "$RENDER_OUTPUT" ]]; then
  die "Rendered manifest not found at $RENDER_OUTPUT"
fi

log "Applying manifest to namespace '$NAMESPACE'"
"${kubectl_cmd[@]}" apply -f "$RENDER_OUTPUT"

log "Deployment triggered. Verify pod status with:"
log "  $KUBECTL_BIN --kubeconfig $KUBECONFIG_PATH -n $NAMESPACE get pods"
log "Port-forward commands (run from your remote Ubuntu server):"
log "  $KUBECTL_BIN --kubeconfig $KUBECONFIG_PATH -n $NAMESPACE port-forward svc/vista3d-frontend 8501:8501"
log "  $KUBECTL_BIN --kubeconfig $KUBECONFIG_PATH -n $NAMESPACE port-forward svc/vista3d-image-server 8888:8888"

log "Setup completed successfully."

