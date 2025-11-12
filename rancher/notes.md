# Rancher Quick Notes

- Bootstrap Rancher for local testing:
  - `docker run -d --restart=unless-stopped --name rancher -p 8080:80 -p 8443:443 --privileged rancher/rancher:latest`
  - `docker logs rancher 2>&1 | grep "Bootstrap Password:"`
- Export your Rancher token as `RANCHER_TOKEN=token-xxxx:yyyy` and keep it out of version control.
- Common `setup_rancher_env.sh` invocation:
  ```bash
  ./rancher/setup_rancher_env.sh \
    --rancher-url https://localhost:8443 \
    --rancher-token "$RANCHER_TOKEN" \
    --cluster local \
    --ngc-key-file /home/hpadmin/NGC_API_KEY \
    --kubectl /var/lib/rancher/rke2/bin/kubectl \
    --non-interactive
  ```
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

