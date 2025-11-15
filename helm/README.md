# Deploying Helm Chart in PCAI

* `cd helm && helm package .`
* deploy Vista3D NIM in PCAI
    * get url and generate api key
* Click Import Frameworks Button in Tools & Frameworks
* Go through the step to install PCAI
* When you are updating the values.yaml stage, update the following environment variables:
    * `VISTA3D_SERVER`
    * `VISTA3D_API_KEY`


# MLIS
add this whitelist to Vista3D 
DOMAIN_WHITELIST =  [".*","http://.*","https://.*","http://.*:.*","https://.*:.*","file:///.*","*"]
 
