#!/usr/bin/env python3
import os
import sys
import re
import argparse
import time
import json
from datetime import datetime
from fix import call_deepseek_api

# 默认参数值
DEFAULT_GEN_ITER = 3
DEFAULT_VAL_ITER = 2
DEFAULT_VAL_PROBLEMS = 5
DEFAULT_MAX_WAIT = 300
DEFAULT_MAX_TOKENS = 32768

def create_output_dir(base_dir="output"):
    """创建带时间戳的输出目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(base_dir, f"output_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def save_iteration_data(output_dir, iteration, content_type, content):
    """保存迭代数据到文件"""
    filename = f"{content_type}{iteration}.txt"
    path = os.path.join(output_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def read_file_content(file_path):
    """读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"错误: 输入文件 '{file_path}' 未找到。", file=sys.stderr)
        return None
    except Exception as e:
        print(f"错误: 读取文件 '{file_path}' 时出现异常: {e}", file=sys.stderr)
        return None

def strip_markdown(text):
    """移除Markdown语法"""
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'(^|\n)#+\s*', r'\1', text)
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'(^|\n)>\s?', r'\1', text)
    text = re.sub(r'(^|\n)[\-\*\+]\s+', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text

def count_visible_chars(text):
    """计算可见字符数"""
    stripped = strip_markdown(text)
    return len(re.sub(r"\s+", "", stripped))

def detect_language(text):
    """检测文本主要语言"""
    total = len(text)
    if total == 0: return None
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    ratio = chinese / total
    return '中文' if ratio > 0.3 else 'English'

def generate_questions(content, api_key, model, num_questions, timeout):
    """生成考试题目"""
    prompt = f"请基于以下文本内容，生成{num_questions}道选择题（单选或多选）。确保题目覆盖文本中的重要知识点和易错点：\n{content}"
    
    system_message = (
        "您是一位经验丰富的考试命题专家。任务："
        "1. 根据文本内容推断课程主题和重点"
        "2. 只生成选择题（单选或多选）"
        "3. 题目难度应接近期末考试水平"
        "4. 格式要求："
        "   - 每道题以题号开始（如：1.）"
        "   - 题目内容"
        "   - 选项以A、B、C、D等大写字母开头"
        "   - 最后一行标注'答案：'和正确答案"
        "5. 确保题目覆盖所有重要知识点"
    )
    
    try:
        questions = call_deepseek_api(
            prompt=prompt,
            api_key=api_key,
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system_message=system_message,
            timeout=timeout
        )
        return questions
    except Exception as e:
        print(f"题目生成失败: {e}", file=sys.stderr)
        return None

def parse_answers_with_api(answers_text, api_key, model, timeout):
    """解析解答结果"""
    prompt = (
        f"请分析以下解答文本，提取每道题的状态（正确、错误或无法解答）：\n{answers_text}\n\n"
        "输出格式要求："
        "1. 输出JSON格式"
        "2. 包含一个数组，每个元素是一个对象"
        "3. 每个对象包含两个字段：'question'（题目内容）和'status'（状态）"
        "4. 状态只能是'正确'、'错误'或'无法解答'"
    )
    
    system_message = (
        "你是一个解答解析器。任务："
        "1. 分析提供的解答文本"
        "2. 识别每道题的题目内容"
        "3. 判断每道题的状态"
        "4. 输出严格的JSON格式"
    )
    
    try:
        result_json = call_deepseek_api(
            prompt=prompt,
            api_key=api_key,
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system_message=system_message,
            timeout=timeout
        )
        
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            json_match = re.search(r'\[.*\]', result_json, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            print(f"无法解析为有效JSON: {result_json}")
            return None
    except Exception as e:
        print(f"解析API调用失败: {e}", file=sys.stderr)
        return None

def solve_questions_with_cheatsheet(questions, cheatsheet, api_key, model, timeout):
    """使用摘要内容解答题目"""
    prompt = (
        f"你正在参加半开卷考试，只能参考以下摘要内容：\n{cheatsheet}\n\n"
        f"请尝试解答以下题目（只能使用摘要中的信息）：\n{questions}\n\n"
        "输出要求："
        "1. 对于每道题，先完整写出题目"
        "2. 然后写'解答：'和你的解答"
        "3. 最后写'状态：'并给出状态"
    )
    
    system_message = (
        "你是一位考生，只能使用提供的复习摘要来解答问题。"
        "严格规则："
        "1. 只能使用摘要中的信息"
        "2. 客观评估解答状态"
        "3. 诚实评估，不要猜测"
    )
    
    try:
        answers = call_deepseek_api(
            prompt=prompt,
            api_key=api_key,
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system_message=system_message,
            timeout=timeout
        )
        
        results = parse_answers_with_api(answers, api_key, model, timeout)
        return answers, results
    except Exception as e:
        print(f"题目解答失败: {e}", file=sys.stderr)
        return None, None

def generate_visualization(results, output_dir, iteration):
    """生成正确性可视化"""
    if not results:
        print("无有效结果数据，无法生成可视化")
        return None, None
    
    visualization = ""
    for result in results:
        if "status" in result:
            if "正确" in result["status"]:
                visualization += "🟩"
            elif "错误" in result["status"] or "无法解答" in result["status"]:
                visualization += "🟥"
            else:
                visualization += "⬜"
        else:
            visualization += "⬜"
    
    vis_path = os.path.join(output_dir, f"visual{iteration}.txt")
    with open(vis_path, 'w', encoding='utf-8') as f:
        f.write(visualization)
    
    result_path = os.path.join(output_dir, f"result{iteration}.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump({
            "visualization": visualization,
            "correct_count": sum(1 for r in results if "status" in r and "正确" in r["status"]),
            "incorrect_count": sum(1 for r in results if "status" in r and "错误" in r["status"]),
            "unsolved_count": sum(1 for r in results if "status" in r and "无法解答" in r["status"]),
            "details": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"可视化结果: {visualization}")
    print(f"正确: {sum(1 for r in results if 'status' in r and '正确' in r['status'])}题, "
          f"错误: {sum(1 for r in results if 'status' in r and '错误' in r['status'])}题, "
          f"无法解答: {sum(1 for r in results if 'status' in r and '无法解答' in r['status'])}题")
    
    return vis_path, result_path

def iterative_summarize(content, api_key, model, final_limit, output_dir, 
                       gen_iter, val_iter, val_problems, max_wait):
    """迭代式摘要生成"""
    lang = detect_language(content)
    lang_instruction = f"若原文主要使用{lang}，请使用相同语言输出摘要。" if lang else ''
    
    try:
        cap = int(os.getenv("DEEPSEEK_MAX_VISIBLE_CHARS", "30000"))
    except ValueError:
        cap = 30000
    
    raw_limits = []
    for i in range(gen_iter):
        if i == 0: raw_limits.append(5 * final_limit)
        elif i == 1: raw_limits.append(2 * final_limit)
        else: raw_limits.append(final_limit)
    limits = [min(l, cap) for l in raw_limits]
    
    current_content = content
    save_iteration_data(output_dir, "0_raw", "gen", content)
    
    for idx, limit in enumerate(limits, start=1):
        if idx == 1:
            system_message = (
                "您是一位高效的学术助手和专业的总结者，" 
                f"当前扮演角色: 经验丰富的考试复习摘要助手（迭代{idx}），你需要把用户给出的资料进行高度的概括，帮助用户制作半开卷考试的入场资料。"
                f"由于半开卷考试的纸张大小有限，经用户计算，目标可见字符数严格不超过 {limit}。"
                f"任务：将提供的讲义浓缩成简洁、高度可扫描的考试复习备忘录，字数严格不超过 {limit} 字（可见字符）。"
                "请先估算最终摘要的可见字符长度，如果可能超过限制，请预先规划删除策略。"
                "侧重核心概念、定义、关键公式、重要步骤和易混淆考点。"
                "请仅基于提供文本，不含外部信息或臆造内容。"
                "请以Markdown格式输出，加粗关键术语，~划掉~表示可弱化。"
                "第一次摘要时，请识别并对关键考点使用**加粗**标注，以便后续保留；"
                "思考流程：识别主题→提炼定义、公式、见解和记忆提示；"
                f"若内容过多，请大胆删除与考试无关知识点，以确保输出长度不超过 {limit} 字；"
                f"若已满足限制，无需压缩；{lang_instruction}"
                "同时，请始终满足以下要求：\n"
                f"1. 明确课程名称，推测学生的前置知识\n"
                f"2. 删除考试中绝对不会遇到的内容\n"
                f"3. 用户群体均为准备期末考试的大学生\n"
                f"4. 始终保持可读性"
            )
        else:
            system_message = (
                f"您是一位更高级的考试复习摘要专家（迭代{idx}）。基于上一次结果，精简至严格不超过 {limit} 字："
                "请首先评估当前摘要长度，若超过限制，务必进一步删除非核心内容；"
                "确认覆盖所有核心考点；保留**加粗**，弱化或删除~划掉~；"
                f"若已满足限制，无需再次压缩；压缩困难时可删除更细节非考试相关内容；"
                f"{lang_instruction}优化表达，增加记忆提示；保持逻辑连贯、易快速浏览；"
                "同时，请始终满足以下要求：\n"
                f"1. 明确课程名称，推测学生的前置知识\n"
                f"2. 删除考试中绝对不会遇到的内容\n"
                f"3. 用户群体均为准备期末考试的大学生\n"
                f"4. 以Markdown格式输出"
            )
        
        print(f"\n=== 生成阶段迭代 {idx}/{len(limits)} ===")
        try:
            result = call_deepseek_api(
                prompt=current_content,
                api_key=api_key,
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system_message=system_message,
                deep_thought=True,
                timeout=max_wait
            )
        except Exception as e:
            print(f"Error: 第 {idx} 次 API 调用失败: {e}", file=sys.stderr)
            return None
        
        if not result or not isinstance(result, str):
            print(f"Error: 第 {idx} 次 API 调用未返回有效字符串。", file=sys.stderr)
            return None
        
        current_content = result
        save_iteration_data(output_dir, f"{idx}", "gen", current_content)
    
    for loop in range(1, val_iter + 1):
        print(f"\n=== 验证阶段迭代 {loop}/{val_iter} ===")
        
        save_iteration_data(output_dir, f"{loop}_pre", "gen", current_content)
        
        print(f"生成 {val_problems} 道选择题...")
        questions = generate_questions(
            content=content,
            api_key=api_key,
            model=model,
            num_questions=val_problems,
            timeout=max_wait
        )
        
        if not questions:
            print("题目生成失败，跳过反馈循环")
            continue
        
        q_path = save_iteration_data(output_dir, loop, "val", questions)
        print(f"已保存选择题: {q_path}")
        
        print("尝试使用摘要解答选择题...")
        answers, results = solve_questions_with_cheatsheet(
            questions=questions,
            cheatsheet=current_content,
            api_key=api_key,
            model=model,
            timeout=max_wait
        )
        
        if not answers or not results:
            print("题目解答失败，跳过反馈循环")
            continue
        
        a_path = save_iteration_data(output_dir, loop, "result", answers)
        print(f"已保存解答: {a_path}")
        
        vis_path, result_path = generate_visualization(results, output_dir, loop)
        if vis_path and result_path:
            print(f"已保存可视化: {vis_path}")
            print(f"已保存详细结果: {result_path}")
        
        unsolved_questions = []
        if results:
            for r in results:
                if "question" in r and "status" in r:
                    if "无法解答" in r["status"] or "错误" in r["status"]:
                        unsolved_questions.append(r["question"])
        
        print(f"发现 {len(unsolved_questions)} 道无法解答的题目")
        
        unsolved_text = "\n".join([f"- {q}" for q in unsolved_questions[:10]])
        prompt = (
            f"当前摘要：\n{current_content}\n\n"
            f"原始文本：\n{content}...\n\n"
            f"无法解答的题目：\n{unsolved_text}\n\n"
            f"任务：优化摘要以覆盖未解答题目所需的知识点，同时保持严格不超过 {final_limit} 字。"
            "优化策略："
            "1. 保留所有已覆盖的知识点"
            "2. 添加解答题目所需的关键信息"
            "3. 删除相对次要的内容以保持长度"
            "4. 确保新摘要能解答上述题目"
        )
        
        system_message = (
            "您是一位更高级的考试复习摘要专家（迭代{idx}）。基于上一次结果，精简至严格不超过 {limit} 字，如果你要加入新的内容，请务必保证加入后也满足字数要求："
            "请首先评估当前摘要长度，若超过限制，务必进一步删除非核心内容；"
            "确认覆盖所有核心考点；保留**加粗**，弱化或删除~划掉~；"
            "优化表达，增加记忆提示；保持逻辑连贯、易快速浏览；"
            "同时，请始终满足以下要求：\n"
            "要求："
            "1. 分析未解答题目缺失的知识点"
            "2. 从原始文本中提取必要信息添加到摘要"
            "3. 删除相对次要的内容以保持长度限制"
            "4. 确保新摘要能解答这些题目"
            "5. 保持Markdown格式和重点标注"
            f"最终摘要必须严格不超过 {final_limit} 字"
        )
        
        print("基于反馈优化摘要...")
        try:
            optimized_summary = call_deepseek_api(
                prompt=prompt,
                api_key=api_key,
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system_message=system_message,
                timeout=max_wait
            )
            current_content = optimized_summary
            save_iteration_data(output_dir, f"{loop}_post", "gen", current_content)
            print(f"验证迭代 {loop} 完成，摘要已更新")
        except Exception as e:
            print(f"摘要优化失败: {e}", file=sys.stderr)
            break
    
    save_iteration_data(output_dir, "final", "gen", current_content)
    return current_content

def main():
    parser = argparse.ArgumentParser(description="生成考试复习备忘录")
    parser.add_argument("--filename", required=True, help="输入文件路径，例如 input.txt")
    parser.add_argument("--maxtoken", required=True, type=int, help="输入你对字数的限制，例如 4096")
    parser.add_argument("--apikey", required=True, type=str, help="输入你的 apikey，例如 sk-xxxx")
    parser.add_argument("--output_dir", help="输出目录", default="output")
    
    parser.add_argument("--geniter", type=int, default=DEFAULT_GEN_ITER, 
                       help=f"生成阶段迭代轮数 (默认: {DEFAULT_GEN_ITER})")
    parser.add_argument("--valiter", type=int, default=DEFAULT_VAL_ITER, 
                       help=f"验证阶段迭代轮数 (默认: {DEFAULT_VAL_ITER})")
    parser.add_argument("--valproblems", type=int, default=DEFAULT_VAL_PROBLEMS, 
                       help=f"每次验证生成的题目数量 (默认: {DEFAULT_VAL_PROBLEMS})")
    parser.add_argument("--maxwait", type=int, default=DEFAULT_MAX_WAIT, 
                       help=f"每次API调用的最大等待时间(秒) (默认: {DEFAULT_MAX_WAIT})")
    
    args = parser.parse_args()

    content = read_file_content(args.filename)
    if content is None: sys.exit(1)
    
    try:
        final_limit = args.maxtoken
        if final_limit <= 0: raise ValueError
    except Exception:
        print("错误: 字数限制需大于 0。", file=sys.stderr)
        sys.exit(1)

    api_key = args.apikey
    if not api_key:
        print("错误: API key 未提供。", file=sys.stderr)
        sys.exit(1)
    
    output_dir = create_output_dir(args.output_dir)
    print(f"所有输出文件将保存到: {output_dir}")
    
    print("\n=== 配置参数 ===")
    print(f"超时设置: {args.maxwait}秒")
    print(f"最终字数限制: {final_limit}字")
    print(f"生成阶段迭代轮数: {args.geniter}")
    print(f"验证阶段迭代轮数: {args.valiter}")
    print(f"题目数量: {args.valproblems}道选择题/验证迭代")
    
    model = "deepseek-reasoner"
    final_result = iterative_summarize(
        content, 
        api_key=api_key, 
        model=model,
        final_limit=final_limit,
        output_dir=output_dir,
        gen_iter=args.geniter,
        val_iter=args.valiter,
        val_problems=args.valproblems,
        max_wait=args.maxwait
    )
    
    if final_result is None:
        print("Error: 摘要过程失败。", file=sys.stderr)
        sys.exit(1)
        
    output_path = os.path.join(output_dir, "final_summary.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_result)
    print(f"\n=== 最终结果 ===")
    print(f"最终摘要已成功生成并保存到: {output_path}")
    print(f"摘要长度: {count_visible_chars(final_result)}字")
    
    print("\n=== 输出文件说明 ===")
    print("| 文件名             | 说明                                                         |")
    print("|--------------------|--------------------------------------------------------------|")
    print("| gen0_raw.txt       | 原始输入文本                                                 |")
    print("| genX.txt           | Stage 1 的第 X 轮的输出                                           |")
    print("| genX_pre.txt       | Stage 2 的第 X 轮的输入                                        |")
    print("| valX.txt           | Stage 2 的第 X 轮的验证题目                                     |")
    print("| resultX.txt        | Stage 2 的第 X 轮的题目解答                                    |")
    print("| resultX.json       | Stage 2 的第 X 轮的题目解答的统计                               |")
    print("| visualX.txt        | Stage 2 的第 X 轮的题目解答的可视化颜色条                        |")
    print("| genX_post.txt      | Stage 2 的第 X 轮的输出                                 |")
    print("| final_summary.txt  | 最终输出                                             |")

if __name__ == "__main__":
    main()