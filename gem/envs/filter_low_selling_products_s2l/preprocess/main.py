#!/usr/bin/env python3
"""
预处理脚本 - 设置低销量产品筛选任务的初始环境（使用本地数据库）
支持动态难度控制
"""

import os
import sys
import shutil
import json
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime

# 添加项目路径
current_dir = Path(__file__).parent
task_dir = current_dir.parent
sys.path.insert(0, str(task_dir))

from mcp_convert.mcps.woocommerce.database_utils import WooCommerceDatabase
from mcp_convert.mcps.email.database_utils import EmailDatabase
from mcp_convert.mcps.woocommerce.init_database import initialize_database as init_woocommerce_db
from mcp_convert.mcps.email.init_database import initialize_database as init_email_db
from gem.utils.filesystem import nfs_safe_rmtree

def clear_database_folders(woocommerce_db_dir: str, email_db_dir: str) -> bool:
    """清空 WooCommerce 和 Email 数据库文件夹"""
    print(f"\n🗑️  清空数据库文件夹...")
    print("=" * 60)
    
    try:

        woocommerce_path = Path(woocommerce_db_dir)
        email_path = Path(email_db_dir)
        
        # 清空 WooCommerce 数据库文件夹
        if woocommerce_path.exists():
            print(f"   🛒 删除 WooCommerce 数据库文件夹: {woocommerce_path}")
            nfs_safe_rmtree(woocommerce_path)
            print(f"   ✓ WooCommerce 文件夹已删除")
        else:
            print(f"   ℹ️  WooCommerce 文件夹不存在，跳过删除")
        
        # 清空 Email 数据库文件夹
        if email_path.exists():
            print(f"   📧 删除 Email 数据库文件夹: {email_path}")
            nfs_safe_rmtree(email_path)
            print(f"   ✓ Email 文件夹已删除")
        else:
            print(f"   ℹ️  Email 文件夹不存在，跳过删除")
        
        print(f"✅ 数据库文件夹清空完成")
        return True
        
    except Exception as e:
        print(f"❌ 清空文件夹失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def copy_initial_workspace_to_agent(task_root: Path, agent_workspace: str) -> bool:
    """将 initial_workspace 复制到 agent_workspace"""
    initial_workspace = task_root / "initial_workspace"
    agent_workspace_path = Path(agent_workspace)
    
    print(f"\n📂 复制 initial_workspace 到 agent_workspace...")
    print(f"   源目录: {initial_workspace}")
    print(f"   目标目录: {agent_workspace_path}")
    
    try:
        if not initial_workspace.exists():
            print(f"   ℹ️  initial_workspace 不存在，创建空目录")
            initial_workspace.mkdir(parents=True, exist_ok=True)
        
        # 确保 agent_workspace 存在
        agent_workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 复制所有文件
        copied_count = 0
        for item in initial_workspace.iterdir():
            dest = agent_workspace_path / item.name
            
            if item.is_file():
                shutil.copy2(item, dest)
                print(f"   ✓ 复制文件: {item.name}")
                copied_count += 1
            elif item.is_dir():
                if dest.exists():
                    nfs_safe_rmtree(dest)
                shutil.copytree(item, dest)
                print(f"   ✓ 复制目录: {item.name}")
                copied_count += 1
        
        if copied_count > 0:
            print(f"✅ 成功复制 {copied_count} 个项目到 agent_workspace")
        else:
            print(f"   ℹ️  initial_workspace 为空，无文件需要复制")
        return True
    except Exception as e:
        print(f"❌ 复制失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_products_and_subscribers(task_root: Path,
                                     num_low_selling: int = 5,
                                     num_normal_selling: int = 3,
                                     num_subscribers: int = 3,
                                     seed: int = 42) -> bool:
    """
    生成商品和订阅者数据
    
    Args:
        task_root: 任务根目录
        num_low_selling: 低销量商品数量
        num_normal_selling: 正常销量商品数量
        num_subscribers: 订阅者数量
        seed: 随机种子
        
    Returns:
        True if successful
    """
    print("\n📝 步骤0: 生成商品和订阅者数据...")
    print("=" * 60)
    
    try:
        generator_script = Path(__file__).parent / "generate_products_data.py"
        
        if not generator_script.exists():
            print(f"❌ 数据生成脚本不存在: {generator_script}")
            return False
        
        # 构建命令
        cmd = [
            sys.executable,
            str(generator_script),
            "--output-dir", str(task_root),
            "--num-low-selling", str(num_low_selling),
            "--num-normal-selling", str(num_normal_selling),
            "--num-subscribers", str(num_subscribers),
            "--seed", str(seed)
        ]
        
        print(f"🎲 生成参数:")
        print(f"   低销量商品: {num_low_selling}")
        print(f"   正常销量商品: {num_normal_selling}")
        print(f"   订阅者: {num_subscribers}")
        print(f"   随机种子: {seed}")
        
        # 运行生成脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        
        # 输出生成脚本的输出
        if result.stdout:
            print(result.stdout)
        
        if result.returncode != 0:
            print(f"❌ 数据生成失败:")
            if result.stderr:
                print(result.stderr)
            return False
        
        print("✅ 数据生成成功！")
        return True
        
    except Exception as e:
        print(f"❌ 数据生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def setup_woocommerce_database(woocommerce_db_dir: str, task_root: Path, use_generated_data: bool = True) -> bool:
    """设置 WooCommerce 数据库"""
    print("\n🛒 步骤1: 初始化 WooCommerce 数据库...")
    print("=" * 60)
    
    try:
        # 创建数据库目录
        Path(woocommerce_db_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库（使用 init_database.py）
        print(f"   📁 数据库目录: {woocommerce_db_dir}")
        
        # 如果使用生成的数据，读取并插入
        if use_generated_data:
            generated_products_file = task_root / "preprocess" / "generated_products.json"
            
            if generated_products_file.exists():
                print(f"   📦 使用生成的商品数据: {generated_products_file}")
                
                # 先初始化空数据库（不包含示例商品数据）
                init_woocommerce_db(woocommerce_db_dir, verbose=False, include_demo_data=False)
                
                # 读取生成的商品数据
                with open(generated_products_file, 'r', encoding='utf-8') as f:
                    products_data = json.load(f)
                
                # 获取数据库实例
                db = WooCommerceDatabase(data_dir=woocommerce_db_dir)
                
                # 批量创建商品
                print(f"   📤 插入 {len(products_data)} 个商品到数据库...")
                for idx, product_data in enumerate(products_data, 1):
                    try:
                        product_id = db.create_product(product_data)
                        if idx % 50 == 0:
                            print(f"      进度: {idx}/{len(products_data)}")
                    except Exception as e:
                        print(f"      ⚠️  插入商品 {product_data.get('name')} 失败: {e}")
                
                print(f"   ✅ 商品数据插入完成")
            else:
                print(f"   ⚠️  未找到生成的商品数据，使用默认初始化（包含示例商品）")
                init_woocommerce_db(woocommerce_db_dir, verbose=True, include_demo_data=True)
        else:
            # 使用默认初始化（包含示例商品）
            init_woocommerce_db(woocommerce_db_dir, verbose=True, include_demo_data=True)
        
        # 验证数据库
        db = WooCommerceDatabase(data_dir=woocommerce_db_dir)
        products = db.list_products()
        orders = db.list_orders()
        customers = db.list_customers()
        
        print(f"\n✅ WooCommerce 数据库初始化完成！")
        print(f"   产品数量: {len(products)}")
        print(f"   订单数量: {len(orders)}")
        print(f"   客户数量: {len(customers)}")
        
        return True
        
    except Exception as e:
        print(f"❌ WooCommerce 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def ensure_users_exist(db: EmailDatabase, users_info: list) -> bool:
    """确保用户在数据库中存在"""
    print(f"\n👥 确保 {len(users_info)} 个用户存在于数据库...")
    
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


def clear_email_database(db: EmailDatabase, user_emails: list) -> bool:
    """清理指定用户的邮箱数据"""
    print(f"\n🗑️  清理 {len(user_emails)} 个邮箱的数据库...")
    
    try:
        for user_email in user_emails:
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


def setup_email_database(email_db_dir: str, task_root: Path, admin_email: str, admin_password: str, admin_name: str) -> bool:
    """设置 Email 数据库"""
    print("\n📧 步骤2: 初始化 Email 数据库...")
    print("=" * 60)
    
    try:
        # 创建数据库目录
        Path(email_db_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        db = EmailDatabase(data_dir=email_db_dir)
        
        # 读取 subscriber.json
        subscriber_file = task_root / "initial_workspace" / "subscriber.json"
        if not subscriber_file.exists():
            print(f"   ⚠️  未找到 subscriber.json，仅创建管理员用户")
            subscribers = []
        else:
            with open(subscriber_file, 'r', encoding='utf-8') as f:
                subscriber_config = json.load(f)
            subscribers = subscriber_config.get('subscriber_list', [])
            print(f"   📋 找到 {len(subscribers)} 个订阅者")
        
        # 准备所有用户信息（管理员 + 订阅者）
        users_info = [
            {"email": admin_email, "password": admin_password, "name": admin_name}
        ]
        
        for subscriber in subscribers:
            users_info.append({
                "email": subscriber['email'],
                "password": "subscriber123",  # 默认密码
                "name": subscriber['name']
            })
        
        # 创建所有用户
        if not ensure_users_exist(db, users_info):
            print("❌ 用户创建失败")
            return False
        
        # 为所有用户清理/创建邮箱文件夹
        all_emails = [u['email'] for u in users_info]
        if not clear_email_database(db, all_emails):
            print("⚠️  邮箱文件夹创建未完全成功，但继续执行")
        
        print(f"\n✅ Email 数据库初始化完成！")
        print(f"   管理员账号: {admin_email}")
        print(f"   订阅者账号: {len(subscribers)} 个")
        for subscriber in subscribers:
            print(f"      • {subscriber['name']} ({subscriber['email']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Email 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_admin_credentials(task_root: Path, email: str, password: str) -> bool:
    """将管理员账号信息保存到 initial_workspace"""
    print(f"\n💾 步骤3: 保存管理员账号信息...")
    print("=" * 60)
    
    try:
        initial_workspace = task_root / "initial_workspace"
        initial_workspace.mkdir(parents=True, exist_ok=True)
        
        credentials_file = initial_workspace / "admin_credentials.txt"
        
        with open(credentials_file, 'w', encoding='utf-8') as f:
            f.write(f"WooCommerce & Email Admin Account\n")
            f.write(f"==================================\n\n")
            f.write(f"Email: {email}\n")
            f.write(f"Password: {password}\n\n")
            f.write(f"This account has access to both WooCommerce and Email systems.\n")
        
        print(f"   ✓ 账号信息已保存到: {credentials_file}")
        return True
        
    except Exception as e:
        print(f"   ❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = ArgumentParser(description="预处理脚本 - 设置低销量产品筛选任务的初始环境")
    parser.add_argument("--agent_workspace", required=False, help="Agent工作空间路径")
    parser.add_argument("--launch_time", required=False, help="Launch time")
    
    # 数据生成控制
    parser.add_argument("--skip-generation", action="store_true",
                       help="跳过数据生成，使用现有文件")
    parser.add_argument("--num-low-selling", type=int, default=3,
                       help="低销量商品数量 (默认: 5)")
    parser.add_argument("--num-normal-selling", type=int, default=5,
                       help="正常销量商品数量 (默认: 3)")
    parser.add_argument("--num-subscribers", type=int, default=3,
                       help="订阅者数量 (默认: 3)")
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (默认: 42)")
    
    # 难度预设
    parser.add_argument("--difficulty", type=str, default=None,
                       choices=["easy", "medium", "hard", "expert", "extreme", "insane"],
                       help="难度预设（可选，会覆盖其他参数）")

    args = parser.parse_args()
    
    # 应用难度预设
    if args.difficulty:
        print(f"🎲 使用难度预设: {args.difficulty}")
        
        if args.difficulty == "easy":
            args.num_low_selling = 3
            args.num_normal_selling = 2
            args.num_subscribers = 2
        elif args.difficulty == "medium":
            args.num_low_selling = 5
            args.num_normal_selling = 5
            args.num_subscribers = 3
        elif args.difficulty == "hard":
            args.num_low_selling = 10
            args.num_normal_selling = 15
            args.num_subscribers = 5
        elif args.difficulty == "expert":
            args.num_low_selling = 20
            args.num_normal_selling = 30
            args.num_subscribers = 10
        elif args.difficulty == "extreme":
            args.num_low_selling = 50
            args.num_normal_selling = 100
            args.num_subscribers = 25
        elif args.difficulty == "insane":
            args.num_low_selling = 100
            args.num_normal_selling = 200
            args.num_subscribers = 50
    else:
        print(f"🎲 使用自定义参数")
    
    print("\n" + "=" * 60)
    print("🎯 低销量产品筛选任务 - 预处理（本地数据库版本）")
    print("=" * 60)
    print("使用本地数据库 (WooCommerce + Email)")

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
    else:
        woocommerce_db_dir = str(Path(__file__).parent.parent / "local_db" / "woocommerce")
        email_db_dir = str(Path(__file__).parent.parent / "local_db" / "emails")
    
    print(f"\n📂 Task root directory: {task_root}")
    print(f"📂 数据库目录:")
    print(f"   WooCommerce: {woocommerce_db_dir}")
    print(f"   Email: {email_db_dir}")

    # 步骤0: 生成商品和订阅者数据（可选）
    if not args.skip_generation:
        print("\n" + "=" * 60)
        print("STEP 0: 生成商品和订阅者数据")
        print("=" * 60)
        
        if not generate_products_and_subscribers(
            task_root=task_root,
            num_low_selling=args.num_low_selling,
            num_normal_selling=args.num_normal_selling,
            num_subscribers=args.num_subscribers,
            seed=args.seed
        ):
            print("❌ 数据生成失败！")
            sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("STEP 0: 跳过数据生成")
        print("=" * 60)
        print("使用现有数据文件")
    
    # 清空数据库文件夹
    if not clear_database_folders(woocommerce_db_dir, email_db_dir):
        print("⚠️  清空数据库文件夹失败，但继续执行")
    
    # 步骤1: 设置 WooCommerce 数据库
    if not setup_woocommerce_database(woocommerce_db_dir, task_root, use_generated_data=not args.skip_generation):
        print("❌ WooCommerce 数据库设置失败")
        sys.exit(1)
    
    # 步骤2: 设置 Email 数据库（包括订阅者）
    if not setup_email_database(email_db_dir, task_root, admin_email, admin_password, admin_name):
        print("❌ Email 数据库设置失败")
        sys.exit(1)
    
    # 步骤3: 保存管理员账号信息
    if not save_admin_credentials(task_root, admin_email, admin_password):
        print("⚠️  保存管理员账号信息失败，但继续执行")
    
    # 设置环境变量
    os.environ['WOOCOMMERCE_DATA_DIR'] = woocommerce_db_dir
    os.environ['EMAIL_DATA_DIR'] = email_db_dir
    
    # 写入环境变量文件
    if args.agent_workspace:
        env_file = Path(args.agent_workspace).parent / "local_db" / ".env"
    else:
        env_file = Path(woocommerce_db_dir).parent / ".env"
    
    try:
        env_file.parent.mkdir(parents=True, exist_ok=True)
        with open(env_file, 'w') as f:
            f.write(f"# WooCommerce & Email Database Environment Variables\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"export WOOCOMMERCE_DATA_DIR={woocommerce_db_dir}\n")
            f.write(f"export EMAIL_DATA_DIR={email_db_dir}\n")
        print(f"\n📄 环境变量文件已创建: {env_file}")
    except Exception as e:
        print(f"⚠️  无法创建环境变量文件: {e}")
    
    # 步骤4: 复制 initial_workspace 到 agent_workspace
    if args.agent_workspace:
        print(f"\n📋 步骤4: 复制 initial_workspace 到 agent_workspace...")
        print("=" * 60)
        if not copy_initial_workspace_to_agent(task_root, args.agent_workspace):
            print("⚠️  复制 initial_workspace 失败，但继续执行")
    else:
        print(f"\n⚠️  未指定 agent_workspace，跳过复制步骤")
    
    # 读取订阅者信息用于最终输出
    subscriber_file = task_root / "initial_workspace" / "subscriber.json"
    subscribers = []
    if subscriber_file.exists():
        with open(subscriber_file, 'r', encoding='utf-8') as f:
            subscriber_config = json.load(f)
        subscribers = subscriber_config.get('subscriber_list', [])
    
    print("\n" + "=" * 60)
    print("🎉 低销量产品筛选任务环境预处理完成！")
    print("=" * 60)
    
    if not args.skip_generation:
        print(f"✅ 数据生成完成")
        print(f"   • 低销量商品: {args.num_low_selling} 个")
        print(f"   • 正常销量商品: {args.num_normal_selling} 个")
        print(f"   • 订阅者: {args.num_subscribers} 个")
    
    print(f"✅ WooCommerce 数据库已初始化")
    print(f"✅ Email 数据库已初始化")
    print(f"✅ 管理员账号已创建并保存")
    print(f"✅ {len(subscribers)} 个订阅者账号已创建")
    if args.agent_workspace:
        print(f"✅ initial_workspace 已复制到 agent_workspace")
    
    print(f"\n📂 目录位置:")
    print(f"   WooCommerce 数据库: {woocommerce_db_dir}")
    print(f"   Email 数据库: {email_db_dir}")
    print(f"   initial_workspace: {task_root / 'initial_workspace'}")
    if args.agent_workspace:
        print(f"   agent_workspace: {args.agent_workspace}")
    
    print(f"\n📌 环境变量:")
    print(f"   WOOCOMMERCE_DATA_DIR={woocommerce_db_dir}")
    print(f"   EMAIL_DATA_DIR={email_db_dir}")
    
    print(f"\n👤 管理员账号:")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print(f"   Name: {admin_name}")
    
    print(f"\n👥 订阅者账号 ({len(subscribers)} 个):")
    for subscriber in subscribers:
        print(f"   • {subscriber['name']} ({subscriber['email']}) - Password: subscriber123")
    
    print(f"\n💡 下一步: Agent 可以使用以下 MCP 服务器:")
    print(f"   • woocommerce-simplified - 查看产品、订单、销售数据")
    print(f"   • emails-simplified - 发送通知邮件")
    print(f"\n📝 任务提示:")
    print(f"   • 分析销售数据，找出低销量产品（在库>90天，30天销量<10）")
    print(f"   • 将低销量产品移动到 Outlet/Clearance 分类")
    print(f"   • 通过 Email 向 {len(subscribers)} 个订阅者发送促销通知")
    
    # 显示难度信息
    if args.difficulty:
        print(f"\n🎮 难度设置: {args.difficulty.upper()}")
    
    print(f"\n📊 数据库统计:")
    # 验证并显示数据库统计
    try:
        wc_db = WooCommerceDatabase(data_dir=woocommerce_db_dir)
        all_products = list(wc_db.products.values())
        
        # 计算低销量商品
        from datetime import datetime
        current_date = datetime.now()
        low_selling_count = 0
        
        for product in all_products:
            date_created_str = product.get('date_created', '')
            if not date_created_str:
                continue
            
            date_created = datetime.fromisoformat(date_created_str.replace('Z', '+00:00'))
            days_in_stock = (current_date - date_created.replace(tzinfo=None)).days
            
            sales_30_days = 0
            for meta in product.get('meta_data', []):
                if meta.get('key') == 'sales_last_30_days':
                    sales_30_days = int(meta.get('value', 0))
                    break
            
            if days_in_stock > 90 and sales_30_days < 10:
                low_selling_count += 1
        
        print(f"   总产品数: {len(all_products)}")
        print(f"   低销量产品: {low_selling_count} 个 (在库>90天，30天销量<10)")
        print(f"   正常销售产品: {len(all_products) - low_selling_count} 个")
        
    except Exception as e:
        print(f"   ⚠️  无法读取数据库统计: {e}")
    
    sys.exit(0)
