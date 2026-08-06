# 포털 서비스 계정 권한 최소화 가이드 (sudo · Slurm JWT)

포털이 클러스터에 갖는 두 갈래 권한을 최소화하는 방법을 정리한다.

- **SSH 경로** — `sudo`로 사용자 권한에 내려간다 (§1~§8)
- **REST 경로** — Slurm JWT로 slurmrestd를 호출한다 (§9)

**둘 다 해야 한다.** 한쪽만 잠그면 다른 쪽 문이 열려 있다.
정의서 §4.1의 요구사항을 만족시키기 위한 문서다.

> **포털 서비스 계정 + SSH 개인키(Secret 저장) 사용, 제한적 sudo(least privilege)로
> 사용자 impersonation — 전체 root sudo 지양**

- 작성일: 2026-08-06
- 대상: 로그인 노드(현재 `slurm01` `slurm02`), 서비스 계정 `ubuntu`
- **적용은 클러스터 관리자가 한다.** 이 문서는 가이드이며 포털이 설정을 바꾸지 않는다.

## 1. 현재 상태와 위험

```
$ sudo -l              # ubuntu 계정
User ubuntu may run the following commands on slurm01:
    (ALL : ALL) ALL
    (ALL) NOPASSWD: ALL
```

**무제한 root**다. 포털이 이 계정의 개인키를 Secret 저장소에 갖고 있으므로,
**포털이 침해되면 클러스터 root가 그대로 넘어간다.** 포털은 웹에 노출된 서비스이므로
공격면이 가장 넓은 쪽에 가장 큰 권한이 붙어 있는 구성이다.

## 2. 포털이 실제로 실행하는 것

코드에서 도출한 전부다(`app/clients/ssh/client.py`, `app/clients/ssh/pty.py`).
호출 형태는 항상 `sudo -n -u <대상사용자> <명령>`이며, **인자는 리스트로만 조립한다**
(셸 문자열 조립 없음).

| 명령 | 용도 | 기능 ID |
|---|---|---|
| `/usr/lib/openssh/sftp-server` | 파일 목록·읽기·쓰기·디렉터리 생성, 세션 `connection.json` 읽기 | U-FM-01, U-IA-02 |
| `-i` (대상 사용자 로그인 셸) | 웹 터미널 PTY | U-SH-01 |
| `getent passwd <user>` | 홈 경로 인식 | U-FM-01 |
| `df -P -k` | 파일시스템 사용량 | A-DB-05 |
| `quota -w -u <user>` | 쿼터 | A-DB-05 |
| `sshare -P -n -U -u <user> -o <필드>` | Fairshare | U-AC-02 |

이 외에는 없다. Job 제출·조회·취소, 노드·계정·QOS 조회는 전부 **slurmrestd(REST)**로
가므로 sudo가 관여하지 않는다.

**터널(U-IA-02 원격 데스크톱)은 sudo를 쓰지 않는다** — SSH `direct-tcpip`는 서비스 계정
자신의 권한으로 열리고, 접근 통제는 포털의 세션 소유자 검증이 담당한다.

## 2.5 순서 주의 — 회수가 먼저다

**권한을 추가하기 전에 기존 권한을 빼앗지 않으면 아무것도 나아지지 않는다.**
sudoers.d는 모든 파일을 읽고 마지막 매치가 이기므로, 이 문서의 `portal` 파일을 추가해도
그 목록에 **없는** 명령은 기존 규칙이 여전히 root로 허용한다.

현재 살아 있는 root 경로 두 개(실측):

```
/etc/sudoers.d/90-cloud-init-users:  ubuntu ALL=(ALL) NOPASSWD:ALL
/etc/sudoers:                        %sudo ALL=(ALL:ALL) ALL   (ubuntu가 sudo 그룹 멤버)
```

조치 절차와 잠김 방지 주의사항은 **§7 V1**에, 전체 적용 순서는 **§8**에 있다.

## 3. 권장 sudoers

`/etc/sudoers.d/portal` (권한 `0440`, 반드시 `visudo -cf`로 검사)

```sudoers
# 포털 서비스 계정 — 정의서 §4.1 최소 권한.
#
# 대상 사용자는 **포털 이용 전용 AD 그룹**으로 한정한다. 'domain users'(전원)를 쓰면,
# 나중에 관리자에게 AD 그룹으로 sudo를 주는 순간 다음 경로가 열린다:
#   포털 침해 -> sudo -u <관리자 AD 계정> bash -> 그 계정의 sudo -> root
# sudo 권한이 있는 계정은 이 그룹에 절대 넣지 않는다.
Runas_Alias PORTAL_USERS = %hpc-portal-users

# 전용 그룹을 아직 못 만들었다면 임시로 gid를 쓰되, 위 위험을 안고 가는 것임을 인지할 것.
#   Runas_Alias PORTAL_USERS = %#200513

Cmnd_Alias PORTAL_SFTP  = /usr/lib/openssh/sftp-server
Cmnd_Alias PORTAL_SHELL = /usr/bin/bash, /bin/bash
Cmnd_Alias PORTAL_INFO  = /usr/bin/getent passwd *, \
                          /usr/bin/df -P -k, \
                          /usr/bin/quota -w -u *, \
                          /usr/bin/sshare -P -n -U -u * -o *

Defaults:portalsvc !requiretty, use_pty
# OS 레벨 감사. 포털 DB의 감사 로그는 포털이 침해되면 함께 넘어가므로 독립 기록이 필요하다.
Defaults:portalsvc log_output, log_input

portalsvc ALL = (PORTAL_USERS) NOPASSWD: PORTAL_SFTP, PORTAL_SHELL, PORTAL_INFO
```

`log_input`은 웹 터미널 입력까지 남기므로 **보관 기간과 접근 권한을 먼저 정하고** 켠다.
기록은 `/var/log/sudo-io`에 쌓이고 `sudoreplay -l`로 조회한다.

### 왜 이 형태인가

**`Runas_Alias`가 핵심이다.** 명령 목록을 아무리 좁혀도 대상 사용자에 `root`가, 또는
**sudo 권한을 가진 계정**이 들어가면 의미가 없다. 그래서 AD 전원(`domain users`)이 아니라
포털 이용 전용 그룹을 쓴다. 그룹 이름에 공백이 있으면 GID 표기(`%#<gid>`)로 피한다.

**`PORTAL_SHELL`은 좁힐 수 없다.** 웹 터미널은 사용자 셸을 그대로 띄우는 기능이라,
"그 사용자로서 무엇이든 실행"이 곧 기능 자체다. 다만 **그 사용자 권한을 넘지 못하며**,
`Runas_Alias`가 root를 배제하므로 권한 상승 경로는 되지 않는다.

`sudo -i`는 대상 사용자의 로그인 셸을 실행하므로 sudoers에 그 셸 경로가 있어야 한다.
현재 AD 사용자 셸은 `/bin/bash`이고, Ubuntu 24.04는 usrmerge라 `/usr/bin/bash`가 실체다.
**두 경로를 모두 넣어야 안전하다.**

**`NOPASSWD`는 필수다.** 포털은 비대화형이라 비밀번호를 입력할 수 없다. 코드도 `sudo -n`
(비대화형)으로 호출하므로 이 설정이 빠지면 즉시 실패한다.

**`use_pty`는 유지한다.** sudo가 별도 PTY에서 명령을 돌려, 대상 사용자가 남긴 TTY 훔치기
공격을 막는다. 웹 터미널은 어차피 PTY를 따로 요청하므로 영향이 없다.

## 4. 배포판별 확인 사항

경로는 **반드시 실제 노드에서 확인하고 적는다.** sudoers의 명령 경로가 틀리면 조용히
거부되고, 포털에서는 "명령 실행 실패(rc=1)"로만 보인다.

```bash
command -v getent df quota sshare bash
ls -l /usr/lib/openssh/sftp-server /usr/libexec/openssh/sftp-server
getent passwd <AD사용자> | cut -d: -f7      # 로그인 셸
getent group "domain users"                  # gid 확인
```

현재 클러스터 실측값(Ubuntu 24.04):

```
/usr/bin/getent   /usr/bin/df   /usr/bin/sshare   /usr/bin/bash
/usr/lib/openssh/sftp-server
domain users → gid 200513,  로그인 셸 /bin/bash
quota → 설치되어 있지 않음 (쿼터 조회는 빈 목록으로 처리되므로 문제 없음)
```

- **Rocky/RHEL 계열**은 sftp-server가 `/usr/libexec/openssh/sftp-server`다.
  포털은 클러스터 등록 시 이 경로를 설정으로 받는다(`SshTarget.sftp_server`).
- **`quota`가 없으면** 그 줄을 빼도 된다. 포털은 실패를 오류로 올리지 않고 빈 목록으로 둔다.
- **`sshare`가 없으면** Fairshare 칸만 비고 나머지는 정상 동작한다.

## 5. 적용과 검증

서버별 절차는 **§8 서버별 조치 런북**에 있다. 순서·검증·롤백을 그쪽에서 한 번에 따라간다.

> sudoers를 잘못 쓰면 서비스 계정이 아무것도 못 하게 되어 포털의 SSH 기능이 통째로 멈춘다.
> 반드시 `visudo -cf`로 검사하고, 기존 설정을 백업한 뒤 적용한다.

## 6. 남는 위험 (이 설정으로도 없어지지 않는 것)

**셸 허용은 그 사용자의 자산 전부를 연다.** `sudo -u <user> bash`로 그 사용자의 SSH 개인키,
Kerberos 티켓, `.git-credentials`를 읽을 수 있다 — **클러스터 밖으로 나가는 횡적 이동**이다.
더 나쁜 것은 `~/.ssh/authorized_keys`에 키를 심을 수 있다는 점으로, **포털 키를 교체해도
그 백도어는 남는다.** 웹 터미널·파일 관리자 기능의 본질이라 sudoers로는 막을 수 없다.

그래서 **실질적 통제선은 sudoers가 아니라 포털의 인가 로직**이다. 대상 사용자를 클라이언트가
지정하지 못하게 코드에서 막고 테스트로 고정해 둔 이유가 이것이다. sudoers는 "포털이 침해돼도
root는 아니다"까지만 보장한다.

**개인키가 곧 권한이다.** 유출되면 위 통제가 전부 무력화된다. 정기 교체와
`authorized_keys`의 `from=` 제한을 함께 쓴다(현재 `from=` 0건 — 어디서든 쓸 수 있는 상태).

**와일드카드는 기대보다 넓게 매치된다.** sudo의 `*`는 공백을 포함해 매치되므로
`quota -w -u *`는 `quota -w -u root`도 허용한다. 여기 있는 넷은 전부 읽기 전용이라 실질
피해는 작지만, 쓰기 명령에는 절대 와일드카드를 쓰지 않는다.

## 7. 취약점별 조치

위험이 큰 순서다. **V1·V8이 두 경로(SSH·REST)의 뿌리이며, 이 둘을 하지 않으면
나머지는 의미가 없다.**

---

### V1 (치명) 기존 root 권한이 살아 있다

`/etc/sudoers.d/portal`을 추가해도 목록에 **없는** 명령은 기존 규칙이 여전히 허용한다.
sudoers.d는 모든 파일을 읽고 마지막 매치가 이긴다.

**조치**

```bash
# 0) 먼저 다른 root 경로를 확보한다 — 콘솔 접근 또는 별도 관리자 계정.
#    이 단계를 건너뛰면 노드에 갇힐 수 있다.
sudo cp /etc/sudoers.d/90-cloud-init-users /root/90-cloud-init-users.bak

# 1) cloud-init의 무제한 규칙 제거
sudo rm /etc/sudoers.d/90-cloud-init-users

# 2) sudo 그룹 멤버십 제거 (%sudo ALL=(ALL:ALL) ALL 경로 차단)
sudo gpasswd -d ubuntu sudo
```

**검증** — 아래가 `uid=0`을 내면 아직 끝나지 않은 것이다.

```bash
sudo -n id                    # 거부되어야 정상
sudo -l -U <서비스계정>       # PORTAL_* 외에 아무것도 없어야 한다
```

**잔여 위험** — 다른 sudoers 파일이 나중에 추가되면 같은 문제가 재발한다.
`/etc/sudoers.d/`를 구성관리(Ansible 등)로 고정하고 수동 편집을 막는다.

---

### V8 (치명) Slurm JWT가 `slurm` 관리자다 — **sudo와 별개 경로**

sudoers를 아무리 좁혀도 이 토큰 하나로 임의 사용자 코드 실행과 Slurm 전체 관리가 된다.
SSH도 sudo도 거치지 않는다.

**조치** — §9 전체. 요약하면 관리 작업 토큰 분리(§9.3) + 온디맨드 단기 토큰(§9.4).

**잔여 위험** — impersonation 능력 자체는 없앨 수 없다(§9.5). 노출만 줄인다.

---

### V2 (높음) Runas 대상이 AD 전원이다

현재 AD 사용자에게 sudo가 없어 아직 안전하지만, 관리자에게 AD 그룹으로 sudo를 주는
순간 `포털 침해 → sudo -u <관리자> bash → 그 계정의 sudo → root` 경로가 열린다.

**조치**

1. AD에 포털 이용 전용 그룹 `hpc-portal-users`를 만들고 **일반 사용자만** 넣는다.
   **sudo 권한이 있는 계정은 절대 넣지 않는다.**
2. 노드에서 해석되는지 확인한다.

```bash
getent group hpc-portal-users          # 멤버가 보여야 한다
```

3. sudoers의 `Runas_Alias`를 그 그룹으로 바꾼다(§3 참조).

**검증**

```bash
sudo -n -u root id                     # 거부
sudo -n -u <그룹 밖 AD 계정> /usr/bin/id   # 거부
```

**잔여 위험** — **신규 사용자를 그룹에 넣지 않으면 포털이 그 사용자로 동작하지 못한다.**
파일 관리자·터미널이 "명령 실행 실패"로 나온다. 계정 발급 절차에 그룹 추가를 포함시킨다.

---

### V3 (높음) `ubuntu`는 관리자 공용 계정이다

지금은 `authorized_keys`에 키가 하나뿐이라 사실상 포털 전용이지만, 관리자가 자기 키를
추가하는 순간 **사람이 포털 권한을 그대로 갖는다.**

**조치**

```bash
sudo useradd -m -s /bin/bash -c "HPC Portal service account" portalsvc
sudo install -d -m 700 -o portalsvc -g portalsvc /home/portalsvc/.ssh

# 포털 키만, 출발지 제한과 함께 등록 (실측: 포털은 192.168.1.100에서 나온다)
echo 'from="192.168.1.100",no-agent-forwarding,no-X11-forwarding,no-user-rc \
ssh-ed25519 AAAA... portal' | sudo tee /home/portalsvc/.ssh/authorized_keys
sudo chown portalsvc:portalsvc /home/portalsvc/.ssh/authorized_keys
sudo chmod 600 /home/portalsvc/.ssh/authorized_keys
```

포털 쪽도 함께 바꾼다: **관리자 → 클러스터**에서 `ssh_account`를 `portalsvc`로 수정하고
SSH 키를 새 키로 교체한 뒤 파일 관리자·터미널로 확인한다.

**검증**

```bash
sudo -l -U portalsvc                   # PORTAL_*만
sudo -l -U ubuntu                      # 아무것도 없어야 한다
```

**잔여 위험** — `no-port-forwarding`은 **넣으면 안 된다.** 원격 데스크톱이 SSH
`direct-tcpip` 터널을 쓰므로 함께 막힌다(§2 참조).

---

### V4 (중간) 셸 허용은 그 사용자의 자산 전부를 연다

`sudo -u <user> bash`로 그 사용자의 SSH 개인키·Kerberos 티켓·`.git-credentials`를 읽을 수
있고, `~/.ssh/authorized_keys`에 키를 심으면 **포털 키를 교체해도 그 백도어는 남는다.**
웹 터미널·파일 관리자 기능의 본질이라 **sudoers로는 제거할 수 없고 완화만 가능하다.**

**조치 (완화)**

1. **포털 인가 로직을 통제선으로 유지한다.** 대상 사용자를 클라이언트가 지정할 수 없게
   막혀 있고 테스트로 고정돼 있다. **새 기능을 추가할 때 이 원칙을 깨지 않는 것이 핵심이다.**
2. **포털 파드의 egress를 제한한다.** 로그인 노드 22번 외로 나가지 못하게 하면, 침해되어도
   클러스터 밖으로 번지지 않는다(k8s NetworkPolicy).
3. **`authorized_keys` 변조를 감시한다.** 홈이 NFS라 `auditd` 감시는 다른 노드에서 일어난
   변경을 놓친다. 한 호스트에서 주기적으로 지문을 떠 비교하는 편이 확실하다.

```bash
# 예: 매시간 스냅샷 후 변경분만 보고
find /home -maxdepth 3 -name authorized_keys -exec sha256sum {} \; \
  > /var/lib/portal/authkeys.now
diff /var/lib/portal/authkeys.prev /var/lib/portal/authkeys.now
```

**잔여 위험** — 근본 제거 불가. 이 기능(웹 터미널)을 제공하는 한 감수하는 위험이며,
탐지와 대응 속도로 관리한다.

---

### V5 (중간) OS 레벨 감사 기록이 없다

포털 DB의 감사 로그는 포털이 침해되면 함께 넘어간다. **독립된 기록이 필요하다.**

**조치** — sudoers에 추가(§3에 반영됨).

```sudoers
Defaults:portalsvc log_output, log_input
```

```bash
sudo install -d -m 700 /var/log/sudo-io
sudoreplay -l                          # 세션 목록
sudoreplay <ID>                        # 재생
```

**잔여 위험** — **웹 터미널 입력이 그대로 기록된다.** 사용자가 터미널에 입력한 비밀번호·
토큰이 남을 수 있으므로, **보관 기간·접근 권한·열람 절차를 먼저 정하고** 켜야 한다.
정하지 못했다면 `log_input` 없이 `log_output`만 켜는 것도 방법이다.
로그 자체를 원격(syslog)으로 밀어내면 노드 침해 시에도 남는다.

---

### V6 (낮음) 키에 출발지 제한이 없다

현재 `from=` 0건이다. 키가 유출되면 어디서든 쓸 수 있다.

**조치** — V3의 `authorized_keys`에 `from="192.168.1.100"`을 넣는다(실측 출발지).

**검증**

```bash
last -i -n 5 portalsvc                 # 192.168.1.100에서만 접속되는지
```

**잔여 위험** — **k3s 노드가 늘거나 IP가 바뀌면 포털이 잠긴다.** 노드를 추가할 계획이 있으면
대역으로 적는다(`from="192.168.1.0/24"`). 키 교체 주기도 함께 정한다(예: 분기).

---

### V7 (낮음) 명령 인자의 와일드카드

sudo의 `*`는 공백을 포함해 기대보다 넓게 매치된다. 현재 대상 넷은 **전부 읽기 전용**이라
실질 피해가 작다(`quota -w -u root`로 남의 쿼터를 보는 정도).

**조치** — 지금은 그대로 두어도 된다. 다만 **쓰기 명령에는 절대 와일드카드를 쓰지 않는다.**
새 명령을 추가할 때 인자를 고정할 수 있으면 고정한다.

---

## 8. 서버별 조치 런북

### 대상 서버

| 서버 | 주소 | 역할 | 조치 |
|---|---|---|---|
| AD 서버 | (도메인 `dt-hpc.net`) | 계정·그룹 관리 | 단계 1 |
| dev01 | 192.168.1.100 | 포털(k3s) · 빌드 | 단계 2 |
| slurm01 | 192.168.1.201 | 로그인 노드 | 단계 3·4·6·7 |
| slurm02 | 192.168.1.202 | 로그인 노드 | 단계 3·4·6·7 |
| 포털 웹 | https://www.dt-hpc.net:9443 | 관리자 콘솔 | 단계 5 |

**slurm01·slurm02는 동일한 작업을 각각 해야 한다.** 두 노드가 서로 다른 클러스터로
등록돼 있어 한쪽만 하면 다른 쪽 포털 기능이 죽는다.

### 순서가 중요하다

```
1  AD 그룹 생성            영향 없음
2  키 생성                 영향 없음
3  portalsvc 계정 생성      영향 없음 (계정만 만들고 아직 안 씀)
4  sudoers 배치            영향 없음 (ubuntu 권한은 그대로)
5  포털 전환 + 화면 확인    ← 여기서 처음으로 새 경로가 쓰인다
6  기존 권한 회수           ← 되돌릴 필요가 없다고 확인한 뒤에
7  최종 검증
```

**4번(sudoers)이 5번(포털 전환)보다 먼저여야 한다.** 순서가 바뀌면 `portalsvc`에 sudo
권한이 없는 상태로 전환되어 파일 관리자·웹 터미널·사용량 화면이 즉시 실패한다.

**6번은 마지막이다.** 5번까지 정상 동작을 확인한 뒤에 옛 권한을 거둔다.

---

### 단계 0 — 사전 확보 (slurm01, slurm02)

단계 6에서 `ubuntu`의 root 경로를 끊는다. **그 전에 다른 접근 수단을 확보한다.**

```bash
# 각 노드에서 실행
sudo cp /etc/sudoers.d/90-cloud-init-users /root/90-cloud-init-users.bak
sudo cp -a /etc/sudoers /root/sudoers.bak
id ubuntu                      # 소속 그룹 기록
```

- 콘솔(SCP 콘솔의 VNC/시리얼) 접근이 되는지 확인한다.
- 또는 sudo 권한이 있는 별도 관리자 계정을 미리 만들어 둔다.

---

### 단계 1 — AD 서버: 포털 이용 그룹 생성

**대상: AD 도메인 컨트롤러**

1. 보안 그룹 `hpc-portal-users` 생성 (Global 또는 Universal).
2. **포털을 쓸 일반 사용자만** 넣는다 — 현재 `jungryul0515.park`, `jooyeong.lee`,
   `sangjoon.sun`.
3. **sudo 권한을 가졌거나 가질 예정인 계정은 절대 넣지 않는다.**
   포털 침해 시 그 계정을 경유해 root로 올라가는 경로가 된다.

**검증 (slurm01, slurm02 각각)**

```bash
sudo sss_cache -E                       # SSSD 캐시 무효화
getent group hpc-portal-users           # 멤버가 보여야 한다
```

비어 있으면 SSSD가 아직 못 읽은 것이다. 캐시를 지워도 안 나오면
`sudo systemctl restart sssd` 후 다시 확인한다.

> **운영 규칙**: 앞으로 신규 사용자를 만들 때 이 그룹에 넣는 것을 계정 발급 절차에
> 포함시킨다. 빠뜨리면 그 사용자만 포털 파일·터미널이 "명령 실행 실패"로 나온다.

---

### 단계 2 — dev01: 서비스 계정 키 생성

**대상: dev01 (192.168.1.100)**

```bash
ssh-keygen -t ed25519 -N "" -C "hpc-portal service" -f ~/portalsvc_key
cat ~/portalsvc_key.pub                 # 단계 3에서 노드에 등록
cat ~/portalsvc_key                     # 단계 5에서 포털에 등록
```

**단계 5까지 끝나면 개인키 로컬 사본을 지운다.** 포털 Secret 저장소 밖에 남기지 않는다.

```bash
shred -u ~/portalsvc_key
```

---

### 단계 3 — slurm01·slurm02: 서비스 계정 생성

**대상: 두 노드에서 각각 실행**

**홈을 `/home` 밖에 둔다.** `/home`은 NFS 공유라 두 노드가 같은 디렉터리를 보게 되고,
노드별 UID가 다르면 소유권이 어긋난다. 노드 로컬 경로를 쓰면 이 문제가 아예 없어진다.

```bash
sudo useradd -r -m -d /var/lib/portalsvc -s /bin/bash \
     -c "HPC Portal service account" portalsvc
sudo install -d -m 700 -o portalsvc -g portalsvc /var/lib/portalsvc/.ssh

# <PUBKEY> 자리에 단계 2의 portalsvc_key.pub 내용을 넣는다.
# from= 은 포털의 실제 출발지다(실측: k3s가 SNAT하여 노드 IP로 나온다).
sudo tee /var/lib/portalsvc/.ssh/authorized_keys > /dev/null <<'EOF'
from="192.168.1.100",no-agent-forwarding,no-X11-forwarding,no-user-rc <PUBKEY>
EOF

sudo chown portalsvc:portalsvc /var/lib/portalsvc/.ssh/authorized_keys
sudo chmod 600 /var/lib/portalsvc/.ssh/authorized_keys
```

> **`no-port-forwarding`을 넣지 말 것.** 원격 데스크톱(U-IA-02)이 SSH `direct-tcpip`
> 터널을 쓰므로 함께 막힌다.

> **셸은 `/bin/bash`로 둔다.** `nologin`이면 포털이 SSH로 접속하지 못한다.
> 접근 제한은 `authorized_keys`의 `from=`과 sudoers가 담당한다.

**검증 (dev01에서)**

```bash
ssh -i ~/portalsvc_key portalsvc@192.168.1.201 id
ssh -i ~/portalsvc_key portalsvc@192.168.1.202 id
```

---

### 단계 4 — slurm01·slurm02: sudoers 배치

**대상: 두 노드에서 각각 실행**

§3의 내용으로 `/etc/sudoers.d/portal`을 만든다.

```bash
sudo visudo -f /etc/sudoers.d/portal        # 편집기가 문법 검사까지 한다
sudo chmod 0440 /etc/sudoers.d/portal
sudo visudo -cf /etc/sudoers.d/portal       # 재확인
```

**검증**

```bash
sudo -l -U portalsvc                        # PORTAL_* 목록이 보여야 한다
sudo -n -u jungryul0515.park id             # 거부되어야 정상(id는 목록에 없다)
```

이 시점에는 `ubuntu`의 옛 권한이 그대로 살아 있어 **포털은 계속 정상 동작한다.**

---

### 단계 5 — 포털 웹: 계정·키 전환

**대상: https://www.dt-hpc.net:9443 (관리자)**

두 클러스터에 **각각** 적용한다.

1. **관리자 → 클러스터** → `slurm-cluster-1` 수정
2. **SSH 서비스 계정**을 `ubuntu` → `portalsvc`
3. **SSH 개인키**에 단계 2의 `portalsvc_key` 내용 붙여넣기 → 저장
4. `slurm-cluster-2`에 같은 작업 반복

**검증 — 네 화면이 모두 되어야 다음 단계로 간다.**

| 화면 | 확인하는 것 |
|---|---|
| 파일 관리자 | `sftp-server` |
| 웹 터미널 | 로그인 셸 |
| 사용량 / 프로필 | `getent passwd`, `sshare` |
| 인터랙티브 앱 → 데스크톱 접속 | SSH 터널 (`direct-tcpip`) |

하나라도 실패하면 **단계 6으로 넘어가지 말고** 원인을 먼저 해결한다.
클러스터 설정을 `ubuntu`와 옛 키로 되돌리면 즉시 복구된다.

---

### 단계 6 — slurm01·slurm02: 기존 권한 회수

**대상: 두 노드에서 각각 실행. 단계 5가 전부 통과한 뒤에만.**

```bash
sudo rm /etc/sudoers.d/90-cloud-init-users     # ubuntu ALL=(ALL) NOPASSWD:ALL 제거
sudo gpasswd -d ubuntu sudo                     # %sudo 경로 차단
```

> `gpasswd -d`는 **이미 열려 있는 ubuntu 세션에는 즉시 반영되지 않는다.** 그 세션이
> 로그아웃할 때까지 옛 그룹 권한이 유지되므로, 회수 확인은 새 세션에서 한다.

---

### 단계 7 — 최종 검증 (slurm01, slurm02)

```bash
# 회수 확인 — 새 SSH 세션에서
sudo -n id                                  # 거부되어야 한다. uid=0이면 회수 실패
sudo -l -U ubuntu                           # 아무 권한도 없어야 한다
sudo -l -U portalsvc                        # PORTAL_* 만

# 권한 경계 확인
sudo -n -u root id                          # 거부 (Runas 제한)
sudo -n -u jungryul0515.park /usr/bin/id    # 거부 (명령 제한)
sudo -n -u <그룹 밖 AD 계정> /usr/bin/df -P -k   # 거부 (Runas 제한)

# 허용 확인
sudo -n -u jungryul0515.park /usr/bin/df -P -k   # 동작
```

마지막으로 포털에서 단계 5의 네 화면을 다시 확인한다.

---

### 롤백

문제가 생기면 **역순으로** 되돌린다. 각 단계는 독립적으로 되돌릴 수 있다.

| 되돌릴 것 | 서버 | 명령 |
|---|---|---|
| 기존 권한 복원 | slurm01·02 | `sudo cp /root/90-cloud-init-users.bak /etc/sudoers.d/ && sudo chmod 0440 /etc/sudoers.d/90-cloud-init-users`<br>`sudo gpasswd -a ubuntu sudo` |
| 포털 계정 되돌리기 | 포털 웹 | 클러스터 수정에서 `ssh_account`를 `ubuntu`로, 이전 SSH 키 재등록 |
| sudoers 제거 | slurm01·02 | `sudo rm /etc/sudoers.d/portal` |
| 서비스 계정 제거 | slurm01·02 | `sudo userdel -r portalsvc` (홈 `/var/lib/portalsvc` 함께 삭제) |

**가장 흔한 실패와 대처**

| 증상 | 원인 | 대처 |
|---|---|---|
| 포털 전 기능이 SSH 실패 | 키·계정 불일치 | 클러스터 설정을 `ubuntu`+옛 키로 복구 |
| 파일·터미널만 실패 | sudoers 명령 경로 오타 | `sudo -l -U portalsvc`로 목록 확인, §4의 실제 경로와 대조 |
| 특정 사용자만 실패 | AD 그룹 미등록 | `getent group hpc-portal-users`로 확인 후 추가 |
| 데스크톱만 실패 | `no-port-forwarding` 지정 | `authorized_keys`에서 제거 |
| `sudo -n id`가 root | 단계 6 미완료 | `90-cloud-init-users` 잔존 또는 ubuntu가 아직 sudo 그룹 |

## 9. Slurm JWT 권한 축소

sudo가 SSH 경로를 다룬다면, 이 절은 **REST 경로**를 다룬다. sudoers를 아무리 좁혀도
이쪽이 열려 있으면 의미가 없다.

### 9.1 현재 상태와 실측

포털이 보관 중인 토큰의 주체는 **`slurm`(SlurmUser)** 이고 수명이 1년이다.

```
$ python -c "..."   # 토큰 payload 디코드
{'exp': 1817430835, 'iat': 1785894835, 'sun': 'slurm'}
                                        ^^^^^^^^^^^^ Slurm 전체 관리자
```

이 토큰으로 가능한 것: **아무 사용자 이름으로나 Job 제출**(= 그 사용자로 컴퓨트 노드에서
코드 실행), 계정·QOS 생성/삭제, 임의 Job 취소, 노드 drain. SSH도 sudo도 필요 없다.

**"전용 계정으로 바꾸면 되지 않나"를 실측으로 확인했다.** 일반 사용자
(`jungryul0515.park`, AdminLevel 없음) 이름으로 토큰을 발급해 시험했다.

| 시도 | 결과 |
|---|---|
| 본인 Job 조회 | HTTP 200 |
| 본인 Job 제출 | 성공 (`job_id` 반환) |
| slurmdb 계정 **조회** | HTTP 200 (읽기는 권한 불필요) |
| **남의 이름으로 Job 제출** | **`1007 Protocol authentication error`** |

**결론: impersonation은 `slurm`/root 토큰에서만 된다.** AdminLevel을 줘도 안 된다 —
AdminLevel은 slurmdbd 관리 권한이지 "남 행세" 권한이 아니다(`root`가 `Administrator`인
것도 확인했다). 즉 **`slurm`을 대체할 계정은 없다.**

### 9.2 목표

능력을 없앨 수는 없다. 포털이 사용자 대신 Job을 내는 것이 기능이기 때문이다.
그래서 목표는 **노출 축소**다.

| 지금 | 목표 |
|---|---|
| 1년짜리 관리자 토큰이 Secret 저장소에 상주 | **저장된 장기 토큰 없음** |
| 유출되면 1년간 유효 | 유출돼도 10분 |
| 발급·사용 이력 없음 | sudo 로그에 발급 이력 |
| 관리 작업도 `slurm` 권한으로 | 관리 작업은 impersonation 불가 계정으로 |

---

### 9.3 조치 B — 관리 작업 토큰 분리 (먼저, 쉬움)

계정·QOS CRUD(A-US-02·03)는 impersonation이 필요 없다. AdminLevel만 있으면 된다.
**이 토큰은 유출돼도 남 행세를 못 하므로** 피해 범위가 작다.

**대상: slurm01, slurm02 (클러스터마다 1회)**

```bash
# 1) 서비스 계정에 Slurm 관리 권한 부여 (OS 계정 portalsvc는 §8 단계 3에서 만든 것)
sudo -u slurm sacctmgr -i add user portalsvc account=root adminlevel=Administrator

# 2) 확인
sudo -u slurm sacctmgr -n -P show user portalsvc format=User,AdminLevel
#    → portalsvc|Administrator

# 3) 관리 토큰 발급 (30일)
sudo -u slurm scontrol token username=portalsvc lifespan=2592000
```

**검증 — impersonation이 막혔는지 반드시 확인한다.**

```bash
ADMTOK=<위에서 받은 토큰>
curl -s -X POST \
  -H "X-SLURM-USER-NAME: jooyeong.lee" \
  -H "X-SLURM-USER-TOKEN: $ADMTOK" \
  -H "Content-Type: application/json" \
  -d '{"script":"#!/bin/bash\nhostname","job":{"name":"probe","partition":"cpu","environment":["PATH=/usr/bin"],"current_working_directory":"/tmp"}}' \
  http://localhost:6820/slurm/v0.0.41/job/submit | grep -o '"error_number":[0-9]*'
#    → "error_number":1007  이 나와야 정상. job_id가 나오면 실패 — 권한이 과하다.
```

---

### 9.4 조치 A — 온디맨드 단기 토큰

`slurm` 토큰을 **저장하지 않고**, 필요할 때 SSH로 짧게 발급받는다.

> **전제가 바뀌었다.** `token_provider.py`의 docstring은 "외부 소유 클러스터라 scontrol
> 접근 불가"를 근거로 저장 방식을 택했다고 적고 있다. 지금은 로그인 노드 SSH가 있으므로
> 그 전제가 더 이상 유효하지 않다.

#### 클러스터 쪽 — sudoers 추가

**파일: `/etc/sudoers.d/portal` (slurm01, slurm02 각각)**

§3의 내용에 아래를 **추가**한다.

```sudoers
# 토큰 발급만 slurm 권한으로 허용한다. 셸이나 다른 scontrol 하위 명령은 주지 않는다.
Runas_Alias PORTAL_SLURM = slurm
Cmnd_Alias  PORTAL_TOKEN = /usr/bin/scontrol token username=* lifespan=*

portalsvc ALL = (PORTAL_SLURM) NOPASSWD: PORTAL_TOKEN
```

**주의사항**

- **`/usr/bin/scontrol`을 통째로 허용하지 말 것.** 그러면 노드 drain·Job 취소·설정 변경까지
  `slurm` 권한으로 열린다. 반드시 `token` 하위 명령과 인자까지 적는다.
- 인자 개수가 정확히 일치해야 매치된다. **포털은 항상 `username=`과 `lifespan=`을 둘 다
  넘겨야 한다.** 하나라도 빠지면 sudo가 거부한다.
- 경로는 노드에서 확인한다: `command -v scontrol`.

**검증**

```bash
sudo -n -u slurm scontrol token username=jungryul0515.park lifespan=600   # 허용
sudo -n -u slurm scontrol ping                                             # 거부되어야 정상
sudo -n -u slurm /usr/bin/bash                                             # 거부되어야 정상
```

#### 포털 쪽 — 코드 변경 (미구현)

여기부터는 **백엔드 수정이 필요하다.** 현재 코드는 Secret 저장소에서 토큰을 읽는다.

| 파일 | 변경 내용 |
|---|---|
| `backend/app/clients/ssh/client.py` | `slurm_token(username, lifespan)` 메서드 추가. `sudo -u slurm scontrol token username=<X> lifespan=<N>` 실행 후 출력의 `SLURM_JWT=` 뒤를 파싱한다. `filesystems()`·`fairshare()`와 같은 방식 |
| `backend/app/clients/token_provider.py` | `token()`이 Secret이 아니라 위 메서드를 호출하도록 전환. 발급 비용이 있으므로 **Redis에 캐시**한다(키 `slurm:jwt:<cluster>:<user>`, TTL = lifespan의 절반) |
| `backend/app/clients/factory.py` | `slurm()`이 클러스터당 client 하나를 풀링한다. 사용자별 토큰을 쓰려면 **풀 키를 `(cluster_id, username)`으로** 바꾸거나, `token_provider`가 호출 시점의 사용자를 받도록 시그니처를 바꾼다 |
| `backend/app/services/cluster.py` | `slurm_client(cluster)` → `slurm_client(cluster, username=...)`. 호출부(Job·노드·계정·리포트·세션 서비스) 전부 영향 |
| `backend/app/services/cluster.py` `KIND_SLURM_JWT` | 관리 토큰용 종류(`SLURM_JWT_ADMIN`) 추가. 관리 작업 경로는 이 자격증명을 쓴다(조치 B) |

**가용성 트레이드오프** — 지금은 REST 경로가 SSH와 독립적이다. 이 변경 후에는
**SSH가 끊기면 Slurm 조회까지 전부 멈춘다.** 토큰 캐시가 그 창을 줄여주지만 없애지는 못한다.
캐시 TTL을 짧게 잡을수록 안전하고, 길게 잡을수록 SSH 장애에 강하다.

### 9.5 남는 한계 (정직하게)

**`scontrol token username=*`을 허용하면 포털은 아무 사용자의 토큰이나 만들 수 있다.**
힘으로 따지면 `slurm` 토큰을 들고 있는 것과 **동등하다.**

줄어드는 것은 능력이 아니라 노출이다.

- 가만히 있는 자격증명이 사라진다 (Secret 저장소 유출 = 즉시 관리자 → 해당 없음)
- 유효 기간이 1년 → 10분
- 발급마다 sudo 로그가 남는다 (§5 `log_output`)

능력까지 없애려면 impersonation을 REST에서 걷어내고 **Job 제출도 `sudo -u <user> sbatch`로
옮겨야 한다.** 그러면 모든 사용자 행위가 sudoers 통제 아래로 들어오지만
`JobService` 전면 재작성이 필요하다. 지금 얻는 것에 비해 변경이 크다.

### 9.6 적용 순서

```
1  조치 B: sacctmgr로 portalsvc에 AdminLevel 부여 + impersonation 차단 확인   (클러스터만)
2  조치 B: 관리 토큰 발급 → 포털에 SLURM_JWT_ADMIN으로 등록                  (코드 변경 필요)
3  조치 A: sudoers에 PORTAL_TOKEN 추가 + 발급/거부 검증                       (클러스터만)
4  조치 A: 포털 토큰 공급자를 온디맨드 방식으로 전환                          (코드 변경)
5  기존 slurm 장기 토큰 폐기 — Secret 저장소에서 삭제
```

**5번은 4번이 끝나고 정상 동작을 확인한 뒤에** 한다. 그 전에 지우면 포털의 Slurm 기능이
전부 멈춘다.

1·3번은 클러스터에서만 하면 되고 포털 동작에 영향이 없다. **먼저 해두어도 안전하다.**

## 10. 기능을 추가할 때

명령 목록을 좁히면 **새 기능이 sudoers 갱신을 요구한다.** 포털 코드에서
`_run_as(...)`를 새로 쓰는 순간 이 문서와 sudoers를 함께 고쳐야 한다.
그 비용이 최소 권한의 대가다.
