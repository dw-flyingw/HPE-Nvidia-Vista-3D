docker run -d --restart=unless-stopped --name rancher  -p 8080:80 -p 8443:443   --privileged   rancher/rancher:latest
docker logs rancher 2>&1 | grep "Bootstrap Password:"
