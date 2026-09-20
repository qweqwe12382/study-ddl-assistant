<template>
    <el-dialog v-model="classDialogVisible" :title="editingClass ? '编辑上课时间' : '添加上课时间'" width="560px" destroy-on-close>
      <el-form label-position="top" class="dialog-form" @submit.prevent="$emit('save-class')">
        <div class="form-grid two-columns">
          <el-form-item label="课程" required>
            <CourseSelect v-model="classForm.course_id" :courses="courses" @created="$emit('add-course', $event)" />
          </el-form-item>
          <el-form-item label="星期" required>
            <el-select v-model="classForm.weekday" style="width: 100%">
              <el-option v-for="day in weekdays" :key="day.value" :label="day.label" :value="day.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="上课时间" required>
            <el-input v-model="classForm.start_time" type="time" />
          </el-form-item>
          <el-form-item label="下课时间" required>
            <el-input v-model="classForm.end_time" type="time" />
          </el-form-item>
          <el-form-item label="教室或地点">
            <el-input v-model="classForm.location" maxlength="120" placeholder="例如：博学楼 B203（可稍后补充）" />
          </el-form-item>
        </div>
        <details class="schedule-options" :open="Boolean(editingClass)">
          <summary>周次与备注 <span>第 {{ classForm.start_week }}–{{ classForm.end_week }} 周 · {{ weekPatternLabel(classForm.week_pattern) }}</span></summary>
          <div class="form-grid two-columns">
          <el-form-item label="开始周" required>
            <el-input-number v-model="classForm.start_week" :min="1" :max="30" style="width: 100%" />
          </el-form-item>
          <el-form-item label="结束周" required>
            <el-input-number v-model="classForm.end_week" :min="1" :max="30" style="width: 100%" />
          </el-form-item>
          <el-form-item label="周次规则" required>
            <el-select v-model="classForm.week_pattern" style="width: 100%">
              <el-option label="每周" value="all" />
              <el-option label="仅单周" value="odd" />
              <el-option label="仅双周" value="even" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="classForm.note" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="实验课、线上会议号等可选信息" />
        </el-form-item>
        </details>
        <div class="dialog-actions">
          <el-button v-if="editingClass" type="danger" plain :loading="deleting" @click="$emit('remove-class', editingClass)">删除这节课</el-button>
          <span class="dialog-actions-spacer"></span>
          <el-button @click="classDialogVisible = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">{{ editingClass ? '保存修改' : '加入课表' }}</el-button>
        </div>
      </el-form>
    </el-dialog>

    <el-dialog v-model="examDialogVisible" :title="editingExam ? '编辑考试' : '添加考试'" width="560px" destroy-on-close>
      <el-form label-position="top" class="dialog-form" @submit.prevent="$emit('save-exam')">
        <div class="form-grid two-columns">
          <el-form-item label="课程" required>
            <CourseSelect v-model="examForm.course_id" :courses="courses" @created="$emit('add-course', $event)" />
          </el-form-item>
          <el-form-item label="考试类型" required>
            <el-select v-model="examForm.exam_type" style="width: 100%">
              <el-option label="随堂测验" value="quiz" />
              <el-option label="期中考试" value="midterm" />
              <el-option label="期末考试" value="final" />
              <el-option label="其他考试" value="other" />
            </el-select>
          </el-form-item>
        </div>
        <div class="form-grid two-columns">
          <el-form-item label="开始时间" required>
            <el-date-picker v-model="examForm.starts_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" placeholder="选择日期和时间" style="width: 100%" />
          </el-form-item>
          <el-form-item label="考场">
            <el-input v-model="examForm.location" maxlength="120" placeholder="例如：第一教学楼 101" />
          </el-form-item>
        </div>
        <details class="schedule-options" :open="Boolean(editingExam)">
          <summary>更多信息 <span>名称、结束时间、座位和备注</span></summary>
          <el-form-item label="考试名称">
            <el-input v-model="examForm.title" maxlength="160" :placeholder="suggestedExamTitle || '默认使用课程名与考试类型'" />
          </el-form-item>
          <div class="form-grid two-columns">
          <el-form-item label="结束时间">
            <el-date-picker v-model="examForm.ends_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" placeholder="可选" style="width: 100%" />
          </el-form-item>
          <el-form-item label="座位号">
            <el-input v-model="examForm.seat_number" maxlength="50" placeholder="例如：A-18" />
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="examForm.note" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="携带物品、考试范围等可选信息" />
        </el-form-item>
        </details>
        <div class="dialog-actions">
          <span class="dialog-actions-spacer"></span>
          <el-button @click="examDialogVisible = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">{{ editingExam ? '保存修改' : '加入考试安排' }}</el-button>
        </div>
      </el-form>
    </el-dialog>

</template>
<script setup>
import { ElButton, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElOption, ElSelect } from 'element-plus'
import CourseSelect from './CourseSelect.vue'
const classDialogVisible = defineModel('classDialogVisible', { type: Boolean, default: false })
const examDialogVisible = defineModel('examDialogVisible', { type: Boolean, default: false })
defineProps({
  classForm: { type: Object, required: true }, examForm: { type: Object, required: true },
  editingClass: { type: Object, default: null }, editingExam: { type: Object, default: null },
  courses: { type: Array, default: () => [] }, weekdays: { type: Array, required: true },
  saving: Boolean, deleting: Boolean, suggestedExamTitle: { type: String, default: '' },
})
defineEmits(['add-course', 'save-class', 'save-exam', 'remove-class'])
function weekPatternLabel(value) { return { all: '每周', odd: '仅单周', even: '仅双周' }[value] || '每周' }
</script>
<style scoped>
.form-grid { display: grid; gap: 0 16px; }
.two-columns { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.dialog-actions { display: flex; align-items: center; gap: 10px; margin-top: 20px; }
.dialog-actions-spacer { flex: 1; }
.schedule-options { margin: 2px 0 18px; border-top: 1px solid var(--ledger-line); }
.schedule-options summary { cursor: pointer; padding: 14px 0; font-size: 13px; }
.schedule-options summary span { margin-left: 8px; color: var(--ledger-muted); }
@media (max-width: 620px) { .two-columns { grid-template-columns: minmax(0, 1fr); } .dialog-actions { flex-wrap: wrap; } }
</style>
