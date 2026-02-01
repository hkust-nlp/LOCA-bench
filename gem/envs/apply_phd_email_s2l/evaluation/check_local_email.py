#!/usr/bin/env python3
"""
本地邮件服务器附件检查脚本
用于检查本地邮箱中主题包含指定关键词的邮件附件，
下载ZIP附件，解压并与参考文件夹结构进行比较
"""

import os
import sys
import json
import zipfile
import argparse
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from gem.utils.filesystem import nfs_safe_rmtree
try:
    import PyPDF2
except ImportError:
    print("警告: PyPDF2 未安装，PDF内容检测功能将不可用")
    PyPDF2 = None

# 添加 mcp_convert 路径以导入 EmailDatabase
try:
    from mcp_convert.mcps.email.database_utils import EmailDatabase
except ImportError:
    EmailDatabase = None

try:
    from utils.app_specific.poste.local_email_manager import LocalEmailManager
except ImportError:
    LocalEmailManager = None


class LocalEmailAttachmentChecker:
    def __init__(self, email_db=None, receiver_email=None, groundtruth_workspace=None, config_file=None, temp_dir=None):
        """
        初始化本地邮件附件检查器

        Args:
            email_db: EmailDatabase 实例（新模式）
            receiver_email: 接收者邮箱地址（新模式）
            groundtruth_workspace: 参考文件夹路径
            config_file: 接收方邮箱配置文件路径（旧模式，兼容性）
            temp_dir: 临时目录路径（可选，如果不指定则使用代码目录下的temp_attachments）
        """
        # 新模式：直接使用数据库
        if email_db is not None and receiver_email is not None:
            self.use_database = True
            self.email_db = email_db
            self.receiver_email = receiver_email
            self.email_manager = None
            print(f"✅ 使用数据库模式，接收者: {receiver_email}")
        # 旧模式：使用 LocalEmailManager（向后兼容）
        elif config_file is not None:
            if LocalEmailManager is None:
                raise ImportError("LocalEmailManager 不可用，请使用数据库模式")
            self.use_database = False
            self.email_manager = LocalEmailManager(config_file, verbose=True)
            self.email_db = None
            self.receiver_email = None
            print(f"✅ 使用 LocalEmailManager 模式")
        else:
            raise ValueError("必须提供 (email_db, receiver_email) 或 config_file")

        self.groundtruth_workspace = groundtruth_workspace
        if temp_dir:
            self.temp_dir = temp_dir
        else:
            self.temp_dir = os.path.join(Path(__file__).parent, 'temp_attachments')
        self.valid_structures = {}  # 存储有效的文件结构选项
    
    def set_valid_structures(self, structures_dict: Dict):
        """设置有效的文件结构选项
        
        Args:
            structures_dict: {prof_email: {'name': str, 'structure_key': str, 'structure_name': str, 'structure_def': dict}}
        """
        self.valid_structures = structures_dict
        print(f"📝 设置了 {len(structures_dict)} 个有效的文件结构选项")
    
    def convert_structure_def_to_directory_structure(self, structure_def: Dict) -> Dict:
        """将FILE_STRUCTURES格式的结构定义转换为directory_structure格式
        
        Args:
            structure_def: {'folders': [...], 'files': {...}}
        
        Returns:
            directory_structure格式: {path: {'dirs': [...], 'files': [...]}}
        """
        directory_structure = {'': {'dirs': [], 'files': []}}
        
        # 定义占位符替换规则
        # Recommendation_Letter_[ProfessorName]-1.pdf -> Recommendation_Letter_Alex-1.pdf
        # Recommendation_Letter_[ProfessorName]-2.pdf -> Recommendation_Letter_Lily-2.pdf
        placeholder_replacements = {
            'Recommendation_Letter_[ProfessorName]-1.pdf': 'Recommendation_Letter_Alex-1.pdf',
            'Recommendation_Letter_[ProfessorName]-2.pdf': 'Recommendation_Letter_Lily-2.pdf'
        }
        
        # 添加顶层文件夹
        folders = structure_def.get('folders', [])
        directory_structure['']['dirs'] = folders
        
        # 添加每个文件夹的内容
        files_dict = structure_def.get('files', {})
        for folder in folders:
            directory_structure[folder] = {'dirs': [], 'files': []}
            file_list = files_dict.get(folder, [])
            
            for file_item in file_list:
                # 处理占位符替换
                if file_item in placeholder_replacements:
                    file_item = placeholder_replacements[file_item]
                
                if '/' in file_item:
                    # 子文件夹，如 "Awards_Certificates/All_Awards_Certificates.pdf"
                    subfolder, subfile = file_item.split('/', 1)
                    
                    # 对子文件也进行占位符替换
                    if subfile in placeholder_replacements:
                        subfile = placeholder_replacements[subfile]
                    
                    if subfolder not in directory_structure[folder]['dirs']:
                        directory_structure[folder]['dirs'].append(subfolder)
                    
                    # 添加子文件夹的内容
                    subfolder_path = f"{folder}/{subfolder}"
                    if subfolder_path not in directory_structure:
                        directory_structure[subfolder_path] = {'dirs': [], 'files': []}
                    directory_structure[subfolder_path]['files'].append(subfile)
                else:
                    # 普通文件
                    directory_structure[folder]['files'].append(file_item)
        
        return directory_structure
        
    def create_temp_dir(self) -> bool:
        """创建临时目录用于下载附件"""
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"✅ 创建临时目录: {self.temp_dir}")
            return True
        except Exception as e:
            print(f"❌ 创建临时目录失败: {e}")
            return False
    
    def search_emails_with_attachments(self, subject_keyword: str = "submit_material") -> List[Dict]:
        """搜索包含特定主题关键词且有附件的邮件"""
        try:
            print(f"🔍 在接收方邮箱中搜索主题包含 '{subject_keyword}' 且有附件的邮件...")
            
            if self.use_database:
                # 数据库模式：直接从数据库读取
                user_dir = self.email_db._get_user_data_dir(self.receiver_email)
                emails_file = os.path.join(user_dir, "emails.json")
                
                if not os.path.exists(emails_file):
                    print(f"⚠️ 邮件数据文件不存在: {emails_file}")
                    return []
                
                with open(emails_file, 'r', encoding='utf-8') as f:
                    emails_data = json.load(f)
                
                # 筛选包含主题关键词且有附件的邮件
                emails_with_attachments = []
                for email_id, email in emails_data.items():
                    subject = email.get('subject', '')
                    attachments = email.get('attachments', [])
                    
                    if subject_keyword.lower() in subject.lower() and len(attachments) > 0:
                        emails_with_attachments.append(email)
                
                if not emails_with_attachments:
                    print("⚠️ 没有找到匹配的邮件")
                    return []
                
                print(f"✅ 找到 {len(emails_with_attachments)} 封匹配的邮件")
                return emails_with_attachments
            else:
                # LocalEmailManager 模式（向后兼容）
                emails_with_attachments = self.email_manager.get_emails_with_attachments(
                    subject_keyword=subject_keyword
                )
                
                if not emails_with_attachments:
                    print("⚠️ 没有找到匹配的邮件")
                    return []
                
                print(f"✅ 找到 {len(emails_with_attachments)} 封匹配的邮件")
                return emails_with_attachments
            
        except Exception as e:
            print(f"❌ 邮件搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def download_zip_attachments(self, emails: List[Dict]) -> List[str]:
        """下载邮件中的ZIP附件"""
        downloaded_files = []
        
        for i, email_data in enumerate(emails):
            try:
                print(f"\n📧 处理第 {i+1} 封邮件...")
                
                subject = email_data.get('subject', 'Unknown Subject')
                print(f"   主题: {subject}")
                
                # 检查附件信息
                attachments = email_data.get('attachments', [])
                zip_attachments = [att for att in attachments if att['filename'].lower().endswith('.zip')]
                
                if not zip_attachments:
                    print(f"   ⚠️ 该邮件没有ZIP附件")
                    continue
                
                for attachment in zip_attachments:
                    filename = attachment['filename']
                    print(f"   发现ZIP附件: {filename}")
                    print(f"   附件内容: {attachment}")
                
                if self.use_database:
                    # 数据库模式：从附件数据中读取
                    for attachment in zip_attachments:
                        filename = attachment['filename']
                        attachment_path = attachment.get('path', '')
                        content_base64 = attachment.get('content', '')
                        
                        try:
                            # 方法1: 如果有完整路径，直接从路径复制文件
                            if attachment_path and os.path.exists(attachment_path):
                                print(f"   📁 从路径读取: {attachment_path}")
                                import shutil
                                dest_path = os.path.join(self.temp_dir, filename)
                                shutil.copy2(attachment_path, dest_path)
                                downloaded_files.append(dest_path)
                                print(f"   ✅ 复制完成: {filename}")
                            # 方法2: 从 base64 内容解码
                            elif content_base64:
                                print(f"   📦 从 base64 解码")
                                content_bytes = base64.b64decode(content_base64)
                                
                                # 保存到临时目录
                                file_path = os.path.join(self.temp_dir, filename)
                                with open(file_path, 'wb') as f:
                                    f.write(content_bytes)
                                
                                downloaded_files.append(file_path)
                                print(f"   ✅ 解码完成: {filename}")
                            else:
                                print(f"   ⚠️ 附件 {filename} 没有路径或内容数据")
                        except Exception as e:
                            print(f"   ❌ 处理附件 {filename} 失败: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    # LocalEmailManager 模式（向后兼容）
                    downloaded = self.email_manager.download_attachments_from_email(
                        email_data, self.temp_dir
                    )
                    
                    # 只保留ZIP文件
                    zip_files = [f for f in downloaded if f.lower().endswith('.zip')]
                    downloaded_files.extend(zip_files)
                    
                    for zip_file in zip_files:
                        print(f"   ✅ 下载完成: {os.path.basename(zip_file)}")
                
            except Exception as e:
                print(f"   ❌ 处理邮件失败: {e}")
                import traceback
                traceback.print_exc()
        
        return downloaded_files
    
    def extract_zip_files(self, zip_files: List[str]) -> bool:
        """解压ZIP文件"""
        if not zip_files:
            print("⚠️ 没有ZIP文件需要解压")
            return False
        
        success_count = 0
        for zip_file in zip_files:
            try:
                print(f"\n📦 解压文件: {os.path.basename(zip_file)}")
                
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    # 检查ZIP文件内容
                    file_list = zip_ref.namelist()
                    print(f"   ZIP文件包含 {len(file_list)} 个文件/文件夹")
                    
                    # 解压到临时目录
                    zip_ref.extractall(self.temp_dir)
                    print(f"   ✅ 解压完成")
                    success_count += 1
                    
            except Exception as e:
                print(f"   ❌ 解压失败: {e}")
        
        return success_count > 0
    
    def get_directory_structure(self, path: str) -> Dict:
        """获取目录结构"""
        structure = {}
        
        try:
            for root, dirs, files in os.walk(path):
                # 计算相对路径
                rel_path = os.path.relpath(root, path)
                if rel_path == '.':
                    rel_path = ''
                
                # 添加目录
                if rel_path:
                    structure[rel_path] = {'dirs': [], 'files': []}
                else:
                    structure[''] = {'dirs': [], 'files': []}
                
                # 添加子目录
                for dir_name in dirs:
                    if rel_path:
                        structure[rel_path]['dirs'].append(dir_name)
                    else:
                        structure['']['dirs'].append(dir_name)
                
                # 添加文件
                for file_name in files:
                    if rel_path:
                        structure[rel_path]['files'].append(file_name)
                    else:
                        structure['']['files'].append(file_name)
                        
        except Exception as e:
            print(f"❌ 获取目录结构失败: {e}")
        
        return structure
    
    def normalize_recommendation_letter_name(self, filename: str) -> str:
        """标准化推荐信文件名，使 Professor前缀可选

        例如:
        - Recommendation_Letter_ProfessorAlex-1.pdf -> Recommendation_Letter_Alex-1.pdf
        - Recommendation_Letter_ProfessorLily-2.pdf -> Recommendation_Letter_Lily-2.pdf
        - Recommendation_Letter_Alex-1.pdf -> Recommendation_Letter_Alex-1.pdf (保持不变)
        """
        import re
        # 匹配 Recommendation_Letter_Professor<Name>-<Number>.pdf 格式
        pattern = r'^Recommendation_Letter_Professor([A-Za-z]+)-(\d+)\.pdf$'
        match = re.match(pattern, filename)
        if match:
            name = match.group(1)
            number = match.group(2)
            return f'Recommendation_Letter_{name}-{number}.pdf'
        return filename

    def compare_structures(self, extracted_structure: Dict, reference_structure: Dict) -> Tuple[bool, List[str]]:
        """比较两个目录结构"""
        differences = []
        is_match = True

        print("\n🔍 比较文件结构...")

        # 检查所有目录
        all_dirs = set(extracted_structure.keys()) | set(reference_structure.keys())

        for dir_path in all_dirs:
            extracted = extracted_structure.get(dir_path, {'dirs': [], 'files': []})
            reference = reference_structure.get(dir_path, {'dirs': [], 'files': []})

            # 检查目录
            extracted_dirs = set(extracted['dirs'])
            reference_dirs = set(reference['dirs'])

            missing_dirs = reference_dirs - extracted_dirs
            extra_dirs = extracted_dirs - reference_dirs

            if missing_dirs:
                differences.append(f"目录 '{dir_path}' 缺少子目录: {list(missing_dirs)}")
                is_match = False

            if extra_dirs:
                differences.append(f"目录 '{dir_path}' 有多余子目录: {list(extra_dirs)}")
                is_match = False

            # 检查文件 - 使用标准化后的文件名进行比较
            extracted_files = set(extracted['files'])
            reference_files = set(reference['files'])

            # 标准化推荐信文件名进行比较
            extracted_files_normalized = {self.normalize_recommendation_letter_name(f) for f in extracted_files}
            reference_files_normalized = {self.normalize_recommendation_letter_name(f) for f in reference_files}

            missing_files = reference_files_normalized - extracted_files_normalized
            extra_files = extracted_files_normalized - reference_files_normalized

            if missing_files:
                differences.append(f"目录 '{dir_path}' 缺少文件: {list(missing_files)}")
                is_match = False

            if extra_files:
                differences.append(f"目录 '{dir_path}' 有多余文件: {list(extra_files)}")
                is_match = False

        return is_match, differences
    
    def print_structure(self, structure: Dict, title: str):
        """打印目录结构"""
        print(f"\n{title}:")
        print("=" * 50)
        
        for dir_path in sorted(structure.keys()):
            if dir_path:
                print(f"📁 {dir_path}/")
            else:
                print("📁 根目录/")
            
            data = structure[dir_path]
            
            for dir_name in sorted(data['dirs']):
                print(f"   📁 {dir_name}/")
            
            for file_name in sorted(data['files']):
                print(f"   📄 {file_name}")
    
    def find_extracted_materials_dir(self) -> Optional[str]:
        """寻找解压后的Application_Materials目录"""
        for root, dirs, files in os.walk(self.temp_dir):
            for dir_name in dirs:
                if dir_name.startswith('Application_Materials_'):
                    return os.path.join(root, dir_name)
        return None
    
    def check_pdf_content(self, pdf_path: str) -> Tuple[bool, List[str]]:
        """检查PDF内容是否符合要求"""
        if not PyPDF2:
            print("⚠️ PyPDF2 未安装，跳过PDF内容检测")
            return True, []
        
        if not os.path.exists(pdf_path):
            return False, [f"PDF文件不存在: {pdf_path}"]
        
        # 检查文件大小和基本信息
        file_size = os.path.getsize(pdf_path)
        print(f"📄 检查PDF文件: {pdf_path}")
        print(f"   文件大小: {file_size} bytes")
        
        if file_size == 0:
            return False, ["PDF文件大小为0，可能是损坏的文件"]
        
        errors = []
        expected_awards = [
            ("Outstanding Student Award 2021", 1),
            ("Research Competition First Place 2022", 2), 
            ("Academic Excellence Award 2023", 3)
        ]
        
        try:
            with open(pdf_path, 'rb') as file:
                # 尝试多个PDF读取方法
                try:
                    # 方法1: 使用strict=False (兼容性更好)
                    pdf_reader = PyPDF2.PdfReader(file, strict=False)
                    print("   ✅ 使用非严格模式读取PDF成功")
                except Exception as e1:
                    print(f"   ⚠️ 非严格模式读取失败: {e1}")
                    try:
                        # 方法2: 重新打开文件并使用默认模式
                        file.seek(0)
                        pdf_reader = PyPDF2.PdfReader(file)
                        print("   ✅ 使用默认模式读取PDF成功")
                    except Exception as e2:
                        error_msg = f"读取PDF文件失败: 非严格模式错误={e1}, 默认模式错误={e2}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
                        return False, errors
                
                total_pages = len(pdf_reader.pages)
                print(f"   总页数: {total_pages}")
                
                if total_pages != 3:
                    errors.append(f"PDF页数错误: 期望3页，实际{total_pages}页")
                    return False, errors
                
                for award_text, page_num in expected_awards:
                    try:
                        page = pdf_reader.pages[page_num - 1]  # 页面从0开始索引
                        text = page.extract_text()
                        
                        print(f"   第{page_num}页原始文本长度: {len(text)}")
                        if len(text) > 0:
                            print(f"   第{page_num}页前50字符: {text[:50]}")
                        
                        # 检查关键字是否存在 (移除空格进行比较)
                        text_clean = text.replace(' ', '').replace('\n', '').lower()
                        award_clean = award_text.replace(' ', '').lower()
                        
                        if award_clean in text_clean:
                            print(f"   ✅ 第{page_num}页包含: {award_text}")
                        else:
                            error_msg = f"第{page_num}页缺少预期内容: {award_text}"
                            errors.append(error_msg)
                            print(f"   ❌ {error_msg}")
                            print(f"   清理后的文本: {text_clean[:100]}")
                            print(f"   期望的内容: {award_clean}")
                            
                    except Exception as e:
                        error_msg = f"读取第{page_num}页失败: {e}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
                        
        except Exception as e:
            error_msg = f"打开PDF文件失败: {e}"
            errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False, errors
        
        return len(errors) == 0, errors
    
    def run(self, subject_keyword: str = "submit_material") -> bool:
        """运行完整的下载和比较流程"""
        print("🚀 开始检查接收方邮箱中的邮件附件和文件结构比较")
        print("=" * 60)
        
        # 1. 创建临时目录
        if not self.create_temp_dir():
            return False
        
        try:
            # 2. 搜索带附件的邮件
            emails = self.search_emails_with_attachments(subject_keyword)
            if not emails:
                print("❌ 没有找到匹配的邮件，流程终止")
                return False
            
            # 3. 下载ZIP附件
            zip_files = self.download_zip_attachments(emails)
            if not zip_files:
                print("❌ 没有找到ZIP附件，流程终止")
                return False
            
            # 4. 解压ZIP文件
            if not self.extract_zip_files(zip_files):
                print("❌ ZIP文件解压失败，流程终止")
                return False
            
            # 5. 寻找解压后的Application_Materials目录
            extracted_materials_dir = self.find_extracted_materials_dir()
            if not extracted_materials_dir:
                print("❌ 没有找到Application_Materials_*目录")
                return False
            
            print(f"✅ 找到解压后的材料目录: {os.path.basename(extracted_materials_dir)}")
            
            # 6. 获取文件结构
            print(f"\n📂 获取解压后的文件结构...")
            extracted_structure = self.get_directory_structure(extracted_materials_dir)
            
            # 获取参考文件夹结构
            # 如果设置了valid_structures且只有一个结构，使用structure_def生成参考结构
            # 否则使用groundtruth
            if self.valid_structures and len(self.valid_structures) == 1:
                prof_info = list(self.valid_structures.values())[0]
                if 'structure_def' in prof_info:
                    print(f"📂 根据结构定义生成参考结构: {prof_info['structure_name']}")
                    reference_structure = self.convert_structure_def_to_directory_structure(prof_info['structure_def'])
                else:
                    # 回退到groundtruth
                    print(f"📂 从groundtruth获取参考结构...")
                    groundtruth_materials_dir = self._find_groundtruth_materials_dir()
                    if not groundtruth_materials_dir:
                        return False
                    reference_structure = self.get_directory_structure(groundtruth_materials_dir)
            else:
                # 使用groundtruth
                print(f"📂 从groundtruth获取参考结构...")
                groundtruth_materials_dir = self._find_groundtruth_materials_dir()
                if not groundtruth_materials_dir:
                    return False
                reference_structure = self.get_directory_structure(groundtruth_materials_dir)
            
            # 7. 打印结构
            self.print_structure(extracted_structure, "解压后的文件结构")
            self.print_structure(reference_structure, "参考文件夹结构")
            
            # 8. 比较结构
            # 如果设置了 valid_structures，根据数量决定验证模式
            if self.valid_structures:
                if len(self.valid_structures) == 1:
                    # 只有一个有效结构时，进行严格验证
                    print(f"\n🔍 严格验证模式：检查是否符合指定的文件结构...")
                    is_match, differences = self.compare_structures(extracted_structure, reference_structure)
                    prof_info = list(self.valid_structures.values())[0]
                    matched_structure = prof_info['structure_name']
                else:
                    # 多个有效结构时，采用宽松验证（符合任一结构即可）
                    print(f"\n🔍 宽松验证模式：检查是否符合 {len(self.valid_structures)} 个有效结构之一...")
                    is_match = True  # 宽松验证：只要文件合理即可
                    differences = []
                    matched_structure = "任意有效结构"
                    print("✅ 只要提交了合理的文件即可")
            else:
                # 原始严格验证模式
                is_match, differences = self.compare_structures(extracted_structure, reference_structure)
                matched_structure = "标准结构"
            
            # 9. 检查All_Awards_Certificates.pdf的内容（如果存在）
            pdf_content_valid = True
            pdf_errors = []
            
            # 在各种可能的位置查找 Awards PDF
            awards_pdf_locations = [
                os.path.join(extracted_materials_dir, '02_Academic_Materials', 'Awards_Certificates', 'All_Awards_Certificates.pdf'),
                os.path.join(extracted_materials_dir, '01_Academic_Materials', 'Awards_Certificates', 'All_Awards_Certificates.pdf'),
                os.path.join(extracted_materials_dir, '03_Academic_Materials', 'Awards_Certificates', 'All_Awards_Certificates.pdf'),
                os.path.join(extracted_materials_dir, '04_Academic_Materials', 'Awards_Certificates', 'All_Awards_Certificates.pdf'),
            ]
            
            awards_pdf_path = None
            for path in awards_pdf_locations:
                if os.path.exists(path):
                    awards_pdf_path = path
                    break
            
            if awards_pdf_path:
                print(f"\n🔍 检查All_Awards_Certificates.pdf的内容...")
                pdf_content_valid, pdf_errors = self.check_pdf_content(awards_pdf_path)
            else:
                # PDF 不存在也可以接受（某些变体不要求 Awards）
                if self.valid_structures:
                    print("ℹ️  All_Awards_Certificates.pdf不存在（某些变体可能不需要）")
                    pdf_content_valid = True  # 宽松模式
                else:
                    pdf_content_valid = False
                    pdf_errors = ["All_Awards_Certificates.pdf文件不存在"]
                    print("❌ All_Awards_Certificates.pdf文件不存在")
            
            # 10. 输出结果
            print("\n" + "=" * 60)
            print("📊 比较结果")
            print("=" * 60)
            
            # 文件结构检查结果
            print("\n📁 文件结构检查:")
            if is_match:
                if self.valid_structures:
                    print(f"✅ 文件结构符合要求！（匹配: {matched_structure}）")
                    print(f"   可用的结构选项:")
                    for prof_email, info in self.valid_structures.items():
                        print(f"   • {info['name']}: {info['structure_name']}")
                else:
                    print(f"✅ 文件结构完全匹配！（{matched_structure}）")
            else:
                print("❌ 文件结构不匹配")
                print("差异详情:")
                for diff in differences:
                    print(f"   • {diff}")
            
            # PDF内容检查结果
            print("\n📄 PDF内容检查:")
            if pdf_content_valid:
                print("✅ All_Awards_Certificates.pdf内容符合要求！")
            else:
                print("❌ All_Awards_Certificates.pdf内容不符合要求")
                print("错误详情:")
                for error in pdf_errors:
                    print(f"   • {error}")
            
            # 综合结果
            overall_success = is_match and pdf_content_valid
            print(f"\n{'='*60}")
            print("🎯 综合结果:")
            if overall_success:
                print("✅ 所有检查项目均通过！")
            else:
                print("❌ 检查未完全通过，请查看上述详情")
            
            return overall_success
            
        finally:
            # 清理临时目录
            try:
                import shutil
                nfs_safe_rmtree(self.temp_dir)
                print(f"🧹 清理临时目录: {self.temp_dir}")
            except Exception as e:
                print(f"⚠️ 清理临时目录失败: {e}")


def main():
    parser = argparse.ArgumentParser(description='本地邮件附件检查和文件结构比较')
    parser.add_argument('--config_file', '-c',
                       default='files/receiver_config.json',
                       help='接收方邮箱配置文件路径')
    parser.add_argument('--subject', '-s',
                       default='submit_material',
                       help='邮件主题关键词')
    parser.add_argument('--agent_workspace', '-w',
                       default='test_workspace',
                       help='agent工作空间')
    parser.add_argument('--groundtruth_workspace', '-r',
                       help='参考文件夹', required=True)
    args = parser.parse_args()
    
    print(f"📧 使用接收方邮箱配置文件: {args.config_file}")
    
    # 创建检查器并运行
    checker = LocalEmailAttachmentChecker(args.config_file, args.agent_workspace, args.groundtruth_workspace)
    success = checker.run(args.subject)
    
    if success:
        print("\n🎉 流程执行成功！")
    else:
        print("\n💥 流程执行失败！")
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())