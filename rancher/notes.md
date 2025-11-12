docker run -d --restart=unless-stopped --name rancher  -p 8080:80 -p 8443:443   --privileged   rancher/rancher:latest
docker logs rancher 2>&1 | grep "Bootstrap Password:"
export KUBECONFIG=/path/to/rancher-cluster-kubeconfig.yaml kubectl get nodes
export NGC_API_KEY='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'
./rancher/helm/NGC_API_KEY


export RANCHER_TOKEN='4vrrl2xgmgtzdf8ld46vgds2ttq4vccw9p2p6mssc7fnr4f8m27pl8'

access key
token-kv928

secret key
4vrrl2xgmgtzdf8ld46vgds2ttq4vccw9p2p6mssc7fnr4f8m27pl8

bearer token
token-kv928:4vrrl2xgmgtzdf8ld46vgds2ttq4vccw9p2p6mssc7fnr4f8m27pl8


rancher login https://localhost:8443 --skip-verify --token token-kv928:4vrrl2xgmgtzdf8ld46vgds2ttq4vccw9p2p6mssc7fnr4f8m27pl8


AdminToken2
token-m8nbw
2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm
token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm

rancher clusters ls

./rancher/setup_rancher_env.sh \
  --rancher-url https://localhost:8443 \
  --rancher-token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
  --cluster local \
  --ngc-key-file ~/path/to/ngc.key \
  --skip-pull-secret   # only if you don’t need a registry credential


export RANCHER_TOKEN='token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm'



./rancher/setup_rancher_env.sh \
  --rancher-url https://localhost:8443 \
  --rancher-token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
  --cluster local \
  --ngc-key-file /home/hpadmin/NGC_API_KEY



export KUBECONFIG=/home/hpadmin/.kube/vista3d-rancher.yaml


   rancher login https://localhost:8443 \
     --skip-verify \
     --token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
     --context local \
     --set-default

./rancher/setup_rancher_env.sh \
  --rancher-url https://localhost:8443 \
  --rancher-token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
  --cluster local \
  --ngc-key-file /home/hpadmin/NGC_API_KEY

 rancher projects ls
ID              NAME      STATE     DESCRIPTION
local:p-2fzct   Default   active    Default project created for the cluster
local:p-88wcg   System    active    System project created for the cluster


   rancher login https://localhost:8443 \
     --skip-verify \
     --token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
     --context local:p-2fzct \
     --set-default

INFO[0000] Saving config to /home/hpadmin/.rancher/cli2.json 


./rancher/setup_rancher_env.sh \
  --rancher-url https://localhost:8443 \
  --rancher-token token-m8nbw:2kctcsv2rdhcz66j6gqjdmsvhsdp7x7t6z848w82jv5z4fgf5kblnm \
  --cluster local \
  --ngc-key-file /home/hpadmin/NGC_API_KEY


export KUBECONFIG=/home/hpadmin/.kube/vista3d-rancher.yaml
kubectl get storageclass          # see what exists, e.g. local-path


export KUBECONFIG=/home/hpadmin/.kube/vista3d-rancher.yaml
kubectl config get-contexts      # optional sanity check
kubectl get storageclass

   /var/lib/rancher/rke2/bin/kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml get storageclass

   unalias kubectl          # only affects current shell
   hash -r
   kubectl version --client




./rancher/render_vista3d_manifest.sh \
  --namespace vista3d \
  --storage-class longhorn \
  --output ./rancher/vista3d.yaml


   /var/lib/rancher/rke2/bin/kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml apply -f ./rancher/vista3d.yaml






   kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml -n vista3d delete secret ngc-regcred --ignore-not-found

   kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml \
     -n vista3d create secret docker-registry ngc-regcred \
     --docker-server=nvcr.io \
     --docker-username='$oauthtoken' \
     --docker-password="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"\


   kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml \
     -n vista3d create secret docker-registry ngc-regcred \
     --docker-server=nvcr.io \
     --docker-username='$oauthtoken' \
     --docker-password="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" \
     --docker-email=dave.wright@hpe.com


kubectl --kubeconfig /home/hpadmin/.kube/vista3d-rancher.yaml \
  -n vista3d port-forward svc/vista3d-frontend 8501:8501

export KUBECONFIG=/home/hpadmin/.kube/vista3d-rancher.yaml

export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
