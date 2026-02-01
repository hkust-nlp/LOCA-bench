#!/usr/bin/env python3
"""
演示 JSON 文件和 SQLite 数据库之间的关联关系
"""

import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

from database_utils import GoogleCloudDatabase


def print_section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def main():
    print_section("JSON 文件和 SQLite 数据库关联演示")
    
    db = GoogleCloudDatabase()
    
    # ==================== 步骤 1: 查看 JSON 元数据 ====================
    print_section("步骤 1: 查看 JSON 元数据")
    
    # 读取表元数据
    tables_file = os.path.join(db.data_dir, "bigquery_tables.json")
    with open(tables_file, 'r') as f:
        tables = json.load(f)
    
    # 选择一个表来演示
    table_key = "project-1:sales_dataset.transactions"
    if table_key in tables:
        table_info = tables[table_key]
        print(f"\n📋 JSON 元数据（{table_key}）:")
        print(f"  - 表 ID: {table_info['tableId']}")
        print(f"  - 项目 ID: {table_info['projectId']}")
        print(f"  - 数据集 ID: {table_info['datasetId']}")
        print(f"  - 记录的行数: {table_info['numRows']}")
        print(f"  - 最后修改: {table_info['modified']}")
        print(f"\n  Schema (前 3 列):")
        for field in table_info['schema'][:3]:
            print(f"    - {field['name']}: {field['type']} ({field['mode']})")
    
    # ==================== 步骤 2: 查看 SQLite 实际数据 ====================
    print_section("步骤 2: 查看 SQLite 实际数据")
    
    # 连接到 SQLite 数据库
    sqlite_db = os.path.join(db.data_dir, "bigquery_data.db")
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    
    # 查看表结构
    table_name = "project-1_sales_dataset_transactions"
    print(f"\n🗄️  SQLite 表结构（{table_name}）:")
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]}: {col[2]} {'NOT NULL' if col[3] else ''}")
    
    # 查看实际行数
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    actual_row_count = cursor.fetchone()[0]
    print(f"\n📊 SQLite 实际行数: {actual_row_count}")
    
    # 查看几行数据
    print(f"\n📝 SQLite 数据示例（前 3 行）:")
    cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
    rows = cursor.fetchall()
    for i, row in enumerate(rows, 1):
        print(f"  Row {i}: transaction_id={row[0]}, amount={row[2]}")
    
    conn.close()
    
    # ==================== 步骤 3: 演示关联 - 插入数据 ====================
    print_section("步骤 3: 演示关联 - 插入数据")
    
    print("\n🔄 插入新数据...")
    new_row = [{
        "transaction_id": "txn_demo_relation",
        "customer_id": "cust_demo",
        "amount": 999.99,
        "currency": "USD",
        "timestamp": "2024-02-01T15:00:00Z"
    }]
    
    # 记录插入前的状态
    print(f"\n插入前:")
    print(f"  - JSON 元数据显示行数: {table_info['numRows']}")
    
    # 插入数据
    success = db.insert_table_rows("project-1", "sales_dataset", "transactions", new_row)
    print(f"  - 插入操作: {'✅ 成功' if success else '❌ 失败'}")
    
    # 检查插入后的状态
    print(f"\n插入后:")
    
    # 1. JSON 元数据自动更新了
    with open(tables_file, 'r') as f:
        tables_updated = json.load(f)
    table_info_updated = tables_updated[table_key]
    print(f"  - JSON 元数据更新后行数: {table_info_updated['numRows']}")
    print(f"  - JSON 修改时间更新: {table_info_updated['modified']}")
    
    # 2. SQLite 数据也增加了
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    new_row_count = cursor.fetchone()[0]
    print(f"  - SQLite 实际行数: {new_row_count}")
    
    # 验证新数据确实存在
    cursor.execute(f'SELECT * FROM "{table_name}" WHERE transaction_id = "txn_demo_relation"')
    new_data = cursor.fetchone()
    if new_data:
        print(f"  - ✅ 在 SQLite 中找到新数据: {new_data[0]}, amount={new_data[2]}")
    
    conn.close()
    
    # ==================== 步骤 4: 演示关联 - 查询缓存 ====================
    print_section("步骤 4: 演示关联 - 查询缓存")
    
    # 执行查询
    query = f'SELECT * FROM `project-1.sales_dataset.transactions` WHERE transaction_id = "txn_demo_relation"'
    print(f"\n🔍 执行查询: {query}")
    
    result = db.run_bigquery_query(query)
    print(f"  - 查询状态: {result['status']}")
    print(f"  - 返回行数: {result['totalRows']}")
    print(f"  - 是否缓存: {result.get('cached', False)}")
    
    # 查看缓存文件
    cache_file = os.path.join(db.data_dir, "query_results.json")
    with open(cache_file, 'r') as f:
        cache = json.load(f)
    print(f"\n💾 查询结果已缓存到 query_results.json")
    print(f"  - 缓存的查询数: {len(cache)}")
    
    # 再次执行相同查询
    print(f"\n🔍 再次执行相同查询...")
    result2 = db.run_bigquery_query(query)
    print(f"  - 是否使用缓存: {result2.get('cached', False)}")
    
    # ==================== 步骤 5: 演示关联 - 删除数据 ====================
    print_section("步骤 5: 演示关联 - 删除数据")
    
    print(f"\n🗑️  删除测试数据...")
    deleted = db.delete_table_rows("project-1", "sales_dataset", "transactions",
                                   "transaction_id = 'txn_demo_relation'")
    print(f"  - 删除了 {deleted} 行")
    
    # 检查删除后的状态
    print(f"\n删除后:")
    
    # 1. JSON 元数据又更新了
    with open(tables_file, 'r') as f:
        tables_final = json.load(f)
    table_info_final = tables_final[table_key]
    print(f"  - JSON 元数据行数恢复: {table_info_final['numRows']}")
    
    # 2. SQLite 数据被删除
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    final_row_count = cursor.fetchone()[0]
    print(f"  - SQLite 行数恢复: {final_row_count}")
    
    # 3. 缓存被清除
    with open(cache_file, 'r') as f:
        cache_final = json.load(f)
    print(f"  - 查询缓存被清除: {len(cache_final)} 个缓存")
    
    conn.close()
    
    # ==================== 总结 ====================
    print_section("总结：JSON 和 SQLite 的关联")
    
    print("""
✅ 关联关系总结:

1. **Schema 定义（JSON → SQLite）**
   - JSON 文件定义表的 schema（列名、类型）
   - SQLite 根据 schema 创建表结构
   - 关系：JSON 是"设计图"，SQLite 是"建筑"

2. **数据存储（SQLite + JSON）**
   - SQLite 存储实际的行数据
   - JSON 记录统计信息（行数、大小、修改时间）
   - 关系：SQLite 是"仓库"，JSON 是"清单"

3. **数据操作（双向同步）**
   - INSERT/UPDATE/DELETE 操作 SQLite
   - 自动更新 JSON 元数据
   - 关系：操作后自动同步，保持一致

4. **查询缓存（JSON）**
   - 查询结果缓存在 JSON 文件
   - 数据修改时清除缓存
   - 关系：缓存提高性能，修改时失效

5. **文件分工**
   ```
   bigquery_datasets.json    → 数据集配置
   bigquery_tables.json      → 表 schema + 统计
   bigquery_data.db          → 表的实际数据
   query_results.json        → 查询结果缓存
   storage_*.json            → Cloud Storage 元数据
   compute_*.json            → Compute Engine 元数据
   iam_*.json                → IAM 元数据
   ```

🎯 核心设计理念：
  - JSON → 元数据、配置、缓存（人类可读）
  - SQLite → 数据、查询（机器优化）
  - 自动同步 → 保持一致性
    """)
    
    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()

