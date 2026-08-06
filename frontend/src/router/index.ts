import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { installChunkReload } from '@/utils/chunk-reload'
import { getToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

/**
 * 라우트 메타
 *  - `public`   : 인증 불필요 (로그인·부트스트랩)
 *  - `admin`    : `admin:access` 권한 필요
 *  - `scr`/`title`/`icon` : 사이드바·크럼 표시용 (정의서 화면 ID)
 */
declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    admin?: boolean
    title?: string
    scr?: string
    icon?: string
    group?: string
    /** 백엔드 API에 연결되지 않은 화면(정적 데이터) */
    staticOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '로그인', scr: 'SCR-01' },
  },
  {
    path: '/setup',
    name: 'setup',
    component: () => import('@/views/SetupView.vue'),
    meta: { public: true, title: '최초 설정', scr: 'SCR-01' },
  },

  // ===== 사용자 포털 =====
  {
    path: '/',
    redirect: '/cluster',
  },
  {
    path: '/cluster',
    name: 'cluster',
    component: () => import('@/views/user/ClusterView.vue'),
    meta: { title: '클러스터', scr: 'SCR-02', icon: '◈', group: '클러스터' },
  },
  {
    path: '/notices',
    name: 'notices',
    component: () => import('@/views/user/NoticesView.vue'),
    meta: { title: '공지사항', scr: 'SCR-16', icon: '📢', group: '클러스터', staticOnly: true },
  },
  {
    path: '/jobs',
    name: 'jobs',
    component: () => import('@/views/user/JobsView.vue'),
    meta: { title: 'Job 목록', scr: 'SCR-03', icon: '☰', group: 'Job' },
  },
  {
    path: '/jobs/submit',
    name: 'job-submit',
    component: () => import('@/views/user/JobSubmitView.vue'),
    meta: { title: 'Job 제출', scr: 'SCR-04', icon: '✎', group: 'Job' },
  },
  {
    path: '/jobs/:jobId',
    name: 'job-detail',
    component: () => import('@/views/user/JobDetailView.vue'),
    meta: { title: 'Job 상세', scr: 'SCR-05' },
  },
  {
    path: '/apps',
    name: 'apps',
    component: () => import('@/views/user/AppsView.vue'),
    meta: { title: '인터랙티브 앱', scr: 'SCR-06', icon: '▣', group: '작업 환경' },
  },
  {
    // 세션 화면은 목록에서만 들어간다 — 메뉴에 올리지 않는다(group 없음).
    path: '/apps/:sid',
    name: 'desktop',
    component: () => import('@/views/user/DesktopView.vue'),
    meta: { title: '원격 데스크톱', scr: 'SCR-06' },
  },
  {
    path: '/files',
    name: 'files',
    component: () => import('@/views/user/FilesView.vue'),
    meta: { title: '파일 관리자', scr: 'SCR-07', icon: '▤', group: '작업 환경', staticOnly: true },
  },
  {
    path: '/terminal',
    name: 'terminal',
    component: () => import('@/views/user/TerminalView.vue'),
    meta: { title: '웹 터미널', scr: 'SCR-08', icon: '❯', group: '작업 환경', staticOnly: true },
  },
  {
    path: '/usage',
    name: 'usage',
    component: () => import('@/views/user/UsageView.vue'),
    meta: { title: '사용량 / 프로필', scr: 'SCR-09', icon: '◔', group: '내 정보' },
  },

  // ===== 관리자 콘솔 =====
  {
    path: '/admin',
    redirect: '/admin/dashboard',
  },
  {
    path: '/admin/dashboard',
    name: 'admin-dashboard',
    component: () => import('@/views/admin/DashboardView.vue'),
    meta: { admin: true, title: '대시보드', scr: 'SCR-10', icon: '▦', group: '모니터링' },
  },
  {
    path: '/admin/clusters',
    name: 'admin-clusters',
    component: () => import('@/views/admin/ClustersView.vue'),
    meta: { admin: true, title: '클러스터 관리', scr: 'SCR-18', icon: '◈', group: '자원 관리' },
  },
  {
    path: '/admin/nodes',
    name: 'admin-nodes',
    component: () => import('@/views/admin/NodesView.vue'),
    meta: {
      admin: true, title: '노드 / 파티션', scr: 'SCR-11', icon: '▤',
      group: '자원 관리', staticOnly: true,
    },
  },
  {
    path: '/admin/jobs',
    name: 'admin-jobs',
    component: () => import('@/views/admin/JobsView.vue'),
    meta: { admin: true, title: '전체 Job 관리', scr: 'SCR-12', icon: '☰', group: '자원 관리' },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/admin/UsersView.vue'),
    meta: { admin: true, title: '사용자', scr: 'SCR-13', icon: '👥', group: '사용자 / 정책' },
  },
  {
    path: '/admin/ad',
    name: 'admin-ad',
    component: () => import('@/views/admin/AdView.vue'),
    meta: { admin: true, title: 'AD 연결', scr: 'SCR-13', icon: '🔗', group: '사용자 / 정책' },
  },
  {
    path: '/admin/accounts',
    name: 'admin-accounts',
    component: () => import('@/views/admin/AccountsView.vue'),
    meta: {
      admin: true, title: '계정', scr: 'SCR-13', icon: '▩',
      group: '사용자 / 정책', staticOnly: true,
    },
  },
  {
    path: '/admin/qos',
    name: 'admin-qos',
    component: () => import('@/views/admin/QosView.vue'),
    meta: {
      admin: true, title: 'QOS', scr: 'SCR-13', icon: '⚖',
      group: '사용자 / 정책', staticOnly: true,
    },
  },
  {
    path: '/admin/reports',
    name: 'admin-reports',
    component: () => import('@/views/admin/ReportsView.vue'),
    meta: { admin: true, title: '통계 / 리포트', scr: 'SCR-14', icon: '◔', group: '운영', staticOnly: true },
  },
  {
    path: '/admin/billing',
    name: 'admin-billing',
    component: () => import('@/views/admin/BillingView.vue'),
    meta: { admin: true, title: '비용 / Billing', scr: 'SCR-19', icon: '₩', group: '운영', staticOnly: true },
  },
  {
    path: '/admin/license',
    name: 'admin-license',
    component: () => import('@/views/admin/LicenseView.vue'),
    meta: { admin: true, title: 'License 관리', scr: 'SCR-17', icon: '▧', group: '운영', staticOnly: true },
  },
  {
    path: '/admin/settings',
    name: 'admin-settings',
    component: () => import('@/views/admin/SettingsView.vue'),
    meta: { admin: true, title: '포털 운영 설정', scr: 'SCR-15', icon: '⚙', group: '운영' },
  },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 배포 직후 옛 탭이 사라진 청크를 부르면 화면이 조용히 멈춘다 — 한 번 새로고침해 복구한다.
installChunkReload(router)

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) return true

  // 새로고침 직후에는 store가 비어 있다. 토큰이 있으면 복구를 먼저 시도한다.
  if (!auth.isAuthenticated && getToken()) {
    await auth.restore()
  }
  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.isAdmin) {
    return { name: 'cluster' }
  }
  return true
})
