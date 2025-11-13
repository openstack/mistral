{{/*
Find mistral operator image in various places and hash it using sha1.
*/}}
{{- define "mistral.operatorId" -}}
  {{- include "mistral.operatorImage" . | sha1sum -}}
{{- end -}}

{{/*
Find mistral operator image in various places
*/}}
{{- define "mistral.operatorImage" -}}
  {{- if .Values.deployDescriptor -}}
    {{- if hasKey .Values.deployDescriptor "mistral-operator" -}}
      {{- printf "%s" .Values.deployDescriptor "mistral-operator" "image" -}}
    {{- else if hasKey .Values.deployDescriptor "mistral-operator-image" -}}
      {{- printf "%s" .Values.deployDescriptor "mistral-operator-image" "image" -}}
    {{- else -}}
      {{- printf "%s" .Values.deployDescriptor.mistralOperator.image -}}
    {{- end -}}
  {{- else if .Values.mistralOperatorImage -}}
    {{- printf "%s" .Values.mistralOperatorImage -}}
  {{- else -}}
    {{- printf "%s" .Values.operatorImage -}}
  {{- end -}}
{{- end -}}

{{/*
Find mistral bluegreenagent image in various places
*/}}
{{- define "mistral.blueGreenAgentImage" -}}
  {{- if .Values.deployDescriptor -}}
    {{- if hasKey .Values.deployDescriptor "bluegreen-agent" -}}
      {{- printf "%s" .Values.deployDescriptor "bluegreen-agent" "image" -}}
    {{- else -}}
      {{- printf "%s" .Values.deployDescriptor.bluegreenagento.image -}}
    {{- end -}}
  {{- else if .Values.bluegreenAgento -}}
    {{- printf "%s" .Values.bluegreenAgento -}}
  {{- else -}}
    {{- printf "%s" .Values.bluegreenAgent.image -}}
  {{- end -}}
{{- end -}}

{{/*
Find mistral image in various places.
*/}}
{{- define "mistral.dockerImage" -}}
  {{- if .Values.deployDescriptor -}}
    {{- if .Values.mistralImage -}}
      {{- printf "%s" .Values.mistralImage -}}
    {{- else -}}
      {{- printf "%s" .Values.deployDescriptor.mistral.image -}}
    {{- end -}}
  {{- else if .Values.mistralImage -}}
    {{- printf "%s" .Values.mistralImage -}}
  {{- else -}}
    {{- printf "%s" .Values.mistral.dockerImage -}}
  {{- end -}}
{{- end -}}


{{/*
Find mistral tests image in various places.
*/}}
{{- define "mistral.testsImage" -}}
  {{- if .Values.deployDescriptor -}}
    {{- if .Values.deployDescriptor.testsImage -}}
      {{- printf "%s" .Values.deployDescriptor.testsImage -}}
    {{- else -}}
      {{- printf "%s" .Values.deployDescriptor.tests.image -}}
    {{- end -}}
  {{- else if .Values.testsImage -}}
    {{- printf "%s" .Values.testsImage -}}
  {{- else -}}
    {{- printf "%s" .Values.integrationTests.dockerImage -}}
  {{- end -}}
{{- end -}}


{{/*
Find a Mistral disaster recovery service operator image in various places.
Image can be found from:
* SaaS/App deployer (or groovy.deploy.v3) from .Values.disasterRecoveryImage
* DP.Deployer from .Values.deployDescriptor.disasterRecoveryImage.image
* or from default values .Values.disasterRecovery.image
*/}}
{{- define "disasterRecovery.image" -}}
  {{- if .Values.deployDescriptor -}}
    {{- if hasKey .Values.deployDescriptor "disasterRecoveryImage" -}}
      {{- printf "%s" .Values.deployDescriptor.disasterRecoveryImage.image -}}
    {{- else if hasKey .Values.deployDescriptor "prod.platform.streaming_disaster-recovery-daemon" -}}
      {{- printf "%s" (index .Values.deployDescriptor "prod.platform.streaming_disaster-recovery-daemon" "image") -}}
    {{- else -}}
      {{- printf "%s" (index .Values.deployDescriptor "disaster-recovery-daemon" "image") -}}
    {{- end -}}
  {{- else if .Values.disasterRecoveryImage -}}
    {{- printf "%s" .Values.disasterRecoveryImage -}}
  {{- else -}}
    {{- printf "%s" .Values.disasterRecovery.image -}}
  {{- end -}}
{{- end -}}


{{- define "find_image" -}}
  {{- $image := .default -}}
  {{- if .vals.deployDescriptor -}}
    {{- if index .vals.deployDescriptor .SERVICE_NAME -}}
      {{- $image = (index .vals.deployDescriptor .SERVICE_NAME "image") -}}
    {{- end -}}
  {{- end -}}
  {{ printf "%s" $image }}
{{- end -}}



{{- define "mistral.monitoredImages" -}}
  {{- if .Values.deployDescriptor -}}
    {{- printf "deployment mistral-operator mistral-operator %s, " (include "find_image" (dict "SERVICE_NAME" "mistral-operator-image" "vals" .Values "default" "not_found")) -}}

    {{- if (eq (include "mistral.enableDisasterRecovery" .) "true") }}
      {{- printf "deployment mistral-operator mistral-disaster-recovery %s, " (include "find_image" (dict "SERVICE_NAME" "prod.platform.streaming_disaster-recovery-daemon" "vals" .Values "default" "not_found")) -}}
    {{- end -}}

    {{- if eq (include "bluegreenAgent.enabled" .) "true" }}
      {{- printf "deployment mistral-operator bluegreen-agent %s, " (include "find_image" (dict "SERVICE_NAME" "bluegreen-agent" "vals" .Values "default" "not_found")) -}}
    {{- end -}}

    {{- if eq (include "integrationTests.enabled" .) "true" }}
      {{- printf "deployment mistral-tests mistral-tests %s, " (include "find_image" (dict "SERVICE_NAME" "tests" "vals" .Values "default" "not_found")) -}}
    {{- end -}}

    {{- if eq (include "mistral.liteEnabled" .) "false" }}
      {{- printf "deployment mistral-engine mistral-engine %s, " (include "find_image" (dict "SERVICE_NAME" "mistral" "vals" .Values "default" "not_found")) -}}
      {{- printf "deployment mistral-executor mistral-executor %s, " (include "find_image" (dict "SERVICE_NAME" "mistral" "vals" .Values "default" "not_found")) -}}
      {{- printf "deployment mistral-monitoring mistral-monitoring %s, " (include "find_image" (dict "SERVICE_NAME" "mistral" "vals" .Values "default" "not_found")) -}}
      {{- printf "deployment mistral-api mistral-api %s, " (include "find_image" (dict "SERVICE_NAME" "mistral" "vals" .Values "default" "not_found")) -}}
      {{- printf "deployment mistral-notifier mistral-notifier %s, " (include "find_image" (dict "SERVICE_NAME" "mistral" "vals" .Values "default" "not_found")) -}}
    {{- end -}}
  {{- else -}}
    ""
  {{- end -}}
{{- end -}}
