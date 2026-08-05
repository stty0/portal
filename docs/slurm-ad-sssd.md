# Slurm 클러스터 2세트 — Ubuntu 24.04 + SSSD로 AD 계정 연동

개발용 Slurm 클러스터 2세트(`seoul-hpc`, `pangyo-gpu`)의 전 노드가 **같은 AD 계정·같은 UID**로
동작하도록 SSSD를 구성하는 절차. 포털(`portal`)이 이미 같은 AD를 바라보고 있으므로,
**포털이 저장한 사용자명과 노드의 `getpwnam` 결과가 정확히 일치해야 한다**는 제약이 설계의 축이다.

---

## 0. 대상 환경

실제 AD에 질의해 확인한 값이다.

| 항목 | 값 |
|---|---|
| 도메인 (DNS) | `dt-hpc.net` |
| 도메인 (NetBIOS) | `DT-HPC` |
| 도메인 컨트롤러 | `WIN-7CUUJHSK57G.dt-hpc.net` / `192.168.1.10` |
| 기능 수준 | Windows Server 2025 |
| 사용자 OU | `OU=people,DC=dt-hpc,DC=net` |
| 식별 속성 | `sAMAccountName` (포털 설정과 동일) |
| POSIX 속성(`uidNumber`) 보유 계정 | **0건** |
| 노드 OS | Ubuntu 24.04 LTS (SSSD 2.9.x) |

노드 구성 예시 — 실제 호스트명에 맞춰 바꿔 쓴다.

| 클러스터 | 역할 | 호스트 |
|---|---|---|
| `seoul-hpc` | 로그인 / 컨트롤러 / 계산 | `seoul-login01` / `seoul-ctld01` / `seoul-cn[01-04]` |
| `pangyo-gpu` | 로그인 / 컨트롤러 / 계산 | `pangyo-login01` / `pangyo-ctld01` / `pangyo-gpu[01-02]` |

---

## 1. 설계 결정 — UID를 어떻게 정할 것인가

Slurm은 사용자를 **UID 숫자**로 다룬다. 노드마다 같은 이름이 다른 UID로 해석되면
작업이 남의 파일을 건드리거나 `Invalid user id` 로 죽는다. 방법은 둘이다.

| 방식 | 조건 | 판단 |
|---|---|---|
| **AD POSIX 속성** (`uidNumber`/`gidNumber`) | AD 계정마다 값을 직접 채워야 함 | 현재 **0건** — 전 계정에 수동 부여 필요 |
| **SSSD ID 매핑** (SID → UID 알고리즘 계산) | AD 변경 불필요 | **채택** |

ID 매핑은 사용자 SID를 정해진 알고리즘으로 UID에 대응시킨다. 알고리즘이 결정적이므로
**같은 파라미터를 쓰는 모든 노드가 같은 UID를 얻는다** — 클러스터가 2개여도, 나중에 노드를
추가해도 동일하다. 대신 다음을 반드시 지켜야 한다.

> **파라미터를 `sssd.conf`에 명시적으로 고정한다.**
> `ldap_idmap_range_min` / `range_max` / `range_size` 는 기본값에 의존하지 말고 직접 적는다.
> 한 노드만 값이 다르면 그 노드에서만 UID가 어긋나고, 증상은 "가끔 작업이 실패한다"로 나타나
> 원인 추적이 매우 어렵다.

향후 POSIX 속성 방식으로 전환하려면 **전체 노드 동시 전환 + 기존 파일 소유권 일괄 변경**이
필요하다. 시작 시점에 정하고 바꾸지 않는 편이 낫다.

---

## 2. 사전 준비 (전 노드 공통)

### 2.1 DNS를 도메인 컨트롤러로

`realm join`은 `_ldap._tcp.dc._msdcs.dt-hpc.net` SRV 레코드로 DC를 찾는다. 일반 DNS로는 조회되지 않는다.

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    ens160:
      nameservers:
        addresses: [192.168.1.10]
        search: [dt-hpc.net]
```

```bash
sudo netplan apply
dig +short -t SRV _ldap._tcp.dc._msdcs.dt-hpc.net   # 결과가 나와야 진행 가능
```

### 2.2 시간 동기화

Kerberos는 기본 5분 이상 시계가 어긋나면 인증을 거부한다. **AD 연동 실패의 가장 흔한 원인이다.**

```bash
sudo apt install -y chrony
echo "server 192.168.1.10 iburst" | sudo tee /etc/chrony/conf.d/ad.conf
sudo systemctl restart chrony
chronyc sources -v        # ^* 로 동기화 확인
```

### 2.3 호스트명은 FQDN으로

```bash
sudo hostnamectl set-hostname seoul-login01.dt-hpc.net
```

`/etc/hosts`에 `127.0.1.1 seoul-login01.dt-hpc.net seoul-login01` 이 있어야 한다.

### 2.4 패키지

```bash
sudo apt update
sudo apt install -y sssd-ad sssd-tools realmd adcli krb5-user \
                    samba-common-bin oddjob oddjob-mkhomedir packagekit libnss-sss libpam-sss
```

`krb5-user` 설치 중 realm을 물으면 대문자로 `DT-HPC.NET` 을 입력한다.
놓쳤다면 나중에 다시 띄울 수 있다.

```bash
sudo dpkg-reconfigure krb5-config
```

또는 `/etc/krb5.conf`를 직접 쓴다.

```ini
[libdefaults]
    default_realm = DT-HPC.NET
    dns_lookup_realm = false
    dns_lookup_kdc = true
    ticket_lifetime = 24h
    forwardable = true
    # 역방향 조회 영역이 없으므로 끈다 (9.1 참고)
    rdns = false

[realms]
    DT-HPC.NET = {
        kdc = WIN-7CUUJHSK57G.dt-hpc.net
        admin_server = WIN-7CUUJHSK57G.dt-hpc.net
    }

[domain_realm]
    .dt-hpc.net = DT-HPC.NET
    dt-hpc.net = DT-HPC.NET
```

확인:

```bash
kinit jungryul0515.park      # realm 생략 가능하면 default_realm이 먹은 것
klist
kdestroy
```

---

## 3. 도메인 조인

### 3.1 AD 쪽 사전 작업

현재 이 도메인에 존재하는 OU는 `OU=Domain Controllers` 와 `OU=people` 뿐이다.
아래 중 필요한 것을 **조인 전에** AD에서 만들어 둔다.

| 대상 | 필요 시점 | 없으면 |
|---|---|---|
| `OU=servers` + 하위 `OU=seoul-hpc` / `OU=pangyo-gpu` | `--computer-ou` 를 쓸 때 | 조인 실패 → 플래그를 빼면 `CN=Computers`로 들어감 (동작에는 지장 없음) |
| 조인 권한 계정 | 항상 | `sysadmin`은 `Administrators` 소속이라 그대로 사용 가능 |
| 보안 그룹 `hpc-users` | 로그인 대상을 제한할 때 | `sssd.conf`의 `simple_allow_groups` 줄을 지운다 → `OU=people` 전원 허용 |

### 3.2 조인 실행

클러스터별로 컴퓨터 계정 OU를 분리하면 나중에 GPO·정리 작업이 쉬워진다.

```bash
# 도메인이 보이는지 먼저 확인
realm discover dt-hpc.net

# seoul-hpc 노드
sudo realm join --user=sysadmin \
     --computer-ou="OU=seoul-hpc,OU=servers,DC=dt-hpc,DC=net" dt-hpc.net

# pangyo-gpu 노드
sudo realm join --user=sysadmin \
     --computer-ou="OU=pangyo-gpu,OU=servers,DC=dt-hpc,DC=net" dt-hpc.net
```

OU를 따로 만들지 않을 거면 `--computer-ou` 를 빼면 `CN=Computers` 에 들어간다.

조인 확인:

```bash
realm list
sudo klist -k /etc/krb5.keytab | head    # 호스트 keytab 발급 확인
```

---

## 4. `/etc/sssd/sssd.conf` — 전 노드 동일 파일

`realm join`이 만든 기본 파일은 **그대로 쓰면 안 된다.** 사용자명이 `user@dt-hpc.net` 형태가 되고
홈이 `/home/user@dt-hpc.net`이 되는데, 포털이 저장한 사용자명(`sAMAccountName`)과 달라져
포털에서 제출한 작업이 노드에서 계정을 못 찾는다.

> **주의 — `sssd.conf`는 줄 끝 주석(inline comment)을 지원하지 않는다.**
> `key = value   # 설명` 이라고 쓰면 `# 설명`까지 값으로 읽혀 파싱에 실패하고 **SSSD가 기동하지 않는다.**
> 주석은 반드시 `#`으로 시작하는 **독립된 줄**에만 쓴다. 아래 예시는 그 규칙을 지키고 있다.

```ini
[sssd]
domains = dt-hpc.net
config_file_version = 2
services = nss, pam

[nss]
# AD 계정은 loginShell 속성이 없다 — 없으면 로그인 직후 세션이 끊긴다
default_shell = /bin/bash
# 전 노드가 같은 홈 경로를 봐야 한다
override_homedir = /home/%u
# 시스템 계정은 SSSD에 묻지 않는다 (부팅·munge 조회 지연 방지)
filter_users = root,munge,slurm,daemon,bin,sys
filter_groups = root,munge,slurm

[pam]
offline_credentials_expiration = 7

[domain/dt-hpc.net]
id_provider = ad
auth_provider = ad
chpass_provider = ad
access_provider = simple

ad_domain = dt-hpc.net
krb5_realm = DT-HPC.NET
realmd_tags = manual

# ad_server 는 일부러 지정하지 않는다.
# SRV 레코드(_ldap._tcp.dc._msdcs.dt-hpc.net)로 DC를 자동 탐색하게 두면
# DC 호스트명이 바뀌거나 DC가 늘어나도 설정을 손댈 필요가 없다.
# 지정할 경우 이름 하나만 틀려도 그 노드만 조용히 Offline 이 된다
# (kinit 은 SRV 로 성공하므로 원인이 잘 드러나지 않는다).

# --- 사용자명 형식: 포털과 반드시 일치시킨다 -------------------------
# False 라야 jungryul0515.park 로 해석된다 (True면 ...@dt-hpc.net)
use_fully_qualified_names = False
case_sensitive = False

# --- 검색 범위 -------------------------------------------------------
# 사용자는 포털의 "사용자 DN"과 같은 지점으로 좁힌다
ldap_user_search_base = OU=people,DC=dt-hpc,DC=net
# 그룹은 도메인 전체를 봐야 한다. 기본 그룹 Domain Users가
# CN=Users 에 있어서, OU=people 로 좁히면 그룹 이름 해석이 실패한다
ldap_group_search_base = DC=dt-hpc,DC=net

# --- UID/GID 산출: 전 노드 동일해야 함 (값 고정) ---------------------
ldap_id_mapping = True
ldap_idmap_range_min = 200000
ldap_idmap_range_max = 2000200000
ldap_idmap_range_size = 200000
ldap_idmap_default_domain_sid = S-1-5-21-750617150-2013882115-1463020004

# --- 로그인 허용 범위 ------------------------------------------------
# hpc-users 그룹을 만들지 않았다면 아래 simple_allow_groups 줄을 지운다
simple_allow_groups = hpc-users@dt-hpc.net
# 기본값 enforcing이면 GPO 때문에 로그인이 거부된다 (5장 참고)
ad_gpo_access_control = permissive

# --- 캐시/성능 -------------------------------------------------------
# DC 장애 시에도 로그인 유지
cache_credentials = True
# getent passwd 전체 나열 비활성 (권장)
enumerate = False

# --- 역방향 DNS 영역이 없으면 PTR 등록이 실패한다 (9.1 참고) ---------
dyndns_update_ptr = False
```

```bash
sudo chmod 600 /etc/sssd/sssd.conf     # 권한이 넓으면 SSSD가 기동을 거부한다
sudo systemctl restart sssd
```

### 4.1 `ldap_idmap_default_domain_sid`

위 값은 실제 AD에서 확인한 이 도메인의 SID다 (사용자 SID
`S-1-5-21-750617150-2013882115-1463020004-1106` 에서 마지막 RID를 뗀 값).
명시해 두면 도메인이 늘어나도 UID 대역이 흔들리지 않는다. 직접 재확인하려면:

```bash
sudo net getdomainsid
```

### 4.2 전 노드 배포

설정은 한 벌을 만들어 복사한다. 노드마다 손으로 편집하면 반드시 어긋난다.

```bash
for h in seoul-ctld01 seoul-cn0{1..4}; do
  scp /etc/sssd/sssd.conf root@$h:/etc/sssd/sssd.conf
  ssh root@$h 'chmod 600 /etc/sssd/sssd.conf && sss_cache -E && systemctl restart sssd'
done
```

---

## 5. 로그인 허용 범위

`access_provider = simple` + `simple_allow_groups` 로 특정 그룹만 허용한다.
**AD에 `hpc-users` 같은 보안 그룹을 만들고 사용자를 넣어야 동작한다** — OU는 쓸 수 없다
(그룹 멤버십은 `memberOf` 속성으로만 판정되고, 여기에 OU는 절대 들어가지 않는다).

그룹을 아직 안 만들었다면 `simple_allow_groups` 줄을 지운다. 그러면 §4의
`ldap_search_base`(= `OU=people`) 안의 계정 전원이 로그인 가능하다.

`ad_gpo_access_control = permissive` 를 넣은 이유: SSSD 기본값은 `enforcing`이라
AD의 "로컬 로그온 허용" GPO에 도메인 사용자가 없으면 **인증은 성공하는데 로그인이 거부된다**.
증상이 비밀번호 오류와 구분되지 않아 원인 찾기가 어렵다. GPO를 정식으로 구성하기 전까지는
`permissive`로 두고 접근 제어는 `simple_allow_groups`로 한다.

---

## 6. 홈 디렉터리

### 권장: 공유 스토리지(NFS)

Slurm 작업은 어느 계산 노드에서 실행될지 모른다. 홈이 노드마다 따로 있으면
**제출 디렉터리·출력 파일·입력 데이터가 계산 노드에 없어서** 작업이 실패한다.

> 사용자가 로그인 노드에만 접속해 자기 홈에서만 작업하더라도 공유는 필요하다.
> **사용자가 어디에 있느냐가 아니라 작업이 어디서 실행되느냐**가 기준이기 때문이다.
> `~/exp1`에서 `sbatch`하면 그 작업은 계산 노드에서 `~/exp1`을 열려고 한다.

정확히 말하면 **배치 스크립트 본문은 문제가 아니다.** `sbatch`가 스크립트를 읽어
slurmctld에 저장하고, slurmd가 계산 노드의 spool 디렉터리에 다시 써주기 때문에
스크립트 파일 자체는 공유 스토리지에 없어도 실행된다. 깨지는 것은 그 주변이다.

| 항목 | 기본 동작 | 홈이 노드 로컬이면 |
|---|---|---|
| 작업 디렉터리 | `sbatch`를 실행한 경로를 그대로 사용 | 계산 노드에 그 경로가 없어 `couldn't chdir to ... going to /tmp instead` 후 `/tmp`에서 실행 |
| 표준 출력 | 작업 디렉터리에 `slurm-<jobid>.out` 생성 | 경로가 없어 파일 생성 실패 → **작업이 그대로 종료** |
| 입력 데이터·바이너리 | 스크립트 안의 상대/홈 경로로 참조 | 파일 없음 → 스크립트가 실패 |
| 결과 파일 | 작업 디렉터리에 기록 | 실행된 노드의 로컬 디스크에 흩어짐. 사용자는 찾을 수 없다 |

더 나쁜 경우는 **경로가 노드마다 존재하지만 내용이 다른** 상황이다. 작업은 "성공"으로 끝나는데
읽은 파일이 다른 노드의 옛 파일이거나 결과가 조용히 사라진다 — 원인 추적이 매우 어렵다.

포털에서 제출할 때도 동일하다. 포털은 `work_dir`을 지정해 slurmrestd에 넘기므로,
그 경로가 전 계산 노드에서 같은 실체를 가리켜야 한다.

```bash
# 스토리지 노드
sudo apt install -y nfs-kernel-server
echo "/export/home 192.168.1.0/24(rw,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra

# 전 노드
sudo apt install -y nfs-common
echo "storage:/export/home /home nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab
sudo mount -a
```

두 클러스터가 홈을 공유할지는 정책 문제다. 공유하면 사용자가 클러스터를 옮겨도 파일이 따라오고,
분리하면 장애 영향 범위가 좁아진다. 포털의 클러스터 등록 항목
`group_path_tpl` / `scratch_path_tpl` 이 이 경로 정책과 일치해야 한다.

### 6.1 NFS를 이미 쓰고 있다면 — AD 연동에서 추가로 확인할 것

**NFS는 사용자를 이름이 아니라 UID 숫자로 판정한다.** 그래서 §7.2의 UID 일치 검증이
단순한 위생 점검이 아니라 **권한 문제**가 된다. 한 노드만 UID가 어긋나면 그 노드에서
사용자가 자기 파일에 접근하지 못하거나, 더 나쁘게는 **같은 UID로 매핑된 다른 사람의 파일을
자기 것처럼 읽고 쓴다.** SSSD 배포 후 반드시 대조한다.

```bash
# 어느 노드에서든 같은 사용자·같은 숫자로 보여야 한다
ls -ln /home/jungryul0515.park | head -3
ls -l  /home/jungryul0515.park | head -3
```

| 증상 | 원인 | 조치 |
|---|---|---|
| 소유자가 `nobody:nogroup` 으로 보임 | NFSv4 idmap 도메인 불일치 | 서버·전 클라이언트의 `/etc/idmapd.conf` 에 `Domain = dt-hpc.net` 동일 지정 후 `nfsidmap -c` |
| 노드마다 소유자 이름이 다름 | SSSD UID 불일치 | §4 idmap 값 고정 후 재배포 (§7.2) |
| 숫자 UID로만 보임 (`ls -l` 에 숫자) | 그 노드에서 SSSD 조회 실패 | `id <user>` 로 확인, `sss_cache -E` 후 재시작 |

### 홈 디렉터리 자동 생성 (mkhomedir) — NFS의 대안이 아니다

AD 계정에는 홈 디렉터리 실체가 없으므로 누군가는 만들어 줘야 한다. `pam_mkhomedir`가 그 역할이다.

```bash
sudo pam-auth-update --enable mkhomedir
sudo systemctl enable --now oddjobd
```

**둘은 해결하는 문제가 다르다. 보통은 함께 쓴다.**

| | NFS 공유 | pam_mkhomedir |
|---|---|---|
| 하는 일 | 모든 노드가 **같은 실체**를 보게 함 | 홈이 없으면 **만들어 줌** |
| 없으면 | 노드마다 다른 홈 → 작업 실패·결과 유실 | 첫 로그인 시 홈이 없어 `/` 로 떨어짐 |

권장 구성은 **`/home`을 NFS로 마운트하고, mkhomedir는 로그인 노드에만 켜는 것**이다.
첫 로그인 때 공유 스토리지 위에 홈이 생기고 전 계산 노드가 그것을 그대로 본다.

> **계산 노드에는 mkhomedir를 켜지 않는다.** 로컬 `/home` 위에 노드마다 빈 홈이 생겨
> §6 서두의 "경로는 있는데 내용이 다른" 최악의 상황이 된다.

> **NFS `root_squash` 주의.** `pam_mkhomedir`는 root 권한으로 디렉터리를 만드는데,
> 기본 export 옵션인 `root_squash`는 root를 `nobody`로 낮춰 생성이 실패한다.
> 로그인 노드에 한해 `no_root_squash`로 export하거나, 홈을 미리 만들어 두고 소유권을 부여한다.

mkhomedir 단독으로 충분한 경우는 **노드가 하나뿐일 때**(컨트롤러=계산 노드인 단일 노드 구성)뿐이다.
계산 노드를 추가하는 순간 공유 스토리지가 필요하다.

---

## 7. 검증 — 여기를 통과해야 Slurm을 올린다

### 7.1 단일 노드

```bash
id jungryul0515.park
# uid=205xxx(jungryul0515.park) gid=205xxx(domain users) ...

getent passwd jungryul0515.park
# jungryul0515.park:*:205xxx:205xxx:jungryul0515 park:/home/jungryul0515.park:/bin/bash

su - jungryul0515.park -c 'pwd; id -u'
```

확인 사항: 사용자명에 `@dt-hpc.net` 이 **붙지 않을 것**, 홈이 `/home/<사용자명>` 일 것, 셸이 있을 것.

### 7.2 전 노드 UID 일치 (가장 중요)

```bash
for h in seoul-login01 seoul-ctld01 seoul-cn0{1..4} \
         pangyo-login01 pangyo-ctld01 pangyo-gpu0{1,2}; do
  printf '%-16s %s\n' "$h" "$(ssh $h id -u jungryul0515.park 2>&1)"
done | tee /tmp/uid-check.txt

# 서로 다른 값이 있으면 여기서 2줄 이상 출력된다 → 그 노드의 sssd.conf를 재배포
awk '{print $2}' /tmp/uid-check.txt | sort -u
```

**출력이 한 줄이 아니면 Slurm 설치를 진행하지 않는다.**

### 7.3 포털과의 정합성

```bash
# 포털이 AD에서 읽는 이름과 노드가 해석하는 이름이 같아야 한다
getent passwd jungryul0515.park >/dev/null && echo "노드 OK"
```

포털 DB의 `user.username` 은 `sAMAccountName` 값이다. §4의 `use_fully_qualified_names = False`
가 이 일치를 보장한다. 이 값을 True로 두면 포털이 제출한 작업의 사용자 임퍼소네이션
(`X-SLURM-USER-NAME`)이 노드에서 해석되지 않는다.

---

## 8. Slurm 쪽에서 추가로 맞춰야 할 것

SSSD가 계정을 공급해도, Slurm은 별도로 다음을 요구한다.

| 항목 | 내용 |
|---|---|
| **기동 순서** | `slurmd`/`slurmctld`가 SSSD보다 먼저 뜨면 UID 조회에 실패한다. 유닛에 `After=sssd.service` 추가 |
| **munge** | `munge` 계정은 **로컬 시스템 계정**(uid<1000)이라 AD와 무관. 단 `/etc/munge/munge.key`는 전 노드 동일해야 하고 권한은 `0400 munge:munge` |
| **UID 대역 충돌** | AD 계정은 200000 이상, 로컬 시스템 계정은 1000 미만 → 충돌 없음. 로컬에 테스트 계정을 만들 때 200000 이상을 쓰지 말 것 |
| **slurmdbd 사용자 등록** | SSSD가 계정을 보여줘도 accounting에는 자동 등록되지 않는다. `sacctmgr add user <name> Account=<acct>` 필요 |
| **계산 노드 SSH 제한** | `pam_slurm_adopt`로 작업이 있는 사용자만 계산 노드에 접속하게 제한 |
| **`AllowGroups`** | `/etc/ssh/sshd_config`에서 로그인 노드 접근을 AD 그룹으로 제한 가능 |

`sacctmgr` 등록은 포털의 A-US-01(JIT 프로비저닝)과 별개다. 포털은 **포털 DB**에 사용자를
만들 뿐 Slurm accounting에는 손대지 않는다. 두 곳을 이어붙이는 자동화는 아직 없다.

---

## 9. 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| `realm join` 이 `Cannot contact any KDC` | DNS가 DC를 안 봄 | §2.1 SRV 조회부터 확인 |
| `Clock skew too great` | 시계 5분 이상 차이 | §2.2 chrony |
| `id <user>` 가 `no such user` | 검색 범위 밖 / 캐시 | `ldap_search_base` 확인 후 `sss_cache -E && systemctl restart sssd` |
| 비밀번호는 맞는데 로그인 거부 | `ad_gpo_access_control = enforcing` | §5 `permissive` |
| 사용자명이 `user@dt-hpc.net` | realmd 기본 설정 | `use_fully_qualified_names = False` |
| 로그인 직후 세션 종료 | 셸 없음 | `default_shell = /bin/bash` |
| 노드마다 UID가 다름 | idmap 파라미터 불일치 | §4 값 고정 후 **전 노드 재배포** + 캐시 삭제(아래 9.2) |
| `su - <user>` 가 `Permission denied` | `simple_allow_groups`에 없는 그룹 지정 | 그룹을 만들거나 그 줄을 삭제 |
| `groups: cannot find name for group ID ...` | 그룹 검색 범위가 `OU=people`로 좁혀짐 | §4의 `ldap_group_search_base`를 도메인 루트로 |
| 특정 노드만 `Online status: Offline` (`kinit -k`는 성공) | `ad_server`에 적은 이름이 DNS에 없음 | `sssctl domain-status`의 **Active servers** 이름을 `dig`로 확인. `ad_server` 줄 삭제 권장 |
| SSSD가 기동 실패 | `sssd.conf` 권한 | `chmod 600` |
| `Dynamic DNS update failed` (PTR만) | AD DNS에 역방향 조회 영역 없음 | 아래 9.1 — 인증에는 영향 없음 |

### 9.2 idmap 설정을 바꿨는데 UID가 그대로다

**SID→UID 슬라이스 배정은 SSSD 캐시에 기록되며, 한 번 정해지면 설정을 바꿔도 유지된다.**
`sss_cache -E`는 사용자 엔트리만 무효화할 뿐 슬라이스 배정은 지우지 못한다. 캐시 파일을 지워야 한다.

```bash
sudo systemctl stop sssd
sudo rm -f /var/lib/sss/db/*
sudo systemctl start sssd
id <user>
```

> **이미 그 UID로 만들어진 파일이 있으면 소유권이 어긋난다.** 홈·스크래치에 데이터가 쌓이기 전,
> 첫 노드 구성 단계에서 UID 체계를 확정할 것. 나중에 바꾸려면 전 노드 동시 전환 +
> `chown -R` 일괄 변경이 필요하다.

참고로 `ldap_idmap_default_domain_sid` 를 지정하면 그 도메인이 **첫 슬라이스**를 받아
UID가 `range_min + RID` 로 예측 가능해진다 (예: RID 1106 → 201106). 지정하지 않으면
도메인 SID 해시로 슬라이스가 정해져 `103801106` 같은 값이 나온다. **어느 쪽이든 무방하나
전 노드가 동일해야 한다** — 한 노드만 이 줄이 빠져도 UID가 어긋난다.

### 9.1 `Dynamic DNS update failed` — PTR 등록 실패

SSSD는 기동 시 자기 A/AAAA·PTR 레코드를 AD DNS에 등록한다(`dyndns_update` 기본 True).
정방향은 성공했는데 PTR만 실패한다면 **역방향 조회 영역이 AD DNS에 없기 때문**이다.

```bash
dig +short @192.168.1.10 slurm01.dt-hpc.net              # A 등록됨 → 정방향은 정상
dig +noall +authority @192.168.1.10 -x 192.168.1.201     # 1.168.192.in-addr.arpa 권한 없음
```

**인증·계정 해석에는 영향이 없다.** SSSD는 정방향 이름과 Kerberos로 동작한다.
다음 둘 중 하나를 고른다.

```ini
# (a) PTR 등록만 끈다 — 가장 간단, A 레코드 자동 등록은 유지
dyndns_update_ptr = False

# (b) DNS를 수동 관리한다면 자동 등록 자체를 끈다
dyndns_update = False
```

정석은 DC의 DNS 관리자에서 역방향 조회 영역 `1.168.192.in-addr.arpa` 를 만들고
동적 업데이트를 "보안 설정만"으로 여는 것이다. 그러면 (a) 없이도 PTR이 정상 등록된다.

로그: `journalctl -u sssd -f`, 상세 디버깅은 도메인 섹션에 `debug_level = 6` 후 재시작.
설정 점검: `sudo sssctl config-check`, 사용자 조회 경로 추적: `sudo sssctl user-checks <user>`.

---

## 10. 보안 메모

- **SSSD는 LDAP 서명 강제 정책의 영향을 받지 않는다.** 포털은 simple bind를 쓰기 때문에
  DC의 서명 강제를 껐지만, SSSD는 Kerberos GSSAPI로 붙어 서명·암호화를 자체 수행한다.
  따라서 **DC의 서명 강제를 다시 켜도 SSSD 연동은 정상 동작한다** — 포털에 LDAPS를
  적용한 뒤에는 되돌리는 것을 권한다.
- 노드는 도메인 조인 시 발급된 **호스트 keytab**(`/etc/krb5.keytab`)으로 인증하므로,
  포털처럼 bind 계정 비밀번호를 노드에 심을 필요가 없다.
- `cache_credentials = True`는 자격증명 해시를 노드에 남긴다. DC 장애 시 로그인 유지를 위한
  교환이며, 계산 노드에서 원치 않으면 로그인 노드에만 켠다.
- 노드를 폐기할 때 `sudo realm leave dt-hpc.net` 으로 AD의 컴퓨터 계정을 정리한다.

---

## 부록 A — 도메인 조인 없이 사용자 정보만 가져오기 (LDAP 클라이언트 모드)

AD에 컴퓨터 계정을 만들지 않고, **읽기 전용 bind 계정 하나로** 사용자·그룹 정보만 가져오는 구성이다.
`id_provider`를 `ad`가 아니라 `ldap`으로 바꾸면 된다. 노드는 AD 입장에서 그냥 LDAP 클라이언트이므로
`realm join`·`adcli`·호스트 keytab이 모두 필요 없다.

### 먼저 확인한 사실

이 AD는 **익명 조회를 허용하지 않는다.** 익명 bind 자체는 받아주지만(RootDSE 조회용),
실제 검색은 `operationsError`로 거부된다 — AD 기본 동작이다.

```
익명 bind: 성공
  익명으로 사용자 조회: 0건 (operationsError)
```

따라서 **bind 계정 자격증명이 전 노드에 필요하다.** 이것이 도메인 조인 방식과의 핵심 차이다.

### `/etc/sssd/sssd.conf`

```ini
[sssd]
domains = dt-hpc.net
config_file_version = 2
services = nss, pam

[nss]
default_shell = /bin/bash
override_homedir = /home/%u
filter_users = root,munge,slurm,daemon,bin,sys

[pam]
offline_credentials_expiration = 7

[domain/dt-hpc.net]
# --- 조인 없이 LDAP으로만 읽는다 -------------------------------------
id_provider = ldap
ldap_uri = ldap://192.168.1.10
ldap_schema = ad
ldap_search_base = OU=people,DC=dt-hpc,DC=net

# AD는 익명 조회를 막으므로 bind 계정이 필요하다
ldap_default_bind_dn = CN=SYSADMIN,CN=Users,DC=dt-hpc,DC=net
ldap_default_authtok_type = password
ldap_default_authtok = <bind 계정 비밀번호>

# AD가 돌려주는 referral을 따라가면 조회가 수 초씩 지연된다 — 반드시 끈다
ldap_referrals = False


# 사용자명·UID 산출은 조인 방식과 동일하게 맞춘다
ldap_user_name = sAMAccountName
ldap_id_mapping = True
ldap_idmap_range_min = 200000
ldap_idmap_range_max = 2000200000
ldap_idmap_range_size = 200000
ldap_idmap_default_domain_sid = S-1-5-21-750617150-2013882115-1463020004
use_fully_qualified_names = False
case_sensitive = False

# --- 인증: Kerberos (keytab 없이 동작) --------------------------------
auth_provider = krb5
krb5_server = 192.168.1.10
krb5_realm = DT-HPC.NET
# 호스트 keytab이 없어 KDC 응답을 검증할 수 없다
krb5_validate = False

access_provider = simple
# simple_allow_groups = hpc-users@dt-hpc.net
cache_credentials = True
enumerate = False
```

```bash
sudo chmod 600 /etc/sssd/sssd.conf
sudo systemctl restart sssd
id jungryul0515.park            # 조인 방식과 같은 UID가 나와야 한다
```

`ldap_id_mapping`은 `ldap_schema = ad`일 때 `objectSid`를 읽어 계산한다. 조회 권한만 있으면
**조인 방식과 완전히 같은 UID**가 나오므로, 두 방식을 섞어 쓰거나 나중에 전환해도 UID는 유지된다
(§7.2 검증은 그대로 수행할 것).

### 인증 방식 선택

| `auth_provider` | 동작 | 판단 |
|---|---|---|
| `krb5` | 사용자 비밀번호로 KDC에서 TGT 획득 | **권장.** 비밀번호가 평문으로 오가지 않는다 |
| `ldap` | DC에 simple bind로 검증 | **비권장.** LDAPS 인증서가 없는 현 상태에서는 사용자 비밀번호가 네트워크에 평문 노출 |

계산 노드처럼 **사용자가 직접 로그인하지 않는 노드**라면 `auth_provider`와 `[pam]`을 아예 빼고
`services = nss`만 둬도 된다. Slurm이 필요로 하는 건 UID 해석뿐이다.

### 조인 방식과의 비교

| | 도메인 조인 (`id_provider = ad`) | 조인 없음 (`id_provider = ldap`) |
|---|---|---|
| AD에 남기는 것 | 컴퓨터 계정 1개/노드 | 없음 |
| 노드에 두는 비밀 | 호스트 keytab (노드별·자동 갱신) | **bind 계정 비밀번호 (전 노드 공통·평문)** |
| 자격증명 폐기 | 컴퓨터 계정 삭제로 노드 단위 차단 | 비밀번호 변경 시 **전 노드 동시 교체** |
| DC 이중화 | SRV 레코드로 자동 탐색·failover | `ldap_uri`에 나열한 서버만 |
| 비밀번호 만료·정책 | 지원 | 제한적 |
| 준비 난이도 | DNS·시계·조인 권한 필요 | LDAP 포트만 열리면 됨 |

### 언제 이 방식을 고르나

- **개발 클러스터처럼 노드가 자주 생겼다 사라지는 경우** — 컴퓨터 계정 찌꺼기가 안 남는다.
- AD 관리 권한을 받기 어려운 경우 — 읽기 전용 계정 하나면 된다.
- 계산 노드가 UID 해석만 필요하고 로그인은 안 받는 경우.

반대로 **운영 환경이라면 조인 방식을 권한다.** 결정적인 이유는 비밀 관리다. 조인 방식은
노드마다 다른 keytab을 쓰고 자동 갱신되며 노드 하나만 폐기할 수 있는데, 이 방식은
**같은 비밀번호가 모든 계산 노드의 파일에 평문으로 들어간다.** 노드 한 대만 뚫려도
그 계정으로 AD 전체를 조회할 수 있다.

### 필수 보완 — 읽기 전용 전용 계정

이 방식을 쓴다면 `sysadmin`을 그대로 쓰지 말 것. `sysadmin`은 `Administrators` 그룹 소속이라
비밀번호가 노출되면 피해 범위가 도메인 전체다. AD에 **일반 사용자 권한의 전용 계정**
(예: `svc-sssd`)을 만들고, 비밀번호 무기한 만료 + `OU=people` 읽기 권한만 부여해 쓴다.
포털의 bind 계정도 같은 이유로 분리하는 것이 좋다.

---

## 부록 B — 신규 노드 투입 체크리스트

```
[ ] DNS를 192.168.1.10으로 (SRV 조회 성공)
[ ] chrony 동기화 (chronyc sources 에 ^*)
[ ] hostname FQDN + /etc/hosts
[ ] 패키지 설치
[ ] realm join (해당 클러스터 OU)
[ ] sssd.conf 를 기존 노드에서 복사 (직접 편집 금지)
[ ] chmod 600 + sss_cache -E + restart
[ ] id <테스트계정> → UID가 기존 노드와 동일한지 대조
[ ] 홈(NFS) 마운트
[ ] munge.key 복사 후 munge 기동
[ ] slurmd 기동 (After=sssd.service 확인)
```
