<template>
  <div class="settings">
    <h2>系统设置</h2>

    <el-row :gutter="20">
      <!-- 夸克网盘设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span><el-icon><Folder /></el-icon> 夸克网盘设置</span>
              <el-button type="primary" size="small" @click="saveQuarkSettings">
                保存
              </el-button>
            </div>
          </template>

          <el-form :model="quarkSettings" label-width="100px" size="default">
            <el-form-item label="Cookie">
              <el-input
                v-model="quarkSettings.cookie"
                type="password"
                placeholder="请输入夸克网盘 Cookie"
                show-password
              />
            </el-form-item>

            <el-form-item label="自动创建文件夹">
              <el-switch v-model="quarkSettings.auto_create_folder" />
            </el-form-item>

            <el-form-item label="保存文件夹">
              <el-select
                v-model="quarkSettings.save_folders"
                multiple
                allow-create
                filterable
                placeholder="请输入或选择保存文件夹"
                style="width: 100%"
              >
                <el-option label="filmTransfer" value="filmTransfer" />
                <el-option label="filmTransfer_backup" value="filmTransfer_backup" />
                <el-option label="filmTransfer_alt" value="filmTransfer_alt" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 过滤设置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span><el-icon><Filter /></el-icon> 资源过滤设置</span>
              <el-button type="primary" size="small" @click="saveFilterSettings">
                保存
              </el-button>
            </div>
          </template>

          <el-form :model="filterSettings" label-width="100px" size="default">
            <el-form-item label="最低分辨率">
              <el-select v-model="filterSettings.min_resolution" style="width: 100%">
                <el-option label="720p" value="720p" />
                <el-option label="1080p" value="1080p" />
                <el-option label="2160p" value="2160p" />
              </el-select>
            </el-form-item>

            <el-form-item label="最小大小 (GB)">
              <el-input-number v-model="filterSettings.min_size_gb" :min="0" :max="100" />
            </el-form-item>

            <el-form-item label="最大大小 (GB)">
              <el-input-number v-model="filterSettings.max_size_gb" :min="0" :max="200" />
            </el-form-item>

            <el-form-item label="优选编码">
              <el-select
                v-model="filterSettings.preferred_codecs"
                multiple
                placeholder="请选择编码"
                style="width: 100%"
              >
                <el-option label="HEVC" value="HEVC" />
                <el-option label="H265" value="H265" />
                <el-option label="H264" value="H264" />
                <el-option label="AVC" value="AVC" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 通知设置 -->
    <el-card class="notification-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Bell /></el-icon> 通知设置</span>
          <el-button type="primary" size="small" @click="saveNotificationSettings">
                保存
              </el-button>
        </div>
      </template>

      <el-form :model="notificationSettings" label-width="120px" size="default">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="启用通知">
              <el-switch v-model="notificationSettings.enabled" />
            </el-form-item>

            <el-form-item label="通知类型">
              <el-select v-model="notificationSettings.type" style="width: 100%">
                <el-option label="Bark" value="bark" />
                <el-option label="钉钉" value="dingtalk" />
                <el-option label="Telegram" value="telegram" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="Bark Key" v-if="notificationSettings.type === 'bark'">
              <el-input v-model="notificationSettings.bark_key" placeholder="请输入 Bark Key" />
            </el-form-item>

            <el-form-item label="Telegram Bot Token" v-if="notificationSettings.type === 'telegram'">
              <el-input v-model="notificationSettings.telegram_bot_token" placeholder="请输入 Bot Token" />
            </el-form-item>

            <el-form-item label="Telegram Chat ID" v-if="notificationSettings.type === 'telegram'">
              <el-input v-model="notificationSettings.telegram_chat_id" placeholder="请输入 Chat ID" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const quarkSettings = reactive({
  cookie: '',
  auto_create_folder: true,
  save_folders: ['filmTransfer']
})

const filterSettings = reactive({
  min_resolution: '720p',
  min_size_gb: 0.5,
  max_size_gb: 60,
  preferred_codecs: ['HEVC', 'H265', 'H264']
})

const notificationSettings = reactive({
  enabled: false,
  type: 'bark',
  bark_key: '',
  telegram_bot_token: '',
  telegram_chat_id: ''
})

const fetchSettings = async () => {
  try {
    const [quarkRes, filterRes] = await Promise.all([
      api.get('/settings/quark'),
      api.get('/settings/filter')
    ])

    if (quarkRes.data.settings) {
      Object.assign(quarkSettings, quarkRes.data.settings)
    }
    if (filterRes.data.settings) {
      Object.assign(filterSettings, filterRes.data.settings)
    }
  } catch (error) {
    console.error('Failed to fetch settings:', error)
  }
}

const saveQuarkSettings = async () => {
  try {
    await api.put('/settings/quark', quarkSettings)
    ElMessage.success('夸克网盘设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const saveFilterSettings = async () => {
  try {
    await api.put('/settings/filter', filterSettings)
    ElMessage.success('过滤设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const saveNotificationSettings = async () => {
  try {
    await api.put('/settings/notification', notificationSettings)
    ElMessage.success('通知设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
.settings h2 {
  margin-bottom: 20px;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.el-card {
  margin-bottom: 20px;
}

.notification-card {
  margin-top: 20px;
}
</style>
