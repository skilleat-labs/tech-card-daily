/**
 * downloader.js
 * html2canvas + JSZip 다운로드 헬퍼
 * (실제 로직은 index.html의 downloadZip()에 있고,
 *  이 파일은 Node.js 자동화에서 재사용할 유틸을 export합니다.)
 */

'use strict';

// 브라우저 환경에서는 no-op (index.html의 인라인 스크립트가 처리)
// Node.js / Playwright 환경에서 require()로 사용할 경우를 위한 구조

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {};
}
