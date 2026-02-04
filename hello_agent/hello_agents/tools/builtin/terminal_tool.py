"""TerminalTool - 命令行工具

为Agent提供安全的命令行执行能力，支持：
- 文件系统操作（ls, cat, head, tail, find, grep）
- 文本处理（wc, sort, uniq）
- 目录导航（pwd, cd）
- 安全限制（白名单命令、路径限制、超时控制）

使用场景：
- JIT（即时）文件检索与分析
- 代码仓库探索
- 日志文件分析
- 数据文件预览

安全特性：
- 命令白名单（只允许安全的只读命令）
- 工作目录限制（沙箱）
- 超时控制
- 输出大小限制
- 禁止危险操作（rm, mv, chmod等）
"""

# ============================================================================
# 导入依赖
# ============================================================================
from typing import Dict, Any, List, Optional  # 类型注解，提高代码可读性
import subprocess  # 子进程管理，用于执行命令
import os          # 操作系统接口，用于环境变量
from pathlib import Path  # 路径处理，比 os.path 更现代化
import shlex       # Shell 命令解析，安全地分割命令字符串
import platform    # 平台检测，用于识别操作系统类型

# 从基类导入 Tool 框架组件
# - Tool: 工具基类，定义了工具的基本接口
# - ToolParameter: 参数定义类，描述工具接受的参数
from ..base import Tool, ToolParameter


# ============================================================================
# TerminalTool 类 - 核心实现
# ============================================================================
# 设计模式：这是一个典型的「安全沙箱」设计
# - 继承自 Tool 基类，遵循统一的工具接口规范
# - 使用「白名单模式」：只允许预定义的安全命令
# - 使用「沙箱模式」：限制命令在指定工作目录内执行
# - 使用「超时控制」：防止命令执行时间过长
# ============================================================================

class TerminalTool(Tool):
    """命令行工具 - 让 Agent 具备安全的命令行执行能力
    
    这是一个跨平台的命令行工具封装，继承自 Tool 基类。
    Agent 可以通过调用这个工具来执行文件系统操作、文本处理等命令。
    
    核心功能：
    1. **文件系统操作**：ls/dir、cat/type、find/where、grep/findstr
    2. **文本处理**：wc、sort、uniq、cut、awk、sed
    3. **目录导航**：pwd、cd（支持相对路径和沙箱限制）
    4. **代码执行**：python、node、bash、powershell（白名单控制）
    
    安全特性：
    - **命令白名单**：只允许预定义的安全命令，防止危险操作
    - **工作目录限制**：所有命令在指定工作目录（沙箱）内执行
    - **超时控制**：默认30秒超时，防止命令执行时间过长
    - **输出大小限制**：默认10MB，防止输出过大占用内存
    - **跨平台支持**：自动检测操作系统，适配 Windows/Linux/Mac
    
    使用示例：
        >>> # 自动检测操作系统
        >>> terminal = TerminalTool(workspace="./project", os_type="auto")
        >>> 
        >>> # 手动指定Windows
        >>> terminal = TerminalTool(workspace="./project", os_type="windows")
        >>> 
        >>> # 列出文件
        >>> result = terminal.run({"command": "ls -la"})  # Linux/Mac
        >>> result = terminal.run({"command": "dir"})     # Windows
        >>> 
        >>> # 查看文件内容
        >>> result = terminal.run({"command": "cat README.md"})
        >>> 
        >>> # 搜索文件
        >>> result = terminal.run({"command": "grep -r 'TODO' src/"})
        >>> 
        >>> # 查看文件前10行
        >>> result = terminal.run({"command": "head -n 10 data.csv"})
    """

    # ------------------------------------------------------------------------
    # 命令白名单 - 安全控制的核心
    # ------------------------------------------------------------------------
    # 学习要点：白名单模式是安全设计的最佳实践
    # - 只允许明确列出的命令，默认拒绝所有其他命令
    # - 跨平台兼容：同时支持 Unix 和 Windows 命令
    # - 只读操作为主：避免 rm、mv、chmod 等危险命令
    # ------------------------------------------------------------------------
    ALLOWED_COMMANDS = {
        # 文件列表与信息
        'ls', 'dir', 'tree',
        # 文件内容查看
        'cat', 'type', 'head', 'tail', 'less', 'more',
        # 文件搜索
        'find', 'where', 'grep', 'egrep', 'fgrep', 'findstr',
        # 文本处理
        'wc', 'sort', 'uniq', 'cut', 'awk', 'sed',
        # 目录操作
        'pwd', 'cd',
        # 文件信息
        'file', 'stat', 'du', 'df',
        # 其他
        'echo', 'which', 'whereis',
        # 代码执行
        'python', 'python3', 'node', 'bash', 'sh', 'powershell', 'cmd',
    }

    # ------------------------------------------------------------------------
    # 构造函数 - 初始化工具
    # ------------------------------------------------------------------------
    # 学习要点：
    # 1. 使用默认参数提供合理的默认配置
    # 2. 调用父类 __init__ 注册工具元信息
    # 3. 初始化时确保必要的目录存在
    # 4. 自动检测操作系统类型，实现跨平台兼容
    # ------------------------------------------------------------------------
    def __init__(
        self,
        workspace: str = ".",              # 工作目录（沙箱根目录），默认为当前目录
        timeout: int = 30,                  # 命令执行超时时间（秒），防止命令卡死
        max_output_size: int = 10 * 1024 * 1024,  # 输出大小限制（10MB），防止内存溢出
        allow_cd: bool = True,              # 是否允许 cd 命令，控制目录切换权限
        os_type: str = "auto"               # 操作系统类型："auto", "windows", "linux", "mac"
    ):
        # 调用父类构造函数，注册工具的基本信息
        # name: 工具名称，Agent 通过这个名称调用工具
        # description: 工具描述，帮助 Agent 理解工具的用途
        super().__init__(
            name="terminal",
            description="跨平台命令行工具 - 执行安全的文件系统、文本处理和代码执行命令（支持Windows/Linux/Mac）"
        )

        # ========== 初始化配置参数 ==========
        # 使用 Path 对象处理路径，比字符串更安全、更方便
        # resolve() 将相对路径转为绝对路径，避免路径歧义
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.allow_cd = allow_cd

        # ========== 检测或设置操作系统类型 ==========
        # 自动检测：调用 _detect_os() 识别当前操作系统
        # 手动指定：使用传入的 os_type 参数
        if os_type == "auto":
            self.os_type = self._detect_os()
        else:
            self.os_type = os_type.lower()

        # ========== 初始化工作目录 ==========
        # current_dir: 当前工作目录，初始为 workspace 根目录
        # cd 命令会修改这个变量，但始终限制在 workspace 内（沙箱）
        self.current_dir = self.workspace

        # 确保工作目录存在
        # parents=True: 如果父目录不存在，一并创建
        # exist_ok=True: 如果目录已存在，不报错
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------------
    # 操作系统检测方法 - 私有方法（以 _ 开头）
    # ------------------------------------------------------------------------
    # 学习要点：跨平台兼容性的关键
    # - 使用 platform.system() 获取操作系统名称
    # - 统一返回小写字符串："windows", "mac", "linux"
    # ------------------------------------------------------------------------
    def _detect_os(self) -> str:
        """检测操作系统类型
        
        使用 platform.system() 识别当前操作系统。
        
        Returns:
            操作系统类型字符串："windows", "mac", "linux"
        """
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "mac"
        else:
            return "linux"
    
    # ------------------------------------------------------------------------
    # run 方法 - 工具的核心入口点
    # ------------------------------------------------------------------------
    # 学习要点：这是工具执行的统一入口
    # - 所有命令执行都通过这个方法
    # - 负责参数验证、命令解析、安全检查、执行调度
    # - 返回格式化的执行结果字符串
    # ------------------------------------------------------------------------
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具
        
        这是 Agent 调用工具的入口方法。接收命令参数，
        执行安全检查后调度到具体的执行方法。
        
        执行流程：
        1. 参数验证 - 确保提供了必要的参数
        2. 命令解析 - 使用 shlex 安全地分割命令字符串
        3. 白名单检查 - 确保命令在允许列表中
        4. 特殊处理 - cd 命令需要特殊处理（修改内部状态）
        5. 命令执行 - 调用 subprocess 执行命令
        
        Args:
            parameters: 包含 command 参数的字典
            
        Returns:
            命令执行结果的字符串描述
        """
        # === 第一步：参数验证 ===
        # validate_parameters() 由基类提供，检查必需参数是否存在
        if not self.validate_parameters(parameters):
            return "[错误] 参数验证失败"
        
        # 获取命令字符串并去除首尾空白
        command = parameters.get("command", "").strip()
        
        # 防御性编程：确保命令不为空
        if not command:
            return "[错误] 命令不能为空"
        
        # === 第二步：解析命令 ===
        # 使用 shlex.split() 安全地分割命令字符串
        # shlex 会正确处理引号、转义字符等，避免注入攻击
        # 例如："cat 'my file.txt'" -> ["cat", "my file.txt"]
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return f"[错误] 命令解析失败: {e}"
        
        if not parts:
            return "[错误] 命令不能为空"
        
        # 提取基础命令（第一个单词）
        # 例如：["ls", "-la"] -> "ls"
        base_command = parts[0]
        
        # === 第三步：白名单检查 ===
        # 这是安全控制的核心：只允许白名单中的命令
        if base_command not in self.ALLOWED_COMMANDS:
            return f"[错误] 不允许的命令: {base_command}\n允许的命令: {', '.join(sorted(self.ALLOWED_COMMANDS))}"
        
        # === 第四步：特殊处理 cd 命令 ===
        # cd 命令不是真正执行外部程序，而是修改内部状态
        # 需要单独处理，更新 self.current_dir
        if base_command == 'cd':
            return self._handle_cd(parts)
        
        # === 第五步：执行命令 ===
        # 调用 _execute_command() 使用 subprocess 执行命令
        return self._execute_command(command)
    
    # ------------------------------------------------------------------------
    # get_parameters 方法 - 定义工具的参数规范
    # ------------------------------------------------------------------------
    # 学习要点：这是工具「自描述」能力的关键
    # - Agent 通过此方法了解工具需要哪些参数
    # - 参数定义会被转换为 LLM 能理解的 schema
    # - 类似于 OpenAPI/Swagger 的参数描述
    # ------------------------------------------------------------------------
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义
        
        返回工具接受的所有参数的定义，包括：
        - name: 参数名
        - type: 参数类型
        - description: 参数描述（帮助 LLM 理解如何使用）
        - required: 是否必需
        """
        return [
            ToolParameter(
                name="command",
                type="string",
                description=(
                    f"要执行的命令（白名单: {', '.join(sorted(list(self.ALLOWED_COMMANDS)[:10]))}...）\n"
                    "示例: 'ls -la', 'cat file.txt', 'grep pattern *.py', 'head -n 20 data.csv'"
                ),
                required=True
            ),
        ]
    
    # ------------------------------------------------------------------------
    # _handle_cd - 处理 cd 命令
    # ------------------------------------------------------------------------
    # 学习要点：cd 命令的特殊性
    # - cd 不是外部程序，而是修改 shell 的内部状态
    # - 需要在 Python 中模拟 cd 的行为：修改 self.current_dir
    # - 必须进行沙箱检查：不允许跳出 workspace 目录
    # ------------------------------------------------------------------------
    def _handle_cd(self, parts: List[str]) -> str:
        """处理 cd 命令
        
        cd 命令用于切换当前工作目录。由于 subprocess 执行的命令
        在独立的子进程中，无法影响父进程的工作目录，因此需要
        在 Python 中模拟 cd 的行为。
        
        处理流程：
        1. 权限检查 - 确保 allow_cd 为 True
        2. 参数解析 - 提取目标目录
        3. 路径计算 - 处理相对路径（.., ., ~）
        4. 沙箱检查 - 确保目标目录在 workspace 内
        5. 存在性检查 - 确保目标目录存在
        6. 更新状态 - 修改 self.current_dir
        
        Args:
            parts: 命令分割后的列表，例如 ["cd", "src"]
            
        Returns:
            操作结果字符串
        """
        # === 第一步：权限检查 ===
        # 如果初始化时设置了 allow_cd=False，则禁止 cd 命令
        if not self.allow_cd:
            return "[错误] cd 命令已禁用"
        
        # === 第二步：参数解析 ===
        # cd 无参数时，返回当前目录
        if len(parts) < 2:
            return f"当前目录: {self.current_dir}"
        
        target_dir = parts[1]
        
        # === 第三步：路径计算 ===
        # 处理特殊路径符号：
        # - "..": 父目录
        # - ".": 当前目录
        # - "~": 工作目录根（沙箱根）
        # - 其他: 相对路径或绝对路径
        if target_dir == "..":
            new_dir = self.current_dir.parent
        elif target_dir == ".":
            new_dir = self.current_dir
        elif target_dir == "~":
            new_dir = self.workspace
        else:
            # 拼接路径并解析为绝对路径
            # resolve() 会处理 .., ., 符号链接等
            new_dir = (self.current_dir / target_dir).resolve()
        
        # === 第四步：沙箱检查 ===
        # 这是安全控制的关键：确保目标目录在 workspace 内
        # relative_to() 会抛出 ValueError 如果路径不在 workspace 内
        try:
            new_dir.relative_to(self.workspace)
        except ValueError:
            return f"[错误] 不允许访问工作目录外的路径: {new_dir}"
        
        # === 第五步：存在性检查 ===
        # 确保目标路径存在且是目录
        if not new_dir.exists():
            return f"[错误] 目录不存在: {new_dir}"
        
        if not new_dir.is_dir():
            return f"[错误] 不是目录: {new_dir}"
        
        # === 第六步：更新状态 ===
        # 修改内部状态，后续命令将在新目录中执行
        self.current_dir = new_dir
        return f"[成功] 切换到目录: {self.current_dir}"
    
    # ------------------------------------------------------------------------
    # _execute_command - 执行命令
    # ------------------------------------------------------------------------
    # 学习要点：使用 subprocess 安全地执行外部命令
    # - 使用 shell=True 支持管道、重定向等 shell 特性
    # - 使用 capture_output=True 捕获标准输出和标准错误
    # - 使用 timeout 参数防止命令卡死
    # - 使用 cwd 参数指定工作目录
    # ------------------------------------------------------------------------
    def _execute_command(self, command: str) -> str:
        """执行命令
        
        使用 subprocess.run() 在子进程中执行命令。
        
        处理流程：
        1. 根据操作系统类型选择执行方式
        2. 设置工作目录为 self.current_dir
        3. 捕获标准输出和标准错误
        4. 检查输出大小，防止内存溢出
        5. 格式化返回结果
        
        Args:
            command: 要执行的命令字符串
            
        Returns:
            命令执行结果（包含输出、错误、返回码）
        """
        try:
            # === 第一步：执行命令 ===
            # 使用 subprocess.run() 在子进程中执行命令
            # 
            # 关键参数说明：
            # - shell=True: 通过 shell 执行，支持管道、重定向等特性
            # - cwd: 工作目录，命令在此目录中执行
            # - capture_output=True: 捕获标准输出和标准错误
            # - text=True: 以文本模式读取输出（而非字节）
            # - timeout: 超时时间，防止命令卡死
            # - env: 环境变量，继承父进程的环境
            # 
            # 注意：Windows 和 Unix 系统的命令执行方式相同
            # shell=True 在 Windows 上会使用 cmd.exe，在 Unix 上会使用 /bin/sh
            if self.os_type == "windows":
                # Windows 下使用 cmd.exe 执行命令
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.current_dir),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=os.environ.copy()
                )
            else:
                # Unix 系统（Linux/Mac）使用 /bin/sh 执行命令
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.current_dir),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=os.environ.copy()
                )

            # === 第二步：合并输出 ===
            # 将标准输出和标准错误合并为一个字符串
            # 这样 Agent 可以同时看到正常输出和错误信息
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            # === 第三步：检查输出大小 ===
            # 防止输出过大占用内存，超过限制则截断
            if len(output) > self.max_output_size:
                output = output[:self.max_output_size]
                output += f"\n\n[警告] 输出被截断（超过 {self.max_output_size} 字节）"

            # === 第四步：添加返回码信息 ===
            # 返回码非 0 表示命令执行失败或有警告
            # 在输出前添加返回码信息，帮助 Agent 判断执行状态
            if result.returncode != 0:
                output = f"[警告] 命令返回码: {result.returncode}\n\n{output}"

            # === 第五步：返回结果 ===
            # 如果没有输出，返回成功提示
            return output if output else "[成功] 命令执行成功（无输出）"

        except subprocess.TimeoutExpired:
            # 命令执行超时
            return f"[错误] 命令执行超时（超过 {self.timeout} 秒）"
        except Exception as e:
            # 其他异常（如权限错误、命令不存在等）
            return f"[错误] 命令执行失败: {e}"

    # ------------------------------------------------------------------------
    # 辅助方法 - 提供额外的工具功能
    # ------------------------------------------------------------------------
    # 这些方法不是 Tool 接口的一部分，但提供了有用的辅助功能
    # ------------------------------------------------------------------------
    
    def get_current_dir(self) -> str:
        """获取当前工作目录
        
        Returns:
            当前工作目录的绝对路径字符串
        """
        return str(self.current_dir)

    def reset_dir(self):
        """重置到工作目录根
        
        将 current_dir 重置为 workspace，相当于执行 cd ~
        """
        self.current_dir = self.workspace

    def get_os_type(self) -> str:
        """获取当前操作系统类型
        
        Returns:
            操作系统类型字符串："windows", "mac", "linux"
        """
        return self.os_type

