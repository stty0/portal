# k3s 배포 — Portal DB · Redis · Backend · Traefik

포털 백엔드와 그 의존 서비스를 k3s에 배포한다.
설계 근거: [backend-design.md](../../docs/backend-design.md) §5.2(Traefik/컨테이너)·§5.3(DB)·§5.4(Redis)·§4(세션).

## 접속 URL

| | |
|---|---|
| **포털 (프론트엔드)** | `https://www.dt-hpc.net:9443/` |
| API 베이스 | `https://www.dt-hpc.net:9443/api/v1` |
| Swagger UI | `https://www.dt-hpc.net:9443/api/v1/docs` |
| ReDoc | `https://www.dt-hpc.net:9443/api/v1/redoc` |
| OpenAPI | `https://www.dt-hpc.net:9443/api/v1/openapi.json` |
| HTTP | `http://www.dt-hpc.net:9080/...` → 9443으로 301 |

같은 도메인·포트에서 경로로 가른다 — `/api/**`는 백엔드, **그 외 전부는 SPA**.
Traefik 라우트에 `priority`를 명시해 API 규칙이 SPA catch-all보다 먼저 매칭된다.

> **왜 9080/9443인가**: 이 서버의 80/443은 **기존 nginx**가 점유하고 있고
> `osmo.dt-hpc.net`·`keycloak.dt-hpc.net`의 TLS를 종단한다. 뺏으면 그 서비스가 죽으므로
> Traefik에 별도 포트를 준다. nginx 설정은 **전혀 건드리지 않았다**.

## 구성

| 리소스 | 종류 | 근거 |
|---|---|---|
| `mysql` | StatefulSet 1 replica + PVC 10Gi + liveness/readiness probe | §5.3 — 소규모는 단일 인스턴스, K8s 운영 시 StatefulSet·probe 필수 |
| `local-path-retain` | StorageClass (`reclaimPolicy: Retain`) | §5.3 — k3s 기본 local-path는 Delete라 PVC 삭제 시 데이터 소실 |
| `redis` | Deployment 1 replica, 영속성 없음(emptyDir) | §5.4 — 캐시/세션 용도라 유실 허용, 이중화 불필요 |
| `portal-backend` | Deployment 1 replica + initContainer(`alembic upgrade head`) | §5.2 — 컨테이너 배포. DB/Redis는 **클러스터 내부 DNS**로 접근 |
| `portal-frontend` | Deployment 1 replica (Vue 빌드 산출물 + Nginx, 비루트 8080) | §5.2 — Vue+Nginx 정적 서빙 |
| `portal-api` / `portal-http` | Traefik IngressRoute (+ https-redirect Middleware) | §5.2 — Traefik ingress |
| `traefik` HelmChartConfig | 내장 Traefik의 hostPort를 9080/9443으로 | 80/443은 nginx 점유 |
| `*-nodeport` | NodePort 30306 / 30379 | **개발용** DB/Redis 직접 접근. 운영에서는 제거 |

### hostPort와 업데이트 전략
`hostPort`는 노드당 하나만 바인딩되므로 RollingUpdate는 새 파드가 옛 파드와 포트를 다투다
**Pending으로 멈춘다**. HelmChartConfig에서 `updateStrategy: Recreate`로 고정했다(순간 중단 감수).

## 백엔드 이미지 빌드·반입

k3s는 containerd를 쓰므로 docker 이미지를 별도로 import해야 한다(`imagePullPolicy: Never`).

```bash
cd ../../backend
sudo docker build -t hpc-portal-backend:0.1.0 .
sudo docker save hpc-portal-backend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
kubectl -n hpc-portal rollout restart deploy/portal-backend

cd ../frontend
sudo docker build -t hpc-portal-frontend:0.1.0 .
sudo docker save hpc-portal-frontend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
kubectl -n hpc-portal rollout restart deploy/portal-frontend
```

프론트엔드는 SPA라 nginx가 `try_files … /index.html` 폴백을 담당한다 —
없으면 `/jobs` 같은 경로로 직접 들어오거나 새로고침할 때 404가 난다.

## TLS

certbot 인증서(`/etc/letsencrypt/live/www.dt-hpc.net`)를 k8s Secret `dt-hpc-tls`로 넣어 쓴다.

**갱신 시 Secret도 갱신해야 한다** — 안 하면 Traefik이 만료된 인증서를 계속 제공한다(조용히 깨짐).
[certbot-deploy-hook.sh](certbot-deploy-hook.sh)를 설치해 두면 자동화된다:

```bash
sudo install -m 755 certbot-deploy-hook.sh /etc/letsencrypt/renewal-hooks/deploy/hpc-portal-tls.sh
sudo certbot renew --dry-run   # 훅 동작 확인
```

## 접속이 안 될 때

Traefik 액세스 로그가 켜져 있다. **요청이 서버까지 도달했는지**가 여기서 갈린다 —
이걸 안 보면 NAT/방화벽 문제와 라우팅 문제를 구분할 수 없다.

```bash
kubectl -n kube-system logs deploy/traefik --tail=20 | grep -v '^\x1b'
```

| 로그에 | 의미 | 조치 |
|---|---|---|
| 클라이언트 IP가 **안 보임** | 패킷이 서버에 도달 못 함 | 라우터 포트포워딩 / 방화벽 (아래) |
| 보이고 **404** | 도달함, 경로 불일치 | `/api/...` 경로 확인 |
| 보이고 **502/503** | 도달함, 백엔드 문제 | `kubectl -n hpc-portal logs deploy/portal-backend` |

외부 공개에 필요한 NAT 규칙 (공인 IP `123.41.34.26`):

```
TCP 9443 → 192.168.1.100:9443     # HTTPS (필수)
TCP 9080 → 192.168.1.100:9080     # HTTP→HTTPS 리다이렉트 (선택)
```

호스트에는 방화벽이 없고(INPUT policy ACCEPT), hostPort DNAT 규칙에 소스 제한도 없다.
이 서버 안에서는 hairpin NAT가 동작하지 않아 공인 IP로는 자체 검증이 불가능하다.

## 배포

```bash
kubectl apply -f 00-namespace.yaml

# 자격증명은 매니페스트에 없다 — 난수로 생성해 Secret으로만 존재한다.
kubectl -n hpc-portal create secret generic mysql-credentials \
  --from-literal=root-password="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)" \
  --from-literal=username=portal \
  --from-literal=password="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
kubectl -n hpc-portal create secret generic redis-credentials \
  --from-literal=password="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"

kubectl apply -f 10-mysql.yaml -f 20-redis.yaml
kubectl -n hpc-portal wait --for=condition=ready pod -l app=mysql --timeout=300s

# 백엔드 환경변수(자격증명 포함) — 값은 위에서 만든 Secret에서 가져온다
MP=$(kubectl -n hpc-portal get secret mysql-credentials -o jsonpath='{.data.password}' | base64 -d)
RP=$(kubectl -n hpc-portal get secret redis-credentials -o jsonpath='{.data.password}' | base64 -d)
kubectl -n hpc-portal create secret generic portal-backend-env \
  --from-literal=PORTAL_DATABASE_URL="mysql+pymysql://portal:${MP}@mysql.hpc-portal.svc.cluster.local:3306/portal?charset=utf8mb4" \
  --from-literal=PORTAL_REDIS_URL="redis://:${RP}@redis.hpc-portal.svc.cluster.local:6379/0" \
  --from-literal=PORTAL_JWT_SECRET="$(openssl rand -base64 48)" \
  --from-literal=PORTAL_SETUP_TOKEN="$(openssl rand -hex 16)" \
  --from-literal=PORTAL_SECRET_AD_BIND="<AD bind 암호>" \
  --from-literal=PORTAL_AD_TLS_VERIFY="false"

# TLS Secret (certbot 인증서)
sudo cat /etc/letsencrypt/live/www.dt-hpc.net/fullchain.pem > /tmp/fc.pem
sudo cat /etc/letsencrypt/live/www.dt-hpc.net/privkey.pem  > /tmp/pk.pem
kubectl -n hpc-portal create secret tls dt-hpc-tls --cert=/tmp/fc.pem --key=/tmp/pk.pem
shred -u /tmp/fc.pem /tmp/pk.pem

kubectl apply -f 30-backend.yaml -f 40-ingress.yaml -f 50-traefik-ports.yaml -f 60-frontend.yaml
```

## 접속 정보 확인

```bash
kubectl -n hpc-portal get secret mysql-credentials -o jsonpath='{.data.password}' | base64 -d
kubectl -n hpc-portal get secret redis-credentials -o jsonpath='{.data.password}' | base64 -d
```

호스트에서: `127.0.0.1:30306`(MySQL) · `127.0.0.1:30379`(Redis).

## 스키마 + 데이터

```bash
cd ../../backend
set -a && . ./.env.dev && set +a     # 자격증명 포함 — .gitignore 처리됨
.venv/bin/alembic upgrade head       # 21개 테이블(+alembic_version) + RBAC seed(운영에도 필요)
.venv/bin/python scripts/seed_dev.py # 개발용 예시 데이터 (멱등, --reset 지원)
```

`alembic`의 `0002_rbac_seed`는 **운영에도 필요한 초기 데이터**(role 2·permission 1·매핑 1)이고,
`seed_dev.py`는 **개발·데모용**이다 — 운영 DB에 실행하지 않는다.

## 운영 전 반드시 처리할 것

- **정기 백업 미구현** — §5.3이 요구하는 `CronJob → S3` 백업이 없다. 현재 PVC 손상 시 복구 수단이 없다.
- **NodePort 제거** — 개발 편의용이라 클러스터 밖에 DB/Redis 포트가 열려 있다.
- **방화벽/포트포워딩** — 외부(`123.41.34.26`)에서 9080/9443이 이 호스트로 들어오도록 라우터·방화벽 설정이 필요하다. 이 서버 안에서는 hairpin NAT가 동작하지 않아 검증하지 못했다.
- **로컬 스토리지** — local-path는 단일 노드 전용이다. §5.3의 "네트워크 스토리지" 요건을 만족하지 않는다.
- **Secret 저장소** — 현재 백엔드는 `EnvSecretStore`(환경변수)를 쓴다. §9 미확정 항목으로, 멀티 replica에서는 런타임 등록 Secret이 공유되지 않는다.

---

## Helm 차트

`deploy/helm/hpc-portal/`에 같은 구성을 차트로도 두었다. 이 디렉터리의 매니페스트는
**현재 배포의 정본이자 차트의 원본**이다 — 둘 중 하나를 고치면 다른 쪽도 맞춰야 한다.

차트가 더하는 것은 하나다: 위에서 `kubectl create secret`으로 치던 절차를 흡수하고,
**업그레이드 때 기존 값을 지킨다**(비밀번호와, 운영 중 손으로 넣은 `PORTAL_SECRET_CLUSTER_*`).

설치·인수 절차는 [helm/hpc-portal/README.md](../helm/hpc-portal/README.md) 참조.
