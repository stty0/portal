# Exec Plan: Frontend — Vue 3 + TypeScript + Tailwind

- 근거 plan: [docs/plan.md](plan.md)
- 담당: 구현·검증 Claude

## 공통 규칙
- `<script setup lang="ts">` + Composition API. Options API 혼용 금지.
- 색상·간격은 **Tailwind 테마 토큰만** 쓴다. 임의 hex 금지(정적 프로토타입 규칙 계승).
- 사이드바/톱바는 `AppShell` 한 곳에만 존재한다. 화면이 복제하지 않는다.
- 화면 요소에 기능 정의서 ID를 `<Fid id="U-JB-01" />`로 유지(추적성).
- API 호출은 `src/api/*`를 통해서만. view가 `fetch`를 직접 부르지 않는다.
- 정적 데이터 화면은 `<StaticNotice />`로 명시한다.

## Task 목록

### T-01 프로젝트 스캐폴딩
- Vite + Vue3 + TS, Tailwind v4, Pinia, vue-router 설치·설정
- `vite.config.ts` 개발 프록시(`/api` → Traefik 9443)
- 수용: `npm run dev` 기동, `npm run build` 통과

### T-02 디자인 토큰 이관
- `design/css/style.css` `:root` → `src/assets/main.css`의 `@theme`
- 브랜드/뉴트럴/사이드바/상태 색, radius, shadow, font
- 수용: 토큰이 Tailwind 유틸(`bg-brand-700` 등)로 사용 가능

### T-03 API 클라이언트 · 타입
- `types/api.ts`(백엔드 스키마 대응), `api/client.ts`(토큰 주입·오류 정규화·401 처리)
- 도메인별: `auth.ts` `clusters.ts` `jobs.ts` `users.ts`
- 수용: 오류가 `{code,message,detail}`로 정규화되어 표면화

### T-04 스토어 · 라우터
- `stores/auth.ts`(로그인/로그아웃/권한), `stores/cluster.ts`(전역 클러스터 스코프)
- 라우터 가드: 미인증 → 로그인, `admin:access` 없으면 ADMIN 라우트 차단
- 수용: USER 계정이 ADMIN 경로 접근 시 차단

### T-05 공통 UI 컴포넌트
- `Card` `Table` `Badge` `Chip` `Btn` `Modal` `Field` `Meter` `Fid` `StaticNotice` `PageHead`
- 수용: 정적 프로토타입과 시각적으로 일치

### T-06 레이아웃 (AppShell)
- 사이드바(USER 9 / ADMIN 12 메뉴, 접기 상태 localStorage), 톱바(알림·도움말·클러스터 선택·계정), 푸터
- 수용: 22화면이 이 하나를 공유, 복붙 0

### T-07 인증 화면 (SCR-01)
- 로그인 + 최초 부트스트랩(`/auth/setup-status`로 분기)
- 수용: 실 백엔드로 로그인/로그아웃 동작

### T-08 API 연결 화면
- USER: 클러스터 현황(SCR-02) · Job 목록(03) · Job 제출(04) · Job 상세(05)
- ADMIN: 대시보드(10) · 전체 Job(12) · 사용자/AD(13) · 클러스터 관리(18)
- 수용: 실 API로 조회·제출·취소·역할변경·AD 동기화 동작

### T-09 정적 화면
- USER: 인터랙티브 앱(06) · 파일(07) · 터미널(08) · 사용량(09) · 공지(16)
- ADMIN: 노드/파티션(11) · 계정 · QOS · 리포트(14) · 설정(15) · License(17) · Billing(19)
- 수용: 디자인 재현 + 정적 데이터 표시

### T-10 검증
- `vue-tsc` 타입체크, `npm run build`, 라우트 도달성, 실 백엔드 연동 확인
- 수용: plan.md §5 전부

## 실행 순서
T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 → T-09 → T-10
