Vista3D Helm Chart
==================

Deploy the HPE NVIDIA Vista3D stack (backend NIM microservice, Streamlit frontend, and image server) onto a Rancher-managed Kubernetes cluster.

Prerequisites
-------------
- A Rancher 2.7+ installation with a downstream cluster provisioned and available.
- Cluster nodes with NVIDIA GPUs and the NVIDIA GPU Operator or equivalent GPU device plugin installed.
- Persistent storage class capable of ReadWriteOnce for large volumes (e.g., Longhorn, EBS, or CSI-backed storage).
- Optional: a private image registry credential stored as a Kubernetes secret (e.g., `regcred`).

Configuration
-------------
The chart is driven from `values.yaml`. For Rancher-specific overrides, copy or reference `values-rancher.yaml`:

```bash
helm install vista3d ./vista3d \
  --namespace vista3d \
  --create-namespace \
  -f values-rancher.yaml \
  --set-file secrets.ngcApiKey=/path/to/ngc.key
```

Key values to review:
- `global.imageRegistry` / `global.imagePullSecrets` — point to private registries mirrored inside your environment.
- `backend`, `frontend`, `imageServer` — image tags, GPU requests, and environment variables.
- `persistence.*` — storage class and capacity. Ensure the chosen class is available on the Rancher cluster.
- `ingress` — enable and set hostname when exposing outside the cluster.
- `secrets.ngcApiKey` — required to pull NIM models from NVIDIA NGC.

Packaging & Publishing
----------------------
Package the chart and either upload it to a Helm repository or import into Rancher as a Catalog app:

```bash
cd rancher/helm
make lint
make package

# To host in a Helm repo (e.g., GitHub Pages):
HELM_REPO_URL=https://<org>.github.io/<repo>/ make index
```

In Rancher UI, add the Helm repository under **Apps & Marketplace → Repositories**, then install the chart release from the UI.

Installation via Rancher UI
---------------------------
1. Navigate to **Apps & Marketplace → Charts** and locate the Vista3D chart (after adding your repo) or drag-and-drop the packaged `.tgz` file.
2. Choose the target namespace (e.g., `vista3d`) and paste overrides from `values-rancher.yaml`.
3. Upload the NGC API key as a secret (Rancher will create it) or pre-create it in the namespace and reference via `global.imagePullSecrets`.
4. Launch the app and monitor the workloads under **Workload → Deployments** to verify the desired containers (`nvcr.io/nim/nvidia/vista3d`, `dwtwp/vista3d-frontend`, `dwtwp/vista3d-image-server`) are running.

Scripted Deployment (RKE2 CLI)
------------------------------
Operators with `kubectl` access to the Rancher-managed RKE2 cluster can use the helper script in `rancher/helm/deploy-vista3d.sh` to perform a repeatable CLI deployment.

```bash
cd rancher/helm
./deploy-vista3d.sh \
  --ngc-key-file /secure/path/ngc.key \
  --namespace vista3d \
  --set ingress.hosts[0].host=vista3d.example.com
```

Key details:
- The script wraps `helm upgrade --install` with the Rancher-oriented defaults from `vista3d/values-rancher.yaml`.
- `--ngc-key-file` (or `NGC_API_KEY_FILE`) points to a local file containing the NGC API key so the chart can populate the secret required by the backend pod.
- Supply additional Helm overrides via repeated `--set` flags or by pointing `--values` to a custom values file.
- Use `--dry-run` to preview manifests and `--skip-ngc` if the secret already exists in the namespace.
- After the command completes, monitor the rollout with `kubectl get pods -n <namespace>`.

Validation
----------
- Confirm PVCs are bound (`kubectl get pvc -n vista3d`).
- Check GPU pods schedule on GPU nodes (`kubectl describe pod -n vista3d vista3d-backend-*`).
- Access the frontend through the configured ingress or NodePort to validate end-to-end functionality.

