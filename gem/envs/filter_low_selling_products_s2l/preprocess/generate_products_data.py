#!/usr/bin/env python3
"""
动态生成低销量产品筛选任务的数据
包括：商品数据和订阅者数据
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from argparse import ArgumentParser
from typing import List, Dict


class ProductsDataGenerator:
    """商品和订阅者数据生成器"""
    
    def __init__(self, seed: int = 42):
        """初始化生成器"""
        random.seed(seed)
        self.current_date = datetime.now()
        
        # 商品名称库 (扩展以支持最多2000个商品)
        self.brands = [
            "Samsung", "LG", "Sony", "Xiaomi", "AOC", "Dell", "HP", "Lenovo", "Apple", "Asus",
            "Acer", "MSI", "Razer", "Logitech", "Microsoft", "Google", "Huawei", "OnePlus", "Oppo", "Vivo",
            "Panasonic", "Philips", "Sharp", "Toshiba", "TCL", "Hisense", "JBL", "Bose", "Sennheiser", "Corsair",
            "HyperX", "SteelSeries", "BenQ", "ViewSonic", "GIGABYTE", "EVGA", "Zotac", "Sapphire", "XFX", "Crucial"
        ]
        self.products = [
            "Monitor", "Phone", "TV", "Laptop", "Tablet", "Keyboard", "Mouse", "Headphone", "Speaker", "Camera",
            "Router", "Switch", "Hub", "Webcam", "Microphone", "Printer", "Scanner", "Projector", "SSD", "HDD",
            "RAM", "GPU", "CPU", "Motherboard", "PSU", "Cooler", "Fan", "UPS", "NAS", "Dock",
            "Stylus", "Gamepad", "Joystick", "VRHeadset", "Smartwatch", "Earbuds", "Soundbar", "Subwoofer", "Amplifier", "Mixer"
        ]
        self.accessories = [
            "Case", "Charger", "Cable", "Stand", "Cover", "Adapter", "Protector", "Holder",
            "Mount", "Sleeve", "Bag", "Pouch", "Dock", "Hub", "Splitter", "Extender",
            "Skin", "Film", "Grip", "Strap", "Clip", "Bracket", "Tray", "Mat"
        ]

        # 订阅者名字库 (扩展以支持最多2000个订阅者)
        self.first_names = [
            "John", "Mike", "Tom", "Sarah", "Emily", "David", "Lisa", "Kevin", "Anna", "Chris",
            "Jessica", "Daniel", "Michelle", "Brian", "Amanda", "Robert", "Jennifer", "William", "Linda", "James",
            "Mary", "Patricia", "Elizabeth", "Barbara", "Susan", "Margaret", "Dorothy", "Nancy", "Karen", "Betty",
            "Helen", "Sandra", "Donna", "Carol", "Ruth", "Sharon", "Michelle", "Laura", "Kimberly", "Deborah",
            "Michael", "Christopher", "Matthew", "Joshua", "Andrew", "Joseph", "Anthony", "Ryan", "Nicholas", "Tyler",
            "Jacob", "Ethan", "Noah", "Mason", "Lucas", "Oliver", "Elijah", "Liam", "Benjamin", "Alexander"
        ]
        self.last_names = [
            "Zhang", "Li", "Wang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou",
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
            "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
            "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
        ]
    
    def generate_low_selling_products(self, count: int) -> List[Dict]:
        """
        生成低销量商品数据

        Args:
            count: 要生成的低销量商品数量

        Returns:
            商品数据列表
        """
        products = []
        used_names = set()

        for i in range(count):
            # 生成唯一的商品名称
            attempts = 0
            while attempts < 100:
                # 生成商品名称
                if random.random() < 0.3:
                    # 30% 概率生成配件类商品
                    name = f"{random.choice(self.brands)} {random.choice(self.accessories)}"
                else:
                    # 70% 概率生成主要产品
                    name = f"{random.choice(self.brands)} {random.choice(self.products)}"

                # 添加版本号或年份使名称唯一
                if random.random() < 0.5:
                    name += f" v{random.randint(1, 20)}"
                else:
                    name += f" {random.randint(2020, 2023)}"

                # 检查名称是否已存在
                if name not in used_names:
                    used_names.add(name)
                    break
                attempts += 1
            
            # 确保在库超过90天 (90-365天)
            days_in_stock = random.randint(91, 365)
            date_created = self.current_date - timedelta(days=days_in_stock)
            
            # 30天销量 < 10 (0-9)
            sales_30_days = random.randint(0, 9)
            total_sales = sales_30_days + random.randint(5, 30)
            
            # 价格
            regular_price = round(random.uniform(19.99, 299.99), 2)
            # 给一些折扣 (10%-50%)
            discount = random.uniform(0.1, 0.5)
            sale_price = round(regular_price * (1 - discount), 2)
            
            # 库存
            stock_quantity = random.randint(10, 100)
            
            product = {
                "name": name,
                "type": "simple",
                "regular_price": str(regular_price),
                "sale_price": str(sale_price),
                "stock_quantity": stock_quantity,
                "manage_stock": True,
                "stock_status": "instock",
                "date_created": date_created.isoformat(),
                "meta_data": [
                    {"key": "product_type", "value": "low_selling"},
                    {"key": "sales_last_30_days", "value": str(sales_30_days)},
                    {"key": "_sales_last_30_days", "value": str(sales_30_days)},
                    {"key": "total_sales", "value": str(total_sales)},
                    {"key": "_total_sales", "value": str(total_sales)}
                ]
            }
            
            products.append(product)
        
        return products
    
    def generate_normal_selling_products(self, count: int) -> List[Dict]:
        """
        生成正常销量商品数据（不符合低销量条件）

        Args:
            count: 要生成的正常销量商品数量

        Returns:
            商品数据列表
        """
        products = []
        used_names = set()

        for i in range(count):
            # 生成唯一的商品名称
            attempts = 0
            while attempts < 100:
                # 生成商品名称
                name = f"{random.choice(self.brands)} {random.choice(self.products)}"

                # 添加版本号使名称唯一 (扩展年份范围以支持更多商品)
                name += f" {random.randint(2020, 2025)}"

                # 检查名称是否已存在
                if name not in used_names:
                    used_names.add(name)
                    break
                attempts += 1
            
            # 有三种正常商品类型：
            # 1. 在库时间短 (< 90天)
            # 2. 30天销量高 (>= 10)
            # 3. 两者都满足
            product_category = random.choice(['short_time', 'high_sales', 'both'])
            
            if product_category == 'short_time':
                # 在库时间短
                days_in_stock = random.randint(1, 89)
                sales_30_days = random.randint(0, 15)
            elif product_category == 'high_sales':
                # 销量高
                days_in_stock = random.randint(91, 300)
                sales_30_days = random.randint(10, 100)
            else:  # both
                # 两者都好
                days_in_stock = random.randint(1, 89)
                sales_30_days = random.randint(10, 100)
            
            date_created = self.current_date - timedelta(days=days_in_stock)
            total_sales = sales_30_days + random.randint(10, 100)
            
            # 价格
            regular_price = round(random.uniform(29.99, 499.99), 2)
            # 小折扣或无折扣
            if random.random() < 0.5:
                sale_price = round(regular_price * random.uniform(0.9, 0.98), 2)
            else:
                sale_price = None  # 无折扣
            
            # 库存
            stock_quantity = random.randint(20, 200)
            
            product = {
                "name": name,
                "type": "simple",
                "regular_price": str(regular_price),
                "stock_quantity": stock_quantity,
                "manage_stock": True,
                "stock_status": "instock",
                "date_created": date_created.isoformat(),
                "meta_data": [
                    {"key": "product_type", "value": "normal_selling"},
                    {"key": "sales_last_30_days", "value": str(sales_30_days)},
                    {"key": "_sales_last_30_days", "value": str(sales_30_days)},
                    {"key": "total_sales", "value": str(total_sales)},
                    {"key": "_total_sales", "value": str(total_sales)}
                ]
            }
            
            if sale_price:
                product["sale_price"] = str(sale_price)
            
            products.append(product)
        
        return products
    
    def generate_subscribers(self, count: int) -> List[Dict]:
        """
        生成订阅者数据
        
        Args:
            count: 要生成的订阅者数量
            
        Returns:
            订阅者数据列表
        """
        subscribers = []
        used_emails = set()
        
        for i in range(count):
            # 生成唯一的名字和邮箱
            attempts = 0
            while attempts < 100:
                first_name = random.choice(self.first_names)
                last_name = random.choice(self.last_names)
                email = f"{first_name.lower()}{last_name.lower()}{random.randint(1, 99)}@mcpt.com"
                
                if email not in used_emails:
                    used_emails.add(email)
                    break
                attempts += 1
            
            subscriber = {
                "email": email,
                "name": f"{first_name} {last_name}"
            }
            
            subscribers.append(subscriber)
        
        return subscribers


def generate_products_and_subscribers(
    output_dir: Path,
    num_low_selling: int = 5,
    num_normal_selling: int = 3,
    num_subscribers: int = 3,
    seed: int = 42
) -> bool:
    """
    生成商品和订阅者数据并保存
    
    Args:
        output_dir: 输出目录（任务根目录）
        num_low_selling: 低销量商品数量
        num_normal_selling: 正常销量商品数量
        num_subscribers: 订阅者数量
        seed: 随机种子
        
    Returns:
        True if successful
    """
    print("=" * 60)
    print("生成商品和订阅者数据")
    print("=" * 60)
    
    try:
        # 初始化生成器
        generator = ProductsDataGenerator(seed=seed)
        
        # 生成商品数据
        print(f"\n📦 生成商品数据...")
        low_selling = generator.generate_low_selling_products(num_low_selling)
        normal_selling = generator.generate_normal_selling_products(num_normal_selling)
        
        all_products = low_selling + normal_selling
        random.shuffle(all_products)  # 打乱顺序
        
        print(f"   ✓ 低销量商品: {num_low_selling} 个")
        print(f"   ✓ 正常销量商品: {num_normal_selling} 个")
        print(f"   ✓ 商品总数: {len(all_products)} 个")
        
        # 生成订阅者数据
        print(f"\n👥 生成订阅者数据...")
        subscribers = generator.generate_subscribers(num_subscribers)
        print(f"   ✓ 订阅者: {num_subscribers} 个")
        
        # 保存商品数据到 preprocess 目录（供WooCommerce数据库使用）
        preprocess_dir = output_dir / "preprocess"
        preprocess_dir.mkdir(parents=True, exist_ok=True)
        
        products_file = preprocess_dir / "generated_products.json"
        with open(products_file, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=2, ensure_ascii=False)
        print(f"\n💾 商品数据已保存: {products_file}")
        
        # 保存订阅者数据到 initial_workspace
        initial_workspace = output_dir / "initial_workspace"
        initial_workspace.mkdir(parents=True, exist_ok=True)
        
        subscriber_file = initial_workspace / "subscriber.json"
        subscriber_data = {"subscriber_list": subscribers}
        with open(subscriber_file, 'w', encoding='utf-8') as f:
            json.dump(subscriber_data, f, indent=2, ensure_ascii=False)
        print(f"💾 订阅者数据已保存: {subscriber_file}")
        
        # 保存 groundtruth 信息
        groundtruth_workspace = output_dir / "groundtruth_workspace"
        groundtruth_workspace.mkdir(parents=True, exist_ok=True)
        
        groundtruth_file = groundtruth_workspace / "generation_metadata.json"
        metadata = {
            "generation_params": {
                "num_low_selling": num_low_selling,
                "num_normal_selling": num_normal_selling,
                "num_subscribers": num_subscribers,
                "seed": seed,
                "total_products": len(all_products)
            },
            "low_selling_products": [p["name"] for p in low_selling],
            "normal_selling_products": [p["name"] for p in normal_selling],
            "subscribers": [s["email"] for s in subscribers],
            "timestamp": datetime.now().isoformat()
        }
        
        with open(groundtruth_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"💾 Groundtruth 元数据已保存: {groundtruth_file}")
        
        print("\n✅ 数据生成完成！")
        return True
        
    except Exception as e:
        print(f"❌ 数据生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = ArgumentParser(description="生成低销量产品筛选任务的数据")
    parser.add_argument("--output-dir", type=str, required=True,
                       help="输出目录（任务根目录）")
    parser.add_argument("--num-low-selling", type=int, default=5,
                       help="低销量商品数量 (默认: 5)")
    parser.add_argument("--num-normal-selling", type=int, default=3,
                       help="正常销量商品数量 (默认: 3)")
    parser.add_argument("--num-subscribers", type=int, default=3,
                       help="订阅者数量 (默认: 3)")
    parser.add_argument("--seed", type=int, default=42,
                       help="随机种子 (默认: 42)")
    
    args = parser.parse_args()
    
    success = generate_products_and_subscribers(
        output_dir=Path(args.output_dir),
        num_low_selling=args.num_low_selling,
        num_normal_selling=args.num_normal_selling,
        num_subscribers=args.num_subscribers,
        seed=args.seed
    )
    
    exit(0 if success else 1)

