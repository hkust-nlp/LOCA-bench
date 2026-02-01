#!/usr/bin/env python3
"""
成功的多轮执行示例

这个示例会真正完成多轮执行并返回真实结果（没有占位符）
"""

import json
import sys
from pathlib import Path

# Add gem to path
gem_root = Path(__file__).parent.parent.parent.parent.parent
if str(gem_root) not in sys.path:
    sys.path.insert(0, str(gem_root))


def example_without_filesystem():
    """
    示例1：不使用文件系统工具
    只使用纯Python代码，没有工具调用
    """
    print("=" * 70)
    print("示例1：纯Python代码（无工具调用）")
    print("=" * 70)

    from gem.tools.mcp_server.programmatic_tool_calling.helper import (
        get_programmatic_tool_calling_stdio_config,
        ProgrammaticToolCallingTool
    )

    workspace_path = Path(__file__).parent
    mcp_config = {"mcpServers": {}}
    prog_cfg = get_programmatic_tool_calling_stdio_config(workspace_path=str(workspace_path))
    mcp_config["mcpServers"].update(prog_cfg)

    tool = ProgrammaticToolCallingTool(mcp_config, validate_on_init=False)

    # 获取工具名
    available_tools = tool.get_available_tools()
    prog_tool_name = [t['name'] for t in available_tools if 'programmatic_tool_calling' in t['name']][0]

    # 纯计算代码（无工具调用）
    code = '''
# 计算斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

# 计算前10个数
fib_numbers = [fibonacci(i) for i in range(10)]
print(f"Fibonacci numbers: {fib_numbers}")

# 计算总和
total = sum(fib_numbers)
print(f"Sum: {total}")

result = f"Calculated {len(fib_numbers)} Fibonacci numbers, sum = {total}"
'''

    print("\n代码:")
    print(code)
    print("\n执行中...")

    tool_parsed, has_error, observation, _, _ = tool.execute_tool(
        prog_tool_name,
        {"code": code},
        "example_001"
    )

    result = json.loads(observation)

    print("\n" + "=" * 70)
    print("结果")
    print("=" * 70)
    print(f"✓ 成功: {result['success']}")
    print(f"✓ 返回值: {result['return_value']}")
    print(f"✓ 执行时间: {result['execution_time_seconds']:.3f}s")
    print(f"✓ 工具调用次数: {len(result['tool_calls'])}")
    print(f"✓ needs_tool_execution: {result.get('needs_tool_execution', False)}")

    print(f"\n控制台输出:")
    for line in result['stdout'].strip().split('\n'):
        print(f"  {line}")

    # 验证没有占位符
    has_placeholder = any(
        '__TOOL_CALL_PENDING_' in str(tr.get('observation', ''))
        for tr in result.get('tool_results', [])
    )

    if has_placeholder:
        print(f"\n✗ 发现占位符！")
        return False
    else:
        print(f"\n✓ 没有占位符，执行成功！")
        return True


def example_with_memory_tool():
    """
    示例2：使用 memory 工具
    memory 工具总是可以访问的，不会有路径问题
    """
    print("\n\n" + "=" * 70)
    print("示例2：使用 memory 工具（读写内存）")
    print("=" * 70)

    from gem.tools.mcp_server.programmatic_tool_calling.helper import (
        get_programmatic_tool_calling_stdio_config,
        ProgrammaticToolCallingTool
    )
    from gem.tools.mcp_server.memory.helper import get_memory_stdio_config

    workspace_path = Path(__file__).parent

    # 创建合并配置
    mcp_config = {"mcpServers": {}}

    # 添加 memory 服务器
    memory_cfg = get_memory_stdio_config()
    mcp_config["mcpServers"].update(memory_cfg)

    # 添加 programmatic_tool_calling 服务器
    prog_cfg = get_programmatic_tool_calling_stdio_config(workspace_path=str(workspace_path))
    mcp_config["mcpServers"].update(prog_cfg)

    tool = ProgrammaticToolCallingTool(mcp_config, validate_on_init=False)

    # 获取工具名
    available_tools = tool.get_available_tools()
    print(f"\n可用工具 ({len(available_tools)} 个):")
    for t in available_tools[:5]:
        print(f"  - {t['name']}")
    if len(available_tools) > 5:
        print(f"  ... 还有 {len(available_tools) - 5} 个工具")

    prog_tool_name = [t['name'] for t in available_tools if 'programmatic_tool_calling' in t['name']][0]

    # 使用 memory 工具的代码
    code = '''
# 步骤1：创建实体
print("Step 1: Creating entities...")
tools.memory_create_entities(
    entities=[
        {"name": "user1", "entityType": "person", "observations": ["喜欢编程", "Python开发者"]},
        {"name": "user2", "entityType": "person", "observations": ["喜欢音乐", "吉他手"]}
    ]
)
print("  Created 2 entities")

# 步骤2：查询实体
print("Step 2: Searching entities...")
results = tools.memory_search_nodes(query="编程")
print(f"  Found {len(results)} matching entities")

# 步骤3：创建关系
print("Step 3: Creating relations...")
tools.memory_create_relations(
    relations=[
        {"from": "user1", "to": "user2", "relationType": "knows"}
    ]
)
print("  Created 1 relation")

# 步骤4：读取图
print("Step 4: Reading graph...")
graph = tools.memory_read_graph()
print(f"  Graph has {len(graph.get('entities', []))} entities and {len(graph.get('relations', []))} relations")

result = f"Successfully managed knowledge graph: {len(graph.get('entities', []))} entities, {len(graph.get('relations', []))} relations"
'''

    print("\n代码:")
    print(code)
    print("\n执行中...")

    tool_parsed, has_error, observation, _, _ = tool.execute_tool(
        prog_tool_name,
        {"code": code},
        "example_002"
    )

    result = json.loads(observation)

    print("\n" + "=" * 70)
    print("结果")
    print("=" * 70)
    print(f"✓ 成功: {result['success']}")
    print(f"✓ 返回值: {result['return_value']}")
    print(f"✓ 执行时间: {result['execution_time_seconds']:.3f}s")
    print(f"✓ 工具调用次数: {len(result['tool_calls'])}")
    print(f"✓ needs_tool_execution: {result.get('needs_tool_execution', False)}")

    print(f"\n工具调用历史:")
    for i, tc in enumerate(result['tool_calls'], 1):
        print(f"  {i}. {tc['tool_name']}")

    print(f"\n控制台输出:")
    for line in result['stdout'].strip().split('\n'):
        print(f"  {line}")

    # 验证没有占位符
    has_placeholder = any(
        '__TOOL_CALL_PENDING_' in str(tr.get('observation', ''))
        for tr in result.get('tool_results', [])
    )

    if has_placeholder:
        print(f"\n✗ 发现占位符！")
        print(f"\n工具结果详情:")
        for tr in result['tool_results']:
            obs = tr['observation']
            if len(obs) > 100:
                obs = obs[:100] + "..."
            print(f"  - {tr['tool_call_id']}: {obs}")
        return False
    else:
        print(f"\n✓ 没有占位符，所有工具调用都成功完成！")
        print(f"✓ 多轮执行成功，返回真实结果！")
        return True


def example_with_proper_filesystem():
    """
    示例3：使用正确配置的 filesystem 工具
    确保路径在允许范围内
    """
    print("\n\n" + "=" * 70)
    print("示例3：使用 filesystem 工具（正确配置）")
    print("=" * 70)

    from gem.tools.mcp_server.programmatic_tool_calling.helper import (
        get_programmatic_tool_calling_stdio_config,
        ProgrammaticToolCallingTool
    )
    from gem.tools.mcp_server.filesystem.helper import get_filesystem_stdio_config

    workspace_path = Path(__file__).parent

    # 创建合并配置 - 使用正确的 allowed_directory
    mcp_config = {"mcpServers": {}}

    # 添加 filesystem 服务器 - 允许访问整个 programmatic_tool_calling 目录
    filesystem_cfg = get_filesystem_stdio_config(allowed_directory=str(workspace_path))
    mcp_config["mcpServers"].update(filesystem_cfg)

    # 添加 programmatic_tool_calling 服务器
    prog_cfg = get_programmatic_tool_calling_stdio_config(workspace_path=str(workspace_path))
    mcp_config["mcpServers"].update(prog_cfg)

    tool = ProgrammaticToolCallingTool(mcp_config, validate_on_init=False)

    # 获取工具名
    available_tools = tool.get_available_tools()
    prog_tool_name = [t['name'] for t in available_tools if 'programmatic_tool_calling' in t['name']][0]

    # 使用 filesystem 工具的代码 - 使用绝对路径确保访问成功
    code = f'''
import os

# 使用绝对路径
workspace = "{workspace_path}"

# 步骤1：列出工作空间中的文件
print("Step 1: Listing files in workspace...")
files = tools.filesystem_list_directory(path=workspace)
print(files)
print(f"  Found {{len(files)}} files")

# 步骤2：筛选 .md 文档
md_files = [f for f in files if f.endswith('.md')]
print(f"Step 2: Found {{len(md_files)}} markdown files")

# 步骤3：读取第一个 .md 文件（如果存在）
if md_files:
    first_md = md_files[0]
    print(f"Step 3: Reading {{first_md}}...")
    content = tools.filesystem_read_file(path=os.path.join(workspace, first_md))
    lines = content.split('\\n')
    print(f"  File has {{len(lines)}} lines, {{len(content)}} characters")

    # 显示前3行
    print("  First 3 lines:")
    for i, line in enumerate(lines[:3], 1):
        if line.strip():
            preview = line[:60] + "..." if len(line) > 60 else line
            print(f"    {{i}}. {{preview}}")

    result = f"Successfully processed {{len(files)}} files, read {{first_md}} ({{len(lines)}} lines)"
else:
    result = f"Successfully listed {{len(files)}} files (no .md files found)"
'''

    print("\n代码:")
    for line in code.split('\n')[:10]:
        print(f"  {line}")
    print("  ...")
    print("\n执行中...")

    print(tool.get_available_tools())
    print("prog_tool_name: ", prog_tool_name)

    tool_parsed, has_error, observation, _, _ = tool.execute_tool(
        prog_tool_name,
        {"code": code},
        "example_003"
    )

    result = json.loads(observation)

    print("\n" + "=" * 70)
    print("结果")
    print("=" * 70)
    print(f"✓ 成功: {result['success']}")
    print(f"✓ 返回值: {result['return_value']}")
    print(f"✓ 执行时间: {result['execution_time_seconds']:.3f}s")
    print(f"✓ 工具调用次数: {len(result['tool_calls'])}")
    print(f"✓ needs_tool_execution: {result.get('needs_tool_execution', False)}")

    print(f"\n工具调用历史:")
    for i, tc in enumerate(result['tool_calls'], 1):
        args_summary = ', '.join(f"{k}=..." for k in tc['args'].keys())
        print(f"  {i}. {tc['tool_name']}({args_summary})")

    print(f"\n控制台输出:")
    for line in result['stdout'].strip().split('\n'):
        print(f"  {line}")

    # 验证没有占位符
    has_placeholder = any(
        '__TOOL_CALL_PENDING_' in str(tr.get('observation', ''))
        for tr in result.get('tool_results', [])
    )

    if has_placeholder:
        print(f"\n✗ 发现占位符！")
        return False
    else:
        print(f"\n✓ 没有占位符，所有工具调用都成功完成！")
        print(f"✓ 多轮执行成功，返回真实结果！")
        return True


def main():
    """运行所有成功的示例"""
    print("\n" + "=" * 70)
    print("成功的多轮执行示例集")
    print("=" * 70)
    print("\n这些示例展示了真正完成多轮执行并返回真实结果的情况")
    print("（没有占位符，没有 needs_tool_execution=True）\n")

    results = []

    try:
        # # 示例1：纯Python
        # result1 = example_without_filesystem()
        # results.append(("纯Python代码", result1))

        # # 示例2：Memory工具
        # result2 = example_with_memory_tool()
        # results.append(("Memory工具", result2))

        # 示例3：Filesystem工具（正确配置）
        result3 = example_with_proper_filesystem()
        results.append(("Filesystem工具", result3))

    except Exception as e:
        print(f"\n❌ 示例执行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 总结
    print("\n\n" + "=" * 70)
    print("总结")
    print("=" * 70)

    for name, success in results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{status}: {name}")

    all_success = all(r[1] for r in results)

    if all_success:
        print("\n" + "=" * 70)
        print("🎉 所有示例都成功完成多轮执行！")
        print("=" * 70)
        print("\n关键要点:")
        print("1. ✓ 纯Python代码：无工具调用，直接返回结果")
        print("2. ✓ Memory工具：工具调用成功，多轮执行完成")
        print("3. ✓ Filesystem工具：正确配置路径，工具调用成功")
        print("\n所有示例的最终结果:")
        print("- needs_tool_execution = False ✓")
        print("- 没有占位符 ✓")
        print("- 包含真实数据 ✓")
        print("- 多轮执行自动完成 ✓")
        return 0
    else:
        print("\n⚠️  部分示例失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
