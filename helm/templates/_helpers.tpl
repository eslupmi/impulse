
# Expand the name of the chart.

{{- define "impulse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}


# Create a default fully qualified app name.
# We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
# If release name contains chart name it will be used as a full name.

{{- define "impulse.fullname" -}}
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


# Create chart name and version as used by the chart label.

{{- define "impulse.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}


# Common labels

{{- define "impulse.labels" -}}
helm.sh/chart: {{ include "impulse.chart" . }}
{{ include "impulse.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.labels }}
{{- toYaml . | nindent 0 }}
{{- end }}
{{- end }}


# Selector labels

{{- define "impulse.selectorLabels" -}}
app.kubernetes.io/name: {{ include "impulse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}


# Create the name of the service account to use

{{- define "impulse.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "impulse.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

# Var for autoscaling
{{- define "impulse.autoscalingEnabled" -}}
{{- if .Values.autoscaling -}}
{{- .Values.autoscaling.enabled | default false -}}
{{- else -}}
false
{{- end -}}
{{- end -}}

# Image name helper
{{- define "impulse.image" -}}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) -}}
{{- end -}}