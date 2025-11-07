#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

usage() {
  cat <<'EOF'
Usage: deploy-vista3d.sh [options]

Deploy or upgrade the Vista3D Helm release onto a Rancher-managed RKE2 cluster.

Options:
  -n, --namespace NAME       Kubernetes namespace (default: vista3d)
  -r, --release NAME         Helm release name (default: vista3d)
  -f, --values FILE          Values file to use (default: vista3d/values-rancher.yaml)
  -k, --ngc-key-file FILE    Path to NGC API key file; required unless --skip-ngc is set
      --set key=value        Additional Helm --set overrides (repeatable)
      --dry-run              Run Helm in --dry-run mode
      --skip-ngc             Do not set the NGC API key via --set-file
      --help                 Show this help message

Environment variables:
  NGC_API_KEY_FILE           Default source for --ngc-key-file
  VISTA3D_NAMESPACE          Default namespace
  VISTA3D_RELEASE            Default release name
  VISTA3D_VALUES_FILE        Default values file path

Examples:
  ./deploy-vista3d.sh -k ~/secrets/ngc.key
  ./deploy-vista3d.sh --namespace vista3d-prod --set ingress.hosts[0].host=vista3d.example.com \
      --ngc-key-file /secure/ngc.key
EOF
}

ensure_binary() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' not found in PATH" >&2
    exit 1
  fi
}

namespace=${VISTA3D_NAMESPACE:-vista3d}
release=${VISTA3D_RELEASE:-vista3d}
values_file=${VISTA3D_VALUES_FILE:-"$SCRIPT_DIR/vista3d/values-rancher.yaml"}
ngc_key_file=${NGC_API_KEY_FILE:-""}
skip_ngc=false
dry_run=false
extra_sets=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--namespace)
      [[ $# -lt 2 ]] && { echo "Error: --namespace requires a value" >&2; usage; exit 1; }
      namespace="$2"
      shift 2
      ;;
    -r|--release)
      [[ $# -lt 2 ]] && { echo "Error: --release requires a value" >&2; usage; exit 1; }
      release="$2"
      shift 2
      ;;
    -f|--values)
      [[ $# -lt 2 ]] && { echo "Error: --values requires a file path" >&2; usage; exit 1; }
      values_file="$2"
      shift 2
      ;;
    -k|--ngc-key-file)
      [[ $# -lt 2 ]] && { echo "Error: --ngc-key-file requires a file path" >&2; usage; exit 1; }
      ngc_key_file="$2"
      shift 2
      ;;
    --set)
      [[ $# -lt 2 ]] && { echo "Error: --set requires a value" >&2; usage; exit 1; }
      extra_sets+=("$2")
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --skip-ngc)
      skip_ngc=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option '$1'" >&2
      usage
      exit 1
      ;;
  esac
done

ensure_binary helm
ensure_binary kubectl

if [[ ! -f "$values_file" ]]; then
  echo "Error: values file '$values_file' does not exist" >&2
  exit 1
fi

if [[ "$skip_ngc" == false ]]; then
  if [[ -z "$ngc_key_file" ]]; then
    echo "Error: NGC API key file must be provided via --ngc-key-file or NGC_API_KEY_FILE" >&2
    exit 1
  fi
  if [[ ! -f "$ngc_key_file" ]]; then
    echo "Error: NGC API key file '$ngc_key_file' not found" >&2
    exit 1
  fi
fi

echo "Deploying Vista3D Helm release"
echo "  Release:    $release"
echo "  Namespace:  $namespace"
echo "  Values:     $values_file"
if [[ "$skip_ngc" == true ]]; then
  echo "  NGC key:    skipped (using existing secret or values overrides)"
else
  echo "  NGC key:    $ngc_key_file"
fi
if [[ ${#extra_sets[@]} -gt 0 ]]; then
  printf '  Extra set: %s\n' "${extra_sets[@]}"
fi
if [[ "$dry_run" == true ]]; then
  echo "  Mode:       dry-run"
fi

helm_args=(
  upgrade --install "$release" "$SCRIPT_DIR/vista3d"
  --namespace "$namespace"
  --create-namespace
  -f "$values_file"
)

if [[ "$dry_run" == true ]]; then
  helm_args+=(--dry-run --debug)
fi

if [[ "$skip_ngc" == false ]]; then
  helm_args+=(--set-file "secrets.ngcApiKey=$ngc_key_file")
fi

for set_arg in "${extra_sets[@]}"; do
  helm_args+=(--set "$set_arg")
done

helm "${helm_args[@]}"

echo
echo "Deployment command completed. Use 'kubectl get pods -n $namespace' to monitor pod status."

