/**
 * 입력 필드 공통 클래스.
 *
 * 14개 화면이 같은 문자열을 각자 갖고 있었고, 그러다 **두 갈래로 갈렸다** —
 * 절반은 `border-line`(카드 구분선 색), 절반은 `border-line-dark`. 같은 입력이 화면마다
 * 다르게 보였다. 입력 경계는 구분선보다 진해야 눈에 잡히므로 `line-dark`로 통일한다.
 *
 * **`inputBase`에는 폭이 없다.** 폭이 필요한 곳은 각자 붙인다 —
 * `[inputClass, 'w-auto']`처럼 덧붙이면 `w-full`과 `w-auto`가 **둘 다 남아 CSS 생성
 * 순서가 승자를 정하고**, 클래스 순서로는 못 이긴다. 이 프로젝트에서 네 번 만난 함정이다.
 */
export const inputBase =
  'px-3 py-2 rounded-lg border border-line-dark text-[14.5px] outline-none focus:border-brand-500'

/** 칸을 가득 채우는 기본형. 폼 안에서는 대개 이것을 쓴다. */
export const inputClass = `w-full ${inputBase}`
