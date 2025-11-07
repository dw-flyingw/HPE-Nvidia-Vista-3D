#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CHART_DIR="$SCRIPT_DIR/helm/vista3d"
DEFAULT_VALUES_FILE="$CHART_DIR/values-rancher.yaml"
DEFAULT_OUTPUT_PATH=${VISTA3D_RENDER_OUTPUT:-$SCRIPT_DIR/vista3d-generated.yaml}

usage() {
  cat <<'EOF'
Usage: render_vista3d_manifest.sh [options]

Generate a Rancher-importable Kubernetes manifest for Vista3D using the Helm chart.

Options:
  --release NAME           Helm release name (default: vista3d)
  --namespace NAME         Kubernetes namespace (default: vista3d)
  --values FILE            Additional Helm values file (repeatable)
  --set key=val            Additional Helm --set override (repeatable)
  --set-string key=val     Additional Helm --set-string override (repeatable)
  --storage-class NAME     Override persistence.storageClass (default: longhorn)
  --output PATH            Output YAML path (default: ./rancher/vista3d-generated.yaml)
  --ingress-host HOST      Hostname for ingress (enables ingress when set)
  --ingress-class CLASS    Ingress class name (default: nginx)
  --ingress-tls-secret SEC TLS secret for ingress (enables TLS block when set)
  --image-registry REG     Prefix all images with custom registry
  --backend-tag TAG        Backend image tag override (default: 1.0.0)
  --frontend-tag TAG       Frontend image tag override (default: microk8s-latest)
  --image-server-tag TAG   Image server image tag override (default: microk8s-latest)
  --output-size SIZE       PVC size for output data (default: 200Gi)
  --dicom-size SIZE        PVC size for dicom data (default: 100Gi)
  --image-pull-secret NAME Reference imagePullSecrets entry (optional)
  --save-overrides PATH    Write temporary overrides file to a persistent path
  --non-interactive        Do not prompt for missing values
  --skip-deps              Skip 'helm dependency update'
  --dry-run                Show Helm command without rendering manifests
  --help                   Show this help message

Environment:
  VISTA3D_NAMESPACE, VISTA3D_RELEASE, VISTA3D_RENDER_OUTPUT

Example:
  ./render_vista3d_manifest.sh --namespace vista3d --ingress-host vista3d.example.com \
      --ingress-tls-secret vista3d-tls --output ./rancher/vista3d.yaml
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
  local current_value="${!var_name-}"

  if [[ -n "$current_value" ]]; then
    return
  fi

  if [[ "$NON_INTERACTIVE" == true ]]; then
    die "Missing required value for $var_name"
  fi

  read -rp "$prompt_text" current_value
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

NON_INTERACTIVE=false
SKIP_DEPS=false
DRY_RUN=false

RELEASE_NAME=${VISTA3D_RELEASE:-vista3d}
NAMESPACE=${VISTA3D_NAMESPACE:-vista3d}
STORAGE_CLASS=${VISTA3D_STORAGE_CLASS:-longhorn}
OUTPUT_PATH="$DEFAULT_OUTPUT_PATH"
INGRESS_HOST=${VISTA3D_INGRESS_HOST:-}
INGRESS_CLASS=${VISTA3D_INGRESS_CLASS:-nginx}
INGRESS_TLS_SECRET=${VISTA3D_INGRESS_TLS_SECRET:-}
IMAGE_REGISTRY=${VISTA3D_IMAGE_REGISTRY:-}
IMAGE_PULL_SECRET=${VISTA3D_IMAGE_PULL_SECRET:-}
BACKEND_TAG=${VISTA3D_BACKEND_TAG:-1.0.0}
FRONTEND_TAG=${VISTA3D_FRONTEND_TAG:-microk8s-latest}
IMAGESERVER_TAG=${VISTA3D_IMAGE_SERVER_TAG:-microk8s-latest}
OUTPUT_SIZE=${VISTA3D_OUTPUT_SIZE:-200Gi}
DICOM_SIZE=${VISTA3D_DICOM_SIZE:-100Gi}
OVERRIDE_PATH=""

VALUES_FILES=()
SET_ARGS=()
SET_STRING_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release)
      RELEASE_NAME="$2"; shift 2 ;;
    --namespace)
      NAMESPACE="$2"; shift 2 ;;
    --values)
      VALUES_FILES+=("$2"); shift 2 ;;
    --set)
      SET_ARGS+=(--set "$2"); shift 2 ;;
    --set-string)
      SET_STRING_ARGS+=(--set-string "$2"); shift 2 ;;
    --storage-class)
      STORAGE_CLASS="$2"; shift 2 ;;
    --output)
      OUTPUT_PATH="$2"; shift 2 ;;
    --ingress-host)
      INGRESS_HOST="$2"; shift 2 ;;
    --ingress-class)
      INGRESS_CLASS="$2"; shift 2 ;;
    --ingress-tls-secret)
      INGRESS_TLS_SECRET="$2"; shift 2 ;;
    --image-registry)
      IMAGE_REGISTRY="$2"; shift 2 ;;
    --backend-tag)
      BACKEND_TAG="$2"; shift 2 ;;
    --frontend-tag)
      FRONTEND_TAG="$2"; shift 2 ;;
    --image-server-tag)
      IMAGESERVER_TAG="$2"; shift 2 ;;
    --output-size)
      OUTPUT_SIZE="$2"; shift 2 ;;
    --dicom-size)
      DICOM_SIZE="$2"; shift 2 ;;
    --image-pull-secret)
      IMAGE_PULL_SECRET="$2"; shift 2 ;;
    --save-overrides)
      OVERRIDE_PATH="$2"; shift 2 ;;
    --non-interactive)
      NON_INTERACTIVE=true; shift ;;
    --skip-deps)
      SKIP_DEPS=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      die "Unknown option: $1" ;;
  esac
done

ensure_cmd helm

if [[ ! -d "$CHART_DIR" ]]; then
  die "Helm chart directory '$CHART_DIR' not found"
fi

if [[ ! -f "$DEFAULT_VALUES_FILE" ]]; then
  die "Default values file '$DEFAULT_VALUES_FILE' not found"
fi

if [[ "${#VALUES_FILES[@]}" -gt 0 ]]; then
  for vf in "${VALUES_FILES[@]}"; do
    [[ -f "$vf" ]] || die "Values file '$vf' not found"
  done
fi

if [[ -z "$INGRESS_HOST" ]]; then
  if [[ "$NON_INTERACTIVE" == false ]]; then
    if confirm "Configure ingress?"; then
      prompt_if_empty INGRESS_HOST "Ingress hostname: "
      read -rp "TLS secret (leave blank for none): " INGRESS_TLS_SECRET
    fi
  fi
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

if [[ -z "$OVERRIDE_PATH" ]]; then
  if ! OVERRIDE_PATH=$(mktemp 2>/dev/null); then
    fallback_dir="$SCRIPT_DIR/tmp"
    mkdir -p "$fallback_dir"
    OVERRIDE_PATH=$(mktemp -p "$fallback_dir")
  fi
  CLEANUP_OVERRIDE=true
else
  CLEANUP_OVERRIDE=false
  mkdir -p "$(dirname "$OVERRIDE_PATH")"
fi

cleanup() {
  if [[ "${CLEANUP_OVERRIDE:-false}" == true ]]; then
    rm -f "$OVERRIDE_PATH"
  fi
}

trap cleanup EXIT

INGRESS_ENABLED=false
if [[ -n "$INGRESS_HOST" ]]; then
  INGRESS_ENABLED=true
fi

{
  echo "# Generated overrides for Vista3D"
  echo "global:"
  echo "  imageRegistry: \"${IMAGE_REGISTRY}\""
  if [[ -n "$IMAGE_PULL_SECRET" ]]; then
    echo "  imagePullSecrets:"
    echo "    - name: ${IMAGE_PULL_SECRET}"
  else
    echo "  imagePullSecrets: []"
  fi
  echo "backend:"
  echo "  image:"
  echo "    tag: \"${BACKEND_TAG}\""
  echo "frontend:"
  echo "  image:"
  echo "    tag: \"${FRONTEND_TAG}\""
  echo "imageServer:"
  echo "  image:"
  echo "    tag: \"${IMAGESERVER_TAG}\""
  echo "persistence:"
  echo "  storageClass: \"${STORAGE_CLASS}\""
  echo "  output:"
  echo "    size: \"${OUTPUT_SIZE}\""
  echo "  dicom:"
  echo "    size: \"${DICOM_SIZE}\""
  echo "ingress:"
  if [[ "$INGRESS_ENABLED" == true ]]; then
    echo "  enabled: true"
    echo "  className: \"${INGRESS_CLASS}\""
    echo "  hosts:"
    echo "    - host: ${INGRESS_HOST}"
    echo "      paths:"
    echo "        - path: /"
    echo "          pathType: Prefix"
    if [[ -n "$INGRESS_TLS_SECRET" ]]; then
      echo "  tls:"
      echo "    - hosts:"
      echo "        - ${INGRESS_HOST}"
      echo "      secretName: ${INGRESS_TLS_SECRET}"
    else
      echo "  tls: []"
    fi
  else
    echo "  enabled: false"
    echo "  hosts: []"
    echo "  tls: []"
  fi
} >"$OVERRIDE_PATH"

echo "# Vista3D Helm rendering"
echo "Release:     $RELEASE_NAME"
echo "Namespace:   $NAMESPACE"
echo "Output:      $OUTPUT_PATH"
echo "Overrides:   $OVERRIDE_PATH"

INGRESS_STATUS=$([[ "$INGRESS_ENABLED" == true ]] && echo "$INGRESS_HOST" || echo "disabled")
echo "Ingress:     $INGRESS_STATUS"

if [[ "$SKIP_DEPS" == false ]]; then
  echo "Updating Helm dependencies"
  helm dependency update "$CHART_DIR" >/dev/null
fi

helm_cmd=(helm template "$RELEASE_NAME" "$CHART_DIR" -n "$NAMESPACE" -f "$DEFAULT_VALUES_FILE")

for vf in "${VALUES_FILES[@]}"; do
  helm_cmd+=(-f "$vf")
done

helm_cmd+=(-f "$OVERRIDE_PATH")

if [[ ${#SET_ARGS[@]} -gt 0 ]]; then
  helm_cmd+=("${SET_ARGS[@]}")
fi

if [[ ${#SET_STRING_ARGS[@]} -gt 0 ]]; then
  helm_cmd+=("${SET_STRING_ARGS[@]}")
fi

if [[ "$DRY_RUN" == true ]]; then
  echo "Helm command: ${helm_cmd[*]}"
  exit 0
fi

echo "Rendering manifests"
"${helm_cmd[@]}" >"$OUTPUT_PATH"

echo "Manifest written to $OUTPUT_PATH"
echo "Import into Rancher via 'Apps & Marketplace' > 'Import YAML' or apply with kubectl."

