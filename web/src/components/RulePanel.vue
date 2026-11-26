<template>
  <el-card shadow="never" class="rules-card">
    <template #header>
      <div class="card-head">
        <span>监控规则</span>
        <el-button type="primary" size="small" @click="openCreate">
          新建规则
        </el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="rules" stripe>
      <el-table-column
        prop="ruleName"
        label="规则"
        min-width="220"
        show-overflow-tooltip
      />
      <el-table-column
        prop="marketHashName"
        label="饰品"
        min-width="230"
        show-overflow-tooltip
      />
      <el-table-column label="磨损桶" width="90">
        <template #default="{ row }">{{ wearLabel(row.wearBucket) }}</template>
      </el-table-column>
      <el-table-column label="最高价" width="110">
        <template #default="{ row }">¥{{ yuan(row.maxPrice) }}</template>
      </el-table-column>
      <el-table-column label="折扣" width="90">
        <template #default="{ row }">{{ pct(row.discountPct) }}</template>
      </el-table-column>
      <el-table-column label="相对闸" width="90">
        <template #default="{ row }">{{ pct(row.relativeGapPct) }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch
            size="small"
            :model-value="row.enabled === 1"
            @change="toggle(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑规则' : '新建规则'"
      width="720px"
      destroy-on-close
    >
      <el-form :model="form" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="规则名">
              <el-input v-model="form.ruleName" maxlength="128" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="磨损桶">
              <el-select v-model="form.wearBucket" style="width: 100%">
                <el-option
                  v-for="item in wearOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="饰品">
          <el-input v-model="form.marketHashName" maxlength="255" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="磨损下限">
              <el-input-number
                v-model="form.floatMin"
                :min="0"
                :max="1"
                :step="0.001"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="磨损上限">
              <el-input-number
                v-model="form.floatMax"
                :min="0"
                :max="1"
                :step="0.001"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="最高价（元）">
              <el-input-number
                v-model="form.maxPriceYuan"
                :min="0"
                :step="10"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="折扣阈值">
              <el-input-number
                v-model="form.discountPct"
                :min="0"
                :max="100"
                :step="0.5"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="相对闸">
              <el-input-number
                v-model="form.relativeGapPct"
                :min="0"
                :max="100"
                :step="0.5"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="冷却（秒）">
              <el-input-number
                v-model="form.cooldownSec"
                :min="0"
                :step="60"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="每日上限">
              <el-input-number
                v-model="form.dailyLimit"
                :min="0"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最少样本">
              <el-input-number
                v-model="form.minSample"
                :min="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="合并窗口">
              <el-input-number
                v-model="form.mergeWindowSec"
                :min="0"
                :step="30"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch
                v-model="form.enabled"
                :active-value="1"
                :inactive-value="0"
                active-text="启用"
                inactive-text="停用"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="过滤 JSON">
          <el-input
            v-model="form.filterJson"
            type="textarea"
            :rows="3"
            placeholder='{"exclude_keywords":["改名","刮印花","租","押金"]}'
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          保存
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createRule, getRules, toggleRule, updateRule } from '../api'

const wearOptions = [
  { value: 1, label: '崭新出厂' },
  { value: 2, label: '略有磨损' },
  { value: 3, label: '久经沙场' },
  { value: 4, label: '破损不堪' },
  { value: 5, label: '战痕累累' }
]

const rules = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)

const form = reactive({
  id: null,
  ruleName: '',
  marketHashName: 'AWP | Asiimov (Field-Tested)',
  wearBucket: 3,
  floatMin: 0.15,
  floatMax: 0.38,
  maxPriceYuan: 780,
  discountPct: 8,
  relativeGapPct: 3,
  filterJson: '{"exclude_keywords":["改名","刮印花","租","押金"]}',
  cooldownSec: 600,
  dailyLimit: 20,
  minSample: 30,
  mergeWindowSec: 120,
  enabled: 1
})

function defaultForm() {
  return {
    id: null,
    ruleName: '',
    marketHashName: 'AWP | Asiimov (Field-Tested)',
    wearBucket: 3,
    floatMin: 0.15,
    floatMax: 0.38,
    maxPriceYuan: 780,
    discountPct: 8,
    relativeGapPct: 3,
    filterJson: '{"exclude_keywords":["改名","刮印花","租","押金"]}',
    cooldownSec: 600,
    dailyLimit: 20,
    minSample: 30,
    mergeWindowSec: 120,
    enabled: 1
  }
}

async function loadRules() {
  loading.value = true
  try {
    rules.value = await getRules()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || '加载规则失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    ruleName: row.ruleName || '',
    marketHashName: row.marketHashName || '',
    wearBucket: row.wearBucket ?? 3,
    floatMin: row.floatMin ?? 0,
    floatMax: row.floatMax ?? 1,
    maxPriceYuan: row.maxPrice == null ? 0 : Number(row.maxPrice) / 100,
    discountPct: row.discountPct ?? 8,
    relativeGapPct: row.relativeGapPct ?? 3,
    filterJson: row.filterJson || '{}',
    cooldownSec: row.cooldownSec ?? 600,
    dailyLimit: row.dailyLimit ?? 20,
    minSample: row.minSample ?? 30,
    mergeWindowSec: row.mergeWindowSec ?? 120,
    enabled: row.enabled ?? 1
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.ruleName.trim() || !form.marketHashName.trim()) {
    ElMessage.warning('规则名和饰品名不能为空')
    return
  }

  let filter
  try {
    filter = JSON.parse(form.filterJson || '{}')
  } catch (error) {
    ElMessage.error('过滤 JSON 不是合法 JSON')
    return
  }
  if (filter === null || typeof filter !== 'object' || Array.isArray(filter)) {
    ElMessage.error('过滤 JSON 必须是对象')
    return
  }

  const payload = {
    ruleName: form.ruleName.trim(),
    marketHashName: form.marketHashName.trim(),
    wearBucket: form.wearBucket,
    floatMin: form.floatMin,
    floatMax: form.floatMax,
    maxPrice: form.maxPriceYuan > 0 ? Math.round(form.maxPriceYuan * 100) : null,
    discountPct: form.discountPct,
    relativeGapPct: form.relativeGapPct,
    filterJson: JSON.stringify(filter),
    cooldownSec: form.cooldownSec,
    dailyLimit: form.dailyLimit,
    minSample: form.minSample,
    mergeWindowSec: form.mergeWindowSec,
    enabled: form.enabled
  }

  saving.value = true
  try {
    if (form.id) {
      await updateRule(form.id, payload)
    } else {
      await createRule(payload)
    }
    ElMessage.success(form.id ? '规则已更新' : '规则已创建')
    dialogVisible.value = false
    await loadRules()
  } catch (error) {
    const detail = error?.response?.data?.message || error?.response?.data?.error
    ElMessage.error(
      detail ||
        (error?.response?.status === 409 ? '规则名已存在' : '保存失败')
    )
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  try {
    await toggleRule(row.id)
    ElMessage.success(row.enabled === 1 ? '规则已停用' : '规则已启用')
    await loadRules()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error.message || '切换失败')
  }
}

const yuan = (cents) =>
  cents == null ? '-' : (Number(cents) / 100).toFixed(2)
const pct = (value) =>
  value == null ? '-' : `${Number(value).toFixed(2)}%`
const wearLabel = (value) =>
  wearOptions.find((item) => item.value === value)?.label || '-'

onMounted(loadRules)
</script>

<style scoped>
.rules-card {
  margin-top: 16px;
}
</style>
