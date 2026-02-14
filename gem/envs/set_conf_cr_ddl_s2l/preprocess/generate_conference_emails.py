#!/usr/bin/env python3
"""
会议截止日期邮件生成器

生成包含不同会议 camera-ready deadline 的邮件
支持难度控制：会议数量、噪声邮件、截止日期变更等
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from argparse import ArgumentParser, RawDescriptionHelpFormatter


class ConferenceEmailGenerator:
    """会议邮件生成器"""
    
    # 基础会议信息模板
    BASE_CONFERENCES = {
        'COML': {
            'full_name': 'Conference on Machine Learning',
            'acronym': 'COML',
            'track_types': ['main-track', 'workshop', 'demo'],
            'organizer': 'coml-chairs@ml-conference.org',
            'website': 'https://coml2025.org'
        },
        'NLPR': {
            'full_name': 'Natural Language Processing Research Conference',
            'acronym': 'NLPR',
            'track_types': ['main-track', 'short-paper', 'industry'],
            'organizer': 'nlpr-committee@nlp-research.org',
            'website': 'https://nlpr2025.org'
        },
        'CVAI': {
            'full_name': 'Computer Vision and AI Symposium',
            'acronym': 'CVAI',
            'track_types': ['main-track', 'workshop', 'poster'],
            'organizer': 'cvai-organizers@vision-ai.org',
            'website': 'https://cvai2025.org'
        },
        'DLNN': {
            'full_name': 'Deep Learning and Neural Networks Conference',
            'acronym': 'DLNN',
            'track_types': ['main-track', 'tutorial', 'demo'],
            'organizer': 'dlnn-chairs@deeplearning.org',
            'website': 'https://dlnn2025.org'
        },
        'ROBO': {
            'full_name': 'International Conference on Robotics',
            'acronym': 'ROBO',
            'track_types': ['main-track', 'application', 'workshop'],
            'organizer': 'robo-committee@robotics.org',
            'website': 'https://robo2025.org'
        },
        'DATA': {
            'full_name': 'Big Data Analytics Conference',
            'acronym': 'DATA',
            'track_types': ['main-track', 'industry', 'poster'],
            'organizer': 'data-chairs@bigdata-conf.org',
            'website': 'https://data2025.org'
        }
    }
    
    # 会议主题模板（用于生成更多会议）
    CONFERENCE_TOPICS = [
        # AI & ML
        'Machine Learning', 'Deep Learning', 'Neural Networks', 'Computer Vision',
        'Natural Language Processing', 'Reinforcement Learning', 'Transfer Learning',
        'Meta Learning', 'Few-Shot Learning', 'Self-Supervised Learning',
        'Generative AI', 'Large Language Models', 'Multimodal Learning',
        'Graph Neural Networks', 'Attention Mechanisms', 'Transformer Models',
        
        # Robotics & Automation
        'Robotics', 'Autonomous Systems', 'Robot Learning', 'Human-Robot Interaction',
        'Swarm Intelligence', 'Drone Systems', 'Industrial Automation',
        
        # Data & Analytics
        'Data Science', 'Big Data', 'Data Mining', 'Text Mining', 'Stream Processing',
        'Data Visualization', 'Business Analytics', 'Predictive Analytics',
        'Time Series Analysis', 'Anomaly Detection', 'Clustering Analysis',
        
        # Software & Systems
        'Software Engineering', 'Distributed Systems', 'Database Systems',
        'Operating Systems', 'Parallel Computing', 'Grid Computing',
        'High Performance Computing', 'Scientific Computing',
        
        # Cloud & Infrastructure
        'Cloud Computing', 'Edge Computing', 'Fog Computing', 'Serverless Computing',
        'Cloud Native', 'DevOps', 'Microservices', 'Containerization',
        'Service Mesh', 'Infrastructure as Code',
        
        # Security & Privacy
        'Cybersecurity', 'Network Security', 'Information Security', 'Privacy Preserving',
        'Cryptography', 'Blockchain', 'Digital Forensics', 'Threat Intelligence',
        
        # Networks & Communications
        'Network Protocols', 'Wireless Networks', '5G Networks', '6G Networks',
        'Mobile Computing', 'Sensor Networks', 'IoT', 'Network Optimization',
        
        # Web & Multimedia
        'Web Technologies', 'Web Services', 'Semantic Web', 'Social Media',
        'Multimedia Systems', 'Graphics', 'Image Processing', 'Video Analysis',
        'Audio Processing', 'Speech Recognition', 'Music Information Retrieval',
        
        # Extended Reality
        'Virtual Reality', 'Augmented Reality', 'Mixed Reality', 'Haptic Systems',
        'Game Development', '3D Graphics', 'Computer Animation',
        
        # Specialized Domains
        'Bioinformatics', 'Computational Biology', 'Healthcare Informatics',
        'Medical Imaging', 'Drug Discovery', 'Genomics', 'Proteomics',
        'Smart Cities', 'Urban Computing', 'Transportation Systems',
        'Energy Systems', 'Environmental Informatics', 'Climate Modeling',
        'Financial Technology', 'Algorithmic Trading', 'Risk Management',
        
        # Human-Centered Computing
        'Human-Computer Interaction', 'User Experience', 'Accessibility',
        'Social Computing', 'Collaborative Systems', 'Crowdsourcing',
        'Recommender Systems', 'Personalization', 'Sentiment Analysis',
        
        # Information & Knowledge
        'Information Retrieval', 'Knowledge Management', 'Knowledge Graphs',
        'Question Answering', 'Information Extraction', 'Document Analysis',
        'Search Engines', 'Ontology Engineering',
        
        # Emerging Technologies
        'Quantum Computing', 'Neuromorphic Computing', 'DNA Computing',
        'Optical Computing', 'Brain-Computer Interfaces', 'Wearable Computing',
        'Affective Computing', 'Pervasive Computing', 'Ubiquitous Computing'
    ]
    
    CONFERENCE_TYPES = [
        'Conference', 'Symposium', 'Workshop', 'Summit', 'Congress',
        'Forum', 'Colloquium', 'Meeting', 'Convention'
    ]
    
    def __init__(self, seed: int = 42, max_conferences: int = 200):
        random.seed(seed)
        self.seed = seed
        self.max_conferences = max_conferences
        self.CONFERENCES = self._generate_conferences()
    
    def _generate_conferences(self) -> Dict:
        """动态生成会议列表"""
        conferences = self.BASE_CONFERENCES.copy()
        
        # 生成额外的会议
        used_acronyms = set(conferences.keys())
        
        for i in range(self.max_conferences - len(self.BASE_CONFERENCES)):
            # 随机选择主题和类型
            topic = random.choice(self.CONFERENCE_TOPICS)
            conf_type = random.choice(self.CONFERENCE_TYPES)
            
            # 生成缩写（取首字母）
            words = topic.split()
            if len(words) >= 2:
                acronym = ''.join([w[0] for w in words[:min(4, len(words))]])
            else:
                acronym = words[0][:4].upper()
            
            # 如果缩写重复，添加数字后缀
            base_acronym = acronym
            counter = 1
            while acronym in used_acronyms:
                acronym = f"{base_acronym}{counter}"
                counter += 1
            
            used_acronyms.add(acronym)
            
            # 生成会议信息
            conferences[acronym] = {
                'full_name': f"International {conf_type} on {topic}",
                'acronym': acronym,
                'track_types': random.sample(
                    ['main-track', 'workshop', 'demo', 'short-paper', 'industry', 'poster', 'tutorial', 'application'],
                    k=random.randint(3, 5)
                ),
                'organizer': f"{acronym.lower()}-chairs@{topic.lower().replace(' ', '-')}-conf.org",
                'website': f"https://{acronym.lower()}2025.org"
            }
        
        return conferences
    
    def generate_deadline(self, base_date: datetime, days_offset: int = 15) -> str:
        """生成截止日期（ISO格式）"""
        deadline = base_date + timedelta(days=days_offset)
        # 使用 AoE 时区 (UTC-12)
        return f"{deadline.strftime('%Y-%m-%d')}T23:59:00-12:00"
    
    def generate_camera_ready_email(self, 
                                    conference_key: str,
                                    track: str,
                                    deadline: str,
                                    email_date: str,
                                    is_reminder: bool = False,
                                    is_extension: bool = False,
                                    old_deadline: str = None) -> Dict:
        """生成 camera-ready 邮件"""
        conf = self.CONFERENCES[conference_key]
        
        if is_extension:
            subject = f"[{conf['acronym']} {track}] Camera-Ready Deadline EXTENDED"
            body = f"""Dear Author,

We are writing to inform you that the camera-ready deadline for {conf['full_name']} {track} has been EXTENDED.

Original deadline: {old_deadline}
NEW deadline: {deadline}

Please prepare your final camera-ready manuscript by the new deadline.

Best regards,
{conf['full_name']} Organizing Committee
{conf['organizer']}
Website: {conf['website']}
"""
        elif is_reminder:
            subject = f"[{conf['acronym']} {track}] REMINDER: Camera-Ready Deadline Approaching"
            body = f"""Dear Author,

This is a friendly reminder that the camera-ready deadline for {conf['full_name']} {track} is approaching.

Deadline: {deadline}

Please ensure you submit your final camera-ready manuscript before the deadline.

Best regards,
{conf['full_name']} Organizing Committee
{conf['organizer']}
Website: {conf['website']}
"""
        else:
            subject = f"[{conf['acronym']} {track}] Camera-Ready Submission Instructions"
            body = f"""Dear Author,

Congratulations on your paper acceptance to {conf['full_name']} {track}!

Please submit your camera-ready manuscript by:
Deadline: {deadline}

Submission requirements:
- Format: PDF (max 10 pages)
- Follow the camera-ready guidelines on our website
- Include author information and acknowledgments
- Sign the copyright form

Best regards,
{conf['full_name']} Organizing Committee
{conf['organizer']}
Website: {conf['website']}
"""
        
        # 生成唯一的邮件ID
        email_id = f"email_{conference_key}_{track}_{random.randint(1000, 9999)}"
        
        return {
            'email_id': email_id,
            'subject': subject,
            'from_addr': conf['organizer'],
            'to_addr': None,  # 将在主函数中设置
            'date': email_date,
            'body_text': body,
            'body_html': f"<html><body><pre>{body}</pre></body></html>",
            'folder': 'INBOX',
            'is_read': False,
            'is_important': False,
            'message_id': f"<{email_id}@{conf['organizer'].split('@')[1]}>",
            'attachments': []
        }
    
    def generate_noise_email(self, 
                            conference_key: str,
                            email_date: str,
                            noise_type: str = 'general') -> Dict:
        """生成噪声邮件（非camera-ready相关）"""
        conf = self.CONFERENCES[conference_key]
        
        noise_templates = {
            'general': {
                'subject': f"[{conf['acronym']}] Conference Update",
                'body': f"""Dear Participant,

We have some general updates about {conf['full_name']}.

Registration is now open. Early bird discount available until next month.

Best regards,
{conf['full_name']} Team
"""
            },
            'workshop': {
                'subject': f"[{conf['acronym']} Workshop] Call for Participation",
                'body': f"""Dear Researcher,

We invite you to participate in the workshops at {conf['full_name']}.

Workshop submission deadline: TBD

Best regards,
Workshop Chairs
"""
            },
            'registration': {
                'subject': f"[{conf['acronym']}] Registration Reminder",
                'body': f"""Dear Author,

Don't forget to register for {conf['full_name']}.

Early registration deadline: Soon

Best regards,
Registration Team
"""
            }
        }
        
        template = noise_templates.get(noise_type, noise_templates['general'])
        email_id = f"noise_{conference_key}_{noise_type}_{random.randint(1000, 9999)}"
        
        return {
            'email_id': email_id,
            'subject': template['subject'],
            'from_addr': conf['organizer'],
            'to_addr': None,
            'date': email_date,
            'body_text': template['body'],
            'body_html': f"<html><body><pre>{template['body']}</pre></body></html>",
            'folder': 'INBOX',
            'is_read': random.choice([True, False]),
            'is_important': False,
            'message_id': f"<{email_id}@{conf['organizer'].split('@')[1]}>",
            'attachments': []
        }
    
    def generate_emails(self,
                       num_target_conferences: int = 1,
                       num_noise_conferences: int = 2,
                       num_noise_emails_per_conf: int = 2,
                       enable_reminders: bool = False,
                       enable_extensions: bool = False,
                       base_date: datetime = None,
                       target_deadline_offset: int = 15) -> Dict:
        """
        生成邮件集合
        
        Args:
            num_target_conferences: 包含真实 camera-ready deadline 的会议数量
            num_noise_conferences: 噪声会议数量（不包含目标信息）
            num_noise_emails_per_conf: 每个会议的噪声邮件数量
            enable_reminders: 是否发送提醒邮件（增加难度）
            enable_extensions: 是否包含截止日期延期（增加难度）
            base_date: 基准日期
            target_deadline_offset: 目标截止日期偏移天数
        """
        if base_date is None:
            base_date = datetime(2025, 9, 15)  # 默认基准日期
        
        emails = []
        target_conferences_list = []  # 存储所有目标会议信息
        
        # 选择会议
        all_conf_keys = list(self.CONFERENCES.keys())
        random.shuffle(all_conf_keys)
        
        target_conf_keys = all_conf_keys[:num_target_conferences]
        noise_conf_keys = all_conf_keys[num_target_conferences:num_target_conferences + num_noise_conferences]
        
        print(f"🎯 目标会议（包含 camera-ready deadline）: {', '.join(target_conf_keys)}")
        print(f"🔊 噪声会议（不包含目标信息）: {', '.join(noise_conf_keys)}")
        
        # 生成目标会议的邮件（包含camera-ready deadline）
        for i, conf_key in enumerate(target_conf_keys):
            conf = self.CONFERENCES[conf_key]
            track = random.choice(conf['track_types'])
            
            # 第一个会议使用 main-track
            if i == 0:
                track = 'main-track'
            
            # 生成截止日期
            deadline = self.generate_deadline(base_date, target_deadline_offset + i * 2)
            
            # 保存会议信息
            conference_info = {
                'conference': conf_key,
                'track': track,
                'deadline': deadline,
                'full_name': conf['full_name']
            }
            
            # 邮件发送日期（截止日期前几天）
            email_date_dt = base_date - timedelta(days=random.randint(1, 3))
            email_date = email_date_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 主要邮件
            email = self.generate_camera_ready_email(
                conf_key, track, deadline, email_date
            )
            emails.append(email)

            # 先处理延期（如果启用），以便后续提醒邮件能使用正确的 deadline
            final_deadline = deadline
            extension_date_dt = None
            if enable_extensions and random.random() < 0.5:
                old_deadline = deadline
                final_deadline = self.generate_deadline(base_date, target_deadline_offset + i * 2 + 3)
                extension_date_dt = base_date - timedelta(days=random.randint(0, 1))
                extension_date = extension_date_dt.strftime('%Y-%m-%d %H:%M:%S')

                extension_email = self.generate_camera_ready_email(
                    conf_key, track, final_deadline, extension_date,
                    is_extension=True, old_deadline=old_deadline
                )
                emails.append(extension_email)

                # 更新会议信息中的deadline
                conference_info['deadline'] = final_deadline

            # 再处理提醒邮件（根据提醒日期决定使用哪个 deadline）
            if enable_reminders:
                reminder_date_dt = base_date - timedelta(days=random.randint(0, 1))
                reminder_date = reminder_date_dt.strftime('%Y-%m-%d %H:%M:%S')

                # 如果提醒在延期之后发送，使用延期后的 deadline
                if extension_date_dt and reminder_date_dt >= extension_date_dt:
                    reminder_deadline = final_deadline
                else:
                    reminder_deadline = deadline

                reminder_email = self.generate_camera_ready_email(
                    conf_key, track, reminder_deadline, reminder_date, is_reminder=True
                )
                emails.append(reminder_email)
            
            # 添加到目标会议列表
            target_conferences_list.append(conference_info)
        
        # 生成噪声会议的邮件（不包含camera-ready信息）
        for conf_key in noise_conf_keys:
            num_emails = random.randint(1, num_noise_emails_per_conf)
            
            for _ in range(num_emails):
                noise_type = random.choice(['general', 'workshop', 'registration'])
                email_date_dt = base_date - timedelta(days=random.randint(0, 5))
                email_date = email_date_dt.strftime('%Y-%m-%d %H:%M:%S')
                
                noise_email = self.generate_noise_email(conf_key, email_date, noise_type)
                emails.append(noise_email)
        
        # 按日期排序（最旧的在前）
        emails.sort(key=lambda x: x['date'])
        
        # 生成元数据
        metadata = {
            'base_date': base_date.strftime('%Y-%m-%d'),
            'total_emails': len(emails),
            'target_info': {
                'conferences': target_conferences_list,  # 所有目标会议列表
                'count': num_target_conferences
            },
            'noise_info': {
                'conferences': noise_conf_keys,  # 噪声会议列表
                'count': num_noise_conferences,
                'emails_per_conf': num_noise_emails_per_conf
            },
            'difficulty': {
                'enable_reminders': enable_reminders,
                'enable_extensions': enable_extensions
            }
        }
        
        return {
            'emails': emails,
            'metadata': metadata
        }


def parse_arguments():
    """解析命令行参数"""
    parser = ArgumentParser(
        description='会议截止日期邮件生成器',
        formatter_class=RawDescriptionHelpFormatter
    )
    
    # 基础配置
    parser.add_argument('--num-target', type=int, default=1,
                        help='包含目标信息的会议数量，默认: 1')
    parser.add_argument('--num-noise', type=int, default=2,
                        help='噪声会议数量，默认: 2')
    parser.add_argument('--noise-emails', type=int, default=2,
                        help='每个噪声会议的邮件数量，默认: 2')
    parser.add_argument('--max-conferences', type=int, default=200,
                        help='最大会议池大小，默认: 200')
    parser.add_argument('--seed', type=int, default=42,
                        help='随机种子，默认: 42')
    
    # 难度控制
    parser.add_argument('--enable-reminders', action='store_true',
                        help='启用提醒邮件（增加邮件数量）')
    parser.add_argument('--enable-extensions', action='store_true',
                        help='启用截止日期延期（增加混淆）')
    parser.add_argument('--base-date', type=str, default='2025-09-15',
                        help='基准日期（today），格式: YYYY-MM-DD')
    parser.add_argument('--deadline-offset', type=int, default=15,
                        help='deadline 距离 base_date 的天数，默认: 15')
    
    # 输出配置
    parser.add_argument('--output-dir', type=str, default='.',
                        help='输出目录，默认: 当前目录')
    parser.add_argument('--receiver-email', type=str, default='rkelly27@mcp.com',
                        help='接收者邮箱，默认: rkelly27@mcp.com')
    
    # 预设难度
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard', 'expert'],
                        help='预设难度等级')
    
    return parser.parse_args()


def apply_difficulty_preset(args):
    """应用难度预设"""
    if args.difficulty == 'easy':
        # 简单：1个目标会议，1个噪声会议，无额外复杂度
        args.num_target = 1
        args.num_noise = 1
        args.noise_emails = 1
        args.enable_reminders = False
        args.enable_extensions = False
        
    elif args.difficulty == 'medium':
        # 中等：1个目标会议，2-3个噪声会议，有提醒邮件
        args.num_target = 1
        args.num_noise = 2
        args.noise_emails = 2
        args.enable_reminders = True
        args.enable_extensions = False
        
    elif args.difficulty == 'hard':
        # 困难：1-2个目标会议，3-4个噪声会议，有提醒和延期
        args.num_target = random.randint(1, 2)
        args.num_noise = 3
        args.noise_emails = 3
        args.enable_reminders = True
        args.enable_extensions = True
        
    elif args.difficulty == 'expert':
        # 专家：多个目标会议，大量噪声，所有混淆因素
        args.num_target = random.randint(2, 3)
        args.num_noise = 4
        args.noise_emails = 4
        args.enable_reminders = True
        args.enable_extensions = True


def main():
    args = parse_arguments()
    
    # 应用难度预设
    if args.difficulty:
        apply_difficulty_preset(args)
    
    print("=" * 60)
    print("会议截止日期邮件生成器")
    print("=" * 60)
    print(f"配置:")
    print(f"  会议池大小: {args.max_conferences}")
    print(f"  目标会议数: {args.num_target}")
    print(f"  噪声会议数: {args.num_noise}")
    print(f"  噪声邮件/会议: {args.noise_emails}")
    print(f"  启用提醒: {args.enable_reminders}")
    print(f"  启用延期: {args.enable_extensions}")
    print(f"  基准日期: {args.base_date}")
    print(f"  截止日期偏移: {args.deadline_offset} 天")
    print(f"  随机种子: {args.seed}")
    print("=" * 60)
    
    # 解析基准日期
    base_date = datetime.strptime(args.base_date, '%Y-%m-%d')
    
    # 生成邮件
    print(f"🔧 初始化会议生成器（生成 {args.max_conferences} 个会议）...")
    generator = ConferenceEmailGenerator(seed=args.seed, max_conferences=args.max_conferences)
    print(f"✅ 会议池已生成: {len(generator.CONFERENCES)} 个会议")
    result = generator.generate_emails(
        num_target_conferences=args.num_target,
        num_noise_conferences=args.num_noise,
        num_noise_emails_per_conf=args.noise_emails,
        enable_reminders=args.enable_reminders,
        enable_extensions=args.enable_extensions,
        base_date=base_date,
        target_deadline_offset=args.deadline_offset
    )
    
    # 设置接收者邮箱
    for email in result['emails']:
        email['to_addr'] = args.receiver_email
    
    # 保存到文件
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存邮件备份
    backup_file = output_dir / "files" / "emails_backup.json"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 成功生成 {len(result['emails'])} 封邮件")
    
    target_info = result['metadata'].get('target_info', {})
    target_conferences = target_info.get('conferences', [])
    
    if len(target_conferences) == 1:
        print(f"   目标会议: {target_conferences[0]['conference']}")
        print(f"   截止日期: {target_conferences[0]['deadline']}")
    else:
        print(f"   目标会议数: {len(target_conferences)}")
        for conf_info in target_conferences:
            print(f"      • {conf_info['conference']} ({conf_info['track']}): {conf_info['deadline']}")
    
    print(f"   输出文件: {backup_file}")
    
    # 保存 groundtruth
    groundtruth_dir = output_dir / "groundtruth_workspace"
    groundtruth_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 today.txt
    today_file = groundtruth_dir / "today.txt"
    with open(today_file, 'w') as f:
        f.write(args.base_date)
    
    print(f"   Today 文件: {today_file}")
    
    # 保存元数据用于评估
    metadata_file = groundtruth_dir / "conference_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(result['metadata'], f, indent=2, ensure_ascii=False)
    
    print(f"   元数据文件: {metadata_file}")
    print("\n✅ 邮件生成完成！")


if __name__ == "__main__":
    main()

