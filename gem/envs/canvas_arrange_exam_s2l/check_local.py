from argparse import ArgumentParser
import asyncio
import re
from datetime import datetime, timedelta

import subprocess
import os
import json
import pandas as pd

from helper import normalize_str

def check_time_order(df_agent):
    """
    检查考试时间顺序是否正确（由近到远排列，TBD在最后）
    
    Returns:
        (is_valid, error_message)
    """
    if len(df_agent) == 0:
        return True, None
    
    try:
        prev_datetime = None
        tbd_encountered = False
        
        for idx, row in df_agent.iterrows():
            date_str = str(row.get('Final Date (MM/DD/YYYY)', '')).strip()
            time_str = str(row.get('Start Time (HH:MM)', '')).strip()
            course_code = row.get('Course Code', 'Unknown')
            
            # 检查是否是TBD
            if date_str.upper() == 'TBD' or time_str.upper() == 'TBD' or date_str == 'nan' or time_str == 'nan':
                tbd_encountered = True
                continue
            
            # 如果之前遇到过TBD，现在又遇到非TBD的，说明顺序错误
            if tbd_encountered:
                return False, f"时间顺序错误: TBD 考试必须在最后，但在 {course_code} 之前发现了TBD考试"
            
            # 解析日期和时间
            try:
                # 解析 MM/DD/YYYY 格式
                date_parts = date_str.split('/')
                if len(date_parts) != 3:
                    return False, f"日期格式错误: {course_code} 的日期 '{date_str}' 不是 MM/DD/YYYY 格式"
                
                month, day, year = date_parts
                
                # 解析 HH:MM 格式
                time_parts = time_str.split(':')
                if len(time_parts) != 2:
                    return False, f"时间格式错误: {course_code} 的时间 '{time_str}' 不是 HH:MM 格式"
                
                hour, minute = time_parts
                
                # 创建datetime对象
                current_datetime = datetime(int(year), int(month), int(day), int(hour), int(minute))
                
                # 检查顺序（应该是升序，即由近到远）
                if prev_datetime is not None:
                    if current_datetime < prev_datetime:
                        return False, f"时间顺序错误: {course_code} 的考试时间 ({date_str} {time_str}) 应该在前一个考试之后"
                
                prev_datetime = current_datetime
                
            except (ValueError, IndexError) as e:
                return False, f"日期/时间解析错误: {course_code} - {str(e)}"
        
        return True, None
        
    except Exception as e:
        return False, f"检查时间顺序时出错: {str(e)}"

def check_local(agent_workspace: str, groundtruth_workspace: str):
    """
    比较两个CSV文件内容，检查是否完全一致。
    内容完全一致返回 (True, None)，否则返回 (False, '文件内容不一致')。
    """
    agent_needed_file = os.path.join(agent_workspace,"exam_schedule.xlsx")
    groundtruth_needed_file = os.path.join(groundtruth_workspace,"exam_schedule.xlsx")

    # 检查文件是否存在
    if not os.path.exists(agent_needed_file):
        return False, f'代理工作空间文件不存在: {agent_needed_file}'
    
    if not os.path.exists(groundtruth_needed_file):
        return False, f'基准工作空间文件不存在: {groundtruth_needed_file}'

    try:
        # 读取两个xlsx文件
        print("agent_needed_file: ", agent_needed_file)
        df_agent = pd.read_excel(agent_needed_file, engine='openpyxl')
        df_ground = pd.read_excel(groundtruth_needed_file, engine='openpyxl')
        
        # 首先检查时间顺序
        print("\n⏰ 检查时间顺序...")
        time_order_valid, time_order_error = check_time_order(df_agent)
        if not time_order_valid:
            print(f"❌ 时间顺序检查失败: {time_order_error}")
            return False, f"时间顺序错误: {time_order_error}"
        else:
            print("✅ 时间顺序正确（由近到远排列，TBD在最后）")
        
        # 定义需要比较的关键列，就是所有
        key_columns = ['Course Code', 'Course Name', 'Proctor Name', 'Proctor Email', 'Open-book/Closed-book', 'Final Date (MM/DD/YYYY)', 'Start Time (HH:MM)', 'Duration (minutes)', 'Location', 'Information Source(Announcement/Email/Message)', 'Course Credit']
        
        print(f"Agent output rows: {len(df_agent)}")
        print(f"Ground truth rows: {len(df_ground)}")
        
        # 数值比较函数
        def compare_numeric_values(agent_val, ground_val):
            """
            比较数值型字段，如Course Credit
            处理'4.0'和'4'这种数值相等但字符串不同的情况
            """
            try:
                # 尝试转换为浮点数进行比较
                agent_num = float(str(agent_val).strip())
                ground_num = float(str(ground_val).strip())
                return agent_num == ground_num
            except (ValueError, TypeError):
                # 如果无法转换为数字，则按字符串比较
                return str(agent_val).strip() == str(ground_val).strip()
        
        # 字符串容忍性比较函数
        def compare_strings_tolerant(agent_val, ground_val, field_name):
            """
            更宽松的字符串比较，容忍以下情况：
            1. ground truth是agent值的子串（如 'emily' 匹配 'emily davis'）
            2. Information Source的别名（如 'announcement' 匹配 'canvas announcement'）
            """
            agent_str = str(agent_val).strip().lower()
            ground_str = str(ground_val).strip().lower()
            
            # 完全匹配
            if agent_str == ground_str:
                return True
            
            # 对于Proctor Name字段，检查ground truth是否是agent值中的一部分
            # 例如：'emily' 应该匹配 'emily davis'
            if field_name == 'Proctor Name':
                # 分割成单词进行比较
                agent_words = set(agent_str.split())
                ground_words = set(ground_str.split())
                # 如果ground truth的所有单词都在agent中出现，认为匹配
                if ground_words.issubset(agent_words):
                    return True
            
            # 对于Information Source字段，处理别名
            if field_name == 'Information Source(Announcement/Email/Message)':
                # 标准化source类型
                def normalize_source(s):
                    s = s.lower().strip()
                    # 移除 'canvas' 前缀
                    s = s.replace('canvas ', '').replace('canvas', '')
                    s = s.strip()
                    return s
                
                agent_source = normalize_source(agent_str)
                ground_source = normalize_source(ground_str)
                
                if agent_source == ground_source:
                    return True
            
            # 检查ground truth是否是agent的子串
            if ground_str in agent_str:
                return True
            
            # 检查agent是否是ground truth的子串（反向检查）
            if agent_str in ground_str:
                return True
            
            return False

        # 首先检查行数是否一致
        if len(df_agent) != len(df_ground):
            error_msg = f"行数不一致: Agent有{len(df_agent)}门课程, Ground truth有{len(df_ground)}门课程"
            print(f"❌ {error_msg}")
            return False, error_msg
        
        # 按课程代码进行匹配和比较
        matches = 0
        total_courses = len(df_ground)  # 使用groundtruth的行数作为总数
        differences = []
        missing_in_agent = []
        
        # 首先检查groundtruth中的每门课程是否都在agent中存在
        for idx_ground, row_ground in df_ground.iterrows():
            course_code_ground = row_ground['Course Code']
            matching_rows_agent = df_agent[df_agent['Course Code'] == course_code_ground]
            
            if matching_rows_agent.empty:
                missing_in_agent.append(course_code_ground)
                differences.append(f"❌ 课程 {course_code_ground} 在agent输出中未找到（必需课程缺失）")
        
        # 如果有groundtruth中的课程在agent中缺失，直接返回失败
        if missing_in_agent:
            error_msg = f"Agent输出缺失 {len(missing_in_agent)} 门必需课程: {', '.join(missing_in_agent)}"
            print(f"❌ {error_msg}")
            for diff in differences:
                print(f"  - {diff}")
            return False, error_msg
        
        # 遍历groundtruth中的每门课程，检查agent中的对应课程是否完全匹配
        for idx_ground, row_ground in df_ground.iterrows():
            course_code_ground = row_ground['Course Code']
            
            # 在agent输出中查找对应的课程
            matching_rows_agent = df_agent[df_agent['Course Code'] == course_code_ground]
            
            # 取第一个匹配的行
            row_agent = matching_rows_agent.iloc[0]
            
            # 比较关键列
            course_matches = True
            course_diffs = []

            for col in key_columns:
                val_agent = row_agent.get(col, 'N/A')
                val_ground = row_ground.get(col, 'N/A')
                
                # 标准化值进行比较
                val_agent_norm = normalize_str(str(val_agent)) if pd.notna(val_agent) else 'TBD'
                val_agent_norm = val_agent_norm.replace('professor','') # for professor smith
                val_ground_norm = normalize_str(str(val_ground)) if pd.notna(val_ground) else 'TBD'
                
                if col == 'Course Credit':
                    # 对Course Credit使用数值比较
                    is_match = compare_numeric_values(val_agent_norm, val_ground_norm)
                    if not is_match:
                        course_matches = False
                        course_diffs.append(f"{col}: Agent='{val_agent_norm}' vs Ground='{val_ground_norm}'")
                else:
                    # 其他列使用宽容的字符串比较
                    is_match = compare_strings_tolerant(val_agent_norm, val_ground_norm, col)
                    if not is_match:
                        course_matches = False
                        course_diffs.append(f"{col}: Agent='{val_agent_norm}' vs Ground='{val_ground_norm}'")
            
            if course_matches:
                matches += 1
                print(f"✅ {course_code_ground}: 完全匹配")
            else:
                differences.append(f"❌ {course_code_ground}: {'; '.join(course_diffs)}")
        
        # 检查agent中是否有groundtruth中没有的额外课程
        extra_courses = []
        for idx_agent, row_agent in df_agent.iterrows():
            course_code_agent = row_agent['Course Code']
            if not any(df_ground['Course Code'] == course_code_agent):
                extra_courses.append(course_code_agent)
                differences.append(f"⚠️  课程 {course_code_agent} 在ground truth中未找到（额外课程）")
        
        # 计算匹配率（基于groundtruth的课程数量）
        if total_courses > 0:
            match_rate = matches / total_courses
        else:
            match_rate = 0
        
        print(f"\n📊 比较结果:")
        print(f"Ground truth课程总数: {total_courses}")
        print(f"Agent输出课程总数: {len(df_agent)}")
        print(f"完全匹配的课程: {matches}/{total_courses} ({match_rate:.1%})")
        
        if extra_courses:
            print(f"⚠️  Agent输出中有 {len(extra_courses)} 门额外课程（不在ground truth中）")
        
        if differences:
            print(f"\n❌ 发现 {len(differences)} 个差异:")
            for diff in differences[:10]:  # 只显示前10个差异
                print(f"  - {diff}")
            if len(differences) > 10:
                print(f"  ... 还有 {len(differences) - 10} 个差异")
        
        # 必须满足：1) 匹配率100%  2) 没有额外课程
        if match_rate >= 1.0 and len(extra_courses) == 0:
            print("✅ 文件内容完全一致（所有ground truth课程都匹配，且无额外课程）")
            return True, None
        else:
            if match_rate < 1.0:
                error_msg = f'匹配率不足: {match_rate:.1%}, 差异数量: {len(differences)}'
            else:
                error_msg = f'Agent输出包含 {len(extra_courses)} 门额外课程'
            print(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        return False, f'读取xlsx文件时出错: {str(e)}'



