from argparse import ArgumentParser
import sys
import os
from pathlib import Path


if __name__=="__main__":
    parser = ArgumentParser(description="Course Assistant 评估脚本")
    parser.add_argument("--agent_workspace", required=False, help="Agent工作空间路径")
    parser.add_argument("--groundtruth_workspace", required=False, help="Groundtruth工作空间路径")
    parser.add_argument("--res_log_file", required=False, help="结果日志文件路径")
    parser.add_argument("--launch_time", required=False, help="Launch time")
    parser.add_argument('--subject', '-s', default='nlp-course-emergency', help='邮件主题关键词')
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 Course Assistant 任务评估")
    print("=" * 60)
    
    # 检查 check_local.py 是否存在
    current_dir = Path(__file__).parent
    check_local_path = current_dir / "check_local.py"
    
    if not check_local_path.exists():
        print("\n❌ 错误: check_local.py 不存在")
        print("💡 请先运行预处理脚本生成配置:")
        print("   python3 preprocess/main.py --agent_workspace /path/to/workspace")
        exit(1)
    
    # 动态导入 check_local
    try:
        from .check_local import main as check_local_main
        print("✅ 使用动态生成的 check_local.py 配置")
    except ImportError as e:
        print(f"❌ 错误: 无法导入 check_local: {e}")
        print("💡 请确保 check_local.py 格式正确")
        exit(1)
    
    # 设置 EMAIL_DATA_DIR 环境变量
    if args.agent_workspace:
        workspace_parent = Path(args.agent_workspace).parent
        email_db_dir = str(workspace_parent / "local_db" / "emails")
        os.environ['EMAIL_DATA_DIR'] = email_db_dir
        print(f"📂 Agent 工作空间: {args.agent_workspace}")
        print(f"📂 Email 数据库目录: {email_db_dir}")
    
    # 显示检查信息
    print(f"📧 检查邮件主题: {args.subject}")
    print("=" * 60)
    
    # 运行邮件检查
    try:
        success = check_local_main()
    except Exception as e:
        print(f"\n❌ 运行过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 评估成功！所有学生都收到了正确的催促邮件")
        print("=" * 60)
        print("✅ 邮件主题正确: nlp-course-emergency")
        print("✅ 邮件内容包含学生姓名和学号")
        print("✅ 没有多余或错误的邮件")
    else:
        print("💥 评估失败！请检查以上错误信息")
        print("=" * 60)
        print("📝 常见问题:")
        print("   • Agent 是否正确识别了未提交作业的学生？")
        print("   • 邮件主题是否为 'nlp-course-emergency'？")
        print("   • 邮件内容是否包含学生的姓名和学号？")
        print("   • 是否发送到了正确的学生邮箱？")
    
    exit(0 if success else 1)