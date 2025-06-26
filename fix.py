import os
import fitz  # PyMuPDF
import requests
import json
import logging
import os
import sys
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Union, List, Dict, Generator

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DeepSeekAPI")

def create_retry_session(
    retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: tuple = (500, 502, 504),
    session: Optional[requests.Session] = None,
) -> requests.Session:
    """创建带有重试机制的请求会话"""
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def call_deepseek_api(
    prompt: str,
    api_key: str,
    model: str = "deepseek-reasoner",
    stream: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.7,
    top_p: float = 1.0,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
    stop: Optional[Union[str, List[str]]] = None,
    n: int = 1,
    logprobs: bool = False,
    top_logprobs: Optional[int] = None,
    user: Optional[str] = None,
    seed: Optional[int] = None,
    response_format: Optional[Dict] = None,
    enable_web_search: bool = False,
    deep_thought: bool = False,
    system_message: Optional[str] = None,
    timeout: Union[int, float] = 120,
    stream_timeout: Union[int, float] = 300,
    session: Optional[requests.Session] = None,
    retries: int = 3,
    backoff_factor: float = 0.3,
    **kwargs
) -> Union[str, List[str], Generator[str, None, None]]:
    
    url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 构建消息系统
    messages = []
    
    # 添加系统消息（如果提供）
    if system_message:
        messages.append({"role": "system", "content": system_message})
    
    # 添加深度思考指令（如果启用）
    if deep_thought:
        messages.append({"role": "system", "content": "请进行深度思考，逐步分析问题"})
    
    # 添加联网搜索指令（如果启用）
    if enable_web_search:
        messages.append({"role": "system", "content": "你可以使用联网搜索功能获取最新信息"})
    
    # 添加用户消息
    messages.append({"role": "user", "content": prompt})
    
    # 构建请求数据
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
        "temperature": temperature,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "n": n
    }
    
    # 添加可选参数
    if stop is not None:
        data["stop"] = stop
    if logprobs:
        data["logprobs"] = logprobs
    if top_logprobs is not None:
        data["top_logprobs"] = top_logprobs
    if user is not None:
        data["user"] = user
    if seed is not None:
        data["seed"] = seed
    if response_format is not None:
        data["response_format"] = response_format
    
    # 添加其他API参数
    data.update(kwargs)
    
    try:
        # 创建带重试机制的会话
        session = create_retry_session(
            retries=retries,
            backoff_factor=backoff_factor,
            session=session
        )
        
        if stream:
            # 流式处理 - 返回生成器
            logger.info(f"发送流式请求到DeepSeek API，超时={stream_timeout}秒")
            response = session.post(
                url,
                headers=headers,
                json=data,
                stream=True,
                timeout=stream_timeout
            )
            response.raise_for_status()
            
            def content_generator():
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            json_str = decoded_line[5:].strip()
                            if json_str == "[DONE]":
                                logger.info("流式响应完成")
                                break
                            try:
                                chunk = json.loads(json_str)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        content = delta["content"]
                                        # 确保内容始终是字符串且不为None
                                        if content is None:
                                            logger.debug("收到空内容块，跳过")
                                            continue
                                        content_str = str(content)
                                        yield content_str
                            except json.JSONDecodeError:
                                logger.warning("JSON解析错误，跳过数据块")
                                continue
                
            return content_generator()
            
        else:
            # 非流式处理 - 返回字符串
            logger.info(f"发送请求到DeepSeek API，超时={timeout}秒")
            response = session.post(
                url,
                headers=headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # 处理多个响应
            if n > 1:
                responses = []
                for choice in result['choices']:
                    content = choice['message']['content']
                    # 确保内容不为None
                    if content is None:
                        content = ""
                    responses.append(str(content))
                return responses
            
            content = result['choices'][0]['message']['content']
            # 确保内容不为None
            if content is None:
                content = ""
            return str(content)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API请求错误: {str(e)}")
        return f"API请求错误: {str(e)}"
    except (KeyError, IndexError):
        logger.error("响应解析错误: 无效的API响应格式")
        return "响应解析错误: 无效的API响应格式"
    except json.JSONDecodeError:
        logger.error("JSON解析错误: 无效的API响应格式")
        return "JSON解析错误: 无效的API响应格式"

def save_file(path: str, content: str) -> None:
    """保存内容到文件"""
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # 确保内容为字符串且不为None
    if content is None:
        content = ""
    content = str(content)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"内容已保存至 {path}")

def save_stream_thoughts(path: str, generator: Generator[str, None, None]) -> str:
    """
    保存流式输出的思考过程
    
    参数:
        path: 保存思考过程的文件路径
        generator: 流式响应生成器
        
    返回:
        完整响应内容（不含None）
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    full_response = ""
    try:
        # 打开文件用于实时写入思考过程
        with open(path, "w", encoding="utf-8") as f_thoughts:
            for chunk in generator:
                # 确保chunk是字符串且不为None
                if chunk is None:
                    logger.debug("收到空块，跳过")
                    continue
                    
                chunk_str = str(chunk)
                
                # 打印到控制台（可选）
                print(chunk_str, end='', flush=True)
                
                # 写入思考过程文件（仅写入当前块）
                f_thoughts.write(chunk_str)
                f_thoughts.flush()  # 确保实时写入
                
                # 拼接完整响应
                full_response += chunk_str
                
    except Exception as e:
        logger.error(f"保存思考过程时出错: {str(e)}")
    
    logger.info(f"思考过程已保存至 {path}")
    return full_response

def save_stream_result(path: str, content: str) -> None:
    """
    保存流式输出的最终结果
    
    参数:
        path: 保存最终结果的文件路径
        content: 完整响应内容
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # 确保内容为字符串且不为None
    if content is None:
        content = ""
    content = str(content)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"最终结果已保存至 {path}")

def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    full_text = []

    for page in doc:
        text = page.get_text("text")  # 提取格式化文本（包括中文、代码缩进）
        full_text.append(text)

    doc.close()
    return "\n".join(full_text)

def save_to_file(text: str, output_path: str = "output.txt"):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    pdf_file = "lec3-rand-alg.pdf"  

    content = extract_text_from_pdf(pdf_file)

    prompt = content

    with open("prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)

    import subprocess

    subprocess.run([
        "python", "callapi.py",
        "--api_key", "sk-c30706e4088c471e9aa44cabc1de677f",
        "--prompt", prompt,  # 安全传入长字符串
        "--system_message", "这些是一门课程的课件或者笔记，你需要注意：我们直接通过某种工具将其转换成了纯文本，可能会造成格式错误，乱码或者信息丢失，请务必先根据已有的知识进行修复，然后逐字逐句的以 Markdown 的格式输出，你需要用 $ 包裹公式而不是括号和斜杠，输出修复后的内容，不要进行包括概括，内容拓展等的任何操作！！！",
        "--model", "deepseek-reasoner",
        "--max_tokens", "16384",
        "--deep_thought", "True",
        "--timeout", "1145",
        "--stream", "False"
    ])