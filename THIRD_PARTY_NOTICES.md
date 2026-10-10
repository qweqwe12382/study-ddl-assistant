# 第三方软件与制作工具说明

本清单记录2026-10-10本机实际安装包的许可证元数据，用于来源披露。项目根目录MIT许可证适用于本项目自行编写的代码，不改变第三方组件的许可。精确版本见backend/requirements.txt和frontend/package-lock.json；完整条款以各分发包附带许可证为准。

## 后端直接依赖

| 组件 | 实测版本 | 许可证元数据 |
| --- | --- | --- |
| fastapi | 0.141.1 | MIT |
| uvicorn | 0.52.1 | BSD-3-Clause |
| pydantic | 2.13.4 | MIT |
| SQLAlchemy | 2.0.51 | MIT |
| PyMuPDF | 1.28.0 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License |
| python-docx | 1.2.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| pytest | 9.1.1 | MIT |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| icalendar | 7.2.2 | BSD-2-Clause |
| requests | 2.34.2 | Apache-2.0 |
| beautifulsoup4 | 4.13.4 | MIT License |
| openai | 2.53.0 | Apache-2.0 |
| pandas | 3.0.5 | BSD-3-Clause |
| rapidocr-onnxruntime | 1.2.3 | Apache-2.0 |

PyMuPDF分发包标明GNU AGPL 3.0与Artifex商业许可双许可；本项目没有声明已购买商业许可。涉及该组件的再分发或部署应按其实际许可处理，不能把整个依赖栈一概称为MIT。依赖安装由官方包注册表完成，本仓库不捆绑Python包或模型权重。

## 前端直接依赖

| 组件 | 锁定版本 | 许可证 |
| --- | --- | --- |
| @element-plus/icons-vue | 2.3.2 | MIT |
| axios | 1.19.0 | MIT |
| element-plus | 2.14.3 | MIT |
| vue | 3.5.41 | MIT |
| vue-router | 4.6.4 | MIT |
| @vitejs/plugin-vue | 6.0.8 | MIT |
| eslint | 9.39.5 | MIT |
| eslint-plugin-vue | 10.11.0 | MIT |
| prettier | 3.9.6 | MIT |
| vite | 7.3.6 | MIT |

## Android与静态素材

Android使用Kotlin、AndroidX/Compose、Material组件及Gradle工具链；版本目录与依赖声明位于android。源代码交付不捆绑Android SDK。界面字体Noto Sans SC及Manrope采用SIL OFL，原始许可证与来源保留在frontend/public/fonts。本项目书本标识为项目SVG，主页插图的制作说明见现有设计材料。

## 报告与视频制作

技术报告和评测用例按比赛附件结构编写，AI辅助整理，正式签署由成员完成。文档生成使用docx，渲染使用本机Word；图表由代码绘制。视频使用实际本地应用截图、合成课程数据、程序化排版和FFmpeg编码；旁白使用D盘已部署的Qwen3-TTS-12Hz-0.6B-CustomVoice，预置Vivian音色，没有克隆真人声音。模型权重不纳入仓库，视频不用外部音乐或第三方影像。视频脚本及字幕随作品提供。

本清单不是全部传递依赖的逐文件许可证副本；传递依赖由锁文件及各分发包许可证追溯。软件测试结果、合成示例与AI辅助制作方式均已在技术报告中区分披露。
