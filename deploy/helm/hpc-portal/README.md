# hpc-portal Helm 차트

`deploy/k8s/`의 매니페스트를 그대로 옮긴 차트다. **동작을 바꾸지 않았고**, 손으로 치던
Secret 생성 절차만 차트가 흡수했다.

## 설치

```bash
helm install portal ./deploy/helm/hpc-portal \
  -n hpc-portal --create-namespace \
  --set-file backend.sshKnownHosts=known_hosts \
  --set ingress.host=www.dt-hpc.net \
  --set ingress.tlsSecretName=dt-hpc-tls \
  --set backend.appIconHostPath=/home/.portal/app-icons
```

**새 클러스터라면 이것만 먼저 하면 된다.** 저장소는 기본으로 클러스터 기본
StorageClass를 쓰므로(k3s는 local-path) 별도 준비가 필요 없다. 아이콘 디렉터리는
노드에 미리 만들어 둔다 — 없으면 목록이 비고 업로드가 422로 끊긴다.

```bash
sudo mkdir -p /home/.portal/app-icons && sudo chown 10001:10001 /home/.portal/app-icons
```

이미지는 k3s containerd에 미리 넣어 둔다(`imagePullPolicy: Never`가 기본이다):

```bash
sudo docker save hpc-portal-backend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
sudo docker save hpc-portal-frontend:0.1.0 | sudo /usr/local/bin/k3s ctr images import -
```

TLS Secret은 **차트가 만들지 않는다** — 개인키가 values에 남으면 안 된다. certbot 인증서를
Secret으로 넣고 이름만 알려 준다(`certbot-deploy-hook.sh`가 갱신을 자동화한다).

처음 한 번은 클러스터 전역 객체도 필요하다:

```bash
--set storageClass.create=true    # PVC를 지워도 데이터가 남는다(reclaimPolicy: Retain)
--set mysql.storage.className=local-path-retain   # 위와 **함께** 쓴다. 한쪽만 켜면 렌더가 멈춘다
--set traefik.configure=true      # 내장 Traefik의 hostPort를 9080/9443으로
```

## 자격증명을 다루는 방식

**한 번 만든 값은 지킨다.** 비밀번호를 업그레이드마다 새로 만들면 MySQL 볼륨에 남은 옛
비밀번호와 어긋나 파드가 뜨지 못한다. 차트는 설치 때 난수를 만들고, 그 뒤로는 기존
Secret에서 읽어 그대로 쓴다. values에 값을 적으면 그쪽이 이긴다.

**차트가 모르는 키도 지킨다.** `PORTAL_SECRET_CLUSTER_*`(클러스터 JWT·SSH 키)는 운영 중에
손으로 넣는다 — `EnvSecretStore.put()`이 프로세스 안에만 두고 영속화는 배포 수단의 몫이기
때문이다(`backend/app/core/secrets.py`). 차트는 기존 Secret의 키를 **통째로 물려받고** 자기가
아는 키만 덮어쓴다. 이 병합이 없으면 `helm upgrade` 한 번에 모든 클러스터 연결이 끊긴다.

설정 토큰 확인:

```bash
kubectl -n hpc-portal get secret portal-backend-env \
  -o jsonpath='{.data.PORTAL_SETUP_TOKEN}' | base64 -d; echo
```

## 이미 떠 있는 배포를 차트로 옮기려면

`deploy/k8s/`로 올린 리소스에는 Helm 소유권 표시가 없어서 그대로는 못 가져온다.
**리소스 이름이 같아야** 교체가 아니라 인수가 된다 — `fullnameOverride=portal`이 그 역할이다.

```bash
# 1. 무엇이 바뀌는지 먼저 본다. 서버 dry-run이라야 기존 Secret을 읽는다.
helm install portal ./deploy/helm/hpc-portal -n hpc-portal --dry-run=server --take-ownership \
  --set fullnameOverride=portal \
  --set mysql.existingSecret=mysql-credentials \
  --set redis.existingSecret=redis-credentials \
  --set ingress.tlsSecretName=dt-hpc-tls

# 2. 렌더 결과에 PORTAL_SECRET_CLUSTER_* 키가 그대로 있는지 확인한 뒤 실행한다.
```

> **먼저 DB를 백업한다.** 인수 과정에서 MySQL StatefulSet이 다시 만들어질 수 있고,
> `deploy/k8s/`의 StatefulSet과 차트의 selector 라벨이 다르다(`app: mysql` →
> `app.kubernetes.io/*`). StatefulSet은 selector를 바꿀 수 없어 **삭제 후 재생성**이
> 필요하다. PVC는 `Retain`이라 데이터 자체는 남지만, 순서를 확인하지 않고 하지 말 것.

새 환경에 처음 배포하는 것이라면 위 인수 절차가 필요 없다.

## values 요약

| 키 | 뜻 |
|---|---|
| `image.*.repository` / `tag` / `pullPolicy` | 이미지. 레지스트리를 쓰면 `pullPolicy: IfNotPresent` |
| `mysql.*` / `redis.*` | 내장 DB·캐시. `enabled: false`로 외부 것을 쓸 수 있다 |
| `backend.env` | Secret에 그대로 실리는 값. **자격증명은 여기 두지 말 것**(values에 평문으로 남는다) |
| `backend.existingSecret` | env Secret을 직접 관리하면 이름만. 차트는 만들지 않는다 |
| `backend.sshKnownHosts` | 로그인 노드 호스트키. 없으면 파일 관리자·터미널·세션이 막힌다 |
| `ingress.host` / `tlsSecretName` | 도메인과 인증서 Secret |
| `traefik.configure` | 내장 Traefik hostPort 변경(**클러스터 전역**) |
| `storageClass.create` | reclaimPolicy Retain StorageClass(**클러스터 전역**). `mysql.storage.className`과 함께 켠다 |
| `backend.appIconHostPath` | 앱 아이콘이 놓이는 노드 디렉터리. 비우면 마운트하지 않는다(업로드 422) |
| `backend.env.PORTAL_COOKIE_SECURE` | **TLS 없이 열면 `"false"`로.** 기본 true라 http에서 로그인이 조용히 실패한다 |
| `dev.nodePorts.enabled` | DB·Redis를 클러스터 밖에 연다. **운영에서는 끄기** |
