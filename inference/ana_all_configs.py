import json
import numpy as np
import os
import glob
import tiktoken
import csv
import argparse
import sys

# 初始化tokenizer
def get_tokenizer(model_name="gpt-4o"):
    """获取tokenizer"""
    try:
        return tiktoken.encoding_for_model(model_name)
    except:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens_tiktoken(text, tokenizer):
    """使用tiktoken计算token数"""
    if isinstance(text, str):
        try:
            return len(tokenizer.encode(text, disallowed_special=()))
        except Exception as e:
            print(f"Warning: tiktoken encoding failed: {e}")
            return len(text.split())
    return 0

def count_tokens_simple(text):
    """简单的token计算方法（按空格分词）"""
    if isinstance(text, str):
        return len(text.split())
    return 0

def count_characters(text):
    """计算字符数"""
    if isinstance(text, str):
        return len(text)
    return 0

def load_summary_file(base_dir):
    """加载summary文件，获取分组信息"""
    # 查找summary文件
    summary_files = glob.glob(os.path.join(base_dir, "summary-*.json"))
    
    if not summary_files:
        return None
    
    # 使用最新的summary文件
    summary_file = max(summary_files, key=os.path.getmtime)
    
    try:
        with open(summary_file, 'r') as f:
            summary_data = json.load(f)
        
        print(f"✅ 找到summary文件: {os.path.basename(summary_file)}")
        
        # 检查是否启用了分组
        group_by_seed = summary_data.get('group_by_seed', False)
        config_groups = summary_data.get('config_groups', None)
        
        if group_by_seed and config_groups:
            print(f"✅ 检测到配置分组（group_by_seed=True）")
            print(f"   共 {len(config_groups)} 个配置组")
            return {
                'group_by_seed': True,
                'config_groups': {int(k): v for k, v in config_groups.items()},
                'summary_data': summary_data
            }
        else:
            print(f"   未启用配置分组（group_by_seed=False 或无分组信息）")
            return {
                'group_by_seed': False,
                'config_groups': None,
                'summary_data': summary_data
            }
    except Exception as e:
        print(f"⚠️  读取summary文件失败: {e}")
        return None

def extract_text_from_content(content):
    """从Claude Agent SDK的content格式中提取文本"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "TextBlock":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "text":
                    # ToolResultBlock内部的text格式: {"type": "text", "text": "..."}
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "ToolUseBlock":
                    # 将tool use转换为JSON字符串来计算tokens
                    try:
                        text_parts.append(json.dumps(item, ensure_ascii=False))
                    except:
                        pass
                elif item.get("type") == "ToolResultBlock":
                    # Tool result的内容
                    result_content = item.get("content", "")
                    if isinstance(result_content, str):
                        text_parts.append(result_content)
                    elif isinstance(result_content, list):
                        # 递归处理嵌套的content
                        text_parts.append(extract_text_from_content(result_content))
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts)
    return ""

def analyze_config_file(json_path, tokenizer):
    """分析单个config文件（单次run）"""
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        stats = {
            'total_messages': 0,
            'tool_calls': 0,
            'user_messages': 0,
            'assistant_messages': 0,
            'tool_content_chars': 0,
            'tool_content_words': 0,
            'tool_content_tokens': 0,
            'all_content_chars': 0,
            'all_content_words': 0,
            'all_content_tokens': 0,
            'tool_content_list': [],
            'api_total_tokens': 0,  # API调用的总tokens
            'api_prompt_tokens': 0,
            'api_completion_tokens': 0,
            'api_total_cost': 0.0,  # API调用的总cost
            'accuracy': 0.0,  # 准确度
            'total_steps': 0,  # 总步数
            'completed': False,  # 是否完成
            'has_context_length_error': False,  # 是否出现context length error
            'proper_ending': False,  # 是否正常结束（accuracy=1.0 或 最后的assistant message包含claim_done_claim_done）
            'reset_count': 0,  # reset事件次数
            'summary_count': 0,  # summary事件次数
            'trim_count': 0,  # trim事件次数
            'thinking_reset_count': 0,  # thinking_reset事件次数
            'tokens_before_each_assistant': [],  # 记录每次assistant回复前的累计tokens
            'trimmed_tokens_total': 0,  # 被trim掉的tokens总数
            'reset_tokens_total': 0,  # 被reset掉的tokens总数
            'thinking_reset_tokens_total': 0,  # 被thinking_reset掉的tokens总数
            'summary_tokens_total': 0,  # 被summary掉的tokens总数
            'has_error': False,  # 是否包含error类型的action（用于排除token统计）
        }
        
        # 检查steps中是否有error类型的action
        if "steps" in data:
            for step in data["steps"]:
                if "action" in step and isinstance(step["action"], dict):
                    if step["action"].get("type") == "error":
                        stats['has_error'] = True
                        break

        # 提取accuracy, total_steps, completed
        # 使用 or 确保 None 值被转换为默认值
        stats['accuracy'] = data.get('accuracy', 0.0) or 0.0
        stats['total_steps'] = data.get('total_steps', 0) or 0
        stats['completed'] = data.get('completed', False) or False

        # 统计reset、summary、trim和thinking_reset事件次数（兼容三种格式）
        # 1. 旧格式：reset_events, summary_events等
        stats['reset_count'] = len(data.get('reset_events', []))
        stats['summary_count'] = len(data.get('summary_events', []))
        stats['trim_count'] = len(data.get('trim_events', []))
        stats['thinking_reset_count'] = len(data.get('thinking_reset_events', []))

        # 计算被trim掉的tokens总数
        trim_events = data.get('trim_events', [])
        for trim_event in trim_events:
            trim_info = trim_event.get('trim_info', {})
            original_tokens = trim_info.get('original_total_tokens', 0)
            trimmed_tokens = trim_info.get('trimmed_total_tokens', 0)
            stats['trimmed_tokens_total'] += (original_tokens - trimmed_tokens)

        # 计算被reset掉的tokens总数
        reset_events = data.get('reset_events', [])
        
        # 构建step到usage的映射，用于最精准的估算
        step_usage_map = {}
        if "steps" in data:
            for step in data["steps"]:
                step_info = step.get("info", {})
                tool_use_counter = step_info.get("tool_use_counter", 0)
                if tool_use_counter > 0:
                    usage = step.get("action", {}).get("raw_response", {}).get("usage", {})
                    step_usage_map[tool_use_counter] = usage
        
        for reset_event in reset_events:
            tokens_before = reset_event.get('tokens_before_reset', 0)
            tokens_after = reset_event.get('tokens_after_reset', 0)
            # 兼容旧格式：如果没有tokens_before_reset，尝试使用total_tokens
            if tokens_before == 0:
                tokens_before = reset_event.get('total_tokens', 0)
            
            # 如果没有tokens_after_reset，尝试估算
            if tokens_after == 0 and tokens_before > 0:
                # 最精准方法: 使用reset后下一步的prompt_tokens
                reset_step = reset_event.get('step', 0)
                next_step_num = reset_step + 1
                if next_step_num in step_usage_map:
                    next_usage = step_usage_map[next_step_num]
                    tokens_after = next_usage.get('prompt_tokens', 0)
                
                # 如果最精准方法失败，使用消息数量比例估算
                if tokens_after == 0:
                    messages_before = reset_event.get('messages_before_count', 0)
                    messages_after = reset_event.get('messages_after_count', 0)
                    if messages_before > 0 and messages_after > 0:
                        tokens_after = int(tokens_before * (messages_after / messages_before))
                    else:
                        # 备选: 基于移除的消息对比例估算
                        reset_info = reset_event.get('reset_info', {})
                        num_pairs_removed = reset_info.get('num_pairs_removed', 0)
                        total_pairs = reset_info.get('total_pairs', 0)
                        if total_pairs > 0 and num_pairs_removed > 0:
                            tokens_after = int(tokens_before * (1 - num_pairs_removed / total_pairs))
            
            if tokens_before and tokens_after:
                stats['reset_tokens_total'] += (tokens_before - tokens_after)

        # 计算被thinking_reset掉的tokens总数
        thinking_reset_events = data.get('thinking_reset_events', [])
        for thinking_reset_event in thinking_reset_events:
            tokens_before = thinking_reset_event.get('tokens_before_reset', 0)
            tokens_after = thinking_reset_event.get('tokens_after_reset', 0)
            # 兼容旧格式：如果没有tokens_before_reset，尝试使用total_tokens
            if tokens_before == 0:
                tokens_before = thinking_reset_event.get('total_tokens', 0)
            
            # 如果没有tokens_after_reset，尝试估算
            if tokens_after == 0 and tokens_before > 0:
                # 最精准方法: 使用thinking_reset后下一步的prompt_tokens
                reset_step = thinking_reset_event.get('step', 0)
                next_step_num = reset_step + 1
                if next_step_num in step_usage_map:
                    next_usage = step_usage_map[next_step_num]
                    tokens_after = next_usage.get('prompt_tokens', 0)
                
                # 如果最精准方法失败，使用thinking_reset_info估算
                if tokens_after == 0:
                    thinking_reset_info = thinking_reset_event.get('thinking_reset_info', {})
                    total_reasoning_length = thinking_reset_info.get('total_reasoning_content_length', 0)
                    # 粗略估算: 1 char ≈ 0.25 tokens (英文)
                    if total_reasoning_length > 0:
                        estimated_reasoning_tokens = int(total_reasoning_length * 0.25)
                        tokens_after = tokens_before - estimated_reasoning_tokens
            
            if tokens_before and tokens_after:
                stats['thinking_reset_tokens_total'] += (tokens_before - tokens_after)

        # 计算被summary掉的tokens总数
        summary_events = data.get('summary_events', [])
        for summary_event in summary_events:
            tokens_before = summary_event.get('tokens_before_summary', 0)
            tokens_after = summary_event.get('tokens_after_summary', 0)
            # 兼容旧格式：如果没有tokens_before_summary，尝试使用total_tokens
            if tokens_before == 0:
                tokens_before = summary_event.get('total_tokens', 0)
            
            # 如果没有tokens_after_summary，尝试估算
            if tokens_after == 0 and tokens_before > 0:
                # 最精准方法: 使用summary后下一步的prompt_tokens
                summary_step = summary_event.get('step', 0)
                next_step_num = summary_step + 1
                if next_step_num in step_usage_map:
                    next_usage = step_usage_map[next_step_num]
                    tokens_after = next_usage.get('prompt_tokens', 0)
                
                # 如果最精准方法失败，使用消息数量比例估算
                if tokens_after == 0:
                    messages_before = summary_event.get('messages_before_count', 0)
                    messages_after = summary_event.get('messages_after_count', 0)
                    if messages_before > 0 and messages_after > 0:
                        tokens_after = int(tokens_before * (messages_after / messages_before))
            
            if tokens_before and tokens_after:
                stats['summary_tokens_total'] += (tokens_before - tokens_after)

        # 2. Claude Agent SDK格式：clear_tool_results_events和compact_events
        stats['reset_count'] += len(data.get('clear_tool_results_events', []))
        stats['summary_count'] += len(data.get('compact_events', []))

        # 3. run_claude_api.py格式：从context_management_events中提取
        if 'context_management_events' in data:
            for event in data['context_management_events']:
                event_type = event.get('type', '')
                if 'clear_tool_uses' in event_type:
                    stats['reset_count'] += 1
                elif 'clear_thinking' in event_type:
                    stats['thinking_reset_count'] += 1

        # 先根据accuracy判断：如果accuracy是1.0，默认算正常结束
        if stats['accuracy'] == 1.0:
            stats['proper_ending'] = True

        # 提取API usage信息 - 兼容三种格式
        # 优先检查run_claude_api.py格式（total_usage字段）
        if "total_usage" in data:
            # run_claude_api.py格式：直接从total_usage提取
            total_usage = data["total_usage"]
            stats['api_prompt_tokens'] = total_usage.get("input_tokens", 0)
            stats['api_completion_tokens'] = total_usage.get("output_tokens", 0)
            stats['api_total_cost'] = total_usage.get("total_cost_usd", 0.0) or 0.0

            # api_total_tokens从最后一步的usage_tracking中提取（包含所有token类型）
            # 公式: input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens
            if "usage_tracking" in data and len(data["usage_tracking"]) > 0:
                last_step = data["usage_tracking"][-1]
                stats['api_total_tokens'] = (
                    last_step.get("input_tokens", 0) +
                    last_step.get("cache_creation_input_tokens", 0) +
                    last_step.get("cache_read_input_tokens", 0) +
                    last_step.get("output_tokens", 0)
                )
            else:
                # 如果没有usage_tracking，回退到简单计算
                stats['api_total_tokens'] = stats['api_prompt_tokens'] + stats['api_completion_tokens']

        elif "steps" in data and len(data["steps"]) > 0:
            try:
                # 检测是否为Claude Agent SDK格式
                first_step = data["steps"][0]
                is_claude_agent_format = "message" in first_step and "message_type" in first_step

                if is_claude_agent_format:
                    # Claude Agent SDK格式：从usage_summary或steps中的usage字段提取
                    if "usage_summary" in data:
                        usage_summary = data["usage_summary"]
                        # 总input tokens = input_tokens + cache_read + cache_creation
                        input_tokens = usage_summary.get("total_input_tokens", 0)
                        cache_read = usage_summary.get("cache_read_input_tokens", 0)
                        cache_creation = usage_summary.get("cache_creation_input_tokens", 0)
                        output_tokens = usage_summary.get("total_output_tokens", 0)

                        stats['api_prompt_tokens'] = input_tokens + cache_read + cache_creation
                        stats['api_completion_tokens'] = output_tokens
                        stats['api_total_tokens'] = stats['api_prompt_tokens'] + stats['api_completion_tokens']
                        stats['api_total_cost'] = usage_summary.get("total_cost_usd", 0.0) or 0.0
                    else:
                        # 从steps中累加usage
                        for step in data["steps"]:
                            if "usage" in step:
                                usage = step["usage"]
                                stats['api_prompt_tokens'] += usage.get("input_tokens", 0)
                                stats['api_completion_tokens'] += usage.get("output_tokens", 0)
                        stats['api_total_tokens'] = stats['api_prompt_tokens'] + stats['api_completion_tokens']
                else:
                    # 原始格式：从action.raw_response.usage中提取
                    for step in data["steps"]:
                        if "action" in step and "raw_response" in step["action"]:
                            usage = step["action"]["raw_response"].get("usage", {})

                            # 累加tokens（从每个step获取）
                            step_total_tokens = usage.get("total_tokens", 0)
                            step_prompt_tokens = usage.get("prompt_tokens", 0)
                            step_completion_tokens = usage.get("completion_tokens", 0)

                            # 对于tokens，只使用最后一个有效的值（因为API可能返回累积值）
                            if step_total_tokens > stats['api_total_tokens']:
                                stats['api_total_tokens'] = step_total_tokens
                                stats['api_prompt_tokens'] = step_prompt_tokens
                                stats['api_completion_tokens'] = step_completion_tokens

                            # 累加cost（每个step的cost需要相加）
                            step_cost = usage.get("cost", 0.0)
                            if step_cost > 0:
                                stats['api_total_cost'] += step_cost

            except Exception as e:
                print(f"  Warning: 无法提取usage信息: {e}")
        
        # 统计消息 - 兼容三种格式
        messages = []
        is_claude_agent_format = False
        is_run_claude_api_format = False

        # 检测格式类型
        # 1. 优先检测run_claude_api.py格式（有full_messages_history或claude_messages）
        if "full_messages_history" in data and data["full_messages_history"]:
            is_run_claude_api_format = True
        # 2. 检测是否为Claude Agent SDK格式
        elif "steps" in data and len(data["steps"]) > 0:
            first_step = data["steps"][0]
            is_claude_agent_format = "message" in first_step and "message_type" in first_step

        if is_run_claude_api_format:
            # run_claude_api.py格式：使用full_messages_history
            # full_messages_history包含完整的消息历史
            messages = data.get("full_messages_history", [])

            # 如果full_messages_history为空，尝试使用claude_messages
            if not messages and "claude_messages" in data:
                messages = data["claude_messages"]

        elif is_claude_agent_format:
            # Claude Agent SDK格式：从steps中提取messages
            # 将user_prompt转换为user message
            if "user_prompt" in data:
                messages.append({
                    "role": "user",
                    "content": data["user_prompt"]
                })

            # 从steps中提取assistant/tool messages
            for step in data["steps"]:
                message = step.get("message", {})
                message_type = step.get("message_type", "")

                if message_type == "AssistantMessage":
                    messages.append({
                        "role": "assistant",
                        "content": message.get("content", []),
                        "tool_calls": []  # 从content中的ToolUseBlock提取
                    })
                elif message_type == "UserMessage":
                    # UserMessage可能包含ToolResultBlock
                    content = message.get("content", [])
                    # 检查是否包含ToolResultBlock
                    has_tool_result = False
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "ToolResultBlock":
                                has_tool_result = True
                                break

                    if has_tool_result:
                        # 这是tool result message
                        messages.append({
                            "role": "tool",
                            "content": content
                        })
                    else:
                        # 这是普通user message
                        messages.append({
                            "role": "user",
                            "content": content
                        })
        else:
            # 原始格式：使用full_messages_history或final_messages
            if "full_messages_history" in data:
                full_history = data["full_messages_history"]

                # 检查第一个消息是否为user，如果不是，需要从final_messages中取第一个user消息
                if full_history and len(full_history) > 0:
                    first_message = full_history[0]
                    if first_message.get("role") != "user":
                        # 从final_messages中找第一个user消息
                        if "final_messages" in data:
                            final_messages = data["final_messages"]
                            for msg in final_messages:
                                if msg.get("role") == "user":
                                    # 将第一个user消息加入到messages开头
                                    messages.append(msg)
                                    break
                        # 然后添加full_messages_history的所有消息
                        messages.extend(full_history)
                    else:
                        # 如果第一个消息就是user，直接使用full_messages_history
                        messages = full_history
                else:
                    messages = full_history
            elif "final_messages" in data:
                # 如果没有full_messages_history，回退到使用final_messages
                messages = data["final_messages"]
        
        if messages:
            stats['total_messages'] = len(messages)
            
            for item in messages:
                role = item.get("role", "")
                
                # 如果遇到assistant消息，记录当前累计的tokens（在处理这条assistant消息之前）
                if role == "assistant":
                    stats['tokens_before_each_assistant'].append({
                        'assistant_index': stats['assistant_messages'],  # 第几个assistant消息
                        'cumulative_tokens': stats['all_content_tokens']  # 累计tokens数
                    })
                
                # 收集该消息的所有内容用于统计
                all_text_parts = []
                
                # 处理不同role的内容
                if role == "tool":
                    stats['tool_calls'] += 1
                    content = item.get("content", "")
                    # 使用extract_text_from_content处理content
                    content_text = extract_text_from_content(content)
                    if content_text:
                        all_text_parts.append(content_text)
                        # 单独统计tool content
                        char_count = count_characters(content_text)
                        word_count = count_tokens_simple(content_text)
                        token_count = count_tokens_tiktoken(content_text, tokenizer)

                        stats['tool_content_chars'] += char_count
                        stats['tool_content_words'] += word_count
                        stats['tool_content_tokens'] += token_count
                        stats['tool_content_list'].append({
                            'chars': char_count,
                            'words': word_count,
                            'tokens': token_count
                        })

                elif role == "user":
                    stats['user_messages'] += 1
                    # Claude API格式: user消息的content可能包含tool_result
                    content = item.get("content", "")
                    if isinstance(content, list):
                        has_tool_result = False
                        for content_item in content:
                            if isinstance(content_item, dict) and content_item.get("type") == "tool_result":
                                has_tool_result = True
                                # 统计tool_result作为tool调用（Claude格式）
                                stats['tool_calls'] += 1
                                tool_result_content = content_item.get("content", "")
                                if tool_result_content:
                                    tool_content_text = extract_text_from_content(tool_result_content)
                                    if tool_content_text:
                                        all_text_parts.append(tool_content_text)
                                        # 单独统计tool content
                                        char_count = count_characters(tool_content_text)
                                        word_count = count_tokens_simple(tool_content_text)
                                        token_count = count_tokens_tiktoken(tool_content_text, tokenizer)

                                        stats['tool_content_chars'] += char_count
                                        stats['tool_content_words'] += word_count
                                        stats['tool_content_tokens'] += token_count
                                        stats['tool_content_list'].append({
                                            'chars': char_count,
                                            'words': word_count,
                                            'tokens': token_count
                                        })
                            else:
                                # 非tool_result的内容（如普通text）
                                content_text = extract_text_from_content(content_item)
                                if content_text:
                                    all_text_parts.append(content_text)
                    else:
                        # content是字符串的情况
                        content_text = extract_text_from_content(content)
                        if content_text:
                            all_text_parts.append(content_text)

                elif role == "assistant":
                    stats['assistant_messages'] += 1
                    # assistant需要统计: content, reasoning_content, tool_calls
                    content = item.get("content", "")
                    content_text = extract_text_from_content(content)
                    if content_text:
                        all_text_parts.append(content_text)

                    reasoning_content = item.get("reasoning_content", "")
                    if reasoning_content:
                        all_text_parts.append(extract_text_from_content(reasoning_content))

                    tool_calls = item.get("tool_calls", [])
                    if tool_calls:
                        # 将tool_calls转换为JSON字符串来计算tokens
                        try:
                            tool_calls_str = json.dumps(tool_calls, ensure_ascii=False)
                            all_text_parts.append(tool_calls_str)
                        except:
                            pass

                else:
                    # 其他role，统计content
                    content = item.get("content", "")
                    content_text = extract_text_from_content(content)
                    if content_text:
                        all_text_parts.append(content_text)
                
                # 统计该消息的总内容到all_content
                if all_text_parts:
                    combined_text = "\n".join(all_text_parts)
                    char_count = count_characters(combined_text)
                    word_count = count_tokens_simple(combined_text)
                    token_count = count_tokens_tiktoken(combined_text, tokenizer)
                    
                    stats['all_content_chars'] += char_count
                    stats['all_content_words'] += word_count
                    stats['all_content_tokens'] += token_count
        
        # 检查最后一条消息是否包含context length error和是否正常结束
        if messages and len(messages) > 0:
            last_message = messages[-1]
            if last_message.get("role") == "assistant":
                content = last_message.get("content", "")
                content_text = extract_text_from_content(content)
                # 检查context length error
                if "maximum context length" in content_text or "context length" in content_text.lower():
                    stats['has_context_length_error'] = True

                # 额外检查是否有claim_done_claim_done的tool call（即使accuracy不是1.0也可能正常结束）
                tool_calls = last_message.get("tool_calls", [])
                if tool_calls:
                    for tool_call in tool_calls:
                        if isinstance(tool_call, dict):
                            function_info = tool_call.get("function", {})
                            if isinstance(function_info, dict):
                                function_name = function_info.get("name", "")
                                if function_name == "claim_done_claim_done":
                                    stats['proper_ending'] = True
                                    break

                # Claude Agent SDK格式: 检查content中的ToolUseBlock
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "ToolUseBlock":
                            tool_name = item.get("name", "")
                            if "claim_done" in tool_name:
                                stats['proper_ending'] = True
                                break
        
        return stats
    except Exception as e:
        print(f"Error processing {json_path}: {e}")
        return None

# 解析命令行参数
parser = argparse.ArgumentParser(description='分析benchmark配置文件的统计信息')
parser.add_argument('--input', '-i', type=str, required=False,
                    help='输入目录路径（包含config_*子目录的benchmark目录）')
parser.add_argument('--output', '-o', type=str, required=False,
                    help='输出目录路径（保存分析结果的目录，默认为输入目录的父目录）')
args = parser.parse_args()

def analyze_config_dir(config_path, tokenizer):
    """分析整个config目录（所有run）"""
    # 找到该config下的所有JSON文件
    json_files = sorted(glob.glob(os.path.join(config_path, "*.json")))
    
    # 过滤掉error文件（文件名中包含 "-error-" 的文件是中间错误状态，不应计入统计）
    original_count = len(json_files)
    json_files = [f for f in json_files if '-error-' not in os.path.basename(f)]
    filtered_count = original_count - len(json_files)
    if filtered_count > 0:
        print(f"  已过滤 {filtered_count} 个error文件")
    
    if not json_files:
        print(f"  Warning: 没有找到JSON文件")
        return None
    
    # 存储所有run的统计信息
    all_runs = []
    
    for json_path in json_files:
        stats = analyze_config_file(json_path, tokenizer)
        if stats:
            all_runs.append(stats)
    
    if not all_runs:
        return None
    
    # 过滤掉有error的runs用于token统计
    valid_runs_for_tokens = [r for r in all_runs if not r.get('has_error', False)]
    error_runs_count = len(all_runs) - len(valid_runs_for_tokens)
    if error_runs_count > 0:
        print(f"  ⚠️  跳过 {error_runs_count} 个含error的run的token统计")
    
    # 汇总统计
    config_summary = {
        'total_runs': len(all_runs),
        'success_runs': sum(1 for r in all_runs if r['completed']),
        'error_runs': sum(1 for r in all_runs if not r['completed']),
        'error_action_runs': error_runs_count,  # 包含error action的run数量
        'valid_runs_for_tokens': len(valid_runs_for_tokens),  # 用于token统计的有效run数量
        'context_length_error_runs': sum(1 for r in all_runs if r.get('has_context_length_error', False)),
        'context_length_error_rate': sum(1 for r in all_runs if r.get('has_context_length_error', False)) / len(all_runs) if len(all_runs) > 0 else 0,
        'improper_ending_runs': sum(1 for r in all_runs if not r.get('proper_ending', False)),
        'improper_ending_rate': sum(1 for r in all_runs if not r.get('proper_ending', False)) / len(all_runs) if len(all_runs) > 0 else 0,
        
        # accuracy和steps统计（使用所有runs）
        'accuracies': [r['accuracy'] for r in all_runs],
        'steps': [r['total_steps'] for r in all_runs],
        'avg_accuracy': sum(r['accuracy'] for r in all_runs) / len(all_runs),
        'avg_steps': sum(r['total_steps'] for r in all_runs) / len(all_runs),
        
        # reset、summary、trim和thinking_reset事件统计（使用所有runs）
        'total_reset_count': sum(r['reset_count'] for r in all_runs),
        'total_summary_count': sum(r['summary_count'] for r in all_runs),
        'total_trim_count': sum(r['trim_count'] for r in all_runs),
        'total_thinking_reset_count': sum(r['thinking_reset_count'] for r in all_runs),
        'avg_reset_count': sum(r['reset_count'] for r in all_runs) / len(all_runs),
        'avg_summary_count': sum(r['summary_count'] for r in all_runs) / len(all_runs),
        'avg_trim_count': sum(r['trim_count'] for r in all_runs) / len(all_runs),
        'avg_thinking_reset_count': sum(r['thinking_reset_count'] for r in all_runs) / len(all_runs),
        
        # token统计（只使用没有error的runs）
        'total_tool_calls': sum(r['tool_calls'] for r in valid_runs_for_tokens),
        'total_tool_content_tokens': sum(r['tool_content_tokens'] for r in valid_runs_for_tokens),
        'total_all_content_tokens': sum(r['all_content_tokens'] for r in valid_runs_for_tokens),
        'total_api_tokens': sum(r['api_total_tokens'] for r in valid_runs_for_tokens),
        'total_api_prompt_tokens': sum(r['api_prompt_tokens'] for r in valid_runs_for_tokens),
        'total_api_completion_tokens': sum(r['api_completion_tokens'] for r in valid_runs_for_tokens),
        'total_api_cost': sum(r['api_total_cost'] for r in valid_runs_for_tokens),
        'total_trimmed_tokens': sum(r['trimmed_tokens_total'] for r in valid_runs_for_tokens),  # 被trim掉的tokens总数
        'total_reset_tokens': sum(r['reset_tokens_total'] for r in valid_runs_for_tokens),  # 被reset掉的tokens总数
        'total_thinking_reset_tokens': sum(r['thinking_reset_tokens_total'] for r in valid_runs_for_tokens),  # 被thinking_reset掉的tokens总数
        'total_summary_tokens': sum(r['summary_tokens_total'] for r in valid_runs_for_tokens),  # 被summary掉的tokens总数
        'total_api_tokens_with_trimmed': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] for r in valid_runs_for_tokens),  # 包含被trim掉的tokens
        'total_api_tokens_with_trimmed_and_reset': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] + r['reset_tokens_total'] for r in valid_runs_for_tokens),  # 包含被trim和reset掉的tokens
        'total_api_tokens_with_all_removed': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] + r['reset_tokens_total'] + r['thinking_reset_tokens_total'] + r['summary_tokens_total'] for r in valid_runs_for_tokens),  # 包含被trim、reset、thinking_reset和summary掉的tokens
        
        # 平均每个run的统计（只使用没有error的runs）
        'avg_tool_calls': sum(r['tool_calls'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_tool_content_tokens': sum(r['tool_content_tokens'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_all_content_tokens': sum(r['all_content_tokens'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_api_tokens': sum(r['api_total_tokens'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_api_prompt_tokens': sum(r['api_prompt_tokens'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_api_completion_tokens': sum(r['api_completion_tokens'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_api_cost': sum(r['api_total_cost'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,
        'avg_trimmed_tokens': sum(r['trimmed_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 平均每个run被trim掉的tokens
        'avg_reset_tokens': sum(r['reset_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 平均每个run被reset掉的tokens
        'avg_thinking_reset_tokens': sum(r['thinking_reset_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 平均每个run被thinking_reset掉的tokens
        'avg_summary_tokens': sum(r['summary_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 平均每个run被summary掉的tokens
        'avg_api_tokens_with_trimmed': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 包含被trim掉的平均tokens
        'avg_api_tokens_with_trimmed_and_reset': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] + r['reset_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 包含被trim和reset掉的平均tokens
        'avg_api_tokens_with_all_removed': sum(r['api_total_tokens'] + r['trimmed_tokens_total'] + r['reset_tokens_total'] + r['thinking_reset_tokens_total'] + r['summary_tokens_total'] for r in valid_runs_for_tokens) / len(valid_runs_for_tokens) if len(valid_runs_for_tokens) > 0 else 0,  # 包含被trim、reset、thinking_reset和summary掉的平均tokens
        
        # 所有run的详细信息
        'runs': all_runs
    }
    
    # 计算平均每个tool call的tokens
    if config_summary['total_tool_calls'] > 0:
        config_summary['avg_tokens_per_tool_call'] = config_summary['total_tool_content_tokens'] / config_summary['total_tool_calls']
    else:
        config_summary['avg_tokens_per_tool_call'] = 0
    
    return config_summary

# 主目录路径
if args.input:
    base_dir = args.input
else:
    print("错误: 必须提供 --input 参数指定输入目录")
    print("使用方法: python ana_all_configs.py --input /path/to/benchmark/dir")
    sys.exit(1)

# 验证输入目录是否存在
if not os.path.exists(base_dir):
    print(f"错误: 输入目录不存在: {base_dir}")
    sys.exit(1)

if not os.path.isdir(base_dir):
    print(f"错误: 输入路径不是目录: {base_dir}")
    sys.exit(1)

# 输出目录路径
if args.output:
    output_dir = args.output
else:
    # 默认为输入目录的父目录
    output_dir = os.path.dirname(base_dir)

# 创建输出目录（如果不存在）
os.makedirs(output_dir, exist_ok=True)

print(f"输入目录: {base_dir}")
print(f"输出目录: {output_dir}")
print("=" * 100)

# 尝试加载summary文件获取分组信息
print("\n正在检查分组信息...")
summary_info = load_summary_file(base_dir)
group_by_seed = False
config_groups = None

if summary_info:
    group_by_seed = summary_info.get('group_by_seed', False)
    config_groups = summary_info.get('config_groups', None)
    
    if group_by_seed and config_groups:
        print("\n📊 分组统计模式")
        print(f"   配置组数量: {len(config_groups)}")
        for group_id, config_indices in sorted(config_groups.items()):
            print(f"   Group {group_id}: 包含 config_{config_indices} (共{len(config_indices)}个runs)")
    else:
        print("\n📊 独立配置模式")
else:
    print("   未找到summary文件，使用独立配置模式")

print("=" * 100)

# 初始化tokenizer
print("\n正在初始化tokenizer...")
tokenizer = get_tokenizer()

# 存储所有config的统计结果
all_configs_stats = {}

# 遍历所有config目录
config_dirs = sorted([d for d in os.listdir(base_dir) if d.startswith('config_')])

print(f"\n找到 {len(config_dirs)} 个配置目录\n")
print("=" * 100)

for config_dir in config_dirs:
    config_path = os.path.join(base_dir, config_dir)
    
    # 提取config_id
    config_id = int(config_dir.split('_')[1])
    
    # 如果是分组模式，显示分组信息
    group_info = ""
    if group_by_seed and config_groups:
        # 检查这个config_id属于哪个组
        for group_id, member_configs in config_groups.items():
            if config_id in member_configs:
                group_info = f" [Group {group_id}]"
                if len(member_configs) > 1:
                    group_info += f" (与 config_{[c for c in member_configs if c != config_id]} 同组)"
                break
    
    print(f"\n正在分析 {config_dir}{group_info}...")
    
    stats = analyze_config_dir(config_path, tokenizer)
    
    if stats:
        all_configs_stats[config_dir] = stats
        
        print(f"  总Run数: {stats['total_runs']}")
        print(f"  成功Run数: {stats['success_runs']}")
        print(f"  失败Run数: {stats['error_runs']}")
        print(f"  Context Length Error数: {stats['context_length_error_runs']} ({stats['context_length_error_rate']*100:.1f}%)")
        print(f"  非正常结束数: {stats['improper_ending_runs']} ({stats['improper_ending_rate']*100:.1f}%)")
        print(f"  === 任务指标 ===")
        print(f"  平均准确度: {stats['avg_accuracy']:.4f}")
        print(f"  平均步数: {stats['avg_steps']:.2f}")
        print(f"  准确度列表: {stats['accuracies']}")
        print(f"  步数列表: {stats['steps']}")
        print(f"  === Reset & Summary & Trim & Thinking Reset统计 ===")
        print(f"  总Reset次数: {stats['total_reset_count']}")
        print(f"  总Summary次数: {stats['total_summary_count']}")
        print(f"  总Trim次数: {stats['total_trim_count']}")
        print(f"  总Thinking Reset次数: {stats['total_thinking_reset_count']}")
        print(f"  平均每个Run的Reset次数: {stats['avg_reset_count']:.2f}")
        print(f"  平均每个Run的Summary次数: {stats['avg_summary_count']:.2f}")
        print(f"  平均每个Run的Trim次数: {stats['avg_trim_count']:.2f}")
        print(f"  平均每个Run的Thinking Reset次数: {stats['avg_thinking_reset_count']:.2f}")
        print(f"  === API Usage（所有run总和） ===")
        print(f"  总API Cost: ${stats['total_api_cost']:.6f} 💰💰💰")
        print(f"  平均每个Run的API Cost: ${stats['avg_api_cost']:.6f}")
        print(f"  总API Tokens: {stats['total_api_tokens']:,} ⭐⭐⭐")
        print(f"  平均每个Run的API Tokens: {stats['avg_api_tokens']:,.2f}")
        print(f"  总API Prompt Tokens: {stats['total_api_prompt_tokens']:,}")
        print(f"  总API Completion Tokens: {stats['total_api_completion_tokens']:,}")
        print(f"  === Tool Content统计（所有run总和） ===")
        print(f"  总Tool调用数: {stats['total_tool_calls']}")
        print(f"  总Tool Content Tokens: {stats['total_tool_content_tokens']:,}")
        print(f"  平均每个Tool Call的Tokens: {stats['avg_tokens_per_tool_call']:.2f}")
        print(f"  总所有Content Tokens: {stats['total_all_content_tokens']:,}")
        
        # 显示tokens变化趋势统计
        if stats['runs'] and any(run.get('tokens_before_each_assistant') for run in stats['runs']):
            all_progressions = []
            for run in stats['runs']:
                progression = run.get('tokens_before_each_assistant', [])
                if progression and len(progression) > 0:
                    all_progressions.append(progression)
            
            if all_progressions:
                print(f"  === Tokens变化趋势 ===")
                # 计算平均每个run的assistant数量
                avg_assistants = sum(len(p) for p in all_progressions) / len(all_progressions)
                print(f"  平均每个Run的Assistant回复数: {avg_assistants:.1f}")
                
                # 如果所有run的assistant数量相同，可以显示平均tokens变化
                if len(set(len(p) for p in all_progressions)) == 1:
                    num_steps = len(all_progressions[0])
                    print(f"  平均Tokens增长轨迹 (在每次assistant回复前):")
                    for step in range(num_steps):
                        avg_tokens = sum(p[step]['cumulative_tokens'] for p in all_progressions) / len(all_progressions)
                        print(f"    Assistant #{step}: {avg_tokens:,.0f} tokens")

print("\n" + "=" * 100)
print("\n=== 汇总统计 ===\n")

# 显示分组模式信息
if group_by_seed and config_groups:
    print(f"📊 分组统计模式")
    print(f"   实际配置组数: {len(config_groups)}")
    print(f"   配置目录总数: {len(config_dirs)}")
    print(f"\n配置组详情:")
    for group_id, member_configs in sorted(config_groups.items()):
        config_names = [f"config_{c}" for c in member_configs]
        print(f"   Group {group_id}: {', '.join(config_names)} (共{len(member_configs)}个runs)")
    print()
else:
    print(f"📊 独立配置模式")
    print(f"   配置总数: {len(config_dirs)}\n")

print("=" * 50)

# 汇总统计
total_runs = sum(s['total_runs'] for s in all_configs_stats.values())
total_success = sum(s['success_runs'] for s in all_configs_stats.values())
total_error = sum(s['error_runs'] for s in all_configs_stats.values())
total_context_length_errors = sum(s['context_length_error_runs'] for s in all_configs_stats.values())
total_improper_endings = sum(s['improper_ending_runs'] for s in all_configs_stats.values())
total_reset_events = sum(s['total_reset_count'] for s in all_configs_stats.values())
total_summary_events = sum(s['total_summary_count'] for s in all_configs_stats.values())
total_trim_events = sum(s['total_trim_count'] for s in all_configs_stats.values())
total_thinking_reset_events = sum(s['total_thinking_reset_count'] for s in all_configs_stats.values())

total_tool_calls = sum(s['total_tool_calls'] for s in all_configs_stats.values())
total_tool_tokens = sum(s['total_tool_content_tokens'] for s in all_configs_stats.values())
total_all_tokens = sum(s['total_all_content_tokens'] for s in all_configs_stats.values())
total_api_tokens = sum(s['total_api_tokens'] for s in all_configs_stats.values())
total_api_prompt_tokens = sum(s['total_api_prompt_tokens'] for s in all_configs_stats.values())
total_api_completion_tokens = sum(s['total_api_completion_tokens'] for s in all_configs_stats.values())
total_api_cost = sum(s['total_api_cost'] for s in all_configs_stats.values())
total_trimmed_tokens = sum(s['total_trimmed_tokens'] for s in all_configs_stats.values())
total_reset_tokens = sum(s['total_reset_tokens'] for s in all_configs_stats.values())
total_thinking_reset_tokens = sum(s['total_thinking_reset_tokens'] for s in all_configs_stats.values())
total_summary_tokens = sum(s['total_summary_tokens'] for s in all_configs_stats.values())
total_api_tokens_with_trimmed = sum(s['total_api_tokens_with_trimmed'] for s in all_configs_stats.values())
total_api_tokens_with_trimmed_and_reset = sum(s['total_api_tokens_with_trimmed_and_reset'] for s in all_configs_stats.values())
total_api_tokens_with_all_removed = sum(s['total_api_tokens_with_all_removed'] for s in all_configs_stats.values())

# 收集各config的统计列表
avg_accuracy_list = [s['avg_accuracy'] for s in all_configs_stats.values()]
avg_steps_list = [s['avg_steps'] for s in all_configs_stats.values()]
tool_tokens_list = [s['total_tool_content_tokens'] for s in all_configs_stats.values()]
all_tokens_list = [s['total_all_content_tokens'] for s in all_configs_stats.values()]
avg_tokens_per_call_list = [s['avg_tokens_per_tool_call'] for s in all_configs_stats.values()]
api_tokens_list = [s['total_api_tokens'] for s in all_configs_stats.values()]
api_prompt_tokens_list = [s['total_api_prompt_tokens'] for s in all_configs_stats.values()]
api_completion_tokens_list = [s['total_api_completion_tokens'] for s in all_configs_stats.values()]
avg_api_tokens_per_run_list = [s['avg_api_tokens'] for s in all_configs_stats.values()]
api_cost_list = [s['total_api_cost'] for s in all_configs_stats.values()]
avg_api_cost_per_run_list = [s['avg_api_cost'] for s in all_configs_stats.values()]
trimmed_tokens_list = [s['total_trimmed_tokens'] for s in all_configs_stats.values()]
avg_trimmed_tokens_per_run_list = [s['avg_trimmed_tokens'] for s in all_configs_stats.values()]
reset_tokens_list = [s['total_reset_tokens'] for s in all_configs_stats.values()]
avg_reset_tokens_per_run_list = [s['avg_reset_tokens'] for s in all_configs_stats.values()]
thinking_reset_tokens_list = [s['total_thinking_reset_tokens'] for s in all_configs_stats.values()]
avg_thinking_reset_tokens_per_run_list = [s['avg_thinking_reset_tokens'] for s in all_configs_stats.values()]
summary_tokens_list = [s['total_summary_tokens'] for s in all_configs_stats.values()]
avg_summary_tokens_per_run_list = [s['avg_summary_tokens'] for s in all_configs_stats.values()]
api_tokens_with_trimmed_list = [s['total_api_tokens_with_trimmed'] for s in all_configs_stats.values()]
avg_api_tokens_with_trimmed_per_run_list = [s['avg_api_tokens_with_trimmed'] for s in all_configs_stats.values()]
api_tokens_with_trimmed_and_reset_list = [s['total_api_tokens_with_trimmed_and_reset'] for s in all_configs_stats.values()]
avg_api_tokens_with_trimmed_and_reset_per_run_list = [s['avg_api_tokens_with_trimmed_and_reset'] for s in all_configs_stats.values()]
api_tokens_with_all_removed_list = [s['total_api_tokens_with_all_removed'] for s in all_configs_stats.values()]
avg_api_tokens_with_all_removed_per_run_list = [s['avg_api_tokens_with_all_removed'] for s in all_configs_stats.values()]

total_error_action_runs = sum(s.get('error_action_runs', 0) for s in all_configs_stats.values())
total_valid_runs_for_tokens = sum(s.get('valid_runs_for_tokens', s['total_runs']) for s in all_configs_stats.values())

# 过滤掉所有run的tokens都为0的config（用于计算有效config的平均tokens）
valid_configs_for_tokens = {k: v for k, v in all_configs_stats.items() if v.get('valid_runs_for_tokens', v['total_runs']) > 0}
excluded_configs_for_tokens = {k: v for k, v in all_configs_stats.items() if v.get('valid_runs_for_tokens', v['total_runs']) == 0}
num_excluded_configs = len(excluded_configs_for_tokens)

# 为有效configs重新计算token相关的统计列表
if valid_configs_for_tokens:
    valid_config_names = sorted(valid_configs_for_tokens.keys(), key=lambda x: int(x.split('_')[1]))
    valid_api_tokens_list = [valid_configs_for_tokens[k]['total_api_tokens'] for k in valid_config_names]
    valid_avg_api_tokens_per_run_list = [valid_configs_for_tokens[k]['avg_api_tokens'] for k in valid_config_names]
    valid_api_cost_list = [valid_configs_for_tokens[k]['total_api_cost'] for k in valid_config_names]
    valid_avg_api_cost_per_run_list = [valid_configs_for_tokens[k]['avg_api_cost'] for k in valid_config_names]
    valid_api_tokens_with_all_removed_list = [valid_configs_for_tokens[k]['total_api_tokens_with_all_removed'] for k in valid_config_names]
    valid_avg_api_tokens_with_all_removed_per_run_list = [valid_configs_for_tokens[k]['avg_api_tokens_with_all_removed'] for k in valid_config_names]
    valid_tool_tokens_list = [valid_configs_for_tokens[k]['total_tool_content_tokens'] for k in valid_config_names]
    valid_avg_tokens_per_call_list = [valid_configs_for_tokens[k]['avg_tokens_per_tool_call'] for k in valid_config_names]
    # Tool calls相关统计
    valid_tool_calls_list = [valid_configs_for_tokens[k]['total_tool_calls'] for k in valid_config_names]
    valid_avg_tool_calls_per_run_list = [valid_configs_for_tokens[k]['avg_tool_calls'] for k in valid_config_names]
    valid_avg_tool_content_tokens_per_run_list = [valid_configs_for_tokens[k]['avg_tool_content_tokens'] for k in valid_config_names]
else:
    valid_config_names = []
    valid_api_tokens_list = []
    valid_avg_api_tokens_per_run_list = []
    valid_api_cost_list = []
    valid_avg_api_cost_per_run_list = []
    valid_api_tokens_with_all_removed_list = []
    valid_avg_api_tokens_with_all_removed_per_run_list = []
    valid_tool_tokens_list = []
    valid_avg_tokens_per_call_list = []
    valid_tool_calls_list = []
    valid_avg_tool_calls_per_run_list = []
    valid_avg_tool_content_tokens_per_run_list = []

print(f"配置总数: {len(all_configs_stats)}")
print(f"总Run数: {total_runs}")
print(f"总成功数: {total_success}")
print(f"总失败数: {total_error}")
print(f"总成功率: {total_success / total_runs * 100:.2f}%")
print(f"含Error Action的Run数: {total_error_action_runs} (这些run的token统计已被排除)")
print(f"用于Token统计的有效Run数: {total_valid_runs_for_tokens}")
print(f"因所有run都含error而被排除的Config数: {num_excluded_configs}")
if num_excluded_configs > 0:
    print(f"  被排除的Configs: {', '.join(sorted(excluded_configs_for_tokens.keys(), key=lambda x: int(x.split('_')[1])))}")
print(f"用于Token统计的有效Config数: {len(valid_configs_for_tokens)}")
print(f"总Context Length Error数: {total_context_length_errors} ({total_context_length_errors / total_runs * 100:.2f}%)")
print(f"总非正常结束数: {total_improper_endings} ({total_improper_endings / total_runs * 100:.2f}%)")
print(f"总Reset事件数: {total_reset_events} (平均每run: {total_reset_events / total_runs:.2f})")
print(f"总Summary事件数: {total_summary_events} (平均每run: {total_summary_events / total_runs:.2f})")
print(f"总Trim事件数: {total_trim_events} (平均每run: {total_trim_events / total_runs:.2f})")
print(f"总Thinking Reset事件数: {total_thinking_reset_events} (平均每run: {total_thinking_reset_events / total_runs:.2f})")

print(f"\n{'='*50}")
print(f"--- 任务指标统计 ⭐⭐⭐ ---")
print(f"{'='*50}")
print(f"平均准确度（所有configs）: {np.mean(avg_accuracy_list):.4f}")
print(f"准确度中位数: {np.median(avg_accuracy_list):.4f}")
print(f"准确度最大值: {max(avg_accuracy_list):.4f} ({config_dirs[avg_accuracy_list.index(max(avg_accuracy_list))]})")
print(f"准确度最小值: {min(avg_accuracy_list):.4f} ({config_dirs[avg_accuracy_list.index(min(avg_accuracy_list))]})")
print(f"准确度标准差: {np.std(avg_accuracy_list):.4f}")
print(f"\n平均步数（所有configs）: {np.mean(avg_steps_list):.2f}")
print(f"步数中位数: {np.median(avg_steps_list):.2f}")
print(f"步数最大值: {max(avg_steps_list):.2f} ({config_dirs[avg_steps_list.index(max(avg_steps_list))]})")
print(f"步数最小值: {min(avg_steps_list):.2f} ({config_dirs[avg_steps_list.index(min(avg_steps_list))]})")
print(f"步数标准差: {np.std(avg_steps_list):.2f}")

print(f"\n{'='*50}")
print(f"--- API Usage 统计 ⭐⭐⭐ ---")
print(f"{'='*50}")
print(f"API总Cost（所有runs）: ${total_api_cost:.6f} 💰💰💰")
print(f"平均每个Config的API Cost（所有runs总和）: ${np.mean(api_cost_list):.6f}")
print(f"平均每个Run的API Cost: ${np.mean(avg_api_cost_per_run_list):.6f}")
print(f"每个Config的API Cost中位数: ${np.median(api_cost_list):.6f}")
print(f"每个Config的API Cost最大值: ${max(api_cost_list):.6f} ({config_dirs[api_cost_list.index(max(api_cost_list))]})")
print(f"每个Config的API Cost最小值: ${min(api_cost_list):.6f} ({config_dirs[api_cost_list.index(min(api_cost_list))]})")
print(f"每个Config的API Cost标准差: ${np.std(api_cost_list):.6f}")
print(f"\nAPI总Tokens数（所有runs）: {total_api_tokens:,}")
print(f"API总Prompt Tokens: {total_api_prompt_tokens:,}")
print(f"API总Completion Tokens: {total_api_completion_tokens:,}")
print(f"\n平均每个Config的API Tokens（所有runs总和）: {np.mean(api_tokens_list):,.2f}")
print(f"平均每个Run的API Tokens: {np.mean(avg_api_tokens_per_run_list):,.2f}")
print(f"每个Config的API Tokens中位数: {np.median(api_tokens_list):,.2f}")
print(f"每个Config的API Tokens最大值: {max(api_tokens_list):,} ({config_dirs[api_tokens_list.index(max(api_tokens_list))]})")
print(f"每个Config的API Tokens最小值: {min(api_tokens_list):,} ({config_dirs[api_tokens_list.index(min(api_tokens_list))]})")
print(f"每个Config的API Tokens标准差: {np.std(api_tokens_list):,.2f}")

print(f"\n--- Trimmed Tokens 统计（被trim掉的tokens）✂️✂️✂️ ---")
print(f"被Trim掉的总Tokens数（所有runs）: {total_trimmed_tokens:,}")
print(f"平均每个Run被Trim掉的Tokens: {np.mean(avg_trimmed_tokens_per_run_list):,.2f}")

print(f"\n--- Reset Tokens 统计（被reset掉的tokens）🔄🔄🔄 ---")
print(f"被Reset掉的总Tokens数（所有runs）: {total_reset_tokens:,}")
print(f"平均每个Run被Reset掉的Tokens: {np.mean(avg_reset_tokens_per_run_list):,.2f}")

print(f"\n--- Thinking Reset Tokens 统计（被thinking_reset掉的tokens）🧠🧠🧠 ---")
print(f"被Thinking Reset掉的总Tokens数（所有runs）: {total_thinking_reset_tokens:,}")
print(f"平均每个Run被Thinking Reset掉的Tokens: {np.mean(avg_thinking_reset_tokens_per_run_list):,.2f}")

print(f"\n--- Summary Tokens 统计（被summary掉的tokens）📋📋📋 ---")
print(f"被Summary掉的总Tokens数（所有runs）: {total_summary_tokens:,}")
print(f"平均每个Run被Summary掉的Tokens: {np.mean(avg_summary_tokens_per_run_list):,.2f}")

print(f"\n--- API Tokens（包含被trim掉的）🔢🔢🔢 ---")
print(f"API总Tokens数（包含trimmed，所有runs）: {total_api_tokens_with_trimmed:,}")
print(f"平均每个Run的API Tokens（包含trimmed）: {np.mean(avg_api_tokens_with_trimmed_per_run_list):,.2f}")
print(f"每个Config的API Tokens（包含trimmed）中位数: {np.median(api_tokens_with_trimmed_list):,.2f}")
if api_tokens_with_trimmed_list:
    print(f"每个Config的API Tokens（包含trimmed）最大值: {max(api_tokens_with_trimmed_list):,} ({config_dirs[api_tokens_with_trimmed_list.index(max(api_tokens_with_trimmed_list))]})")
    print(f"每个Config的API Tokens（包含trimmed）最小值: {min(api_tokens_with_trimmed_list):,} ({config_dirs[api_tokens_with_trimmed_list.index(min(api_tokens_with_trimmed_list))]})")
print(f"每个Config的API Tokens（包含trimmed）标准差: {np.std(api_tokens_with_trimmed_list):,.2f}")

print(f"\n--- API Tokens（包含被trim和reset掉的）---")
print(f"API总Tokens数（包含trimmed+reset，所有runs）: {total_api_tokens_with_trimmed_and_reset:,}")
print(f"平均每个Run的API Tokens（包含trimmed+reset）: {np.mean(avg_api_tokens_with_trimmed_and_reset_per_run_list):,.2f}")
print(f"每个Config的API Tokens（包含trimmed+reset）中位数: {np.median(api_tokens_with_trimmed_and_reset_list):,.2f}")
if api_tokens_with_trimmed_and_reset_list:
    print(f"每个Config的API Tokens（包含trimmed+reset）最大值: {max(api_tokens_with_trimmed_and_reset_list):,} ({config_dirs[api_tokens_with_trimmed_and_reset_list.index(max(api_tokens_with_trimmed_and_reset_list))]})")
    print(f"每个Config的API Tokens（包含trimmed+reset）最小值: {min(api_tokens_with_trimmed_and_reset_list):,} ({config_dirs[api_tokens_with_trimmed_and_reset_list.index(min(api_tokens_with_trimmed_and_reset_list))]})")
print(f"每个Config的API Tokens（包含trimmed+reset）标准差: {np.std(api_tokens_with_trimmed_and_reset_list):,.2f}")

print(f"\n--- API Tokens（包含被trim、reset和thinking_reset掉的）⭐⭐⭐ ---")
print(f"API总Tokens数（包含trimmed+reset+thinking_reset，所有runs）: {total_api_tokens_with_all_removed:,} ⭐⭐⭐")
print(f"平均每个Run的API Tokens（包含trimmed+reset+thinking_reset）: {np.mean(avg_api_tokens_with_all_removed_per_run_list):,.2f}")
print(f"每个Config的API Tokens（包含all_removed）中位数: {np.median(api_tokens_with_all_removed_list):,.2f}")
if api_tokens_with_all_removed_list:
    print(f"每个Config的API Tokens（包含all_removed）最大值: {max(api_tokens_with_all_removed_list):,} ({config_dirs[api_tokens_with_all_removed_list.index(max(api_tokens_with_all_removed_list))]})")
    print(f"每个Config的API Tokens（包含all_removed）最小值: {min(api_tokens_with_all_removed_list):,} ({config_dirs[api_tokens_with_all_removed_list.index(min(api_tokens_with_all_removed_list))]})")
print(f"每个Config的API Tokens（包含all_removed）标准差: {np.std(api_tokens_with_all_removed_list):,.2f}")

# 仅有效Config的Token统计（排除所有run都含error的config）
print(f"\n{'='*50}")
print(f"--- 仅有效Configs的Token统计（排除{num_excluded_configs}个全error的config）🎯🎯🎯 ---")
print(f"{'='*50}")
if valid_configs_for_tokens:
    print(f"有效Config数: {len(valid_configs_for_tokens)}")
    print(f"有效Configs的API总Tokens: {sum(valid_api_tokens_list):,}")
    print(f"有效Configs的平均每个Config API Tokens: {np.mean(valid_api_tokens_list):,.2f}")
    print(f"有效Configs的平均每个Run API Tokens: {np.mean(valid_avg_api_tokens_per_run_list):,.2f} ⭐⭐⭐")
    print(f"有效Configs的API Tokens中位数: {np.median(valid_api_tokens_list):,.2f}")
    print(f"有效Configs的API Tokens标准差: {np.std(valid_api_tokens_list):,.2f}")
    print(f"\n有效Configs的API总Cost: ${sum(valid_api_cost_list):.6f}")
    print(f"有效Configs的平均每个Config API Cost: ${np.mean(valid_api_cost_list):.6f}")
    print(f"有效Configs的平均每个Run API Cost: ${np.mean(valid_avg_api_cost_per_run_list):.6f} ⭐⭐⭐")
    print(f"\n有效Configs的API Tokens（包含all_removed）总数: {sum(valid_api_tokens_with_all_removed_list):,}")
    print(f"有效Configs的平均每个Config API Tokens（包含all_removed）: {np.mean(valid_api_tokens_with_all_removed_list):,.2f}")
    print(f"有效Configs的平均每个Run API Tokens（包含all_removed）: {np.mean(valid_avg_api_tokens_with_all_removed_per_run_list):,.2f} ⭐⭐⭐")
    
    # Tool calls相关统计
    print(f"\n--- 有效Configs的Tool Calls统计 🔧🔧🔧 ---")
    print(f"有效Configs的Tool调用总次数: {sum(valid_tool_calls_list):,}")
    print(f"有效Configs的平均每个Config Tool调用次数: {np.mean(valid_tool_calls_list):,.2f}")
    print(f"有效Configs的平均每个Run Tool调用次数: {np.mean(valid_avg_tool_calls_per_run_list):,.2f} ⭐⭐⭐")
    
    # Tool content tokens相关统计
    print(f"\n--- 有效Configs的Tool Content Tokens统计 📝📝📝 ---")
    print(f"有效Configs的Tool Content总Tokens: {sum(valid_tool_tokens_list):,}")
    print(f"有效Configs的平均每个Config Tool Content Tokens: {np.mean(valid_tool_tokens_list):,.2f}")
    print(f"有效Configs的平均每个Run Tool Content Tokens: {np.mean(valid_avg_tool_content_tokens_per_run_list):,.2f} ⭐⭐⭐")
    if sum(valid_tool_calls_list) > 0:
        print(f"有效Configs的平均每个Tool Call的Tokens: {sum(valid_tool_tokens_list) / sum(valid_tool_calls_list):,.2f} ⭐⭐⭐")
else:
    print(f"⚠️  没有有效的Config用于Token统计（所有Config的所有run都含error）")

print(f"\n{'='*50}")
print(f"--- Tool Content 统计 ---")
print(f"{'='*50}")
print(f"Tool调用总次数（所有runs）: {total_tool_calls:,}")
print(f"Tool Content总Tokens数（所有runs）: {total_tool_tokens:,} ⭐")
if total_tool_calls > 0:
    print(f"全局平均每个Tool Call的Tokens: {total_tool_tokens / total_tool_calls:.2f} ⭐⭐")
else:
    print(f"全局平均每个Tool Call的Tokens: N/A (没有Tool调用) ⭐⭐")
print(f"\n平均每个Config的Tool Tokens（所有runs总和）: {np.mean(tool_tokens_list):,.2f}")
print(f"Tool Tokens中位数: {np.median(tool_tokens_list):,.2f}")
print(f"Tool Tokens最大值: {max(tool_tokens_list):,} ({config_dirs[tool_tokens_list.index(max(tool_tokens_list))]})")
print(f"Tool Tokens最小值: {min(tool_tokens_list):,} ({config_dirs[tool_tokens_list.index(min(tool_tokens_list))]})")
print(f"Tool Tokens标准差: {np.std(tool_tokens_list):,.2f}")
print(f"\n--- 每个Tool Call平均Tokens统计 ⭐⭐ ---")
print(f"各Config平均每个Tool Call的Tokens - 平均值: {np.mean(avg_tokens_per_call_list):,.2f}")
print(f"各Config平均每个Tool Call的Tokens - 中位数: {np.median(avg_tokens_per_call_list):,.2f}")
print(f"各Config平均每个Tool Call的Tokens - 最大值: {max(avg_tokens_per_call_list):,.2f} ({config_dirs[avg_tokens_per_call_list.index(max(avg_tokens_per_call_list))]})")
print(f"各Config平均每个Tool Call的Tokens - 最小值: {min(avg_tokens_per_call_list):,.2f} ({config_dirs[avg_tokens_per_call_list.index(min(avg_tokens_per_call_list))]})")
print(f"各Config平均每个Tool Call的Tokens - 标准差: {np.std(avg_tokens_per_call_list):,.2f}")

print(f"\n--- 所有Content统计 ---")
print(f"所有Content总Tokens数（所有runs）: {total_all_tokens:,} ⭐")
print(f"\n平均每个Config的总Tokens（所有runs总和）: {np.mean(all_tokens_list):,.2f} ⭐")
print(f"总Tokens中位数: {np.median(all_tokens_list):,.2f}")
print(f"总Tokens最大值: {max(all_tokens_list):,} ({config_dirs[all_tokens_list.index(max(all_tokens_list))]})")
print(f"总Tokens最小值: {min(all_tokens_list):,} ({config_dirs[all_tokens_list.index(min(all_tokens_list))]})")
print(f"总Tokens标准差: {np.std(all_tokens_list):,.2f}")

# 按Reset次数排序显示
print(f"\n{'='*80}")
print(f"--- 按Reset次数排序的Config列表 🔄🔄🔄 ---")
print(f"{'='*80}")
sorted_configs_reset = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_reset_count'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_reset, 1):
    print(f"{i:2d}. {config_name:12s}: Reset: {stats['total_reset_count']:3d}次 (平均{stats['avg_reset_count']:.2f}/run) | Summary: {stats['total_summary_count']:3d}次 (平均{stats['avg_summary_count']:.2f}/run) | Trim: {stats['total_trim_count']:3d}次 (平均{stats['avg_trim_count']:.2f}/run) | Thinking Reset: {stats['total_thinking_reset_count']:3d}次 (平均{stats['avg_thinking_reset_count']:.2f}/run) | 准确度: {stats['avg_accuracy']:.4f}")

# 按Summary次数排序显示
print(f"\n{'='*80}")
print(f"--- 按Summary次数排序的Config列表 📝📝📝 ---")
print(f"{'='*80}")
sorted_configs_summary = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_summary_count'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_summary, 1):
    print(f"{i:2d}. {config_name:12s}: Summary: {stats['total_summary_count']:3d}次 (平均{stats['avg_summary_count']:.2f}/run) | Reset: {stats['total_reset_count']:3d}次 (平均{stats['avg_reset_count']:.2f}/run) | Trim: {stats['total_trim_count']:3d}次 (平均{stats['avg_trim_count']:.2f}/run) | Thinking Reset: {stats['total_thinking_reset_count']:3d}次 (平均{stats['avg_thinking_reset_count']:.2f}/run) | 准确度: {stats['avg_accuracy']:.4f}")

# 按Trim次数排序显示
print(f"\n{'='*80}")
print(f"--- 按Trim次数排序的Config列表 ✂️✂️✂️ ---")
print(f"{'='*80}")
sorted_configs_trim = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_trim_count'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_trim, 1):
    print(f"{i:2d}. {config_name:12s}: Trim: {stats['total_trim_count']:3d}次 (平均{stats['avg_trim_count']:.2f}/run) | Reset: {stats['total_reset_count']:3d}次 (平均{stats['avg_reset_count']:.2f}/run) | Summary: {stats['total_summary_count']:3d}次 (平均{stats['avg_summary_count']:.2f}/run) | Thinking Reset: {stats['total_thinking_reset_count']:3d}次 (平均{stats['avg_thinking_reset_count']:.2f}/run) | 准确度: {stats['avg_accuracy']:.4f}")

# 按Thinking Reset次数排序显示
print(f"\n{'='*80}")
print(f"--- 按Thinking Reset次数排序的Config列表 🧠🧠🧠 ---")
print(f"{'='*80}")
sorted_configs_thinking_reset = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_thinking_reset_count'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_thinking_reset, 1):
    print(f"{i:2d}. {config_name:12s}: Thinking Reset: {stats['total_thinking_reset_count']:3d}次 (平均{stats['avg_thinking_reset_count']:.2f}/run) | Reset: {stats['total_reset_count']:3d}次 (平均{stats['avg_reset_count']:.2f}/run) | Summary: {stats['total_summary_count']:3d}次 (平均{stats['avg_summary_count']:.2f}/run) | Trim: {stats['total_trim_count']:3d}次 (平均{stats['avg_trim_count']:.2f}/run) | 准确度: {stats['avg_accuracy']:.4f}")

# 按Improper Ending Rate排序显示
print(f"\n{'='*80}")
print(f"--- 按非正常结束比例排序的Config列表 ⚠️⚠️⚠️ ---")
print(f"{'='*80}")
sorted_configs_improper = sorted(all_configs_stats.items(), key=lambda x: x[1]['improper_ending_rate'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_improper, 1):
    print(f"{i:2d}. {config_name:12s}: 非正常结束: {stats['improper_ending_runs']}/{stats['total_runs']} ({stats['improper_ending_rate']*100:.1f}%) | 准确度: {stats['avg_accuracy']:.4f} | 平均步数: {stats['avg_steps']:6.2f}")

# 按Context Length Error Rate排序显示
print(f"\n{'='*80}")
print(f"--- 按Context Length Error比例排序的Config列表 🚨🚨🚨 ---")
print(f"{'='*80}")
sorted_configs_ctx_err = sorted(all_configs_stats.items(), key=lambda x: x[1]['context_length_error_rate'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_ctx_err, 1):
    print(f"{i:2d}. {config_name:12s}: Context Length Error: {stats['context_length_error_runs']}/{stats['total_runs']} ({stats['context_length_error_rate']*100:.1f}%) | 准确度: {stats['avg_accuracy']:.4f} | 平均步数: {stats['avg_steps']:6.2f}")

# 按准确度排序显示
print(f"\n{'='*80}")
print(f"--- 按平均准确度排序的Config列表 ⭐⭐⭐ ---")
print(f"{'='*80}")
sorted_configs_acc = sorted(all_configs_stats.items(), key=lambda x: x[1]['avg_accuracy'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_acc, 1):
    ctx_err_str = f"CtxErr: {stats['context_length_error_runs']}/{stats['total_runs']} ({stats['context_length_error_rate']*100:.1f}%)"
    improper_str = f"非正常结束: {stats['improper_ending_runs']}/{stats['total_runs']} ({stats['improper_ending_rate']*100:.1f}%)"
    reset_summary_trim_str = f"Reset: {stats['total_reset_count']}次 | Summary: {stats['total_summary_count']}次 | Trim: {stats['total_trim_count']}次 | Thinking Reset: {stats['total_thinking_reset_count']}次"
    print(f"{i:2d}. {config_name:12s}: 准确度: {stats['avg_accuracy']:.4f} | 平均步数: {stats['avg_steps']:6.2f} | 成功/总数: {stats['success_runs']}/{stats['total_runs']} | {improper_str} | {ctx_err_str} | {reset_summary_trim_str} | API cost: ${stats['total_api_cost']:.6f}")

# 按API Total Cost排序显示
print(f"\n{'='*80}")
print(f"--- 按API Total Cost排序的Config列表 💰💰💰 ---")
print(f"{'='*80}")
sorted_configs_cost = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_api_cost'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_cost, 1):
    print(f"{i:2d}. {config_name:12s}: API总cost: ${stats['total_api_cost']:9.6f} | 平均每run: ${stats['avg_api_cost']:9.6f} | API tokens: {stats['total_api_tokens']:8,} | Tool调用: {stats['total_tool_calls']:3d}次")

# 按API Total Tokens排序显示
print(f"\n{'='*80}")
print(f"--- 按API Total Tokens排序的Config列表 ⭐⭐⭐ ---")
print(f"{'='*80}")
sorted_configs_api = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_api_tokens'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_api, 1):
    print(f"{i:2d}. {config_name:12s}: API总tokens: {stats['total_api_tokens']:8,} | 平均每run: {stats['avg_api_tokens']:8,.2f} | Prompt: {stats['total_api_prompt_tokens']:8,} | Completion: {stats['total_api_completion_tokens']:7,} | Tool调用: {stats['total_tool_calls']:3d}次")

# 按Tool Content Tokens排序显示
print(f"\n{'='*80}")
print(f"--- 按Tool Content Tokens数排序的Config列表 ---")
print(f"{'='*80}")
sorted_configs = sorted(all_configs_stats.items(), key=lambda x: x[1]['total_tool_content_tokens'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs, 1):
    print(f"{i:2d}. {config_name:12s}: Tool Content: {stats['total_tool_content_tokens']:8,} tokens (平均每call: {stats['avg_tokens_per_tool_call']:7.2f}) | Tool调用: {stats['total_tool_calls']:3d}次")

# 按平均每个tool call的tokens排序显示
print(f"\n{'='*80}")
print(f"--- 按平均每个Tool Call的Tokens排序的Config列表 ---")
print(f"{'='*80}")
sorted_configs_avg = sorted(all_configs_stats.items(), key=lambda x: x[1]['avg_tokens_per_tool_call'], reverse=True)
for i, (config_name, stats) in enumerate(sorted_configs_avg, 1):
    print(f"{i:2d}. {config_name:12s}: 平均 {stats['avg_tokens_per_tool_call']:7.2f} tokens/call | 总Tool Content tokens: {stats['total_tool_content_tokens']:8,} | Tool调用: {stats['total_tool_calls']:3d}次")

print("\n" + "=" * 100)

# 保存结果到文件
import datetime
output_filename = f"analysis_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
output_path = os.path.join(output_dir, output_filename)

# 准备要保存的数据（移除runs详细信息中的大量内容，只保留关键指标）
save_data = {
    "analysis_time": datetime.datetime.now().isoformat(),
    "base_directory": base_dir,
    "grouping_info": {
        "group_by_seed": group_by_seed,
        "config_groups": {str(k): v for k, v in config_groups.items()} if config_groups else None,
        "num_groups": len(config_groups) if config_groups else len(all_configs_stats)
    },
    "summary": {
        "total_configs": len(all_configs_stats),
        "total_runs": total_runs,
        "total_success": total_success,
        "total_error": total_error,
        "total_error_action_runs": sum(s.get('error_action_runs', 0) for s in all_configs_stats.values()),  # 包含error action的run数量
        "total_valid_runs_for_tokens": sum(s.get('valid_runs_for_tokens', s['total_runs']) for s in all_configs_stats.values()),  # 用于token统计的有效run数量
        "success_rate": total_success / total_runs if total_runs > 0 else 0,
        "total_context_length_errors": total_context_length_errors,
        "context_length_error_rate": total_context_length_errors / total_runs if total_runs > 0 else 0,
        "total_improper_endings": total_improper_endings,
        "improper_ending_rate": total_improper_endings / total_runs if total_runs > 0 else 0,
        "total_reset_events": total_reset_events,
        "total_summary_events": total_summary_events,
        "total_trim_events": total_trim_events,
        "total_thinking_reset_events": total_thinking_reset_events,
        "avg_reset_per_run": total_reset_events / total_runs if total_runs > 0 else 0,
        "avg_summary_per_run": total_summary_events / total_runs if total_runs > 0 else 0,
        "avg_trim_per_run": total_trim_events / total_runs if total_runs > 0 else 0,
        "avg_thinking_reset_per_run": total_thinking_reset_events / total_runs if total_runs > 0 else 0,
        
        # 任务指标
        "avg_accuracy": float(np.mean(avg_accuracy_list)),
        "median_accuracy": float(np.median(avg_accuracy_list)),
        "avg_steps": float(np.mean(avg_steps_list)),
        "median_steps": float(np.median(avg_steps_list)),
        
        # API tokens
        "total_api_tokens": total_api_tokens,
        "total_api_prompt_tokens": total_api_prompt_tokens,
        "total_api_completion_tokens": total_api_completion_tokens,
        "avg_api_tokens_per_config": float(np.mean(api_tokens_list)),
        "avg_api_tokens_per_run": float(np.mean(avg_api_tokens_per_run_list)),
        
        # API cost
        "total_api_cost": float(total_api_cost),
        "avg_api_cost_per_config": float(np.mean(api_cost_list)),
        "avg_api_cost_per_run": float(np.mean(avg_api_cost_per_run_list)),
        
        # Tool content
        "total_tool_calls": total_tool_calls,
        "total_tool_content_tokens": total_tool_tokens,
        "avg_tokens_per_tool_call": total_tool_tokens / total_tool_calls if total_tool_calls > 0 else 0,
        "total_all_content_tokens": total_all_tokens,
        
        # Trimmed tokens
        "total_trimmed_tokens": total_trimmed_tokens,
        "avg_trimmed_tokens_per_run": float(np.mean(avg_trimmed_tokens_per_run_list)),
        "total_api_tokens_with_trimmed": total_api_tokens_with_trimmed,
        "avg_api_tokens_with_trimmed_per_run": float(np.mean(avg_api_tokens_with_trimmed_per_run_list)),
        
        # Reset tokens
        "total_reset_tokens": total_reset_tokens,
        "avg_reset_tokens_per_run": float(np.mean(avg_reset_tokens_per_run_list)),
        "total_api_tokens_with_trimmed_and_reset": total_api_tokens_with_trimmed_and_reset,
        "avg_api_tokens_with_trimmed_and_reset_per_run": float(np.mean(avg_api_tokens_with_trimmed_and_reset_per_run_list)),
        
        # Thinking reset tokens
        "total_thinking_reset_tokens": total_thinking_reset_tokens,
        "avg_thinking_reset_tokens_per_run": float(np.mean(avg_thinking_reset_tokens_per_run_list)),
        
        # Summary tokens
        "total_summary_tokens": total_summary_tokens,
        "avg_summary_tokens_per_run": float(np.mean(avg_summary_tokens_per_run_list)),
        
        "total_api_tokens_with_all_removed": total_api_tokens_with_all_removed,
        "avg_api_tokens_with_all_removed_per_run": float(np.mean(avg_api_tokens_with_all_removed_per_run_list)),
        
        # 仅有效Configs的统计（排除所有run都含error的config）
        "num_excluded_configs_for_tokens": num_excluded_configs,
        "excluded_configs_for_tokens": list(excluded_configs_for_tokens.keys()) if excluded_configs_for_tokens else [],
        "num_valid_configs_for_tokens": len(valid_configs_for_tokens),
        "valid_configs_total_api_tokens": sum(valid_api_tokens_list) if valid_api_tokens_list else 0,
        "valid_configs_avg_api_tokens_per_config": float(np.mean(valid_api_tokens_list)) if valid_api_tokens_list else 0,
        "valid_configs_avg_api_tokens_per_run": float(np.mean(valid_avg_api_tokens_per_run_list)) if valid_avg_api_tokens_per_run_list else 0,
        "valid_configs_total_api_cost": sum(valid_api_cost_list) if valid_api_cost_list else 0,
        "valid_configs_avg_api_cost_per_config": float(np.mean(valid_api_cost_list)) if valid_api_cost_list else 0,
        "valid_configs_avg_api_cost_per_run": float(np.mean(valid_avg_api_cost_per_run_list)) if valid_avg_api_cost_per_run_list else 0,
        "valid_configs_total_api_tokens_with_all_removed": sum(valid_api_tokens_with_all_removed_list) if valid_api_tokens_with_all_removed_list else 0,
        "valid_configs_avg_api_tokens_with_all_removed_per_config": float(np.mean(valid_api_tokens_with_all_removed_list)) if valid_api_tokens_with_all_removed_list else 0,
        "valid_configs_avg_api_tokens_with_all_removed_per_run": float(np.mean(valid_avg_api_tokens_with_all_removed_per_run_list)) if valid_avg_api_tokens_with_all_removed_per_run_list else 0,
        
        # 有效Configs的Tool Calls统计
        "valid_configs_total_tool_calls": sum(valid_tool_calls_list) if valid_tool_calls_list else 0,
        "valid_configs_avg_tool_calls_per_config": float(np.mean(valid_tool_calls_list)) if valid_tool_calls_list else 0,
        "valid_configs_avg_tool_calls_per_run": float(np.mean(valid_avg_tool_calls_per_run_list)) if valid_avg_tool_calls_per_run_list else 0,
        
        # 有效Configs的Tool Content Tokens统计
        "valid_configs_total_tool_content_tokens": sum(valid_tool_tokens_list) if valid_tool_tokens_list else 0,
        "valid_configs_avg_tool_content_tokens_per_config": float(np.mean(valid_tool_tokens_list)) if valid_tool_tokens_list else 0,
        "valid_configs_avg_tool_content_tokens_per_run": float(np.mean(valid_avg_tool_content_tokens_per_run_list)) if valid_avg_tool_content_tokens_per_run_list else 0,
        "valid_configs_avg_tokens_per_tool_call": sum(valid_tool_tokens_list) / sum(valid_tool_calls_list) if valid_tool_calls_list and sum(valid_tool_calls_list) > 0 else 0,
    },
    "configs": {}
}

# 为每个config添加汇总数据（包含每个run的详细信息）
for config_name, stats in all_configs_stats.items():
    # 提取每个run的关键指标
    runs_detail = []
    for idx, run in enumerate(stats['runs']):
        run_info = {
            "run_index": idx,
            "accuracy": run['accuracy'],
            "total_steps": run['total_steps'],
            "completed": run['completed'],
            "has_context_length_error": run.get('has_context_length_error', False),
            "proper_ending": run.get('proper_ending', False),
            "has_error": run.get('has_error', False),  # 是否包含error action（用于排除token统计）
            "reset_count": run.get('reset_count', 0),
            "summary_count": run.get('summary_count', 0),
            "trim_count": run.get('trim_count', 0),
            "thinking_reset_count": run.get('thinking_reset_count', 0),
            "total_messages": run['total_messages'],
            "tool_calls": run['tool_calls'],
            "user_messages": run['user_messages'],
            "assistant_messages": run['assistant_messages'],
            "tool_content_tokens": run['tool_content_tokens'],
            "all_content_tokens": run['all_content_tokens'],
            "api_total_tokens": run['api_total_tokens'],
            "api_prompt_tokens": run['api_prompt_tokens'],
            "api_completion_tokens": run['api_completion_tokens'],
            "api_total_cost": run['api_total_cost'],
            "trimmed_tokens_total": run.get('trimmed_tokens_total', 0),  # 被trim掉的tokens总数
            "reset_tokens_total": run.get('reset_tokens_total', 0),  # 被reset掉的tokens总数
            "thinking_reset_tokens_total": run.get('thinking_reset_tokens_total', 0),  # 被thinking_reset掉的tokens总数
            "summary_tokens_total": run.get('summary_tokens_total', 0),  # 被summary掉的tokens总数
            "api_total_tokens_with_trimmed": run['api_total_tokens'] + run.get('trimmed_tokens_total', 0),  # 包含被trim掉的tokens
            "api_total_tokens_with_trimmed_and_reset": run['api_total_tokens'] + run.get('trimmed_tokens_total', 0) + run.get('reset_tokens_total', 0),  # 包含被trim和reset掉的tokens
            "api_total_tokens_with_all_removed": run['api_total_tokens'] + run.get('trimmed_tokens_total', 0) + run.get('reset_tokens_total', 0) + run.get('thinking_reset_tokens_total', 0) + run.get('summary_tokens_total', 0),  # 包含所有被删掉的tokens
            "tokens_before_each_assistant": run.get('tokens_before_each_assistant', []),  # 每次assistant回复前的累计tokens
        }
        runs_detail.append(run_info)
    
    save_data["configs"][config_name] = {
        "total_runs": stats['total_runs'],
        "success_runs": stats['success_runs'],
        "error_runs": stats['error_runs'],
        "error_action_runs": stats.get('error_action_runs', 0),  # 包含error action的run数量
        "valid_runs_for_tokens": stats.get('valid_runs_for_tokens', stats['total_runs']),  # 用于token统计的有效run数量
        "context_length_error_runs": stats['context_length_error_runs'],
        "context_length_error_rate": stats['context_length_error_rate'],
        "improper_ending_runs": stats['improper_ending_runs'],
        "improper_ending_rate": stats['improper_ending_rate'],
        "total_reset_count": stats['total_reset_count'],
        "total_summary_count": stats['total_summary_count'],
        "total_trim_count": stats['total_trim_count'],
        "total_thinking_reset_count": stats['total_thinking_reset_count'],
        "avg_reset_count": stats['avg_reset_count'],
        "avg_summary_count": stats['avg_summary_count'],
        "avg_trim_count": stats['avg_trim_count'],
        "avg_thinking_reset_count": stats['avg_thinking_reset_count'],
        "avg_accuracy": stats['avg_accuracy'],
        "avg_steps": stats['avg_steps'],
        "accuracies": stats['accuracies'],
        "steps": stats['steps'],
        "total_tool_calls": stats['total_tool_calls'],
        "total_tool_content_tokens": stats['total_tool_content_tokens'],
        "total_all_content_tokens": stats['total_all_content_tokens'],
        "total_api_tokens": stats['total_api_tokens'],
        "total_api_prompt_tokens": stats['total_api_prompt_tokens'],
        "total_api_completion_tokens": stats['total_api_completion_tokens'],
        "total_api_cost": stats['total_api_cost'],
        "avg_tool_calls": stats['avg_tool_calls'],
        "avg_tool_content_tokens": stats['avg_tool_content_tokens'],
        "avg_all_content_tokens": stats['avg_all_content_tokens'],
        "avg_api_tokens": stats['avg_api_tokens'],
        "avg_api_prompt_tokens": stats['avg_api_prompt_tokens'],
        "avg_api_completion_tokens": stats['avg_api_completion_tokens'],
        "avg_api_cost": stats['avg_api_cost'],
        "avg_tokens_per_tool_call": stats['avg_tokens_per_tool_call'],
        "total_trimmed_tokens": stats['total_trimmed_tokens'],
        "avg_trimmed_tokens": stats['avg_trimmed_tokens'],
        "total_reset_tokens": stats['total_reset_tokens'],
        "avg_reset_tokens": stats['avg_reset_tokens'],
        "total_thinking_reset_tokens": stats['total_thinking_reset_tokens'],
        "avg_thinking_reset_tokens": stats['avg_thinking_reset_tokens'],
        "total_summary_tokens": stats['total_summary_tokens'],
        "avg_summary_tokens": stats['avg_summary_tokens'],
        "total_api_tokens_with_trimmed": stats['total_api_tokens_with_trimmed'],
        "avg_api_tokens_with_trimmed": stats['avg_api_tokens_with_trimmed'],
        "total_api_tokens_with_trimmed_and_reset": stats['total_api_tokens_with_trimmed_and_reset'],
        "avg_api_tokens_with_trimmed_and_reset": stats['avg_api_tokens_with_trimmed_and_reset'],
        "total_api_tokens_with_all_removed": stats['total_api_tokens_with_all_removed'],
        "avg_api_tokens_with_all_removed": stats['avg_api_tokens_with_all_removed'],
        "runs": runs_detail  # 添加每个run的详细指标
    }

# 保存到文件
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(save_data, f, indent=2, ensure_ascii=False)

print(f"\n✅ 分析结果已保存到: {output_path}")

# 保存CSV文件
csv_filename = f"analysis_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
csv_path = os.path.join(output_dir, csv_filename)

# 按config编号排序
sorted_config_names = sorted(all_configs_stats.keys(), key=lambda x: int(x.split('_')[1]))

# 准备CSV数据
csv_data = []
metrics = [
    ('avg_accuracy', 'Average Accuracy'),
    ('avg_steps', 'Average Steps'),
    ('improper_ending_rate', 'Improper Ending Rate'),
    ('improper_ending_runs', 'Improper Ending Count'),
    ('context_length_error_rate', 'Context Length Error Rate'),
    ('context_length_error_runs', 'Context Length Error Count'),
    ('total_reset_count', 'Total Reset Count'),
    ('avg_reset_count', 'Average Reset Count'),
    ('total_summary_count', 'Total Summary Count'),
    ('avg_summary_count', 'Average Summary Count'),
    ('total_trim_count', 'Total Trim Count'),
    ('avg_trim_count', 'Average Trim Count'),
    ('total_thinking_reset_count', 'Total Thinking Reset Count'),
    ('avg_thinking_reset_count', 'Average Thinking Reset Count'),
    ('avg_tool_calls', 'Average Tool Calls'),
    ('total_tool_content_tokens', 'Total Tool Content Tokens'),
    ('avg_tool_content_tokens', 'Average Tool Content Tokens'),
    ('total_all_content_tokens', 'Total All Content Tokens'),
    ('avg_all_content_tokens', 'Average All Content Tokens'),
    ('total_api_tokens', 'Total API Tokens'),
    ('avg_api_tokens', 'Average API Tokens'),
    ('total_api_cost', 'Total API Cost ($)'),
    ('avg_api_cost', 'Average API Cost ($)'),
    ('total_trimmed_tokens', 'Total Trimmed Tokens'),
    ('avg_trimmed_tokens', 'Average Trimmed Tokens'),
    ('total_reset_tokens', 'Total Reset Tokens'),
    ('avg_reset_tokens', 'Average Reset Tokens'),
    ('total_thinking_reset_tokens', 'Total Thinking Reset Tokens'),
    ('avg_thinking_reset_tokens', 'Average Thinking Reset Tokens'),
    ('total_summary_tokens', 'Total Summary Tokens'),
    ('avg_summary_tokens', 'Average Summary Tokens'),
    ('total_api_tokens_with_trimmed', 'Total API Tokens (incl. Trimmed)'),
    ('avg_api_tokens_with_trimmed', 'Average API Tokens (incl. Trimmed)'),
    ('total_api_tokens_with_trimmed_and_reset', 'Total API Tokens (incl. Trimmed+Reset)'),
    ('avg_api_tokens_with_trimmed_and_reset', 'Average API Tokens (incl. Trimmed+Reset)'),
    ('total_api_tokens_with_all_removed', 'Total API Tokens (incl. All Removed)'),
    ('avg_api_tokens_with_all_removed', 'Average API Tokens (incl. All Removed)')
]

# 写入CSV
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # 如果有分组信息，写入分组说明
    if group_by_seed and config_groups:
        writer.writerow(['# Grouping Mode: Enabled'])
        writer.writerow(['# Config Groups:'])
        for group_id, member_configs in sorted(config_groups.items()):
            config_names = [f"config_{c}" for c in member_configs]
            writer.writerow([f"# Group {group_id}:", ', '.join(config_names)])
        writer.writerow([])  # 空行分隔
    else:
        writer.writerow(['# Grouping Mode: Disabled'])
        writer.writerow([])  # 空行分隔
    
    # 写入表头
    header = ['Metric'] + sorted_config_names
    writer.writerow(header)
    
    # 写入每个指标的行
    for metric_key, metric_name in metrics:
        row = [metric_name]
        for config_name in sorted_config_names:
            value = all_configs_stats[config_name][metric_key]
            # 根据指标类型格式化数值
            if metric_key == 'avg_accuracy':
                row.append(f"{value:.4f}")
            elif metric_key == 'avg_steps':
                row.append(f"{value:.2f}")
            elif metric_key == 'improper_ending_rate':
                row.append(f"{value:.4f}")
            elif metric_key == 'improper_ending_runs':
                row.append(f"{int(value)}")
            elif metric_key == 'context_length_error_rate':
                row.append(f"{value:.4f}")
            elif metric_key == 'context_length_error_runs':
                row.append(f"{int(value)}")
            elif metric_key in ['total_reset_count', 'total_summary_count', 'total_trim_count', 'total_thinking_reset_count']:
                row.append(f"{int(value)}")
            elif metric_key in ['avg_reset_count', 'avg_summary_count', 'avg_trim_count', 'avg_thinking_reset_count']:
                row.append(f"{value:.2f}")
            elif metric_key in ['total_tool_content_tokens', 'total_all_content_tokens', 'total_api_tokens', 'total_trimmed_tokens', 'total_reset_tokens', 'total_thinking_reset_tokens', 'total_summary_tokens', 'total_api_tokens_with_trimmed', 'total_api_tokens_with_trimmed_and_reset', 'total_api_tokens_with_all_removed']:
                row.append(f"{int(value)}")  # 总tokens数显示为整数
            elif metric_key in ['avg_tool_content_tokens', 'avg_all_content_tokens', 'avg_api_tokens', 'avg_trimmed_tokens', 'avg_reset_tokens', 'avg_thinking_reset_tokens', 'avg_summary_tokens', 'avg_api_tokens_with_trimmed', 'avg_api_tokens_with_trimmed_and_reset', 'avg_api_tokens_with_all_removed']:
                row.append(f"{value:.2f}")  # 平均tokens保留2位小数
            elif metric_key in ['avg_api_cost', 'total_api_cost']:
                row.append(f"{value:.8f}")  # cost保留更多小数位
            else:
                row.append(f"{value:.2f}")
        writer.writerow(row)

print(f"✅ CSV汇总文件已保存到: {csv_path}")

# 保存tokens变化趋势CSV文件
tokens_progression_filename = f"tokens_progression_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
tokens_progression_path = os.path.join(output_dir, tokens_progression_filename)

with open(tokens_progression_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # 写入表头
    writer.writerow(['# Tokens Progression Before Each Assistant Response'])
    writer.writerow(['# This file shows the cumulative token count before each assistant message in each run'])
    writer.writerow([])
    
    # 为每个config写入数据
    for config_name in sorted_config_names:
        stats = all_configs_stats[config_name]
        
        writer.writerow([f'### {config_name} ###'])
        writer.writerow(['Run Index', 'Assistant Index', 'Cumulative Tokens Before Assistant'])
        
        # 遍历每个run
        for run_idx, run in enumerate(stats['runs']):
            tokens_progression = run.get('tokens_before_each_assistant', [])
            
            if tokens_progression:
                for item in tokens_progression:
                    assistant_idx = item['assistant_index']
                    cumulative_tokens = item['cumulative_tokens']
                    writer.writerow([run_idx, assistant_idx, cumulative_tokens])
            else:
                # 如果没有数据，写入一行说明
                writer.writerow([run_idx, 'N/A', 'No data'])
        
        writer.writerow([])  # 空行分隔不同的config

print(f"✅ Tokens变化趋势文件已保存到: {tokens_progression_path}")
print("=" * 100)

