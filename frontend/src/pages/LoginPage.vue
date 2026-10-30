<script setup>
/** 登录页：账号密码登录，按角色分流（developer/admin → 管理后台，agent → 工作台）。 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { apiLogin, setToken } from '../api'
import BrandLogo from '../components/BrandLogo.vue'

const emit = defineEmits(['logged-in'])

const username = ref('')
const password = ref('')
const showPwd = ref(false)
const errMsg = ref('')
const shake = ref(false)
const loading = ref(false)

/* ===== 悬浮星图：关键词节点散布在三维体积中（非共面），透视投影渲染 =====
   立体感来源：远小近大 + 空气透视（远处模糊变暗）+ 深度遮挡 + 星点粒子 + 双层视差星空。
   无鼠标时整网也在缓慢游移（idle sway），始终是活的。 */
const F = 1.6 // 焦距（归一化单位）
/* 关键词：手工布点构成不规则星团，n7 藏在球后制造穿透遮挡 */
const NODES = [
  { key: 'n0', text: '高效', x: -0.34, y: -0.26, z: 0.10 },
  { key: 'n1', text: '简洁', x: 0.30, y: -0.34, z: -0.16 },
  { key: 'n2', text: '互联', x: -0.44, y: 0.10, z: -0.26 },
  { key: 'n3', text: '实时', x: 0.46, y: 0.06, z: 0.14 },
  { key: 'n4', text: '安全', x: -0.20, y: 0.34, z: 0.20 },
  { key: 'n5', text: '智能', x: 0.18, y: 0.38, z: -0.10 },
  { key: 'n6', text: '协作', x: 0.02, y: -0.44, z: 0.28 },
  { key: 'n7', text: '可靠', x: -0.02, y: -0.06, z: -0.40 },
]
/* 无标签星点：填充体积，旋转时 selling depth */
const STARS = [
  { k: 's0', x: 0.52, y: -0.12, z: 0.02 },
  { k: 's1', x: -0.14, y: -0.52, z: -0.06 },
  { k: 's2', x: 0.40, y: 0.30, z: -0.30 },
  { k: 's3', x: -0.42, y: -0.30, z: 0.30 },
  { k: 's4', x: 0.12, y: 0.52, z: 0.18 },
  { k: 's5', x: -0.30, y: 0.44, z: -0.22 },
  { k: 's6', x: 0.50, y: 0.18, z: 0.34 },
  { k: 's7', x: -0.54, y: 0.14, z: -0.08 },
]
const ORIGIN = { x: 0, y: 0, z: 0 }
const RING = [0, 6, 1, 3, 5, 4, 2] // 外环连接顺序
const EDGES = [
  ...NODES.map((b) => ({ a: ORIGIN, b, cls: '' })), // 枢纽辐射
  ...RING.map((i, j) => ({ a: NODES[i], b: NODES[RING[(j + 1) % RING.length]], cls: 'edge' })), // 外环
  { a: NODES[2], b: NODES[3], cls: 'edge' }, // 横穿枢纽后方
  { a: NODES[1], b: NODES[4], cls: 'edge' },
  { a: NODES[7], b: NODES[0], cls: 'edge' }, // 球后节点牵出的深度线
  { a: NODES[7], b: NODES[3], cls: 'edge' },
]

const tilt = ref({ rx: 0, ry: 0 })
const target = { rx: 0, ry: 0 }
const cur = { rx: 0, ry: 0 }
let rafId = 0
let t0 = 0
function tick(now) {
  if (!t0) t0 = now
  const t = (now - t0) / 1000
  cur.rx += (target.rx - cur.rx) * 0.16 // 缓动跟随（快）
  cur.ry += (target.ry - cur.ry) * 0.16
  /* idle sway：无鼠标时整网也在持续旋转游移，始终是活的 */
  tilt.value = {
    rx: cur.rx + Math.sin(t * 1.35) * 4.5,
    ry: cur.ry + Math.cos(t * 1.05) * 5.8,
  }
  rafId = requestAnimationFrame(tick)
}
function onMove(e) {
  const r = e.currentTarget.getBoundingClientRect()
  target.rx = -((e.clientY - r.top) / r.height - 0.5) * 14
  target.ry = ((e.clientX - r.left) / r.width - 0.5) * 18
}
function resetTilt() {
  target.rx = 0
  target.ry = 0
}
onBeforeUnmount(() => rafId && cancelAnimationFrame(rafId))
onMounted(() => {
  rafId = requestAnimationFrame(tick)
})

function project(p, rx, ry) {
  const ax = (rx * Math.PI) / 180
  const ay = (ry * Math.PI) / 180
  const x1 = p.x * Math.cos(ay) + p.z * Math.sin(ay)
  const z1 = -p.x * Math.sin(ay) + p.z * Math.cos(ay)
  const y1 = p.y * Math.cos(ax) - z1 * Math.sin(ax)
  const z2 = p.y * Math.sin(ax) + z1 * Math.cos(ax)
  const s = F / (F + z2)
  return { px: x1 * s, py: y1 * s, s, z: z2 }
}
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

/* 关键词节点：深度 → 缩放 / 透明度 / 模糊（空气透视）/ 遮挡层级 */
const nodesView = computed(() =>
  NODES.map((n) => {
    const q = project(n, tilt.value.rx, tilt.value.ry)
    return {
      key: n.key,
      text: n.text,
      style: {
        left: 50 + q.px * 100 + '%',
        top: 50 + q.py * 100 + '%',
        transform: `translate(-50%, -50%) scale(${q.s.toFixed(3)})`,
        opacity: clamp(0.5 + (q.s - 0.8) * 1.8, 0.35, 1),
        '--fz': q.z < 0 ? `${Math.min(2, -q.z * 4).toFixed(2)}px` : '0px', // 只虚化底板，不虚化文字
        zIndex: Math.round(100 + q.z * 200),
      },
    }
  })
)
/* 星点粒子：同投影管线，远处更小更暗 */
const starsView = computed(() =>
  STARS.map((st) => {
    const q = project(st, tilt.value.rx, tilt.value.ry)
    const size = 5 * q.s
    return {
      k: st.k,
      style: {
        left: 50 + q.px * 100 + '%',
        top: 50 + q.py * 100 + '%',
        width: size.toFixed(1) + 'px',
        height: size.toFixed(1) + 'px',
        opacity: clamp(0.9 - Math.max(0, -q.z) * 1.6, 0.15, 0.9),
        zIndex: Math.round(100 + q.z * 200),
      },
    }
  })
)
/* 连线：端点走同一投影；透明度随两端平均深度衰减（远处线更淡更细） */
const linesView = computed(() =>
  EDGES.map((e, i) => {
    const a = project(e.a, tilt.value.rx, tilt.value.ry)
    const b = project(e.b, tilt.value.rx, tilt.value.ry)
    const depth = (a.z + b.z) / 2
    return {
      k: i, cls: e.cls,
      x1: 50 + a.px * 100, y1: 50 + a.py * 100,
      x2: 50 + b.px * 100, y2: 50 + b.py * 100,
      o: clamp((e.cls === 'edge' ? 0.5 : 0.68) - depth * 0.6, 0.08, 0.75),
      w: e.cls === 'edge' ? 1.0 : 1.4,
    }
  })
)
/* 双层视差星空背景：随倾斜反向轻移，拉开画面纵深 */
const starsFar = computed(() => ({
  transform: `translate(${(-tilt.value.ry * 2.2).toFixed(1)}px, ${(tilt.value.rx * 1.8).toFixed(1)}px)`,
}))
const starsNear = computed(() => ({
  transform: `translate(${(-tilt.value.ry * 6).toFixed(1)}px, ${(tilt.value.rx * 4.5).toFixed(1)}px)`,
}))
/* 地面辉光：反向漂移，像云团下方的一盏灯 */
const glowStyle = computed(() => ({
  transform: `translate(calc(-50% + ${(-tilt.value.ry * 10).toFixed(1)}px), ${(-tilt.value.rx * 6).toFixed(1)}px)`,
}))

const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' }

function setErr(msg) {
  errMsg.value = msg
  shake.value = false
  requestAnimationFrame(() => { shake.value = true })
}

async function submit() {
  const u = username.value.trim()
  const p = password.value
  if (!u || !p) { setErr('请输入账号和密码'); return }

  errMsg.value = ''
  loading.value = true
  try {
    const data = await apiLogin(u, p)
    setToken(data.token)
    emit('logged-in', data.user)
  } catch (ex) {
    setErr(ex.message || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-body" @mousemove="onMove" @mouseleave="resetTilt">
    <div class="login-wrap">
      <!-- 左侧品牌区：脑图式关键词 -->
      <section class="login-brand">
        <div class="brand-row rise">
          <BrandLogo :size="46" />
          <div>
            <div class="big-name">SI客服系统</div>
            <div class="big-sub">SI · CUSTOMER SERVICE SYSTEM</div>
          </div>
        </div>

        <div class="mind-map rise rise-1" aria-hidden="true">
          <i class="stars far" :style="starsFar"></i>
          <i class="stars near" :style="starsNear"></i>
          <div class="map-glow" :style="glowStyle"></div>
          <svg class="links" viewBox="0 0 100 100" preserveAspectRatio="none">
            <line
              v-for="l in linesView" :key="l.k"
              :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
              :class="l.cls" :style="{ strokeOpacity: l.o, strokeWidth: l.w }"
            />
          </svg>
          <span class="node core" title=""><i class="ring r2"></i></span>
          <i v-for="st in starsView" :key="st.k" class="star-dot" :style="st.style"></i>
          <span v-for="n in nodesView" :key="n.key" class="node kw" :style="n.style">{{ n.text }}</span>
        </div>

        <p class="tagline rise rise-2">一站式客服工作台 · 消息同步 · 会话协作 · 客户资料</p>

        <div class="login-meta rise rise-3">
          <span class="m-chip num">ENV · DEV</span>
        </div>
      </section>

      <!-- 右侧登录卡 -->
      <section class="login-card rise rise-2" :class="{ shake }">
        <div class="card-tag">
          <h2>登录</h2>
          <span class="latin">Sign in</span>
        </div>
        <p class="hint">使用管理员分配的账号登录，按角色进入对应工作台</p>

        <form class="login-form" novalidate @submit.prevent="submit">
          <div class="field">
            <label for="login-username">账号</label>
            <div class="input-group">
              <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
              <input id="login-username" v-model="username" class="input" type="text" placeholder="如：admin01" autocomplete="username">
            </div>
          </div>
          <div class="field">
            <label for="login-password">密码</label>
            <div class="input-group">
              <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/></svg></span>
              <input id="login-password" v-model="password" class="input" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password">
              <button type="button" class="icon-btn eye-btn" aria-label="显示或隐藏密码" @click="showPwd = !showPwd">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>

          <div class="form-err" :class="{ show: errMsg }">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 20h16a2 2 0 0 0 1.73-2Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
            <span>{{ errMsg }}</span>
          </div>

          <button class="btn btn-primary btn-block" type="submit" :class="{ loading }" :disabled="loading">登 录</button>
        </form>

        <p class="login-foot num">首次使用请找开发者开通账号 · 初始密码 123456</p>
      </section>
    </div>
  </div>
</template>
