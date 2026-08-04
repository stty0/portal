#!/bin/bash
# certbot 갱신 → k8s TLS Secret 동기화
#
# Traefik은 `dt-hpc-tls` Secret의 사본을 쓰므로, certbot이 인증서를 갱신해도
# Secret을 갱신하지 않으면 **만료된 인증서를 계속 제공한다**(조용히 깨진다).
#
# 설치:
#   sudo install -m 755 certbot-deploy-hook.sh /etc/letsencrypt/renewal-hooks/deploy/hpc-portal-tls.sh
# 확인:
#   sudo certbot renew --dry-run
set -euo pipefail

LINEAGE_NAME="www.dt-hpc.net"
NAMESPACE="hpc-portal"
SECRET="dt-hpc-tls"
KUBECTL="/usr/local/bin/kubectl"
KUBECONFIG_PATH="/etc/rancher/k3s/k3s.yaml"

# deploy 훅은 갱신된 모든 인증서에 대해 실행된다 — 우리 것만 처리한다.
if [[ "${RENEWED_LINEAGE:-}" != "/etc/letsencrypt/live/${LINEAGE_NAME}" ]]; then
    exit 0
fi

"${KUBECTL}" --kubeconfig="${KUBECONFIG_PATH}" -n "${NAMESPACE}" \
    create secret tls "${SECRET}" \
    --cert="${RENEWED_LINEAGE}/fullchain.pem" \
    --key="${RENEWED_LINEAGE}/privkey.pem" \
    --dry-run=client -o yaml \
  | "${KUBECTL}" --kubeconfig="${KUBECONFIG_PATH}" apply -f -

# Traefik의 Kubernetes CRD provider가 Secret 변경을 감시해 자동 반영하므로
# 재시작하지 않는다. hostPort는 노드당 하나뿐이라 rollout이 자기 자신과 충돌해
# 새 파드가 Pending으로 멈춘다.

logger -t hpc-portal-tls "k8s Secret ${NAMESPACE}/${SECRET} 갱신 완료 (${LINEAGE_NAME})"
