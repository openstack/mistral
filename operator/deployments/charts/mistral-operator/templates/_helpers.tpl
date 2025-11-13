{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "mistral-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "mistral-operator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "mistral-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "mistral-operator.labels" -}}
helm.sh/chart: {{ include "mistral-operator.chart" . }}
{{ include "mistral-operator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "mistral-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mistral-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "mistral-operator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "mistral-operator.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}


{{- define "restricted.globalPodSecurityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: "RuntimeDefault"
{{- end -}}

{{- define "restricted.globalContainerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/*
Configure Mistral service 'enableDisasterRecovery' property
*/}}
{{- define "mistral.enableDisasterRecovery" -}}
  {{- if or (eq .Values.disasterRecovery.mode "active") (eq .Values.disasterRecovery.mode "standby") (eq .Values.disasterRecovery.mode "disable") -}}
    {{- printf "true" }}
  {{- else -}}
    {{- printf "false" }}
  {{- end -}}
{{- end -}}

{{/*
Ingress host for Mistral
*/}}
{{- define "mistral.ingressHost" -}}
  {{- if .Values.mistral.ingress.host }}
    {{- .Values.mistral.ingress.host }}
  {{- end -}}
{{- end -}}

{{/*
Postgres host for Mistral.
*/}}
{{- define "mistral.pgHost" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_HOST | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_HOST }}
  {{- else -}}
    {{- .Values.mistralCommonParams.postgres.host -}}
  {{- end -}}
{{- end -}}

{{/*
Postgres port for Mistral.
*/}}
{{- define "mistral.pgPort" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_PORT | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_PORT }}
  {{- else -}}
    {{- .Values.mistralCommonParams.postgres.port -}}
  {{- end -}}
{{- end -}}

{{/*
Postgres admin username for Mistral.
*/}}
{{- define "mistral.pgAdminUser" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_ADMIN_USERNAME | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_ADMIN_USERNAME }}
  {{- else -}}
    {{- .Values.secrets.pgAdminUser -}}
  {{- end -}}
{{- end -}}

{{/*
Postgres admin password for Mistral.
*/}}
{{- define "mistral.pgAdminPass" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_ADMIN_PASSWORD | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_ADMIN_PASSWORD }}
  {{- else -}}
    {{- .Values.secrets.pgAdminPassword -}}
  {{- end -}}
{{- end -}}

{{/*
Postgres username for Mistral.
*/}}
{{- define "mistral.pgUser" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_MISTRAL_USERNAME | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_MISTRAL_USERNAME }}
  {{- else -}}
    {{- .Values.secrets.pgUser -}}
  {{- end -}}
{{- end -}}

{{/*
Postgres password for Mistral.
*/}}
{{- define "mistral.pgPass" -}}
  {{- if and (ne (.Values.INFRA_POSTGRES_MISTRAL_PASSWORD | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_POSTGRES_MISTRAL_PASSWORD }}
  {{- else if and (.Values.secrets.pgPassword) (ne (.Values.secrets.pgPassword | toString) "") -}}
    {{- .Values.secrets.pgPassword }}
  {{- else -}}
    {{- printf "mistral_nc" }}
  {{- end -}}
{{- end -}}

{{/*
Postgres DB name for Mistral
*/}}
{{- define "mistral.pgDbName" -}}
  {{- if .Values.mistralCommonParams.postgres.dbName }}
    {{- .Values.mistralCommonParams.postgres.dbName }}
  {{- else -}}
    {{- printf "mistral-%s" .Release.Namespace }}
  {{- end -}}
{{- end -}}

{{/*
Postgres transaction idle in session timeout Mistral
*/}}
{{- define "mistral.idleTimeout" -}}
  {{- if .Values.mistralCommonParams.postgres.idleTimeout }}
    {{- .Values.mistralCommonParams.postgres.idleTimeout }}
  {{- else -}}
    {{- printf "30s" }}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ VHost name for Mistral
*/}}
{{- define "mistral.rabbitmqVHost" -}}
  {{- if .Values.mistralCommonParams.rabbit.vhost }}
    {{- .Values.mistralCommonParams.rabbit.vhost }}
  {{- else -}}
    {{- printf "mistral-%s" .Release.Namespace }}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ host for Mistral.
*/}}
{{- define "mistral.rabbitHost" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_HOST | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_HOST }}
  {{- else -}}
    {{- .Values.mistralCommonParams.rabbit.host -}}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ port for Mistral.
*/}}
{{- define "mistral.rabbitPort" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_PORT | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_PORT }}
  {{- else -}}
    {{- .Values.mistralCommonParams.rabbit.port -}}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ admin username for Mistral.
*/}}
{{- define "mistral.rabbitAdminUser" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_ADMIN_USERNAME | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_ADMIN_USERNAME }}
  {{- else -}}
    {{- .Values.secrets.rabbitAdminUser -}}
  {{- end -}}
{{- end -}}

{{/*
RabbitMQ admin password for Mistral.
*/}}
{{- define "mistral.rabbitAdminPassword" -}}
  {{- if and (ne (.Values.INFRA_RABBITMQ_ADMIN_PASSWORD | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_RABBITMQ_ADMIN_PASSWORD }}
  {{- else -}}
    {{- .Values.secrets.rabbitAdminPassword -}}
  {{- end -}}
{{- end -}}


{{/*
Kafka host for Mistral.
*/}}
{{- define "mistral.kafkaHost" -}}
  {{- if and (ne (.Values.INFRA_KAFKA_BOOTSTRAP_SERVER | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_KAFKA_BOOTSTRAP_SERVER }}
  {{- else -}}
    {{- .Values.mistralCommonParams.kafkaNotifications.host -}}
  {{- end -}}
{{- end -}}

{{/*
Kafka admin username for Mistral.
*/}}
{{- define "mistral.kafkaAdminUsername" -}}
  {{- if and (ne (.Values.INFRA_KAFKA_ADMIN_USERNAME | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_KAFKA_ADMIN_USERNAME }}
  {{- else -}}
    {{- .Values.secrets.kafkaSaslPlainUsername -}}
  {{- end -}}
{{- end -}}

{{/*
Kafka admin password for Mistral.
*/}}
{{- define "mistral.kafkaAdminPassword" -}}
  {{- if and (ne (.Values.INFRA_KAFKA_ADMIN_PASSWORD | toString) "<nil>") .Values.mistral.cloudIntegrationEnabled -}}
    {{- .Values.INFRA_KAFKA_ADMIN_PASSWORD }}
  {{- else -}}
    {{- .Values.secrets.kafkaSaslPlainPassword -}}
  {{- end -}}
{{- end -}}

{{/*
Kafka topic name for Mistral
*/}}
{{- define "mistral.kafkaTopic" -}}
  {{- if .Values.mistralCommonParams.kafkaNotifications.topic }}
    {{- .Values.mistralCommonParams.kafkaNotifications.topic }}
  {{- else -}}
    {{- printf "mistral-%s" .Release.Namespace }}
  {{- end -}}
{{- end -}}

{{/*
Whether Mistral SSL enabled
*/}}
{{- define "mistral.enableTls" -}}
  {{- .Values.mistral.tls.enabled -}}
{{- end -}}

{{/*
Whether Mistral certificates are Specified
*/}}
{{- define "mistral.certificatesSpecified" -}}
  {{- $filled := false -}}
  {{- range $key, $value := .Values.mistral.tls.certificates -}}
    {{- if $value -}}
        {{- $filled = true -}}
    {{- end -}}
  {{- end -}}
  {{- $filled -}}
{{- end -}}

{{/*
Provider used to generate SSL certificates
*/}}
{{- define "services.certProvider" -}}
  {{- default "helm" .Values.mistral.tls.generateCerts.certProvider -}}
{{- end -}}

{{/*
Mistral SSL secret name
*/}}
{{- define "mistral.tlsSecretName" -}}
  {{- if .Values.mistral.tls.enabled -}}
    {{- if and (or .Values.mistral.tls.generateCerts.enabled (eq (include "mistral.certificatesSpecified" .) "true")) (not .Values.mistral.tls.secretName) -}}
      {{- printf "mistral-tls-secret" -}}
    {{- else -}}
      {{- .Values.mistral.tls.secretName -}}
    {{- end -}}
  {{- else -}}
    {{- "" -}}
  {{- end -}}
{{- end -}}

{{/*
  Mistral Monitoring scheme
  */}}
  {{- define "mistral.monitoringScheme" -}}
    {{- if and .Values.mistral.tls.enabled .Values.mistral.tls.services.monitoring.enabled -}}
      {{- printf "https" -}}
    {{- else -}}
      {{- printf "http" -}}
  {{- end -}}
{{- end -}}

{{/*
DNS names used to generate SSL certificate with "Subject Alternative Name" field
*/}}
{{- define "mistral.certDnsNames" -}}
  {{- $mistralName := "mistral" -}}
  {{- $mistralMonitoringName := "mistral-monitoring" -}}
  {{- $dnsNames := list "localhost" $mistralName $mistralMonitoringName (printf "%s.%s" $mistralName .Release.Namespace) (printf "%s.%s.svc.cluster.local" $mistralName .Release.Namespace) (printf "%s.%s.svc" $mistralName .Release.Namespace) (printf "%s.%s" $mistralMonitoringName .Release.Namespace) (printf "%s.%s.svc.cluster.local" $mistralMonitoringName .Release.Namespace) (printf "%s.%s.svc" $mistralMonitoringName .Release.Namespace) -}}
  {{ if (eq .Values.mistral.ingress.enabled true) }}
  {{- $dnsNames = append $dnsNames .Values.mistral.ingress.host -}}
  {{- end -}}
  {{- $dnsNames = concat $dnsNames .Values.mistral.tls.subjectAlternativeName.additionalDnsNames -}}
  {{- $dnsNames | toYaml -}}
{{- end -}}

{{/*
IP addresses used to generate SSL certificate with "Subject Alternative Name" field
*/}}
{{- define "mistral.certIpAddresses" -}}
  {{- $ipAddresses := list "127.0.0.1" -}}
  {{- $ipAddresses = concat $ipAddresses .Values.mistral.tls.subjectAlternativeName.additionalIpAddresses -}}
  {{- $ipAddresses | toYaml -}}
{{- end -}}

{{/*
Generate certificates for Mistral
*/}}
{{- define "mistral.generateCerts" -}}
  {{- $dnsNames := include "mistral.certDnsNames" . | fromYamlArray -}}
  {{- $ipAddresses := include "mistral.certIpAddresses" . | fromYamlArray -}}
  {{- $duration := default 365 .Values.mistral.tls.generateCerts.durationDays | int -}}
  {{- $ca := genCA "mistral-ca" $duration -}}
  {{- $mistralName := "mistral" -}}
  {{- $cert := genSignedCert $mistralName $ipAddresses $dnsNames $duration $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
ca.crt: {{ $ca.Cert | b64enc }}
{{- end -}}

{{/*
Whether bluegreenAgent is enabled
*/}}
{{- define "bluegreenAgent.enabled" -}}
  {{- .Values.bluegreenAgent.enabled -}}
{{- end -}}


{{/*
Define if we need perform db cleanup
*/}}
{{- define "mistral.cleanup" -}}
{{- if and (hasKey .Values.mistralCommonParams "cleanup") (ne .Values.mistralCommonParams.cleanup "") }}
    {{- .Values.mistralCommonParams.cleanup -}}
{{- else if eq .Values.DEPLOY_MODE "CleanInstall" }}
    true
{{- else }}
    false
{{- end -}}
{{- end -}}


{{/*
Service Account for Site Manager depending on smSecureAuth
*/}}
{{- define "disasterRecovery.siteManagerServiceAccount" -}}
  {{- if .Values.disasterRecovery.httpAuth.smServiceAccountName -}}
    {{- .Values.disasterRecovery.httpAuth.smServiceAccountName -}}
  {{- else -}}
    {{- if .Values.disasterRecovery.httpAuth.smSecureAuth -}}
      {{- "site-manager-sa" -}}
    {{- else -}}
      {{- "sm-auth-sa" -}}
    {{- end -}}
  {{- end -}}
{{- end -}}


{{/*
Whether integrationTests is enabled
*/}}
{{- define "integrationTests.enabled" -}}
  {{- .Values.integrationTests.enabled -}}
{{- end -}}


{{- define "mistral.liteEnabled" -}}
  {{- .Values.mistral.liteEnabled -}}
{{- end -}}


{{/*
Find mistral operator image in open source values.
*/}}
{{- define "mistral.operatorId" -}}
  {{- .Values.operatorImage | sha1sum -}}
{{- end -}}


{{/*
Find mistral docker image in open source values.
*/}}
{{- define "mistral.dockerImage" -}}
  {{- printf "%s" .Values.mistral.dockerImage -}}
{{- end -}}


{{/*
Find mistral tests image in open source values.
*/}}
{{- define "mistral.testsImage" -}}
  {{- printf "%s" .Values.integrationTests.dockerImage -}}
{{- end -}}

{{/*
Find disaster recovery image in open source values.
*/}}
{{- define "disasterRecovery.image" -}}
  {{- printf "%s" .Values.disasterRecovery.image -}}
{{- end -}}


{{/*
Monitor mistral images for deployments in open source (returns empty string).
*/}}
{{- define "mistral.monitoredImages" -}}
  ""
{{- end -}}

{{/*
Whether Disaster recovery TLS enabled
*/}}
{{- define "disasterRecovery.enableTls" -}}
  {{- and .Values.mistral.tls.enabled .Values.mistral.tls.services.disasterRecovery.enabled -}}
{{- end -}}

{{/*
Protocol for DRD
*/}}
{{- define "disasterRecovery.protocol" -}}
{{- if eq (include "disasterRecovery.enableTls" .) "true" -}}
  {{- "https://" -}}
{{- else -}}
  {{- "http://" -}}
{{- end -}}
{{- end -}}


{{/*
Determining whether IDP JWK Secrets should be populated
*/}}
{{- define "idpSecrets.populate" -}}
{{- $auth := toString (default false .Values.mistralCommonParams.auth.enable) | lower -}}
{{- if (eq $auth "true") -}}
{{- if and
  (not (empty .Values.secrets.idpClientId))
  (ne  (toString .Values.secrets.idpClientId) "null")
-}}
idp-client-id: {{ .Values.secrets.idpClientId | b64enc }}
{{- end -}}
{{- if and
  (not (empty .Values.secrets.idpClientSecret))
  (ne  (toString .Values.secrets.idpClientSecret) "null")
-}}
idp-client-secret: {{ .Values.secrets.idpClientSecret | b64enc }}
{{- end -}}
{{- if and
  (not (empty .Values.secrets.idpJwkExp))
  (ne  (toString .Values.secrets.idpJwkExp) "null")
-}}
idp-jwk-exp: {{ .Values.secrets.idpJwkExp | b64enc }}
{{- end -}}
{{- if and
  (not (empty .Values.secrets.idpJwkMod))
  (ne  (toString .Values.secrets.idpJwkMod) "null")
-}}
idp-jwk-mod: {{ .Values.secrets.idpJwkMod | b64enc }}
{{- end -}}
{{- else -}}
idp-client-id: {{ .Values.secrets.idpClientId | b64enc }}
idp-client-secret: {{ .Values.secrets.idpClientSecret | b64enc }}
idp-jwk-exp: {{ .Values.secrets.idpJwkExp | b64enc }}
idp-jwk-mod: {{ .Values.secrets.idpJwkMod | b64enc }}
{{- end -}}
{{- end -}}

{{/*
Truncate string to less than 63 chars
*/}}
{{- define "truncateString" -}}
{{- $str := . | toString  -}}
{{- if gt (len $str) 63 -}}
  {{- $version := regexReplaceAll "^[0-9]+\\.[0-9]+\\.[0-9]+-" $str ""  -}}
  {{- regexReplaceAll "-([0-9]+)\\.0\\.0-" $version "$1-" | trunc 62 | trimSuffix "-" -}}
{{- else -}}
  {{- $str -}}
{{- end -}}
{{- end -}}

{{/*
Helm version for helm chart
*/}}
{{- define "mistralOperator.version" -}}
{{- if .Values.kubernetesLabels.mistralOperator.version -}}
  {{- template "truncateString" .Values.kubernetesLabels.mistralOperator.version -}}
{{- else -}}
  {{- template "truncateString" .Chart.Version -}}
{{- end -}}
{{- end -}}
