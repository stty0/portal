# Frontend — Slurm HPC Portal

Vue 3 + TypeScript + Tailwind CSS v4 SPA. 화면 SoT: [../정의서.md](../정의서.md),
디자인 원본: [../design/](../design/) 정적 프로토타입.

## 실행

```bash
npm install
npm run dev        # http://localhost:5173  (/api → Traefik 9443 프록시)
npm run build      # vue-tsc 타입체크 + 프로덕션 빌드 → dist/
npm run typecheck
```

개발 서버는 `/api`를 `https://192.168.1.100:9443`(Traefik)으로 프록시한다.
다른 백엔드를 보려면 `VITE_API_TARGET=... npm run dev`.

배포 시에는 프록시가 필요 없다 — Traefik이 같은 도메인에서 `/api`를 백엔드로,
나머지를 프론트엔드로 라우팅한다.

## 구조

| 디렉토리 | 역할 |
|---|---|
| `views/` | 화면(SCR) 단위 페이지. `user/` 9개 + `admin/` 12개 + 로그인·최초설정 |
| `components/layout/` | `AppShell`(사이드바·톱바·푸터) — **22화면이 공유** |
| `components/ui/` | `Card` `Table` `Badge` `Chip` `Btn` `Modal` `Field` `Meter` `Fid` 등 |
| `router/` | 라우팅 + 인증/권한 가드. 사이드바 메뉴는 라우터 meta에서 파생 |
| `stores/` | `auth`(세션·권한), `cluster`(전역 클러스터 스코프) |
| `api/` | 도메인별 백엔드 호출. view가 `fetch`를 직접 부르지 않는다 |
| `types/` | 백엔드 스키마 대응 타입 |
| `assets/main.css` | Tailwind + **디자인 토큰**(`design/css/style.css` `:root` 이관) |

### 정적 프로토타입에서 달라진 것
- **사이드바/톱바 복붙 제거** — 22개 파일에 복제돼 있던 마크업이 `AppShell` 한 벌이 됐다.
  메뉴 변경은 라우터 meta만 고치면 된다(CLAUDE.md 구조 규칙이 해소된 지점).
- **디자인 토큰 유지** — 색·간격을 하드코딩하지 않고 Tailwind 테마 토큰만 쓴다.
- **fid 칩 유지** — `<Fid id="U-JB-01" />`로 기능 정의서 추적성을 이어간다.

## 백엔드 연결 상태

백엔드가 구현한 도메인만 실제로 동작한다. 나머지는 화면만 있고 **정적 데이터**다.

| 상태 | 화면 |
|---|---|
| **실 API 연동** | 로그인·최초설정 · 클러스터 현황(일부) · Job 목록/제출/상세 · 대시보드(Job 통계) · 전체 Job 관리 · 사용자 · AD 연결 · 클러스터 관리 |
| 정적 데이터 | 공지 · 인터랙티브 앱 · 파일 · 터미널 · 사용량 · 노드/파티션 · 계정 · QOS · 리포트 · Billing · License · 운영설정 |

정적 화면은 상단에 `StaticNotice` 배너로 미연결 API를 명시하고, 사이드바 메뉴에도
`静` 표시가 붙는다 — "동작하는 화면"과 "그림"이 섞이지 않게 하기 위해서다.

## 알려진 제약
- 실시간 폴링·SSE·WebSocket 미구현(C-04) — Job 로그 tail·웹 터미널은 화면만.
- i18n(C-06) 미도입 — 한국어 하드코딩.
- 클러스터 전환 시 현재 화면을 다시 읽기 위해 `router.go(0)`으로 새로고침한다.
