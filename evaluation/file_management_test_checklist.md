# 文件管理与接口功能测试清单

## 1. 使用范围

- 本清单用于人工验证JWT鉴权、五种文件上传、文件列表、同名替换、删除、输入校验、Swagger和前端知识库管理。
- 本轮共有20项核心测试；`AUTH-05`和`TX-01`仅保留在延期附录，不影响本轮是否通过。
- 执行入口以Swagger `http://localhost:8000/docs`为主，前端只做最终冒烟测试。
- 固定fixture不得修改：
  - `tests/fixtures/rag_eval/rag_eval_basic.txt`
  - `tests/fixtures/rag_eval/rag_eval_technical.md`
  - `tests/fixtures/rag_eval/rag_eval_normal.docx`
  - `tests/fixtures/rag_eval/rag_eval_table.docx`
  - `tests/fixtures/rag_eval/rag_eval_pages.pdf`

## 2. 数据库选择

### 方案A：使用当前本地开发数据库

- 仅当数据库可以清理、可以恢复，且没有重要或不可恢复的资料时使用。
- 测试前通过文件列表记录完整基线；测试后必须恢复到相同基线。
- 即使数据库可以清空，也只能通过接口删除本轮明确上传的文件，不执行全表清理。

### 方案B：使用独立评测数据库

- 当前数据库有重要资料时，在同一PostgreSQL实例中新建独立评测数据库，不要求安装第二套数据库服务。
- 独立评测数据库使用相同表结构，只保存本轮评测用户和评测文件。
- 测试结束后通过接口删除测试文件；是否保留评测数据库由项目维护者决定。

### 共同安全要求

- `documents`表没有`user_id`隔离，专用测试用户不能隔离知识库文件。
- 不允许在有重要资料的数据库执行同名替换和删除。
- 不记录JWT原文、数据库地址、数据库凭证、模型密钥或Authorization请求头。
- 不通过SQL执行`DELETE`、`TRUNCATE`或`DROP`；数据库证据只允许使用限定测试文件名的只读查询。
- 文件列表没有固定排序，使用文件名集合和对应字段判断，不按数组位置判断。

## 3. 执行前准备

1. 选择方案A或方案B，并在结果表`notes`中记录选择，不填写数据库地址。
2. 启动服务后使用专用评测账号登录，但不要把JWT复制到结果表或截图中。
3. 先执行`ENV-01`保存测试前文件列表，再开始上传。
4. 临时文件只放系统临时目录，统一使用`FM_EVAL_`前缀。
5. 同名替换准备两个不同临时目录，两个目录中都创建`FM_EVAL_REPLACE.txt`：V1包含`FM-REPLACE-V1`，V2包含`FM-REPLACE-V2`，且V2正文明显长于V1。
6. 大小限制文件只生成“当前配置上限+1字节”的`FM_EVAL_OVERSIZE.txt`，不要生成远超上限的文件。

## 4. 20项核心测试

| 案例 | 测试目的 | 前置条件 | Swagger或前端操作 | 预期HTTP状态码 | 预期响应关键字段 | 保存证据 | 数据库只读核验 | 清理方式 |
|---|---|---|---|---:|---|---|---|---|
| ENV-01 | 保存测试前文件列表基线 | 已选择安全数据库并取得有效Token | Swagger调用`GET /api/knowledge/documents` | 200 | `code=200`，`data`为文件数组 | 脱敏响应、文件名与Chunk数 | 否 | 不清理；基线用于最终对比 |
| AUTH-01 | 验证评测用户可注册 | 评测用户名未被占用 | Swagger调用`POST /api/auth/register`，提交符合长度要求的用户名和口令 | 200 | 返回`id`和`username`，不返回口令 | 状态码和脱敏响应 | 否 | 评测用户保留供复测 |
| AUTH-02 | 验证正确凭证可取得Token | AUTH-01完成 | Swagger调用`POST /api/auth/login`，使用表单字段`username`和`password` | 200 | `access_token`存在，`token_type=bearer` | 只记录Token已返回，不保存Token值 | 否 | 无 |
| AUTH-03 | 验证无Token被拒绝 | 不进行Swagger授权 | 调用`GET /api/knowledge/documents`且不带Authorization头 | 401 | 错误响应包含`code=401`和错误消息 | 状态码与响应，不保存请求头 | 否 | 无 |
| AUTH-04 | 验证错误Token被拒绝 | 准备一个被修改过且不可用的Token，不保存其原文 | 使用错误Token调用`GET /api/knowledge/documents` | 401 | `code=401`，提示凭证无效或已过期 | 状态码与脱敏响应 | 否 | 清除错误Token并重新授权 |
| UP-01 | 验证TXT上传 | 有效Token，fixture未与重要资料同名 | Swagger上传`tests/fixtures/rag_eval/rag_eval_basic.txt` | 200 | `code=200`，`file_type=txt`，`chunk_count>0` | 响应、文件名、Chunk数、日志时间 | 否 | 最终通过DELETE接口删除 |
| UP-02 | 验证Markdown上传 | 有效Token，fixture未与重要资料同名 | Swagger上传`tests/fixtures/rag_eval/rag_eval_technical.md` | 200 | `code=200`，`file_type=md`，`chunk_count>0` | 响应、文件名、Chunk数、日志时间 | 否 | 最终通过DELETE接口删除 |
| UP-03 | 验证普通DOCX上传 | 有效Token，fixture未与重要资料同名 | Swagger上传`tests/fixtures/rag_eval/rag_eval_normal.docx` | 200 | `code=200`，`file_type=docx`，`chunk_count>0` | 响应、文件名、Chunk数、日志时间 | 否 | 最终通过DELETE接口删除 |
| UP-04 | 验证表格DOCX上传 | 有效Token，fixture未与重要资料同名 | Swagger上传`tests/fixtures/rag_eval/rag_eval_table.docx` | 200 | `code=200`，`file_type=docx`，`chunk_count>0` | 响应、文件名、Chunk数、日志时间 | 否 | 最终通过DELETE接口删除 |
| UP-05 | 验证文本型PDF上传 | 有效Token，fixture未与重要资料同名 | Swagger上传`tests/fixtures/rag_eval/rag_eval_pages.pdf` | 200 | `code=200`，`file_type=pdf`，`chunk_count>0` | 响应、文件名、Chunk数、日志时间 | 否 | 最终通过DELETE接口删除 |
| LIST-01 | 验证文件列表和统计 | UP-01至UP-05成功 | Swagger调用`GET /api/knowledge/documents`，按文件名查找五份fixture | 200 | 五个文件都存在，类型正确，Chunk数与上传响应一致 | 完整脱敏列表；不依赖返回顺序 | 否 | 无 |
| REPLACE-01 | 验证同名文件替换旧Chunk | 两个临时目录中已有同名V1和V2文件 | 先上传V1并刷新列表，再上传同名V2并再次刷新 | 200 | 两次上传均成功；列表只有一个同名文件；最终Chunk数等于V2响应而非两版之和 | 两次响应、两次列表、两个唯一标记说明 | 是：旧标记不存在，新标记存在 | 通过DELETE接口删除`FM_EVAL_REPLACE.txt`，再删除两个临时文件 |
| DELETE-01 | 验证删除文件及全部Chunk | UP-01成功并已记录TXT的Chunk数 | Swagger调用`DELETE /api/knowledge/documents/rag_eval_basic.txt`，随后刷新列表 | 200 | `file_name=rag_eval_basic.txt`；`deleted_chunk_count`等于删除前Chunk数；列表中不再存在 | 删除响应、删除前后列表、日志时间 | 是：对应`source`的数据库行数为0 | 已由本案例删除，无额外清理 |
| DELETE-02 | 验证删除不存在文件 | DELETE-01完成 | 再次删除`rag_eval_basic.txt` | 404 | `code=404`，提示没有找到该知识库文件 | 状态码和响应 | 否 | 无 |
| VALID-01 | 验证不支持格式被拒绝 | 临时目录有小型`FM_EVAL_UNSUPPORTED.csv` | Swagger上传该CSV | 400 | `code=400`，消息说明允许的扩展名；列表无新增项 | 响应和操作后列表 | 否 | 删除临时CSV |
| VALID-02 | 验证0字节文件被拒绝 | 临时目录有0字节`FM_EVAL_EMPTY.txt` | Swagger上传空TXT | 400 | `code=400`，消息说明没有提取到有效文本；列表无新增项 | 响应和操作后列表 | 否 | 删除临时TXT |
| VALID-03 | 验证纯空白文件被拒绝 | 临时目录有只含空格和换行的`FM_EVAL_BLANK.md` | Swagger上传空白Markdown | 400 | `code=400`，消息说明没有提取到有效文本；列表无新增项 | 响应和操作后列表 | 否 | 删除临时Markdown |
| VALID-04 | 验证文件大小限制 | 已由项目维护者确认非敏感的当前大小上限，并生成上限+1字节TXT | Swagger上传`FM_EVAL_OVERSIZE.txt` | 400 | `code=400`，消息说明文件超过大小限制；列表无新增项 | 文件字节数、响应、操作后列表 | 否 | 删除临时超限TXT |
| SWAGGER-01 | 验证Swagger基本操作 | 后端使用预定地址运行 | 打开`/docs`，确认认证、上传、列表、删除接口可展开并完成一次授权调用 | 200 | 文档页可打开；相关接口可见；授权后的列表请求返回`code=200` | 页面截图和一次脱敏列表响应 | 否 | 不保存Token，退出或关闭页面 |
| UI-01 | 验证前端知识库管理基本操作 | AUTH-02、Swagger核心接口已通过 | 前端登录，上传一个小型临时TXT，刷新列表，确认删除提示并删除 | 200 | 登录、上传、列表、删除请求成功；页面显示Chunk数并刷新 | 页面截图、浏览器状态码、后端响应；错误文字以后端实际响应为准 | 否 | 删除临时文件并在前端退出登录 |

## 5. 延期附录

| 案例 | 延期内容 | 当前处理 |
|---|---|---|
| AUTH-05 | 使用过期Token请求知识库接口，预期401 | 标记`DEFERRED`；本轮不修改Token有效期，也不等待Token过期 |
| TX-01 | 同名替换过程中受控触发Embedding失败，验证事务回滚 | 标记`DEFERRED`；本轮不修改Embedding配置或注入故障 |

## 6. 测试结束检查

1. 通过DELETE接口逐个删除本轮仍存在的fixture和`FM_EVAL_`文件，不通过SQL清理。
2. 调用文件列表，按文件名集合和Chunk数与`ENV-01`基线比较，不比较返回顺序。
3. 删除所有系统临时目录中的V1、V2、空文件、空白文件、CSV和超限文件。
4. 确认结果表没有JWT、Authorization头、数据库地址、数据库凭证或模型密钥。
5. 20项核心测试单独判断；两项延期测试保持`DEFERRED`，不阻断本轮结论。
