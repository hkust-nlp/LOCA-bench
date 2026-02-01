#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Canvas List Test 任务配置生成器
动态生成不同难度的任务配置
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple
import argparse


class TaskConfigGenerator:
    """任务配置生成器"""
    
    # 课程模板库 (扩展到 55 门课程)
    COURSE_TEMPLATES = {
        "CS": [
            {"name": "Introduction to Computer Science", "code": "CS101", "credits": 3},
            {"name": "Data Structures and Algorithms", "code": "CS201", "credits": 4},
            {"name": "Database Systems", "code": "CS301", "credits": 4},
            {"name": "Software Engineering Practice", "code": "CS302", "credits": 3},
            {"name": "Software Engineering", "code": "CS401", "credits": 4},
            {"name": "Operating Systems", "code": "CS303", "credits": 4},
            {"name": "Computer Networks", "code": "CS304", "credits": 3},
            {"name": "Compiler Design", "code": "CS402", "credits": 4},
            {"name": "Web Development", "code": "CS202", "credits": 3},
            {"name": "Mobile Application Development", "code": "CS305", "credits": 3},
            {"name": "Computer Graphics", "code": "CS403", "credits": 3},
            {"name": "Parallel Computing", "code": "CS404", "credits": 3},
            {"name": "Computer Architecture", "code": "CS405", "credits": 4},
            {"name": "Algorithm Analysis", "code": "CS406", "credits": 3},
            {"name": "Theory of Computation", "code": "CS407", "credits": 3},
        ],
        "AI": [
            {"name": "Fundamentals of Artificial Intelligence", "code": "AI101", "credits": 3},
            {"name": "Machine Learning", "code": "AI201", "credits": 4},
            {"name": "Deep Learning", "code": "AI301", "credits": 4},
            {"name": "Computer Vision", "code": "AI302", "credits": 3},
            {"name": "Natural Language Processing", "code": "NLP101", "credits": 3},
            {"name": "Reinforcement Learning", "code": "AI303", "credits": 4},
            {"name": "Data Mining", "code": "AI304", "credits": 3},
            {"name": "Statistical Learning", "code": "AI305", "credits": 3},
        ],
        "MATH": [
            {"name": "Linear Algebra", "code": "MATH101", "credits": 3},
            {"name": "Advanced Mathematics", "code": "MATH201", "credits": 4},
            {"name": "Probability and Statistics", "code": "MATH202", "credits": 3},
            {"name": "Discrete Mathematics", "code": "MATH102", "credits": 3},
            {"name": "Numerical Analysis", "code": "MATH301", "credits": 4},
            {"name": "Calculus I", "code": "MATH103", "credits": 4},
            {"name": "Calculus II", "code": "MATH104", "credits": 4},
            {"name": "Mathematical Modeling", "code": "MATH302", "credits": 3},
        ],
        "DB": [
            {"name": "Database Systems Fundamentals", "code": "DB101", "credits": 2},
            {"name": "Advanced Database Systems", "code": "DB201", "credits": 3},
            {"name": "Big Data Technologies", "code": "DB301", "credits": 4},
            {"name": "Data Warehousing", "code": "DB302", "credits": 3},
            {"name": "Big Data Analytics", "code": "DB401", "credits": 4},
        ],
        "NET": [
            {"name": "Network Programming", "code": "NET101", "credits": 3},
            {"name": "Network Security", "code": "NET201", "credits": 3},
            {"name": "Cloud Computing", "code": "NET301", "credits": 4},
            {"name": "Distributed Systems", "code": "NET302", "credits": 4},
            {"name": "Full Stack Development", "code": "WEB301", "credits": 4},
            {"name": "Backend Development", "code": "WEB302", "credits": 3},
        ],
        "SEC": [
            {"name": "Information Security", "code": "SEC101", "credits": 4},
            {"name": "Cryptography", "code": "SEC201", "credits": 4},
            {"name": "Cybersecurity", "code": "SEC301", "credits": 3},
        ],
        "OTHER": [
            {"name": "English Foundation", "code": "ENG101", "credits": 1},
            {"name": "Modern European History", "code": "HIST301", "credits": 4},
            {"name": "Critical Thinking and Logic", "code": "PHIL201", "credits": 3},
            {"name": "Business Communication", "code": "BUS101", "credits": 2},
            {"name": "Psychology", "code": "PSY101", "credits": 3},
            {"name": "Human Computer Interaction", "code": "HCI301", "credits": 3},
            {"name": "Software Testing", "code": "SE301", "credits": 3},
            {"name": "Project Management", "code": "PM201", "credits": 2},
            {"name": "Technical Writing", "code": "TW101", "credits": 2},
            {"name": "Ethics in Computing", "code": "ETH201", "credits": 2},
            {"name": "Embedded Systems", "code": "EMB301", "credits": 4},
        ]
    }
    
    # 教师邮箱池
    TEACHER_EMAILS = [
        "stephenb@mcp.com",
        "brandonr@mcp.com",
        "richardl@mcp.com",
        "jenniferj31@mcp.com",
        "smith@mcp.com",
        "johnson@mcp.com",
        "williams@mcp.com",
    ]
    
    # 考试类型
    EXAM_TYPES = ["closed_book", "open_book", "no_exam"]
    
    # 建筑和房间
    BUILDINGS = ["A", "B", "C", "D"]
    
    def __init__(self, seed: int = 42):
        """初始化生成器"""
        random.seed(seed)
        self.current_date = datetime.now()
    
    def generate_student_users(self, num_students: int) -> List[Dict[str, Any]]:
        """生成学生用户列表"""
        users = []
        
        # 第一个学生必须是 Ryan Brown (任务的主角)
        users.append({
            "id": 14,
            "first_name": "Ryan",
            "last_name": "Brown",
            "full_name": "Ryan Brown",
            "email": "ryan.brown93@mcp.com",
            "password": "BryapivvLK7C"
        })
        
        # 生成其他学生
        first_names = ["Jacob", "Christine", "Emily", "Michael", "Sarah", 
                      "David", "Jessica", "James", "Ashley", "Robert", "Amanda",
                      "Daniel", "Jennifer", "Matthew", "Lisa", "Christopher", "Karen"]
        last_names = ["Flores", "Hall", "Smith", "Johnson", "Williams",
                     "Jones", "Davis", "Miller", "Wilson", "Moore", "Taylor",
                     "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin"]
        
        used_emails = {"ryan.brown93@mcp.com"}
        
        for i in range(1, num_students):
            first = random.choice(first_names)
            last = random.choice(last_names)
            
            # 生成唯一邮箱
            email_base = f"{first.lower()}.{last.lower()}"
            email = f"{email_base}{random.randint(1, 99)}@mcp.com"
            while email in used_emails:
                email = f"{email_base}{random.randint(1, 99)}@mcp.com"
            used_emails.add(email)
            
            # 生成随机密码
            password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
            
            users.append({
                "id": 14 + i,
                "first_name": first,
                "last_name": last,
                "full_name": f"{first} {last}",
                "email": email,
                "password": password
            })
        
        return users
    
    def generate_quiz_questions(self, num_questions: int, points_per_question: int = 50) -> List[Dict]:
        """生成测验问题"""
        question_templates = [
            {
                "text": "What is the primary function of {topic}?",
                "answers": [
                    "To manage {function1}",
                    "To create {function2}",
                    "To compile {function3}",
                    "To browse {function4}"
                ]
            },
            {
                "text": "Which {concept} follows the {principle} principle?",
                "answers": [
                    "{option1}",
                    "{option2}",
                    "{option3}",
                    "{option4}"
                ]
            }
        ]
        
        questions = []
        for i in range(num_questions):
            template = random.choice(question_templates)
            questions.append({
                "question_text": f"Question {i+1}: Sample question text",
                "question_type": "multiple_choice_question",
                "points_possible": points_per_question,
                "answers": [
                    {"answer_text": f"Correct answer", "answer_weight": 100},
                    {"answer_text": f"Wrong answer 1", "answer_weight": 0},
                    {"answer_text": f"Wrong answer 2", "answer_weight": 0},
                    {"answer_text": f"Wrong answer 3", "answer_weight": 0}
                ]
            })
        
        return questions
    
    def generate_quiz(self, difficulty: str = "medium") -> Dict:
        """生成测验配置"""
        difficulty_settings = {
            "easy": {"num_questions": 2, "time_limit": 45, "points": 80, "attempts": 3},
            "medium": {"num_questions": 2, "time_limit": 60, "points": 100, "attempts": 2},
            "hard": {"num_questions": 3, "time_limit": 90, "points": 150, "attempts": 1},
        }
        
        settings = difficulty_settings.get(difficulty, difficulty_settings["medium"])
        points_per_question = settings["points"] // settings["num_questions"]
        
        # 随机决定未来的截止时间（1-14天）
        due_days = random.randint(1, 14)
        due_date = self.current_date + timedelta(days=due_days)
        
        return {
            "title": f"Quiz - Sample Title",
            "description": "Sample quiz description covering key concepts.",
            "quiz_type": random.choice(["Graded Quiz", "assignment"]),
            "time_limit": settings["time_limit"],
            "shuffle_answers": True,
            "show_correct_answers": random.choice([True, False]),
            "allowed_attempts": settings["attempts"],
            "scoring_policy": "keep_highest",
            "points_possible": settings["points"],
            "due_at": due_date.strftime("%Y-%m-%dT23:59:00Z"),
            "questions": self.generate_quiz_questions(settings["num_questions"], points_per_question)
        }
    
    def generate_assignment(self, difficulty: str = "medium") -> Dict:
        """生成作业配置"""
        difficulty_settings = {
            "easy": {"points": 50, "types": "online_text_entry"},
            "medium": {"points": 100, "types": ["online_upload", "online_text_entry"]},
            "hard": {"points": 150, "types": ["online_upload", "online_text_entry"]},
        }
        
        settings = difficulty_settings.get(difficulty, difficulty_settings["medium"])
        
        # 随机决定未来的截止时间（1-14天）
        due_days = random.randint(1, 14)
        due_date = self.current_date + timedelta(days=due_days)
        
        assignment = {
            "name": "Sample Assignment",
            "description": "Sample assignment description with requirements.",
            "points_possible": settings["points"],
            "due_at": due_date.strftime("%Y-%m-%dT23:59:00Z"),
            "submission_types": settings["types"],
            "published": True
        }
        
        # 如果是复杂作业，添加允许的文件扩展名
        if isinstance(settings["types"], list) and "online_upload" in settings["types"]:
            assignment["allowed_extensions"] = ["pdf", "zip", "docx"]
        
        return assignment
    
    def generate_announcement(self, course: Dict, has_exam: bool = True) -> Dict:
        """生成课程公告"""
        if not has_exam or course.get("exam_type") == "no_exam":
            return {
                "title": f"Course Information - {course['course_code']}",
                "content": f"Welcome to {course['name']}! This course does not have a traditional final exam."
            }
        
        exam_time = course.get("exam_time", "TBD")
        if exam_time == "TBD":
            return {
                "title": f"Final Exam Announcement - {course['course_code']}",
                "content": "Exam information is to be confirmed and will be officially communicated via email."
            }
        
        exam_date = datetime.strptime(exam_time, "%Y-%m-%d %H:%M")
        duration = course.get("duration", "120")
        location = course.get("location", "TBD")
        
        content = f"""Dear {course['course_code']} students,

This is to announce that the final exam for {course['name']} will be held on:

📅 Date: {exam_date.strftime('%B %d, %Y')}
⏰ Time: {exam_date.strftime('%I:%M %p')}
⏱️ Duration: {duration} minutes
📍 Location: {location}

"""
        
        if course.get("exam_type") == "open_book":
            content += "Note: This is an OPEN BOOK exam. You may bring your textbooks and notes.\n\n"
        
        content += """Please arrive 15 minutes before the exam time. Bring your student ID and necessary writing materials.

Good luck!

Best regards,
Course Instructor"""
        
        return {
            "title": f"Final Exam Announcement - {course['course_code']}",
            "content": content
        }
    
    def generate_courses(self, 
                        num_courses: int = 10,
                        quiz_probability: float = 0.8,
                        assignment_probability: float = 0.7,
                        quiz_difficulty: str = "medium",
                        assignment_difficulty: str = "medium",
                        exemption_probability: float = 0.1,
                        no_exam_probability: float = 0.15,
                        student_emails: List[str] = None) -> List[Dict]:
        """生成课程配置列表"""
        
        courses = []
        used_codes = set()

        # 收集所有课程模板
        all_templates = []
        for category, templates in self.COURSE_TEMPLATES.items():
            all_templates.extend(templates)

        # 随机选择课程（允许重复使用模板以支持更多课程，上限800）
        num_courses = min(num_courses, 800)
        if num_courses <= len(all_templates):
            selected_templates = random.sample(all_templates, num_courses)
        else:
            # 先使用所有模板，然后随机重复选择填充剩余数量
            selected_templates = all_templates.copy()
            remaining = num_courses - len(all_templates)
            selected_templates.extend(random.choices(all_templates, k=remaining))
        
        for idx, template in enumerate(selected_templates):
            # 确保课程代码唯一
            course_code = f"{template['code']}-{idx+1}"
            while course_code in used_codes:
                course_code = f"{template['code']}-{random.randint(1, 99)}"
            used_codes.add(course_code)
            
            # 基本课程信息
            course = {
                "name": f"{template['name']}-{idx+1}",
                "course_code": course_code,
                "teacher": random.choice(self.TEACHER_EMAILS),
                "credits": template["credits"],
            }
            
            # 考试类型和时间
            exam_type = random.choice(self.EXAM_TYPES) if random.random() < no_exam_probability else random.choice(["closed_book", "open_book"])
            course["exam_type"] = exam_type
            
            if exam_type != "no_exam":
                # 生成考试时间（未来2-4周）
                exam_date = self.current_date + timedelta(days=random.randint(14, 28))
                course["exam_time"] = exam_date.strftime("%Y-%m-%d %H:%M")
                course["duration"] = str(random.choice([90, 120, 150, 180]))
                course["duration_unit"] = "minutes"
                
                # 生成考场
                building = random.choice(self.BUILDINGS)
                room = random.randint(101, 505)
                course["location"] = f"Building {building} Room {room}"
            else:
                course["duration"] = "20"
                course["duration_unit"] = "minutes"
                course["location"] = f"Building {random.choice(self.BUILDINGS)} Room {random.randint(101, 505)}"
                course["assessment"] = random.choice([
                    "Assignments + Group Presentation",
                    "Project + Report",
                    "Portfolio Assessment"
                ])
            
            # 免修分数（低概率）
            if random.random() < exemption_probability:
                course["exemption_score"] = random.choice([85, 90, 95])
            
            # 生成测验（根据概率）
            if random.random() < quiz_probability:
                course["quiz"] = self.generate_quiz(quiz_difficulty)
                course["quiz"]["title"] = f"{course_code} {random.choice(['Midterm', 'Chapter', 'Unit'])} Quiz"
            
            # 生成作业（根据概率）
            if random.random() < assignment_probability:
                course["assignment"] = self.generate_assignment(assignment_difficulty)
                course["assignment"]["name"] = f"{course_code} {random.choice(['Homework', 'Project', 'Assignment'])}"
            
            # 生成公告
            course["announcement"] = self.generate_announcement(course, exam_type != "no_exam")
            
            # 添加学生
            if student_emails:
                course["students"] = student_emails
            
            courses.append(course)
        
        return courses
    
    def generate_submission_config(self, 
                                   courses: List[Dict],
                                   submission_probability: float = 0.3) -> Dict:
        """生成作业提交配置（噪声）"""
        submissions = {}
        
        for course in courses:
            course_code = course["course_code"]
            
            # 决定是否为这个课程的作业添加已提交状态
            if "assignment" in course and random.random() < submission_probability:
                submissions[course_code] = {
                    "assignment_submitted": True,
                    "submission_time": (self.current_date - timedelta(days=random.randint(1, 7))).isoformat()
                }
        
        return submissions
    
    def generate_memory_json(self, courses: List[Dict], exemption_meet_probability: float = 0.6) -> Dict:
        """生成 Ryan Brown 的 memory.json，包含免修课程信息
        
        Args:
            courses: 课程列表
            exemption_meet_probability: Ryan 达到免修要求的概率 (0-1)
        """
        
        # 基础个人信息
        observations = [
            "Student ID: 2201210606",
            "Email: ryan.brown93@mcp.com",
            "Address: Building 1, Unit 1, Haidian Road Community",
            "Phone: 13812345678",
            "Major: Computer Science and Technology",
            "Hobbies: Programming, Reading, Basketball",
            "Graduation year: 2024",
            "GPA: 3.8",
            "University: Peking University",
            "Degree: Bachelor's",
            "Education period: 2020-09 to 2024-06",
            "Currently pursuing: Master's degree",
            "Health condition: Gout, cannot eat seafood",
            "Daily routine: Regular schedule",
            "Mental health: Healthy",
            "Personality: Lively",
            "Swimming ability: Cannot swim",
            "Birthday: 2000-01-01"
        ]
        
        # 添加免修课程信息
        exemption_courses = []
        non_exemption_courses = []
        
        for course in courses:
            if "exemption_score" in course:
                exemption_score = course["exemption_score"]
                course_name = course["name"]
                course_code = course["course_code"]
                
                # 根据课程类型生成不同的免修考试类型
                if "English" in course_name or "ENG" in course_code:
                    exam_type = "entrance English exam"
                elif "Math" in course_name or "MATH" in course_code:
                    exam_type = "mathematics placement test"
                elif "Physics" in course_name or "PHYS" in course_code:
                    exam_type = "physics proficiency exam"
                else:
                    exam_type = f"{course_name} qualification exam"
                
                # 随机决定 Ryan 是否达到免修要求
                meets_requirement = random.random() < exemption_meet_probability
                
                if meets_requirement:
                    # 达到免修要求：分数略高于或等于免修分数
                    actual_score = exemption_score + random.randint(0, 5)
                    observation = f"Score for the {exam_type}: {actual_score}. The exemption requirement is {exemption_score}, which has been met. This may qualify for course exemption for {course_code}."
                    
                    exemption_courses.append({
                        "course_code": course_code,
                        "course_name": course_name,
                        "exemption_score": exemption_score,
                        "actual_score": actual_score,
                        "exam_type": exam_type,
                        "qualified": True
                    })
                else:
                    # 未达到免修要求：分数低于免修分数
                    actual_score = exemption_score - random.randint(1, 10)
                    observation = f"Score for the {exam_type}: {actual_score}. The exemption requirement is {exemption_score}, which has not been met. Need to take {course_code}."
                    
                    non_exemption_courses.append({
                        "course_code": course_code,
                        "course_name": course_name,
                        "exemption_score": exemption_score,
                        "actual_score": actual_score,
                        "exam_type": exam_type,
                        "qualified": False
                    })
                
                observations.append(observation)
        
        memory = {
            "type": "entity",
            "entityType": "Person",
            "name": "Ryan Brown",
            "observations": observations
        }
        
        return memory, exemption_courses, non_exemption_courses
    
    def generate_groundtruth_csv(self, 
                                 courses: List[Dict], 
                                 exemption_courses: List[Dict],
                                 submissions: Dict) -> Tuple[List[Dict], List[Dict]]:
        """生成 groundtruth CSV 数据（Ryan Brown 需要完成的任务）"""
        
        # 获取免修课程的 course_code 集合
        exempted_course_codes = {ec['course_code'] for ec in exemption_courses}
        
        # 获取已提交作业的 course_code 集合
        submitted_course_codes = set(submissions.keys())
        
        print(f"\n📋 Groundtruth 过滤信息:")
        print(f"   免修课程: {len(exempted_course_codes)} 个 - {list(exempted_course_codes) if exempted_course_codes else '无'}")
        print(f"   已提交作业: {len(submitted_course_codes)} 个 - {list(submitted_course_codes) if submitted_course_codes else '无'}")
        
        quiz_data = []
        assignment_data = []
        filtered_assignments = []
        
        for course in courses:
            course_code = course['course_code']
            course_name = course['name']
            credits = course.get('credits', 3)
            
            # 如果课程被免修，跳过所有任务
            if course_code in exempted_course_codes:
                continue
            
            # 处理 Quiz
            if 'quiz' in course:
                quiz = course['quiz']
                quiz_data.append({
                    'course_code': course_code,
                    'course_name': course_name,
                    'credits': credits,
                    'quiz_title': quiz.get('title', 'Quiz'),
                    'number_of_questions': len(quiz.get('questions', [])),
                    'time_limit': quiz.get('time_limit', 60),
                    'allowed_attempts': quiz.get('allowed_attempts', 1),
                    'scoring_policy': quiz.get('scoring_policy', 'keep_highest'),
                    'points_possible': quiz.get('points_possible', 100),
                    'deadline': quiz.get('due_at', '')
                })
            
            # 处理 Assignment（排除已提交的）
            if 'assignment' in course:
                if course_code not in submitted_course_codes:
                    assignment = course['assignment']
                    assignment_data.append({
                        'course_code': course_code,
                        'assignment_title': assignment.get('name', 'Assignment'),
                        'description': assignment.get('description', ''),
                        'deadline': assignment.get('due_at', ''),
                        'course_name': course_name,
                        'points_possible': assignment.get('points_possible', 100)
                    })
                else:
                    # 记录被过滤的作业
                    filtered_assignments.append(course_code)
        
        # 按 deadline 和 course_code 排序
        # 排序规则：
        # 1. 首先按 deadline 的时间顺序（chronological order）
        # 2. 相同 deadline 的任务按 course_code 的字典顺序（dictionary order）
        from datetime import datetime
        
        def sort_key(item):
            try:
                deadline = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00'))
            except:
                deadline = datetime.max
            return (deadline, item['course_code'])
        
        quiz_data.sort(key=sort_key)
        assignment_data.sort(key=sort_key)
        
        # 打印过滤结果
        if filtered_assignments:
            print(f"   ✓ 已过滤已提交作业: {filtered_assignments}")
        
        return quiz_data, assignment_data
    
    def save_groundtruth_csv(self, 
                            quiz_data: List[Dict], 
                            assignment_data: List[Dict],
                            output_dir: Path):
        """保存 groundtruth CSV 文件"""
        import csv
        
        groundtruth_dir = output_dir / "groundtruth_workspace"
        groundtruth_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 quiz_info.csv（即使数据为空也保存列名）
        quiz_csv_path = groundtruth_dir / "quiz_info.csv"
        fieldnames_quiz = ['course_code', 'course_name', 'credits', 'quiz_title', 
                          'number_of_questions', 'time_limit', 'allowed_attempts', 
                          'scoring_policy', 'points_possible', 'deadline']
        with open(quiz_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames_quiz)
            writer.writeheader()
            if quiz_data:
                writer.writerows(quiz_data)
            f.write('\n')  # 添加空行到文件末尾
        print(f"✅ 已保存: {quiz_csv_path} ({len(quiz_data)} 个 quiz)")
        
        # 保存 assignment_info.csv（即使数据为空也保存列名）
        assignment_csv_path = groundtruth_dir / "assignment_info.csv"
        fieldnames_assignment = ['course_code', 'assignment_title', 'description', 
                                'deadline', 'course_name', 'points_possible']
        with open(assignment_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames_assignment)
            writer.writeheader()
            if assignment_data:
                writer.writerows(assignment_data)
            f.write('\n')  # 添加空行到文件末尾
        print(f"✅ 已保存: {assignment_csv_path} ({len(assignment_data)} 个 assignment)")
        
        return quiz_csv_path, assignment_csv_path
    
    def save_config(self, 
                   output_dir: Path,
                   num_courses: int = 10,
                   num_students: int = 3,
                   quiz_probability: float = 0.8,
                   assignment_probability: float = 0.7,
                   submission_probability: float = 0.3,
                   quiz_difficulty: str = "medium",
                   assignment_difficulty: str = "medium",
                   exemption_probability: float = 0.1,
                   no_exam_probability: float = 0.15,
                   exemption_meet_probability: float = 0.6):
        """保存完整的任务配置"""
        
        print(f"🎲 生成任务配置...")
        print(f"   课程数量: {num_courses}")
        print(f"   学生数量: {num_students}")
        print(f"   测验概率: {quiz_probability:.0%}")
        print(f"   作业概率: {assignment_probability:.0%}")
        print(f"   已提交概率: {submission_probability:.0%}")
        print(f"   免修概率: {exemption_probability:.0%}")
        print(f"   无考试概率: {no_exam_probability:.0%}")
        
        # 生成学生用户
        students = self.generate_student_users(num_students)
        student_emails = [s["email"] for s in students]
        
        # 生成课程
        courses = self.generate_courses(
            num_courses=num_courses,
            quiz_probability=quiz_probability,
            assignment_probability=assignment_probability,
            quiz_difficulty=quiz_difficulty,
            assignment_difficulty=assignment_difficulty,
            exemption_probability=exemption_probability,
            no_exam_probability=no_exam_probability,
            student_emails=student_emails
        )
        
        # 生成提交配置
        submissions = self.generate_submission_config(courses, submission_probability)
        
        # 生成 Ryan Brown 的 memory.json
        memory, exemption_courses, non_exemption_courses = self.generate_memory_json(
            courses, 
            exemption_meet_probability
        )
        
        # 保存文件
        files_dir = output_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 course_config.json
        course_config_path = files_dir / "course_config.json"
        with open(course_config_path, 'w', encoding='utf-8') as f:
            json.dump({"courses": courses}, f, indent=2, ensure_ascii=False)
        print(f"✅ 已保存: {course_config_path}")
        
        # 保存 canvas_users.json
        users_path = files_dir / "canvas_users.json"
        with open(users_path, 'w', encoding='utf-8') as f:
            json.dump(students, f, indent=2, ensure_ascii=False)
        print(f"✅ 已保存: {users_path}")
        
        # 保存 submission_config.json（用于 preprocess）
        submission_path = files_dir / "submission_config.json"
        with open(submission_path, 'w', encoding='utf-8') as f:
            json.dump(submissions, f, indent=2, ensure_ascii=False)
        print(f"✅ 已保存: {submission_path}")
        
        # 保存 memory.json 到 initial_workspace/memory/
        memory_dir = output_dir / "initial_workspace" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_path = memory_dir / "memory.json"
        with open(memory_path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False)
        print(f"✅ 已保存: {memory_path}")
        
        # 生成并保存 groundtruth CSV 文件
        quiz_data, assignment_data = self.generate_groundtruth_csv(
            courses, 
            exemption_courses, 
            submissions
        )
        self.save_groundtruth_csv(quiz_data, assignment_data, output_dir)
        
        # 统计信息
        total_quizzes = sum(1 for c in courses if "quiz" in c)
        total_assignments = sum(1 for c in courses if "assignment" in c)
        total_tasks = total_quizzes + total_assignments
        submitted_count = len(submissions)
        qualified_exemption_count = len(exemption_courses)
        total_exemption_courses = qualified_exemption_count + len(non_exemption_courses)
        
        print(f"\n📊 统计信息:")
        print(f"   总课程数: {len(courses)}")
        print(f"   有免修机制的课程: {total_exemption_courses}")
        print(f"   Ryan 达到免修要求: {qualified_exemption_count}")
        print(f"   Ryan 未达到免修要求: {len(non_exemption_courses)}")
        print(f"   总测验数: {total_quizzes}")
        print(f"   总作业数: {total_assignments}")
        print(f"   总任务数: {total_tasks}")
        print(f"   已提交数: {submitted_count}")
        print(f"   需完成数: {total_tasks - submitted_count}")
        print(f"\n📝 Groundtruth (Ryan 需要完成的任务):")
        print(f"   Quiz 数量: {len(quiz_data)}")
        print(f"   Assignment 数量: {len(assignment_data)}")
        print(f"   总计: {len(quiz_data) + len(assignment_data)}")
        
        if qualified_exemption_count > 0:
            print(f"\n✅ Ryan 达到免修要求的课程 (已添加到 memory):")
            for exemption in exemption_courses:
                print(f"   • {exemption['course_code']}: {exemption['course_name']}")
                print(f"     免修要求: {exemption['exemption_score']}, Ryan 成绩: {exemption['actual_score']} ✓")
        
        if len(non_exemption_courses) > 0:
            print(f"\n❌ Ryan 未达到免修要求的课程 (需要上课):")
            for course_info in non_exemption_courses:
                print(f"   • {course_info['course_code']}: {course_info['course_name']}")
                print(f"     免修要求: {course_info['exemption_score']}, Ryan 成绩: {course_info['actual_score']} ✗")
        
        return {
            "courses": len(courses),
            "total_exemption_courses": total_exemption_courses,
            "qualified_exemptions": qualified_exemption_count,
            "unqualified_exemptions": len(non_exemption_courses),
            "quizzes": total_quizzes,
            "assignments": total_assignments,
            "total_tasks": total_tasks,
            "submitted": submitted_count,
            "remaining": total_tasks - submitted_count,
            "groundtruth_quizzes": len(quiz_data),
            "groundtruth_assignments": len(assignment_data),
            "groundtruth_total": len(quiz_data) + len(assignment_data)
        }


def main():
    parser = argparse.ArgumentParser(description="Canvas List Test 任务配置生成器")
    
    # 基本参数
    parser.add_argument("--num-courses", type=int, default=10,
                       help="课程数量 (默认: 10)")
    parser.add_argument("--num-students", type=int, default=3,
                       help="学生数量 (默认: 3)")
    
    # 概率参数
    parser.add_argument("--quiz-prob", type=float, default=0.8,
                       help="每个课程有测验的概率 (0-1, 默认: 0.8)")
    parser.add_argument("--assignment-prob", type=float, default=0.7,
                       help="每个课程有作业的概率 (0-1, 默认: 0.7)")
    parser.add_argument("--submission-prob", type=float, default=0.3,
                       help="作业已提交的概率 (噪声, 0-1, 默认: 0.3)")
    parser.add_argument("--exemption-prob", type=float, default=0.1,
                       help="课程可免修的概率 (0-1, 默认: 0.1)")
    parser.add_argument("--exemption-meet-prob", type=float, default=0.6,
                       help="Ryan达到免修要求的概率 (0-1, 默认: 0.6)")
    parser.add_argument("--no-exam-prob", type=float, default=0.15,
                       help="课程无考试的概率 (0-1, 默认: 0.15)")
    
    # 难度参数
    parser.add_argument("--quiz-difficulty", choices=["easy", "medium", "hard"], default="medium",
                       help="测验难度 (默认: medium)")
    parser.add_argument("--assignment-difficulty", choices=["easy", "medium", "hard"], default="medium",
                       help="作业难度 (默认: medium)")
    
    # 其他参数
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (默认: 42)")
    parser.add_argument("--output-dir", type=str, default=".",
                       help="输出目录 (默认: 当前目录)")
    
    args = parser.parse_args()
    
    # 生成配置
    generator = TaskConfigGenerator(seed=args.seed)
    output_dir = Path(args.output_dir)
    
    stats = generator.save_config(
        output_dir=output_dir,
        num_courses=args.num_courses,
        num_students=args.num_students,
        quiz_probability=args.quiz_prob,
        assignment_probability=args.assignment_prob,
        submission_probability=args.submission_prob,
        quiz_difficulty=args.quiz_difficulty,
        assignment_difficulty=args.assignment_difficulty,
        exemption_probability=args.exemption_prob,
        exemption_meet_probability=args.exemption_meet_prob,
        no_exam_probability=args.no_exam_prob
    )
    
    print(f"\n🎉 配置生成完成！")
    print(f"\n💡 使用示例:")
    print(f"   python preprocess/main.py --agent_workspace /path/to/workspace")


if __name__ == "__main__":
    main()

