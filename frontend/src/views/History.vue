<template>
  <div class="history">
    <div class="page-header">
      <h2>同步历史</h2>
      <el-space>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 240px"
          @change="resetPage"
        />

        <el-select v-model="filterStatus" placeholder="状态" style="width: 100px" clearable @change="resetPage">
          <el-option label="已保存" value="saved" />
          <el-option label="失败" value="failed" />
          <el-option label="跳过" value="skipped" />
          <el-option label="待手动" value="pending_manual" />
        </el-select>

        <el-button type="primary" @click="fetchHistory">
          <el-icon><Search /></el-icon>
          查询
        </el-button>

        <el-button @click="handleExport">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </el-space>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="history-stats" v-if="stats">
      <el-col :span="4">
        <el-card shadow="hover" class="history-stat">
          <div class="stat-value">{{ stats.today_synced || 0 }}</div>
          <div class="stat-label">今日同步</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="history-stat success">
          <div class="stat-value">{{ stats.today_saved || 0 }}</div>
          <div class="stat-label">今日保存</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="history-stat warning">
          <div class="stat-value">{{ stats.today_skipped || 0 }}</div>
          <div class="stat-label">今日跳过</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="history-stat danger">
          <div class="stat-value">{{ stats.today_failed || 0 }}</div>
          <div class="stat-label">今日失败</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="history-stat info">
          <div class="stat-value">{{ stats.today_pending_manual || 0 }}</div>
          <div class="stat-label">待手动处理</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <el-table :data="records" v-loading="loading" style="width: 100%">
        <el-table-column prop="item_name" label="影视名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类型" width="70">
          <template #default="{ row }">
            <el-tag :type="row.item_type === 'movie' ? 'success' : 'warning'" size="small">
              {{ row.item_type === 'movie' ? '电影' : '剧集' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_title" label="资源标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resolution" label="分辨率" width="70" />
        <el-table-column prop="size_gb" label="大小 (GB)" width="70" />
        <el-table-column prop="save_path" label="保存路径" min-width="150" show-overflow-tooltip />
        <el-table-column prop="sync_time" label="同步时间" width="170" />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
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
          @size-change="fetchHistory"
          @current-change="fetchHistory"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="dialogVisible" title="同步详情" width="700px">
      <el-descriptions :column="2" border v-if="selectedRecord">
        <el-descriptions-item label="影视名称">{{ selectedRecord.item_name }}</el-descriptions-item>
        <el-descriptions-item label="类型">
          {{ selectedRecord.item_type === 'movie' ? '电影' : '剧集' }}
        </el-descriptions-item>
        <el-descriptions-item label="资源标题" :span="2">{{ selectedRecord.resource_title }}</el-descriptions-item>
        <el-descriptions-item label="资源链接" :span="2">
          <el-link :href="selectedRecord.resource_url" target="_blank" type="primary">
            {{ selectedRecord.resource_url }}
          </el-link>
        </el-descriptions-item>
        <el-descriptions-item label="分辨率">{{ selectedRecord.resolution }}</el-descriptions-item>
        <el-descriptions-item label="大小 (GB)">{{ selectedRecord.size_gb }}</el-descriptions-item>
        <el-descriptions-item label="编码">{{ selectedRecord.codec }}</el-descriptions-item>
        <el-descriptions-item label="保存路径" :span="2">{{ selectedRecord.save_path }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedRecord.status)">
            {{ getStatusText(selectedRecord.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="同步时间">{{ selectedRecord.sync_time }}</el-descriptions-item>
        <el-descriptions-item label="失败原因" :span="2" v-if="selectedRecord.error_reason">
          <el-text type="danger">{{ selectedRecord.error_reason }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="尝试路径" :span="2" v-if="selectedRecord.attempted_paths && selectedRecord.attempted_paths.length > 0">
          <el-tag v-for="(path, index) in selectedRecord.attempted_paths" :key="index" size="small" style="margin-right: 8px;">
            {{ path }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="尝试资源" :span="2" v-if="selectedRecord.tried_resources && selectedRecord.tried_resources.length > 0">
          <div v-for="(resource, index) in selectedRecord.tried_resources" :key="index" style="margin-bottom: 8px;">
            <el-link :href="resource.url" target="_blank" type="primary" :underline="false">
              #{{ index + 1 }}. {{ resource.title?.substring(0, 50) || '未知标题' }}
            </el-link>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false)
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const dateRange = ref([])
const filterStatus = ref('')
const stats = ref(null)
const dialogVisible = ref(false)
const selectedRecord = ref(null)

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
    skipped: '已跳过',
    pending_manual: '待手动'
  }
  return texts[status] || status
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    } else {
      // 默认最近 7 天
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - 7)
      params.start_date = start.toISOString().split('T')[0]
      params.end_date = end.toISOString().split('T')[0]
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }

    // 并行请求，添加超时处理
    const [recordsRes, statsRes] = await Promise.all([
      api.get('/history', { params }),
      api.get('/history/stats')
    ])

    records.value = recordsRes.data.records
    total.value = recordsRes.data.total
    stats.value = statsRes.data.stats
  } catch (error) {
    console.error('Failed to fetch history:', error)
    ElMessage.error('加载同步历史失败：' + (error.message || '未知错误'))
    records.value = []
    total.value = 0
    stats.value = null
  } finally {
    loading.value = false
  }
}

const handleExport = () => {
  window.open('/api/history/export', '_blank')
}

const handleView = (row) => {
  selectedRecord.value = row
  dialogVisible.value = true
}

// 筛选条件改变时重置页码
const resetPage = () => {
  currentPage.value = 1
  fetchHistory()
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.history {
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

.history-stats {
  margin-bottom: 16px;
}

.history-stat {
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

.history-stat.success .stat-value {
  color: #67c23a;
}

.history-stat.danger .stat-value {
  color: #f56c6c;
}

.history-stat.warning .stat-value {
  color: #e6a23c;
}

.history-stat.info .stat-value {
  color: #909399;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
