#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
计算传感器异常数据的脚本
功能：从live_sensor_data.csv中筛选2025年8月19日11:30-12:30的数据，
      对照machine_operating_parameters.xlsx中的正常参数范围，
      找出所有异常读数并生成报告
"""

import pandas as pd
from datetime import datetime
import os

def load_sensor_data(file_path):
    """
    加载传感器实时数据

    Args:
        file_path: CSV文件路径

    Returns:
        DataFrame: 传感器数据
    """
    df = pd.read_csv(file_path)
    # 将timestamp列转换为datetime类型
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def load_operating_parameters(file_path):
    """
    加载机器正常运行参数范围

    Args:
        file_path: Excel文件路径

    Returns:
        DataFrame: 参数范围数据
    """
    df = pd.read_excel(file_path)
    return df

def filter_time_range(df, start_time, end_time):
    """
    筛选指定时间范围的数据

    Args:
        df: 传感器数据DataFrame
        start_time: 开始时间字符串
        end_time: 结束时间字符串

    Returns:
        DataFrame: 筛选后的数据
    """
    start_dt = pd.to_datetime(start_time)
    end_dt = pd.to_datetime(end_time)

    # 筛选时间范围内的数据
    mask = (df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)
    filtered_df = df[mask].copy()

    print(f"筛选时间范围: {start_time} 到 {end_time}")
    print(f"筛选后数据量: {len(filtered_df)} 条记录")

    return filtered_df

def identify_anomalies(sensor_data, parameters):
    """
    识别超出正常范围的异常读数

    Args:
        sensor_data: 传感器数据DataFrame
        parameters: 参数范围DataFrame

    Returns:
        DataFrame: 异常记录
    """
    anomalies = []

    # 遍历每条传感器数据
    for idx, row in sensor_data.iterrows():
        machine_id = row['machine_id']
        sensor_type = row['sensor_type']
        reading = row['reading']
        timestamp = row['timestamp']

        # 查找对应机器和传感器类型的参数范围
        param_mask = (parameters['machine_id'] == machine_id) & \
                     (parameters['sensor_type'] == sensor_type)
        param_row = parameters[param_mask]

        if len(param_row) == 0:
            # 如果没有找到对应的参数范围，跳过
            continue

        # 获取最小值和最大值
        min_value = param_row['min_value'].values[0]
        max_value = param_row['max_value'].values[0]

        # 检查是否超出范围
        if reading < min_value or reading > max_value:
            anomaly = {
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),  # 保留毫秒
                'machine_id': machine_id,
                'sensor_type': sensor_type,
                'reading': reading,
                'normal_range': f'{min_value:.2f} - {max_value:.2f}'
            }
            anomalies.append(anomaly)

    # 即使空也保留列结构
    if len(anomalies) == 0:
        anomalies_df = pd.DataFrame(columns=['timestamp', 'machine_id', 'sensor_type', 'reading', 'normal_range'])
    else:
        anomalies_df = pd.DataFrame(anomalies)
    print(f"\n发现异常数据: {len(anomalies)} 条")

    return anomalies_df

def save_anomaly_report(anomalies_df, output_path):
    """
    保存异常报告为CSV文件

    Args:
        anomalies_df: 异常数据DataFrame
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 保存CSV文件
    anomalies_df.to_csv(output_path, index=False)
    print(f"\n异常报告已保存至: {output_path}")
    print(f"报告包含 {len(anomalies_df)} 条异常记录")

def main():
    """
    主函数：执行完整的异常检测流程
    """
    # 解析命令行参数
    import argparse
    from pathlib import Path
    import glob
    
    parser = argparse.ArgumentParser(description="生成异常检测groundtruth报告")
    parser.add_argument("--sensor-data", type=str, help="传感器数据CSV文件路径")
    parser.add_argument("--parameters", type=str, help="机器参数Excel文件路径")
    parser.add_argument("--output", type=str, help="输出异常报告CSV文件路径")
    parser.add_argument("--task-root", type=str, help="任务根目录")
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    
    # 确定文件路径
    if args.task_root:
        # 使用提供的task_root
        task_root = Path(args.task_root)
    else:
        # 向后兼容：自动推断（代码目录的上一级）
        task_root = script_dir.parent
    
    # 传感器数据路径
    if args.sensor_data:
        sensor_data_path = args.sensor_data
    else:
        # 默认位置：task_root/files/machine_operating/live_sensor.csv
        sensor_data_candidates = [
            task_root / "files" / "machine_operating" / "live_sensor.csv",
            script_dir / "live_sensor_data.csv",  # 向后兼容
            script_dir / "machine_operating" / "live_sensor.csv",  # 向后兼容
        ]
        
        sensor_data_path = None
        for candidate in sensor_data_candidates:
            if candidate.exists():
                sensor_data_path = str(candidate)
                break
        
        if not sensor_data_path:
            print("❌ 错误：找不到传感器数据文件")
            print(f"   请确保文件存在于: {task_root / 'files' / 'machine_operating' / 'live_sensor.csv'}")
            return
    
    # 参数文件路径
    if args.parameters:
        parameters_path = args.parameters
    else:
        # 默认位置：task_root/initial_workspace/machine_operating_parameters.xlsx
        parameters_candidates = [
            task_root / "initial_workspace" / "machine_operating_parameters.xlsx",
            script_dir / "machine_operating_parameters.xlsx",  # 向后兼容
        ]
        
        parameters_path = None
        for candidate in parameters_candidates:
            if candidate.exists():
                parameters_path = str(candidate)
                break
        
        if not parameters_path:
            print("❌ 错误：找不到机器参数文件")
            print(f"   请确保文件存在于: {task_root / 'initial_workspace' / 'machine_operating_parameters.xlsx'}")
            return
    
    # 输出文件路径
    if args.output:
        output_path = args.output
    else:
        # 默认位置：task_root/groundtruth_workspace/anomaly_report.csv
        output_path = str(task_root / "groundtruth_workspace" / "anomaly_report.csv")
    
    print(f"使用文件:")
    print(f"  传感器数据: {sensor_data_path}")
    print(f"  参数配置: {parameters_path}")
    print(f"  输出报告: {output_path}")

    # 定义时间范围
    start_time = '2025-08-19 11:30:00'
    end_time = '2025-08-19 12:30:00'

    print("="*60)
    print("开始处理传感器异常检测任务")
    print("="*60)

    # 1. 加载传感器数据
    print("\n1. 加载传感器数据...")
    sensor_data = load_sensor_data(sensor_data_path)
    print(f"   加载了 {len(sensor_data)} 条传感器记录")

    # 2. 加载参数范围
    print("\n2. 加载机器运行参数范围...")
    parameters = load_operating_parameters(parameters_path)
    print(f"   加载了 {len(parameters)} 条参数配置")

    # 3. 筛选时间范围
    print("\n3. 筛选时间范围内的数据...")
    filtered_data = filter_time_range(sensor_data, start_time, end_time)

    # 4. 识别异常
    print("\n4. 识别异常读数...")
    anomalies = identify_anomalies(filtered_data, parameters)

    # 5. 保存报告
    print("\n5. 保存异常报告...")
    save_anomaly_report(anomalies, output_path)

    # 显示部分异常数据样例
    if len(anomalies) > 0:
        print("\n异常数据样例（前10条）:")
        print(anomalies.head(10).to_string())

    print("\n="*60)
    print("任务完成！")
    print("="*60)

if __name__ == '__main__':
    main()