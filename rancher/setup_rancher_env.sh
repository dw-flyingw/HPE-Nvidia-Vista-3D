#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

DEFAULT_NAMESPACE=${VISTA3D_NAMESPACE:-vista3d}
DEFAULT_STORAGE_CLASS=${VISTA3D_STORAGE_CLASS:-longhorn}
DEFAULT_KUBECONFIG=${VISTA3D_KUBECONFIG_PATH:-$HOME/.kube/vista3d-rancher.yaml}

usage() {
  cat <<'EOF'
Usage: setup_rancher_env.sh [options]

Prepare a Rancher-managed Kubernetes cluster for the Vista3D deployment.

Options:
  --rancher-url URL          Rancher server URL (default: $RANCHER_URL)
  --rancher-token TOKEN      Rancher API token (default: $RANCHER_TOKEN)
  --cluster NAME_OR_ID       Rancher cluster name or ID (default: $RANCHER_CLUSTER)
  --namespace NAME           Kubernetes namespace to manage (default: vista3d)
  --storage-class NAME       Preferred storageClass for PVCs (default: longhorn)
  --ngc-key-file PATH        Path to file containing the NGC API key
  --kubeconfig PATH          Destination path for generated kubeconfig
  --registry FQDN            Container registry host to create pull secret for
  --registry-username USER   Username for the registry pull secret
  --registry-password PASS   Password/token for the registry pull secret
  --registry-email EMAIL     Email for the registry pull secret (optional)
  --rancher-context ID       Rancher project context (e.g. local:p-xxxxx) to avoid interactive prompt
  --skip-tls-verify          Pass --skip-verify to Rancher CLI login
  --non-interactive          Fail instead of prompting for missing inputs
  --force-login              Force re-login and kubeconfig download even if cached
  --skip-secret              Skip creating/replacing the vista3d-secrets secret
  --skip-pull-secret         Skip creating/updating the registry pull secret
  --context NAME             kubectl context name to write into kubeconfig (optional)
  --help                     Show this message and exit

Environment:
  RANCHER_URL, RANCHER_TOKEN, RANCHER_CLUSTER, VISTA3D_NAMESPACE,
  VISTA3D_STORAGE_CLASS, NGC_API_KEY_FILE, VISTA3D_KUBECONFIG_PATH

Examples:
  ./setup_rancher_env.sh --rancher-url https://rancher.example.com \
      --rancher-token token-abc123 --cluster workhorse-gpu --ngc-key-file ~/secrets/ngc.key

  ./setup_rancher_env.sh --non-interactive --skip-pull-secret --skip-secret \
      --rancher-url $RANCHER_URL --rancher-token $RANCHER_TOKEN --cluster c-m-abc1
EOF
}

error() {
  echo "Error: $*" >&2
}

die() {
  error "$*"
  exit 1
}

ensure_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Required command '$1' not found in PATH"
  fi
}

prompt_if_empty() {
  local var_name="$1"
  local prompt_text="$2"
  local secret="${3:-false}"
  local current_value="${!var_name-}"

  if [[ -n "$current_value" ]]; then
    return
  fi

  if [[ "$NON_INTERACTIVE" == true ]]; then
    die "Missing required value for $var_name"
  fi

  if [[ "$secret" == true ]]; then
    read -rsp "$prompt_text" current_value
    echo
  else
    read -rp "$prompt_text" current_value
  fi

  printf -v "$var_name" '%s' "$current_value"
}

confirm() {
  local prompt="$1"
  local reply

  if [[ "$NON_INTERACTIVE" == true ]]; then
    return 0
  fi

  while true; do
    read -rp "$prompt [y/n]: " reply
    case "$reply" in
      [Yy]*) return 0 ;;
      [Nn]*) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

decode_cluster_id() {
  local search="$1"

  if [[ -z "$search" ]]; then
    die "Cluster identifier cannot be empty"
  fi

  if [[ "$search" == c-* ]] || [[ "$search" == local ]]; then
    echo "$search"
    return 0
  fi

  local resolved=""
  while IFS=$'\t' read -r cid cname _; do
    if [[ "$cname" == "$search" ]]; then
      resolved="$cid"
      break
    fi
  done < <(rancher clusters ls --format '{{.ID}}\t{{.Name}}\t{{.State}}')

  if [[ -z "$resolved" ]]; then
    die "Unable to resolve cluster name '$search'. Use --cluster with the exact Rancher cluster ID or name."
  fi

  echo "$resolved"
}

ensure_namespace() {
  local ns="$1"
  if kubectl get namespace "$ns" >/dev/null 2>&1; then
    echo "Namespace '$ns' already exists"
  else
    echo "Creating namespace '$ns'"
    kubectl create namespace "$ns"
  fi
}

create_ngc_secret() {
  local ns="$1"
  local key_file="$2"

  [[ -f "$key_file" ]] || die "NGC key file '$key_file' not found"

  # Kubernetes secret expects key named ngc-api-key per Helm chart
  if kubectl get secret vista3d-secrets -n "$ns" >/dev/null 2>&1; then
    echo "Replacing existing secret 'vista3d-secrets' in namespace '$ns'"
  else
    echo "Creating secret 'vista3d-secrets' in namespace '$ns'"
  fi

  kubectl delete secret vista3d-secrets -n "$ns" >/dev/null 2>&1 || true
  kubectl create secret generic vista3d-secrets \
    --from-file=ngc-api-key="$key_file" \
    -n "$ns"
}

create_pull_secret() {
  local ns="$1"
  local registry="$2"
  local username="$3"
  local password="$4"
  local email="$5"
  local name="${6:-regcred}"

  if [[ -z "$registry" || -z "$username" || -z "$password" ]]; then
    die "Registry, username, and password are required to create an image pull secret"
  fi

  if kubectl get secret "$name" -n "$ns" >/dev/null 2>&1; then
    echo "Updating existing image pull secret '$name'"
    kubectl delete secret "$name" -n "$ns" >/dev/null 2>&1 || true
  else
    echo "Creating image pull secret '$name'"
  fi

  local args=("$name" --docker-server="$registry" --docker-username="$username" --docker-password="$password")
  if [[ -n "$email" ]]; then
    args+=(--docker-email="$email")
  fi
  args+=(-n "$ns")

  kubectl create secret docker-registry "${args[@]}"
}

NON_INTERACTIVE=false
FORCE_LOGIN=false
SKIP_SECRET=false
SKIP_PULL_SECRET=false
REGISTRY_NAME=regcred
KUBECTL_CONTEXT=""
RANCHER_CONTEXT=${RANCHER_CONTEXT:-}
RANCHER_SKIP_VERIFY=false

RANCHER_URL=${RANCHER_URL:-}
RANCHER_TOKEN=${RANCHER_TOKEN:-}
RANCHER_CLUSTER=${RANCHER_CLUSTER:-}
NAMESPACE="$DEFAULT_NAMESPACE"
STORAGE_CLASS="$DEFAULT_STORAGE_CLASS"
NGC_KEY_FILE=${NGC_API_KEY_FILE:-}
KUBECONFIG_PATH="$DEFAULT_KUBECONFIG"
REGISTRY_HOST=${VISTA3D_REGISTRY_HOST:-}
REGISTRY_USER=${VISTA3D_REGISTRY_USER:-}
REGISTRY_PASS=${VISTA3D_REGISTRY_PASS:-}
REGISTRY_EMAIL=${VISTA3D_REGISTRY_EMAIL:-}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rancher-url)
      RANCHER_URL="$2"; shift 2 ;;
    --rancher-token)
      RANCHER_TOKEN="$2"; shift 2 ;;
    --cluster)
      RANCHER_CLUSTER="$2"; shift 2 ;;
    --namespace)
      NAMESPACE="$2"; shift 2 ;;
    --storage-class)
      STORAGE_CLASS="$2"; shift 2 ;;
    --ngc-key-file)
      NGC_KEY_FILE="$2"; shift 2 ;;
    --kubeconfig)
      KUBECONFIG_PATH="$2"; shift 2 ;;
    --registry)
      REGISTRY_HOST="$2"; shift 2 ;;
    --registry-username)
      REGISTRY_USER="$2"; shift 2 ;;
    --registry-password)
      REGISTRY_PASS="$2"; shift 2 ;;
    --registry-email)
      REGISTRY_EMAIL="$2"; shift 2 ;;
    --registry-name)
      REGISTRY_NAME="$2"; shift 2 ;;
    --context)
      KUBECTL_CONTEXT="$2"; shift 2 ;;
    --rancher-context)
      RANCHER_CONTEXT="$2"; shift 2 ;;
    --skip-tls-verify)
      RANCHER_SKIP_VERIFY=true; shift ;;
    --non-interactive)
      NON_INTERACTIVE=true; shift ;;
    --force-login)
      FORCE_LOGIN=true; shift ;;
    --skip-secret)
      SKIP_SECRET=true; shift ;;
    --skip-pull-secret)
      SKIP_PULL_SECRET=true; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      die "Unknown option: $1" ;;
  esac
done

ensure_cmd rancher
ensure_cmd kubectl
ensure_cmd helm
ensure_cmd docker

prompt_if_empty RANCHER_URL "Rancher server URL: "
prompt_if_empty RANCHER_TOKEN "Rancher API token: " true
prompt_if_empty RANCHER_CLUSTER "Rancher cluster name or ID: "

if [[ "$SKIP_SECRET" == false ]]; then
  prompt_if_empty NGC_KEY_FILE "Path to NGC API key file: "
fi

echo "# Vista3D Rancher Environment Setup"
echo "Rancher URL:        $RANCHER_URL"
echo "Rancher Cluster:    $RANCHER_CLUSTER"
echo "Namespace:          $NAMESPACE"
echo "Storage Class:      ${STORAGE_CLASS:-<cluster default>}"
echo "Kubeconfig path:    $KUBECONFIG_PATH"
echo "NGC key file:       ${NGC_KEY_FILE:-<skipped>}"
if [[ "$SKIP_PULL_SECRET" == true ]]; then
  pull_secret_status="skipped"
elif [[ -n "$REGISTRY_HOST" ]]; then
  pull_secret_status="$REGISTRY_HOST (secret: $REGISTRY_NAME)"
else
  pull_secret_status="<none>"
fi

echo "Registry pull secret: $pull_secret_status"

if [[ "$NON_INTERACTIVE" == false ]]; then
  confirm "Continue with these settings?" || die "Aborted by user"
fi

login_args=(login "$RANCHER_URL" --token "$RANCHER_TOKEN")
if [[ "$FORCE_LOGIN" == true ]]; then
  login_args+=(--cleanup)
fi
if [[ "$RANCHER_SKIP_VERIFY" == true ]]; then
  login_args+=(--skip-verify)
fi
if [[ -n "$RANCHER_CONTEXT" ]]; then
  login_args+=(--context "$RANCHER_CONTEXT")
fi

echo "Logging into Rancher CLI"
rancher "${login_args[@]}" >/dev/null

cluster_id=$(decode_cluster_id "$RANCHER_CLUSTER")
echo "Resolved cluster '$RANCHER_CLUSTER' to ID '$cluster_id'"

if [[ "$FORCE_LOGIN" == true || ! -f "$KUBECONFIG_PATH" ]]; then
  mkdir -p "$(dirname "$KUBECONFIG_PATH")"
  echo "Downloading kubeconfig to $KUBECONFIG_PATH"
  rancher cluster kubeconfig "$cluster_id" >"$KUBECONFIG_PATH"
else
  echo "Kubeconfig $KUBECONFIG_PATH already exists (use --force-login to refresh)"
fi

export KUBECONFIG="$KUBECONFIG_PATH"

if [[ -n "$KUBECTL_CONTEXT" ]]; then
  kubectl config use-context "$KUBECTL_CONTEXT"
fi

ensure_namespace "$NAMESPACE"

if [[ -n "$STORAGE_CLASS" ]]; then
  echo "Verifying storage class '$STORAGE_CLASS'"
  if ! kubectl get storageclass "$STORAGE_CLASS" >/dev/null 2>&1; then
    echo "Warning: storage class '$STORAGE_CLASS' not found. Update your Helm values accordingly." >&2
  fi
fi

if [[ "$SKIP_SECRET" == false ]]; then
  create_ngc_secret "$NAMESPACE" "$NGC_KEY_FILE"
fi

if [[ "$SKIP_PULL_SECRET" == false && -n "$REGISTRY_HOST" ]]; then
  create_pull_secret "$NAMESPACE" "$REGISTRY_HOST" "$REGISTRY_USER" "$REGISTRY_PASS" "$REGISTRY_EMAIL" "$REGISTRY_NAME"
elif [[ "$SKIP_PULL_SECRET" == false ]]; then
  echo "Skipping registry pull secret; no registry host provided"
fi

cat <<EOF

Setup complete.

Next steps:
  1. Export KUBECONFIG: export KUBECONFIG="$KUBECONFIG_PATH"
  2. Verify access: kubectl get nodes
  3. Update Helm values if needed (storageClass: $STORAGE_CLASS, namespace: $NAMESPACE)
  4. Render or deploy the Vista3D manifests using ./rancher/render_vista3d_manifest.sh or helm.

GPU scheduling reminders:
  - Ensure GPU nodes are labeled (e.g., kubectl label nodes <node> nvidia.com/gpu.present=true)
  - Tolerations may require taints similar to nvidia.com/gpu=present:NoSchedule

EOF

