import sys
import os
import tarfile
import json
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Dict

# 添加当前目录到路径以便导入本地模块
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 添加 mcp_convert 路径以导入 EmailDatabase

from mcp_convert.mcps.email.database_utils import EmailDatabase


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


def import_emails_to_database(db: EmailDatabase, receiver_email: str, backup_file: Path) -> bool:
    """从备份文件导入邮件到数据库"""
    print(f"📨 从备份文件导入邮件到数据库...")
    print(f"   备份文件: {backup_file}")
    print(f"   接收者: {receiver_email}")
    
    try:
        # 读取备份文件
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        emails = backup_data.get('emails', [])
        print(f"   📧 找到 {len(emails)} 封邮件")
        
        # 获取接收者的用户数据目录
        user_dir = db._get_user_data_dir(receiver_email)
        emails_file = os.path.join(user_dir, "emails.json")
        folders_file = os.path.join(user_dir, "folders.json")
        
        # 加载现有邮件数据
        try:
            with open(emails_file, 'r', encoding='utf-8') as f:
                emails_data = json.load(f)
        except:
            emails_data = {}
        
        # 加载现有文件夹数据
        try:
            with open(folders_file, 'r', encoding='utf-8') as f:
                folders_data = json.load(f)
        except:
            folders_data = {
                "INBOX": {"total": 0, "unread": 0},
                "Sent": {"total": 0, "unread": 0},
                "Trash": {"total": 0, "unread": 0}
            }
        
        # 导入邮件
        imported_count = 0
        for email in emails:
            email_id = email.get('email_id')
            folder = email.get('folder', 'INBOX')
            is_read = email.get('is_read', False)
            
            # 将邮件添加到数据库
            emails_data[email_id] = {
                'id': email_id,
                'subject': email.get('subject', ''),
                'from': email.get('from_addr', ''),
                'to': email.get('to_addr', receiver_email),
                'cc': email.get('cc_addr'),
                'bcc': email.get('bcc_addr'),
                'date': email.get('date', ''),
                'message_id': email.get('message_id', ''),
                'body': email.get('body_text', ''),
                'html_body': email.get('body_html', ''),
                'is_read': is_read,
                'is_important': email.get('is_important', False),
                'folder': folder,
                'attachments': email.get('attachments', [])
            }
            
            # 更新文件夹计数
            if folder not in folders_data:
                folders_data[folder] = {"total": 0, "unread": 0}
            
            folders_data[folder]["total"] += 1
            if not is_read:
                folders_data[folder]["unread"] += 1
            
            imported_count += 1
            print(f"   ✓ [{imported_count}/{len(emails)}] 导入: {email.get('subject', 'No Subject')}")
        
        # 保存更新后的数据
        db._save_json_file(emails_file, emails_data)
        db._save_json_file(folders_file, folders_data)
        
        print(f"\n✅ 成功导入 {imported_count} 封邮件")
        return True
        
    except Exception as e:
        print(f"   ❌ 邮件导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_config(task_dir: Path, 
                    num_professors: int = 3, 
                    structure: str = "standard", 
                    receiver_idx: int = 0, 
                    seed: int = 42,
                    num_positive: int = 2,
                    positive_weight: float = 1.0,
                    research_assistant_weight: float = 1.0,
                    no_spots_weight: float = 1.0,
                    no_response_weight: float = 1.0,
                    assign_different_structures: bool = True) -> bool:
    """生成任务配置"""
    print("\n📝 步骤0: 生成任务配置...")
    print("=" * 60)
    
    # 配置生成脚本路径
    generator_script = task_dir / "generate_task_config.py"
    
    if not generator_script.exists():
        print(f"❌ 配置生成脚本不存在: {generator_script}")
        return False
    
    # 构建命令
    import subprocess
    cmd = [
        sys.executable,
        str(generator_script),
        "--num-professors", str(num_professors),
        "--structure", structure,
        "--receiver-idx", str(receiver_idx),
        "--seed", str(seed),
        "--num-positive", str(num_positive),
        "--positive-weight", str(positive_weight),
        "--research-assistant-weight", str(research_assistant_weight),
        "--no-spots-weight", str(no_spots_weight),
        "--no-response-weight", str(no_response_weight),
        "--output-dir", str(task_dir)
    ]
    
    # 添加分配不同结构的参数
    if assign_different_structures:
        cmd.append("--assign-different-structures")
    
    print(f"🎲 生成参数:")
    print(f"   导师数量: {num_professors}")
    print(f"   文件结构: {structure}")
    print(f"   分配不同结构: {assign_different_structures}")
    print(f"   接收者索引: {receiver_idx}")
    print(f"   随机种子: {seed}")
    print(f"   积极回复数量: {num_positive}")
    print(f"   回复类型权重:")
    print(f"      积极回复: {positive_weight}")
    print(f"      研究助理: {research_assistant_weight}")
    print(f"      无名额: {no_spots_weight}")
    print(f"      不回复: {no_response_weight}")
    
    try:
        # 运行配置生成脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(task_dir)
        )
        
        # 输出生成脚本的输出
        if result.stdout:
            print(result.stdout)
        
        if result.returncode != 0:
            print(f"❌ 配置生成失败:")
            if result.stderr:
                print(result.stderr)
            return False
        
        print("✅ 配置生成成功！")
        return True
        
    except Exception as e:
        print(f"❌ 配置生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("--agent_workspace", required=False)
    parser.add_argument("--launch_time", required=False, help="Launch time")
    
    # 配置生成参数
    parser.add_argument("--skip-generation", action="store_true", 
                       help="跳过配置生成，使用现有文件")
    parser.add_argument("--num-professors", type=int, default=10,
                       help="导师数量 (默认: 3)")
    parser.add_argument("--structure", type=str, default="standard",
                       choices=["standard", "variant1", "variant2", "variant3", "variant4", "variant5"],
                       help="文件结构类型 (默认: standard)")
    parser.add_argument("--receiver-idx", type=int, default=0,
                       help="接收者索引 (默认: 0)")
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (默认: 42)")
    parser.add_argument("--no-assign-different-structures", action="store_false",
                       dest="assign_different_structures",
                       help="禁用为每个积极回复的导师分配不同的文件结构（默认启用）")
    
    # 回复类型控制参数
    parser.add_argument("--num-positive", type=int, default=1,
                       help="积极回复的导师数量 (默认: 2)")
    parser.add_argument("--positive-weight", type=float, default=1.0,
                       help="积极回复的权重 (默认: 1.0)")
    parser.add_argument("--research-assistant-weight", type=float, default=1.0,
                       help="研究助理回复的权重 (默认: 1.0)")
    parser.add_argument("--no-spots-weight", type=float, default=1.0,
                       help="无名额回复的权重 (默认: 1.0)")
    parser.add_argument("--no-response-weight", type=float, default=1.0,
                       help="不回复的权重 (默认: 1.0)")
    parser.add_argument("--task-root", type=str, default=None,
                       help="任务根目录路径（如果不指定，则使用__file__推导）")

    args = parser.parse_args()
    
    # 首先处理文件解压缩（如果agent_workspace被指定）
    if args.agent_workspace:
        # 确保agent workspace存在
        os.makedirs(args.agent_workspace, exist_ok=True)
        dst_tar_path = os.path.join(args.agent_workspace, "files.tar.gz")
        
        # 解压缩文件
        try:
            with tarfile.open(dst_tar_path, 'r:gz') as tar:
                print(f"正在解压缩申请文件到: {args.agent_workspace}")
                # Try to use filter parameter for Python 3.12+, fall back for older versions
                try:
                    tar.extractall(path=args.agent_workspace, filter='data')
                except TypeError:
                    # Fall back to no filter for Python < 3.12
                    tar.extractall(path=args.agent_workspace)
                print("解压缩完成")
        except Exception as e:
            print(f"解压缩失败: {e}")
            # 继续执行，因为可能文件已经存在或者不需要解压缩
        
        # 删除压缩文件
        try:
            os.remove(dst_tar_path)
            print(f"已删除原始压缩文件: {dst_tar_path}")
        except Exception as e:
            print(f"删除压缩文件失败: {e}")

    print("\n" + "=" * 60)
    print("🚀 申请博士邮件任务环境预处理开始")
    print("=" * 60)
    print("Preprocessing...")
    print("使用本地数据库邮件导入模式")

    # 获取任务根目录
    if args.task_root:
        task_root = Path(args.task_root)
    else:
        task_root = Path(__file__).parent.parent
    
    # 步骤0: 生成任务配置（可选）
    if not args.skip_generation:
        if not generate_config(
            task_root,
            num_professors=args.num_professors,
            structure=args.structure,
            receiver_idx=args.receiver_idx,
            seed=args.seed,
            num_positive=args.num_positive,
            positive_weight=args.positive_weight,
            research_assistant_weight=args.research_assistant_weight,
            no_spots_weight=args.no_spots_weight,
            no_response_weight=args.no_response_weight,
            assign_different_structures=args.assign_different_structures
        ):
            print("❌ 配置生成失败，终止预处理")
            sys.exit(1)
    else:
        print("\n📝 步骤0: 跳过配置生成，使用现有配置")
        print("=" * 60)

    # 获取任务邮件备份文件路径
    task_backup_file = task_root / "files" / "emails_backup.json"
    email_config_file = task_root / "email_config.json"
    receiver_config_file = task_root / "files" / "receiver_config.json"

    if not task_backup_file.exists():
        print("❌ 未找到任务邮件备份文件")
        print("💡 请先运行配置生成或确保 emails_backup.json 文件存在")
        sys.exit(1)

    if not email_config_file.exists():
        print("❌ 未找到邮箱配置文件 email_config.json")
        sys.exit(1)

    if not receiver_config_file.exists():
        print("❌ 未找到接收者配置文件 receiver_config.json")
        sys.exit(1)

    # 读取真实的邮箱账号配置（email_config.json）
    print("\n📧 读取邮箱账号配置...")
    print("=" * 60)
    with open(email_config_file, 'r', encoding='utf-8') as f:
        email_config = json.load(f)
    
    # 真实接收邮件的账号（maryc@mcp.com）
    actual_receiver_email = email_config['email']
    actual_receiver_password = email_config['password']
    actual_receiver_name = email_config['name']
    
    print(f"   实际接收账号: {actual_receiver_name} ({actual_receiver_email})")
    
    # 读取邮件内容中的接收者配置（receiver_config.json）
    with open(receiver_config_file, 'r', encoding='utf-8') as f:
        receiver_config = json.load(f)
    
    # 邮件内容中提到的接收者（myersj@mcp.com）
    content_receiver_email = receiver_config['email']
    content_receiver_password = receiver_config['password']
    content_receiver_name = receiver_config['name']
    
    print(f"   邮件内容接收者: {content_receiver_name} ({content_receiver_email})")

    # 初始化邮件数据库
    print("\n📧 初始化邮件数据库...")
    print("=" * 60)
    
    # 确定 email 数据库目录
    if args.agent_workspace:
        workspace_parent = Path(args.agent_workspace).parent
        email_db_dir = str(workspace_parent / "local_db" / "emails")
    else:
        email_db_dir = str(Path(__file__).parent.parent / "local_db" / "emails")
    
    print(f"📂 Email 数据库目录: {email_db_dir}")
    Path(email_db_dir).mkdir(parents=True, exist_ok=True)
    
    # 初始化 EmailDatabase
    email_db = EmailDatabase(data_dir=email_db_dir)
    
    # 读取备份文件中的发件人邮箱
    print("\n📧 读取发件人信息...")
    print("=" * 60)
    with open(task_backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    # 从邮件中提取所有发件人
    senders = set()
    for email in backup_data.get('emails', []):
        sender = email.get('from_addr', '')
        if sender:
            senders.add(sender)
    
    print(f"   找到 {len(senders)} 个发件人")
    
    # 准备用户信息（包括实际接收者、内容接收者和所有发送者）
    users_info = [
        {"email": actual_receiver_email, "password": actual_receiver_password, "name": actual_receiver_name},
        {"email": content_receiver_email, "password": content_receiver_password, "name": content_receiver_name}
    ]
    
    # 为每个发件人创建用户（使用默认密码）
    for sender in senders:
        name = sender.split('@')[0]
        users_info.append({
            "email": sender,
            "password": "default_password",
            "name": name
        })
    
    # 确保所有用户存在于数据库
    print("\n👥 步骤1: 创建数据库用户...")
    print("=" * 60)
    if not ensure_users_exist(email_db, users_info):
        print("❌ 用户初始化失败")
        sys.exit(1)
    
    # 清理所有用户（实际接收者、内容接收者和发送者）的邮箱数据
    print(f"\n🗑️  步骤2: 清理所有用户邮箱数据库...")
    print("=" * 60)
    
    # 收集所有需要清理的邮箱
    emails_to_clean = [actual_receiver_email, content_receiver_email] + list(senders)
    print(f"   将清理 {len(emails_to_clean)} 个邮箱")
    
    all_success = True
    for email in emails_to_clean:
        if not clear_email_database(email_db, email):
            print(f"⚠️  邮箱 {email} 清理失败")
            all_success = False
    
    if all_success:
        print("✅ 所有邮箱数据库清理完成")
    else:
        print("⚠️ 部分邮箱数据库清理未完全成功，但继续执行")
    
    # 导入邮件到数据库（导入到实际接收账号 maryc@mcp.com）
    print(f"\n📨 步骤3: 导入邮件到数据库...")
    print("=" * 60)
    if not import_emails_to_database(email_db, actual_receiver_email, task_backup_file):
        print("\n❌ 邮件导入失败！")
        sys.exit(1)
    
    # 设置环境变量供 evaluation 使用
    os.environ['EMAIL_DATA_DIR'] = email_db_dir
    
    print("\n" + "=" * 60)
    print("🎉 申请博士邮件任务环境预处理完成！")
    print("=" * 60)
    print(f"✅ 邮件数据库初始化完成")
    print(f"✅ {len(users_info)} 个用户已创建")
    print(f"✅ 所有用户邮箱已清理")
    print(f"✅ 邮件已导入到数据库")
    print(f"\n📂 目录位置:")
    print(f"   Email 数据库: {email_db_dir}")
    print(f"\n📧 实际接收邮箱账号 (登录使用):")
    print(f"   Email: {actual_receiver_email}")
    print(f"   Password: {actual_receiver_password}")
    print(f"   Name: {actual_receiver_name}")
    print(f"\n📧 邮件内容中的接收者:")
    print(f"   Email: {content_receiver_email}")
    print(f"   Name: {content_receiver_name}")
    print(f"\n💡 下一步: Agent 需要分析邮件并准备申请材料")