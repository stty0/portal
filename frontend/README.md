# Frontend — Slurm HPC Portal

Vue SPA + Nginx 정적 서빙(별도 컨테이너). 백엔드는 순수 API. 설계 근거: [../docs/backend-design.md](../docs/backend-design.md) §1.1·§5.2, 화면 SoT: [../정의서.md](../정의서.md).

> 현재는 **디렉토리 스켈레톤**만 존재한다(코드·빌드설정 미생성).
> 화면 원본은 정적 프로토타입 [../design/](../design/)(SCR-01~17, 디자인 토큰·마크업)이며, 이를 Vue 컴포넌트로 이관할 예정이다.

## 디렉토리 구조 (`src/`)
| 디렉토리 | 역할 |
|---|---|
| `views/` | 화면(SCR) 단위 페이지 컴포넌트 (user/admin 포털) |
| `components/` | 재사용 컴포넌트 (사이드바·톱바·클러스터 선택·모달 등, 프로토타입의 복붙 마크업을 공통화) |
| `router/` | vue-router 라우팅 정의 |
| `stores/` | 상태 관리 (선택 클러스터·세션·권한 등) |
| `api/` | 백엔드 REST 호출 클라이언트 |
| `assets/` | 스타일·디자인 토큰 (프로토타입 [../design/css/style.css](../design/css/style.css) `:root` 이관) |
| `public/` | 정적 리소스 |

## 배포
- 빌드 산출물을 **Nginx** 컨테이너로 정적 서빙, Ingress는 **Traefik** (backend-design §5.2).
