<template>
  <div class="tasks">
    <div class="page-header">
      <h2>转存任务</h2>
      <el-space>
        <el-select v-model="filterStatus" placeholder="状态" style="width: 120px" clearable @change="fetchTasks">
          <el-option label="待处理" value="pending" />
          <el-option label="搜索中" value="searching" />
          <el-option label="已找到" value="found" />
          <el-option label="保存中" value="saving" />
          <el-option label="已完成" value="done" />
          <el-option label="失败" value="failed" />
          <el-option label="已跳过" value="skipped" />
          <el-option label="待手动" value="pending_manual" />
        </el-select>

        <el-button type="primary" @click="fetchTasks">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>

        <el-button
          v-if="filterStatus === 'pending_manual'"
          type="danger"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>

        <el-dropdown v-if="filterStatus === 'pending_manual'">
          <el-button type="danger">
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleBatchDeleteAll">
                删除所有待手动
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-button
          v-if="filterStatus === 'pending_manual'"
          type="success"
          @click="handleBatchMarkSynced"
        >
          <el-icon><CircleCheck /></el-icon>
          标记为已同步
        </el-button>

        <el-dropdown v-if="filterStatus === 'pending_manual'">
          <el-button type="success">
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleBatchMarkSyncedAll">
                标记所有为已同步
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-button
          v-if="filterStatus === 'failed'"
          type="warning"
          @click="handleBatchRetry"
        >
          <el-icon><RefreshRight /></el-icon>
          批量重试
        </el-button>

        <el-dropdown v-if="filterStatus === 'failed'">
          <el-button type="warning">
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleBatchRetryAll">
                重试所有失败任务
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-space>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="task-stats" v-if="taskStats">
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat">
          <div class="stat-value">{{ taskStats.pending || 0 }}</div>
          <div class="stat-label">待处理</div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat">
          <div class="stat-value">{{ taskStats.searching || 0 }}</div>
          <div class="stat-label">搜索中</div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat">
          <div class="stat-value">{{ taskStats.saving || 0 }}</div>
          <div class="stat-label">保存中</div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat success">
          <div class="stat-value">{{ taskStats.done || 0 }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat danger">
          <div class="stat-value">{{ taskStats.failed || 0 }}</div>
          <div class="stat-label">失败</div>
        </el-card>
      </el-col>
      <el-col :span="3">
        <el-card shadow="hover" class="task-stat warning">
          <div class="stat-value">{{ taskStats.pending_manual || 0 }}</div>
          <div class="stat-label">待手动</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <el-table :data="tasks" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="task_id" label="ID" width="80" />
        <el-table-column prop="catalog_item_id" label="影视 ID" min-width="120" />
        <el-table-column prop="resource_name" label="资源名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resolution" label="分辨率" width="80" />
        <el-table-column prop="size_gb" label="大小 (GB)" width="80" />
        <el-table-column prop="quark_save_path" label="保存路径" min-width="150" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed'"
              type="primary"
              link
              @click="handleRetry(row)"
            >
              重试
            </el-button>
            <el-button type="primary" link @click="handleView(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="dialogVisible" title="任务详情" width="600px">
      <el-descriptions :column="2" border v-if="selectedTask">
        <el-descriptions-item label="任务 ID">{{ selectedTask.task_id }}</el-descriptions-item>
        <el-descriptions-item label="影视 ID">{{ selectedTask.catalog_item_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedTask.status)">
            {{ getStatusText(selectedTask.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="资源名称">{{ selectedTask.resource_name }}</el-descriptions-item>
        <el-descriptions-item label="资源链接" :span="2">
          <el-link :href="selectedTask.resource_url" target="_blank" type="primary">
            {{ selectedTask.resource_url }}
          </el-link>
        </el-descriptions-item>
        <el-descriptions-item label="分辨率">{{ selectedTask.resolution }}</el-descriptions-item>
        <el-descriptions-item label="大小 (GB)">{{ selectedTask.size_gb }}</el-descriptions-item>
        <el-descriptions-item label="编码">{{ selectedTask.codec }}</el-descriptions-item>
        <el-descriptions-item label="保存路径" :span="2">{{ selectedTask.quark_save_path }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2" v-if="selectedTask.error_msg">
          {{ selectedTask.error_msg }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ selectedTask.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ selectedTask.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false)
const tasks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const taskStats = ref(null)
const dialogVisible = ref(false)
const selectedTask = ref(null)
const selectedTasks = ref([])

const getStatusType = (status) => {
  const types = {
    pending: 'info',
    searching: 'warning',
    found: 'primary',
    saving: 'warning',
    done: 'success',
    failed: 'danger',
    skipped: 'info',
    pending_manual: 'warning'
  }
  return types[status] || ''
}

const getStatusText = (status) => {
  const texts = {
    pending: '待处理',
    searching: '搜索中',
    found: '已找到',
    saving: '保存中',
    done: '已完成',
    failed: '失败',
    skipped: '已跳过',
    pending_manual: '待手动'
  }
  return texts[status] || status
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (filterStatus.value) params.status = filterStatus.value

    const [tasksRes, statsRes] = await Promise.all([
      api.get('/tasks', { params }),
      api.get('/tasks/stats')
    ])

    tasks.value = tasksRes.data.tasks
    total.value = tasksRes.data.total
    taskStats.value = statsRes.data.stats
  } catch (error) {
    console.error('Failed to fetch tasks:', error)
  } finally {
    loading.value = false
  }
}

const handleRetry = async (row) => {
  try {
    await api.put(`/tasks/${row.task_id}`, { status: 'pending' })
    ElMessage.success('任务已重新排队')
    fetchTasks()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const handleView = (row) => {
  selectedTask.value = row
  dialogVisible.value = true
}

const handleSelectionChange = (selection) => {
  selectedTasks.value = selection.map(task => task.task_id)
}

const handleBatchDelete = async () => {
  if (selectedTasks.value.length === 0) {
    ElMessage.warning('请选择要删除的任务')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedTasks.value.length} 个任务吗？删除后无法恢复。`,
      '确认删除',
      { type: 'warning' }
    )

    const res = await api.post('/tasks/batch/delete', {
      task_ids: selectedTasks.value
    })

    ElMessage.success(`已删除 ${res.data.deleted_count} 个任务`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

const handleBatchDeleteAll = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除所有待手动任务吗？删除后可以重新执行检查来发现。`,
      '确认删除全部',
      { type: 'warning' }
    )

    const res = await api.post('/tasks/batch/delete', {
      delete_all: true
    })

    ElMessage.success(`已删除 ${res.data.deleted_count} 个任务`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

const handleBatchMarkSynced = async () => {
  if (selectedTasks.value.length === 0) {
    ElMessage.warning('请选择要标记的任务')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要将选中的 ${selectedTasks.value.length} 个任务标记为已同步吗？`,
      '确认标记',
      { type: 'info' }
    )

    const res = await api.post('/tasks/batch/mark-synced', {
      task_ids: selectedTasks.value
    })

    ElMessage.success(`已标记 ${res.data.marked_count} 个任务为已同步`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('标记失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

const handleBatchMarkSyncedAll = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要将所有待手动任务标记为已同步吗？`,
      '确认标记全部',
      { type: 'info' }
    )

    const res = await api.post('/tasks/batch/mark-synced', {
      mark_all: true
    })

    ElMessage.success(`已标记 ${res.data.marked_count} 个任务为已同步`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('标记失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

const handleBatchRetry = async () => {
  if (selectedTasks.value.length === 0) {
    ElMessage.warning('请选择要重试的任务')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要重试选中的 ${selectedTasks.value.length} 个失败任务吗？`,
      '确认重试',
      { type: 'info' }
    )

    const res = await api.post('/tasks/batch/retry', {
      task_ids: selectedTasks.value
    })

    ElMessage.success(`已重试 ${res.data.retried_count} 个任务`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重试失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

const handleBatchRetryAll = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要重试所有失败任务吗？失败任务可能是资源失效导致的，重试可能仍然失败。`,
      '确认重试全部',
      { type: 'warning' }
    )

    const res = await api.post('/tasks/batch/retry', {
      retry_all: true
    })

    ElMessage.success(`已重试 ${res.data.retried_count} 个任务`)
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重试失败：' + (error.response?.data?.message || '未知错误'))
    }
  }
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.tasks {
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.task-stats {
  margin-bottom: 16px;
}

.task-stat {
  text-align: center;
  border-radius: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.task-stat.success .stat-value {
  color: #67c23a;
}

.task-stat.danger .stat-value {
  color: #f56c6c;
}

.task-stat.warning .stat-value {
  color: #e6a23c;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
