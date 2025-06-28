本系统在 Windows 环境下开发，暂未适配 Linux 系统。提供两种交互方式：图形界面（GUI）和命令行（CLI）。

### 环境依赖配置

初次使用时，请在 Anaconda 中执行以下命令创建环境：

```
conda create -n cheatsheetgen python=3.10 
conda activate cheatsheetgen
pip install requests
pip install PyMuPDF
```

后续使用只需激活环境：

```
conda activate cheatsheetgen
```

然后请从此 GitHub 仓库获取代码，将所有代码放在同一目录下。

https://github.com/YunQianQwQ/Intro2AI-Homework/

### 图形化界面调用

执行 `gui.py` 启动图形界面（Figure 1）。选择输入 PDF 文件和输出目录后，系统将自动完成文本转换和处理流程。

如果您想直接处理 TXT 纯文本，请参见下一节“命令行调用方法”。

### 命令行调用方法

将 `gen.py` `callapi.py` 和原始文本（TXT 格式）置于同一目录。

使用以下命令格式：

```
python gen.py --apikey "sk-xxx" --filename "input.txt" --maxtoken 3000 --geniter 2 --valiter 5 --valproblems 50 --maxwait 500
```

参数说明如下：

|   参数名称    |              含义               |
| :-----------: | :-----------------------------: |
|   `apikey`    |          API 访问密钥           |
|  `filename`   |         输入文本文件名          |
|  `maxtoken`   |        最大 Token 数限制        |
|   `geniter`   |        生成阶段迭代次数         |
|   `valiter`   |        验证阶段迭代次数         |
| `valproblems` |        生成验证题目数量         |
|   `maxwait`   | 单次 API 调用最大等待时间（秒） |

 使用注意事项：

- 为保障生成质量，建议参数下限： $maxtoken \ge 1024,geniter \ge 2,valiter \ge 2,valproblems \ge 20,maxwait \ge 120$
- 预估最大耗时：$maxwait \times (geniter + 3 \times valiter)$
- API 响应时间较长，完整流程可能需要约 1 小时
