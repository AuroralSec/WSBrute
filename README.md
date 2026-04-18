# WSBrute v4.0 - WebShell 暴力破解工具

## 工具简介

WSBrute v4.0 是一款专业的 WebShell 密码暴力破解工具，支持多种 WebShell 类型（PHP、ASP、ASPX、JSP），以及加密 WebShell（Godzilla、Behinder）。具备 WAF 绕过、多线程并发、智能策略检测、断点续传等高级功能。适用于授权渗透测试和安全审计场景。

## 主要特性

### 核心功能

- **多类型支持**：支持 PHP、ASP、ASPX、JSP 等多种 WebShell 类型
- **加密Shell支持**：内置 Godzilla（哥斯拉）和 Behinder（冰蝎）加密 WebShell 策略
- **智能检测**：自动检测目标 WebShell 类型，选择最佳攻击策略
- **WAF 绕过**：内置 10 种 WAF 绕过技术
- **多线程并发**：支持自定义线程数，大幅提升破解效率
- **速率限制**：支持 QPS 限制，避免触发目标防护
- **断点续传**：支持从中断处继续，自动保存进度
- **代理支持**：支持 HTTP/HTTPS 代理
- **自定义请求头**：支持 Cookie、Authorization 等自定义 Header
- **SSL 验证**：可选择跳过 SSL 证书验证
- **结果保存**：支持将结果保存到文件

### WAF 绕过模式

| 模式 | 名称 | 说明 |
|:----:|------|------|
| 1 | 正常 | 不进行任何绕过 |
| 2 | URL 编码 | 对 payload 进行 URL 编码 |
| 3 | 双重 URL 编码 | 双重 URL 编码 |
| 4 | Base64 编码 | Base64 编码 payload |
| 5 | 十六进制编码 | 转换为十六进制 |
| 6 | Unicode 编码 | Unicode 编码 |
| 7 | 大小写混淆 | 随机切换大小写 |
| 8 | 注释插入 | 在关键位置插入注释 |
| 9 | 随机空白字符 | 添加随机空白字符 |
| 10 | 特殊字符混淆 | 添加特殊字符混淆 |

## 环境要求

- Python 3.6+
- requests 库
- urllib3 库

## 安装说明

### 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install requests urllib3
```

## 使用方法

### 基本语法

```bash
python WSBrute.py -u <目标URL> [-p <密码文件>]
```

### 常用示例

#### 1. 基本使用

```bash
python WSBrute.py -u http://target.com/shell.php
```

#### 2. 指定密码文件

```bash
python WSBrute.py -u http://target.com/shell.php -p passwords.txt
```

#### 3. 多线程加速

```bash
python WSBrute.py -u http://target.com/shell.php -t 20
```

#### 4. 设置请求延迟（防封禁）

```bash
python WSBrute.py -u http://target.com/shell.php -t 10 -d 0.5
```

#### 5. 使用 WAF 绕过

```bash
python WSBrute.py -u http://target.com/shell.php --waf-bypass 2
```

#### 6. 指定 Shell 类型

```bash
python WSBrute.py -u http://target.com/shell.php --shell-type godzilla
```

#### 7. 自定义参数名

```bash
python WSBrute.py -u http://target.com/shell.php --param-name pass --second-param data
```

#### 8. 使用代理

```bash
python WSBrute.py -u http://target.com/shell.php --proxy http://127.0.0.1:8080
```

#### 9. 使用 Cookie 认证

```bash
python WSBrute.py -u http://target.com/shell.php --cookie "PHPSESSID=abc123; security=low"
```

#### 10. 添加自定义 Header

```bash
python WSBrute.py -u http://target.com/shell.php -H "Authorization: Bearer xxx" -H "X-Custom: value"
```

#### 11. 限制请求速率

```bash
python WSBrute.py -u http://target.com/shell.php --qps 10
```

#### 12. 自定义成功标记

```bash
python WSBrute.py -u http://target.com/shell.php --success-string "welcome back"
```

#### 13. 使用正则表达式判断成功

```bash
python WSBrute.py -u http://target.com/shell.php --success-regex "password.*correct"
```

#### 14. 跳过 SSL 验证

```bash
python WSBrute.py -u https://target.com/shell.php --no-ssl-verify
```

#### 15. 保存结果到文件

```bash
python WSBrute.py -u http://target.com/shell.php --output result.txt
```

#### 16. 调试模式

```bash
python WSBrute.py -u http://target.com/shell.php --debug
```

## 参数说明

### 必填参数

| 参数 | 说明 |
|------|------|
| `-u, --url` | 目标 WebShell URL 地址（必填） |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-p, --password-file` | ShellPwd.txt | 密码字典文件路径 |
| `-t, --threads` | 10 | 工作线程数 |
| `-d, --delay` | 0 | 请求间隔延迟（秒） |
| `--waf-bypass` | 1 | WAF 绕过模式（1-10） |
| `--shell-type` | auto | Shell 类型（php/godzilla/behinder/asp/jsp） |
| `--param-name` | password | POST 参数名 |
| `--second-param` | data | 加密 Shell 第二个参数名 |
| `--success-string` | _brute_test_force_ | 自定义成功标记字符串 |
| `--success-regex` | None | 自定义成功判断正则表达式 |
| `--timeout` | 30 | 请求超时时间（秒） |
| `--no-ssl-verify` | False | 跳过 SSL 证书验证 |
| `--qps` | 0 | 每秒最大请求数（0=不限制） |
| `--proxy` | None | 代理服务器地址 |
| `--cookie` | None | Cookie 请求头 |
| `-H, --header` | [] | 自定义 HTTP 请求头（可多次使用） |
| `--retry` | 3 | 连接失败重试次数 |
| `--output` | None | 结果输出文件路径 |
| `--debug` | False | 启用调试日志 |

## Shell 类型说明

### PHP Simple

简单的 PHP WebShell，直接 POST 密码参数执行命令。

### Godzilla（哥斯拉）

加密型 WebShell（常见于 PHP、JSP 等），使用 XOR 或 AES 加密。常用参数组合：`--param-name pass --second-param z0`

### Behinder（冰蝎）

加密型 WebShell，使用 AES 加密。常用参数组合：`--param-name pass --second-param data`

### ASP/ASPX

Microsoft ASP/ASP.NET WebShell。

### JSP

Java WebShell。

## 工作原理

1. **URL 验证**：确保目标 URL 格式正确，自动添加 http:// 前缀

2. **策略选择**：
   - 若指定 `--shell-type`，使用指定策略
   - 否则自动检测：发送测试请求，根据响应特征选择最佳策略

3. **基线建立**：发送空 POST 请求建立响应基线（长度、状态码、哈希）

4. **密码尝试**：
   - 多线程并发从密码文件读取密码
   - 根据策略构建请求
   - 应用 WAF 绕过技术（若启用）
   - 发送请求并判断响应

5. **结果判断**：
   - 首先检查响应是否包含成功标记
   - 若配置了正则表达式，测试正则匹配
   - 对比响应长度与基线的差异（超过 1.5 倍阈值）
   - 对比响应哈希与基线的差异

6. **成功输出**：找到正确密码后输出，并保存到文件（若指定）

## 密码文件格式

密码文件应为纯文本格式，每行一个密码：

```
admin
password
123456
letmein
...
```

支持多种编码格式（UTF-8、GBK、BIG5 等），程序会自动尝试解码。

## 恢复功能

程序会自动保存进度到 `.resume` 文件，当中断后重新运行时，会自动从上次中断处继续。

恢复文件名格式：`{密码文件}_{URL哈希前8位}.resume`

## 注意事项

1. **合法性声明**：本工具仅适用于授权的安全测试和渗透测试，使用前请确保已获得明确授权
2. **网络环境**：确保网络连接稳定，避免频繁中断
3. **频率控制**：根据目标服务器性能合理设置线程数、延迟和 QPS
4. **密码字典**：建议使用高质量的密码字典以提高成功率
5. **代理使用**：在高安全性目标上建议使用代理以防止被封禁
6. **WAF 绕过**：部分绕过技术可能不适用于所有目标，请根据实际情况选择

## 性能优化建议

- **小字典**（<1000）：线程数 10-20
- **中等字典**（1000-10000）：线程数 20-50，QPS 限制 50-100
- **大字典**（>10000）：线程数 50，QPS 限制 100+，使用代理

## 示例输出

### 成功示例

```
WSBrute v4.0 - WebShell Brute Force Tool
Target: http://target.com/shell.php
Password file: ShellPwd.txt
Threads: 10
Delay: 0s
WAF bypass: 1
Timeout: 30s
SSL verify: True
Total passwords: 100

[Progress] 50/100 (50.00%) - 10.23 p/s

✓ Password found: admin123
Time elapsed: 4.89 seconds
```

### 未找到示例

```
WSBrute v4.0 - WebShell Brute Force Tool
Target: http://target.com/shell.php
Password file: ShellPwd.txt
Threads: 10
Total passwords: 100

✗ No password found
Time elapsed: 9.78 seconds
```

## 版本信息

**版本**：4.0
**更新日期**：2026-04-18

## 技术支持

如有问题或建议，请通过 Issues 反馈。
