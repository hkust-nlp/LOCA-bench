#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版邮件注入脚本
使用本地 JSON 数据库注入邮件，而不是通过 SMTP/IMAP
"""

import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

# Set random seed for reproducibility
random.seed(42)

# Add mcp_convert path to import the database utilities
from mcp_convert.mcps.email.database_utils import EmailDatabase


# 干扰邮件模板（与原版相同）
DISTRACTION_EMAIL_TEMPLATES = [
    # 购物电商
    {
        "sender": "orders@amazon.com",
        "sender_name": "Amazon",
        "subject_prefix": "Your order has been shipped!",
        "body_template": "Track your package #AMZ{random_number}. Estimated delivery: {delivery_date}. Order total: ${amount:.2f}"
    },
    {
        "sender": "notifications@ebay.com",
        "sender_name": "eBay",
        "subject_prefix": "You've been outbid!",
        "body_template": "Someone outbid you on '{item_name}'. Current bid: ${amount:.2f}. Time left: {hours}h {minutes}m"
    },
    {
        "sender": "deals@target.com",
        "sender_name": "Target",
        "subject_prefix": "Weekend sale: Up to 50% off",
        "body_template": "Don't miss our weekend sale! Save up to 50% on home essentials, electronics, and more. Shop now!"
    },
    {
        "sender": "updates@etsy.com",
        "sender_name": "Etsy",
        "subject_prefix": "Items in your cart are selling fast!",
        "body_template": "The handmade {item_name} you saved has only {quantity} left. Complete your purchase before it's gone!"
    },
    
    # 娱乐媒体
    {
        "sender": "info@netflix.com",
        "sender_name": "Netflix",
        "subject_prefix": "New shows added to your list",
        "body_template": "Watch now! {show_count} new episodes of your favorite shows are available. Start streaming today!"
    },
    {
        "sender": "noreply@youtube.com",
        "sender_name": "YouTube",
        "subject_prefix": "Your video got {views} views!",
        "body_template": "Congratulations! Your video '{video_name}' reached {views} views and has {likes} likes. Keep creating!"
    },
    {
        "sender": "notifications@spotify.com",
        "sender_name": "Spotify",
        "subject_prefix": "Your Discover Weekly is ready",
        "body_template": "We've created a fresh playlist just for you with {song_count} songs we think you'll love. Start listening!"
    },
    {
        "sender": "updates@tiktok.com",
        "sender_name": "TikTok",
        "subject_prefix": "Your video is trending!",
        "body_template": "Your recent TikTok has {views}K views and {likes}K likes! It's trending in your area. 🔥"
    },
    
    # 社交网络
    {
        "sender": "notifications@linkedin.com",
        "sender_name": "LinkedIn",
        "subject_prefix": "Someone viewed your profile",
        "body_template": "{viewer_count} people viewed your profile this week. See who's interested in your experience!"
    },
    {
        "sender": "notification@facebook.com",
        "sender_name": "Facebook",
        "subject_prefix": "You have {count} friend requests",
        "body_template": "You have {friend_requests} friend requests and {notifications} notifications waiting for you. Check them out!"
    },
    {
        "sender": "no-reply@instagram.com",
        "sender_name": "Instagram",
        "subject_prefix": "Your Story highlights got {count}+ views!",
        "body_template": "Your recent Story got {views} views! {username} and {other_count} others liked it. 📸"
    },
    {
        "sender": "notify@twitter.com",
        "sender_name": "Twitter",
        "subject_prefix": "Your tweet is getting attention",
        "body_template": "Your tweet has {retweets} retweets and {likes} likes. {username} and others are talking about it!"
    },
    
    # 金融银行
    {
        "sender": "alerts@chase.com",
        "sender_name": "Chase Bank",
        "subject_prefix": "Account Alert: Large purchase detected",
        "body_template": "A purchase of ${amount:.2f} was made at {merchant}. If this wasn't you, please contact us immediately."
    },
    {
        "sender": "service@paypal.com",
        "sender_name": "PayPal",
        "subject_prefix": "You've received ${amount:.2f}",
        "body_template": "{sender_name} sent you ${amount:.2f}. The money is now in your PayPal account."
    },
    {
        "sender": "notifications@wellsfargo.com",
        "sender_name": "Wells Fargo",
        "subject_prefix": "Your statement is ready",
        "body_template": "Your monthly statement for account ending in {account_digits} is now available. Review your transactions."
    },
    
    # 外卖配送
    {
        "sender": "orders@ubereats.com",
        "sender_name": "Uber Eats",
        "subject_prefix": "Your order is on the way!",
        "body_template": "Your order from {restaurant} is being prepared. Estimated delivery: {delivery_time}. Track your driver!"
    },
    {
        "sender": "no-reply@doordash.com",
        "sender_name": "DoorDash",
        "subject_prefix": "Your order from {restaurant} is on the way!",
        "body_template": "Your Dasher is {minutes} minutes away with your food. Get ready! 🚗"
    },
    {
        "sender": "support@grubhub.com",
        "sender_name": "Grubhub",
        "subject_prefix": "Your delivery has arrived!",
        "body_template": "Your order from {restaurant} has been delivered. Enjoy your meal! Don't forget to rate your experience."
    },
    
    # 旅行住宿
    {
        "sender": "noreply@booking.com",
        "sender_name": "Booking.com",
        "subject_prefix": "Price drop alert!",
        "body_template": "Save ${savings:.2f} on your {destination} trip! Book now and lock in this great rate."
    },
    {
        "sender": "automated@airbnb.com",
        "sender_name": "Airbnb",
        "subject_prefix": "Your trip to {destination} is coming up",
        "body_template": "Your check-in is in {days} days. Here's your host's contact info and directions to the property."
    },
    {
        "sender": "reservations@delta.com",
        "sender_name": "Delta Airlines",
        "subject_prefix": "Check in now for your flight",
        "body_template": "Your flight to {destination} departs in 24 hours. Check in now and save time at the airport!"
    },
    
    # 新闻资讯
    {
        "sender": "newsletters@nytimes.com",
        "sender_name": "The New York Times",
        "subject_prefix": "Your Daily Briefing",
        "body_template": "Here are today's top stories: {headline1}. {headline2}. {headline3}. Read more at NYTimes.com"
    },
    {
        "sender": "noreply@medium.com",
        "sender_name": "Medium",
        "subject_prefix": "Top stories for you",
        "body_template": "{story_count} stories picked for you based on your reading history. Estimated reading time: {minutes} min."
    },
    
    # 团购优惠
    {
        "sender": "deals@groupon.com",
        "sender_name": "Groupon",
        "subject_prefix": "{percent}% off at {business}",
        "body_template": "Limited time offer! Save {percent}% on {service} at {business}. Only {quantity} vouchers left!"
    },
    {
        "sender": "offers@livingsocial.com",
        "sender_name": "LivingSocial",
        "subject_prefix": "Flash sale: {category}",
        "body_template": "24-hour flash sale on {category}! Up to {percent}% off. Don't miss out!"
    },
    
    # 社区论坛
    {
        "sender": "noreply@reddit.com",
        "sender_name": "Reddit",
        "subject_prefix": "Trending posts you might have missed",
        "body_template": "r/{subreddit} has {post_count} trending posts. Top post: '{post_title}' with {upvotes}k upvotes."
    },
    {
        "sender": "noreply@stackoverflow.com",
        "sender_name": "Stack Overflow",
        "subject_prefix": "Your question has {count} new answers",
        "body_template": "{answer_count} developers answered your question about {topic}. One answer was marked as helpful!"
    },
    
    # 健康健身
    {
        "sender": "noreply@myfitnesspal.com",
        "sender_name": "MyFitnessPal",
        "subject_prefix": "Weekly progress: You're on track!",
        "body_template": "Great job! You logged {days} days this week and stayed under your calorie goal {goal_days} times. 💪"
    },
    {
        "sender": "hello@headspace.com",
        "sender_name": "Headspace",
        "subject_prefix": "Time for your daily meditation",
        "body_template": "Take {minutes} minutes for yourself today. Try our new {meditation_type} meditation session."
    },
    
    # 游戏娱乐
    {
        "sender": "noreply@steampowered.com",
        "sender_name": "Steam",
        "subject_prefix": "Weekend Deal: {percent}% off",
        "body_template": "Save {percent}% on {game_name} this weekend! Sale ends {end_date}. Add to cart now! 🎮"
    },
    {
        "sender": "no-reply@twitch.tv",
        "sender_name": "Twitch",
        "subject_prefix": "Your favorite streamer is live!",
        "body_template": "{streamer} is now streaming {game}! Join {viewers}K viewers watching now. 🔴"
    }
]


def generate_distraction_email(template: Dict, timestamp: float) -> Dict:
    """根据模板生成一封干扰邮件"""
    
    # 随机填充变量
    variables = {
        "random_number": random.randint(100000, 999999),
        "delivery_date": (datetime.fromtimestamp(timestamp) + timedelta(days=random.randint(2, 7))).strftime("%B %d"),
        "amount": random.uniform(15.99, 299.99),
        "hours": random.randint(0, 23),
        "minutes": random.randint(0, 59),
        "item_name": random.choice(["wireless headphones", "vintage watch", "yoga mat", "coffee maker", "desk lamp"]),
        "quantity": random.randint(2, 8),
        "show_count": random.randint(3, 15),
        "views": random.randint(100, 9999),
        "likes": random.randint(10, 999),
        "video_name": random.choice(["Morning Routine", "Quick Tutorial", "Daily Vlog", "Product Review", "Cooking Demo"]),
        "song_count": random.randint(20, 50),
        "viewer_count": random.randint(5, 50),
        "count": random.randint(3, 15),
        "friend_requests": random.randint(1, 8),
        "notifications": random.randint(5, 25),
        "username": random.choice(["@mike_j", "@sarah_k", "@alex_m", "@jamie_r", "@chris_b"]),
        "other_count": random.randint(10, 99),
        "retweets": random.randint(5, 500),
        "merchant": random.choice(["Best Buy", "Whole Foods", "Target", "Apple Store", "Amazon"]),
        "sender_name": random.choice(["Mom", "Dad", "Friend", "Alex", "Jamie"]),
        "account_digits": str(random.randint(1000, 9999)),
        "restaurant": random.choice(["Thai Garden", "Pizza Palace", "Burger Joint", "Sushi Bar", "Taco Truck"]),
        "delivery_time": (datetime.fromtimestamp(timestamp) + timedelta(minutes=random.randint(20, 45))).strftime("%I:%M %p"),
        "destination": random.choice(["New York", "San Francisco", "Tokyo", "Paris", "London"]),
        "savings": random.uniform(30, 150),
        "days": random.randint(3, 14),
        "headline1": "Major economic reforms announced",
        "headline2": "Technology sector sees growth",
        "headline3": "Climate summit reaches agreement",
        "story_count": random.randint(5, 12),
        "percent": random.choice([20, 30, 40, 50, 60, 70]),
        "business": random.choice(["Spa Retreat", "Italian Restaurant", "Golf Course", "Yoga Studio"]),
        "service": random.choice(["massage", "dinner for two", "golf", "yoga class"]),
        "category": random.choice(["Restaurants", "Travel", "Beauty", "Activities"]),
        "subreddit": random.choice(["technology", "gaming", "movies", "books", "fitness"]),
        "post_count": random.randint(5, 20),
        "post_title": "TIL something interesting",
        "upvotes": random.randint(1, 50),
        "answer_count": random.randint(2, 8),
        "topic": random.choice(["Python", "JavaScript", "React", "SQL", "algorithms"]),
        "goal_days": random.randint(4, 7),
        "meditation_type": random.choice(["mindfulness", "sleep", "stress relief", "focus"]),
        "game_name": random.choice(["Indie Masterpiece", "Adventure Quest", "Strategy Game", "Puzzle Collection"]),
        "end_date": (datetime.fromtimestamp(timestamp) + timedelta(days=2)).strftime("%B %d"),
        "streamer": random.choice(["ProGamer123", "StreamQueen", "NinjaKing", "GamerGirl"]),
        "game": random.choice(["Fortnite", "Minecraft", "League of Legends", "Valorant"]),
        "viewers": random.randint(1, 50)
    }
    
    # 格式化主题和内容
    subject = template["subject_prefix"].format(**variables)
    body = template["body_template"].format(**variables)
    
    return {
        "from": template["sender"],
        "from_name": template["sender_name"],
        "subject": subject,
        "body": body,
        "timestamp": timestamp
    }


def inject_exam_emails_from_config_simplified(
    config_file: str,
    email_timestamp: float = None,
    clear_inbox: bool = True,
    add_distractions: bool = True,
    agent_workspace: str = None
) -> bool:
    """
    简化版邮件注入函数 - 使用本地数据库
    
    Args:
        config_file: 邮件配置文件路径
        email_timestamp: 邮件时间戳（可选）
        clear_inbox: 是否清空收件箱
        add_distractions: 是否添加干扰邮件
        agent_workspace: Agent工作空间路径
    
    Returns:
        是否成功
    """
    try:
        # 初始化邮件数据库
        if agent_workspace:
            workspace_parent = Path(agent_workspace).parent
            email_data_dir = str(workspace_parent / "local_db" / "emails")
        else:
            email_data_dir = str(Path(__file__).parent.parent / "local_db" / "emails")
        
        Path(email_data_dir).mkdir(parents=True, exist_ok=True)
        email_db = EmailDatabase(data_dir=email_data_dir)
        
        # 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        recipient_email = config['recipient']['email']
        recipient_password = config['recipient'].get('password', 'default_password')
        recipient_name = config['recipient'].get('name', 'User')
        
        sender_email = config['sender_account']['email']
        sender_password = config['sender_account'].get('password', 'default_password')
        sender_name = config['sender_account'].get('name', 'Sender')
        
        # 创建用户账户（直接操作 users.json）
        if not email_db.users:
            email_db.users = {}
        
        email_db.users[recipient_email] = {
            "email": recipient_email,
            "password": recipient_password,
            "name": recipient_name
        }
        email_db.users[sender_email] = {
            "email": sender_email,
            "password": sender_password,
            "name": sender_name
        }
        
        # 为所有考试通知的教师创建邮箱账户
        exam_notifications = config.get('exam_notifications', [])
        for notification in exam_notifications:
            teacher_email = notification.get('teacher_email')
            teacher_name = notification.get('teacher', 'Teacher')
            if teacher_email:
                email_db.users[teacher_email] = {
                    "email": teacher_email,
                    "password": "teacher_pass",
                    "name": teacher_name
                }
        
        email_db._save_json_file("users.json", email_db.users)
        
        # 创建用户数据目录和文件
        all_user_emails = [recipient_email, sender_email]
        # 添加所有教师邮箱
        for notification in exam_notifications:
            teacher_email = notification.get('teacher_email')
            if teacher_email and teacher_email not in all_user_emails:
                all_user_emails.append(teacher_email)
        
        for email in all_user_emails:
            user_dir = email_db._get_user_data_dir(email)
            Path(user_dir).mkdir(parents=True, exist_ok=True)
            
            # 创建空的邮件、文件夹和草稿文件
            emails_file = os.path.join(user_dir, "emails.json")
            folders_file = os.path.join(user_dir, "folders.json")
            drafts_file = os.path.join(user_dir, "drafts.json")
            
            if not os.path.exists(emails_file) or (clear_inbox and email == recipient_email):
                email_db._save_json_file(emails_file, {})
            
            if not os.path.exists(folders_file):
                email_db._save_json_file(folders_file, {
                    "INBOX": {"total": 0, "unread": 0},
                    "Sent": {"total": 0, "unread": 0},
                    "Trash": {"total": 0, "unread": 0}
                })
            
            if not os.path.exists(drafts_file):
                email_db._save_json_file(drafts_file, {})
        
        # 使用当前时间或指定时间
        if email_timestamp is None:
            email_timestamp = datetime.now().timestamp()
        
        exam_time = datetime.fromtimestamp(email_timestamp)
        
        # 直接操作收件人的邮件文件（支持自定义时间戳）
        recipient_dir = email_db._get_user_data_dir(recipient_email)
        recipient_emails_file = os.path.join(recipient_dir, "emails.json")
        recipient_folders_file = os.path.join(recipient_dir, "folders.json")
        
        recipient_emails = email_db._load_json_file(recipient_emails_file)
        recipient_folders = email_db._load_json_file(recipient_folders_file)
        
        def inject_email_to_inbox(from_email: str, from_name: str, subject: str, body: str, timestamp: float):
            """直接注入邮件到收件箱"""
            email_id = email_db._generate_id(recipient_emails)
            email_date = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            
            email_data = {
                "id": email_id,
                "folder": "INBOX",
                "from": from_email,
                "from_name": from_name,
                "to": recipient_email,
                "cc": "",
                "bcc": "",
                "subject": subject,
                "body": body,
                "html_body": body,
                "date": email_date,
                "read": False,
                "important": False,
                "has_attachments": False,
                "attachments": []
            }
            
            recipient_emails[email_id] = email_data
            
            # 更新文件夹计数
            if "INBOX" in recipient_folders:
                recipient_folders["INBOX"]["total"] = recipient_folders["INBOX"].get("total", 0) + 1
                recipient_folders["INBOX"]["unread"] = recipient_folders["INBOX"].get("unread", 0) + 1
        
        # 添加干扰邮件（之前）
        if add_distractions:
            print("\n🎭 步骤1: 注入干扰邮件（考试通知前）...")
            num_before = random.randint(6, 12)
            print(f"📮 正在注入 {num_before} 封干扰邮件（考试通知前）...")
            
            for i in range(num_before):
                # 随机选择模板
                template = random.choice(DISTRACTION_EMAIL_TEMPLATES)
                
                # 生成时间：考试邮件前 0.5-5 天
                days_before = random.uniform(0.5, 5)
                distraction_timestamp = email_timestamp - (days_before * 24 * 3600)
                
                # 生成邮件
                email_data = generate_distraction_email(template, distraction_timestamp)
                
                # 注入到收件箱
                inject_email_to_inbox(
                    from_email=email_data["from"],
                    from_name=email_data["from_name"],
                    subject=email_data["subject"],
                    body=email_data["body"],
                    timestamp=distraction_timestamp
                )
                
                # 显示时间
                email_time_str = datetime.fromtimestamp(distraction_timestamp).strftime("%m-%d %H:%M")
                print(f"  ✅ {email_data['from_name']}: {email_data['subject'][:50]}... ({email_time_str})")
        
        # 注入考试通知邮件（支持多个考试通知）
        print("\n📧 步骤2: 注入考试通知邮件...")
        
        # 获取考试通知列表
        exam_notifications = config.get('exam_notifications', [])
        
        # 检查是否有考试通知需要注入
        if not exam_notifications:
            print("⚠️  没有考试通知邮件需要注入（可能没有email来源的课程）")
        else:
            # 读取模板文件
            exam_content = config.get('email_content', {})
            template_file = exam_content.get('template_file')
            if template_file:
                template_path = Path(config_file).parent / template_file
                if template_path.exists():
                    with open(template_path, 'r', encoding='utf-8') as f:
                        body_template = f.read()
                else:
                    body_template = "Exam notification content here."
            else:
                body_template = "Exam notification content here."
            
            # 遍历所有考试通知
            print(f"📮 正在注入 {len(exam_notifications)} 封考试通知邮件...")
            
            for idx, notification in enumerate(exam_notifications):
                # 为每个通知添加一点时间偏移（几秒到几分钟），使邮件更自然
                time_offset = random.randint(0, 300)  # 0-5分钟的随机偏移
                current_timestamp = email_timestamp + time_offset
                
                subject = notification.get('subject', 'Final Exam Notification')
                
                # 获取教师邮箱，如果没有则使用默认sender
                teacher_email = notification.get('teacher_email', sender_email)
                teacher_name = notification.get('teacher', sender_name)
                
                # 准备模板变量
                exam_info = {
                    'recipient_name': recipient_name,
                    'sender_name': teacher_name,
                    'sender_email': teacher_email,  # 使用教师邮箱
                    'send_time': datetime.fromtimestamp(current_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    'course_name': notification.get('course_name', 'Course'),
                    'exam_date': notification.get('exam_date', 'TBD'),
                    'exam_time': notification.get('exam_time', 'TBD'),
                    'exam_location': notification.get('exam_location', 'TBD'),
                    'exam_type': notification.get('exam_type', 'Closed-book'),
                    'duration': notification.get('duration', 'TBD')
                }
                
                # 替换模板变量
                try:
                    body = body_template.format(**exam_info)
                except KeyError as e:
                    print(f"  ⚠️  模板变量缺失: {e}, 使用默认内容")
                    body = f"Exam notification for {exam_info['course_name']}"
                
                # 注入到收件箱（使用教师邮箱作为发件人）
                inject_email_to_inbox(
                    from_email=teacher_email,
                    from_name=teacher_name,
                    subject=subject,
                    body=body,
                    timestamp=current_timestamp
                )
                
                print(f"  ✅ {notification.get('course_code', 'Course')}: {subject} (from {teacher_email})")
            
            exam_time_str = exam_time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"✅ {len(exam_notifications)} 封考试通知邮件注入成功！(基准时间: {exam_time_str})")
        
        # 添加干扰邮件（之后）
        if add_distractions:
            print("\n🎭 步骤3: 注入干扰邮件（考试通知后）...")
            num_after = random.randint(4, 8)
            print(f"📮 正在注入 {num_after} 封干扰邮件（考试通知后）...")
            
            for i in range(num_after):
                # 随机选择模板
                template = random.choice(DISTRACTION_EMAIL_TEMPLATES)
                
                # 生成时间：考试邮件后 1-48 小时
                hours_after = random.uniform(1, 48)
                distraction_timestamp = email_timestamp + (hours_after * 3600)
                
                # 生成邮件
                email_data = generate_distraction_email(template, distraction_timestamp)
                
                # 注入到收件箱
                inject_email_to_inbox(
                    from_email=email_data["from"],
                    from_name=email_data["from_name"],
                    subject=email_data["subject"],
                    body=email_data["body"],
                    timestamp=distraction_timestamp
                )
                
                # 显示时间
                email_time_str = datetime.fromtimestamp(distraction_timestamp).strftime("%m-%d %H:%M")
                print(f"  ✅ {email_data['from_name']}: {email_data['subject'][:50]}... ({email_time_str})")
        
        # 保存所有邮件到文件
        email_db._save_json_file(recipient_emails_file, recipient_emails)
        email_db._save_json_file(recipient_folders_file, recipient_folders)
        
        print("\n✅ 邮件注入完成！")
        return True
        
    except Exception as e:
        print(f"❌ 邮件注入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='简化版邮件注入脚本')
    parser.add_argument('--config', default='../files/email_config.json', help='配置文件路径')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--agent_workspace', help='Agent工作空间路径')
    args = parser.parse_args()
    
    # 测试模式
    if args.test:
        email_time = datetime(2025, 1, 1, 10, 0, 0)
        email_timestamp = email_time.timestamp()
        
        success = inject_exam_emails_from_config_simplified(
            args.config,
            email_timestamp=email_timestamp,
            clear_inbox=True,
            add_distractions=True,
            agent_workspace=args.agent_workspace
        )
        
        sys.exit(0 if success else 1)
