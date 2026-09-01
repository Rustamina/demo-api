{{/*
_helpers.tpl — файл с переиспользуемыми кусками шаблонов.

Имя начинается с подчёркивания: Helm считает такие файлы служебными
и не пытается отправить их результат в кластер как манифест.

Синтаксис: define объявляет именованный шаблон, include его вызывает.
*/}}

{{/*
Базовое имя чарта. Используется как основа для имён ресурсов.
default берёт первый непустой аргумент: если nameOverride пуст,
возьмётся .Chart.Name.
trunc 63 и trimSuffix "-" — потому что имена в Kubernetes ограничены
63 символами (это требование DNS-1123), а обрезка не должна оставить
дефис на конце.
*/}}
{{- define "demo-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Полное имя ресурсов: <релиз>-<чарт>.
Правила:
  - если задан fullnameOverride, используем его как есть;
  - если имя релиза уже содержит имя чарта (например, релиз назвали
    "demo-api"), не дублируем — получится "demo-api", а не
    "demo-api-demo-api";
  - иначе склеиваем через дефис.

printf "%s-%s" — форматирование строки, как в Go/C.
contains проверяет вхождение подстроки.
*/}}
{{- define "demo-api.fullname" -}}
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
Строка вида "demo-api-1.0.0" для лейбла helm.sh/chart.
replace "+" "_" — в SemVer допустим плюс (build metadata),
а в значениях лейблов Kubernetes он запрещён.
*/}}
{{- define "demo-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Полный набор лейблов. Префикс app.kubernetes.io/ — это
стандартные рекомендованные лейблы Kubernetes. Их понимают
сторонние инструменты: kubectl, Lens, дашборды Grafana.

managed-by: Helm — по нему Helm отличает свои ресурсы от чужих.
*/}}
{{- define "demo-api.labels" -}}
helm.sh/chart: {{ include "demo-api.chart" . }}
{{ include "demo-api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Селекторные лейблы — подмножество, по которому Deployment находит
свои поды, а Service — эндпоинты.

Их выделяют отдельно, потому что selector у Deployment ИММУТАБЕЛЕН.
Если бы туда попал app.kubernetes.io/version, то при каждом обновлении
версии селектор менялся бы, и helm upgrade падал бы с ошибкой.
Это одна из тех вещей, которую понимаешь только после того,
как один раз на неё наступишь.
*/}}
{{- define "demo-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "demo-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Имя ServiceAccount: либо заданное явно, либо сгенерированное.
*/}}
{{- define "demo-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "demo-api.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

