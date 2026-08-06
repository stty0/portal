/**
 * @novnc/novnc 1.7 최소 타입 선언.
 *
 * 패키지가 순수 JS라 타입이 없다. 우리가 실제로 쓰는 표면만 적는다 —
 * 전체를 흉내 내면 업스트림이 바뀔 때 거짓말이 된다.
 */
declare module '@novnc/novnc' {
  export interface RfbOptions {
    /** 웹소켓 subprotocol. 포털 세션 토큰을 여기에 싣는다. */
    wsProtocols?: string[]
    credentials?: { username?: string; password?: string; target?: string }
    shared?: boolean
    repeaterID?: string
  }

  /** RFB가 발생시키는 이벤트. detail 타입을 여기서 고정해 호출부가 캐스팅하지 않게 한다. */
  export interface RfbEventMap {
    connect: CustomEvent<void>
    disconnect: CustomEvent<{ clean: boolean }>
    credentialsrequired: CustomEvent<{ types: string[] }>
    securityfailure: CustomEvent<{ status: number; reason?: string }>
    clipboard: CustomEvent<{ text: string }>
    desktopname: CustomEvent<{ name: string }>
  }

  export default class RFB extends EventTarget {
    constructor(target: HTMLElement, url: string, options?: RfbOptions)

    addEventListener<K extends keyof RfbEventMap>(
      type: K,
      listener: (ev: RfbEventMap[K]) => void,
      options?: boolean | AddEventListenerOptions,
    ): void
    addEventListener(
      type: string,
      listener: EventListenerOrEventListenerObject | null,
      options?: boolean | AddEventListenerOptions,
    ): void

    /** 캔버스를 컨테이너 크기에 맞춘다(서버 해상도는 그대로). */
    scaleViewport: boolean
    /** 컨테이너 크기에 맞춰 서버 해상도 변경을 요청한다. */
    resizeSession: boolean
    viewOnly: boolean
    focusOnClick: boolean
    background: string

    disconnect(): void
    focus(): void
    blur(): void
    sendCtrlAltDel(): void
    sendKey(keysym: number, code: string | null, down?: boolean): void
    clipboardPasteFrom(text: string): void
  }
}
