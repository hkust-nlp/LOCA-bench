# 低销量产品筛选任务 - 数据生成与难度控制

## 概述

本任务支持动态生成商品数据和订阅者数据，并提供难度预设来控制任务复杂度。

## 功能特性

### 1. 动态数据生成

- **低销量商品**：满足条件（在库>90天，30天销量<10）的商品
- **正常销量商品**：不满足低销量条件的对照组商品
- **订阅者**：接收促销邮件的订阅者列表

### 2. 难度控制

通过控制以下参数来调整任务难度：
- 低销量商品数量
- 正常销量商品数量
- 订阅者数量

## 使用方法

### 基本用法

```bash
python main.py --agent_workspace /path/to/workspace
```

### 使用难度预设

#### Easy 模式
```bash
python main.py --agent_workspace /path/to/workspace --difficulty easy
```
- 低销量商品: 3 个
- 正常销量商品: 2 个
- 订阅者: 2 个

#### Medium 模式（默认）
```bash
python main.py --agent_workspace /path/to/workspace --difficulty medium
```
- 低销量商品: 5 个
- 正常销量商品: 5 个
- 订阅者: 3 个

#### Hard 模式
```bash
python main.py --agent_workspace /path/to/workspace --difficulty hard
```
- 低销量商品: 10 个
- 正常销量商品: 15 个
- 订阅者: 5 个

#### Expert 模式
```bash
python main.py --agent_workspace /path/to/workspace --difficulty expert
```
- 低销量商品: 20 个
- 正常销量商品: 30 个
- 订阅者: 10 个

#### Extreme 模式
```bash
python main.py --agent_workspace /path/to/workspace --difficulty extreme
```
- 低销量商品: 50 个
- 正常销量商品: 100 个
- 订阅者: 25 个

#### Insane 模式（最高难度）
```bash
python main.py --agent_workspace /path/to/workspace --difficulty insane
```
- 低销量商品: 100 个
- 正常销量商品: 200 个
- 订阅者: 50 个

### 自定义参数

```bash
python main.py --agent_workspace /path/to/workspace \
  --num-low-selling 15 \
  --num-normal-selling 20 \
  --num-subscribers 8 \
  --seed 123
```

### 跳过数据生成

使用现有的数据文件而不重新生成：

```bash
python main.py --agent_workspace /path/to/workspace --skip-generation
```

## 命令行参数说明

### 必需参数

- `--agent_workspace`: Agent 工作空间路径

### 可选参数

#### 难度预设
- `--difficulty`: 难度级别 (easy/medium/hard/expert)
  - 会覆盖其他数据生成参数

#### 数据生成参数
- `--num-low-selling`: 低销量商品数量（默认: 5）
- `--num-normal-selling`: 正常销量商品数量（默认: 3）
- `--num-subscribers`: 订阅者数量（默认: 3）
- `--seed`: 随机种子（默认: 42）

#### 其他
- `--skip-generation`: 跳过数据生成，使用现有文件
- `--launch_time`: 启动时间（可选）

## 生成的文件

### preprocess/generated_products.json
包含所有生成的商品数据（低销量 + 正常销量）

### initial_workspace/subscriber.json
包含订阅者列表，格式：
```json
{
  "subscriber_list": [
    {
      "email": "user@mcpt.com",
      "name": "User Name"
    }
  ]
}
```

### groundtruth_workspace/generation_metadata.json
包含生成元数据和 groundtruth 信息：
```json
{
  "generation_params": {
    "num_low_selling": 5,
    "num_normal_selling": 3,
    "num_subscribers": 3,
    "seed": 42,
    "total_products": 8
  },
  "low_selling_products": ["产品名称列表"],
  "normal_selling_products": ["产品名称列表"],
  "subscribers": ["邮箱列表"],
  "timestamp": "ISO时间戳"
}
```

## 数据特征

### 低销量商品特征
- 在库时间: 91-365 天
- 30天销量: 0-9 件
- 价格折扣: 10%-50%

### 正常销量商品特征
三种类型：
1. **短时在库型**: 在库 < 90天，销量任意
2. **高销量型**: 在库 > 90天，但销量 >= 10
3. **完美型**: 在库短 + 销量高

## 难度对比

| 难度 | 低销量商品 | 正常销量商品 | 订阅者 | 总商品数 | 推荐场景 |
|------|-----------|-------------|--------|---------|---------|
| Easy | 3 | 2 | 2 | 5 | 快速测试 |
| Medium | 5 | 5 | 3 | 10 | 标准评估 |
| Hard | 10 | 15 | 5 | 25 | 常规压测 |
| Expert | 20 | 30 | 10 | 50 | 高级压测 |
| Extreme | 50 | 100 | 25 | 150 | 性能极限 |
| Insane | 100 | 200 | 50 | 300 | 终极挑战 |

## 示例工作流

### 1. 生成新数据并运行（Medium 难度）
```bash
python main.py --agent_workspace ./workspace --difficulty medium
```

### 2. 生成自定义数据
```bash
python main.py --agent_workspace ./workspace \
  --num-low-selling 8 \
  --num-normal-selling 12 \
  --num-subscribers 6
```

### 3. 使用现有数据测试
```bash
python main.py --agent_workspace ./workspace --skip-generation
```

## 大规模数据支持

### 超高难度级别

系统支持生成上百甚至上千个商品和订阅者：

```bash
# Extreme 难度: 150 商品, 25 订阅者
python main.py --agent_workspace /path --difficulty extreme

# Insane 难度: 300 商品, 50 订阅者
python main.py --agent_workspace /path --difficulty insane

# 自定义超大规模: 500+ 商品, 100+ 订阅者
python main.py --agent_workspace /path \
  --num-low-selling 200 \
  --num-normal-selling 400 \
  --num-subscribers 120
```

### 性能考虑

| 规模 | 商品数 | 生成时间 | 数据库大小 | 内存占用 |
|-----|-------|---------|-----------|---------|
| Small | 5-25 | < 5秒 | < 1MB | < 10MB |
| Medium | 25-100 | 5-15秒 | 1-5MB | 10-30MB |
| Large | 100-300 | 15-30秒 | 5-15MB | 30-80MB |
| XLarge | 300-1000 | 30-120秒 | 15-50MB | 80-200MB |

### 优化建议

1. **固定种子**: 使用相同的 `--seed` 避免重复生成
2. **增量测试**: 从小规模开始，逐步增加
3. **监控资源**: 大规模数据时注意内存和磁盘使用
4. **缓存数据**: 生成一次，多次使用 `--skip-generation`

## 注意事项

1. **随机种子**: 使用相同的 seed 会生成相同的数据，便于复现测试
2. **数据库清理**: 每次运行都会清空并重建数据库
3. **文件覆盖**: 生成的文件会覆盖现有文件
4. **难度预设优先**: 使用 `--difficulty` 会覆盖单独设置的数量参数
5. **商品数量限制**: 建议不超过1000个商品以保证性能
6. **订阅者限制**: 建议不超过200个订阅者以保证邮件检查性能

## 故障排除

### 数据生成失败
检查 `generate_products_data.py` 脚本是否存在于 `preprocess/` 目录

### 商品未正确插入数据库
确保 `generated_products.json` 文件格式正确

### 订阅者数据未生成
检查 `initial_workspace/subscriber.json` 是否正确创建

## 相关文件

- `main.py`: 主预处理脚本
- `generate_products_data.py`: 数据生成脚本
- `setup_test_products.py`: 旧版商品设置（已不使用）

