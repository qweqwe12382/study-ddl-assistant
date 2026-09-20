# 背景装饰素材

2026-09-19 为学伴管家制作。素材在本项目中托管，无外部图库或图片 CDN 请求。

| 素材 | 来源 | 使用位置 |
| --- | --- | --- |
| `study-paper-sage.png` | 内置 image_gen 生成的原始背景，1536 × 1024 | 保留为设计源文件，不进入网页资源包 |
| `study-paper-sage.webp` | 原图转为 WebP，1536 × 1024，25,112 字节 | 登录/注册介绍区、今日重点背景 |
| `folio-lines.svg` | 本项目编写的书页曲线矢量图 | 首页深绿通知改期展示区 |
| `study-path.svg` | 本项目编写的纸页与路径矢量图 | 工作区页首 |
| `study-sculpture-v2.png` | 2026-09-20 内置 image_gen 生成的立体书页原图，1536 × 1024 | 设计源文件，不进入网页资源包 |
| `study-sculpture-v2.webp` | 原图压缩为 WebP，1536 × 1024，99,882 字节 | 首页桌面主视觉 |
| `study-sculpture-v2-small.webp` | 原图等比例缩小为 WebP，768 × 512，28,218 字节 | 首页 760px 及以下主视觉 |

生成方式：内置 `image_gen`，不是第三方图库下载。WebP 使用 Sharp 做格式压缩，构图和尺寸不变。原始 PNG 保留供后续设计修改；网页仅引用较小的 WebP。

背景线稿由 CSS 伪元素显示，`pointer-events: none`，不添加朗读内容或键盘焦点。新版首页主视觉使用带中文替代文本的 `picture` / `img`，声明原始尺寸并优先加载；叠加的书签标签标记为装饰。没有循环动画。主视觉的一次入场、标题下划线描绘及交互过渡尊重减少动态效果偏好。

## 实际生成提示词

```text
Use case: stylized-concept. Asset type: a premium subtle website background decoration for an existing Chinese university study planning app, not a complete UI. Create one wide landscape 1536x1024 abstract paper relief artwork on a very light neutral-white background (#f7faf7). Refined art direction: the outer silhouette of gently fanned open-book pages, 4 to 6 broad sculptural curved paper sheets, extremely thin elegant sage-green edges, softly translucent matte vellum in pale eucalyptus and gray-green. Forms rise from the bottom right corner and sweep toward upper right, making a loose asymmetrical arc; the entire left half and the central 40% stay almost empty near-white for overlaid interface content. One slender muted antique-brass filament follows the edge of a single sheet. Very soft daylight, sophisticated tactile paper grain, barely-there botanical window shadows at the far upper right edge. Low contrast, lots of breathing room, calm academic identity, architectural material-study photography quality. Thin layered paper, no thick plastic geometry. Decorations only: absolutely no text, letters, numbers, logos, watermarks, UI, frames, cards, buttons, icons, stationery objects or mockup. Not a gradient blob, not a pastel cartoon, not glossy 3D, no dark shadows. All four edges blend into almost pure white so it can sit behind a white webpage. Original bespoke abstract artwork.
```

## 调整入口

登录/注册和工作区的装饰位置集中在 `frontend/src/styles/decorations.css`；新版首页的独立构图、尺寸、遮罩和响应式规则在 `frontend/src/styles/landing.css`。

## 2026-09-20 立体书页主视觉

生成模式：内置 `image_gen`，一次生成全新图片，无参考图，无第三方图库素材。原始生成文件保留在 Codex 生成目录，副本以新版本名称保存在本目录。使用 Sharp 进行格式压缩和等比例缩放，没有改变构图或修改内容。网页只加载当前断点所需的 WebP。

实际生成提示词：

```text
Create one exceptionally beautiful premium editorial 3D still-life artwork for a Chinese university study planning website. This is an ORIGINAL ART ASSET, not a website mockup. Landscape 3:2 aspect ratio, clean studio background in warm off-white ivory #f5f3e9, seamless background, no text, no logos, no letters, no numbers, no watermark. Subject: a substantial, exquisitely crafted open academic notebook with a deep forest-green cloth hardback cover, crisp ivory folded paper pages. The book is transformed into a miniature architectural landscape of learning: beautifully fanned sculptural paper sheets curl upward into one elegant paper arch and a series of precise folded steps. Two small closed sage and dark green books sit beside it at different heights. A thin warm brass ribbon bookmark flows through the open pages, a matte sage bookmark with a tiny simple checkmark cutout, one delicate ginkgo sprig lying next to the book. Composition one integrated sculptural still life, airy but rich detail, sits lower center with the curling paper rising in upper right, soft ground contact shadows. Orthographic three-quarter view, premium physical miniature set, Japanese editorial design and architectural paper engineering, realistic paper grain, subtly deckled edges only in fine details, cloth weave, polished brass detail, tactile materials. Restrained palette ivory, forest green #194d3c, pale sage #b7cab2, tiny warm brass accent. Soft directional morning light from upper left creates long luminous shadows, gentle depth, detailed but disciplined composition. Crisp high-end art direction, gallery-quality product photography mixed with masterful handcrafted paper sculpture. No people, no buildings with windows, no computers, no digital screen, no charts, no spheres or generic abstract blobs. Keep all objects fully visible with 8 percent breathing room; background uniform warm ivory and very subtle shadow gradient only.
```
