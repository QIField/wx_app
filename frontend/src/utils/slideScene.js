/** 滑块拼图 Canvas 绘制（纯函数，无组件状态）：
    生成星空场景 → 背景挖缺口 → 拼块取材。由 SlideCaptcha.vue 调用，
    缺口坐标与画布尺寸由组件决定，本模块只负责"画"。 */

/** 拼图轮廓：圆角方块 + 右侧圆形凸起，背景缺口与滑块拼块共用同一 path */
function tracePiecePath(ctx, x, y, s) {
  const r = 8, tab = 8, mid = y + s / 2
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + s - r, y)
  ctx.quadraticCurveTo(x + s, y, x + s, y + r)
  ctx.lineTo(x + s, mid - tab)
  ctx.arc(x + s, mid, tab, -Math.PI / 2, Math.PI / 2, false)
  ctx.lineTo(x + s, y + s - r)
  ctx.quadraticCurveTo(x + s, y + s, x + s - r, y + s)
  ctx.lineTo(x + r, y + s)
  ctx.quadraticCurveTo(x, y + s, x, y + s - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

/** 夜空场景：深蓝渐变 + 星云 + 星点 + 星座连线（呼应登录页品牌星图） */
function paintScene(ctx, w, h) {
  const lg = ctx.createLinearGradient(0, 0, 0, h)
  lg.addColorStop(0, '#16294f')
  lg.addColorStop(1, '#0e1c3c')
  ctx.fillStyle = lg
  ctx.fillRect(0, 0, w, h)

  const glow = (cx, cy, r, color) => {
    const rg = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
    rg.addColorStop(0, color)
    rg.addColorStop(1, 'rgba(10, 22, 48, 0)')
    ctx.fillStyle = rg
    ctx.fillRect(cx - r, cy - r, r * 2, r * 2)
  }
  glow(w * 0.78, h * 0.3, 90, 'rgba(29, 93, 228, 0.32)')
  glow(w * 0.2, h * 0.8, 80, 'rgba(90, 140, 255, 0.18)')

  for (let i = 0; i < 46; i++) {
    ctx.globalAlpha = 0.35 + Math.random() * 0.65
    ctx.fillStyle = Math.random() < 0.85 ? '#d8e4fc' : '#8fb4ff'
    ctx.beginPath()
    ctx.arc(Math.random() * w, Math.random() * h, 0.4 + Math.random() * 1.1, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1

  for (let c = 0; c < 2; c++) paintConstellation(ctx, w, h)
}

function paintConstellation(ctx, w, h) {
  const ox = Math.random() * (w - 90) + 20
  const oy = Math.random() * (h - 70) + 15
  const pts = Array.from({ length: 4 }, () => ({
    x: ox + Math.random() * 60,
    y: oy + Math.random() * 40,
  }))
  ctx.strokeStyle = 'rgba(148, 178, 255, 0.4)'
  ctx.lineWidth = 1
  ctx.beginPath()
  pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)))
  ctx.stroke()
  ctx.fillStyle = 'rgba(216, 228, 252, 0.95)'
  pts.forEach((p) => {
    ctx.beginPath()
    ctx.arc(p.x, p.y, 1.6, 0, Math.PI * 2)
    ctx.fill()
  })
}

/** 重绘一局：场景画布 → 背景挖缺口+暗边 → 拼块取材+高光描边 */
export function renderSlideScene({ bgCanvas, pieceCanvas, width, height, gapX, gapY, pieceSize, pad }) {
  const dpr = window.devicePixelRatio || 1

  // 场景画布（无缺口），供背景与拼块共同取材
  const scene = document.createElement('canvas')
  scene.width = width * dpr
  scene.height = height * dpr
  const sctx = scene.getContext('2d')
  sctx.scale(dpr, dpr)
  paintScene(sctx, width, height)

  bgCanvas.width = width * dpr
  bgCanvas.height = height * dpr
  Object.assign(bgCanvas.style, { width: `${width}px`, height: `${height}px` })
  const bctx = bgCanvas.getContext('2d')
  bctx.scale(dpr, dpr)
  bctx.drawImage(scene, 0, 0, width, height)

  bctx.save()
  bctx.globalCompositeOperation = 'destination-out'
  tracePiecePath(bctx, gapX, gapY, pieceSize)
  bctx.fill()
  bctx.restore()
  bctx.save()
  tracePiecePath(bctx, gapX, gapY, pieceSize)
  bctx.strokeStyle = 'rgba(6, 14, 34, 0.9)'
  bctx.lineWidth = 2
  bctx.stroke()
  bctx.restore()

  const psz = pieceSize + pad * 2
  pieceCanvas.width = psz * dpr
  pieceCanvas.height = psz * dpr
  Object.assign(pieceCanvas.style, { width: `${psz}px`, height: `${psz}px` })
  const pctx = pieceCanvas.getContext('2d')
  pctx.scale(dpr, dpr)
  pctx.save()
  pctx.translate(pad - gapX, pad - gapY)
  tracePiecePath(pctx, gapX, gapY, pieceSize)
  pctx.clip()
  pctx.drawImage(scene, 0, 0, width, height)
  pctx.restore()
  pctx.save()
  pctx.translate(pad - gapX, pad - gapY)
  tracePiecePath(pctx, gapX, gapY, pieceSize)
  pctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'
  pctx.lineWidth = 1.5
  pctx.stroke()
  pctx.restore()
}
