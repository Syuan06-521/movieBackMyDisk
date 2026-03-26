<template>
  <div class="catalog">
    <div class="page-header">
      <h2>影视目录</h2>
      <el-space>
        <el-input
          v-model="searchQuery"
          placeholder="搜索影视..."
          style="width: 200px"
          clearable
          @clear="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>

        <el-select v-model="filterType" placeholder="类型" style="width: 100px" clearable @change="handleFilter">
          <el-option label="电影" value="movie" />
          <el-option label="剧集" value="series" />
        </el-select>
      </el-space>
    </div>

    <el-card>
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="item_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.item_type === 'movie' ? 'success' : 'warning'" size="small">
              {{ row.item_type === 'movie' ? '电影' : '剧集' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="year" label="年份" width="80" />
        <el-table-column prop="addon_name" label="来源" width="150" />
        <el-table-column prop="first_seen" label="收录时间" width="180" />
        <el-table-column label="操作" width="100" fixed="right">
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
          @size-change="fetchItems"
          @current-change="fetchItems"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="dialogVisible" title="影视详情" width="500px">
      <el-descriptions :column="1" border v-if="selectedItem">
        <el-descriptions-item label="名称">{{ selectedItem.name }}</el-descriptions-item>
        <el-descriptions-item label="类型">
          {{ selectedItem.item_type === 'movie' ? '电影' : '剧集' }}
        </el-descriptions-item>
        <el-descriptions-item label="年份">{{ selectedItem.year || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IMDB">{{ selectedItem.imdb_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ selectedItem.addon_name }}</el-descriptions-item>
        <el-descriptions-item label="收录时间">{{ selectedItem.first_seen }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '@/utils/api'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const filterType = ref('')
const dialogVisible = ref(false)
const selectedItem = ref(null)

const fetchItems = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (filterType.value) params.type = filterType.value
    if (searchQuery.value) params.search = searchQuery.value

    const res = await api.get('/catalog', { params })
    items.value = res.data.items
    total.value = res.data.total
  } catch (error) {
    console.error('Failed to fetch catalog:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchItems()
}

const handleFilter = () => {
  currentPage.value = 1
  fetchItems()
}

const handleView = (row) => {
  selectedItem.value = row
  dialogVisible.value = true
}

onMounted(() => {
  fetchItems()
})
</script>

<style scoped>
.catalog {
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

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
