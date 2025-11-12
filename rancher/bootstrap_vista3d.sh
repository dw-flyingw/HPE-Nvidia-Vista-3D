#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

DEFAULT_NAMESPACE=${VISTA3D_NAMESPACE:-vista3d}
DEFAULT_STORAGE_CLASS=${VISTA3D_STORAGE_CLASS:-local-path}
DEFAULT_KUBECONFIG=${VISTA3D_KUBECONFIG_PATH:-$HOME/.kube/vista3d-rancher.yaml}
DEFAULT_RENDER_OUTPUT=${VISTA3D_RENDER_OUTPUT:-$SCRIPT_DIR/vista3d.yaml}
DEFAULT_LOCAL_PATH_MANIFEST="$SCRIPT_DIR/local-path-storage.yaml"

usage() {
  cat <<'EOF'
Usage: bootstrap_vista3d.sh [options]

End-to-end Rancher preparation and deployment for the Vista3D stack. The script:
  1. Runs setup_rancher_env.sh to login, grab kubeconfig, namespace, and secrets.
  2. Ensures a working StorageClass (installs local-path provisioner if selected).
  3. Renders the Vista3D manifests via render_vista3d_manifest.sh.
  4. Applies the manifest to the target cluster.

Options:
  --rancher-url URL          Rancher server URL (https://host:port)
  --rancher-token TOKEN      Rancher API token (token-xxxx:yyyyy)
  --cluster NAME_OR_ID       Rancher cluster name or ID (e.g. local or c-m-xxxx)
  --ngc-key-file PATH        Path to NGC API key file for backend secret
  --rancher-context ID       Rancher project context (e.g. local:p-xxxxx)
  --skip-tls-verify          Pass --skip-verify to Rancher CLI login
  --namespace NAME           Kubernetes namespace for Vista3D (default: vista3d)
  --kubeconfig PATH          Path for kubeconfig emitted by setup script (default: ~/.kube/vista3d-rancher.yaml)
  --kubectl PATH             kubectl binary to use (default: kubectl)
  --storage-class NAME       StorageClass to use for PVCs (default: local-path)
  --install-storage          Force install of storage class manifest even if it exists
  --ingress-host HOST        Enable ingress in rendered manifest with provided host
  --ingress-class CLASS      IngressClass name (default: nginx)
  --ingress-tls-secret SEC   TLS secret name for ingress
  --render-output PATH       Destination for rendered manifest (default: ./rancher/vista3d.yaml)
  --skip-manifest            Skip rendering/applying the Helm manifest
  --skip-apply               Render manifests but skip kubectl apply
  --preserve-pvcs            Do not delete existing vista3d PVCs before apply
  --backend-tag TAG          Override backend image tag
  --frontend-tag TAG         Override frontend image tag
  --image-server-tag TAG     Override image server image tag
  --image-registry FQDN      Registry prefix for all images
  --image-pull-secret NAME   imagePullSecret name to reference in values
  --non-interactive          Pass through to child scripts to avoid prompts
  --skip-deps                Skip helm dependency update during render
  --dry-run                  Show commands without executing kubectl apply
  --help                     Show this help and exit

Examples:
  ./bootstrap_vista3d.sh \
    --rancher-url https://localhost:8443 \
    --rancher-token token-abc:xyz \
    --cluster local \
    --rancher-context local:p-12345 \
    --ngc-key-file ~/NGC_API_KEY

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

kubectl_cmd=()

run_kubectl() {
  "${kubectl_cmd[@]}" "$@"
}

RANCHER_URL=${RANCHER_URL:-}
RANCHER_TOKEN=${RANCHER_TOKEN:-}
RANCHER_CLUSTER=${RANCHER_CLUSTER:-}
RANCHER_CONTEXT=${RANCHER_CONTEXT:-}
NGC_KEY_FILE=${NGC_API_KEY_FILE:-}
NAMESPACE="$DEFAULT_NAMESPACE"
KUBECONFIG_PATH="$DEFAULT_KUBECONFIG"
KUBECTL_PATH=${KUBECTL_PATH:-kubectl}
STORAGE_CLASS="$DEFAULT_STORAGE_CLASS"
INSTALL_STORAGE=false
LOCAL_PATH_MANIFEST=${LOCAL_PATH_MANIFEST:-$DEFAULT_LOCAL_PATH_MANIFEST}
INGRESS_HOST=${VISTA3D_INGRESS_HOST:-}
INGRESS_CLASS=${VISTA3D_INGRESS_CLASS:-nginx}
INGRESS_TLS_SECRET=${VISTA3D_INGRESS_TLS_SECRET:-}
RENDER_OUTPUT="$DEFAULT_RENDER_OUTPUT"
SKIP_MANIFEST=false
SKIP_APPLY=false
PRESERVE_PVCS=false
IMAGE_REGISTRY=${VISTA3D_IMAGE_REGISTRY:-}
IMAGE_PULL_SECRET=${VISTA3D_IMAGE_PULL_SECRET:-}
BACKEND_TAG=${VISTA3D_BACKEND_TAG:-}
FRONTEND_TAG=${VISTA3D_FRONTEND_TAG:-}
IMAGESERVER_TAG=${VISTA3D_IMAGE_SERVER_TAG:-}
NON_INTERACTIVE=false
SKIP_HELM_DEPS=false
DRY_RUN=false
SKIP_TLS_VERIFY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rancher-url)
      RANCHER_URL="$2"; shift 2 ;;
    --rancher-token)
      RANCHER_TOKEN="$2"; shift 2 ;;
    --cluster)
      RANCHER_CLUSTER="$2"; shift 2 ;;
    --ngc-key-file)
      NGC_KEY_FILE="$2"; shift 2 ;;
    --rancher-context)
      RANCHER_CONTEXT="$2"; shift 2 ;;
    --skip-tls-verify)
      SKIP_TLS_VERIFY=true; shift ;;
    --namespace)
      NAMESPACE="$2"; shift 2 ;;
    --kubeconfig)
      KUBECONFIG_PATH="$2"; shift 2 ;;
    --kubectl)
      KUBECTL_PATH="$2"; shift 2 ;;
    --storage-class)
      STORAGE_CLASS="$2"; shift 2 ;;
    --install-storage)
      INSTALL_STORAGE=true; shift ;;
    --ingress-host)
      INGRESS_HOST="$2"; shift 2 ;;
    --ingress-class)
      INGRESS_CLASS="$2"; shift 2 ;;
    --ingress-tls-secret)
      INGRESS_TLS_SECRET="$2"; shift 2 ;;
    --render-output)
      RENDER_OUTPUT="$2"; shift 2 ;;
    --skip-manifest)
      SKIP_MANIFEST=true; shift ;;
    --skip-apply)
      SKIP_APPLY=true; shift ;;
    --preserve-pvcs)
      PRESERVE_PVCS=true; shift ;;
    --image-registry)
      IMAGE_REGISTRY="$2"; shift 2 ;;
    --image-pull-secret)
      IMAGE_PULL_SECRET="$2"; shift 2 ;;
    --backend-tag)
      BACKEND_TAG="$2"; shift 2 ;;
    --frontend-tag)
      FRONTEND_TAG="$2"; shift 2 ;;
    --image-server-tag)
      IMAGESERVER_TAG="$2"; shift 2 ;;
    --non-interactive)
      NON_INTERACTIVE=true; shift ;;
    --skip-deps)
      SKIP_HELM_DEPS=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      die "Unknown option: $1" ;;
  esac
done

if [[ "$KUBECTL_PATH" == "kubectl" ]] && ! command -v kubectl >/dev/null 2>&1 && [[ -x /var/lib/rancher/rke2/bin/kubectl ]]; then
  echo "kubectl binary not found in PATH; using /var/lib/rancher/rke2/bin/kubectl"
  KUBECTL_PATH=/var/lib/rancher/rke2/bin/kubectl
fi

ensure_cmd bash
ensure_cmd "$KUBECTL_PATH"

setup_args=()
[[ -n "$RANCHER_URL" ]] && setup_args+=(--rancher-url "$RANCHER_URL")
[[ -n "$RANCHER_TOKEN" ]] && setup_args+=(--rancher-token "$RANCHER_TOKEN")
[[ -n "$RANCHER_CLUSTER" ]] && setup_args+=(--cluster "$RANCHER_CLUSTER")
[[ -n "$NGC_KEY_FILE" ]] && setup_args+=(--ngc-key-file "$NGC_KEY_FILE")
[[ -n "$RANCHER_CONTEXT" ]] && setup_args+=(--rancher-context "$RANCHER_CONTEXT")
[[ "$SKIP_TLS_VERIFY" == true ]] && setup_args+=(--skip-tls-verify)
[[ -n "$NAMESPACE" ]] && setup_args+=(--namespace "$NAMESPACE")
[[ -n "$KUBECONFIG_PATH" ]] && setup_args+=(--kubeconfig "$KUBECONFIG_PATH")
[[ "$NON_INTERACTIVE" == true ]] && setup_args+=(--non-interactive)

echo ">> Running Rancher environment setup"
"$SCRIPT_DIR/setup_rancher_env.sh" "${setup_args[@]}"

export KUBECONFIG="$KUBECONFIG_PATH"
kubectl_cmd=("$KUBECTL_PATH" --kubeconfig "$KUBECONFIG")

local_path_manifest_available() {
  [[ -f "$LOCAL_PATH_MANIFEST" ]]
}

apply_local_path_provisioner() {
  if ! local_path_manifest_available; then
    die "Local Path manifest '$LOCAL_PATH_MANIFEST' not found. Set LOCAL_PATH_MANIFEST or add the bundled file."
  fi
  echo "Applying local-path provisioner manifest from $LOCAL_PATH_MANIFEST"
  run_kubectl apply -f "$LOCAL_PATH_MANIFEST"
  echo "Waiting for local-path namespace to settle..."
  run_kubectl wait --for=condition=Established --timeout=60s crd/storageclasses.storage.k8s.io >/dev/null 2>&1 || true
  echo "Waiting for local-path-provisioner deployment to become ready..."
  run_kubectl rollout status deployment/local-path-provisioner -n local-path-storage --timeout=180s
}

is_local_path_ready() {
  local available
  available=$(run_kubectl get deployment/local-path-provisioner -n local-path-storage -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "")
  [[ "$available" =~ ^[1-9] ]]
}

configmap_present() {
  run_kubectl -n local-path-storage get configmap/local-path-config >/dev/null 2>&1
}

ensure_storage_class() {
  local reinstall_reason=""

  if [[ "$STORAGE_CLASS" != "local-path" ]]; then
    if [[ "$INSTALL_STORAGE" == true ]]; then
      die "Automatic install only implemented for 'local-path'. Please provision '$STORAGE_CLASS' manually."
    fi
    if ! run_kubectl get storageclass "$STORAGE_CLASS" >/dev/null 2>&1; then
      die "StorageClass '$STORAGE_CLASS' not found. Install it or re-run with --storage-class local-path."
    fi
    echo "StorageClass '$STORAGE_CLASS' detected (custom provisioning assumed)."
    return
  fi

  if run_kubectl get storageclass local-path >/dev/null 2>&1; then
    if [[ "$INSTALL_STORAGE" == true ]]; then
      reinstall_reason="--install-storage requested"
    elif ! is_local_path_ready; then
      reinstall_reason="deployment not ready"
    elif ! configmap_present; then
      reinstall_reason="ConfigMap local-path-config missing"
    fi

    if [[ -z "$reinstall_reason" ]]; then
      echo "Local-path StorageClass present and provisioner healthy."
      return
    fi

    echo "Reinstalling local-path provisioner ($reinstall_reason)."
  else
    echo "Local-path StorageClass not found; installing bundled manifest."
  fi

  apply_local_path_provisioner
}

ensure_storage_class

if [[ "$PRESERVE_PVCS" == false && "$SKIP_MANIFEST" == false ]]; then
  echo "Deleting existing Vista3D PVCs to ensure clean redeploy (use --preserve-pvcs to skip)."
  run_kubectl delete pvc vista3d-output-pvc vista3d-dicom-pvc -n "$NAMESPACE" --ignore-not-found
fi

if [[ "$SKIP_MANIFEST" == true ]]; then
  echo "Skipping manifest render/apply as requested."
  exit 0
fi

render_args=(--non-interactive --namespace "$NAMESPACE" --storage-class "$STORAGE_CLASS" --output "$RENDER_OUTPUT")
[[ "$SKIP_HELM_DEPS" == true ]] && render_args+=(--skip-deps)
[[ -n "$INGRESS_HOST" ]] && render_args+=(--ingress-host "$INGRESS_HOST" --ingress-class "$INGRESS_CLASS")
[[ -n "$INGRESS_TLS_SECRET" ]] && render_args+=(--ingress-tls-secret "$INGRESS_TLS_SECRET")
[[ -n "$IMAGE_REGISTRY" ]] && render_args+=(--image-registry "$IMAGE_REGISTRY")
[[ -n "$IMAGE_PULL_SECRET" ]] && render_args+=(--image-pull-secret "$IMAGE_PULL_SECRET")
[[ -n "$BACKEND_TAG" ]] && render_args+=(--backend-tag "$BACKEND_TAG")
[[ -n "$FRONTEND_TAG" ]] && render_args+=(--frontend-tag "$FRONTEND_TAG")
[[ -n "$IMAGESERVER_TAG" ]] && render_args+=(--image-server-tag "$IMAGESERVER_TAG")

echo ">> Rendering Vista3D manifest"
"$SCRIPT_DIR/render_vista3d_manifest.sh" "${render_args[@]}"

if [[ "$SKIP_APPLY" == true ]]; then
  echo "Skipping kubectl apply as requested (manifest available at $RENDER_OUTPUT)."
  exit 0
fi

echo ">> Applying Vista3D manifest"
if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] $KUBECTL_PATH --kubeconfig \"$KUBECONFIG\" apply -f \"$RENDER_OUTPUT\""
else
  run_kubectl apply -f "$RENDER_OUTPUT"
fi

cat <<EOF

Vista3D deployment initiated.

Next steps:
  - Monitor pods: $KUBECTL_PATH --kubeconfig "$KUBECONFIG" get pods -n "$NAMESPACE"
  - Verify PVC binding: $KUBECTL_PATH --kubeconfig "$KUBECONFIG" get pvc -n "$NAMESPACE"
  - Port-forward services (if ingress disabled):
      $KUBECTL_PATH --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" port-forward svc/vista3d-frontend 8501:8501
      $KUBECTL_PATH --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" port-forward svc/vista3d-image-server 8888:8888

EOF

