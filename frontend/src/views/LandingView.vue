<template>
  <div class="landing-page">
    <a class="public-skip" href="#landing-main">跳到主要内容</a>
    <header class="landing-nav">
      <router-link class="landing-brand" to="/" aria-label="学伴管家首页">
        <BrandMark /><span
          ><strong>学伴管家</strong><small>STUDY, WITH CLARITY.</small></span
        >
      </router-link>
      <nav class="landing-links" aria-label="首页导航">
        <a href="#study-preview">学习日常</a><a href="#workflow">怎么使用</a
        ><a href="#deadline-example">通知改期</a
        ><a href="#workspace">全部功能</a>
      </nav>
      <div class="landing-account">
        <router-link
          v-if="authSession.user"
          class="button button-primary"
          to="/app"
          >进入学习空间<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 12h14m-5-5 5 5-5 5" /></svg
        ></router-link>
        <template v-else
          ><router-link class="text-link" to="/login">登录</router-link
          ><router-link class="button button-primary" to="/register"
            >建立学习空间<svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12h14m-5-5 5 5-5 5" /></svg></router-link
        ></template>
      </div>
    </header>
    <main id="landing-main" tabindex="-1">
      <section class="hero-section" aria-labelledby="hero-title">
        <div class="hero-copy">
          <h1 id="hero-title">
            让学习有序，<br />让行动<span class="hero-emphasis"
              >清晰<svg viewBox="0 0 220 22" aria-hidden="true">
                <path
                  pathLength="1"
                  d="M5 15Q97 2 214 9M24 21Q118 11 184 17"
                /></svg></span
            >。
          </h1>
          <p class="hero-lead">
            把分散的资料、变化的截止、待完成的计划，<br
              class="desktop-break"
            />收进一个清晰的学习空间。<br />从容一点，从今天的下一步开始。
          </p>
          <div class="hero-actions">
            <router-link
              class="button button-primary"
              :to="authSession.user ? '/app' : '/register'"
              >{{ authSession.user ? "打开今天的安排" : "建立学习空间"
              }}<svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14m-5-5 5 5-5 5" /></svg
            ></router-link>
            <a
              v-if="authSession.user"
              class="button button-secondary"
              href="#study-preview"
              >探索学习日常</a
            >
            <button
              v-else
              class="button button-secondary"
              type="button"
              :disabled="demoLoading"
              @click="startDemo"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m9 6 9 6-9 6Z" /></svg
              >{{ demoLoading ? "正在准备演示…" : "体验示例空间" }}
            </button>
          </div>
          <p v-if="demoError" class="demo-error" role="alert">
            {{ demoError }}
          </p>
          <p v-else-if="!authSession.user" class="hero-hint">
            演示无需注册，使用示例数据，仅本地开发环境提供。
          </p>
          <p v-else class="hero-hint">
            {{
              authSession.user.display_name
            }}，欢迎回来。今天也按自己的节奏来。
          </p>
          <a class="hero-explore" href="#study-preview"
            ><span
              ><svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 4v16m-5-5 5 5 5-5" /></svg></span
            >向下，翻开有序的一天</a
          >
        </div>
        <figure class="hero-art">
          <picture
            ><source media="(max-width: 760px)" :srcset="studySculptureSmall" />
            <img
              :src="studySculpture"
              width="1536"
              height="1024"
              alt="展开的墨绿色笔记本，书页叠成拱门与阶梯，黄铜书签穿行其间"
              fetchpriority="high"
              decoding="async"
          /></picture>
          <div class="art-note art-note-top" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M4 5h16v16H4ZM4 10h16M8 3v5M16 3v5m-8 7 3 3 5-6" /></svg
            ><span>把截止记下<small>为行动留出余地</small></span>
          </div>
          <div class="art-note art-note-bottom" aria-hidden="true">
            <span class="note-check"
              ><svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg></span
            ><span>把一件小事完成<small>让每一步，都算数</small></span>
          </div>
          <figcaption>
            <span class="caption-line"></span>一页一页，找到自己的节奏。
          </figcaption>
        </figure>
      </section>
      <div class="learning-ribbon" aria-label="学习空间的日常用途">
        <span
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 6h7l2 3h9v11H3ZM3 6V4h7l2 2h7v3" /></svg
          >资料，有处安放</span
        >
        <span
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 5h16v16H4ZM4 10h16M8 3v5M16 3v5M8 15h3M14 15h2" /></svg
          >截止，心中有数</span
        >
        <span
          ><svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3a9 9 0 1 0 9 9M9 10l3 3L21 4" /></svg
          >行动，步步清晰</span
        >
      </div>
      <section
        id="study-preview"
        class="preview-section section-wrap"
        aria-labelledby="preview-title"
      >
        <div class="preview-copy">
          <h2 id="preview-title">今天的下一步，<br />一眼就清楚。</h2>
          <p class="section-intro">
            不用在消息、文件和待办之间来回寻找。<br />把要做的事放在眼前，给专注留出空间。
          </p>
          <ul class="preview-benefits">
            <li>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m5 12 4 4L19 6" />
              </svg>
              <div>
                <strong>先看清今天，再安排一周</strong>
                <p>课程、任务与复习，放回自己的学习节奏。</p>
              </div>
            </li>
            <li>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m5 12 4 4L19 6" />
              </svg>
              <div>
                <strong>完成一件，就轻松一点</strong>
                <p>划掉待办，看到每一个小小的进展。</p>
              </div>
            </li>
          </ul>
          <a class="inline-link preview-invitation" href="#notebook-example"
            >试着勾选一项，感受一下<svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12h14m-5-5 5 5-5 5" /></svg
          ></a>
          <div class="preview-margin-note" aria-hidden="true">
            <svg viewBox="0 0 110 60">
              <path
                d="M4 8C30 8 25 45 65 40s32-31 39-28M88 10l16 2-3 16"
              /></svg
            ><span>小步，也在向前。</span>
          </div>
        </div>
        <section
          id="notebook-example"
          class="study-scene"
          aria-label="可交互的学习安排示例"
        >
          <div v-folio-enter class="study-notebook">
            <div class="notebook-heading">
              <span class="preview-brand"><BrandMark />学习空间</span
              ><span class="example-tag">交互示例</span>
            </div>
            <div class="notebook-tabs" role="group" aria-label="切换学习场景">
              <button
                v-for="(scene, key) in studyScenes"
                :key="key"
                type="button"
                :aria-pressed="studyMode === key"
                @click="studyMode = key"
              >
                {{ scene.label }}
              </button>
            </div>
            <div class="notebook-date">
              <div>
                <p>{{ studyScene.context }}</p>
                <h3>{{ studyScene.title }}</h3>
              </div>
              <span class="preview-count" aria-hidden="true"
                >{{ String(studyScene.tasks.length).padStart(2, "0")
                }}<small>项安排</small></span
              >
            </div>
            <Transition name="page-turn" mode="out-in"
              ><div :key="studyMode" class="notebook-content">
                <div class="mini-week" aria-hidden="true">
                  <span
                    v-for="(day, index) in weekDays"
                    :key="day"
                    :class="{
                      'is-today': index === (studyMode === 'today' ? 2 : 4),
                    }"
                    ><small>{{ day }}</small
                    ><b>{{ 14 + index }}</b
                    ><i></i
                  ></span>
                </div>
                <div>
                  <label
                    v-for="task in studyScene.tasks"
                    :key="task.id"
                    class="preview-task"
                    :class="{ 'is-done': completedTasks.includes(task.id) }"
                    ><input
                      v-model="completedTasks"
                      type="checkbox"
                      :value="task.id"
                    /><span class="task-check" aria-hidden="true"
                      ><svg viewBox="0 0 16 16">
                        <path d="m3 8 3 3 7-7" /></svg></span
                    ><span class="task-content"
                      ><strong>{{ task.name }}</strong
                      ><small>{{ task.course }}</small></span
                    ><span class="task-time">{{ task.time }}</span></label
                  >
                </div>
              </div></Transition
            >
            <div class="notebook-progress">
              <span aria-live="polite">{{
                completedCount === studyScene.tasks.length
                  ? "本组任务已完成"
                  : `已完成 ${completedCount} / ${studyScene.tasks.length} 项`
              }}</span
              ><span>按自己的节奏</span>
            </div>
            <div
              class="progress-track"
              role="progressbar"
              :aria-valuenow="completedCount"
              :aria-valuemax="studyScene.tasks.length"
              :aria-valuemin="0"
              aria-label="示例任务完成进度"
            >
              <span
                :style="{
                  transform: `scaleX(${completedCount / studyScene.tasks.length})`,
                }"
              ></span>
            </div>
          </div>
          <p class="scene-caption">
            可切换场景、勾选任务。示例变化不会保存到学习空间。
          </p>
        </section>
      </section>
      <section
        id="workflow"
        class="workflow-section section-wrap"
        aria-labelledby="workflow-title"
      >
        <div class="section-heading">
          <h2 id="workflow-title">从一条通知，<br />到一次认真投入。</h2>
          <p>
            让零散的信息，有清晰的去向。<br />收集、确认、执行，三步接上学习日常。
          </p>
        </div>
        <div class="workflow-stage">
          <ol class="workflow-steps" aria-label="查看使用流程">
            <li v-for="(step, index) in workflowSteps" :key="step.key">
              <button
                type="button"
                :aria-pressed="workflowMode === step.key"
                aria-controls="workflow-preview"
                @click="workflowMode = step.key"
              >
                <span class="step-number">{{
                  String(index + 1).padStart(2, "0")
                }}</span
                ><span
                  ><strong>{{ step.title }}</strong
                  ><small>{{ step.description }}</small></span
                ><svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 12h14m-5-5 5 5-5 5" />
                </svg>
              </button>
            </li>
          </ol>
          <div
            id="workflow-preview"
            class="workflow-preview"
            :class="'workflow-' + workflowMode"
            aria-live="polite"
            aria-atomic="true"
          >
            <span class="workflow-example-label">流程示例</span>
            <Transition name="page-turn" mode="out-in">
              <div :key="workflowMode" class="workflow-panel">
                <div
                  v-if="workflowMode === 'collect'"
                  class="collect-visual"
                  aria-hidden="true"
                >
                  <div class="source-file source-file-back">
                    <svg viewBox="0 0 24 24">
                      <path d="M5 3h9l5 5v13H5ZM14 3v6h5M8 13h8M8 17h5" /></svg
                    ><span>实验报告.pdf</span><small>文档资料</small>
                  </div>
                  <div class="source-file source-file-front">
                    <span class="file-heading"><i></i>课程群通知</span
                    ><strong>数据结构 · 实验报告</strong>
                    <p>请于 9 月 20 日 23:59 前<br />提交本次实验报告。</p>
                    <div class="file-rule"></div>
                    <small>原文与资料，一起收好。</small>
                  </div>
                  <div class="file-format-strip">
                    <span>PDF</span><span>图片</span><span>通知原文</span>
                  </div>
                </div>
                <div
                  v-else-if="workflowMode === 'confirm'"
                  class="confirm-visual"
                  aria-hidden="true"
                >
                  <div class="confirm-calendar">
                    <span>SEPTEMBER</span><strong>20</strong
                    ><small>23:59 截止</small><i></i><i></i>
                  </div>
                  <div class="confirm-record">
                    <span>待确认的任务</span><strong>完成实验报告</strong>
                    <p>课程 <b>数据结构</b></p>
                    <p>依据 <b>课程群通知</b></p>
                    <div>
                      <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg
                      >核对后，再保存
                    </div>
                  </div>
                </div>
                <div v-else class="focus-visual" aria-hidden="true">
                  <div class="focus-orbit">
                    <svg viewBox="0 0 220 220">
                      <circle cx="110" cy="110" r="101" />
                      <circle class="timer-arc" cx="110" cy="110" r="101" />
                    </svg>
                    <div>
                      <span>留一段时间给自己</span><strong>25:00</strong
                      ><small>一次，只做一件事</small>
                    </div>
                  </div>
                  <div class="focus-note">
                    <span>这次专注</span><strong>整理课堂笔记</strong
                    ><small>高等数学 · 示例</small>
                  </div>
                </div>
                <div class="workflow-panel-copy">
                  <p>{{ workflowStep.detail }}</p>
                  <router-link class="inline-link" :to="workflowStep.path"
                    >{{ workflowStep.link
                    }}<svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M5 12h14m-5-5 5 5-5 5" /></svg
                  ></router-link>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </section>
      <section
        id="deadline-example"
        class="deadline-section"
        aria-labelledby="deadline-title"
      >
        <div class="deadline-inner section-wrap">
          <div class="deadline-copy">
            <div class="deadline-symbol" aria-hidden="true">
              <svg viewBox="0 0 32 32">
                <path
                  d="M6 10h20v17H6zM6 15h20M11 6v7M21 6v7M11 21h6m-3-3 3 3-3 3"
                />
              </svg>
            </div>
            <h2 id="deadline-title">计划会变，<br />从容可以不变。</h2>
            <p>
              老师发来改期通知？<br />让 DDL 应变台帮你看清时间变化，<br />再决定，怎样安排接下来的学习。
            </p>
            <div class="deadline-principle">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Zm-4 9 3 3 5-6"
                /></svg
              ><span>保留原文依据，确认后再更新。</span>
            </div>
            <router-link class="inline-link" to="/deadline-radar"
              >进入 DDL 应变台<svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14m-5-5 5 5-5 5" /></svg
            ></router-link>
          </div>
          <section class="notice-example" aria-labelledby="example-title">
            <div class="example-topline">
              <h3 id="example-title">数据结构 · 实验报告</h3>
              <span class="example-tag">交互示例</span>
            </div>
            <div class="example-switch" role="group" aria-label="选择通知示例">
              <button
                type="button"
                :aria-pressed="exampleMode === 'earlier'"
                @click="exampleMode = 'earlier'"
              >
                截止提前
              </button>
              <button
                type="button"
                :aria-pressed="exampleMode === 'later'"
                @click="exampleMode = 'later'"
              >
                截止延期
              </button>
            </div>
            <div class="example-result" aria-live="polite" aria-atomic="true">
              <Transition name="notice-change" mode="out-in"
                ><div :key="exampleMode">
                  <div class="notice-source">
                    <span class="source-label">课程群通知 · 示例</span>
                    <blockquote>{{ example.notice }}</blockquote>
                  </div>
                  <div class="deadline-change">
                    <div>
                      <span>原截止时间</span><strong>9 月 20 日</strong
                      ><small>23:59</small>
                    </div>
                    <svg
                      class="change-arrow"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path d="M4 12h16m-6-6 6 6-6 6" />
                    </svg>
                    <div class="proposed-date">
                      <span>{{ example.label }}</span
                      ><strong>{{ example.date }}</strong
                      ><small>{{ example.time }}</small>
                    </div>
                  </div>
                  <p class="example-explanation">{{ example.explanation }}</p>
                </div></Transition
              >
            </div>
            <div class="deadline-timeline" aria-hidden="true">
              <div class="timeline-rail"></div>
              <div
                class="timeline-window"
                :class="{ 'is-later': exampleMode === 'later' }"
              ></div>
              <span
                v-for="day in [16, 18, 20, 22, 24]"
                :key="day"
                :class="{
                  'is-proposed': day === (exampleMode === 'earlier' ? 18 : 22),
                  'is-original': day === 20,
                }"
                ><i></i>{{ day }} 日</span
              >
            </div>
            <p class="example-boundary">
              仅作说明，不会修改任务。实际影响需进入应变台查看。
            </p>
          </section>
        </div>
      </section>
      <section
        id="workspace"
        class="workspace-section section-wrap"
        aria-labelledby="workspace-title"
      >
        <div class="section-heading">
          <h2 id="workspace-title">为整个学期，<br />也为每一个今天。</h2>
          <p>
            从第一份资料，到最后一轮复习。<br />在同一个空间，照顾学习的不同需要。
          </p>
        </div>
        <nav class="workspace-links" aria-label="学习空间全部功能">
          <router-link
            v-for="entry in workspaceEntries"
            :key="entry.path"
            :to="entry.path"
            ><span class="entry-icon" :class="entry.tone" aria-hidden="true"
              ><svg viewBox="0 0 24 24"><path :d="entry.icon" /></svg></span
            ><span
              ><strong>{{ entry.label }}</strong
              ><small>{{ entry.description }}</small></span
            ><svg class="entry-arrow" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 19 19 5M6 5h13v13" /></svg
          ></router-link>
        </nav>
      </section>
      <section class="closing-section" aria-labelledby="closing-title">
        <div class="closing-inner section-wrap">
          <div>
            <h2 id="closing-title">把精力，<br />留给真正的学习。</h2>
            <p>整理好今天，安心向前。</p>
            <router-link
              class="button button-primary"
              :to="authSession.user ? '/app' : '/register'"
              >{{ authSession.user ? "打开学习空间" : "建立学习空间"
              }}<svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14m-5-5 5 5-5 5" /></svg
            ></router-link>
          </div>
          <div class="closing-art" aria-hidden="true">
            <span class="closing-word">Make<br /><em>room.</em></span
            ><svg class="closing-book" viewBox="0 0 350 200">
              <path
                d="M25 45Q107 15 173 57Q242 17 325 43L317 153Q238 139 175 174Q106 139 32 155ZM173 57l2 117M25 57l-9 108q84-17 159 23 71-34 150-20l10-113M43 66q67-18 111 11M42 85q64-17 111 10M41 105q64-14 111 7M40 124q63-11 111 7M195 75q49-23 110-15M195 94q48-22 108-15M195 113q45-20 105-16M196 132q43-18 104-16"
              />
              <path class="book-ribbon" d="M239 41v100l13-10 11 8 3-102" />
            </svg>
          </div>
        </div>
      </section>
    </main>
    <footer class="landing-footer section-wrap">
      <div class="footer-top">
        <router-link class="landing-brand" to="/" aria-label="学伴管家首页"
          ><BrandMark /><strong>学伴管家</strong></router-link
        >
        <p>学习安排，由你做主。</p>
        <a href="#landing-main"
          >回到顶部<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 20V4m-6 6 6-6 6 6" /></svg
        ></a>
      </div>
      <div class="footer-bottom">
        <span>为认真学习的每一天。</span><span>本地开发版本</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { authSession, demoLogin } from "../auth/session";
import studySculpture from "../assets/decor/study-sculpture-v2.webp";
import studySculptureSmall from "../assets/decor/study-sculpture-v2-small.webp";
import BrandMark from "../components/BrandMark.vue";
import { vFolioEnter } from "../directives/folioEnter";

const router = useRouter();
const demoLoading = ref(false);
const demoError = ref("");
const studyMode = ref("today");
const completedTasks = ref(["notes"]);
const weekDays = ["一", "二", "三", "四", "五", "六", "日"];
const studyScenes = {
  today: {
    label: "今天的安排",
    context: "九月 · 学期安排示例",
    title: "今天，从这三件事开始",
    tasks: [
      {
        id: "notes",
        name: "整理课堂笔记",
        course: "高等数学",
        time: "15 分钟",
      },
      {
        id: "report",
        name: "完成实验报告",
        course: "数据结构",
        time: "周五截止",
      },
      {
        id: "words",
        name: "复习一个单元",
        course: "大学英语",
        time: "25 分钟",
      },
    ],
  },
  exam: {
    label: "考前一周",
    context: "考前复习 · 分阶段推进",
    title: "重点、练习、回顾",
    tasks: [
      {
        id: "chapters",
        name: "梳理章节知识点",
        course: "高等数学 · 第一步",
        time: "今天",
      },
      {
        id: "exercises",
        name: "重做典型错题",
        course: "高等数学 · 第二步",
        time: "明天",
      },
      {
        id: "review",
        name: "回顾重点与公式",
        course: "高等数学 · 第三步",
        time: "考前",
      },
    ],
  },
};
const studyScene = computed(() => studyScenes[studyMode.value]);
const completedCount = computed(
  () =>
    studyScene.value.tasks.filter((task) =>
      completedTasks.value.includes(task.id),
    ).length,
);
const workflowMode = ref("collect");
const workflowSteps = [
  {
    key: "collect",
    title: "把资料，收在一起",
    description: "文档、图片、课程通知，都有归处。",
    detail: "上传文档或图片，也可以直接粘贴通知原文。",
    path: "/materials",
    link: "进入资料库",
  },
  {
    key: "confirm",
    title: "把安排，确认清楚",
    description: "对照原文，把任务与截止逐一核对。",
    detail: "课程、任务、截止时间均可修改，确认后再保存。",
    path: "/tasks",
    link: "查看截止任务",
  },
  {
    key: "focus",
    title: "把时间，留给专注",
    description: "拆好复习步骤，一次只做一件事。",
    detail: "把复习拆成小步，用专注计时记录真实投入。",
    path: "/focus",
    link: "开启专注计时",
  },
];
const workflowStep = computed(() =>
  workflowSteps.find((step) => step.key === workflowMode.value),
);
const exampleMode = ref("earlier");
const examples = {
  earlier: {
    notice:
      "数据结构实验报告提交时间提前至 9 月 18 日 20:00，请同学们重新安排。",
    label: "提前后的截止",
    date: "9 月 18 日",
    time: "20:00",
    explanation: "提交时间提前，先为报告留出时间。",
  },
  later: {
    notice: "数据结构实验报告提交时间延期至 9 月 22 日 23:59，其他要求不变。",
    label: "延期后的截止",
    date: "9 月 22 日",
    time: "23:59",
    explanation: "多出两天，可以重新调整学习安排。",
  },
};
const example = computed(() => examples[exampleMode.value]);
const workspaceEntries = [
  {
    path: "/app",
    label: "学习总览",
    description: "看清今天的下一步",
    tone: "green",
    icon: "M3 10 12 3l9 7M5 9v12h14V9M9 21v-8h6v8",
  },
  {
    path: "/materials",
    label: "资料库",
    description: "收好文档与通知",
    tone: "blue",
    icon: "M3 6h7l2 3h9v11H3ZM3 6V4h7l2 2h7v3",
  },
  {
    path: "/tasks",
    label: "截止任务",
    description: "记住每一个截止",
    tone: "yellow",
    icon: "M9 6h12M9 12h12M9 18h12M3 5l1 1 2-3M3 11l1 1 2-3M3 17l1 1 2-3",
  },
  {
    path: "/deadline-radar",
    label: "DDL 应变台",
    description: "改期先看影响",
    tone: "purple",
    icon: "M5 8h15l-3-3M20 16H5l3 3M20 8v5M5 16v-5",
  },
  {
    path: "/focus",
    label: "专注计时",
    description: "一次只做一件事",
    tone: "yellow",
    icon: "M9 2h6M12 2v3M18 6l2-2M12 9v5l3 2M20 14a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  },
  {
    path: "/schedule",
    label: "课表与考试",
    description: "安排一周的节奏",
    tone: "purple",
    icon: "M3 5h18v16H3ZM3 10h18M8 3v5M16 3v5M7 14h3M14 14h3M7 18h3",
  },
  {
    path: "/study-plans",
    label: "复习计划",
    description: "把复习拆成小步",
    tone: "green",
    icon: "M3 20h5v-5h5v-5h5V5h3M4 4l3 3M5 2v6M2 5h6",
  },
  {
    path: "/settings",
    label: "设置",
    description: "按自己的习惯来",
    tone: "blue",
    icon: "M3 6h9M16 6h5M3 12h3M10 12h11M3 18h11M18 18h3M12 3v6h4V3ZM6 9v6h4V9ZM14 15v6h4v-6Z",
  },
];

async function startDemo() {
  if (demoLoading.value) return;
  demoError.value = "";
  demoLoading.value = true;
  try {
    await demoLogin();
    await router.push("/app");
  } catch (error) {
    demoError.value =
      error?.message || "演示暂不可用，请稍后重试，或使用邮箱注册。";
  } finally {
    demoLoading.value = false;
  }
}
</script>

<style scoped src="../styles/landing.css"></style>
