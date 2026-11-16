/** 多选与转发状态（ChatPanel 用）。
 *
 * 交互规则（产品定稿）：中间方暂无合并卡片发送接口，转发统一按逐条真实下发
 * （普通气泡直达微信）；转发方式不再提供选择。合并卡片 API 保留在服务端，
 * 中间方补上原生接口后前端可随时恢复入口（方式确认弹窗 + modeDlg 编排）。
 * 现状、保留资产与恢复步骤全文见 docs/message-forward.md。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { forwardMessages } from '../api'

export function useMultiForward() {
  const multi = ref(false)          // 多选模式
  const pickedIds = ref(new Set())  // 当前会话勾选的消息 id
  const pickerVisible = ref(false)  // 转发目标选择器
  const pending = ref(null)         // { convId, msgIds } 待转发的任务

  function enterMulti() {
    multi.value = true // 多选模式与文本拖选互斥，进入前清掉自定义选中（调用方配合 clearSelection）
    pickedIds.value = new Set()
  }

  function exitMulti() {
    multi.value = false
    pickedIds.value = new Set()
  }

  function togglePick(id) {
    const next = new Set(pickedIds.value)
    next.has(id) ? next.delete(id) : next.add(id)
    pickedIds.value = next
  }

  /* 多选底栏「转发」/单条菜单「转发」→ 打开选择器 */
  function startForward(task) {
    pending.value = task
    pickerVisible.value = true
  }

  /* 选择器确认目标：统一逐条真实下发 */
  function onPickerConfirm(targetIds) {
    pickerVisible.value = false
    doForward(targetIds)
  }

  /* 调转发接口：乐观交互——点确认立刻关选择器、退多选并提示"转发中"，
   * 后台继续等响应；完成/失败再补最终提示。
   * 原因：后端逐条串行调中间方（保序不能并行），N 条消息 N 次往返天然耗时，
   * 不该让多选界面跟着挂住。失败时消息仍在会话里，可重新转发。 */
  function doForward(targetIds) {
    const task = pending.value
    pending.value = null
    if (!task || !targetIds?.length) return
    exitMulti()
    const loading = ElMessage({ message: '正在转发…', type: 'info', duration: 0 })
    forwardMessages({
      conv_id: task.convId,
      msg_ids: task.msgIds,
      target_ids: targetIds,
      mode: 'single',
    })
      .then((data) => {
        loading.close()
        ElMessage.success(
          data.skipped
            ? `已逐条转发 ${data.sent} 条，${data.skipped} 条类型不支持已跳过`
            : `已逐条转发 ${data.sent} 条`,
        )
      })
      .catch((exc) => {
        loading.close()
        ElMessage.error(exc.message || '转发失败')
      })
  }

  return {
    multi, pickedIds, pickerVisible,
    enterMulti, exitMulti, togglePick, startForward, onPickerConfirm,
  }
}
