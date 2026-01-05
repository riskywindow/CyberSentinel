{{/*
Expand the name of the chart.
*/}}
{{- define "cybersentinel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "cybersentinel.fullname" -}}
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
{{- define "cybersentinel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "cybersentinel.labels" -}}
helm.sh/chart: {{ include "cybersentinel.chart" . }}
{{ include "cybersentinel.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "cybersentinel.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cybersentinel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "cybersentinel.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "cybersentinel.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the config map
*/}}
{{- define "cybersentinel.configMapName" -}}
{{- printf "%s-config" (include "cybersentinel.fullname" .) }}
{{- end }}

{{/*
Create the name of the secret
*/}}
{{- define "cybersentinel.secretName" -}}
{{- printf "%s-secret" (include "cybersentinel.fullname" .) }}
{{- end }}

{{/*
Get the postgres host
*/}}
{{- define "cybersentinel.postgresHost" -}}
{{- if .Values.clickhouse.enabled }}
{{- printf "%s-postgresql" (include "cybersentinel.fullname" .) }}
{{- else }}
{{- .Values.clickhouse.external.host }}
{{- end }}
{{- end }}

{{/*
Get the redis host
*/}}
{{- define "cybersentinel.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "cybersentinel.fullname" .) }}
{{- else }}
{{- .Values.redis.external.host }}
{{- end }}
{{- end }}

{{/*
Get the clickhouse host
*/}}
{{- define "cybersentinel.clickhouseHost" -}}
{{- if .Values.clickhouse.enabled }}
{{- printf "%s-clickhouse" (include "cybersentinel.fullname" .) }}
{{- else }}
{{- .Values.clickhouse.external.host }}
{{- end }}
{{- end }}

{{/*
Get the neo4j host
*/}}
{{- define "cybersentinel.neo4jHost" -}}
{{- if .Values.neo4j.enabled }}
{{- printf "%s-neo4j" (include "cybersentinel.fullname" .) }}
{{- else }}
{{- .Values.neo4j.external.host }}
{{- end }}
{{- end }}

{{/*
Get the NATS host
*/}}
{{- define "cybersentinel.natsHost" -}}
{{- if .Values.nats.enabled }}
{{- printf "%s-nats" (include "cybersentinel.fullname" .) }}
{{- else }}
{{- .Values.nats.external.host }}
{{- end }}
{{- end }}

{{/*
Create image pull secret
*/}}
{{- define "cybersentinel.imagePullSecret" -}}
{{- printf "{\"auths\":{\"%s\":{\"username\":\"%s\",\"password\":\"%s\",\"email\":\"%s\",\"auth\":\"%s\"}}}" .registry .username .password .email (printf "%s:%s" .username .password | b64enc) | b64enc }}
{{- end }}

{{/*
Validate required values
*/}}
{{- define "cybersentinel.validateValues" -}}
{{- if and (not .Values.clickhouse.enabled) (not .Values.clickhouse.external.host) }}
{{- fail "Either enable ClickHouse or provide external host" }}
{{- end }}
{{- if and (not .Values.redis.enabled) (not .Values.redis.external.host) }}
{{- fail "Either enable Redis or provide external host" }}
{{- end }}
{{- if and (not .Values.neo4j.enabled) (not .Values.neo4j.external.host) }}
{{- fail "Either enable Neo4j or provide external host" }}
{{- end }}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "cybersentinel.commonEnv" -}}
- name: ENVIRONMENT
  value: {{ .Values.app.environment | quote }}
- name: APP_VERSION
  value: {{ .Chart.AppVersion | quote }}
- name: RELEASE_NAME
  value: {{ .Release.Name | quote }}
- name: NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
- name: NODE_NAME
  valueFrom:
    fieldRef:
      fieldPath: spec.nodeName
{{- end }}

{{/*
Resource limits and requests
*/}}
{{- define "cybersentinel.resources" -}}
{{- if .resources }}
resources:
  {{- if .resources.limits }}
  limits:
    {{- if .resources.limits.cpu }}
    cpu: {{ .resources.limits.cpu }}
    {{- end }}
    {{- if .resources.limits.memory }}
    memory: {{ .resources.limits.memory }}
    {{- end }}
  {{- end }}
  {{- if .resources.requests }}
  requests:
    {{- if .resources.requests.cpu }}
    cpu: {{ .resources.requests.cpu }}
    {{- end }}
    {{- if .resources.requests.memory }}
    memory: {{ .resources.requests.memory }}
    {{- end }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
OpenTelemetry environment variables
*/}}
{{- define "cybersentinel.otelEnv" -}}
{{- $component := .component -}}
{{- with .root }}
{{- if .Values.monitoring.tracing.enabled }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ .Values.monitoring.tracing.endpoint | quote }}
- name: OTEL_SERVICE_NAME
  value: "{{ .Values.monitoring.tracing.serviceName }}-{{ $component }}"
- name: OTEL_SERVICE_VERSION
  value: {{ .Chart.AppVersion | quote }}
- name: OTEL_TRACES_SAMPLER
  value: "traceidratio"
- name: OTEL_TRACES_SAMPLER_ARG
  value: {{ .Values.monitoring.tracing.samplingRatio | quote }}
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.name={{ .Values.monitoring.tracing.serviceName }}-{{ $component }},service.version={{ .Chart.AppVersion }},deployment.environment={{ .Values.app.environment }},component={{ $component }}"
{{- if eq $component "api" }}
- name: OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST
  value: "content-type,authorization"
- name: OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE
  value: "content-type"
{{- end }}
{{- end }}
{{- end }}
{{- end }}