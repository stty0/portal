{{- define "hpc-portal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "hpc-portal.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "hpc-portal.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "hpc-portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: hpc-portal
{{- end -}}

{{/*
  이미 있는 Secret에서 값을 꺼낸다. 없으면 fallback.

  **비밀번호를 업그레이드마다 새로 만들면 안 된다** — MySQL 볼륨에는 옛 비밀번호가 그대로
  남아 있어 파드가 뜨지 못한다. `lookup`은 `helm template`·`--dry-run`에서 빈 값을
  돌려주므로(API 서버를 안 본다) 그때는 fallback이 쓰인다 — 렌더 결과만 다르고
  실제 설치·업그레이드는 기존 값을 지킨다.
*/}}
{{- define "hpc-portal.keepSecret" -}}
{{- $ctx := index . 0 -}}
{{- $name := index . 1 -}}
{{- $key := index . 2 -}}
{{- $fallback := index . 3 -}}
{{- $found := (lookup "v1" "Secret" $ctx.Release.Namespace $name) -}}
{{- if and $found (hasKey ($found.data | default dict) $key) -}}
{{- index $found.data $key | b64dec -}}
{{- else -}}
{{- $fallback -}}
{{- end -}}
{{- end -}}

{{/*
  자격증명을 **한 렌더 안에서 한 번만** 정한다.

  `randAlphaNum`은 부를 때마다 다른 값을 준다. MySQL Secret과 백엔드의 DATABASE_URL이
  각자 부르면 **서로 다른 비밀번호를 갖게 되고 첫 설치부터 접속이 실패한다**(실제로 렌더해
  보고 잡았다 — URL에 비밀번호가 비어 있었다).

  `.Values`는 모든 템플릿이 공유하는 같은 map이라 여기에 적어 두면 두 번째 호출부터는
  같은 값이 나온다. 우선순위는 values > 기존 Secret > 새 난수다.
*/}}
{{- define "hpc-portal.credential" -}}
{{- $ctx := index . 0 -}}
{{- $cache := index . 1 -}}
{{- $given := index . 2 -}}
{{- $secretName := index . 3 -}}
{{- $key := index . 4 -}}
{{- if not (hasKey $ctx.Values $cache) -}}
{{- $existing := include "hpc-portal.keepSecret" (list $ctx $secretName $key "") -}}
{{- $_ := set $ctx.Values $cache (coalesce $given $existing (randAlphaNum 32)) -}}
{{- end -}}
{{- get $ctx.Values $cache -}}
{{- end -}}

{{- define "hpc-portal.mysqlPassword" -}}
{{- include "hpc-portal.credential" (list . "__mysqlPassword" .Values.mysql.password (include "hpc-portal.mysqlSecretName" .) "password") -}}
{{- end -}}

{{- define "hpc-portal.mysqlRootPassword" -}}
{{- include "hpc-portal.credential" (list . "__mysqlRootPassword" .Values.mysql.rootPassword (include "hpc-portal.mysqlSecretName" .) "root-password") -}}
{{- end -}}

{{- define "hpc-portal.redisPassword" -}}
{{- include "hpc-portal.credential" (list . "__redisPassword" .Values.redis.password (include "hpc-portal.redisSecretName" .) "password") -}}
{{- end -}}

{{- define "hpc-portal.jwtSecret" -}}
{{- include "hpc-portal.credential" (list . "__jwtSecret" .Values.backend.jwtSecret (include "hpc-portal.backendSecretName" .) "PORTAL_JWT_SECRET") -}}
{{- end -}}

{{- define "hpc-portal.setupToken" -}}
{{- include "hpc-portal.credential" (list . "__setupToken" .Values.backend.setupToken (include "hpc-portal.backendSecretName" .) "PORTAL_SETUP_TOKEN") -}}
{{- end -}}

{{- define "hpc-portal.mysqlSecretName" -}}
{{- .Values.mysql.existingSecret | default (printf "%s-mysql" (include "hpc-portal.fullname" .)) -}}
{{- end -}}

{{- define "hpc-portal.redisSecretName" -}}
{{- .Values.redis.existingSecret | default (printf "%s-redis" (include "hpc-portal.fullname" .)) -}}
{{- end -}}

{{- define "hpc-portal.backendSecretName" -}}
{{- .Values.backend.existingSecret | default (printf "%s-backend-env" (include "hpc-portal.fullname" .)) -}}
{{- end -}}

{{- define "hpc-portal.knownHostsSecretName" -}}
{{- .Values.backend.existingSshKnownHostsSecret | default (printf "%s-known-hosts" (include "hpc-portal.fullname" .)) -}}
{{- end -}}

{{- define "hpc-portal.backendImage" -}}
{{- printf "%s:%s" .Values.image.backend.repository (.Values.image.backend.tag | default .Chart.AppVersion) -}}
{{- end -}}

{{- define "hpc-portal.frontendImage" -}}
{{- printf "%s:%s" .Values.image.frontend.repository (.Values.image.frontend.tag | default .Chart.AppVersion) -}}
{{- end -}}

{{/*
  PVC가 가리킬 StorageClass 이름. **차트가 만들지 않는 이름을 가리키면 렌더를 멈춘다.**

  이 조합이 조용히 통과하면 PVC가 Pending에서 멈추고 → MySQL이 안 뜨고 → 백엔드
  init 컨테이너(alembic)가 계속 실패한다. 파드 목록만 보면 원인이 안 보이는 자리라
  **설치 전에** 끊는다.
*/}}
{{- define "hpc-portal.mysqlStorageClass" -}}
{{- $name := .Values.mysql.storage.className -}}
{{- if and $name (eq $name .Values.storageClass.name) (not .Values.storageClass.create) -}}
{{- fail (printf "mysql.storage.className=%s 인데 storageClass.create=false 입니다. 그 StorageClass가 클러스터에 이미 있으면 이 값을 그대로 두고, 없으면 --set storageClass.create=true 로 만들거나 mysql.storage.className=\"\" 로 비워 클러스터 기본을 쓰세요." $name) -}}
{{- end -}}
{{- $name -}}
{{- end -}}
