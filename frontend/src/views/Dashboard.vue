<template>
  <div class="dashboard">
    <h2>仪表盘</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon catalog">
              <el-icon :size="32"><Film /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.catalog?.total || 0 }}</div>
              <div class="stat-label">收录影视</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon tasks">
              <el-icon :size="32"><List /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.tasks?.done || 0 }}</div>
              <div class="stat-label">已完成任务</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon sync">
              <el-icon :size="32"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.sync?.today_synced || 0 }}</div>
              <div class="stat-label">今日同步</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon failed">
              <el-icon :size="32"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.sync?.today_failed || 0 }}</div>
              <div class="stat-label">今日失败</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速操作 -->
    <el-card class="quick-actions">
      <template #header>
        <div class="card-header">
          <span>快速操作</span>
        </div>
      </template>

      <el-space wrap>
        <el-button type="primary" @click="showRunDialog">
          <el-icon><VideoPlay /></el-icon>
          执行一次检查
        </el-button>
        <el-button @click="refreshStats">
          <el-icon><Refresh /></el-icon>
          刷新统计
        </el-button>
      </el-space>
    </el-card>

    <!-- 运行模式选择对话框 -->
    <el-dialog
      v-model="runDialogVisible"
      title="执行检查"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="runOptions" label-width="100px">
        <el-form-item label="运行模式">
          <el-radio-group v-model="runOptions.mode">
            <el-radio label="auto">全自动</el-radio>
            <el-radio label="semi-auto">半自动</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容类型">
          <el-select v-model="runOptions.content_type" placeholder="全部类型" clearable style="width: 100%">
            <el-option label="全部类型" value="" />
            <el-option label="电影" value="movie" />
            <el-option label="剧集" value="series" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRun" :loading="running">
          开始执行
        </el-button>
      </template>
    </el-dialog>

    <!-- 任务执行状态对话框 -->
    <el-dialog
      v-model="statusDialogVisible"
      title="任务执行状态"
      width="550px"
      :close-on-click-modal="false"
      class="task-status-dialog"
      center
    >
      <div class="task-status">
        <div class="status-icon-wrapper">
          <div class="status-icon-bg" :class="getStatusBgClass(taskStatus.status)">
            <el-icon v-if="taskStatus.status === 'running'" class="is-loading" :size="48"><Loading /></el-icon>
            <el-icon v-else-if="taskStatus.status === 'completed'" :size="48"><CircleCheck /></el-icon>
            <el-icon v-else-if="taskStatus.status === 'failed'" :size="48"><CircleClose /></el-icon>
            <el-icon v-else-if="taskStatus.status === 'stopped'" :size="48"><VideoPause /></el-icon>
            <el-icon v-else :size="48"><InfoFilled /></el-icon>
          </div>
        </div>
        <div class="status-text">
          <div class="status-title" :class="getStatusTitleClass(taskStatus.status)">{{ getStatusTitle(taskStatus.status) }}</div>
          <div class="status-message">{{ taskStatus.message }}</div>
          <div v-if="taskStatus.error" class="status-error">{{ taskStatus.error }}</div>
        </div>
      </div>

      <el-progress
        v-if="taskStatus.status === 'running'"
        :percentage="taskStatus.progress"
        :stroke-width="8"
        :show-text="true"
        :indeterminate="true"
        :duration="1"
      />

      <!-- 执行日志 -->
      <div v-if="taskLogs.length > 0" class="task-logs">
        <div class="log-header">
          <el-icon><Document /></el-icon>
          <span>执行日志</span>
        </div>
        <div class="log-content">
          <div v-for="(log, index) in taskLogs" :key="index" class="log-line">
            <span class="log-index">{{ index + 1 }}</span>
            <span class="log-text">{{ log }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button
            v-if="taskStatus.status === 'running' || taskStatus.status === 'queued' || taskStatus.status === 'stopping'"
            type="danger"
            @click="handleStopTask"
            :loading="stopping"
            size="large"
          >
            <el-icon><VideoPause /></el-icon>
            停止任务
          </el-button>
          <el-button @click="statusDialogVisible = false" size="large">
            关闭
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 最近同步记录 -->
    <el-card class="recent-syncs">
      <template #header>
        <div class="card-header">
          <span>最近同步记录</span>
          <el-button type="primary" link @click="$router.push('/history')">
            查看更多
          </el-button>
        </div>
      </template>

      <el-table :data="recentRecords" style="width: 100%" v-loading="loading">
        <el-table-column prop="item_name" label="影视名称" />
        <el-table-column prop="item_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.item_type === 'movie' ? 'success' : 'warning'" size="small">
              {{ row.item_type === 'movie' ? '电影' : '剧集' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sync_time" label="同步时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false)
const running = ref(false)
const stopping = ref(false)
const stats = reactive({
  catalog: {},
  tasks: {},
  sync: {}
})
const recentRecords = ref([])

// 运行对话框
const runDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const runOptions = reactive({
  mode: 'auto',
  content_type: ''
})

// 任务状态
const taskId = ref('')
const taskStatus = reactive({
  status: '',
  message: '',
  error: '',
  progress: 0
})
const taskLogs = ref([])

const getStatusType = (status) => {
  const types = {
    saved: 'success',
    failed: 'danger',
    skipped: 'info',
    pending_manual: 'warning'
  }
  return types[status] || ''
}

const getStatusText = (status) => {
  const texts = {
    saved: '已保存',
    failed: '失败',
    skipped: '跳过',
    pending_manual: '待手动'
  }
  return texts[status] || status
}

const getStatusTitle = (status) => {
  const titles = {
    queued: '任务排队中',
    running: '任务执行中',
    stopping: '正在停止任务...',
    completed: '任务已完成',
    failed: '任务失败',
    stopped: '任务已停止'
  }
  return titles[status] || status
}

const getStatusBgClass = (status) => {
  const classes = {
    running: 'icon-bg-running',
    stopping: 'icon-bg-stopping',
    completed: 'icon-bg-completed',
    failed: 'icon-bg-failed',
    stopped: 'icon-bg-stopped'
  }
  return classes[status] || 'icon-bg-default'
}

const getStatusTitleClass = (status) => {
  const classes = {
    running: 'status-title-running',
    stopping: 'status-title-stopping',
    completed: 'status-title-completed',
    failed: 'status-title-failed',
    stopped: 'status-title-stopped'
  }
  return classes[status] || ''
}

const showRunDialog = () => {
  // 获取当前模式
  api.get('/check/modes').then(res => {
    if (res.data.current_mode) {
      runOptions.mode = res.data.current_mode
    }
  }).catch(() => {})
  runDialogVisible.value = true
}

const handleRun = async () => {
  running.value = true
  try {
    const payload = {
      mode: runOptions.mode,
      content_type: runOptions.content_type || null
    }

    const res = await api.post('/check', payload)
    taskId.value = res.data.task_id
    runDialogVisible.value = false
    statusDialogVisible.value = true
    taskStatus.status = 'queued'
    taskStatus.message = '任务已启动，等待执行...'
    taskStatus.progress = 0

    // 轮询任务状态
    pollTaskStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '执行失败')
  } finally {
    running.value = false
  }
}

const pollTaskStatus = async () => {
  if (!taskId.value) return

  try {
    const [statusRes, logsRes] = await Promise.all([
      api.get(`/check/status/${taskId.value}`),
      api.get(`/check/logs/${taskId.value}`)
    ])

    const { status, message, error, progress } = statusRes.data
    taskStatus.status = status
    taskStatus.message = message
    taskStatus.error = error
    taskStatus.progress = progress || 0

    // 更新日志
    if (logsRes.data.logs && logsRes.data.logs.length > 0) {
      taskLogs.value = logsRes.data.logs
    }

    if (status === 'running' || status === 'queued' || status === 'stopping') {
      setTimeout(pollTaskStatus, 2000)
    } else if (status === 'completed') {
      // 检查是否是无更新的情况
      if (message && message.includes('无更新')) {
        ElMessage.info(message)
      } else {
        ElMessage.success('检查完成')
      }
      // 刷新统计
      fetchStats()
      fetchRecentRecords()
    } else if (status === 'failed') {
      ElMessage.error('检查失败：' + (error || '未知错误'))
    } else if (status === 'stopped') {
      ElMessage.info('任务已被停止')
    }
  } catch (error) {
    console.error('Failed to poll task status:', error)
  }
}

const handleStopTask = async () => {
  if (!taskId.value) return

  try {
    stopping.value = true
    await api.post(`/check/stop/${taskId.value}`)
    ElMessage.info('已发送停止信号，等待任务完成...')
    // 继续轮询直到任务状态变为 stopped
    pollTaskStatus()
  } catch (error) {
    ElMessage.error('停止任务失败：' + (error.response?.data?.message || error.message))
  } finally {
    stopping.value = false
  }
}

const fetchStats = async () => {
  try {
    const [catalogRes, tasksRes, syncRes] = await Promise.all([
      api.get('/catalog/stats'),
      api.get('/tasks/stats'),
      api.get('/history/stats')
    ])
    stats.catalog = catalogRes.data.stats
    stats.tasks = tasksRes.data.stats
    stats.sync = syncRes.data.stats
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

const fetchRecentRecords = async () => {
  loading.value = true
  try {
    const res = await api.get('/history/today')
    recentRecords.value = res.data.records.slice(0, 5)
  } catch (error) {
    console.error('Failed to fetch recent records:', error)
  } finally {
    loading.value = false
  }
}

const refreshStats = () => {
  fetchStats()
  fetchRecentRecords()
  ElMessage.success('统计已刷新')
}

onMounted(() => {
  fetchStats()
  fetchRecentRecords()
})
</script>

<style scoped>
.dashboard h2 {
  margin-bottom: 20px;
  color: #303133;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-icon.catalog {
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.stat-icon.tasks {
  background: linear-gradient(135deg, #f093fb, #f5576c);
}

.stat-icon.sync {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
}

.stat-icon.failed {
  background: linear-gradient(135deg, #fa709a, #fee140);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-actions {
  margin-bottom: 20px;
}

.recent-syncs {
  margin-bottom: 20px;
}

.task-status-dialog .task-status {
  display: flex;
  align-items: flex-start;
  gap: 24px;
  padding: 30px 0 20px;
}

.task-status-dialog .status-icon-wrapper {
  flex-shrink: 0;
}

.task-status-dialog .status-icon-bg {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: all 0.3s ease;
}

.task-status-dialog .icon-bg-default {
  background: linear-gradient(135deg, #909399, #c0c4cc);
}

.task-status-dialog .icon-bg-running {
  background: linear-gradient(135deg, #409EFF, #66b1ff);
  animation: pulse-running 1.5s ease-in-out infinite;
}

.task-status-dialog .icon-bg-completed {
  background: linear-gradient(135deg, #67C23A, #85ce61);
  animation: bounce-in 0.5s ease;
}

.task-status-dialog .icon-bg-failed {
  background: linear-gradient(135deg, #F56C6C, #f78989);
  animation: shake-error 0.5s ease;
}

.task-status-dialog .icon-bg-stopped {
  background: linear-gradient(135deg, #E6A23C, #ebb563);
  animation: bounce-in 0.5s ease;
}

.task-status-dialog .icon-bg-stopping {
  background: linear-gradient(135deg, #909399, #a0a5b0);
  animation: pulse-stopping 1.5s ease-in-out infinite;
}

@keyframes pulse-stopping {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(144, 147, 153, 0.5);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 0 15px rgba(144, 147, 153, 0);
  }
}

@keyframes pulse-running {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.5);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 0 15px rgba(64, 158, 255, 0);
  }
}

@keyframes bounce-in {
  0% {
    transform: scale(0.5);
    opacity: 0;
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes shake-error {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}

.task-status-dialog .status-icon .is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.task-status-dialog .status-text {
  flex: 1;
  padding-top: 8px;
}

.task-status-dialog .status-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 10px;
  transition: color 0.3s ease;
}

.task-status-dialog .status-title-running {
  color: #409EFF;
}

.task-status-dialog .status-title-completed {
  color: #67C23A;
}

.task-status-dialog .status-title-failed {
  color: #F56C6C;
}

.task-status-dialog .status-title-stopped {
  color: #E6A23C;
}

.task-status-dialog .status-title-stopping {
  color: #909399;
}

.task-status-dialog .status-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.6;
}

.task-status-dialog .status-error {
  font-size: 13px;
  color: #F56C6C;
  background: linear-gradient(135deg, #FEF0F0, #fff5f5);
  padding: 10px 14px;
  border-radius: 6px;
  margin-top: 10px;
  border-left: 3px solid #F56C6C;
}

.task-status-dialog .el-progress {
  margin-top: 10px;
}

.task-status-dialog .task-logs {
  margin-top: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: linear-gradient(180deg, #fafafa, #f5f7fa);
  max-height: 300px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.task-status-dialog .log-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #fafafa;
}

.task-status-dialog .log-header .el-icon {
  color: #909399;
}

.task-status-dialog .log-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.8;
}

.task-status-dialog .log-line {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #ebeef5;
  animation: slide-in 0.3s ease;
}

.task-status-dialog .log-line:last-child {
  border-bottom: none;
}

.task-status-dialog .log-index {
  flex-shrink: 0;
  color: #909399;
  font-weight: 600;
  user-select: none;
}

.task-status-dialog .log-text {
  flex: 1;
  color: #303133;
  word-break: break-all;
}

@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.task-status-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 10px;
}
</style>
