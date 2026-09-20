# 本地字体与商用许可

本站使用以下两款 SIL Open Font License 1.1 字体。许可允许免费使用、修改、嵌入以及与软件一同商业分发；随字体保留版权与许可，不单独出售字体，不将作者姓名用作背书。完整条款以同目录原始 OFL 文件为准。

| 字体 | 用途 | 本地文件 | 许可 |
| --- | --- | --- | --- |
| Noto Sans SC | 中文界面、品牌与标题，100–900 可变字重 | `noto-sans-sc-ui.woff2` | `NotoSansSC-OFL.txt` |
| Manrope | 西文、日期与计时数字，200–800 可变字重 | `manrope-latin.woff2` | `Manrope-OFL.txt` |

## 官方来源

固定 Google Fonts 仓库版本：`f2bd09badbc763d8757951d52deec29da27e85fb`。

- [Noto Sans SC 字体及原始许可](https://github.com/google/fonts/tree/f2bd09badbc763d8757951d52deec29da27e85fb/ofl/notosanssc)
- [Manrope 字体及原始许可](https://github.com/google/fonts/tree/f2bd09badbc763d8757951d52deec29da27e85fb/ofl/manrope)

中文字体原版权声明：Copyright 2014–2021 Adobe；保留名称为 “Source”。本项目没有使用该保留名称作为修改字体的名称。Manrope 原版权声明：Copyright 2018 The Manrope Project Authors。

## 子集与加载

字体从官方可变 TTF 转为 WOFF2。中文保留本项目固定界面文案所需的 726 个字符；Manrope 保留 214 个西文、数字和标点字符。字形设计不变，版权和许可元数据保留。两文件共 214,148 字节（约 209 KiB）。2026-09-20 随新版介绍页文案补齐中文子集。

中文 CSS 家族别名为 `Noto Sans SC UI`，并声明准确的 `unicode-range`。未收录的用户输入、生僻字及其他文字由 PingFang SC / Microsoft YaHei 等系统字体回退显示。使用 `font-display: swap`，不会为等待字体隐藏正文。字体从本站 `/fonts/` 加载，运行时不连接 Google Fonts 或其他外部字体服务。

页面增加新文案时，下载上述版本的 `NotoSansSC[wght].ttf` 和 `Manrope[wght].ttf`，分别重命名为 `NotoSansSC.ttf`、`Manrope.ttf`，放入任意维护目录。安装 `fonttools` 与 `brotli` 后运行：

```text
python frontend/scripts/subset-fonts.py --source-dir <维护目录>
```

该脚本同时更新 WOFF2 和 `frontend/src/font-faces.css`。日常前端构建直接使用已保存文件，不需要 Python 或联网下载字体。

首次生成工具：fonttools 4.65.0、brotli 1.2.0。

## SHA-256

```text
noto-sans-sc-ui.woff2  318dc1c49b7cd4a35416745212e3b355a1a243dc2fdaf9ab7fe7353fce842abb
manrope-latin.woff2   d5ea44bbd9e1e183170aad9554e47bbedbc15a816749e3f8f784bd7f51cc8d9d
```

界面中的书本标识为本项目编写的 SVG，不包含第三方图标或字体素材。
