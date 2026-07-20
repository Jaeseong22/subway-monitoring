/**
 * 백엔드 API의 기준 주소.
 *
 * `VITE_API_URL`이 **빈 문자열이면 같은 출처(same-origin)** 로 요청한다. 이때는
 * 프론트엔드를 서빙하는 nginx가 `/api`와 `/actuator`를 백엔드로 프록시하므로,
 * 브라우저 입장에서는 모든 요청이 한 도메인으로 나가 CORS가 필요 없다.
 *
 * 이 방식이 중요한 이유: `VITE_API_URL`은 빌드 타임에 번들에 구워지기 때문에,
 * 백엔드 주소를 알아야 하는 구조면 배포 환경(터널 URL, 실제 도메인)이 바뀔 때마다
 * 프론트엔드를 다시 빌드해야 한다. same-origin이면 재빌드가 필요 없다.
 *
 * `??`를 쓰는 이유: `||`는 빈 문자열을 falsy로 보고 기본값으로 넘어가 버려서
 * same-origin 설정이 무시된다.
 */
const RAW_BASE = (import.meta as any).env?.VITE_API_URL;

export const API_BASE: string =
  RAW_BASE === undefined || RAW_BASE === null ? 'http://localhost:8080' : String(RAW_BASE);

/** API 경로를 절대/상대 주소로 만든다. `apiUrl('/api/v1/stations')` 형태로 쓴다. */
export const apiUrl = (path: string): string =>
  `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
