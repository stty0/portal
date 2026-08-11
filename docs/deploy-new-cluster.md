# 새 k3s 서버에 Helm으로 설치하기

- 작성일: 2026-08-10
- 대상: **검증계처럼 아무것도 없는 k3s에 차트만 가져가 처음 설치**하는 경우
- 관련 문서: [deploy/k8s/README.md](../deploy/k8s/README.md)(개발계 매니페스트 구성),
  [deploy/helm/hpc-portal/README.md](../deploy/helm/hpc-portal/README.md)(values 레퍼런스)

## 배포 경로가 둘이다

| | 개발계(dev01) | 새 서버 |
|---|---|---|
| 수단 | `kubectl apply -f deploy/k8s/` | **Helm 차트** |
| 이유 | 먼저 만들어졌고 계속 그렇게 돌고 있다 | 손으로 만들던 Secret 절차를 차트가 흡수한다 |

**둘은 같은 것을 배포하지만 자동으로 동기화되지 않는다.** 매니페스트를 고치면 차트도 봐야
한다 — 실제로 차트가 생성 시점부터 아이콘 마운트를 빠뜨리고 있었고 2026-08-10에야 발견됐다.

---

## 1. 사전 준비 — 수동으로 해야 하는 것

차트가 **하지 않는** 일들이다.

### 1.1 이미지 반입 (필수)

`image.*.pullPolicy: Never`라 레지스트리에서 받지 않는다. 노드의 containerd에 직접 넣는다.

```bash
# 빌드한 기계에서 (dev01에서 만든 꾸러미는 dist-images/ 아래에 있다)
sudo docker save hpc-portal-backend:0.2.0  | gzip > backend-0.2.0.tgz
sudo docker save hpc-portal-frontend:0.2.0 | gzip > frontend-0.2.0.tgz

# 새 서버에서
gunzip -c backend-0.2.0.tgz  | sudo /usr/local/bin/k3s ctr images import -
gunzip -c frontend-0.2.0.tgz | sudo /usr/local/bin/k3s ctr images import -
sudo /usr/local/bin/k3s ctr images ls | grep hpc-portal
```

⚠ **태그가 맞아야 한다.** 차트는 `values.image.*.tag`가 비면 `Chart.appVersion`(현재 `0.2.0`)을
쓴다. `:latest`로 반입하고 배포하면 **롤아웃은 성공하는데 옛 코드가 뜬다** — 개발계에서
실제로 겪은 사고다.

**태그는 불변으로 다룬다.** 같은 `0.2.0`에 내용이 다른 이미지를 두 번 넣지 않는다 —
어느 서버가 무엇을 돌리는지 알 수 없게 되고, `imagePullPolicy: Never`라 파드는 노드에
이미 있는 것을 그대로 쓴다. 코드가 바뀌면 `Chart.yaml`의 `appVersion`을 올리고 그 태그로
빌드한다.

### 1.2 앱 아이콘 디렉터리 (선택 — 아이콘을 쓸 때만)

```bash
sudo mkdir -p /home/.portal/app-icons
sudo chown 10001:10001 /home/.portal/app-icons   # 컨테이너 UID
```

지정하지 않으면 마운트하지 않는다. 아이콘 목록이 비고 업로드는 **422 "아이콘 디렉터리가
없습니다"**로 끊긴다. `emptyDir`로 폴백하지 않는 이유는 **재시작마다 아이콘이 조용히
사라지는 것이 422보다 나쁘기 때문**이다.

### 1.3 로그인 노드 호스트키 (선택 — 파일 관리자·터미널·세션을 쓸 때)

```bash
ssh-keyscan <로그인노드> > known_hosts
```

없으면 파드는 뜨지만 SSH 기능이 전부 막힌다(자동 수락은 중간자 공격을 그대로 통과시키므로
하지 않는다). Job 제출·모니터링은 REST라 동작한다.

### 1.4 TLS 인증서 (선택)

**없어도 접속은 된다** — Traefik이 자기 기본 인증서로 응답한다(실측: `CN=TRAEFIK DEFAULT
CERT`, 자체서명). 브라우저 경고만 나고, https이므로 **쿠키·로그인은 정상 동작한다.**

경고를 없애려면 Secret을 만든다. 타입 `kubernetes.io/tls`, 키 `tls.crt`·`tls.key`:

```bash
kubectl -n hpc-portal create secret tls verify-tls \
  --cert=fullchain.pem --key=privkey.pem
```

차트가 만들지 않는 이유는 **개인키가 `values.yaml`에 평문으로 남기 때문**이다.

자체서명이 필요하면:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout privkey.pem -out fullchain.pem \
  -subj "/CN=<도메인>" -addext "subjectAltName=DNS:<도메인>"
```

---

## 2. 설치

```bash
helm install portal ./deploy/helm/hpc-portal \
  -n hpc-portal --create-namespace \
  --set ingress.host=<도메인> \
  --set ingress.tlsSecretName=verify-tls \
  --set backend.appIconHostPath=/home/.portal/app-icons \
  --set-file backend.sshKnownHosts=known_hosts
```

**저장소 관련 설정은 필요 없다** — 기본이 클러스터 기본 StorageClass다(k3s는 `local-path`).

차트 꾸러미(`hpc-portal-0.2.0.tgz`)를 받아 왔다면 경로 대신 그것을 준다:

```bash
helm install portal ./hpc-portal-0.2.0.tgz -n hpc-portal --create-namespace ...
```

### 포트를 바꿔야 한다면

노드의 80/443을 다른 서비스가 쓰고 있으면:

```bash
--set traefik.configure=true --set traefik.webHostPort=9080 --set traefik.websecureHostPort=9443
```

이 값은 **http→https 리다이렉트가 가리키는 포트도 함께 정한다.** 켜지 않으면 리다이렉트에
포트를 붙이지 않아 표준 443으로 간다 — 검증계처럼 Traefik이 기본 포트에 있는 서버에서
맞는 동작이다(0.2.0에서 고쳤다. 그 전에는 항상 `:9443`을 붙여, 표준 포트를 쓰는 서버에서
**http로 들어온 사용자가 아무도 듣지 않는 포트로 튕겼다**).

⚠ **클러스터 전역 설정(kube-system)이다.** 그리고 `service.spec.type`을 ClusterIP로 고정한다 —
기본 LoadBalancer면 k3s servicelb가 hostPort 80/443을 잡는 파드를 띄워 **그 노드의 기존
80/443 서비스를 DNAT으로 가로챈다**(개발계에서 실제로 겪었다).

### PVC를 지워도 데이터를 남기려면

```bash
--set storageClass.create=true --set mysql.storage.className=local-path-retain
```

**둘을 함께** 켠다. 한쪽만 켜면 렌더가 멈춘다(§4.1).

---

## 3. 부트스트랩 — 무엇이 자동인가

| 항목 | 누가 | 비고 |
|---|---|---|
| DB·계정 생성 | MySQL 컨테이너 | `MYSQL_DATABASE`·`MYSQL_USER` 자동 |
| 스키마 | **init 컨테이너** | `alembic upgrade head`, 앱보다 먼저 |
| RBAC 시드 | 마이그레이션 `0002` | role 2행(USER·ADMIN) · permission 1행(`admin:access`) · 매핑 1행 |
| DB·Redis 비밀번호 | 차트 | 난수 생성, **업그레이드 때 기존 값 유지** |
| JWT 시크릿·setup 토큰 | 차트 | 〃 |
| 앱 카탈로그 | — | **불필요.** 등록이 없으면 코드 카탈로그가 정본이라 그대로 동작한다 |

즉 **DB에 따로 넣을 데이터가 없다.** 스키마와 시드는 파드가 뜨는 과정에서 끝난다.

### 최초 관리자 만들기

포털은 계정을 직접 만들지 않는다 — AD에서 온다(C-02). 순서는:

오브젝트 이름은 **릴리스 이름이 아니라 차트 이름**(`hpc-portal`)에서 나온다
(`fullnameOverride`를 주면 그 값). 즉 `helm install portal ...`로 깔아도 Secret은
`hpc-portal-backend-env`다 — 헷갈리기 쉬우므로 라벨로 찾는 편이 안전하다.

```bash
# 1) setup 토큰을 꺼낸다 (NOTES에도 같은 명령이 나온다)
kubectl -n hpc-portal get secret hpc-portal-backend-env \
  -o jsonpath='{.data.PORTAL_SETUP_TOKEN}' | base64 -d; echo
```

2) 브라우저로 포털에 접속하면 최초 설정 화면이 뜬다.
3) 토큰 + AD 연결 정보(LDAPS URL·Base DN·바인드 계정·허용 그룹)를 넣는다.
4) 검증에 성공한 AD 사용자 **1명이 ADMIN으로 seed** 된다.

이후 사용자는 AD 동기화로 자동 프로비저닝된다.

### 클러스터 자격증명

Slurm JWT·SSH 키는 **설치 시점에 넣지 않는다.** 포털 화면(클러스터 등록)에서 넣으면
`portal-backend-env` Secret에 `PORTAL_SECRET_CLUSTER_<id>_*` 키로 들어간다.

⚠ `values.yaml`의 `backend.env`에는 **넣지 말 것** — values 파일에 평문으로 남는다.
차트는 업그레이드 때 **기존 Secret의 모르는 키를 통째로 물려받는다**(그 병합이 없으면
`helm upgrade` 한 번에 모든 클러스터 연결이 끊긴다).

`portal-backend-env`(개발계 매니페스트)와 `hpc-portal-backend-env`(차트)는 **이름만 다른
같은 역할**이다. 개발계를 차트로 옮길 때는 `--set fullnameOverride=portal`로 이름을 맞춘다.

---

## 4. 함정 — 겪었거나 코드로 확인한 것

### 4.1 StorageClass 이름과 생성 여부가 어긋나면 아무것도 안 뜬다

없는 StorageClass를 가리키면 PVC가 `Pending`에서 멈추고 → MySQL이 안 뜨고 → init
컨테이너가 계속 실패한다. **파드 목록만 보면 원인이 안 보인다.**

그래서 차트가 렌더 단계에서 끊는다:

```
Error: mysql.storage.className=local-path-retain 인데 storageClass.create=false 입니다.
```

### 4.2 평문 http로 열면 로그인만 실패한다

`PORTAL_COOKIE_SECURE` 기본이 `true`라 브라우저가 http에서 쿠키를 버린다. **화면은 뜨는데
로그인만 안 되고 원인이 안 보인다.** Ingress를 끄고 http로 직접 노출할 때만 해당한다:

```bash
--set backend.env.PORTAL_COOKIE_SECURE=false
```

### 4.3 서버 안에서 curl이 되는데 밖에서 안 될 수 있다

CNI portmap은 hostPort DNAT을 **PREROUTING(외부 트래픽)과 OUTPUT(자기 자신) 양쪽**에
건다. 서버 안 curl은 OUTPUT만 지나므로 **외부 연결성을 증명하지 못한다.** 개발계에서
"서버는 정상"이라고 잘못 진단한 적이 있고, 실제 원인은 Traefik이었다.

→ 외부에서 안 되면 **밖에서 확인해야 한다.**

### 4.4 이미지 태그 불일치

§1.1 참조. 롤아웃 성공 ≠ 새 코드. 확인은 **파드 안에서** 한다:

```bash
BE=$(kubectl -n hpc-portal get deploy -l app.kubernetes.io/component=backend -o name)
kubectl -n hpc-portal get $BE -o jsonpath='{..image}{"\n"}'
kubectl -n hpc-portal exec $BE -- python -c "import app; print(app.__file__)"
```

---

## 5. 설치 후 확인

```bash
kubectl -n hpc-portal get pod,svc,pvc

# 이름을 외우지 않는다 — 라벨로 찾는다(릴리스 이름과 오브젝트 이름이 다르다)
BE=$(kubectl -n hpc-portal get deploy -l app.kubernetes.io/component=backend -o name)

# 스키마가 끝까지 올라갔나 (head = 최신 리비전)
kubectl -n hpc-portal exec $BE -- alembic current

# RBAC 시드가 들어갔나
kubectl -n hpc-portal exec $BE -- python -c "
from app.core.config import get_settings
from app.db.session import init_engine, session_scope
from sqlalchemy import text
s=get_settings(); init_engine(s.database_url); db=next(session_scope())
print([r[0] for r in db.execute(text('SELECT code FROM role'))])"

# 응답 (도메인은 Host 헤더로)
curl -sk -o /dev/null -w '%{http_code}\n' -H 'Host: <도메인>' https://127.0.0.1:<포트>/
curl -sk -o /dev/null -w '%{http_code}\n' -H 'Host: <도메인>' https://127.0.0.1:<포트>/api/v1/clusters
```

기대값: 프런트 `200`, `/api/v1/clusters` **`401`**(미인증이 정상). `alembic current`는 `(head)`.

---

## 6. 운영

### 업그레이드

```bash
# 새 이미지 반입 후
helm upgrade portal ./deploy/helm/hpc-portal -n hpc-portal --reuse-values
```

비밀번호는 `lookup`으로 기존 값을 읽어 유지한다 — **새로 만들면 MySQL 볼륨의 옛 비밀번호와
어긋나 파드가 뜨지 못한다.**

### Let's Encrypt 갱신

certbot이 갱신해도 **Secret은 자동으로 안 바뀐다.** Traefik은 Secret 사본을 쓰므로
**만료된 인증서를 계속 제공한다**(조용히 깨진다).
[certbot-deploy-hook.sh](../deploy/k8s/certbot-deploy-hook.sh)를 쓰되 `LINEAGE_NAME`·
`NAMESPACE`·`SECRET` 세 변수만 바꾼다.

### 이미지 빌드 뒤

```bash
sudo docker builder prune -af
```

빌드 캐시와 apptainer 캐시가 쌓여 **노드가 DiskPressure에 걸리고 포털 파드가 evict된
사고**가 있었다.

---

## 7. 참고 실측값 (2026-08-10, 개발계)

| 항목 | 값 |
|---|---|
| 컨테이너 이미지 → SIF 변환 | 2.62GB → **9분 3초** → SIF 1.3GB, 스크래치 피크 2.4GB |
| 로그인 노드 SSH 왕복 | 연결 115~154ms + SFTP 채널 120~260ms + 조회 23ms |
| 앱 이미지 목록 캐시 | 60초(Redis), 실패는 캐시하지 않는다 |

앱 이미지(SIF)는 **포털이 만들지 않는다** — 관리자가 밖에서 받아 변환한 뒤 클러스터의
`{home_base}/.portal/images`에 올려놓는다. 자세한 내용은 [progress.md](progress.md)와
[gpu-simulation.md](gpu-simulation.md) §4.
