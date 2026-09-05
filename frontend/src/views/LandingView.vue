<template>
  <div class="landing-page">
    <a class="public-skip" href="#landing-main">跳到主要内容</a>
    <header class="landing-nav">
      <router-link class="landing-brand" to="/" aria-label="学伴管家首页">
        <span class="brand-tile">学</span>
        <span><strong>学伴管家</strong><small>课程资料与学习任务助手</small></span>
      </router-link>
      <nav aria-label="首页导航">
        <a href="#workflow">怎么工作</a>
        <a href="#boundaries">可信边界</a>
      </nav>
      <div class="landing-account">
        <template v-if="authSession.user">
          <span class="welcome-name">{{ authSession.user.display_name }}，欢迎回来</span>
          <router-link class="button button-primary" to="/app">回到我的学习空间</router-link>
        </template>
        <template v-else>
          <router-link class="text-link" to="/login">登录</router-link>
          <router-link class="button button-primary" to="/register">免费开始</router-link>
        </template>
      </div>
    </header>

    <main id="landing-main">
      <section class="hero-section" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="section-kicker"><span>资料进来</span><i></i><span>下一步出去</span></p>
          <h1 id="hero-title">别再靠截图<br><em>记住截止日期。</em></h1>
          <p class="hero-lead">把课程通知、作业文档和复习资料放进来，学伴管家帮你找出截止时间、保留依据，再整理成今天做得完的行动。</p>
          <div class="hero-actions">
            <router-link class="button button-primary button-large" :to="authSession.user ? '/app' : '/register'">
              {{ authSession.user ? '打开今日安排' : '建立我的学习空间' }}
              <span aria-hidden="true">→</span>
            </router-link>
            <a class="button button-quiet button-large" href="#workflow">先看看怎么用</a>
          </div>
          <ul class="trust-list" aria-label="产品特性">
            <li><span>✓</span>确认后才创建任务</li>
            <li><span>✓</span>每条建议保留来源</li>
            <li><span>✓</span>账号学习空间相互隔离</li>
          </ul>
        </div>

        <div class="week-ledger" aria-label="学伴管家学习安排示意">
          <div class="ledger-topline">
            <div><small>WEEK 07 / 本周安排</small><strong>今天先做这两件</strong></div>
            <span class="ledger-status"><i></i> 已整理</span>
          </div>
          <div class="ledger-days" aria-hidden="true">
            <span>一<small>16</small></span><span class="is-today">二<small>17</small></span><span>三<small>18</small></span><span>四<small>19</small></span><span>五<small>20</small></span>
          </div>
          <div class="ledger-grid">
            <span class="time-label">09:00</span>
            <article class="ledger-card card-blue">
              <div class="course-code">数据结构 · 作业</div>
              <h2>完成树与图实验报告</h2>
              <p>今晚 23:59 截止 · 预计 70 分钟</p>
              <div class="source-pill">来源：实验三通知.pdf</div>
            </article>
            <span class="time-label second">15:00</span>
            <article class="ledger-card card-mint">
              <div class="course-code">线性代数 · 复习</div>
              <h2>矩阵特征值错题回看</h2>
              <p>今日安排 · 预计 35 分钟</p>
              <div class="source-pill">按本周完成反馈调整</div>
            </article>
          </div>
          <aside class="ledger-note">
            <span class="note-pin"></span>
            <small>行动建议</small>
            <strong>先做实验报告，再复习线代</strong>
            <p>实验报告更快到期；不会替你提交，也不会擅自改计划。</p>
          </aside>
        </div>
      </section>

      <section class="campus-strip" aria-label="适用资料类型">
        <span>课程群通知</span><i></i><span>PDF / Word / 图片</span><i></i><span>作业与考试截止时间</span><i></i><span>复习计划</span>
      </section>

      <section id="workflow" class="workflow-section" aria-labelledby="workflow-title">
        <div class="section-heading">
          <p class="section-kicker">一条能走完的学习闭环</p>
          <h2 id="workflow-title">从“我好像看过”到“我知道下一步”</h2>
          <p>学伴管家不只给出回答，而是把结果整理成可核对、可修改、可完成的学习记录。</p>
        </div>
        <div class="workflow-grid">
          <article>
            <span class="step-number">01</span>
            <div class="step-icon">↓</div>
            <h3>先把资料收好</h3>
            <p>上传课程通知、课件和作业要求。原文件与识别结果都会保留在资料中。</p>
            <small>支持批量上传与失败重试</small>
          </article>
          <article>
            <span class="step-number">02</span>
            <div class="step-icon">◇</div>
            <h3>关键内容先核对</h3>
            <p>截止时间、课程和任务名称都能查看原文依据。你确认或修改后，才会进入正式任务列表。</p>
            <small>不确定的字段会明确标记</small>
          </article>
          <article>
            <span class="step-number">03</span>
            <div class="step-icon">✓</div>
            <h3>变成今天的行动</h3>
            <p>根据截止时间、预计用时与近期反馈排优先级，完成后继续校准下一次计划。</p>
            <small>计划调整始终由你确认</small>
          </article>
        </div>
      </section>

      <section class="agent-section" aria-labelledby="agent-title">
        <div class="agent-demo">
          <div class="agent-demo-head"><span>今日行动台</span><small>09:42 更新</small></div>
          <article class="focus-card">
            <span class="risk-tag">距截止 8 小时</span>
            <h3>数据结构实验报告</h3>
            <p>还剩约 70 分钟 · 建议在晚课前完成主体</p>
            <div class="focus-actions"><button type="button">开始处理</button><button type="button">查看依据</button></div>
          </article>
          <div class="mini-row"><span class="mini-check">✓</span><div><strong>高等数学习题 6</strong><small>已完成 · 实际 42 分钟</small></div></div>
          <div class="mini-row"><span class="mini-dot"></span><div><strong>英语展示资料</strong><small>待确认 1 个日期字段</small></div></div>
        </div>
        <div class="agent-copy">
          <p class="section-kicker">不只是回答，更帮你落实下一步</p>
          <h2 id="agent-title">该提醒时提醒，<br>该让你决定时停下来。</h2>
          <p>学伴管家会解释为什么这件事更紧急、依据来自哪里，以及执行后会改变什么。遇到信息不完整，它会把问题留给你确认，而不是假装确定。</p>
          <dl>
            <div><dt>可追溯</dt><dd>建议能回到具体任务、资料或计划项</dd></div>
            <div><dt>可撤回</dt><dd>计划调整先预览差异，再决定是否应用</dd></div>
            <div><dt>会校准</dt><dd>用实际完成时间修正之后的估时</dd></div>
          </dl>
        </div>
      </section>

      <section id="boundaries" class="boundary-section" aria-labelledby="boundary-title">
        <div>
          <p class="section-kicker">清楚的边界，比“全自动”更可靠</p>
          <h2 id="boundary-title">你的学习决定，始终由你确认。</h2>
        </div>
        <div class="boundary-list">
          <article><span>不替你提交</span><p>系统不会登录学校平台或代交作业。</p></article>
            <article><span>不隐藏来源</span><p>识别字段和学伴管家建议保留可回看的依据入口。</p></article>
          <article><span>不混用账号数据</span><p>每个注册账号使用独立学习工作区。</p></article>
        </div>
      </section>

      <section class="closing-section">
        <p>下一条群通知，不必再靠记忆。</p>
        <h2>把资料放进来，今天从哪一步开始会很清楚。</h2>
        <router-link class="button button-light button-large" :to="authSession.user ? '/app' : '/register'">
          {{ authSession.user ? '继续今天的学习' : '用邮箱免费开始' }} <span aria-hidden="true">→</span>
        </router-link>
      </section>
    </main>

    <footer class="landing-footer">
      <div class="landing-brand"><span class="brand-tile">学</span><span><strong>学伴管家</strong><small>课程资料与学习任务助手</small></span></div>
      <p>让每份课程资料，都落到下一步行动。</p>
      <span>本地开发版本</span>
    </footer>
  </div>
</template>

<script setup>
import { authSession } from '../auth/session'
</script>

<style scoped>
.landing-page { --landing-ink: #16213d; --landing-blue: #3157e6; --landing-paper: #f7f8fc; --landing-mint: #78e5cc; --landing-yellow: #ffc857; --landing-line: #dce3f0; min-height: 100vh; color: var(--landing-ink); background: var(--landing-paper); }
.public-skip { position: fixed; z-index: 20; top: 10px; left: 10px; padding: 10px 14px; color: #fff; background: var(--landing-ink); transform: translateY(-150%); }
.public-skip:focus { transform: translateY(0); }
.landing-nav { position: relative; z-index: 5; max-width: 1240px; min-height: 82px; display: flex; align-items: center; gap: 44px; margin: 0 auto; padding: 16px 28px; }
.landing-brand { display: inline-flex; align-items: center; gap: 11px; color: var(--landing-ink); }
.landing-brand > span:last-child { display: grid; }
.landing-brand strong { font-size: 17px; letter-spacing: .04em; }
.landing-brand small { margin-top: 2px; color: #6d7890; font-size: 10px; }
.brand-tile { width: 38px; height: 38px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 11px; color: #fff; background: var(--landing-blue); font: 800 15px/1 Bahnschrift, "Microsoft YaHei", sans-serif; box-shadow: 4px 4px 0 var(--landing-yellow); }
.landing-nav nav { display: flex; gap: 28px; margin-left: auto; }
.landing-nav nav a, .text-link { min-height: 44px; display: inline-flex; align-items: center; color: #4c5872; font-size: 13px; font-weight: 650; }
.landing-nav nav a:hover, .text-link:hover { color: var(--landing-blue); }
.landing-account { display: flex; align-items: center; gap: 15px; }
.welcome-name { max-width: 160px; overflow: hidden; color: #64708a; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.button { min-height: 44px; display: inline-flex; align-items: center; justify-content: center; gap: 16px; padding: 0 19px; border: 1px solid transparent; border-radius: 12px; font-size: 14px; font-weight: 750; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
.button:hover { transform: translateY(-2px); }
.button-primary { color: #fff; background: var(--landing-blue); box-shadow: 0 8px 20px rgba(49, 87, 230, .19); }
.button-primary:hover { color: #fff; background: #2648c6; }
.button-large { min-height: 52px; padding: 0 23px; }
.button-quiet { color: var(--landing-ink); background: transparent; border-color: #bac5da; }
.button-light { color: var(--landing-ink); background: #fff; box-shadow: 6px 6px 0 var(--landing-yellow); }
.hero-section { max-width: 1240px; min-height: 670px; display: grid; grid-template-columns: minmax(0, .92fr) minmax(520px, 1.08fr); align-items: center; gap: 65px; margin: 0 auto; padding: 72px 28px 96px; }
.section-kicker { display: flex; align-items: center; gap: 10px; margin: 0 0 17px; color: var(--landing-blue); font: 750 12px/1.4 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .08em; text-transform: uppercase; }
.section-kicker i { width: 28px; height: 1px; background: #9aacda; }
.hero-copy h1 { max-width: 600px; margin: 0; font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: clamp(52px, 5vw, 76px); line-height: 1.02; letter-spacing: -.06em; }
.hero-copy h1 em { position: relative; z-index: 0; color: var(--landing-blue); font-style: normal; }
.hero-copy h1 em::after { position: absolute; z-index: -1; right: -3px; bottom: 5px; left: -3px; height: 14px; content: ""; background: var(--landing-yellow); opacity: .7; transform: rotate(-1deg); }
.hero-lead { max-width: 620px; margin: 27px 0 0; color: #56627c; font-size: 17px; line-height: 1.85; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 32px; }
.trust-list { display: flex; flex-wrap: wrap; gap: 13px 22px; margin: 25px 0 0; padding: 0; list-style: none; color: #68738b; font-size: 12px; }
.trust-list li { display: flex; align-items: center; gap: 6px; }
.trust-list span { color: #17836d; font-weight: 900; }
.week-ledger { position: relative; min-height: 510px; padding: 25px 25px 32px; overflow: hidden; border: 1px solid #cfd8e9; border-radius: 24px; background: #fff; box-shadow: 18px 22px 0 #dfe6f8, 0 30px 70px rgba(22, 33, 61, .12); transform: rotate(1.2deg); }
.week-ledger::before { position: absolute; inset: 117px 0 0; content: ""; background-image: linear-gradient(#edf0f6 1px, transparent 1px), linear-gradient(90deg, #edf0f6 1px, transparent 1px); background-size: 100% 62px, 20% 100%; }
.ledger-topline { position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: flex-start; padding-bottom: 19px; border-bottom: 1px solid #e1e6ef; }
.ledger-topline div { display: grid; gap: 5px; }
.ledger-topline small, .agent-demo-head small { color: #758097; font: 700 10px/1.3 Bahnschrift, sans-serif; letter-spacing: .1em; }
.ledger-topline strong { font-size: 21px; }
.ledger-status { display: inline-flex; align-items: center; gap: 7px; padding: 7px 10px; color: #176957; border-radius: 99px; background: #e9faf5; font-size: 11px; font-weight: 700; }
.ledger-status i { width: 7px; height: 7px; border-radius: 50%; background: #20a889; box-shadow: 0 0 0 4px rgba(32, 168, 137, .13); }
.ledger-days { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(5, 1fr); margin: 14px 0 8px 58px; color: #7b859a; text-align: center; font-size: 11px; }
.ledger-days span { display: grid; gap: 4px; }
.ledger-days small { font-size: 12px; font-weight: 750; }
.ledger-days .is-today { color: var(--landing-blue); }
.ledger-days .is-today small { width: 27px; height: 27px; display: grid; place-items: center; justify-self: center; border-radius: 9px; color: #fff; background: var(--landing-blue); }
.ledger-grid { position: relative; z-index: 1; min-height: 305px; }
.time-label { position: absolute; top: 20px; left: 0; color: #8a93a5; font: 10px/1 Bahnschrift, sans-serif; }
.time-label.second { top: 181px; }
.ledger-card { position: absolute; width: 58%; padding: 16px; border: 1px solid rgba(22, 33, 61, .1); border-radius: 15px; box-shadow: 0 8px 16px rgba(22, 33, 61, .08); }
.ledger-card.card-blue { top: 8px; left: 20%; background: #eef2ff; }
.ledger-card.card-mint { top: 168px; left: 39%; background: #e9faf5; }
.course-code { color: #53617d; font-size: 10px; font-weight: 800; letter-spacing: .06em; }
.ledger-card h2 { margin: 7px 0 5px; font-size: 15px; line-height: 1.4; }
.ledger-card p { margin: 0; color: #65718a; font-size: 11px; }
.source-pill { width: fit-content; max-width: 100%; margin-top: 10px; padding: 5px 8px; overflow: hidden; color: #526078; border-radius: 6px; background: rgba(255,255,255,.72); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.ledger-note { position: absolute; z-index: 3; right: 15px; bottom: 12px; width: 210px; padding: 20px 17px 16px; background: var(--landing-yellow); box-shadow: 7px 8px 0 rgba(22, 33, 61, .13); transform: rotate(-3deg); }
.note-pin { position: absolute; top: 7px; left: 50%; width: 7px; height: 7px; border-radius: 50%; background: #ad6c12; }
.ledger-note small, .ledger-note strong { display: block; }
.ledger-note small { margin-bottom: 6px; color: #725217; font-size: 9px; font-weight: 800; letter-spacing: .08em; }
.ledger-note strong { font-size: 13px; }
.ledger-note p { margin: 7px 0 0; color: #6c541f; font-size: 10px; line-height: 1.5; }
.campus-strip { display: flex; align-items: center; justify-content: center; gap: 26px; padding: 20px 28px; overflow: hidden; color: #fff; background: var(--landing-ink); font: 700 12px/1.3 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .05em; white-space: nowrap; }
.campus-strip i { width: 5px; height: 5px; border-radius: 50%; background: var(--landing-yellow); }
.workflow-section { max-width: 1184px; margin: 0 auto; padding: 112px 28px 125px; }
.section-heading { max-width: 700px; }
.section-heading h2, .agent-copy h2, .boundary-section h2, .closing-section h2 { margin: 0; font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: clamp(34px, 4vw, 50px); line-height: 1.18; letter-spacing: -.04em; }
.section-heading > p:last-child { max-width: 650px; margin: 21px 0 0; color: #68738b; font-size: 15px; line-height: 1.8; }
.workflow-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 50px; }
.workflow-grid article { position: relative; min-height: 300px; padding: 28px; border: 1px solid var(--landing-line); border-radius: 18px; background: #fff; }
.workflow-grid article:nth-child(2) { transform: translateY(24px); }
.step-number { color: #9aa5ba; font: 800 11px/1 Bahnschrift, sans-serif; letter-spacing: .1em; }
.step-icon { width: 48px; height: 48px; display: grid; place-items: center; margin-top: 32px; border-radius: 14px; color: var(--landing-blue); background: #edf1ff; font-size: 23px; font-weight: 800; }
.workflow-grid article:nth-child(2) .step-icon { color: #8b6011; background: #fff4d7; }
.workflow-grid article:nth-child(3) .step-icon { color: #176957; background: #e6faf4; }
.workflow-grid h3 { margin: 20px 0 10px; font-size: 21px; }
.workflow-grid p { margin: 0; color: #657089; font-size: 14px; line-height: 1.75; }
.workflow-grid small { position: absolute; right: 28px; bottom: 24px; left: 28px; color: #8a94a8; font-size: 11px; }
.agent-section { display: grid; grid-template-columns: minmax(420px, .9fr) minmax(0, 1.1fr); gap: 85px; align-items: center; padding: 110px max(28px, calc((100vw - 1184px)/2)); background: #eaf0ff; }
.agent-demo { max-width: 500px; padding: 21px; border: 1px solid #c5d0ea; border-radius: 21px; background: #fff; box-shadow: 13px 15px 0 var(--landing-blue); }
.agent-demo-head { display: flex; justify-content: space-between; align-items: center; padding: 0 2px 17px; color: #32415e; font-size: 13px; font-weight: 800; }
.focus-card { padding: 21px; border-radius: 15px; background: var(--landing-ink); }
.risk-tag { display: inline-flex; padding: 5px 8px; border-radius: 6px; color: #75510d; background: var(--landing-yellow); font-size: 10px; font-weight: 800; }
.focus-card h3 { margin: 15px 0 7px; color: #fff; font-size: 20px; }
.focus-card p { margin: 0; color: #c4cde0; font-size: 12px; }
.focus-actions { display: flex; gap: 8px; margin-top: 20px; }
.focus-actions button { min-height: 40px; padding: 0 13px; border: 1px solid #8793aa; border-radius: 9px; color: #dce4f5; background: transparent; font-size: 11px; }
.focus-actions button:first-child { color: var(--landing-ink); border-color: var(--landing-mint); background: var(--landing-mint); font-weight: 800; }
.mini-row { display: flex; align-items: center; gap: 11px; padding: 16px 5px 4px; }
.mini-row + .mini-row { border-top: 1px solid #edf0f5; }
.mini-check, .mini-dot { width: 25px; height: 25px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 8px; color: #17705d; background: #ddf7ef; font-weight: 900; }
.mini-dot { background: #fff2cd; }
.mini-dot::after { width: 6px; height: 6px; content: ""; border-radius: 50%; background: #b97a14; }
.mini-row div { display: grid; gap: 3px; }
.mini-row strong { font-size: 12px; }
.mini-row small { color: #7a859b; font-size: 10px; }
.agent-copy { max-width: 620px; }
.agent-copy > p:nth-of-type(2) { margin: 23px 0 0; color: #59667f; font-size: 15px; line-height: 1.9; }
.agent-copy dl { display: grid; gap: 0; margin: 30px 0 0; }
.agent-copy dl div { display: grid; grid-template-columns: 86px 1fr; gap: 15px; padding: 14px 0; border-top: 1px solid #cbd5eb; }
.agent-copy dt { color: var(--landing-blue); font-weight: 850; }
.agent-copy dd { margin: 0; color: #64718b; font-size: 13px; }
.boundary-section { max-width: 1184px; display: grid; grid-template-columns: .85fr 1.15fr; gap: 70px; align-items: start; margin: 0 auto; padding: 115px 28px; }
.boundary-list { border-top: 1px solid #bdc8da; }
.boundary-list article { display: grid; grid-template-columns: 150px 1fr; gap: 20px; padding: 22px 0; border-bottom: 1px solid #bdc8da; }
.boundary-list span { font-weight: 850; }
.boundary-list p { margin: 0; color: #65718a; font-size: 13px; line-height: 1.7; }
.closing-section { max-width: 1184px; margin: 0 auto 70px; padding: 65px; border-radius: 28px; color: #fff; background: var(--landing-blue); }
.closing-section p { margin: 0 0 15px; color: #d9e0ff; font-size: 13px; }
.closing-section h2 { max-width: 760px; }
.closing-section .button { margin-top: 31px; }
.landing-footer { max-width: 1184px; display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 35px; margin: 0 auto; padding: 26px 28px 42px; color: #7a8499; border-top: 1px solid var(--landing-line); font-size: 11px; }
.landing-footer p { margin: 0; }
@media (max-width: 980px) { .landing-nav nav { display: none; } .hero-section { min-height: 0; grid-template-columns: 1fr; padding-top: 55px; } .hero-copy { max-width: 720px; } .week-ledger { max-width: 650px; width: 100%; margin: 10px auto 0; } .workflow-grid { grid-template-columns: 1fr; } .workflow-grid article, .workflow-grid article:nth-child(2) { min-height: 245px; transform: none; } .agent-section { grid-template-columns: 1fr; gap: 65px; } .agent-demo { width: 100%; max-width: 650px; } .boundary-section { grid-template-columns: 1fr; gap: 40px; } }
@media (max-width: 680px) { .landing-nav { min-height: 70px; padding: 13px 16px; } .landing-brand small, .welcome-name, .landing-account .text-link { display: none; } .landing-account { margin-left: auto; } .landing-nav .button { min-height: 42px; padding: 0 14px; } .hero-section { gap: 48px; padding: 47px 16px 70px; } .hero-copy h1 { font-size: clamp(43px, 13vw, 60px); } .hero-lead { font-size: 15px; } .hero-actions { align-items: stretch; flex-direction: column; } .hero-actions .button { width: 100%; } .trust-list { align-items: flex-start; flex-direction: column; } .week-ledger { min-height: 470px; padding: 20px 14px 26px; border-radius: 18px; box-shadow: 9px 11px 0 #dfe6f8; transform: none; } .ledger-topline strong { font-size: 17px; } .ledger-status { display: none; } .ledger-days { margin-left: 40px; } .ledger-card { width: 73%; } .ledger-card.card-blue { left: 15%; } .ledger-card.card-mint { left: 22%; } .ledger-note { right: 9px; width: 180px; } .campus-strip { justify-content: flex-start; overflow-x: auto; } .workflow-section { padding: 85px 16px 95px; } .workflow-grid article { padding: 23px; } .workflow-grid small { right: 23px; left: 23px; } .agent-section { padding: 85px 16px; } .agent-demo { box-shadow: 7px 8px 0 var(--landing-blue); } .boundary-section { padding: 90px 16px; } .boundary-list article { grid-template-columns: 1fr; gap: 8px; } .closing-section { margin: 0 16px 55px; padding: 38px 25px; border-radius: 20px; } .landing-footer { grid-template-columns: 1fr; gap: 14px; padding: 24px 16px 35px; } }
@media (prefers-reduced-motion: reduce) { .button { transition: none; } }
</style>
