// postinstall 脚本：patch Element Plus 2.14.x 的 daterange 自动跳转行为
// 把 "选完年 → 自动切 month 面板" 改成 "选完年 → 停在 year 面板"
// 原代码：currentView.value = mode === "year" ? "month" : "date";
// 新代码：currentView.value = mode === "year" ? "year" : "date";

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dir = dirname(fileURLToPath(import.meta.url))

// EP 有两套产物：es/ (ESM) + lib/ (CJS)，都要 patch
const targets = [
  resolve(__dir, '../node_modules/element-plus/es/components/date-picker-panel/src/composables/use-panel-date-range.mjs'),
  resolve(__dir, '../node_modules/element-plus/lib/components/date-picker-panel/src/composables/use-panel-date-range.js'),
]

const ORIG = 'currentView.value = mode === "year" ? "month" : "date";'
const PATCHED = 'currentView.value = mode === "year" ? "year" : "date";'

let ok = 0
for (const target of targets) {
  if (!existsSync(target)) {
    console.warn(`[patch-ep] 文件不存在，跳过: ${target}`)
    continue
  }
  let content = readFileSync(target, 'utf-8')
  if (content.includes(PATCHED)) {
    ok++
    continue
  }
  if (!content.includes(ORIG)) {
    console.warn(`[patch-ep] 没找到目标代码（EP 版本可能已更新），跳过: ${target}`)
    continue
  }
  content = content.replace(ORIG, PATCHED)
  writeFileSync(target, content, 'utf-8')
  ok++
}
console.log(`[patch-ep] ✓ patch 完成 (${ok}/${targets.length})：选完年不再自动跳月`)
