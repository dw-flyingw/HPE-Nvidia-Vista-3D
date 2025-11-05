{{/*
Expand the name of the chart.
*/}}
{{- define "vista3d.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "vista3d.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "vista3d.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "vista3d.labels" -}}
helm.sh/chart: {{ include "vista3d.chart" . }}
{{ include "vista3d.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "vista3d.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vista3d.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "vista3d.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vista3d.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the frontend service
*/}}
{{- define "vista3d.frontend.serviceName" -}}
{{- printf "%s-frontend" (include "vista3d.fullname" .) }}
{{- end }}

{{/*
Create the name of the image server service
*/}}
{{- define "vista3d.imageServer.serviceName" -}}
{{- printf "%s-image-server" (include "vista3d.fullname" .) }}
{{- end }}

{{/*
Create the name of the backend service
*/}}
{{- define "vista3d.backend.serviceName" -}}
{{- printf "%s-backend" (include "vista3d.fullname" .) }}
{{- end }}

{{/*
Create the name of the frontend deployment
*/}}
{{- define "vista3d.frontend.deploymentName" -}}
{{- printf "%s-frontend" (include "vista3d.fullname" .) }}
{{- end }}

{{/*
Create the name of the image server deployment
*/}}
{{- define "vista3d.imageServer.deploymentName" -}}
{{- printf "%s-image-server" (include "vista3d.fullname" .) }}
{{- end }}

{{/*
Create the name of the backend deployment
*/}}
{{- define "vista3d.backend.deploymentName" -}}
{{- printf "%s-backend" (include "vista3d.fullname" .) }}
{{- end }}

