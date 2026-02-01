"""
远程检查模块 - 检查WooCommerce和邮件发送 (支持本地数据库)
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
task_dir = os.path.dirname(current_dir)
sys.path.insert(0, task_dir)

REMOTE_API_AVAILABLE = False

def check_remote(agent_workspace: str, groundtruth_workspace: str, res_log: Dict, 
                 woocommerce_db=None, email_db=None, groundtruth_metadata=None) -> Tuple[bool, str]:
    """
    检查服务状态 - WooCommerce Product Categories、邮件发送
    支持本地数据库和远程 API 两种模式
    
    Args:
        agent_workspace: Agent工作空间路径
        groundtruth_workspace: Ground truth工作空间路径
        res_log: 执行日志
        woocommerce_db: WooCommerce本地数据库实例 (可选)
        email_db: Email本地数据库实例 (可选)
        groundtruth_metadata: 生成的元数据 (可选)
        
    Returns:
        (检查是否通过, 错误信息)
    """
    
    # 判断使用哪种模式
    use_local_db = (woocommerce_db is not None and email_db is not None)
    
    if use_local_db:
        print("🔍 使用本地数据库模式检查...")
        return check_with_local_db(agent_workspace, groundtruth_workspace, 
                                   woocommerce_db, email_db, groundtruth_metadata)
    elif REMOTE_API_AVAILABLE:
        print("🌐 使用远程API模式检查...")
        return check_with_remote_api(agent_workspace, groundtruth_workspace, res_log)
    else:
        return False, "Neither local database nor remote API is available"


def check_with_local_db(agent_workspace: str, groundtruth_workspace: str,
                        woocommerce_db, email_db, groundtruth_metadata=None) -> Tuple[bool, str]:
    """使用本地数据库进行检查"""
    
    try:
        # 显示元数据信息（如果有）
        if groundtruth_metadata:
            print("\n📊 Groundtruth 元数据信息:")
            gen_params = groundtruth_metadata.get('generation_params', {})
            print(f"   预期低销量商品: {gen_params.get('num_low_selling', 'N/A')} 个")
            print(f"   预期正常商品: {gen_params.get('num_normal_selling', 'N/A')} 个")
            print(f"   订阅者数量: {gen_params.get('num_subscribers', 'N/A')} 个")
            
            # 显示预期的低销量商品名称（前5个）
            expected_low_selling = groundtruth_metadata.get('low_selling_products', [])
            if expected_low_selling:
                print(f"\n   预期低销量商品列表（共{len(expected_low_selling)}个）:")
                for idx, name in enumerate(expected_low_selling[:5], 1):
                    print(f"      {idx}. {name}")
                if len(expected_low_selling) > 5:
                    print(f"      ... 还有 {len(expected_low_selling) - 5} 个")
        
        # 检查1: Product Categories和移动
        print("\n  🏷️ 检查 Product Categories和移动...")
        category_pass, category_msg = check_product_categories_local(woocommerce_db, groundtruth_metadata)
        if not category_pass:
            return False, f"Product Categories检查失败: {category_msg}"
        else:
            print(f"    ✅ {category_msg}")
        
        # 博客文章检查跳过（WooCommerce不管理WordPress博客）
        blog_msg = "博客文章发布检查跳过（WooCommerce不管理WordPress博客）"
        print(f"\n    ℹ️  {blog_msg}")
        
        # 检查2: 邮件发送
        print("  📧 检查邮件发送...")
        email_pass, email_msg = check_email_sending_local(agent_workspace, woocommerce_db, email_db)
        if not email_pass:
            return False, f"邮件发送检查失败: {email_msg}"
        else:
            print(f"    ✅ {email_msg}")
        
        print("✅ 本地数据库检查全部通过")
        return True, f"检查通过: {category_msg}; {email_msg}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"本地数据库检查过程中出错: {str(e)}"


def check_with_remote_api(agent_workspace: str, groundtruth_workspace: str, 
                          res_log: Dict) -> Tuple[bool, str]:
    """使用远程API进行检查（向后兼容）"""
    
    try:
        # 初始化WooCommerce客户端
        site_url = all_token_key_session.woocommerce_site_url
        consumer_key = all_token_key_session.woocommerce_api_key
        consumer_secret = all_token_key_session.woocommerce_api_secret
        
        if not all([site_url, consumer_key, consumer_secret]):
            return False, "WooCommerce API配置不完整"
        
        wc_client = WooCommerceClient(site_url, consumer_key, consumer_secret)
        
        # 检查1: Product Categories和移动
        print("  🏷️ 检查 Product Categories和移动...")
        category_pass, category_msg = check_product_categories_remote(wc_client)
        if not category_pass:
            return False, f"Product Categories检查失败: {category_msg}"
        else:
            print(f"    ✅ {category_msg}")
        
        # 博客文章检查跳过
        blog_msg = "博客文章发布检查跳过（WooCommerce不管理WordPress博客）"
        print(f"\n    ℹ️  {blog_msg}")
        
        # 检查2: 邮件发送
        print("  📧 检查邮件发送...")
        email_pass, email_msg = check_email_sending_remote(agent_workspace, wc_client)
        if not email_pass:
            return False, f"邮件发送检查失败: {email_msg}"
        else:
            print(f"    ✅ {email_msg}")
        
        print("✅ 远程API检查全部通过")
        return True, f"检查通过: {category_msg}; {email_msg}"
        
    except Exception as e:
        return False, f"远程API检查过程中出错: {str(e)}"


def get_low_selling_products_local(woocommerce_db) -> Tuple[List[Dict], List[Dict]]:
    """从本地数据库获取低销量商品"""
    
    all_products = list(woocommerce_db.products.values())
    current_date = datetime.now()
    low_selling_products = []
    other_products = []
    
    for product in all_products:
        # 计算在库天数
        date_created_str = product.get('date_created', '')
        if not date_created_str:
            continue
        
        try:
            date_created = datetime.fromisoformat(date_created_str.replace('Z', '+00:00'))
            days_in_stock = (current_date - date_created.replace(tzinfo=None)).days
        except:
            continue
        
        # 获取30天销量（从meta_data或直接字段）
        sales_30_days = 0
        meta_data = product.get('meta_data', [])
        for meta in meta_data:
            if meta.get('key') in ['sales_last_30_days', '_sales_last_30_days']:
                try:
                    sales_30_days = int(meta.get('value', 0))
                    break
                except (ValueError, TypeError):
                    continue
        
        # 如果meta_data中没有，检查是否有直接字段
        if sales_30_days == 0 and 'sales_last_30_days' in product:
            try:
                sales_30_days = int(product.get('sales_last_30_days', 0))
            except:
                pass
        
        # 获取价格信息
        product_name = product.get('name', '')
        regular_price = float(product.get('regular_price', 0)) if product.get('regular_price') else 0.0
        sale_price = float(product.get('sale_price', 0)) if product.get('sale_price') else regular_price
        
        # 计算折扣率（折扣百分比）
        # discount_rate = (regular_price - sale_price) / regular_price
        # 例如：原价$100，现价$80，折扣率=0.2 (20% off)
        discount_rate = (regular_price - sale_price) / regular_price if regular_price > 0 else 0.0
        
        item = {
            'product': product,
            'name': product_name,
            'regular_price': regular_price,
            'sale_price': sale_price,
            'days_in_stock': days_in_stock,
            'sales_30_days': sales_30_days,
            'discount_rate': discount_rate
        }
        
        # 判断是否为低销量商品（在库>90天，30天销量<10）
        if days_in_stock > 90 and sales_30_days < 10:
            low_selling_products.append(item)
        else:
            other_products.append(item)
    
    # 排序：1.在库时间从长到短（入库时间从早到晚） 2.折扣率从小到大
    # discount_rate = (regular_price - sale_price) / regular_price
    # 值越大折扣越大，从小到大排序 = 折扣小的排前面
    low_selling_products.sort(key=lambda x: (-x['days_in_stock'], x['discount_rate']))
    
    # 调试信息：显示排序后的商品列表
    if low_selling_products:
        print(f"\n📋 低销量商品排序结果 (共 {len(low_selling_products)} 个):")
        print("=" * 80)
        for idx, item in enumerate(low_selling_products, 1):
            print(f"{idx}. {item['name']}")
            print(f"   在库天数: {item['days_in_stock']}天 (创建日期越早天数越多)")
            print(f"   30天销量: {item['sales_30_days']}")
            print(f"   原价: ${item['regular_price']:.2f}, 现价: ${item['sale_price']:.2f}")
            discount_pct = item['discount_rate'] * 100
            print(f"   折扣率: {item['discount_rate']:.3f} ({discount_pct:.1f}% off)")
        print("=" * 80)
    
    return low_selling_products, other_products


def check_product_categories_local(woocommerce_db, groundtruth_metadata=None) -> Tuple[bool, str]:
    """检查Product Categories和低销量商品移动（本地数据库版本）"""
    
    try:
        # 获取低销量商品
        low_selling_products, other_products = get_low_selling_products_local(woocommerce_db)
        
        # 如果有 groundtruth metadata，进行对比
        if groundtruth_metadata:
            expected_low_selling_names = set(groundtruth_metadata.get('low_selling_products', []))
            actual_low_selling_names = set(item['name'] for item in low_selling_products)
            
            print(f"\n🔍 对比预期与实际的低销量商品:")
            print(f"   预期: {len(expected_low_selling_names)} 个")
            print(f"   实际识别: {len(actual_low_selling_names)} 个")
            
            # 检查是否一致
            if expected_low_selling_names != actual_low_selling_names:
                missing = expected_low_selling_names - actual_low_selling_names
                extra = actual_low_selling_names - expected_low_selling_names
                
                if missing:
                    print(f"   ⚠️  缺失的低销量商品: {missing}")
                if extra:
                    print(f"   ⚠️  额外识别的商品: {extra}")
                
                print(f"   ℹ️  注意：可能是商品数据在任务执行中发生了变化")
            else:
                print(f"   ✅ 识别结果与预期完全一致")
        
        # 获取Product Categories
        categories = list(woocommerce_db.categories.values())
        
        # 查找Outlet分类
        outlet_category = None
        outlet_names = ["Outlet/Clearance", "Outlet", "Clearance"]
        
        for category in categories:
            if category.get('name', '') in outlet_names:
                outlet_category = category
                break
        
        if not outlet_category:
            return False, "未找到Outlet/Clearance分类"
        
        print(f"🔍 找到Outlet分类: {outlet_category.get('name')}")
        outlet_category_id = outlet_category.get('id')
        
        # 检查低销量商品情况
        total_low_selling = len(low_selling_products)
        low_selling_in_outlet = 0
        low_selling_not_in_outlet = []
        normal_selling_in_outlet = []
        
        # 检查每个低销量商品是否在Outlet分类中
        for item in low_selling_products:
            product = item['product']
            product_name = item['name']
            
            product_categories = product.get('categories', [])
            is_in_outlet = any(cat.get('id') == outlet_category_id for cat in product_categories)
            
            if is_in_outlet:
                low_selling_in_outlet += 1
            else:
                low_selling_not_in_outlet.append(product_name)
        
        # 检查是否有非低销量商品被错误地放入Outlet分类
        all_products = list(woocommerce_db.products.values())
        for product in all_products:
            product_categories = product.get('categories', [])
            is_in_outlet = any(cat.get('id') == outlet_category_id for cat in product_categories)
            
            if is_in_outlet:
                # 检查是否是低销量商品
                is_low_selling = any(item['name'] == product.get('name') for item in low_selling_products)
                
                if not is_low_selling:
                    # 计算该商品的实际数据
                    date_created_str = product.get('date_created', '')
                    if date_created_str:
                        try:
                            date_created = datetime.fromisoformat(date_created_str.replace('Z', '+00:00'))
                            days_in_stock = (datetime.now() - date_created.replace(tzinfo=None)).days
                        except:
                            days_in_stock = 0
                    else:
                        days_in_stock = 0
                    
                    sales_30_days = 0
                    meta_data = product.get('meta_data', [])
                    for meta in meta_data:
                        if meta.get('key') in ['sales_last_30_days', '_sales_last_30_days']:
                            try:
                                sales_30_days = int(meta.get('value', 0))
                                break
                            except:
                                pass
                    
                    normal_selling_in_outlet.append({
                        'name': product.get('name', 'Unknown'),
                        'days_in_stock': days_in_stock,
                        'sales_30_days': sales_30_days
                    })
        
        # 检查结果
        if total_low_selling == 0:
            return False, "没有找到符合条件的低销量商品（在库>90天，30天销量<10）"
        
        if normal_selling_in_outlet:
            error_details = []
            for item in normal_selling_in_outlet:
                error_details.append(f"{item['name']} (在库{item['days_in_stock']}天，30天销量{item['sales_30_days']})")
            return False, f"发现 {len(normal_selling_in_outlet)} 个非低销量商品被错误地放入Outlet分类: {'; '.join(error_details)}"
        
        if low_selling_in_outlet == 0:
            return False, f"没有低销量商品被移动到Outlet分类。发现 {total_low_selling} 个低销量商品，但都没有在Outlet分类中"
        
        if low_selling_in_outlet < total_low_selling:
            missing_count = total_low_selling - low_selling_in_outlet
            return False, f"只有部分低销量商品被移动到Outlet分类。总共 {total_low_selling} 个低销量商品，仅 {low_selling_in_outlet} 个在Outlet分类中，缺少 {missing_count} 个。未移动的商品: {', '.join(low_selling_not_in_outlet)}"
        
        return True, f"所有 {total_low_selling} 个低销量商品都已正确移动到Outlet分类，且Outlet分类中没有非低销量商品"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Product Categories检查出错: {str(e)}"


def get_attachment_content(attachment: Dict, agent_workspace: str = None, 
                          email_db=None, user_email: str = None, email_id: str = None) -> Optional[str]:
    """获取附件内容（支持多种来源）
    
    Args:
        attachment: 附件字典，可能包含 'content', 'path', 'filename' 等字段
        agent_workspace: Agent工作空间路径（用于查找附件文件）
        email_db: 邮件数据库实例
        user_email: 用户邮箱地址
        email_id: 邮件ID
        
    Returns:
        附件内容字符串，如果获取失败则返回None
    """
    try:
        # 方法1: 直接从content字段读取
        content = attachment.get('content', '')
        if content:
            print(f"   📦 从content字段读取附件内容")
            return content
        
        # 方法2: 从path字段读取文件
        path = attachment.get('path', '')
        if path and os.path.exists(path):
            print(f"   📁 从路径读取附件: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # 方法3: 检查是否有base64编码的内容
        for key in ['data', 'base64', 'content_base64']:
            if key in attachment:
                print(f"   🔐 尝试从{key}字段解码")
                try:
                    import base64
                    decoded = base64.b64decode(attachment[key])
                    return decoded.decode('utf-8')
                except Exception as e:
                    print(f"   ⚠️  base64解码失败: {e}")
        
        # 方法4: 根据filename在agent workspace中查找
        filename = attachment.get('filename', '')
        if filename and agent_workspace:
            # 尝试在agent workspace根目录查找
            possible_paths = [
                os.path.join(agent_workspace, filename),
                os.path.join(agent_workspace, 'attachments', filename),
            ]
            
            # 如果有邮件数据库和用户信息，也尝试在用户附件目录查找
            if email_db and user_email:
                user_dir = email_db._get_user_data_dir(user_email)
                possible_paths.extend([
                    os.path.join(user_dir, 'attachments', filename),
                    os.path.join(user_dir, 'attachments', email_id or '', filename) if email_id else None,
                ])
            
            # 尝试所有可能的路径
            for possible_path in possible_paths:
                if possible_path and os.path.exists(possible_path):
                    print(f"   📁 从agent workspace读取附件: {possible_path}")
                    with open(possible_path, 'r', encoding='utf-8') as f:
                        return f.read()
                elif possible_path:
                    print(f"   ⚠️  路径不存在: {possible_path}")
        
        print(f"   ⚠️  无法获取附件内容")
        print(f"   附件字段: {list(attachment.keys())}")
        if agent_workspace:
            print(f"   已尝试在agent workspace中查找: {filename}")
        return None
        
    except Exception as e:
        print(f"   ❌ 获取附件内容失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_csv_attachment(attachment_content: str) -> List[Dict]:
    """解析CSV附件内容
    
    Args:
        attachment_content: CSV文件内容字符串
        
    Returns:
        List[Dict]: 商品列表，每个商品包含name, original_price, promotional_price, discount_ratio
    """
    import csv
    import io
    
    if not attachment_content:
        print("⚠️  CSV内容为空")
        return []
    
    lines = attachment_content.strip().split('\n')
    if not lines:
        print("⚠️  CSV内容没有行")
        return []
    
    try:
        # 使用csv.DictReader解析
        reader = csv.DictReader(io.StringIO(attachment_content))
        products = []
        
        for row_num, row in enumerate(reader, 1):
            if not row.get('Product Name'):  # 跳过空行
                continue
            
            try:
                # 处理价格：可能包含美元符号和逗号（如 "$1,234.56"）
                def parse_price(price_str):
                    if not price_str:
                        return 0.0
                    # 去掉美元符号、逗号和空格
                    price_str = str(price_str).strip().replace('$', '').replace(',', '')
                    return float(price_str)
                
                # 处理折扣率：可能包含百分号（如 "44.77%"）
                discount_ratio_str = row.get('Discount Ratio', '0').strip()
                if discount_ratio_str.endswith('%'):
                    # 去掉百分号
                    discount_ratio = float(discount_ratio_str.rstrip('%'))
                else:
                    discount_ratio = float(discount_ratio_str)
                
                products.append({
                    'name': row.get('Product Name', '').strip(),
                    'original_price': parse_price(row.get('Original Price', 0)),
                    'promotional_price': parse_price(row.get('Promotional Price', 0)),
                    'discount_ratio': discount_ratio
                })
            except (ValueError, TypeError) as e:
                print(f"⚠️  解析CSV第{row_num}行失败: {e}")
                print(f"   行内容: {row}")
                continue
        
        return products
        
    except Exception as e:
        print(f"❌ CSV解析失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def validate_csv_products(csv_products: List[Dict], expected_low_selling: List[Dict]) -> Tuple[bool, str]:
    """
    验证CSV中的商品是否符合要求
    
    要求：
    1. CSV中的所有商品必须是低销量商品
    2. 按照入库时间从早到晚排序（天数从大到小）
    3. 如果入库时间相同，按折扣率从小到大排序
    4. 价格和折扣率要匹配
    """
    
    # 创建低销量商品映射（按名称）
    expected_products_map = {item['name']: item for item in expected_low_selling}
    
    print(f"\n   🔍 验证CSV商品...")
    
    # 1. 检查商品数量
    if len(csv_products) != len(expected_low_selling):
        return False, f"CSV商品数量({len(csv_products)})与预期的低销量商品数量({len(expected_low_selling)})不符"
    
    # 2. 检查每个商品是否是低销量商品
    for idx, csv_prod in enumerate(csv_products, 1):
        prod_name = csv_prod['name']
        
        if prod_name not in expected_products_map:
            return False, f"CSV中的商品 '{prod_name}' 不是低销量商品"
        
        expected_prod = expected_products_map[prod_name]
        
        # 检查价格
        if abs(csv_prod['original_price'] - expected_prod['regular_price']) > 0.01:
            return False, f"商品 '{prod_name}' 的原价不匹配: CSV={csv_prod['original_price']}, 预期={expected_prod['regular_price']}"
        
        if abs(csv_prod['promotional_price'] - expected_prod['sale_price']) > 0.01:
            return False, f"商品 '{prod_name}' 的促销价不匹配: CSV={csv_prod['promotional_price']}, 预期={expected_prod['sale_price']}"
        
        # 检查折扣率 (允许一定误差，因为可能有四舍五入)
        expected_discount_pct = expected_prod['discount_rate'] * 100
        if abs(csv_prod['discount_ratio'] - expected_discount_pct) > 0.2:
            return False, f"商品 '{prod_name}' 的折扣率不匹配: CSV={csv_prod['discount_ratio']}, 预期={expected_discount_pct:.3f}"
    
    # 3. 检查排序
    # 按照入库时间从早到晚（天数从大到小），相同则按折扣率从小到大
    print(f"\n   🔍 验证排序...")
    print(f"   排序规则: 1.入库时间从早到晚(天数从大到小) 2.相同时按折扣率从小到大")
    
    for idx in range(len(csv_products)):
        csv_name = csv_products[idx]['name']
        expected_name = expected_low_selling[idx]['name']
        
        if csv_name != expected_name:
            # 显示排序错误详情
            print(f"\n   ❌ 排序错误在位置 {idx + 1}:")
            print(f"      CSV商品: {csv_name}")
            print(f"      预期商品: {expected_name}")
            
            # 显示预期的排序
            print(f"\n   📋 预期的排序（前5个）:")
            for i, item in enumerate(expected_low_selling[:5], 1):
                print(f"      {i}. {item['name']}")
                print(f"         在库{item['days_in_stock']}天, 折扣率{item['discount_rate']:.3f}")
            
            # 显示实际的排序
            print(f"\n   📋 CSV的排序（前5个）:")
            for i, csv_prod in enumerate(csv_products[:5], 1):
                prod_name = csv_prod['name']
                if prod_name in expected_products_map:
                    expected_item = expected_products_map[prod_name]
                    print(f"      {i}. {prod_name}")
                    print(f"         在库{expected_item['days_in_stock']}天, 折扣率{expected_item['discount_rate']:.3f}")
            
            return False, f"商品排序错误：位置{idx + 1}应该是'{expected_name}'，但CSV中是'{csv_name}'"
    
    print(f"   ✅ 所有商品验证通过")
    print(f"   ✅ 排序正确")
    
    return True, f"CSV包含所有{len(csv_products)}个低销量商品，价格和排序都正确"


def check_email_sending_local(agent_workspace: str, woocommerce_db, email_db) -> Tuple[bool, str]:
    """检查邮件发送（本地数据库版本） - 从收件人角度检查CSV附件"""
    
    try:
        # 获取低销量商品
        low_selling_products, _ = get_low_selling_products_local(woocommerce_db)
        
        if not low_selling_products:
            return False, "没有找到低销量商品，无法生成期望的邮件内容"
        
        print(f"📋 找到 {len(low_selling_products)} 个低销量商品用于促销")
        
        # 读取订阅者信息
        subscriber_path = os.path.join(agent_workspace, 'subscriber.json')
        if not os.path.exists(subscriber_path):
            return False, f"未找到订阅者配置文件: {subscriber_path}"
        
        with open(subscriber_path, 'r', encoding='utf-8') as f:
            subscriber_config = json.load(f)
        
        subscribers = subscriber_config.get('subscriber_list', [])
        if not subscribers:
            return False, "未找到订阅者信息"
        
        print(f"\n👥 需要检查 {len(subscribers)} 个订阅者的邮件")
        
        # 从收件人角度检查邮件
        matched_recipients = set()
        total_checked_subscribers = 0
        
        print(f"\n🔍 从收件人角度检查邮件（避免群发重复问题）...")
        
        for subscriber in subscribers:
            subscriber_email = subscriber.get('email', '').lower()
            subscriber_name = subscriber.get('name', 'Unknown')
            
            if not subscriber_email:
                continue
            
            total_checked_subscribers += 1
            
            print(f"\n👤 检查订阅者 #{total_checked_subscribers}: {subscriber_name} ({subscriber_email})")
            
            # 检查该订阅者是否在邮件数据库中
            if subscriber_email not in email_db.users:
                print(f"   ⚠️  订阅者不在邮件数据库中（可能是外部邮箱）")
                continue
            
            # 读取订阅者的邮件
            user_dir = email_db._get_user_data_dir(subscriber_email)
            emails_file = os.path.join(user_dir, "emails.json")
            
            if not os.path.exists(emails_file):
                print(f"   ⚠️  邮件文件不存在: {emails_file}")
                continue
            
            try:
                with open(emails_file, 'r', encoding='utf-8') as f:
                    user_emails = json.load(f)
                
                print(f"   📧 邮件总数: {len(user_emails)}")
            except Exception as e:
                print(f"   ❌ 读取邮件文件失败: {e}")
                continue
            
            # 在INBOX中查找包含CSV附件的邮件
            found_valid_email = False
            inbox_count = 0
            
            for email_id, email_data in user_emails.items():
                if email_data.get('folder') != 'INBOX':
                    continue
                
                inbox_count += 1
                
                # 获取邮件信息
                from_addr = email_data.get('from', '')
                subject = email_data.get('subject', '')
                attachments = email_data.get('attachments', [])
                
                # 查找 discount_products.csv 附件
                csv_attachment = None
                for attachment in attachments:
                    filename = attachment.get('filename', '')
                    if filename == 'discount_products.csv':
                        csv_attachment = attachment
                        break
                
                if not csv_attachment:
                    continue
                
                print(f"   ✅ 找到包含CSV附件的邮件")
                print(f"      发件人: {from_addr}")
                print(f"      主题: {subject}")
                
                # 解析CSV内容
                try:
                    # 获取CSV附件内容
                    csv_content = get_attachment_content(
                        csv_attachment,
                        agent_workspace=agent_workspace,
                        email_db=email_db,
                        user_email=subscriber_email,
                        email_id=email_id
                    )
                    
                    if not csv_content:
                        print(f"      ❌ CSV内容为空或无法获取")
                        continue
                    
                    print(f"      📦 CSV内容长度: {len(csv_content)} 字符")
                    
                    # 解析CSV
                    csv_products = parse_csv_attachment(csv_content)
                    
                    if not csv_products:
                        print(f"      ❌ CSV解析失败")
                        continue
                    
                    print(f"      📋 CSV包含 {len(csv_products)} 个商品")
                    
                    # 显示前几个商品
                    print(f"      📝 CSV商品示例（前3个）:")
                    for idx, prod in enumerate(csv_products[:3], 1):
                        print(f"         {idx}. {prod['name']}")
                        print(f"            原价: ${prod['original_price']:.2f}, 促销价: ${prod['promotional_price']:.2f}")
                        print(f"            折扣率: {prod['discount_ratio']:.1f}%")
                    
                    # 验证CSV中的商品
                    is_valid, error_msg = validate_csv_products(csv_products, low_selling_products)
                    
                    if is_valid:
                        matched_recipients.add(subscriber_email)
                        found_valid_email = True
                        print(f"      ✅ CSV验证通过！")
                        break  # 找到一封有效邮件即可
                    else:
                        print(f"      ❌ CSV验证失败: {error_msg}")
                        
                except Exception as e:
                    print(f"      ❌ 处理CSV失败: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            if inbox_count > 0:
                print(f"   📬 INBOX中共有 {inbox_count} 封邮件")
            
            if not found_valid_email:
                print(f"   ❌ 未找到包含有效CSV附件的邮件")
        
        # 最终检查结果总结
        print(f"\n" + "=" * 70)
        print(f"📊 邮件检查结果总结:")
        print(f"   检查的订阅者总数: {total_checked_subscribers}/{len(subscribers)}")
        print(f"   已验证通过的订阅者: {len(matched_recipients)}/{len(subscribers)}")
        
        # 检查结果
        subscriber_map = {sub.get('email', '').lower(): sub.get('name', '') for sub in subscribers}
        missing_recipients = []
        for subscriber in subscribers:
            subscriber_email = subscriber.get('email', '').lower()
            if subscriber_email and subscriber_email not in matched_recipients:
                subscriber_name = subscriber.get('name', 'Unknown')
                missing_recipients.append(f"{subscriber_name} ({subscriber_email})")
        
        if matched_recipients:
            print(f"\n✅ 已验证通过的订阅者:")
            for email in sorted(matched_recipients):
                subscriber_name = subscriber_map.get(email, 'Unknown')
                print(f"   • {subscriber_name} ({email})")
        
        if missing_recipients:
            print(f"\n❌ 未验证通过的订阅者:")
            for recipient in missing_recipients:
                print(f"   • {recipient}")
        
        print("=" * 70)
        
        if not missing_recipients:
            return True, f"所有 {len(subscribers)} 个订阅者都收到了包含正确CSV附件的促销邮件，CSV包含 {len(low_selling_products)} 个低销量商品"
        else:
            return False, f"以下订阅者未收到匹配的邮件或CSV内容不正确: {', '.join(missing_recipients)}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"邮件发送检查出错: {str(e)}"


# ========== 远程API版本的函数（向后兼容） ==========

def check_product_categories_remote(wc_client) -> Tuple[bool, str]:
    """检查Product Categories（远程API版本）"""
    # 保留原有的远程API实现
    pass


def check_email_sending_remote(agent_workspace: str, wc_client) -> Tuple[bool, str]:
    """检查邮件发送（远程API版本）"""
    # 保留原有的远程API实现
    pass
