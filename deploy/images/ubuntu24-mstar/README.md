# ubuntu24-mstar — M-Star CFD 세션 이미지

인터랙티브 앱 `mstar`(U-IA-02)가 쓰는 컨테이너. 여기는 **요약**이다.

- 일반 계약: [docs/build-app-image.md](../../../docs/build-app-image.md)
- **이 이미지를 만든 전 과정**(명령·스크립트 전문·실패한 시도까지):
  [docs/build-mstar-image.md](../../../docs/build-mstar-image.md)

## 왜 rocky9-mate에 넣지 않았나

넣을 수 없다. M-Star 4.1.15는 Ubuntu 24.04 빌드다.

```
$ objdump -T bin/mstar | grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -1
GLIBC_2.38          # Rocky 9는 2.34
$ objdump -T bin/mstar | grep -o 'GLIBCXX_[0-9.]*' | sort -Vu | tail -1
GLIBCXX_3.4.32
```

`ldd`가 실행 자체를 거부한다. 그래서 이미지를 나눴고, **그 순간부터
`start-desktop.sh`·`start-mate.sh`·`reset-window-policy.sh`·`tint2rc`가 복사본**이 됐다.
갈라짐은 [test_session_images.py](../../../backend/tests/test_session_images.py)가 막는다 —
고칠 때는 **양쪽을 함께** 고친다.

## 빌드

M-Star 설치본(3.9GB)은 빌드 컨텍스트에 넣지 않는다. BuildKit 이름 있는 컨텍스트를 쓴다.

```bash
sudo docker build -t ubuntu24-mstar:1.0 \
  --build-context mstar=/home/jrpark/workspace/mstar/mstarcfd-4.1.15-ubuntu24 \
  deploy/images/ubuntu24-mstar

export APPTAINER_TMPDIR=/home/jrpark/.apptainer-tmp
export APPTAINER_CACHEDIR=/home/jrpark/.apptainer-cache
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"
sudo -E apptainer build "$APPTAINER_TMPDIR/ubuntu24-mstar-1.0.sif" docker-daemon://ubuntu24-mstar:1.0

sudo mv "$APPTAINER_TMPDIR/ubuntu24-mstar-1.0.sif" /home/.portal/images/
sudo chown root:root /home/.portal/images/ubuntu24-mstar-1.0.sif   # mv는 소유권을 옮긴다
sudo chmod 755      /home/.portal/images/ubuntu24-mstar-1.0.sif
sudo docker builder prune -af
```

## 패키지에서 조심할 것

| | Rocky 9 | Ubuntu 24.04 |
|---|---|---|
| `Xvnc` | `tigervnc-server` | `tigervnc-standalone-server` |
| **`vncpasswd`** | 〃 (같은 패키지) | **`tigervnc-tools`** ← 따로 뗀다 |

`tigervnc-tools`를 빠뜨리면 **빌드는 성공하고 `Xvnc`도 있는데** 세션이 비밀번호 발급
줄에서 죽는다. docker로 `-SecurityTypes None`만 확인하면 그 줄을 지나가지 않아 못 잡는다.

M-Star가 OS에 요구하는 라이브러리 목록은 추측하지 않았다 — `objdump -p bin/mstar`의
`NEEDED` 중 벤더 번들(`lib/`)에 없는 것만 뽑았다(22개). GTK3 기반(wxWidgets)이다.

## GPU 없이 뜨는 이유

3D 뷰포트는 OpenCASCADE(`libTKOpenGl`)가 그리고 OS의 `libGL.so.1`을 부른다.
`start-mstar.sh`가 Mesa llvmpipe를 명시적으로 고른다.

- 실측: `llvmpipe (LLVM 20.1.2, 256 bits)` · `OpenGL 3.3 (Compatibility Profile)`
- 유휴 세션 RSS **약 674MB**(mstar 439 + Xvnc 109 + marco 91 + tint2 19) — 노드 3915MB에 여유
- **해석(`mstar-cfd-mgpu`)은 CUDA가 필요해 여기서 돌지 않는다.** 라이선스도 없어
  상태 표시줄에 `No license`가 뜬다. 모델 작성·저장·시각화까지가 이 이미지의 범위다.

`OpenGl_Window::CreateWindow: window Visual is incomplete: no depth buffer` 경고가 남지만
와이어프레임 렌더링은 정상이었다(스크린샷 확인). 셰이딩된 곡면에서 z-순서가 어긋나면
여기를 의심한다.

## `mstar.sh`는 `set -u` 아래에서 죽는다

벤더 스크립트가 `$LD_LIBRARY_PATH`를 정의 없이 참조한다. `start-mstar.sh`가
`export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"`로 먼저 막아 둔 것은 그 때문이다 —
지우면 세션이 조용히 안 뜬다.
