#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B Testing 数据生成器
动态生成不同难度的 A/B 测试数据集
"""

import csv
import random
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta


class ABTestingDataGenerator:
    """A/B 测试数据生成器"""
    
    # 场景名称库（扩展到支持100+场景）
    SCENARIO_NAMES = [
        # 电商类别（20个）
        "Appliances", "Automotive", "Baby", "Beauty", "Books", 
        "Clothing", "Education", "Electronics", "Food", "FreshFood",
        "Gaming", "Health", "Home", "Hospitality", "Music",
        "Office", "Outdoor", "Pets", "Sports", "Travel",
        
        # 更多商品类别（30个）
        "Toys", "Garden", "Jewelry", "Furniture", "Art",
        "Crafts", "Industrial", "Software", "Movies", "VideoGames",
        "Fashion", "Shoes", "Bags", "Watches", "Eyewear",
        "Cosmetics", "Skincare", "Fragrance", "HairCare", "PersonalCare",
        "Kitchenware", "Bedding", "Bath", "Decor", "Lighting",
        "Tools", "Hardware", "Paint", "Plumbing", "Electrical",
        
        # 专业类别（30个）
        "Photography", "Audio", "Cameras", "Drones", "SmartHome",
        "Wearables", "Tablets", "Laptops", "Desktops", "Monitors",
        "Networking", "Storage", "Printers", "Scanners", "Projectors",
        "Musical", "Instruments", "RecordingEquipment", "DJEquipment", "ProAudio",
        "Fitness", "Yoga", "Cycling", "Running", "Swimming",
        "Camping", "Hiking", "Fishing", "Hunting", "Climbing",
        
        # 生活方式类别（30个）
        "Nutrition", "Supplements", "Vitamins", "Protein", "OrganicFood",
        "BabyFood", "BabyClothing", "BabyToys", "Diapers", "BabyCare",
        "PetFood", "PetToys", "PetCare", "PetGrooming", "PetTraining",
        "Wedding", "Party", "Gifts", "Flowers", "Cards",
        "Stationery", "SchoolSupplies", "OfficeSupplies", "ArtSupplies", "CraftSupplies",
        "Magazines", "Comics", "Audiobooks", "eBooks", "Textbooks",
        
        # 扩展类别（25个）
        "Antiques", "Collectibles", "Memorabilia", "VintageFashion", "VintageJewelry",
        "LuxuryGoods", "DesignerFashion", "HighEndElectronics", "PremiumBeauty", "GourmetFood",
        "Organic", "EcoFriendly", "Sustainable", "FairTrade", "LocalProducts",
        "HandmadeItems", "CustomProducts", "PersonalizedGifts", "BespokeServices", "ArtisanGoods",
        "DigitalProducts", "OnlineCourses", "Subscriptions", "Memberships", "VirtualGoods",
        
        # 额外商品类别（30个）
        "Snacks", "Beverages", "Coffee", "Tea", "Wine",
        "Beer", "Spirits", "Cheese", "Chocolate", "Bakery",
        "Seafood", "Meat", "Produce", "Dairy", "Frozen",
        "Canned", "Condiments", "Spices", "Pasta", "Rice",
        "Cereal", "Candy", "Desserts", "IceCream", "Pizza",
        "Sandwiches", "Salads", "Soups", "Sauces", "Dips",
        
        # 更多服务和娱乐类别（30个）
        "Streaming", "CloudServices", "WebHosting", "Security", "Insurance",
        "Banking", "Investment", "RealEstate", "Consulting", "Marketing",
        "Advertising", "Design", "Development", "Writing", "Translation",
        "Photography", "Videography", "Animation", "VoiceOver", "Podcast",
        "Events", "Catering", "Cleaning", "Maintenance", "Repair",
        "Installation", "Delivery", "Shipping", "Storage", "Moving",
        
        # 专业服务类别（30个）
        "Legal", "Accounting", "Tax", "Audit", "Compliance",
        "HR", "Recruitment", "Training", "Coaching", "Mentoring",
        "Therapy", "Counseling", "Nutrition", "Dietitian", "Fitness",
        "PersonalTraining", "Massage", "Spa", "Salon", "Barbershop",
        "Veterinary", "Grooming", "DayCare", "Tutoring", "MusicLessons",
        "DanceLessons", "ArtClasses", "LanguageLessons", "Workshops", "Seminars",
        
        # 兴趣爱好类别（20个）
        "Knitting", "Sewing", "Quilting", "Embroidery", "Crochet",
        "Woodworking", "Metalworking", "Pottery", "Painting", "Drawing",
        "Sculpting", "Photography", "Birdwatching", "Astronomy", "Gardening",
        "Aquariums", "Terrariums", "ModelBuilding", "Origami", "Calligraphy"
    ]
    
    def __init__(self, seed: int = 42):
        """初始化生成器"""
        random.seed(seed)
    
    def generate_time_windows(self, 
                             num_days: int = 15,
                             start_date: str = "7/29") -> List[str]:
        """生成时间窗口列表
        
        Args:
            num_days: 天数
            start_date: 开始日期（格式: "M/D"）
            
        Returns:
            时间窗口列表，格式: ["7/29 00:00-00:59", ...]
        """
        time_windows = []
        
        # 解析起始日期
        month, day = map(int, start_date.split('/'))
        current_date = datetime(2024, month, day)
        
        for _ in range(num_days):
            date_str = f"{current_date.month}/{current_date.day}"
            for hour in range(24):
                time_window = f"{date_str} {hour:02d}:00-{hour:02d}:59"
                time_windows.append(time_window)
            current_date += timedelta(days=1)
        
        return time_windows
    
    def generate_ab_data(self,
                        time_windows: List[str],
                        base_conversion_rate: float = 0.74,
                        conversion_diff: float = 0.01,
                        click_range: Tuple[int, int] = (0, 200),
                        noise_level: float = 0.1,
                        zero_probability: float = 0.05) -> List[Dict]:
        """生成 A/B 测试数据
        
        Args:
            time_windows: 时间窗口列表
            base_conversion_rate: 基础转化率
            conversion_diff: A/B 转化率差异（B - A）
            click_range: 点击数范围
            noise_level: 噪音水平（转化率的随机波动）
            zero_probability: 某个值为0的概率
            
        Returns:
            数据行列表
        """
        data_rows = []
        
        # A 和 B 的目标转化率
        a_conversion = base_conversion_rate - conversion_diff / 2
        b_conversion = base_conversion_rate + conversion_diff / 2
        
        for time_window in time_windows:
            # 生成 A 组数据
            if random.random() < zero_probability:
                a_clicks = 0
                a_store_views = 0
            else:
                a_clicks = random.randint(click_range[0], click_range[1])
                # 添加噪音到转化率
                actual_a_conversion = a_conversion + random.gauss(0, noise_level * a_conversion)
                actual_a_conversion = max(0.3, min(0.95, actual_a_conversion))  # 限制范围
                a_store_views = int(a_clicks * actual_a_conversion)
            
            # 生成 B 组数据
            if random.random() < zero_probability:
                b_clicks = 0
                b_store_views = 0
            else:
                b_clicks = random.randint(click_range[0], click_range[1])
                # 添加噪音到转化率
                actual_b_conversion = b_conversion + random.gauss(0, noise_level * b_conversion)
                actual_b_conversion = max(0.3, min(0.95, actual_b_conversion))  # 限制范围
                b_store_views = int(b_clicks * actual_b_conversion)
            
            data_rows.append({
                "time_window": time_window,
                "A_clicks": a_clicks,
                "A_store_views": a_store_views,
                "B_clicks": b_clicks,
                "B_store_views": b_store_views
            })
        
        return data_rows
    
    def calculate_conversion_rate(self, data_rows: List[Dict]) -> Tuple[float, float]:
        """计算实际转化率
        
        Args:
            data_rows: 数据行列表
            
        Returns:
            (A转化率, B转化率)
        """
        total_a_clicks = sum(row["A_clicks"] for row in data_rows)
        total_a_views = sum(row["A_store_views"] for row in data_rows)
        total_b_clicks = sum(row["B_clicks"] for row in data_rows)
        total_b_views = sum(row["B_store_views"] for row in data_rows)
        
        a_rate = total_a_views / total_a_clicks if total_a_clicks > 0 else 0
        b_rate = total_b_views / total_b_clicks if total_b_clicks > 0 else 0
        
        return a_rate, b_rate
    
    def save_csv(self, data_rows: List[Dict], output_file: Path):
        """保存数据到 CSV 文件
        
        Args:
            data_rows: 数据行列表
            output_file: 输出文件路径
        """
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "time_window", "A_clicks", "A_store_views", "B_clicks", "B_store_views"
            ])
            writer.writeheader()
            writer.writerows(data_rows)
    
    def generate_scenarios(self,
                          num_scenarios: int = 20,
                          num_days: int = 15,
                          base_conversion_range: Tuple[float, float] = (0.70, 0.78),
                          conversion_diff_range: Tuple[float, float] = (-0.03, 0.03),
                          click_range: Tuple[int, int] = (0, 200),
                          noise_level: float = 0.1,
                          zero_probability: float = 0.05,
                          difficulty: str = "medium") -> Dict:
        """生成多个场景的数据
        
        Args:
            num_scenarios: 场景数量（支持1-1000+）
            num_days: 每个场景的天数
            base_conversion_range: 基础转化率范围
            conversion_diff_range: A/B 转化率差异范围
            click_range: 点击数范围
            noise_level: 噪音水平
            zero_probability: 值为0的概率
            difficulty: 难度级别 (easy/medium/hard)
            
        Returns:
            包含场景数据和统计信息的字典
        """
        # 根据难度调整参数
        if difficulty == "easy":
            # 简单：明显的转化率差异，少噪音，少场景
            conversion_diff_range = (0.02, 0.05)
            noise_level = 0.05
            num_scenarios = min(num_scenarios, 5)
            click_range = (50, 150)
            zero_probability = 0.02
        elif difficulty == "hard":
            # 困难：微小的转化率差异，多噪音，多场景
            conversion_diff_range = (-0.01, 0.01)
            noise_level = 0.15
            click_range = (0, 250)
            zero_probability = 0.1
        # medium 使用默认参数
        
        scenarios = []
        time_windows = self.generate_time_windows(num_days)
        
        # 选择场景名称 - 支持超过预定义名称数量的场景
        if num_scenarios <= len(self.SCENARIO_NAMES):
            # 如果请求的场景数量不超过预定义名称，随机选择
            selected_names = random.sample(self.SCENARIO_NAMES, num_scenarios)
        else:
            # 如果超过预定义名称数量，使用所有名称并生成额外的编号名称
            selected_names = list(self.SCENARIO_NAMES)
            # 生成额外的场景名称（使用 Scenario_N 格式）
            extra_count = num_scenarios - len(self.SCENARIO_NAMES)
            for i in range(extra_count):
                selected_names.append(f"Scenario_{len(self.SCENARIO_NAMES) + i + 1}")
            print(f"   ℹ️  生成了 {extra_count} 个额外的场景名称 (Scenario_N 格式)")
        
        for scenario_name in selected_names:
            # 为每个场景生成随机参数
            base_conversion = random.uniform(*base_conversion_range)
            conversion_diff = random.uniform(*conversion_diff_range)
            
            # 生成数据
            data_rows = self.generate_ab_data(
                time_windows=time_windows,
                base_conversion_rate=base_conversion,
                conversion_diff=conversion_diff,
                click_range=click_range,
                noise_level=noise_level,
                zero_probability=zero_probability
            )
            
            # 计算实际转化率
            a_rate, b_rate = self.calculate_conversion_rate(data_rows)
            
            scenarios.append({
                "name": scenario_name,
                "data_rows": data_rows,
                "a_conversion_rate": a_rate,
                "b_conversion_rate": b_rate,
                "num_rows": len(data_rows)
            })
        
        return {
            "scenarios": scenarios,
            "num_scenarios": len(scenarios),
            "num_days": num_days,
            "difficulty": difficulty,
            "parameters": {
                "base_conversion_range": base_conversion_range,
                "conversion_diff_range": conversion_diff_range,
                "click_range": click_range,
                "noise_level": noise_level,
                "zero_probability": zero_probability
            }
        }
    
    def save_expected_ratio(self, scenarios: List[Dict], output_file: Path):
        """保存期望的转化率文件（ground truth）
        
        Args:
            scenarios: 场景列表
            output_file: 输出文件路径
        """
        # 计算总体转化率
        total_a_clicks = sum(
            sum(row["A_clicks"] for row in s["data_rows"]) 
            for s in scenarios
        )
        total_a_views = sum(
            sum(row["A_store_views"] for row in s["data_rows"]) 
            for s in scenarios
        )
        total_b_clicks = sum(
            sum(row["B_clicks"] for row in s["data_rows"]) 
            for s in scenarios
        )
        total_b_views = sum(
            sum(row["B_store_views"] for row in s["data_rows"]) 
            for s in scenarios
        )
        
        overall_a_rate = total_a_views / total_a_clicks if total_a_clicks > 0 else 0
        overall_b_rate = total_b_views / total_b_clicks if total_b_clicks > 0 else 0
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["scenario", "A_conversion %", "B_conversion %"])
            
            for scenario in scenarios:
                writer.writerow([
                    scenario["name"],
                    f"{scenario['a_conversion_rate'] * 100:.3f}%",
                    f"{scenario['b_conversion_rate'] * 100:.3f}%"
                ])
            
            writer.writerow([
                "overall (total_store_views/total_clicks)",
                f"{overall_a_rate * 100:.3f}%",
                f"{overall_b_rate * 100:.3f}%"
            ])


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成 A/B 测试数据')
    
    # 基本参数
    parser.add_argument('--num-scenarios', type=int, default=20,
                       help='场景数量，支持1-1000+ (默认: 20)')
    parser.add_argument('--num-days', type=int, default=15,
                       help='每个场景的天数 (默认: 15)')
    parser.add_argument('--seed', type=int, default=42,
                       help='随机种子 (默认: 42)')
    parser.add_argument('--output-dir', type=str, default='files',
                       help='输出目录 (默认: files)')
    
    # 难度控制
    parser.add_argument('--difficulty', type=str, default='medium',
                       choices=['easy', 'medium', 'hard'],
                       help='难度级别 (默认: medium)')
    
    # 高级参数
    parser.add_argument('--base-conversion-min', type=float, default=0.70,
                       help='基础转化率最小值 (默认: 0.70)')
    parser.add_argument('--base-conversion-max', type=float, default=0.78,
                       help='基础转化率最大值 (默认: 0.78)')
    parser.add_argument('--conversion-diff-min', type=float, default=-0.03,
                       help='转化率差异最小值 (默认: -0.03)')
    parser.add_argument('--conversion-diff-max', type=float, default=0.03,
                       help='转化率差异最大值 (默认: 0.03)')
    parser.add_argument('--click-min', type=int, default=0,
                       help='点击数最小值 (默认: 0)')
    parser.add_argument('--click-max', type=int, default=200,
                       help='点击数最大值 (默认: 200)')
    parser.add_argument('--noise-level', type=float, default=0.1,
                       help='噪音水平 (默认: 0.1)')
    parser.add_argument('--zero-probability', type=float, default=0.05,
                       help='值为0的概率 (默认: 0.05)')
    
    # 输出控制
    parser.add_argument('--save-groundtruth', action='store_true',
                       help='同时保存 ground truth 到 groundtruth_workspace')
    parser.add_argument('--groundtruth-dir', type=str, default='groundtruth_workspace',
                       help='Ground truth 输出目录 (默认: groundtruth_workspace)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📊 A/B 测试数据生成器")
    print("=" * 60)
    print(f"场景数量: {args.num_scenarios}")
    print(f"每个场景天数: {args.num_days}")
    print(f"每个场景行数: {args.num_days * 24}")
    print(f"难度级别: {args.difficulty}")
    print(f"随机种子: {args.seed}")
    print(f"输出目录: {args.output_dir}")
    print("=" * 60)
    
    # 创建生成器
    generator = ABTestingDataGenerator(seed=args.seed)
    
    # 生成数据
    result = generator.generate_scenarios(
        num_scenarios=args.num_scenarios,
        num_days=args.num_days,
        base_conversion_range=(args.base_conversion_min, args.base_conversion_max),
        conversion_diff_range=(args.conversion_diff_min, args.conversion_diff_max),
        click_range=(args.click_min, args.click_max),
        noise_level=args.noise_level,
        zero_probability=args.zero_probability,
        difficulty=args.difficulty
    )
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    
    # 清空输出目录下的旧 CSV 文件
    if output_dir.exists():
        old_csv_files = list(output_dir.glob("ab_*.csv"))
        if old_csv_files:
            print(f"\n🗑️  清理输出目录...")
            for old_file in old_csv_files:
                old_file.unlink()
                print(f"   ✓ 删除旧文件: {old_file.name}")
            print(f"   ✅ 已删除 {len(old_csv_files)} 个旧 CSV 文件")
    
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # 保存每个场景的 CSV 文件
    print(f"\n📁 生成场景数据...")
    for scenario in result["scenarios"]:
        filename = f"ab_{scenario['name']}.csv"
        output_file = output_dir / filename
        generator.save_csv(scenario["data_rows"], output_file)
        print(f"   ✅ {filename}: {scenario['num_rows']} 行, "
              f"A转化率={scenario['a_conversion_rate']*100:.3f}%, "
              f"B转化率={scenario['b_conversion_rate']*100:.3f}%")
    
    # 保存 ground truth
    if args.save_groundtruth:
        groundtruth_dir = Path(args.groundtruth_dir)
        groundtruth_dir.mkdir(exist_ok=True, parents=True)
        expected_ratio_file = groundtruth_dir / "expected_ratio.csv"
        generator.save_expected_ratio(result["scenarios"], expected_ratio_file)
        print(f"\n📄 生成 Ground Truth: {expected_ratio_file}")
    
    print("\n" + "=" * 60)
    print("🎉 数据生成完成！")
    print("=" * 60)
    print(f"✅ 生成了 {result['num_scenarios']} 个场景")
    print(f"✅ 每个场景包含 {result['num_days']} 天的数据")
    print(f"✅ 总共 {result['num_scenarios'] * result['num_days'] * 24} 行数据")
    
    print(f"\n📊 生成参数:")
    print(f"   难度: {result['difficulty']}")
    print(f"   基础转化率范围: {result['parameters']['base_conversion_range']}")
    print(f"   转化率差异范围: {result['parameters']['conversion_diff_range']}")
    print(f"   点击数范围: {result['parameters']['click_range']}")
    print(f"   噪音水平: {result['parameters']['noise_level']}")
    print(f"   零值概率: {result['parameters']['zero_probability']}")
    
    print(f"\n📈 转化率统计:")
    a_rates = [s['a_conversion_rate'] for s in result['scenarios']]
    b_rates = [s['b_conversion_rate'] for s in result['scenarios']]
    print(f"   A组平均转化率: {sum(a_rates)/len(a_rates)*100:.3f}%")
    print(f"   B组平均转化率: {sum(b_rates)/len(b_rates)*100:.3f}%")
    print(f"   平均差异: {(sum(b_rates)/len(b_rates) - sum(a_rates)/len(a_rates))*100:.3f}%")


if __name__ == "__main__":
    main()

