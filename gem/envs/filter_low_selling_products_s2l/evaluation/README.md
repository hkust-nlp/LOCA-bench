# 评估脚本说明

## 概述

评估脚本用于验证 Agent 是否成功完成低销量产品筛选任务，包括：
1. 正确识别低销量商品（在库>90天 且 30天销量<10）
2. 将这些商品移动到 Outlet/Clearance 分类
3. 向所有订阅者发送包含商品列表的促销邮件

## 主要更新（支持动态难度）

### ✨ 新功能

1. **Groundtruth 元数据集成**
   - 自动读取 `groundtruth_workspace/generation_metadata.json`
   - 显示生成参数（商品数量、订阅者数量、随机种子等）
   - 对比预期的低销量商品和实际识别的商品

2. **增强的调试信息**
   - 显示预期的低销量商品列表
   - 对比预期与实际，标识差异
   - 提供更详细的诊断信息

3. **向后兼容**
   - 如果没有 groundtruth 元数据，仍然使用动态计算
   - 支持旧的硬编码数据格式

## 使用方法

### 基本用法

```bash
python evaluation/main.py \
  --agent_workspace /path/to/agent_workspace \
  --groundtruth_workspace /path/to/groundtruth_workspace
```

### 参数说明

- `--agent_workspace` (必需): Agent 工作空间路径
- `--groundtruth_workspace` (可选): Groundtruth 工作空间路径
  - 如果提供，会读取 `generation_metadata.json`
  - 如果不提供，使用纯动态评估
- `--res_log_file` (可选): 结果日志文件路径
- `--launch_time` (可选): 启动时间

## 评估流程

### 1. 初始化

```
🚀 Low-Selling Products Filter Evaluation (Local Database)
============================================================

📂 Database Directories:
   WooCommerce: /path/to/local_db/woocommerce
   Email: /path/to/local_db/emails

📋 Loaded groundtruth metadata:
   • Low-selling products: 5
   • Normal-selling products: 5
   • Subscribers: 3
   • Total products: 10
   • Random seed: 42
```

### 2. 检查 WooCommerce & Email 服务

#### 步骤 A: 显示 Groundtruth 信息

```
📊 Groundtruth 元数据信息:
   预期低销量商品: 5 个
   预期正常商品: 5 个
   订阅者数量: 3 个

   预期低销量商品列表（共5个）:
      1. Samsung Monitor v15
      2. LG Phone 2022
      3. Sony TV v8
      4. Xiaomi Tablet 2021
      5. Dell Laptop v3
```

#### 步骤 B: 检查产品分类移动

```
🏷️ 检查 Product Categories和移动...

🔍 对比预期与实际的低销量商品:
   预期: 5 个
   实际识别: 5 个
   ✅ 识别结果与预期完全一致

📋 低销量商品排序结果 (共 5 个):
============================================================
1. Samsung Monitor v15
   在库天数: 245天
   30天销量: 2
   原价: $199.99, 现价: $99.99
   折扣率: 0.500 (50.0% off)
...

🔍 找到Outlet分类: Outlet/Clearance
✅ 5/5 个低销量商品已移动到Outlet分类
```

#### 步骤 C: 检查邮件发送

```
📧 检查邮件发送...
📋 找到 5 个低销量商品用于促销
👥 需要检查 3 个订阅者的邮件

🔍 开始检查所有用户的发送邮件...
   ✅ 找到发送给 john@mcpt.com 的匹配邮件
   ✅ 找到发送给 mike@mcpt.com 的匹配邮件
   ✅ 找到发送给 tom@mcpt.com 的匹配邮件

✅ 3/3 个订阅者收到了正确的促销邮件
```

### 3. 评估总结

```
============================================================
EVALUATION SUMMARY
============================================================
WooCommerce & Email Services: ✅ PASSED

Overall: 1/1 tests passed - ✅ ALL TESTS PASSED!

🎉 Low-selling products filter evaluation completed successfully!

✅ Successfully filtered low-selling products from WooCommerce
✅ Successfully sent notification email with product list
```

## 评估标准

### Product Categories 检查

**通过条件：**
- ✅ 存在 Outlet/Clearance 分类
- ✅ 所有低销量商品（在库>90天 且 30天销量<10）都已移动到该分类
- ✅ 没有正常销量商品被错误移动到该分类

**判断逻辑：**
```python
# 低销量商品条件
days_in_stock > 90 and sales_30_days < 10
```

### 邮件发送检查

**通过条件：**
- ✅ 所有订阅者都收到了邮件
- ✅ 邮件内容包含所有低销量商品
- ✅ 商品信息格式正确（名称 - 原价 - 促销价）
- ✅ 商品顺序正确（按入库时间从早到晚，折扣率从小到大）

**邮件内容格式：**
```
Product Name 1 - Original Price: $XX.XX - Promotional Price: $YY.YY
Product Name 2 - Original Price: $XX.XX - Promotional Price: $YY.YY
...
```

## Groundtruth 元数据格式

`groundtruth_workspace/generation_metadata.json`:

```json
{
  "generation_params": {
    "num_low_selling": 5,
    "num_normal_selling": 5,
    "num_subscribers": 3,
    "seed": 42,
    "total_products": 10
  },
  "low_selling_products": [
    "Samsung Monitor v15",
    "LG Phone 2022",
    ...
  ],
  "normal_selling_products": [
    "Dell Laptop 2025",
    ...
  ],
  "subscribers": [
    "john@mcpt.com",
    "mike@mcpt.com",
    ...
  ],
  "timestamp": "2025-01-01T10:00:00"
}
```

## 对比功能

### 预期 vs 实际

评估脚本会对比：
1. **预期的低销量商品** (从 generation_metadata.json)
2. **实际识别的低销量商品** (从数据库动态计算)

如果不一致，会显示：
- 缺失的商品（预期有但未识别）
- 额外的商品（识别了但不在预期中）

**注意：** 如果商品数据在任务执行中被修改（如销量或日期变化），可能导致差异。

## 错误处理

### 常见错误场景

1. **未找到 Outlet/Clearance 分类**
   ```
   ❌ 未找到Outlet/Clearance分类
   ```
   → Agent 需要创建该分类

2. **低销量商品未移动**
   ```
   ❌ 只有 3/5 个低销量商品在Outlet分类中
   未移动的商品: ['Product A', 'Product B']
   ```
   → Agent 需要移动所有低销量商品

3. **正常商品被错误移动**
   ```
   ❌ 发现 2 个不应在Outlet分类的商品
   ```
   → Agent 错误识别了商品

4. **邮件未发送或内容不正确**
   ```
   ❌ 0/3 个订阅者收到了正确的促销邮件
   ```
   → Agent 需要发送邮件给所有订阅者

## 调试建议

### 1. 查看 Groundtruth 元数据

```bash
cat groundtruth_workspace/generation_metadata.json | python -m json.tool
```

### 2. 检查数据库状态

```python
from mcps.woocommerce.database_utils import WooCommerceDatabase
db = WooCommerceDatabase(data_dir="/path/to/local_db/woocommerce")

# 查看所有商品
products = db.list_products()
print(f"Total products: {len(products)}")

# 查看分类
categories = list(db.categories.values())
for cat in categories:
    print(f"{cat['name']}: {cat['id']}")
```

### 3. 检查邮件数据库

```python
from mcps.email.database_utils import EmailDatabase
db = EmailDatabase(data_dir="/path/to/local_db/emails")

# 查看所有用户
print(f"Users: {list(db.users.keys())}")

# 查看某个用户的邮件
emails = db.list_emails("admin@woocommerce.local")
print(f"Sent emails: {len([e for e in emails if e.get('folder') == 'Sent'])}")
```

## 版本兼容性

### 支持的模式

1. **新版（推荐）**: 使用动态生成数据 + Groundtruth 元数据
   - ✅ 完整的对比功能
   - ✅ 详细的调试信息
   - ✅ 可追溯的生成参数

2. **旧版（兼容）**: 使用硬编码数据
   - ✅ 纯动态计算
   - ⚠️  无元数据对比
   - ⚠️  无生成参数信息

## 输出文件

评估脚本不生成输出文件，所有结果都输出到控制台。

建议重定向输出以保存日志：

```bash
python evaluation/main.py \
  --agent_workspace /path/to/workspace \
  --groundtruth_workspace /path/to/groundtruth \
  2>&1 | tee evaluation_log.txt
```

## 退出码

- `0`: 评估通过
- `1`: 评估失败或发生错误




