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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    # 布尔值转换函数
    def str_to_bool(value):
        """将字符串转换为布尔值"""
        if isinstance(value, bool):
            return value
        if value.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif value.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')
    
    # 修复字符串参数
    parser.add_argument('--prompt', type=str)
    parser.add_argument('--api_key', type=str)
    parser.add_argument('--model', type=str)
    parser.add_argument('--system_message', type=str)
    
    # 修复布尔参数
    parser.add_argument('--stream', type=str_to_bool)
    parser.add_argument('--logprobs', type=str_to_bool)
    parser.add_argument('--enable_web_search', type=str_to_bool)
    parser.add_argument('--deep_thought', type=str_to_bool)
    
    # 修复数字参数
    parser.add_argument('--max_tokens', type=int)
    parser.add_argument('--temperature', type=float)
    parser.add_argument('--top_p', type=float)
    parser.add_argument('--presence_penalty', type=float)
    parser.add_argument('--frequency_penalty', type=float)
    parser.add_argument('--n', type=int)
    parser.add_argument('--top_logprobs', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--retries', type=int)
    parser.add_argument('--backoff_factor', type=float)
    
    # 修复可选参数
    parser.add_argument('--user', type=str)
    
    # 修复复杂类型参数
    # stop 参数处理函数
    def parse_stop(value: str) -> Optional[Union[str, List[str]]]:
        """解析 stop 参数，支持字符串或 JSON 格式的列表"""
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return value
        except json.JSONDecodeError:
            return value
    
    parser.add_argument('--stop', type=parse_stop)
    
    # response_format 参数处理函数
    parser.add_argument('--response_format', type=json.loads)
    
    # 修复超时参数
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--stream_timeout', type=float)
    
    args = parser.parse_args()
    
    # 收集非空参数
    kwargs = {k: v for k, v in vars(args).items() if v is not None}
    
    # API_KEY = "sk-***"
    print("API 已调用...")
    try:
        # 确保传递了必要的参数
        if 'api_key' not in kwargs or 'prompt' not in kwargs:
            raise ValueError("缺少必要参数: api_key 和 prompt 必须提供")
        
        response = call_deepseek_api(**kwargs)
        
        if kwargs.get('stream', False):
            # 流式响应处理
            full_response = save_stream_thoughts("temp\\temp_results.txt", response)
            print("最终结果已保存至 temp\\temp_results.txt")
        else:
            # 非流式响应处理
            save_file("temp\\temp_results.txt", response)  
            print("\n最终结果已保存至 temp\\temp_results.txt")
    except Exception as e:
        print(f"程序出错: {str(e)}")
        sys.exit(1)