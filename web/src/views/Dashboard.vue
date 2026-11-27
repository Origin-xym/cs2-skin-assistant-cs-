<template>
  <div class="page">
        <header class="page-header">
      <div>
        <h1>CS2 饰品监控面板</h1>
        <p class="subtitle">比价、价格曲线和提醒；下单与支付仍在平台手工完成。</p>
      </div>
      <div class="header-right">
        <el-tag :type="healthTagType" effect="plain">{{ healthText }}</el-tag>
        <div class="health-line">
          <span>Stream {{ health.stream.length }} 条</span>
          <span>Pending {{ health.stream.pending }}</span>
          <span
            v-for="item in health.collectors"
            :key="item.platform"
          >
            {{ item.platform }}：{{ healthAge(item) }}
          </span>
        </div>
      </div>
    </header>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" class="filter-form" @submit.prevent>
        <el-form-item label="饰品">
          <el-input
            v-model="query.mhn"
            style="width: 340px"
            placeholder="market_hash_name"
            clearable
          />
        </el-form-item>
        <el-form-item label="磨损桶">
          <el-select v-model="query.wearBucket" style="width: 130px">
            <el-option
              v-for="item in wearOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="天数">
          <el-input-number
            v-model="query.days"
            :min="1"
            :max="90"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadAll">
            刷新
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="summary-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">近 7 日中位</div>
          <div class="stat-value">¥{{ yuan(compare.baseline.median7d) }}</div>
          <div class="stat-sub">样本 {{ compare.baseline.sampleSize }} 条</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">当前最低</div>
          <div class="stat-value">{{ compare.verdict.best || '-' }}</div>
          <div class="stat-sub">到手 ¥{{ yuan(bestPrice) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平台价差</div>
          <div class="stat-value">{{ pct(compare.verdict.gapPct) }}</div>
          <div class="stat-sub">最低与第二低平台</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">相对基准</div>
          <div class="stat-value">{{ pct(compare.verdict.discountPct) }}</div>
          <div class="stat-sub">
            <el-tag
              size="small"
              :type="compare.verdict.isOpportunity ? 'success' : 'info'"
            >
              {{ compare.verdict.isOpportunity ? '达到规则阈值' : '未达到规则阈值' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never">
          <template #header>平台最低价</template>

          <el-empty
            v-if="compare.platforms.length === 0"
            description="暂无平台报价"
          />

          <el-row v-else :gutter="12">
            <el-col
              v-for="platform in compare.platforms"
              :key="platform.platform"
              :xs="24"
              :sm="12"
            >
              <div
                class="platform-card"
                :class="{ best: compare.verdict.best === platform.platform }"
              >
                <div class="platform-head">
                  <strong>{{ platform.platform }}</strong>
                  <el-tag
                    v-if="compare.verdict.best === platform.platform"
                    type="success"
                    size="small"
                  >
                    最低
                  </el-tag>
                </div>

                <div class="price">¥{{ yuan(platform.netCost) }}</div>
                <div class="muted">标价 ¥{{ yuan(platform.lowestPrice) }}</div>

                <div class="meta">
                  <span>float {{ floatText(platform.floatValue) }}</span>
                  <span>seed {{ text(platform.paintSeed) }}</span>
                </div>

                <div class="tags">
                  <el-tag size="small" :type="platform.hasSticker ? 'warning' : 'info'">
                    {{ platform.hasSticker ? '有印花' : '无印花' }}
                  </el-tag>
                  <el-tag size="small" :type="platform.renamed ? 'danger' : 'info'">
                    {{ platform.renamed ? '改过名' : '未改名' }}
                  </el-tag>
                </div>

                <el-button
                  v-if="platform.deeplink"
                  link
                  type="primary"
                  @click="openLink(platform.deeplink)"
                >
                  打开平台 →
                </el-button>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never">
          <template #header>近 {{ query.days }} 天价格</template>
          <div ref="chartRef" class="chart"></div>
          <div v-if="history.points.length === 0" class="muted center">
            暂无历史数据
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="alerts-card">
      <template #header>
        <div class="card-head">
          <span>最近事件</span>
          <el-button link type="primary" @click="loadAlerts">刷新</el-button>
        </div>
      </template>

      <el-table :data="alerts" stripe>
        <el-table-column prop="createdAt" label="时间" width="180" />
        <el-table-column prop="platform" label="平台" width="100" />
        <el-table-column
          prop="marketHashName"
          label="饰品"
          min-width="220"
          show-overflow-tooltip
        />
        <el-table-column label="标价" width="110">
          <template #default="{ row }">¥{{ yuan(row.priceAmount) }}</template>
        </el-table-column>
        <el-table-column label="基准" width="110">
          <template #default="{ row }">¥{{ yuan(row.baselinePrice) }}</template>
        </el-table-column>
        <el-table-column label="折扣" width="100">
          <template #default="{ row }">{{ pct(row.discountPct) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.deeplink"
              link
              type="primary"
              @click="openLink(row.deeplink)"
            >
              打开
            </el-button>
            <el-button
              v-if="row.status === 'PENDING' || row.status === 'SENT'"
              link
              type="success"
              @click="ack(row)"
            >
              标记已读
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <RulePanel />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { ackAlert, getAlerts, getCompare, getHealth, getHistory } from '../api'
import RulePanel from '../components/RulePanel.vue'

const wearOptions = [
  { value: 1, label: '崭新出厂' },
  { value: 2, label: '略有磨损' },
  { value: 3, label: '久经沙场' },
  { value: 4, label: '破损不堪' },
  { value: 5, label: '战痕累累' }
]

const query = reactive({
  mhn: 'AWP | Asiimov (Field-Tested)',
  wearBucket: 3,
  days: 30
})

const compare = reactive({
  marketHashName: '',
  wearBucket: 3,
  baseline: { median7d: null, sampleSize: 0, unit: 'cent' },
  platforms: [],
  verdict: { best: null, gapPct: null, discountPct: null, isOpportunity: false }
})

const history = reactive({ points: [] })
const alerts = ref([])

const health = reactive({
  status: 'UNKNOWN',
  stream: { key: 'cs2:listings', length: 0, pending: 0, lastEntryAt: null },
  collectors: [],
  checkedAt: null
})
let healthTimer = null

const loading = ref(false)
const chartRef = ref(null)
let chart = null

const bestPrice = computed(() =>
  compare.platforms.length > 0 ? compare.platforms[0].netCost : null
)

const healthText = computed(() => {
  if (health.status === 'UP') return '采集正常'
  if (health.status === 'DEGRADED') return '采集部分异常'
  if (health.status === 'DOWN') return '采集停滞'
  return '采集状态未知'
})

const healthTagType = computed(() => {
  if (health.status === 'UP') return 'success'
  if (health.status === 'DEGRADED') return 'warning'
  if (health.status === 'DOWN') return 'danger'
  return 'info'
})

async function loadAll() {
  loading.value = true
  try {
    const params = {
      mhn: query.mhn.trim(),
      wearBucket: query.wearBucket
    }
    const [compareData, historyData, alertData] = await Promise.all([
      getCompare(params),
      getHistory({ ...params, days: query.days }),
      getAlerts()
    ])

    Object.assign(compare, compareData)
    Object.assign(history, historyData)
    alerts.value = alertData

    await nextTick()
    renderChart()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || '请求失败')
  } finally {
    loading.value = false
  }
}

async function loadHealth() {
  try {
    const data = await getHealth()
    Object.assign(health, data)
  } catch (error) {
    health.status = 'UNKNOWN'
  }
}

async function loadAlerts() {
  try {
    alerts.value = await getAlerts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || '刷新事件失败')
  }
}

function renderChart() {
  if (!chartRef.value) {
    return
  }
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const points = history.points || []
  if (points.length === 0) {
    chart.clear()
    return
  }

  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value) => `¥${Number(value).toFixed(2)}`
      },
      legend: { data: ['每日最低', '每日中位'], top: 0 },
      grid: { left: 48, right: 24, top: 42, bottom: 32 },
      xAxis: {
        type: 'category',
        data: points.map((point) => point.date),
        boundaryGap: false
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (value) => `¥${value}` }
      },
      series: [
        {
          name: '每日最低',
          type: 'line',
          data: points.map((point) => point.minPrice / 100),
          smooth: true,
          symbolSize: 6
        },
        {
          name: '每日中位',
          type: 'line',
          data: points.map((point) => point.medianPrice / 100),
          smooth: true,
          symbolSize: 6
        }
      ]
    },
    true
  )
}

function resizeChart() {
  chart?.resize()
}

function openLink(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function ack(row) {
  try {
    await ackAlert(row.id)
    ElMessage.success('已标记')
    await loadAlerts()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || '标记失败')
  }
}

const yuan = (cents) => (cents == null ? '-' : (cents / 100).toFixed(2))
const pct = (value) => (value == null ? '-' : `${Number(value).toFixed(2)}%`)
const floatText = (value) => (value == null ? '-' : Number(value).toFixed(4))
const text = (value) => (value == null ? '-' : value)
const statusType = (status) =>
  ({ SENT: 'success', PENDING: 'warning', ACK: 'info' }[status] || 'info')

const healthAge = (item) => {
  if (item.status === 'DOWN' || item.ageSeconds == null) return '无心跳'
  const prefix = item.status === 'STALE' ? '停更 ' : ''
  if (item.ageSeconds < 60) return `${prefix}${item.ageSeconds}s 前`
  return `${prefix}${Math.floor(item.ageSeconds / 60)}m 前`
}

onMounted(() => {
  loadAll()
  loadHealth()
  healthTimer = setInterval(loadHealth, 30000)
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  if (healthTimer) {
    clearInterval(healthTimer)
  }
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})
</script>
