# Vista3D Rancher Deployment Playbook

This document captures the end-to-end steps (and hard-earned lessons) for standing up the Vista3D stack on a Rancher-managed RKE2/K3s cluster, including storage provisioning and automated tooling.

---

## Prerequisites

- **Rancher CLI** v2.7+ in `PATH` (`rancher --version`).
- **kubectl** that targets your Rancher cluster (for single-node RKE2 the binary is usually `/var/lib/rancher/rke2/bin/kubectl`). If your shell aliases `kubectl` to `microk8s`, point the scripts at the real binary with `--kubectl`.
- **Rancher API token** with cluster admin privileges (`token-xxxx:yyyyy`).
- **Project context ID** (e.g. `local:p-abc12`). Obtain with `rancher projects ls`.
- **NGC API key** saved to a local file for the backend secret.
- **Bash, Helm, kubectl** installed on the host where you run the scripts.

Optional but recommended:
- TLS hostname and secret (or plan to port-forward the frontend).
- Internet access for the script to fetch the local-path provisioner manifest (or replace with an internal mirror).

---

## One-Command Bootstrap

The new `rancher/bootstrap_vista3d.sh` script orchestrates the full workflow:

1. Logs into Rancher, generates kubeconfig, namespace and secrets by calling `setup_rancher_env.sh`.
2. Ensures a working storage class (installs the Rancher Local Path Provisioner when `--storage-class local-path`).
3. Renders the Vista3D Helm chart into a consolidated YAML.
4. Applies the manifest to your cluster.

Example (single-node `local` cluster with local-path storage):

```bash
cd /home/hpadmin/HPE-Nvidia-Vista-3D

./rancher/bootstrap_vista3d.sh \
  --rancher-url https://localhost:8443 \
  --skip-tls-verify \
  --rancher-token token-xxxxx:yyyyy \
  --cluster local \
  --rancher-context local:p-abc12 \
  --ngc-key-file /home/hpadmin/NGC_API_KEY \
  --kubectl /var/lib/rancher/rke2/bin/kubectl \
  --storage-class local-path \
  --render-output ./rancher/vista3d.yaml \
  --non-interactive
```

The script prints progress and reminders. After it finishes:

```bash
export KUBECONFIG=/home/hpadmin/.kube/vista3d-rancher.yaml
/var/lib/rancher/rke2/bin/kubectl get pods -n vista3d
/var/lib/rancher/rke2/bin/kubectl get pvc -n vista3d
```

If you skip ingress, port-forward the frontend for quick access:

```bash
/var/lib/rancher/rke2/bin/kubectl -n vista3d port-forward svc/vista3d-frontend 8501:8501
```

---

## Key Script Flags

`bootstrap_vista3d.sh` accepts most of the underlying script options:

- `--rancher-url`, `--rancher-token`, `--cluster`, `--rancher-context`, `--skip-tls-verify` feed into the Rancher CLI login.
- `--namespace`, `--kubeconfig`, `--kubectl` allow custom namespace and tooling paths.
- `--storage-class` selects the PVC storage class. Use `--install-storage` to force reinstalling the local-path provisioner.
- `--preserve-pvcs` keeps existing `vista3d-output-pvc` and `vista3d-dicom-pvc`. By default they are deleted to avoid immutable storage-class conflicts.
- `--ingress-host`, `--ingress-class`, `--ingress-tls-secret` enable ingress in the rendered manifest.
- `--backend-tag`, `--frontend-tag`, `--image-server-tag`, `--image-registry`, `--image-pull-secret` control image overrides.
- `--skip-manifest`, `--skip-apply`, `--dry-run` split the workflow if you only want setup or render.

See `./rancher/setup_rancher_env.sh --help` and `./rancher/render_vista3d_manifest.sh --help` for fine-grained control.

---

## Storage Options

- **Local Path Provisioner (recommended for single-node clusters)**  
  The bootstrap script installs it automatically when using `--storage-class local-path`. This avoids the complexity of Longhorn (which requires `open-iscsi` and shared mount propagation).

- **Longhorn (advanced)**  
  If you prefer Longhorn, install it through Rancher Apps or Helm *before* running the bootstrap script, then invoke the script with `--storage-class longhorn --install-storage=false`. Ensure `/` is mounted with `rshared` propagation and `open-iscsi` is active on every node.

- **Static hostPath PVs**  
  For one-off demos you can create static PVs and point the chart to them, but the bootstrap automation assumes a dynamic storage class.

---

## Troubleshooting Notes

- **MicroK8s alias**: Some environments alias `kubectl` to `microk8s kubectl`. Use `--kubectl /var/lib/rancher/rke2/bin/kubectl` so the script talks to the Rancher cluster.

- **PVC storage class mismatch**: Kubernetes forbids changing `storageClassName` on existing PVCs. Delete `vista3d-output-pvc` / `vista3d-dicom-pvc` (or run without `--preserve-pvcs`) before switching from Longhorn to local-path.

- **Longhorn shared mounts**: If you return to Longhorn, run `sudo mount --make-rshared /` and add an `ExecStartPre` systemd override for `rke2-server` to persist the setting. Install `open-iscsi` and ensure `iscsid` is running.

- **Rancher CLI prompts**: Supply `--rancher-context` to avoid hidden prompts when the scripts call `rancher login`. Obtain the context with `rancher projects ls`.

---

## Manual Workflow (If Needed)

1. `./rancher/setup_rancher_env.sh --help` — prepares kubeconfig, namespace, secrets.
2. Install a storage backend (`local-path` or Longhorn).
3. `./rancher/render_vista3d_manifest.sh --namespace vista3d --storage-class local-path --output ./rancher/vista3d.yaml --non-interactive`.
4. `/var/lib/rancher/rke2/bin/kubectl --kubeconfig ~/.kube/vista3d-rancher.yaml apply -f ./rancher/vista3d.yaml`.

The `bootstrap_vista3d.sh` script encapsulates these steps but the manual commands remain available for debugging.

---

## Clean-Up

To remove the deployment:

```bash
/var/lib/rancher/rke2/bin/kubectl --kubeconfig ~/.kube/vista3d-rancher.yaml delete -f ./rancher/vista3d.yaml
/var/lib/rancher/rke2/bin/kubectl --kubeconfig ~/.kube/vista3d-rancher.yaml delete namespace vista3d
```

If you installed local-path provisioner solely for Vista3D:

```bash
/var/lib/rancher/rke2/bin/kubectl --kubeconfig ~/.kube/vista3d-rancher.yaml delete ns local-path-storage
```

---

By keeping the scripts and this guide together under `./rancher`, we can rerun the entire provisioning flow quickly when moving to new clusters or recovering from a failed attempt. Pull requests welcome for additional automation or cloud-specific tweaks.

