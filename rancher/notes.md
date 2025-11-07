docker run -d --restart=unless-stopped --name rancher  -p 8080:80 -p 8443:443   --privileged   rancher/rancher:latest
docker logs rancher 2>&1 | grep "Bootstrap Password:"
export KUBECONFIG=/path/to/rancher-cluster-kubeconfig.yaml kubectl get nodes
export NGC_API_KEY='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'
./rancher/helm/NGC_API_KEY


