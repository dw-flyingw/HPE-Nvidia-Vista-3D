# Rancher Quick Notes

- One-time default setup (keeps secrets out of git):
  ```bash
  cp ./rancher/bootstrap_defaults.env.example ./rancher/bootstrap_defaults.env
  # edit bootstrap_defaults.env with token, context, NGC key path, etc.
  ```
- Bootstrap Rancher for local testing:
  - `docker run -d --restart=unless-stopped --name rancher -p 8080:80 -p 8443:443 --privileged rancher/rancher:latest`
  - `docker logs rancher 2>&1 | grep "Bootstrap Password:"`
- After defaults are set, run the full deploy with no flags:
  ```bash
  ./rancher/bootstrap_vista3d.sh
  ```
- Direct invocation with explicit values (replace `<PROJECT_CONTEXT>` once you have it from `rancher projects ls --cluster local`):
  ```bash
  ./rancher/bootstrap_vista3d.sh \
    --rancher-url https://localhost:8443 \
    --rancher-token token-wwsk6:f7kxc7kw892h4fpjg8vjpc7rv42fb6c2rh46tbw4jjsmml5cw8jwkr \
    --cluster local \
    --rancher-context <PROJECT_CONTEXT> \
    --kubectl /var/lib/rancher/rke2/bin/kubectl \
    --storage-class local-path \
    --install-storage \
    --render-output ./rancher/vista3d.yaml \
    --non-interactive
  ```
- If you later add the backend, append `--ngc-key-file /path/to/NGC_API_KEY` (or set `DEFAULT_NGC_KEY_FILE` in the defaults file) so the secret is created automatically.
- Create the NGC registry secret if the backend image pulls from `nvcr.io`:
  ```bash
  /var/lib/rancher/rke2/bin/kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml \
    -n vista3d create secret docker-registry ngc-regcred \
    --docker-server=nvcr.io \
    --docker-username='$oauthtoken' \
    --docker-password="$(cat /home/hpadmin/NGC_API_KEY)" \
    --docker-email=you@example.com
  ```
- Render-only flow (skip apply, useful for reviewing manifests):
  ```bash
  ./rancher/render_vista3d_manifest.sh \
    --namespace vista3d \
    --storage-class local-path \
    --output ./rancher/vista3d.yaml \
    --non-interactive \
    --dry-run
  ```
- Port-forward helpers when ingress is disabled:
  ```bash
  /var/lib/rancher/rke2/bin/kubectl -n vista3d port-forward svc/vista3d-frontend 8501:8501
  /var/lib/rancher/rke2/bin/kubectl -n vista3d port-forward svc/vista3d-image-server 8888:8888
  ```
- Diagnostics snapshot:
  ```bash
  ./rancher/diagnostics.sh | tee /tmp/vista3d-diag.log
  ```

./rancher/setup_frontend_image_server.sh \
  --rancher-token token-token-wwsk6:f7kxc7kw892h4fpjg8vjpc7rv42fb6c2rh46tbw4jjsmml5cw8jwkr \
  --rancher-context local:p-abc12 \
  --skip-tls-verify

token-8vbhb:cdf5qztkjxv92wswhhvv57f292x5rngljmknj9fkqcbcnkpnwzv5wr
