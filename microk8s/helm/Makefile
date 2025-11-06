CHART_NAME ?= vista3d
CHART_DIR ?= $(CHART_NAME)
DIST_DIR ?= dist

.PHONY: lint
lint:
	helm lint $(CHART_DIR)

.PHONY: package
package: | $(DIST_DIR)
	helm package $(CHART_DIR) --destination $(DIST_DIR)

.PHONY: index
index: package
	helm repo index $(DIST_DIR) --url $${HELM_REPO_URL:?set HELM_REPO_URL}

$(DIST_DIR):
	mkdir -p $(DIST_DIR)

