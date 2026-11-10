/* ===== clipboard.js · 剪贴板动作（文本/图片），失败抛错由调用方 toast ===== */

/** 复制文本：Clipboard API 优先；非安全上下文（http 局域网部署）回退 execCommand。 */
export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  await copyViaExecCommand(text)
}

/** 复制图片统一入口，通道按环境自选：
 *  - 安全上下文（localhost/https）：取图 → 非 PNG 经 canvas 转码 → ClipboardItem 写位图（可直接粘贴）
 *  - 非安全上下文（http 局域网部署）：无 Clipboard API，回退"选中页内图片→系统复制"，
 *    imgEl 为页内已加载完成的 <img>（data-mid 定位由组件负责）。 */
export async function copyImage(url, imgEl) {
  if (navigator.clipboard?.write && typeof ClipboardItem !== 'undefined') {
    const blob = await toPngBlob(url)
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    return
  }
  copyImageElement(imgEl)
}

/** 选中页内 img 后触发系统复制：等效浏览器原生"复制图片"，HTTP 下同样把位图写进剪贴板。
 *  必须在用户手势内同步调用（execCommand 限制）；图片未就绪或失败抛错。 */
function copyImageElement(img) {
  if (!img?.complete || !img.naturalWidth) throw new Error('image not ready')
  const sel = window.getSelection()
  const range = document.createRange()
  range.selectNode(img)
  sel.removeAllRanges()
  sel.addRange(range)
  const ok = document.execCommand('copy')
  sel.removeAllRanges()
  if (!ok) throw new Error('execCommand image copy failed')
}

/* execCommand 兜底：隐藏 textarea 选区复制（文本专用；图片无此通道，走选中复制） */
function copyViaExecCommand(text) {
  return new Promise((resolve, reject) => {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) resolve()
    else reject(new Error('execCommand copy failed'))
  })
}

/* 剪贴板位图统一转 PNG：非 png（jpg/webp/gif）drawImage 重编码，动图会定格为首帧 */
async function toPngBlob(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`fetch image ${res.status}`)
  const blob = await res.blob()
  if (blob.type === 'image/png') return blob
  const bmp = await createImageBitmap(blob)
  const canvas = document.createElement('canvas')
  canvas.width = bmp.width
  canvas.height = bmp.height
  canvas.getContext('2d').drawImage(bmp, 0, 0)
  return new Promise((resolve, reject) =>
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('canvas toBlob failed'))), 'image/png'),
  )
}
