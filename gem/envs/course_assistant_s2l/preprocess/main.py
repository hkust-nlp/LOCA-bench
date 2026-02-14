import asyncio
from argparse import ArgumentParser
from pathlib import Path
from time import sleep
import sys
import subprocess
import json
import os
import shutil
from datetime import datetime, timezone
from typing import List, Dict
from gem.utils.filesystem import nfs_safe_rmtree

# 添加当前目录到路径以便导入本地模块
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


from mcp_convert.mcps.email.database_utils import EmailDatabase


def clear_initial_workspace(task_root: Path) -> bool:
    """清空 initial_workspace 目录"""
    initial_workspace = task_root / "initial_workspace"
    
    print(f"🗑️  清空 initial_workspace 目录...")
    
    try:
        if initial_workspace.exists():
            # 删除目录中的所有内容
            for item in initial_workspace.iterdir():
                if item.is_file():
                    item.unlink()
                    print(f"   ✓ 删除文件: {item.name}")
                elif item.is_dir():
                    nfs_safe_rmtree(item)
                    print(f"   ✓ 删除目录: {item.name}")
        else:
            # 如果目录不存在，创建它
            initial_workspace.mkdir(parents=True, exist_ok=True)
            print(f"   ✓ 创建目录: {initial_workspace}")
        
        print("✅ initial_workspace 已清空")
        return True
    except Exception as e:
        print(f"❌ 清空 initial_workspace 失败: {e}")
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
            print(f"❌ initial_workspace 不存在: {initial_workspace}")
            return False
        
        # 确保 agent_workspace 存在
        agent_workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 复制所有文件和子目录
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
        
        print(f"✅ 成功复制 {copied_count} 个项目到 agent_workspace")
        return True
    except Exception as e:
        print(f"❌ 复制失败: {e}")
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


def clear_email_database(db: EmailDatabase, user_emails: List[str]) -> bool:
    """清理指定用户的邮箱数据"""
    print(f"🗑️  清理 {len(user_emails)} 个邮箱的数据库...")
    
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


def send_emails_via_database(db: EmailDatabase,
                             sender_email: str,
                             receiver_email: str,
                             emails_jsonl_path: Path) -> bool:
    """通过直接操作数据库发送邮件"""
    print(f"📨 通过数据库发送邮件...")
    
    try:
        # 登录发送者账户
        sender_user = db.users.get(sender_email)
        if not sender_user:
            print(f"   ❌ 发送者不存在: {sender_email}")
            return False
        
        # 检查接收者是否存在
        receiver_user = db.users.get(receiver_email)
        if not receiver_user:
            print(f"   ❌ 接收者不存在: {receiver_email}")
            return False
        
        # 设置当前用户
        db.current_user_email = sender_email
        db.authenticated = True
        db._load_user_data(sender_email)
        
        # 读取邮件数据
        emails_data = []
        with open(emails_jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    email_data = json.loads(line)
                    emails_data.append(email_data)
                except json.JSONDecodeError:
                    continue
        
        print(f"   📧 准备发送 {len(emails_data)} 封邮件")
        
        # 发送每封邮件
        sent_count = 0
        for i, email_data in enumerate(emails_data, 1):
            try:
                sender_name = email_data.get('sender_name', 'Student')
                subject = email_data.get('subject', 'No Subject')
                content = email_data.get('content', '')
                content_type = email_data.get('content_type', 'plain')
                
                # 使用 EmailDatabase 的 send_email 方法
                html_body = content if content_type == 'html' else None
                plain_body = content if content_type == 'plain' else None
                
                email_result = db.send_email(
                    to=receiver_email,
                    subject=subject,
                    body=plain_body or content,
                    html_body=html_body
                )
                
                sent_count += 1
                print(f"   ✓ [{i}/{len(emails_data)}] {sender_name}: {subject}")
                
                # 小延迟以保持时间顺序
                sleep(0.1)
                
            except Exception as e:
                print(f"   ❌ [{i}/{len(emails_data)}] 发送失败: {e}")
                continue
        
        print(f"\n✅ 成功发送 {sent_count}/{len(emails_data)} 封邮件")
        return sent_count == len(emails_data)
        
    except Exception as e:
        print(f"   ❌ 邮件发送失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_config(task_dir: Path, 
                    email_db: EmailDatabase,
                    sender_email: str,
                    sender_password: str,
                    sender_name: str,
                    receiver_email: str,
                    receiver_password: str,
                    receiver_name: str,
                    num_students: int = 15,
                    dropout_rate: float = 0.1,
                    submission_rate: float = 0.7,
                    num_check: int = 2,
                    seed: int = 42):
    """生成任务配置并创建数据库用户"""
    print("\n📝 步骤0: 生成任务配置...")
    print("=" * 60)
    
    # 配置生成脚本路径 - for environment, it's in the parent directory
    # task_dir is where we want to save the output, but the script is in the env dir
    env_dir = Path(__file__).parent.parent  # course_assistant_s2l env directory
    generator_script = env_dir / "generate_task_config.py"
    
    if not generator_script.exists():
        print(f"❌ 配置生成脚本不存在: {generator_script}")
        return False
    
    # 构建命令
    cmd = [
        sys.executable,
        str(generator_script),
        "--num-students", str(num_students),
        "--dropout-rate", str(dropout_rate),
        "--submission-rate", str(submission_rate),
        "--num-check", str(num_check),
        "--seed", str(seed),
        "--output-dir", str(task_dir)
    ]
    
    print(f"🎲 生成参数:")
    print(f"   学生总数: {num_students}")
    print(f"   退课率: {dropout_rate:.0%}")
    print(f"   提交率: {submission_rate:.0%}")
    print(f"   检查学生数: {num_check}")
    print(f"   随机种子: {seed}")
    
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
        
        # 立即读取生成的学生配置并创建数据库用户
        print("\n👥 创建数据库用户...")
        check_students = read_evaluation_check_students(task_dir)
        
        # 准备所有需要的用户信息
        users_info = [
            {"email": sender_email, "password": sender_password, "name": sender_name},
            {"email": receiver_email, "password": receiver_password, "name": receiver_name}
        ]
        users_info.extend([
            {"email": s['email'], "password": s['password'], "name": s['name']}
            for s in check_students
        ])
        
        # 确保所有用户存在于数据库
        if not ensure_users_exist(email_db, users_info):
            print("❌ 用户创建失败")
            return False
        
        print(f"✅ 成功创建 {len(users_info)} 个数据库用户")
        return True
        
    except Exception as e:
        print(f"❌ 配置生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_students_from_emails_jsonl(jsonl_path: Path):
    """从 emails.jsonl 读取学生信息（已提交的学生）"""
    students = []
    if not jsonl_path.exists():
        return students
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                email_data = json.loads(line)
                # 从 subject 提取学号: nlp-presentation-{student_id}-{name}
                subject = email_data.get('subject', '')
                parts = subject.split('-')
                if len(parts) >= 3:
                    student_id = parts[2]
                    name = email_data.get('sender_name', '')
                    students.append({
                        'name': name,
                        'student_id': student_id
                    })
            except json.JSONDecodeError:
                continue
    
    return students


def read_evaluation_check_students(task_dir: Path):
    """从 students_info.json 和 emails.jsonl 读取需要检查的学生（未提交的在册学生）"""
    students = []
    
    # 读取完整学生信息（包括密码）
    students_info_path = task_dir / "files" / "students_info.json"
    if not students_info_path.exists():
        print(f"⚠️  学生信息文件不存在: {students_info_path}")
        return []
    
    try:
        with open(students_info_path, 'r', encoding='utf-8') as f:
            all_students = json.load(f)
    except Exception as e:
        print(f"⚠️  读取学生信息失败: {e}")
        return []
    
    # 读取 emails.jsonl 获取已提交学生
    emails_jsonl = task_dir / "files" / "emails.jsonl"
    submitted_student_ids = set()
    if emails_jsonl.exists():
        with open(emails_jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    email_data = json.loads(line)
                    # 从主题中提取学号
                    subject = email_data.get('subject', '')
                    import re
                    match = re.search(r'nlp-presentation-(\d+)-', subject)
                    if match:
                        submitted_student_ids.add(match.group(1))
                except:
                    continue
    
    # 筛选未提交的在册学生
    for student in all_students:
        student_id = student['student_id']
        status = student.get('status', 'enrolled')
        
        # 只获取未提交的在册学生
        if status != 'dropped' and student_id not in submitted_student_ids:
            students.append({
                'name': student['name'],
                'email': student['email'],
                'password': student['password'],
                'student_id': student_id
            })
    
    return students


def save_teacher_email_account(task_root: Path, email: str, password: str) -> bool:
    """将教师的邮箱账号信息保存到 initial_workspace/email_account.txt"""
    print(f"\n💾 保存教师邮箱账号信息...")
    
    try:
        initial_workspace = task_root / "initial_workspace"
        email_account_file = initial_workspace / "email_account.txt"
        
        # 确保 initial_workspace 目录存在
        initial_workspace.mkdir(parents=True, exist_ok=True)
        
        # 写入邮箱账号信息
        with open(email_account_file, 'w', encoding='utf-8') as f:
            f.write(f"Email: {email}\n")
            f.write(f"Password: {password}\n")
        
        print(f"   ✓ 邮箱账号信息已保存到: {email_account_file}")
        return True
    except Exception as e:
        print(f"   ❌ 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__=="__main__":
    parser = ArgumentParser()
    parser.add_argument("--agent_workspace", required=False)
    parser.add_argument("--launch_time", required=False, help="Launch time")
    parser.add_argument("--task-root", required=False, help="任务根目录（用于多实例隔离）")
    
    # 配置生成参数
    parser.add_argument("--skip-generation", action="store_true", 
                       help="跳过配置生成，使用现有文件")
    parser.add_argument("--num-students", type=int, default=50,
                       help="学生总数 (默认: 25)")
    parser.add_argument("--dropout-rate", type=float, default=0.1,
                       help="退课率 (0-1, 默认: 0.2)")
    parser.add_argument("--submission-rate", type=float, default=0.5,
                       help="作业提交率 (0-1, 默认: 0.7)")
    parser.add_argument("--num-check", type=int, default=2,
                       help="需要检查的学生数量 (默认: 2)")
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (默认: 42)")
    
    args = parser.parse_args()

    # 获取任务根目录
    # 如果指定了 task-root，使用它；否则使用环境目录作为后备
    if args.task_root:
        task_root = Path(args.task_root)
    else:
        task_root = Path(__file__).parent.parent
    
    print("\n" + "=" * 60)
    print("🚀 课程助理任务环境预处理开始")
    print("=" * 60)
    
    # 步骤-1: 清空 initial_workspace
    print("\n📁 步骤-1: 清空 initial_workspace...")
    print("=" * 60)
    if not clear_initial_workspace(task_root):
        print("❌ 清空 initial_workspace 失败，终止预处理")
        sys.exit(1)
    
    # 初始化邮件数据库（在配置生成之前）
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
    
    # 邮箱配置
    sender_email = "mcooper@mcp.com"
    sender_password = "maria_89vHV7"
    sender_name = "NLP Course Student"
    
    receiver_email = "virginia_diaz@mcp.com"
    receiver_password = "virginia_85W"
    receiver_name = "NLP Course Assistant"
    
    # 步骤0: 生成任务配置（可选）
    if not args.skip_generation:
        if not generate_config(
            task_root,
            email_db,
            sender_email,
            sender_password,
            sender_name,
            receiver_email,
            receiver_password,
            receiver_name,
            num_students=args.num_students,
            dropout_rate=args.dropout_rate,
            submission_rate=args.submission_rate,
            num_check=args.num_check,
            seed=args.seed
        ):
            print("❌ 配置生成失败，终止预处理")
            sys.exit(1)
    else:
        print("\n📝 步骤0: 跳过配置生成，使用现有配置")
        print("=" * 60)
        
        # 即使跳过生成，也要确保用户存在
        print("\n👥 步骤1: 确保用户存在于数据库...")
        print("=" * 60)
        
        check_students = read_evaluation_check_students(task_root)
        
        users_info = [
            {"email": sender_email, "password": sender_password, "name": sender_name},
            {"email": receiver_email, "password": receiver_password, "name": receiver_name}
        ]
        users_info.extend([
            {"email": s['email'], "password": s['password'], "name": s['name']}
            for s in check_students
        ])
        
        if not ensure_users_exist(email_db, users_info):
            print("❌ 用户初始化失败")
            sys.exit(1)
    
    # 读取需要清理的学生邮箱（从 Excel 和 emails.jsonl）
    check_students = read_evaluation_check_students(task_root)
    
    print(f"\n✅ 从 evaluation 配置中读取到 {len(check_students)} 个需要检查的学生")
    for student in check_students:
        print(f"   • {student['name']}: {student['email']}")
    
    # 准备要清理的邮箱列表（用户已经在步骤0中创建）
    emails_to_clean = [sender_email, receiver_email]
    emails_to_clean.extend([s['email'] for s in check_students])
    
    print(f"\n🗑️  步骤2: 清理 {len(emails_to_clean)} 个邮箱数据库...")
    print("=" * 60)
    
    # 清理邮箱数据库
    if not clear_email_database(email_db, emails_to_clean):
        print("⚠️ 邮箱数据库清理未完全成功，但继续执行")
    else:
        print("✅ 邮箱数据库清理完成")
    
    print(f"\n📨 步骤3: 发送邮件到数据库...")
    print("=" * 60)
    print(f"📧 邮件发送配置:")
    print(f"   发送方: {sender_email}")
    print(f"   接收方: {receiver_email}")

    # 邮件数据文件路径
    email_jsonl_file = task_root / "files" / "emails.jsonl"
    
    # 检查邮件文件是否存在
    if not email_jsonl_file.exists():
        print(f"❌ 错误: 邮件数据文件不存在: {email_jsonl_file}")
        print("💡 请确保已经运行配置生成脚本")
        sys.exit(1)
    
    # 统计邮件数量
    num_emails = 0
    with open(email_jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                num_emails += 1
    
    print(f"🚀 通过数据库发送 {num_emails} 封邮件...")
    print(f"   邮件数据: {email_jsonl_file}")
    
    # 通过数据库发送邮件
    if not send_emails_via_database(email_db, sender_email, receiver_email, email_jsonl_file):
        print("❌ 邮件发送失败")
        sys.exit(1)

    # 保存教师邮箱账号到 initial_workspace
    print(f"\n📝 步骤3.5: 保存教师邮箱账号信息...")
    print("=" * 60)
    if not save_teacher_email_account(task_root, receiver_email, receiver_password):
        print("⚠️  保存教师邮箱账号信息失败，但继续执行")
    else:
        print("✅ 教师邮箱账号信息已保存")

    # 设置环境变量供 evaluation 使用
    os.environ['EMAIL_DATA_DIR'] = email_db_dir
    
    # 写入环境变量文件
    env_file = Path(email_db_dir).parent / ".email_env"
    try:
        with open(env_file, 'w') as f:
            f.write(f"# Email Database Environment Variables\\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write(f"export EMAIL_DATA_DIR={email_db_dir}\\n")
        print(f"📄 环境变量文件已创建: {env_file}")
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
    
    print("\\n" + "=" * 60)
    print("🎉 课程助理任务环境预处理完成！")
    print("=" * 60)
    print(f"✅ initial_workspace 已清空并生成新配置")
    print(f"✅ 任务配置已生成")
    print(f"✅ {len(emails_to_clean)} 个邮箱数据库已清理")
    print(f"✅ {num_emails} 封学生作业邮件已写入数据库")
    print(f"✅ 教师邮箱账号信息已保存到 email_account.txt")
    print(f"✅ {len(check_students)} 个学生需要接收催促邮件")
    if args.agent_workspace:
        print(f"✅ initial_workspace 已复制到 agent_workspace")
    print(f"\\n📂 目录位置:")
    print(f"   initial_workspace: {task_root / 'initial_workspace'}")
    if args.agent_workspace:
        print(f"   agent_workspace: {args.agent_workspace}")
    print(f"   Email 数据库: {email_db_dir}")
    print(f"\\n📌 环境变量已设置:")
    print(f"   EMAIL_DATA_DIR={email_db_dir}")
    print(f"\\n📧 教师邮箱账号:")
    print(f"   Email: {receiver_email}")
    print(f"   Password: {receiver_password}")
    print(f"\\n💡 下一步: Agent 需要分析 Excel 并向未提交作业的学生发送催促邮件")