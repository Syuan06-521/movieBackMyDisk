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
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="task-status">
        <div class="status-icon">
          <el-icon v-if="taskStatus.status === 'running'" class="is-loading" :size="40"><Loading /></el-icon>
          <el-icon v-else-if="taskStatus.status === 'completed'" :size="40" color="#67C23A"><CircleCheck /></el-icon>
          <el-icon v-else-if="taskStatus.status === 'failed'" :size="40" color="#F56C6C"><CircleClose /></el-icon>
          <el-icon v-else-if="taskStatus.status === 'stopped'" :size="40" color="#E6A23C"><InfoFilled /></el-icon>
          <el-icon v-else :size="40"><InfoFilled /></el-icon>
        </div>
        <div class="status-text">
          <div class="status-title">{{ getStatusTitle(taskStatus.status) }}</div>
          <div class="status-message">{{ taskStatus.message }}</div>
          <div v-if="taskStatus.error" class="status-error">{{ taskStatus.error }}</div>
        </div>
      </div>
      <el-progress v-if="taskStatus.status === 'running'" :percentage="taskStatus.progress" :indeterminate="true" />

      <!-- 执行日志 -->
      <div v-if="taskLogs.length > 0" class="task-logs">
        <div class="log-title">执行日志</div>
        <div class="log-content">
          <div v-for="(log, index) in taskLogs" :key="index" class="log-line">{{ log }}</div>
        </div>
      </div>

      <template #footer>
        <el-button v-if="taskStatus.status === 'running' || taskStatus.status === 'queued'" type="danger" @click="handleStopTask" :loading="stopping">
          <el-icon><VideoPause /></el-icon>
          停止任务
        </el-button>
        <el-button @click="statusDialogVisible = false">关闭</el-button>
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
    completed: '任务已完成',
    failed: '任务失败',
    stopped: '任务已停止'
  }
  return titles[status] || status
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

    if (status === 'running' || status === 'queued') {
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
    }
  } catch (error) {
    console.error('Failed to poll task status:', error)
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

.task-status {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 0;
}

.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-icon .is-loading {
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

.status-text {
  flex: 1;
}

.status-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}

.status-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 4px;
}

.status-error {
  font-size: 13px;
  color: #F56C6C;
  background: #FEF0F0;
  padding: 8px 12px;
  border-radius: 4px;
  margin-top: 8px;
}

.task-logs {
  margin-top: 16px;
  border: 1px solid #EBEEF5;
  border-radius: 4px;
  background: #F5F7FA;
  max-height: 300px;
  overflow-y: auto;
}

.log-title {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  padding: 8px 12px;
  border-bottom: 1px solid #EBEEF5;
  background: #FAFAFA;
}

.log-content {
  padding: 8px 12px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  color: #303133;
  border-bottom: 1px dashed #EBEEF5;
  padding: 4px 0;
}

.log-line:last-child {
  border-bottom: none;
}
</style>
