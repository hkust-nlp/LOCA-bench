# Canvas List Test S2L Environment

Canvas 课程测试环境，支持动态生成任务配置和完整的环境预处理。

## 功能特性

- ✅ 动态生成课程配置
- ✅ 支持测验（Quiz）和作业（Assignment）
- ✅ 免修机制模拟
- ✅ 学生提交状态管理
- ✅ 自动生成 groundtruth 数据
- ✅ Memory.json 集成
- ✅ 完整的环境预处理流程（集成在 `reset()` 方法中）
- ✅ 本地 JSON 数据库（无需 Canvas API）

## 使用方法

### 1. 标准用法（推荐）- 使用 reset() 方法

```python
from gem.envs.canvas_list_test_s2l import CanvasListTestS2LEnv

# 创建环境并指定参数
env = CanvasListTestS2LEnv(
    task_dir="/path/to/task",
    num_courses=10,          # 课程数量
    num_students=3,          # 学生数量
    quiz_prob=0.8,           # Quiz 概率
    assignment_prob=0.7,     # Assignment 概率
    submission_prob=0.3,     # 已提交概率
    exemption_prob=0.1,      # 免修概率
    exemption_meet_prob=0.6, # 达到免修要求的概率
    no_exam_prob=0.15,       # 无考试概率
    quiz_difficulty="medium", # Quiz 难度
    assignment_difficulty="medium", # Assignment 难度
    seed=42                  # 随机种子
)

# 调用 reset() - 自动执行完整的预处理流程
# 包括：生成配置、清空数据库、创建课程、提交作业
instructions, info = env.reset()

# 获取任务指令
print("任务指令:")
print(instructions)

# info 为空字典 {}
print(f"Info: {info}")  # 输出: Info: {}
```

### 2. 分步执行（高级用法）

如果需要更细粒度的控制，可以分步执行：

```python
from gem.envs.canvas_list_test_s2l import CanvasListTestS2LEnv

# 创建环境
env = CanvasListTestS2LEnv(task_dir="/path/to/task", num_courses=5)

# 仅生成配置（不执行预处理）
stats = env.generate_config()

# 然后可以手动操作数据库或配置文件
# ...

# 或者通过 reset() 执行完整的预处理流程
instructions, info = env.reset()
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `task_dir` | str | None | 任务目录路径 |
| `num_courses` | int | 10 | 课程数量 |
| `num_students` | int | 3 | 学生数量 |
| `quiz_prob` | float | 0.8 | 每个课程有测验的概率 (0-1) |
| `assignment_prob` | float | 0.7 | 每个课程有作业的概率 (0-1) |
| `submission_prob` | float | 0.3 | 作业已提交的概率 (0-1) |
| `exemption_prob` | float | 0.1 | 课程可免修的概率 (0-1) |
| `exemption_meet_prob` | float | 0.6 | Ryan 达到免修要求的概率 (0-1) |
| `no_exam_prob` | float | 0.15 | 课程无考试的概率 (0-1) |
| `quiz_difficulty` | str | "medium" | 测验难度 (easy/medium/hard) |
| `assignment_difficulty` | str | "medium" | 作业难度 (easy/medium/hard) |
| `seed` | int | 42 | 随机种子 |

## 生成的文件

调用 `generate_config()` 后，会在 `task_dir` 下生成以下文件：

```
task_dir/
├── files/
│   ├── course_config.json         # 课程配置
│   ├── canvas_users.json          # 用户信息
│   └── submission_config.json     # 提交状态
├── initial_workspace/
│   └── memory/
│       └── memory.json            # Ryan Brown 的记忆
└── groundtruth_workspace/
    ├── quiz_info.csv              # Quiz groundtruth
    └── assignment_info.csv        # Assignment groundtruth
```

## 返回值

`generate_config()` 返回一个包含统计信息的字典：

```python
{
    'courses': 10,                  # 总课程数
    'total_exemption_courses': 1,   # 有免修机制的课程数
    'qualified_exemptions': 1,      # Ryan 达到免修要求的课程数
    'unqualified_exemptions': 0,    # Ryan 未达到免修要求的课程数
    'quizzes': 8,                   # 总测验数
    'assignments': 7,               # 总作业数
    'total_tasks': 15,              # 总任务数
    'submitted': 2,                 # 已提交数
    'remaining': 13,                # 需完成数
    'groundtruth_quizzes': 7,       # Groundtruth 中的测验数
    'groundtruth_assignments': 5,   # Groundtruth 中的作业数
    'groundtruth_total': 12         # Groundtruth 总任务数
}
```

## 示例

查看 `example_usage.py` 获取完整示例。

## 注意事项

1. **目录结构**: 确保 `generate_task_config.py` 与 `canvas_list_test_s2l.py` 在同一目录
2. **免修机制**: 达到免修要求的课程不会出现在 groundtruth 中
3. **已提交作业**: 已提交的作业不会出现在 groundtruth 中
4. **Groundtruth**: groundtruth CSV 文件按截止时间和课程代码排序

## 依赖

- `gem.core.Env`
- `gem.tools.mcp_server.canvas.database.CanvasDatabase`
- `generate_task_config.TaskConfigGenerator`

## reset() 方法详解

`reset()` 方法会自动执行以下预处理步骤：

1. **生成任务配置** (`generate_config()`)
   - 生成课程配置文件（`course_config.json`）
   - 生成用户配置文件（`canvas_users.json`）
   - 生成提交配置文件（`submission_config.json`）
   - 生成 Ryan Brown 的记忆文件（`memory.json`）
   - 生成 groundtruth CSV 文件

2. **清空本地数据库**
   - 删除所有现有课程、用户、注册等数据
   - 保留默认账户

3. **创建课程**
   - 更新课程截止日期为未来时间
   - 更新 CSV 文件（应用免修和提交过滤）
   - 创建所有课程和教师账户
   - 创建 Quiz 和 Assignment
   - 创建免修政策公告（如适用）
   - 注册所有学生

4. **提交学生作业**
   - 根据 `submission_config.json` 为 Ryan Brown 提交作业
   - 生成随机提交时间

5. **复制初始CSV模板**
   - 将 `quiz_info.csv` 模板复制到 agent_workspace
   - 将 `assignment_info.csv` 模板复制到 agent_workspace
   - 这些文件包含示例格式，供 Agent 参考

### 返回值

`reset()` 返回 `(instructions, info)` 元组：
- `instructions`: 任务指令字符串（通过 `_get_instructions()` 获取）
- `info`: 空字典 `{}`

任务指令内容：
```
My personal information is all stored in memory. Based on the course 
information on Canvas, as well as my assignment and quiz submission status. 
Find all my unfinished course assignments and quizzes that have to be 
completed (find all assignments and quizzes that I must submit, as according 
to information released by the teachers in announcements, some content may 
not need to be submitted), organize the information according to the required 
fields in the workspace's CSV header, keeping the format consistent with 
these examples, and complete these CSV files. In filling the files, please 
fill the quizzes/assignments in chronological order by their deadlines (DDL), 
and for quizzes/assignmen with the same DDL, sort them in the dictionary 
order of the class code. You should directly edit in the given 2 CSV files 
without changing their file names.
```

## 版本历史

- **v1.2.3** (2025-10-06): 修复事件循环关闭错误（使用持久事件循环）
- **v1.2.2** (2025-10-06): 在 `reset()` 中添加CSV模板文件复制步骤
- **v1.2.1** (2025-10-06): 修改 `reset()` 返回值格式，添加 `_get_instructions()` 方法
- **v1.2.0** (2025-10-06): 将预处理流程集成到 `reset()` 方法
- **v1.1.0** (2025-10-06): 将配置参数移至 `__init__` 方法
- **v1.0.0** (2025-10-05): 初始版本

## 技术细节

### 事件循环管理 (v1.2.3+)

环境使用持久的 asyncio 事件循环来避免 "Event loop is closed" 错误：

- 在 `__init__` 中创建事件循环，与环境实例生命周期一致
- 在 `reset()` 中使用 `loop.run_until_complete()` 执行异步操作
- 在 `__del__` 中正确清理所有待处理任务并关闭事件循环

这确保了所有 subprocess（如 Canvas MCP stdio server）可以在事件循环关闭前正常清理。


