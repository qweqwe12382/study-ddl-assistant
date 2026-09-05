import fs from 'node:fs'

const appPath = process.argv[2]
if (!appPath) throw new Error('App.vue path is required')

let source = fs.readFileSync(appPath, 'utf8')

source = source.replace(
  /(<div class="sidebar-footer">\s*<el-tag[^>]*>)[\s\S]*?(<\/el-tag>)/,
  '$1\u5728\u7ebf\u7248$2',
)
source = source.replace(
  /(<div class="sidebar-footer">[\s\S]*?<\/el-tag>\s*<span>)[^<]*(<\/span>)/,
  '$1\u6570\u636e\u4fdd\u5b58\u5728\u670d\u52a1\u5668$2',
)

fs.writeFileSync(appPath, source)
