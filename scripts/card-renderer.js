/**
 * card-renderer.js
 * 카드 데이터 → HTML 문자열 배열 (가변 장 수)
 * + html2canvas PNG 변환
 */

'use strict';

/**
 * @param {object} data    - { cards: [{layout, content},...], caption, ... }
 * @param {object} series  - { id, color, icon, name }
 * @returns {string[]}     - HTML 문자열 배열 (cards.length 개)
 */
function buildCardHTMLs(data, series) {
  const total = data.cards.length;
  return data.cards.map((card, i) => buildCard(card, i, total, series));
}

// ── 카드 라우터 ───────────────────────────────────────────────
function buildCard(card, index, total, series) {
  const inner = (() => {
    switch (card.layout) {
      case 'hook':   return buildHookContent(card.content, series);
      case 'answer': return buildAnswerContent(card.content, series);
      case 'points': return buildPointsContent(card.content, series);
      case 'custom': return buildCustomContent(card.content, series);
      default:       return buildCustomContent(card.content, series);
    }
  })();

  return cardShell(inner, index, total, series);
}

// ── 공통 껍데기 ───────────────────────────────────────────────
const SERIES_DECOS = {
  k8s: `<div class="card-deco card-deco--k8s-glow"></div>
        <div class="card-deco card-deco--k8s-ring1"></div>
        <div class="card-deco card-deco--k8s-ring2"></div>`,
  docker: `<div class="card-deco card-deco--docker-glow"></div>
           <div class="card-deco card-deco--docker-box1"></div>
           <div class="card-deco card-deco--docker-box2"></div>
           <div class="card-deco card-deco--docker-box3"></div>`,
  azure: `<div class="card-deco card-deco--azure-c1"></div>
          <div class="card-deco card-deco--azure-c2"></div>
          <div class="card-deco card-deco--azure-c3"></div>
          <div class="card-deco card-deco--azure-bot"></div>`,
  aiml:  `<div class="card-deco card-deco--aiml-blob1"></div>
          <div class="card-deco card-deco--aiml-blob2"></div>`,
};

function cardShell(innerHtml, index, total, series) {
  const isLight = series.id === 'aiml';

  const dots = Array.from({ length: total }, (_, i) => {
    const active = i === index;
    return `<span class="dot${active ? ' active' : ''}" style="${active ? `background:${series.color};` : ''}"></span>`;
  }).join('');

  return `
<div class="skilleat-card skilleat-card--${series.id}${isLight ? ' skilleat-card--light' : ''}">
  ${SERIES_DECOS[series.id] || ''}
  <div class="card-top-bar" style="background:${series.color}"></div>
  <div class="card-body">
    <div class="card-header-row">
      <span class="series-badge" style="color:${series.color}">${series.icon} ${series.name}</span>
      <span class="card-num">${String(index + 1).padStart(2, '0')} / ${String(total).padStart(2, '0')}</span>
    </div>
    <div class="card-content">
      ${innerHtml}
    </div>
    <div class="card-footer">
      <span class="brand-name">스킬잇</span>
      <div class="dot-indicator">${dots}</div>
    </div>
  </div>
</div>`;
}

// ── hook 레이아웃 ─────────────────────────────────────────────
function buildHookContent(c, series) {
  const q = esc(c.question || '');
  // 마지막 어절(물음표 포함)을 accent 색상으로
  const hookHtml = q.replace(/([^\s]+[?？])\s*$/, `<span style="color:${series.color}">$1</span>`);
  const sub = esc(c.sub || '이 질문, 정확히 알고 넘어가 봅시다.');

  return `
    <div class="hook-question">${hookHtml}</div>
    <div class="hook-sub">${sub}</div>
    <div class="hook-deco" style="
      position:absolute; right:44px; bottom:130px;
      width:260px; height:260px; border-radius:50%;
      border:2px solid ${series.color}22;
      background:radial-gradient(circle,${series.color}10 0%,transparent 70%);
    "></div>`;
}

// ── answer 레이아웃 ───────────────────────────────────────────
function buildAnswerContent(c, series) {
  const title = esc(c.title || '');
  // "A = B" 또는 "A란 B" 앞부분 accent
  const titleHtml = title.replace(/^([^=\-–란]+)/, `<span style="color:${series.color}">$1</span>`);

  const descLines = (c.desc || '').split(/\\n|\n/).map(l => esc(l.trim())).filter(Boolean);
  const descHtml  = descLines.join('<br>');

  const diagramSvg = c.diagram_nodes ? buildDiagramSVG(c.diagram_nodes, series) : '';

  return `
    <div class="answer-title">${titleHtml}</div>
    <div class="answer-desc">${descHtml}</div>
    ${diagramSvg ? `<div class="diagram-wrap">${diagramSvg}</div>` : ''}`;
}

// ── SVG 흐름도 ────────────────────────────────────────────────
function buildDiagramSVG(nodes, series) {
  if (!nodes || !nodes.length) return '';

  const color  = series.color;
  const nodeW  = 160, nodeH = 54, gapX = 80;
  const svgW   = nodes.length * nodeW + (nodes.length - 1) * gapX + 40;
  const svgH   = 150;
  const cy     = svgH / 2;

  let defs = `<marker id="arr_${series.id}" markerWidth="8" markerHeight="8" refX="4" refY="3" orient="auto">
    <path d="M0,0 L0,6 L7,3 z" fill="${color}"/>
  </marker>`;

  let body = '';

  nodes.forEach((node, i) => {
    const x  = 20 + i * (nodeW + gapX);
    const cx = x + nodeW / 2;

    // 화살표
    if (i < nodes.length - 1) {
      const ax1 = x + nodeW + 6;
      const ax2 = x + nodeW + gapX - 6;
      body += `<line x1="${ax1}" y1="${cy}" x2="${ax2}" y2="${cy}"
        stroke="${color}" stroke-width="2.5" marker-end="url(#arr_${series.id})"/>`;
    }

    // 박스
    const isMain = !!node.main;
    const light  = series.id === 'aiml';
    body += `
      <rect x="${x}" y="${cy - nodeH/2}" width="${nodeW}" height="${nodeH}" rx="10"
        fill="${isMain ? color + '28' : (light ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)')}"
        stroke="${isMain ? color : (light ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.16)')}"
        stroke-width="${isMain ? 2 : 1}"/>
      <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle"
        fill="${isMain ? (light ? '#1a1a35' : '#fff') : (light ? 'rgba(0,0,0,0.7)' : 'rgba(232,236,255,0.82)')}"
        font-family="Malgun Gothic,sans-serif" font-size="16"
        font-weight="${isMain ? '700' : '500'}">${esc(node.label || '')}</text>`;

    if (node.sub) {
      body += `<text x="${cx}" y="${cy + nodeH/2 + 18}" text-anchor="middle"
        fill="${light ? 'rgba(0,0,0,0.38)' : 'rgba(232,236,255,0.42)'}" font-family="Malgun Gothic,sans-serif" font-size="13">
        ${esc(node.sub)}</text>`;
    }
  });

  return `<svg viewBox="0 0 ${svgW} ${svgH}" xmlns="http://www.w3.org/2000/svg">
  <defs>${defs}</defs>
  ${body}
</svg>`;
}

// ── points 레이아웃 ───────────────────────────────────────────
function buildPointsContent(c, series) {
  const title  = esc(c.title || '핵심 정리');
  const items  = (c.items || c.points || []).slice(0, 3);

  const itemsHtml = items.map((p, i) => `
    <div class="point-item">
      <div class="point-num" style="background:${series.color}">${i + 1}</div>
      <div>
        <div class="point-label">${esc(p.label || '')}</div>
        <div class="point-desc">${esc(p.desc || '')}</div>
      </div>
    </div>`).join('');

  // 제목의 강조 단어 accent
  const titleHtml = title.replace(/^(\S+)/, `<span style="color:${series.color}">$1</span>`);

  return `
    <div class="points-title">${titleHtml}</div>
    <div class="point-list">${itemsHtml}</div>`;
}

// ── custom 레이아웃 ───────────────────────────────────────────
function buildCustomContent(c, series) {
  const title = esc(c.title || '');
  const body  = esc(c.body || c.desc || '');

  const titleHtml = title.replace(/^(\S+)/, `<span style="color:${series.color}">$1</span>`);

  return `
    <div class="custom-title">${titleHtml}</div>
    <div class="custom-body">${body.replace(/\\n|\n/g, '<br>')}</div>`;
}

// ── 유틸 ─────────────────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── html2canvas PNG 변환 ──────────────────────────────────────
/**
 * @param {number} cardIndex - 0-based
 * @param {object} data
 * @param {object} series
 * @returns {Promise<Blob>}
 */
async function renderCardToBlob(cardIndex, data, series) {
  const htmls  = buildCardHTMLs(data, series);
  const html   = htmls[cardIndex];

  const container = document.createElement('div');
  container.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1080px;height:1080px;';
  container.innerHTML = html;
  document.body.appendChild(container);

  await document.fonts.ready;

  try {
    const canvas = await html2canvas(container.firstElementChild, {
      width:           1080,
      height:          1080,
      scale:           1,
      useCORS:         true,
      backgroundColor: ({ k8s: '#090d24', docker: '#071812', azure: '#080e1e', aiml: '#fafafa' })[series.id] || '#1A1A35',
      logging:         false,
    });

    return new Promise((resolve, reject) => {
      canvas.toBlob(blob => {
        blob ? resolve(blob) : reject(new Error('canvas.toBlob 실패'));
      }, 'image/png');
    });
  } finally {
    document.body.removeChild(container);
  }
}
