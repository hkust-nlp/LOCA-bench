import sys
import os
import tarfile
import shutil
import json
from argparse import ArgumentParser
from pathlib import Path
from gem.utils.filesystem import nfs_safe_rmtree

# Add current directory to sys.path for imports when running as standalone script
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from mcp_convert.mcps.email.database_utils import EmailDatabase
from check_local_email import LocalEmailAttachmentChecker  # type: ignore

# FILE_STRUCTURES will be imported dynamically in main() after parsing --task-root  

def extract_groundtruth_files(groundtruth_workspace: str) -> tuple[str, bool]:
    """Extract groundtruth files from compressed archive to the same directory
    
    Returns:
        tuple: (workspace_path, was_extracted) where was_extracted indicates if extraction occurred
    """
    tar_file_path = os.path.join(groundtruth_workspace, "files.tar.gz")
    
    if not os.path.exists(tar_file_path):
        # If no compressed file exists, assume files are already extracted
        return groundtruth_workspace, False
    
    # Check if files are already extracted
    expected_dir = os.path.join(groundtruth_workspace, "Application_Materials_MaryCastillo_2201210606")
    if os.path.exists(expected_dir):
        print(f"✓ Groundtruth files already extracted in: {groundtruth_workspace}")
        return groundtruth_workspace, False
    
    try:
        with tarfile.open(tar_file_path, 'r:gz') as tar:
            # Try to use filter parameter for Python 3.12+, fall back for older versions
            try:
                tar.extractall(path=groundtruth_workspace, filter='data')
            except TypeError:
                # Fall back to no filter for Python < 3.12
                tar.extractall(path=groundtruth_workspace)
        print(f"✓ Extracted groundtruth files to: {groundtruth_workspace}")
        return groundtruth_workspace, True
    except Exception as e:
        raise Exception(f"Failed to extract groundtruth files: {str(e)}")

def cleanup_extracted_files(groundtruth_workspace: str, was_extracted: bool):
    """Clean up extracted files if they were extracted during this evaluation"""
    if was_extracted:
        expected_dir = os.path.join(groundtruth_workspace, "Application_Materials_MaryCastillo_2201210606")
        if os.path.exists(expected_dir):
            try:
                nfs_safe_rmtree(expected_dir)
                print(f"✓ Cleaned up extracted files from: {groundtruth_workspace}")
            except Exception as e:
                print(f"⚠ Warning: Failed to clean up extracted files from {groundtruth_workspace}: {str(e)}")  

if __name__=="__main__":
    parser = ArgumentParser()
    print("args started")
    parser.add_argument("--agent_workspace", required=False)
    parser.add_argument("--groundtruth_workspace", required=False)
    parser.add_argument("--res_log_file", required=False)
    parser.add_argument("--launch_time", required=False)

    parser.add_argument('--subject', '-s', default='submit_material', help='邮件主题关键词')
    parser.add_argument('--task-root', type=str, default=None, help='任务根目录路径（如果不指定，则使用__file__推导）')
    args = parser.parse_args()

    # 导入 FILE_STRUCTURES 定义
    # 注意：generate_task_config.py 是源代码，位于 env_dir（代码目录）中
    # 使用 __file__ 定位 env_dir，而不是 task_dir
    env_dir_for_import = Path(__file__).parent.parent
    if str(env_dir_for_import) not in sys.path:
        sys.path.insert(0, str(env_dir_for_import))
    try:
        # Use regular import since env_dir_for_import is in sys.path
        from generate_task_config import PhDApplicationConfigGenerator  # type: ignore
        FILE_STRUCTURES = PhDApplicationConfigGenerator.FILE_STRUCTURES
    except ImportError as e:
        print(f"⚠️ 无法导入FILE_STRUCTURES，将使用默认验证: {e}")
        FILE_STRUCTURES = {}

    print("\n" + "=" * 60)
    print("🔍 申请博士邮件任务评估")
    print("=" * 60)

    # Extract groundtruth files if needed
    groundtruth_workspace, was_extracted = extract_groundtruth_files(args.groundtruth_workspace)
    
    try:
        # 读取任务配置
        if args.task_root:
            task_dir = Path(args.task_root)
        else:
            task_dir = Path(__file__).parent.parent

        # 创建临时目录用于附件处理
        temp_dir = task_dir / "temp_attachments"
        temp_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 创建临时目录: {temp_dir}")

        email_config_file = task_dir / "email_config.json"
        task_config_file = task_dir / "task_config_generated.json"
        receiver_config_file = task_dir / "files" / "receiver_config.json"

        if not email_config_file.exists():
            print(f"❌ 未找到邮箱配置文件: {email_config_file}")
            exit(1)
        
        # 读取 Mary 的邮箱配置（查看邮件的账号）
        with open(email_config_file, 'r', encoding='utf-8') as f:
            email_config = json.load(f)
        mary_email = email_config['email']
        mary_name = email_config['name']
        
        # 读取接收者配置（招生委员会成员，Agent 应该发邮件给这个人）
        if receiver_config_file.exists():
            with open(receiver_config_file, 'r', encoding='utf-8') as f:
                receiver_config = json.load(f)
            target_receiver_email = receiver_config['email']
            target_receiver_name = receiver_config['name']
            print(f"📬 目标接收者: {target_receiver_name} ({target_receiver_email})")
        else:
            target_receiver_email = None
            print("⚠️  未找到 receiver_config.json，将检查所有邮件")
        
        # 读取任务配置（了解有哪些 positive professor 及其文件结构要求）
        positive_structures = {}
        if task_config_file.exists():
            with open(task_config_file, 'r', encoding='utf-8') as f:
                task_config = json.load(f)
            
            print(f"📝 任务配置:")
            print(f"   导师数量: {task_config.get('num_professors', 'N/A')}")
            print(f"   积极回复数量: {task_config.get('num_positive', 'N/A')}")
            
            # 提取 positive professors 及其文件结构
            positive_profs = task_config.get('positive_professors', [])
            structure_info = task_config.get('structure_info', {})
            assign_different = task_config.get('assign_different_structures', False)
            
            print(f"\n✅ 有效的文件结构选项 ({len(positive_profs)} 个):")
            for prof in positive_profs:
                prof_email = prof['email']
                if assign_different and prof_email in structure_info:
                    structure = structure_info[prof_email]['structure_key']
                    structure_name = structure_info[prof_email]['structure_info']['name']
                else:
                    structure = task_config.get('structure', 'standard')
                    structure_name = structure_info.get('default', {}).get('structure_info', {}).get('name', '标准结构')
                
                # 获取结构定义
                structure_def = FILE_STRUCTURES.get(structure, {})
                
                positive_structures[prof_email] = {
                    'name': prof['full_name'],
                    'structure_key': structure,
                    'structure_name': structure_name,
                    'structure_def': structure_def
                }
                print(f"   • {prof['full_name']}: {structure_name} ({structure})")
        else:
            print("⚠️  未找到 task_config_generated.json，将使用默认验证")
        
        print(f"\n📧 Mary 的邮箱: {mary_name} ({mary_email})")
        
        # 确定 email 数据库目录
        if args.agent_workspace:
            workspace_parent = Path(args.agent_workspace).parent
            email_db_dir = str(workspace_parent / "local_db" / "emails")
        else:
            email_db_dir = str(Path(__file__).parent.parent / "local_db" / "emails")
        
        print(f"📂 Email 数据库目录: {email_db_dir}")
        
        if not Path(email_db_dir).exists():
            print(f"❌ Email 数据库目录不存在: {email_db_dir}")
            exit(1)
        
        # 初始化 EmailDatabase
        email_db = EmailDatabase(data_dir=email_db_dir)
        
        # 设置环境变量
        os.environ['EMAIL_DATA_DIR'] = email_db_dir
        
        print(f"\n🔍 检查邮件主题关键词: '{args.subject}'")
        print("=" * 60)
        
        # 检查 Agent 是否需要发送到多个 positive 教授，还是只发送到 admissions team
        assign_different = task_config.get('assign_different_structures', False) if task_config_file.exists() else False
        
        if assign_different and positive_structures:
            # 模式1：不同的教授有不同的要求，需要分别向每个教授发送邮件
            print(f"\n🔍 检查模式：多个教授有不同要求，需要分别发送邮件")
            print(f"   需要检查的教授数量: {len(positive_structures)}")
            
            all_success = True
            results = {}
            
            for prof_email, prof_info in positive_structures.items():
                print(f"\n{'='*60}")
                print(f"📧 检查发送给 {prof_info['name']} ({prof_email}) 的邮件")
                print(f"   要求的文件结构: {prof_info['structure_name']} ({prof_info['structure_key']})")
                
                # 为每个教授创建一个checker
                checker = LocalEmailAttachmentChecker(
                    email_db=email_db,
                    receiver_email=prof_email,
                    groundtruth_workspace=groundtruth_workspace,
                    temp_dir=str(temp_dir)
                )
                
                # 只允许这个教授的文件结构
                checker.set_valid_structures({prof_email: prof_info})
                
                success = checker.run(args.subject)
                results[prof_email] = {
                    'success': success,
                    'name': prof_info['name'],
                    'structure': prof_info['structure_name']
                }
                
                if not success:
                    all_success = False
            
            # 输出综合结果
            print("\n" + "=" * 60)
            print("📊 综合评估结果")
            print("=" * 60)
            
            for prof_email, result in results.items():
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['name']} ({prof_email})")
                print(f"   要求结构: {result['structure']}")
            
            if all_success:
                print("\n🎉 测试成功！")
                print("=" * 60)
                print(f"✅ 成功向所有 {len(positive_structures)} 个 positive 教授发送了符合要求的邮件")
            else:
                print("\n💥 测试失败！")
                print("=" * 60)
                print("📝 问题:")
                for prof_email, result in results.items():
                    if not result['success']:
                        print(f"   ❌ 未能向 {result['name']} ({prof_email}) 发送符合要求的邮件")
                        print(f"      • 邮件主题是否包含 'submit_material'？")
                        print(f"      • 附件结构是否符合 {result['structure']}？")
                        print(f"      • 所有必需的文件是否都存在？")
            
            success = all_success
            
        else:
            # 模式2：所有positive教授要求相同，或只发送到 admissions team
            if target_receiver_email:
                print(f"\n📧 检查发送到 {target_receiver_name} ({target_receiver_email}) 的邮件")
            else:
                print(f"\n📧 检查发送到默认接收者的邮件")
            
            # 创建本地邮件附件检查器并运行
            if target_receiver_email:
                check_email = target_receiver_email
            else:
                # 如果没有 receiver_config，就检查 Mary 收到的邮件（向后兼容）
                check_email = mary_email
            
            checker = LocalEmailAttachmentChecker(
                email_db=email_db,
                receiver_email=check_email,
                groundtruth_workspace=groundtruth_workspace,
                temp_dir=str(temp_dir)
            )
            
            # 如果有多个 positive structures，传递给 checker
            if positive_structures:
                checker.set_valid_structures(positive_structures)
            
            success = checker.run(args.subject)  
            
            print("\n" + "=" * 60)
            if success:
                print("🎉 测试成功！")
                print("=" * 60)
                print("✅ 找到匹配的邮件")
                print("✅ 邮件发送到正确的接收者")
                print("✅ 附件结构符合某个 positive professor 的要求")
                print("✅ 文件内容符合要求")
            else:
                print("💥 测试失败！")
                print("=" * 60)
                print("📝 常见问题:")
                if target_receiver_email:
                    print(f"   • Agent 是否发送邮件到 {target_receiver_name} ({target_receiver_email})？")
                else:
                    print("   • Agent 是否发送了邮件到正确的接收者？")
                print("   • 邮件主题是否包含 'submit_material'？")
                if positive_structures:
                    print(f"   • 附件结构是否符合以下任一 professor 的要求？")
                    for prof_email, info in positive_structures.items():
                        print(f"      - {info['name']}: {info['structure_name']}")
                else:
                    print("   • 附件文件夹结构是否正确？")
                print("   • 所有必需的文件是否都存在？")
        
    finally:
        # Clean up extracted files if they were extracted during this run
        cleanup_extracted_files(groundtruth_workspace, was_extracted)

        # Clean up temp_dir if it exists
        try:
            if 'temp_dir' in locals() and temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                print(f"🧹 清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")

    exit(0 if success else 1)