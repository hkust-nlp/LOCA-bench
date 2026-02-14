#!/usr/bin/env python3
"""
WooCommerce New Welcome Task - Preprocess Setup
设置初始工作环境：清空邮箱、设置WooCommerce订单数据、准备BigQuery环境
使用本地数据库 (WooCommerce + Email + Google Cloud)
"""
import os
import sys
import json
import time
import shutil
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to import token configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
task_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(task_dir)))
sys.path.insert(0, task_dir)  # For token_key_session
sys.path.insert(0, project_root)  # For utils
from gem.utils.filesystem import nfs_safe_rmtree
# 添加 mcp_convert 路径以导入数据库工具
from mcp_convert.mcps.woocommerce.database_utils import WooCommerceDatabase
from mcp_convert.mcps.woocommerce.order_generator import create_new_welcome_orders
from mcp_convert.mcps.woocommerce.init_database import initialize_database as init_woocommerce_db
from mcp_convert.mcps.email.database_utils import EmailDatabase
from mcp_convert.mcps.google_cloud.database_utils import GoogleCloudDatabase


def clear_email_database(db: EmailDatabase, user_email: str) -> bool:
    """清理指定用户的邮箱数据"""
    print(f"🗑️  清理邮箱数据库: {user_email}...")
    
    try:
        # 获取用户数据目录
        user_dir = db._get_user_data_dir(user_email)
        
        # 如果用户数据不存在，创建空的
        if not Path(user_dir).exists():
            Path(user_dir).mkdir(parents=True, exist_ok=True)
            # 创建空的邮件、文件夹和草稿文件
            db._save_json_file(os.path.join(user_dir, "emails.json"), {})
            db._save_json_file(os.path.join(user_dir, "folders.json"), {
                "INBOX": {"total": 0, "unread": 0},
                "Sent": {"total": 0, "unread": 0},
                "Trash": {"total": 0, "unread": 0}
            })
            db._save_json_file(os.path.join(user_dir, "drafts.json"), {})
            print(f"   ✓ 创建新用户数据: {user_email}")
        else:
            # 清空现有数据
            db._save_json_file(os.path.join(user_dir, "emails.json"), {})
            db._save_json_file(os.path.join(user_dir, "folders.json"), {
                "INBOX": {"total": 0, "unread": 0},
                "Sent": {"total": 0, "unread": 0},
                "Trash": {"total": 0, "unread": 0}
            })
            db._save_json_file(os.path.join(user_dir, "drafts.json"), {})
            print(f"   ✓ 清理完成: {user_email}")
        
        return True
    except Exception as e:
        print(f"   ❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def ensure_users_exist(db: EmailDatabase, users_info: List[Dict]) -> bool:
    """确保用户在数据库中存在"""
    print(f"👥 确保 {len(users_info)} 个用户存在于数据库...")
    
    try:
        # 读取或初始化 users.json
        if not db.users:
            db.users = {}
        
        for user_info in users_info:
            email = user_info['email']
            password = user_info.get('password', 'default_password')
            name = user_info.get('name', email.split('@')[0])
            
            # 如果用户不存在，添加
            if email not in db.users:
                db.users[email] = {
                    "email": email,
                    "password": password,
                    "name": name
                }
                print(f"   ✓ 创建用户: {name} ({email})")
            else:
                # 更新密码和名称
                db.users[email]["password"] = password
                db.users[email]["name"] = name
                print(f"   ✓ 更新用户: {name} ({email})")
        
        # 保存 users.json
        db._save_json_file("users.json", db.users)
        print(f"✅ 用户数据已保存")
        
        return True
    except Exception as e:
        print(f"❌ 用户初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def clear_mailbox(email_db: EmailDatabase, admin_email: str) -> Dict:
    """
    清空邮箱 - 使用本地数据库清理邮箱

    Returns:
        清理结果字典
    """
    print("📧 开始清空邮箱...")

    try:
        # 清理管理员邮箱
        if clear_email_database(email_db, admin_email):
            return {
                "success": True,
                "cleared_folders": ["INBOX", "Sent", "Trash"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "邮箱清理失败",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        print(f"❌ 邮箱清理过程中出错: {e}")
        return error_result


def setup_woocommerce_orders(
    woocommerce_db_dir: str, 
    task_root: Path,
    total_orders: int = 30,
    first_time_customer_count: int = 12,
    noise_orders_outside_window: int = 0,
    noise_orders_incomplete: int = 0,
    seed: int = None
) -> Dict:
    """
    设置WooCommerce订单数据：清空现有订单并添加新的首次购买订单

    Args:
        woocommerce_db_dir: WooCommerce数据库目录
        task_root: 任务根目录
        total_orders: 总订单数量
        first_time_customer_count: 首次客户数量
        noise_orders_outside_window: 7天外噪声订单数量
        noise_orders_incomplete: 未完成噪声订单数量
        seed: 随机种子

    Returns:
        设置结果字典
    """
    print("🛍️ 设置WooCommerce订单数据...")
    print(f"   总订单数: {total_orders}")
    print(f"   首次客户数: {first_time_customer_count}")
    print(f"   噪声订单(7天外): {noise_orders_outside_window}")
    print(f"   噪声订单(未完成): {noise_orders_incomplete}")
    print(f"   随机种子: {seed}")

    try:
        # 延迟导入WooCommerce模块
        try:
            from mcps.woocommerce.order_generator import create_new_welcome_orders
        except ImportError as e:
            print(f"❌ 无法导入WooCommerce模块: {e}")
            return {
                "success": False,
                "error": f"无法导入WooCommerce模块: {e}",
                "timestamp": datetime.now().isoformat()
            }

        # 第一步：清空现有数据库
        print("🗑️ 清空现有WooCommerce数据库...")
        if Path(woocommerce_db_dir).exists():
            nfs_safe_rmtree(woocommerce_db_dir)
            print(f"   ✓ 删除旧数据库")
        
        # 创建数据库目录
        Path(woocommerce_db_dir).mkdir(parents=True, exist_ok=True)

        # 第二步：生成新订单数据
        print("📦 生成新订单数据...")
        all_orders, first_time_orders = create_new_welcome_orders(
            seed=seed,
            total_orders=total_orders,
            first_time_customer_count=first_time_customer_count,
            noise_orders_outside_window=noise_orders_outside_window,
            noise_orders_incomplete=noise_orders_incomplete
        )

        # 第三步：初始化数据库并插入订单
        print("📤 初始化数据库并插入订单...")
        init_woocommerce_db(woocommerce_db_dir, verbose=False, include_demo_data=False)
        
        # 获取数据库实例
        db = WooCommerceDatabase(data_dir=woocommerce_db_dir)
        
        # 插入客户和订单，同时收集客户信息
        successful_orders = 0
        failed_orders = 0
        customer_info = {}  # {email: {name, first_name, last_name}}
        
        for order in all_orders:
            try:
                # 从订单中提取客户信息（支持两种格式）
                # 格式1: customer_email + customer_name (从create_new_welcome_orders返回)
                customer_email = order.get('customer_email', '') or order.get('billing', {}).get('email', '')
                customer_name = order.get('customer_name', '')
                
                if customer_email:
                    # 收集客户信息
                    if customer_email not in customer_info:
                        # 从customer_name中分离first_name和last_name
                        if customer_name:
                            name_parts = customer_name.split(' ', 1)
                            first_name = name_parts[0] if len(name_parts) > 0 else ''
                            last_name = name_parts[1] if len(name_parts) > 1 else ''
                        else:
                            first_name = order.get('billing', {}).get('first_name', '')
                            last_name = order.get('billing', {}).get('last_name', '')
                            customer_name = f"{first_name} {last_name}".strip()
                        
                        customer_info[customer_email] = {
                            'email': customer_email,
                            'first_name': first_name,
                            'last_name': last_name,
                            'name': customer_name or customer_email.split('@')[0]
                        }
                    
                    # 检查客户是否存在
                    existing_customers = [c for c in db.customers.values() 
                                        if c.get('email') == customer_email]
                    
                    if not existing_customers:
                        # 获取客户信息用于创建
                        cust_info = customer_info[customer_email]
                        # 创建新客户
                        customer_data = {
                            'email': customer_email,
                            'first_name': cust_info['first_name'],
                            'last_name': cust_info['last_name'],
                            'billing': order.get('billing', {}),
                            'shipping': order.get('shipping', {})
                        }
                        db.create_customer(customer_data)
                
                # 创建订单
                db.create_order(order)
                successful_orders += 1
            except Exception as e:
                print(f"      ⚠️  插入订单失败: {e}")
                failed_orders += 1

        print(f"📊 订单设置结果:")
        print(f"   生成新订单: {len(all_orders)} 个")
        print(f"   成功插入: {successful_orders} 个")
        print(f"   失败插入: {failed_orders} 个")
        print(f"   首次购买客户: {len(first_time_orders)} 个")
        print(f"   唯一客户数量: {len(customer_info)} 个")

        # 创建preprocess目录（如果不存在）
        preprocess_dir = task_root / "preprocess"
        preprocess_dir.mkdir(parents=True, exist_ok=True)

        # 保存订单数据到文件供评估使用
        orders_file = task_root / "preprocess" / "generated_orders.json"
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump({
                "all_orders": all_orders,
                "first_time_orders": first_time_orders
            }, f, ensure_ascii=False, indent=2)

        print(f"📄 订单数据已保存到: {orders_file}")

        return {
            "success": failed_orders == 0,
            "generated_orders": len(all_orders),
            "successful_uploads": successful_orders,
            "failed_uploads": failed_orders,
            "first_time_customers": len(first_time_orders),
            "orders_file": str(orders_file),
            "customer_info": list(customer_info.values())  # 返回客户信息列表
        }

    except Exception as e:
        error_msg = f"WooCommerce订单设置过程中出错: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": error_msg
        }


def main():
    """主预处理函数"""

    parser = ArgumentParser(description="Preprocess script - Set up the initial environment for the WooCommerce new welcome task")
    parser.add_argument("--agent_workspace", required=False, help="Agent工作空间路径")
    parser.add_argument("--launch_time", required=False, help="Launch time")
    
    # 数据生成控制参数
    parser.add_argument("--total-orders", type=int, default=20,
                       help="总订单数量 (默认: 30)")
    parser.add_argument("--first-time-customers", type=int, default=10,
                       help="首次购买客户数量 (默认: 12)")
    parser.add_argument("--noise-outside-window", type=int, default=0,
                       help="7天外噪声订单数量 (默认: 0)")
    parser.add_argument("--noise-incomplete", type=int, default=0,
                       help="未完成噪声订单数量 (默认: 0)")
    parser.add_argument("--seed", type=int, default=None,
                       help="随机种子 (默认: 使用当前时间)")
    
    # 难度预设
    parser.add_argument("--difficulty", type=str, default=None,
                       choices=["easy", "medium", "hard", "expert", "extreme"],
                       help="难度预设（可选，会覆盖其他参数）")
    
    args = parser.parse_args()
    
    # 应用难度预设
    if args.difficulty:
        print(f"🎲 使用难度预设: {args.difficulty.upper()}")
        
        if args.difficulty == "easy":
            # 简单：少量订单，高首次客户比例，无噪声
            args.total_orders = 20
            args.first_time_customers = 15
            args.noise_outside_window = 0
            args.noise_incomplete = 0
        elif args.difficulty == "medium":
            # 中等：中等订单数，中等首次客户比例，少量噪声
            args.total_orders = 30
            args.first_time_customers = 12
            args.noise_outside_window = 3
            args.noise_incomplete = 2
        elif args.difficulty == "hard":
            # 困难：较多订单，低首次客户比例，中等噪声
            args.total_orders = 50
            args.first_time_customers = 15
            args.noise_outside_window = 8
            args.noise_incomplete = 5
        elif args.difficulty == "expert":
            # 专家：大量订单，更低首次客户比例，较多噪声
            args.total_orders = 80
            args.first_time_customers = 20
            args.noise_outside_window = 15
            args.noise_incomplete = 10
        elif args.difficulty == "extreme":
            # 极限：海量订单，很低首次客户比例，大量噪声
            args.total_orders = 120
            args.first_time_customers = 25
            args.noise_outside_window = 25
            args.noise_incomplete = 15
    else:
        print(f"🎲 使用自定义参数")
    
    print(f"\n📊 数据生成参数:")
    print(f"   总订单数: {args.total_orders}")
    print(f"   首次客户数: {args.first_time_customers}")
    print(f"   噪声(7天外): {args.noise_outside_window}")
    print(f"   噪声(未完成): {args.noise_incomplete}")
    print(f"   随机种子: {args.seed or '(自动)'}")

    print("\n" + "=" * 80)
    print("WooCommerce New Welcome Task - Preprocessing")
    print("=" * 80)
    print("使用本地数据库 (WooCommerce + Email + Google Cloud)")

    # 获取任务根目录
    # When agent_workspace is provided, task_root is its parent directory
    # Otherwise, assume we're in the code directory structure
    if args.agent_workspace:
        task_root = Path(args.agent_workspace).parent
    else:
        task_root = Path(__file__).parent.parent

    # 管理员账号配置
    admin_email = "admin@woocommerce.local"
    admin_password = "admin123"
    admin_name = "WooCommerce Admin"

    # 确定数据库目录
    if args.agent_workspace:
        workspace_parent = Path(args.agent_workspace).parent
        woocommerce_db_dir = str(workspace_parent / "local_db" / "woocommerce")
        email_db_dir = str(workspace_parent / "local_db" / "emails")
        gcloud_db_dir = str(workspace_parent / "local_db" / "google_cloud")
    else:
        woocommerce_db_dir = str(Path(__file__).parent.parent / "local_db" / "woocommerce")
        email_db_dir = str(Path(__file__).parent.parent / "local_db" / "emails")
        gcloud_db_dir = str(Path(__file__).parent.parent / "local_db" / "google_cloud")
    
    print(f"\n📂 数据库目录:")
    print(f"   WooCommerce: {woocommerce_db_dir}")
    print(f"   Email: {email_db_dir}")
    print(f"   Google Cloud: {gcloud_db_dir}")

    results = []

    try:
        # 第一步：初始化Email数据库并清空邮箱
        print("\n" + "="*60)
        print("Step 1: Setup Email Database and Clear Mailbox")
        print("="*60)

        # 清空并创建email数据库目录
        if Path(email_db_dir).exists():
            nfs_safe_rmtree(email_db_dir)
        Path(email_db_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化EmailDatabase
        email_db = EmailDatabase(data_dir=email_db_dir)
        
        # 创建管理员用户
        users_info = [
            {"email": admin_email, "password": admin_password, "name": admin_name}
        ]
        if not ensure_users_exist(email_db, users_info):
            print("❌ 用户创建失败")
            results.append(("Email Setup", False, {"error": "用户创建失败"}))
        else:
            mailbox_result = clear_mailbox(email_db, admin_email)
            results.append(("Mailbox Cleanup", mailbox_result["success"], mailbox_result))

            if mailbox_result["success"]:
                print("✅ 邮箱清理成功")
            else:
                print("⚠️ 邮箱清理部分失败，但继续后续操作...")

        # 第二步：设置WooCommerce订单
        print("\n" + "="*60)
        print("Step 2: Setup WooCommerce Orders")
        print("="*60)

        woocommerce_result = setup_woocommerce_orders(
            woocommerce_db_dir=woocommerce_db_dir,
            task_root=task_root,
            total_orders=args.total_orders,
            first_time_customer_count=args.first_time_customers,
            noise_orders_outside_window=args.noise_outside_window,
            noise_orders_incomplete=args.noise_incomplete,
            seed=args.seed
        )
        results.append(("WooCommerce Setup", woocommerce_result["success"], woocommerce_result))

        if woocommerce_result["success"]:
            print("✅ WooCommerce订单设置成功")
        else:
            print("❌ WooCommerce订单设置失败")
        
        # 第二步b：为所有WooCommerce客户创建Email用户文件夹
        print("\n" + "="*60)
        print("Step 2b: Create Email Folders for WooCommerce Customers")
        print("="*60)
        
        if "customer_info" in woocommerce_result and woocommerce_result["customer_info"]:
            customer_list = woocommerce_result["customer_info"]
            print(f"📧 为 {len(customer_list)} 个客户创建邮箱用户文件夹...")
            
            # 准备用户信息（添加默认密码）
            customer_users = []
            for customer in customer_list:
                customer_users.append({
                    "email": customer['email'],
                    "password": "customer123",  # 默认客户密码
                    "name": customer['name'] if customer['name'] else customer['email'].split('@')[0]
                })
            
            # 确保这些用户存在
            if ensure_users_exist(email_db, customer_users):
                # 为每个客户创建邮箱文件夹
                customer_email_success = 0
                customer_email_failed = 0
                
                for customer in customer_users:
                    if clear_email_database(email_db, customer['email']):
                        customer_email_success += 1
                    else:
                        customer_email_failed += 1
                
                email_setup_success = customer_email_failed == 0
                results.append(("Customer Email Setup", email_setup_success, {
                    "total_customers": len(customer_users),
                    "successful": customer_email_success,
                    "failed": customer_email_failed
                }))
                
                if email_setup_success:
                    print(f"✅ 成功为 {customer_email_success} 个客户创建邮箱文件夹")
                else:
                    print(f"⚠️ 部分客户邮箱创建失败: {customer_email_success} 成功, {customer_email_failed} 失败")
            else:
                results.append(("Customer Email Setup", False, {"error": "用户创建失败"}))
                print("❌ 客户用户创建失败")
        else:
            print("⚠️ 没有客户信息，跳过邮箱文件夹创建")
            results.append(("Customer Email Setup", True, {"message": "没有客户信息"}))

        # 第三步：设置BigQuery环境（使用本地GoogleCloud数据库）
        print("\n" + "="*60)
        print("Step 3: Setup BigQuery Environment")
        print("="*60)

        # 清空并创建google cloud数据库目录
        if Path(gcloud_db_dir).exists():
            nfs_safe_rmtree(gcloud_db_dir)
        Path(gcloud_db_dir).mkdir(parents=True, exist_ok=True)

        # 初始化GoogleCloudDatabase
        gcloud_db = GoogleCloudDatabase(data_dir=gcloud_db_dir)
        project_id = "local-project"

        # 复制customers_data.json到task_root/preprocess目录
        source_json_path = Path(current_dir) / "customers_data.json"
        dest_json_path = task_root / "preprocess" / "customers_data.json"

        if source_json_path.exists():
            print(f"📋 复制客户数据文件到任务目录...")
            shutil.copy2(source_json_path, dest_json_path)
            print(f"   源文件: {source_json_path}")
            print(f"   目标文件: {dest_json_path}")
            print(f"✅ 客户数据文件复制成功")
        else:
            print(f"⚠️  源客户数据文件不存在: {source_json_path}")

        # 读取客户数据（只插入历史客户，不包含首次客户）
        # 首次客户应该由 Agent 在执行任务时同步到 BigQuery
        json_path = dest_json_path
        if json_path.exists():
            json_data = read_json_data(str(json_path))
            
            try:
                dataset_id = setup_bigquery_resources_local(gcloud_db, project_id, json_data)
                results.append(("BigQuery Setup", True, {"dataset_id": dataset_id}))
                print("✅ BigQuery环境设置成功")
            except Exception as e:
                results.append(("BigQuery Setup", False, {"error": str(e)}))
                print(f"❌ BigQuery设置失败: {e}")
        else:
            results.append(("BigQuery Setup", False, {"error": "客户数据文件不存在"}))
            print("❌ 客户数据文件不存在")

        # 设置环境变量
        os.environ['WOOCOMMERCE_DATA_DIR'] = woocommerce_db_dir
        os.environ['EMAIL_DATA_DIR'] = email_db_dir
        os.environ['GOOGLE_CLOUD_DATA_DIR'] = gcloud_db_dir

        # 汇总结果
        print("\n" + "="*80)
        print("PREPROCESSING SUMMARY")
        print("="*80)

        success_count = sum(1 for _, success, _ in results if success)
        total_count = len(results)

        for step_name, success, details in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{step_name}: {status}")
            if not success and "error" in details:
                print(f"  Error: {details['error']}")

        overall_success = success_count == total_count
        print(f"\nOverall: {success_count}/{total_count} steps completed successfully")

        if overall_success:
            print("\n🎉 所有预处理步骤完成！任务环境已就绪")
            print(f"\n📂 数据库位置:")
            print(f"   WooCommerce: {woocommerce_db_dir}")
            print(f"   Email: {email_db_dir}")
            print(f"   Google Cloud: {gcloud_db_dir}")
            print(f"\n👤 管理员账号:")
            print(f"   Email: {admin_email}")
            print(f"   Password: {admin_password}")

            # CRITICAL: Close all database connections to release locks
            if 'db' in locals() and db:
                db.close()
                print("   ✓ WooCommerce database connection closed")
            # EmailDatabase doesn't have a close() method - it uses JSON, no connections
            if 'gcloud_db' in locals() and gcloud_db:
                gcloud_db.close()
                print("   ✓ Google Cloud database connection closed")

            return True
        else:
            print("\n⚠️ 预处理部分完成，请检查失败的步骤")

            # Close database connections on partial success path
            if 'db' in locals() and db:
                try:
                    db.close()
                    print("   ✓ WooCommerce database connection closed")
                except:
                    pass
            # EmailDatabase doesn't have a close() method
            if 'gcloud_db' in locals() and gcloud_db:
                try:
                    gcloud_db.close()
                    print("   ✓ Google Cloud database connection closed")
                except:
                    pass

            return False

    except Exception as e:
        print(f"❌ 预处理失败: {e}")

        # Close database connections on error path
        if 'db' in locals() and db:
            try:
                db.close()
                print("   ✓ WooCommerce database connection closed (error path)")
            except:
                pass
        # EmailDatabase doesn't have a close() method
        if 'gcloud_db' in locals() and gcloud_db:
            try:
                gcloud_db.close()
                print("   ✓ Google Cloud database connection closed (error path)")
            except:
                pass

        import traceback
        traceback.print_exc()
        return False


# 以下是BigQuery相关函数（使用本地数据库）

import logging

# Enable verbose logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def read_json_data(json_path: str):
    """从JSON文件读取客户数据"""
    print(f"📖 正在读取JSON数据文件: {json_path}")
    
    if not Path(json_path).exists():
        print(f"❌ JSON数据文件不存在: {json_path}")
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            customers = json.load(f)
        
        # 确保数据格式正确
        processed_customers = []
        for customer in customers:
            processed_customer = {
                'id': customer.get('id'),
                'woocommerce_id': customer.get('woocommerce_id'),
                'email': customer.get('email'),
                'first_name': customer.get('first_name'),
                'last_name': customer.get('last_name'),
                'phone': customer.get('phone', ''),
                'date_created': customer.get('date_created'),
                'first_order_date': customer.get('first_order_date'),
                'welcome_email_sent': customer.get('welcome_email_sent', False),
                'welcome_email_date': customer.get('welcome_email_date'),
                'sync_date': customer.get('sync_date'),
                'metadata': customer.get('metadata', '{}')
            }
            processed_customers.append(processed_customer)
        
        print(f"✅ 成功读取 {len(processed_customers)} 条客户记录")
        return processed_customers
        
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ 读取JSON数据文件时出错: {e}")
        return []


def setup_bigquery_resources_local(gcloud_db: GoogleCloudDatabase, project_id: str, json_data: list) -> str:
    """
    Setup BigQuery dataset and tables for WooCommerce CRM using local database
    
    Args:
        gcloud_db: GoogleCloudDatabase instance
        project_id: Project ID
        json_data: Customer data to insert
        
    Returns:
        Dataset ID
    """
    print("=" * 60)
    print("🛍️ 开始设置 BigQuery WooCommerce CRM 资源（本地数据库）")
    print("=" * 60)
    
    dataset_id = "woocommerce_crm"
    
    try:
        # 检查数据集是否存在，如果存在则删除
        existing_dataset = gcloud_db.get_bigquery_dataset(project_id, dataset_id)
        if existing_dataset:
            print(f"ℹ️  找到现有数据集 '{dataset_id}'，删除中...")
            # 删除所有表
            tables = gcloud_db.list_bigquery_tables(project_id, dataset_id)
            for table in tables:
                gcloud_db.delete_bigquery_table(project_id, dataset_id, table['tableId'])
            # 删除数据集
            gcloud_db.delete_bigquery_dataset(project_id, dataset_id)
            print(f"✅ 已删除现有数据集")
        
        # 创建新数据集
        print(f"📦 创建数据集 '{dataset_id}'...")
        dataset_info = {
            "location": "US",
            "description": "WooCommerce CRM dataset for customer management and welcome emails",
            "labels": {}
        }
        gcloud_db.create_bigquery_dataset(project_id, dataset_id, dataset_info)
        print(f"✅ 数据集 '{dataset_id}' 创建成功")
        
        # 创建customers表
        table_name = "customers"
        print(f"🗂️  创建表 '{table_name}'...")
        schema = [
            {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
            {"name": "woocommerce_id", "type": "INTEGER", "mode": "REQUIRED"},
            {"name": "email", "type": "STRING", "mode": "REQUIRED"},
            {"name": "first_name", "type": "STRING", "mode": "NULLABLE"},
            {"name": "last_name", "type": "STRING", "mode": "NULLABLE"},
            {"name": "phone", "type": "STRING", "mode": "NULLABLE"},
            {"name": "date_created", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "first_order_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "welcome_email_sent", "type": "BOOLEAN", "mode": "NULLABLE"},
            {"name": "welcome_email_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "sync_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "metadata", "type": "STRING", "mode": "NULLABLE"},
        ]
        
        table_info = {
            "schema": schema,
            "description": "WooCommerce customer data with welcome email tracking"
        }
        
        gcloud_db.create_bigquery_table(project_id, dataset_id, table_name, table_info)
        print(f"✅ 表 '{table_name}' 创建成功")
        
        # 插入数据
        if json_data:
            print(f"💾 插入 {len(json_data)} 条客户数据...")
            
            # 转换数据格式
            rows = []
            for customer in json_data:
                # 转换时间戳格式
                def convert_timestamp(timestamp_str):
                    if not timestamp_str:
                        return None
                    try:
                        if 'T' in timestamp_str:
                            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).isoformat()
                        else:
                            return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').isoformat()
                    except (ValueError, AttributeError):
                        return None
                
                row = {
                    "id": customer['id'],
                    "woocommerce_id": customer['woocommerce_id'],
                    "email": customer['email'],
                    "first_name": customer['first_name'],
                    "last_name": customer['last_name'],
                    "phone": customer['phone'],
                    "date_created": convert_timestamp(customer['date_created']),
                    "first_order_date": convert_timestamp(customer['first_order_date']),
                    "welcome_email_sent": customer['welcome_email_sent'],
                    "welcome_email_date": convert_timestamp(customer['welcome_email_date']),
                    "sync_date": convert_timestamp(customer['sync_date']),
                    "metadata": customer['metadata']
                }
                rows.append(row)
            
            # 批量插入
            success = gcloud_db.insert_table_rows(project_id, dataset_id, table_name, rows)
            
            if success:
                print(f"✅ 成功插入 {len(rows)} 条客户数据")
            else:
                print(f"❌ 数据插入失败")
                raise Exception("数据插入失败")
        else:
            print("⚠️  没有数据可插入")
        
        return f"{project_id}.{dataset_id}"
        
    except Exception as e:
        print(f"❌ BigQuery资源设置失败: {e}")
        logger.exception("BigQuery setup failed")
        raise

if __name__ == "__main__":
    main()