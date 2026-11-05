/* ===== mock.js · 方案数据（仅静态数据，演示剧本在 app.js） ===== */
window.M = {
  stats: [
    { k: "跳的根源", v: "高度突变", d: "占位 105px → 真实 130~260px，一瞬完成" },
    { k: "候选方案", v: "3 个", d: "锚定补偿 / 尺寸预占 / 固定裁切" },
    { k: "推荐组合", v: "S1+S2", d: "S1 当次见效，S2 根治" },
  ],

  /* 演示策略 */
  strategies: [
    { id: "base", label: "现状", desc: "min 占位，加载后高度突变" },
    { id: "s1", label: "S1 锚定补偿", desc: "高度仍变，视口自动补偿不跳" },
    { id: "s2", label: "S2 尺寸预占位", desc: "占位=真实尺寸，高度根本不变" },
    { id: "s3", label: "S3 固定盒裁切", desc: "统一 180×135，零跳动但裁画面" },
  ],

  solutions: [
    {
      id: "s1",
      pri: "P0",
      title: "滚动锚定补偿",
      tagline: "高度照变，但视口稳如泰山",
      principle: "图片载入前后各记一次列表 scrollHeight，差值补偿到 scrollTop；容器再开 overflow-anchor 让浏览器原生锚定兜底。布局不变，只稳住视野。",
      diff: [
        { t: "css", code: "/* ChatPanel.vue · 消息容器 */\n.messages { overflow-anchor: auto; }" },
        { t: "js", code: "// MessageRow.vue · onMediaOk()\nconst list = document.querySelector('.messages')\nconst before = list.scrollHeight\nrequestAnimationFrame(() => {\n  list.scrollTop += list.scrollHeight - before\n})" },
      ],
      pros: ["全局面：历史图 / 表情 / 视频 / 引用缩略图一次覆盖", "纯前端 2 处小改，零后端", "对旧数据零依赖，当次生效"],
      cons: ["图片最终尺寸仍会变，只是视野不动", "补偿发生在加载完成那一帧，理论有 1 帧微跳"],
      effort: "≈ 10 分钟 · 2 个文件",
      risk: "低",
    },
    {
      id: "s2",
      pri: "P1 · 根治",
      title: "服务端真尺寸预占位",
      tagline: "加载前占位就是最终尺寸，从根上没有变化",
      principle: "同步时本来就会下载缩略图（predownload），顺手用 PIL 读出像素宽高存进 payload.w/h；出参与 WS 原样下发。前端占位块直接 aspect-ratio: w/h，占位高度 = 最终高度。",
      diff: [
        { t: "py", code: "# sync · 缩略图下载完成后\nfrom PIL import Image\nwith Image.open(path) as im:\n    payload[\"w\"], payload[\"h\"] = im.size" },
        { t: "html", code: "<!-- MessageRow.vue · 占位块 -->\n<span class=\"ph ph-img\"\n  :style=\"m.payload.w ? { '--w': m.payload.w, '--h': m.payload.h } : null\">", "note": "无 w/h 的历史消息回退现有 min 占位" },
      ],
      pros: ["根治：高度从头到尾不变，无补偿也无帧跳", "缩略图 / 大图 / 引用缩略图全部一致", "出参 WS 同源，历史+实时统一"],
      cons: ["后端 3 处改动（读尺寸 / 入库 / 下发）", "依赖缩略图下载成功，失败回退 min 占位", "历史存量消息没有 w/h（可接受，回退现状）"],
      effort: "≈ 40 分钟 · 后端 3 处 + 前端 1 处",
      risk: "低（读尺寸失败 try/except 跳过即可）",
    },
    {
      id: "s3",
      pri: "备选",
      title: "固定尺寸盒 + cover 裁切",
      tagline: "最简单的零跳动，代价是裁画面",
      principle: "所有图统一塞进固定盒子（如 180×135），object-fit: cover 填充。占位与最终尺寸恒等，天然零跳动。",
      diff: [{ t: "css", code: ".media.img, .ph-img {\n  width: 180px; height: 135px;\n  object-fit: cover;\n}" }],
      pros: ["实现最简，一行 CSS", "列表布局完全稳定"],
      cons: ["竖图/横图都会被裁，客服看不清图片细节", "与微信原图体验相悖"],
      effort: "≈ 2 分钟",
      risk: "低，但体验不可接受 → 不推荐",
    },
  ],

  checklist: [
    "ChatPanel 消息容器开启 overflow-anchor: auto",
    "MessageRow 图片/表情 onMediaOk 增加 scrollHeight 差值补偿",
    "引用缩略图（q-ph）同样接入补偿",
    "predownload 下载缩略图后用 PIL 读像素宽高写入 payload.w/h（try/except 兜底）",
    "_msg_json 与 WS 广播原样下发 w/h（payload 已透传，核对即可）",
    "前端占位块支持 aspect-ratio 预占位，无 w/h 回退 min 占位",
    "回归验证：旧消息（无 w/h）、引用缩略图、视频加载三类场景不跳",
    "补单测：宽高写入 payload 与出参下发",
  ],
}
