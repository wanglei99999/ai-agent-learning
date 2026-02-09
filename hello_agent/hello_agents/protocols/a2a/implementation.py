"""
基于官方 a2a-sdk 库的 A2A 协议实现

使用官方 a2a-sdk 库实现 Agent-to-Agent Protocol 功能。
官方仓库: https://github.com/a2aproject/a2a-python
安装: pip install a2a-sdk

【学习笔记 - A2A 协议概述】

A2A (Agent-to-Agent) 协议解决的核心问题：Agent 之间怎么互相对话和协作？

与 MCP 的区别：
- MCP: Agent ↔ 工具/资源（人用工具）
- A2A: Agent ↔ Agent（人和人聊天）

本文件的四个核心类：
1. A2AServer  - 服务端：把 Agent 暴露为 HTTP 服务，注册技能供其他 Agent 调用
2. A2AClient  - 客户端：通过 HTTP 调用其他 Agent 的技能
3. AgentNetwork - 网络管理：维护多个 Agent 的地址簿，统一调度
4. AgentRegistry - 注册中心：Agent 上线/下线的登记处

通信方式：基于 Flask 的 HTTP REST API（不同于 MCP 的 JSON-RPC）

建议阅读顺序：A2AServer → A2AClient → AgentNetwork → AgentRegistry
"""

from typing import Dict, Any, List, Optional
import asyncio

# === 可选依赖导入 ===
# 【学习笔记】
# 与 mcp/__init__.py 相同的"优雅降级"模式：
# - 装了 a2a-sdk：正常使用官方库的类型
# - 没装：设为 None，后续代码通过 A2A_AVAILABLE 标志判断是否可用
# 这样即使没装 a2a-sdk，文件也能被导入，不会直接崩溃
try:
    from a2a.client import A2AClient
    from a2a.types import Message
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    A2AClient = None
    Message = None


class A2AServer:
    """A2A 服务器（使用 Flask 提供 HTTP API）
    
    【学习笔记 - A2A Server 的角色】
    
    A2AServer 把一个 Agent 变成一个 HTTP 服务，让其他 Agent 可以通过网络调用它。
    
    类比：开一家餐厅
    - name/description = 店名和招牌
    - skills = 菜单上的菜品
    - run() = 开门营业
    - 其他 Agent（A2AClient）= 来点菜的顾客
    
    与 MCP Server 的区别：
    - MCP Server: 暴露工具/资源/提示词，用 JSON-RPC 通信，面向 LLM
    - A2A Server: 暴露技能（skill），用 HTTP REST 通信，面向其他 Agent
    
    核心概念 - Skill（技能）：
    - 技能就是一个普通的 Python 函数：接收文本输入，返回文本结果
    - 比 MCP 的 Tool 更简单：没有 JSON Schema，没有复杂的参数定义
    - 适合 Agent 之间的高层交互（问答、委托任务）
    """

    def __init__(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        capabilities: Optional[Dict[str, Any]] = None
    ):
        """
        初始化 A2A 服务器

        【学习笔记】
        这里只是保存配置，不会启动服务。调用 run() 才会真正启动 Flask 服务器。
        这和 MCPClient 的"延迟连接"思想类似：构造时配置，使用时连接。

        Args:
            name: Agent 名称，如 "翻译Agent"
            description: Agent 描述，如 "提供中英翻译服务"
            version: Agent 版本号，遵循语义化版本（主版本.次版本.补丁）
            capabilities: Agent 能力描述字典，如 {"chat": True, "translation": True}
        """
        self.name = name
        self.description = description
        self.version = version
        self.capabilities = capabilities or {}
        # skills 字典：技能名 -> 处理函数
        # 类似 MCP Server 的 tools 注册表
        self.skills = {}

    def add_skill(self, skill_name: str, func):
        """添加技能到服务器
        
        【学习笔记】
        技能注册非常简单：把函数存到字典里，key 是技能名，value 是函数本身。
        
        示例：
            def translate(text: str) -> str:
                return "翻译结果..."
            
            server.add_skill("translate", translate)
        
        注意 return func：返回原函数，这样 add_skill 也可以当装饰器用。
        """
        self.skills[skill_name] = func
        return func

    def skill(self, skill_name: str):
        """装饰器方式添加技能
        
        【学习笔记 - 装饰器注册模式】
        这是 add_skill 的语法糖版本，用 @decorator 语法更优雅：
        
            @server.skill("translate")
            def translate(text: str) -> str:
                return "翻译结果..."
        
        等价于：
            def translate(text: str) -> str:
                return "翻译结果..."
            server.add_skill("translate", translate)
        
        这种模式在 Flask（@app.route）、FastMCP（@server.tool）中都很常见。
        """
        def decorator(func):
            self.add_skill(skill_name, func)
            return func
        return decorator

    def run(self, host: str = "0.0.0.0", port: int = 5000):
        """运行服务器（使用 Flask 提供 HTTP API）
        
        【学习笔记 - Flask 与 REST API】
        
        Flask 是 Python 最流行的轻量级 Web 框架。
        这个方法在 run() 内部定义了所有路由，然后启动 Flask 服务器。
        
        REST API 设计：
        - GET  /info              → 获取 Agent 信息（只读，用 GET）
        - GET  /skills            → 列出所有技能（只读，用 GET）
        - POST /execute/<skill>   → 执行技能（有副作用，用 POST）
        - POST /ask               → 通用问答（有副作用，用 POST）
        - GET  /health            → 健康检查（只读，用 GET）
        
        GET vs POST 的选择原则：
        - GET: 获取数据，不修改状态，可以缓存
        - POST: 提交数据，可能修改状态，不可缓存
        
        Args:
            host: 监听地址，"0.0.0.0" 表示接受所有网络接口的连接
            port: 监听端口，默认 5000
        """
        # === 延迟导入 Flask ===
        # 【学习笔记】
        # 把 import 放在方法内部而不是文件顶部，这是"延迟导入"：
        # - 好处：只有真正运行服务器时才需要 Flask，不运行就不需要装
        # - 场景：如果只用 A2AClient 调用别人，完全不需要 Flask
        try:
            from flask import Flask, request, jsonify
        except ImportError:
            raise ImportError(
                "A2A server requires Flask. Install it with: pip install flask"
            )

        app = Flask(self.name)

        # 禁用 Flask 的日志输出（可选）
        # werkzeug 是 Flask 底层的 HTTP 服务器，默认会打印每个请求的日志
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # === 路由定义 ===
        # 【学习笔记 - Flask 路由】
        # @app.route(路径, methods=[方法]) 把 URL 映射到处理函数
        # 当有 HTTP 请求匹配路径和方法时，Flask 自动调用对应的函数

        @app.route('/info', methods=['GET'])
        def get_info():
            """获取 Agent 信息
            
            返回 Agent 的名称、描述、版本、能力等元信息。
            其他 Agent 通过这个接口了解"你是谁、你能做什么"。
            """
            return jsonify(self.get_info())

        @app.route('/skills', methods=['GET'])
        def list_skills():
            """列出所有技能
            
            类似 MCP 的 list_tools()，让调用方知道有哪些技能可用。
            """
            return jsonify({
                "skills": list(self.skills.keys()),
                "count": len(self.skills)
            })

        @app.route('/execute/<skill_name>', methods=['POST'])
        def execute_skill(skill_name):
            """执行指定技能
            
            【学习笔记 - Flask 动态路由】
            <skill_name> 是 URL 参数，Flask 会自动提取并传给函数。
            例如：POST /execute/translate → skill_name = "translate"
            
            请求体格式：{"text": "要处理的文本"}
            响应格式：{"skill": "translate", "result": "...", "status": "success"}
            """
            if skill_name not in self.skills:
                # 404: 资源未找到，同时返回可用技能列表帮助调试
                return jsonify({
                    "error": f"Skill '{skill_name}' not found",
                    "available_skills": list(self.skills.keys())
                }), 404

            try:
                # 从 POST 请求体中提取 JSON 数据
                data = request.get_json() or {}
                # 兼容两种参数名：text 或 query
                text = data.get('text', data.get('query', ''))

                # 调用技能函数（就是之前 add_skill 注册的那个函数）
                result = self.skills[skill_name](text)

                return jsonify({
                    "skill": skill_name,
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                # 500: 服务器内部错误
                return jsonify({
                    "error": str(e),
                    "skill": skill_name,
                    "status": "error"
                }), 500

        @app.route('/ask', methods=['POST'])
        def ask():
            """通用问答接口（自动选择技能）
            
            【学习笔记 - 技能路由策略】
            与 /execute/<skill> 不同，/ask 不需要指定技能名。
            它会遍历所有技能，尝试每一个，返回第一个成功的结果。
            
            这是一种"暴力匹配"策略，简单但不高效。
            更好的做法是用 LLM 来判断应该调用哪个技能（类似 Agent 的工具选择）。
            """
            try:
                data = request.get_json() or {}
                question = data.get('question', data.get('text', ''))

                # 简单策略：尝试所有技能，返回第一个非错误结果
                for skill_name, skill_func in self.skills.items():
                    try:
                        result = skill_func(question)
                        if result and not result.startswith("Error"):
                            return jsonify({
                                "answer": result,
                                "skill_used": skill_name,
                                "status": "success"
                            })
                    except:
                        continue

                return jsonify({
                    "answer": "No suitable skill found for this question",
                    "status": "no_match"
                })
            except Exception as e:
                return jsonify({
                    "error": str(e),
                    "status": "error"
                }), 500

        @app.route('/health', methods=['GET'])
        def health():
            """健康检查
            
            【学习笔记】
            健康检查是微服务的标准实践。
            负载均衡器、监控系统会定期调用这个接口，确认服务还活着。
            类似 MCP 的 ping() 方法。
            """
            return jsonify({"status": "healthy", "agent": self.name})

        # 启动服务器
        print(f"[启动] A2A 服务器 '{self.name}' 启动在 {host}:{port}")
        print(f"[描述] {self.description}")
        print(f"[技能] 可用技能: {list(self.skills.keys())}")
        print(f"[端点] API 端点:")
        print(f"   - GET  {host}:{port}/info - 获取 Agent 信息")
        print(f"   - GET  {host}:{port}/skills - 列出技能")
        print(f"   - POST {host}:{port}/execute/<skill> - 执行技能")
        print(f"   - POST {host}:{port}/ask - 通用问答")
        print(f"   - GET  {host}:{port}/health - 健康检查")
        print()

        app.run(host=host, port=port, debug=False)

    def get_info(self) -> Dict[str, Any]:
        """获取服务器信息
        
        【学习笔记】
        返回 Agent 的"名片"信息，供其他 Agent 了解自己。
        这个方法既被内部的 /info 路由调用，也可以直接在代码中调用。
        
        返回示例：
        {
            "name": "翻译Agent",
            "description": "提供中英翻译服务",
            "version": "1.0.0",
            "capabilities": {"translation": True},
            "protocol": "A2A",
            "skills": ["translate", "detect_language"]
        }
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": self.capabilities,
            "protocol": "A2A",
            "skills": list(self.skills.keys())
        }


class A2AClient:
    """A2A 客户端（通过 HTTP 与 A2AServer 通信）
    
    【学习笔记 - A2A Client 的角色】
    
    A2AClient 是 A2AServer 的对应方，通过 HTTP 请求调用远程 Agent 的技能。
    
    类比：去餐厅吃饭的顾客
    - server_url = 餐厅地址
    - ask() = 问服务员"有什么推荐？"（自动选菜）
    - execute_skill() = 直接点名要某道菜
    - get_info() = 看餐厅介绍
    - list_skills() = 看菜单
    
    与 MCPClient 的区别：
    - MCPClient: 用 async with 管理连接，异步调用，JSON-RPC 协议
    - A2AClient: 无需管理连接，同步调用，HTTP REST 协议
    
    为什么 A2AClient 更简单？
    因为 HTTP 是无状态协议，每次请求都是独立的，不需要维护长连接。
    而 MCP 的 Stdio/SSE 传输需要维护持久连接，所以需要 async with。
    """

    def __init__(self, server_url: str):
        """
        初始化 A2A 客户端

        【学习笔记】
        只保存服务器地址，不建立连接。
        rstrip('/') 去掉末尾的斜杠，避免拼接 URL 时出现双斜杠：
        - "http://localhost:5000/" + "/ask" → "http://localhost:5000//ask" (错误)
        - "http://localhost:5000"  + "/ask" → "http://localhost:5000/ask"  (正确)

        Args:
            server_url: 服务器 URL（例如：http://localhost:5000）
        """
        self.server_url = server_url.rstrip('/')

    def ask(self, question: str) -> str:
        """
        向 Agent 提问（通用接口）

        【学习笔记】
        调用 A2AServer 的 /ask 端点。
        服务端会自动尝试所有技能，返回最合适的结果。
        
        完整的 HTTP 请求流程：
        1. Client 构造 POST 请求，body 是 JSON: {"question": "..."}
        2. requests.post() 发送 HTTP 请求到服务器
        3. 服务器的 Flask 接收请求，调用 ask() 路由函数
        4. 服务器返回 JSON 响应: {"answer": "...", "status": "success"}
        5. Client 解析响应，提取 answer 字段返回

        Args:
            question: 问题文本

        Returns:
            Agent 的回答文本
        """
        try:
            # requests 是 Python 最流行的 HTTP 客户端库
            import requests
            response = requests.post(
                f"{self.server_url}/ask",
                json={"question": question},  # 自动序列化为 JSON，设置 Content-Type
                timeout=30  # 超时 30 秒，防止服务器无响应时永远等待
            )
            # raise_for_status(): 如果 HTTP 状态码是 4xx/5xx，抛出异常
            response.raise_for_status()
            return response.json().get("answer", "No response")
        except Exception as e:
            # 网络错误、超时、服务器错误等都会走到这里
            return f"Error communicating with agent: {str(e)}"

    def execute_skill(self, skill_name: str, text: str = "") -> Dict[str, Any]:
        """
        执行指定技能

        【学习笔记】
        与 ask() 不同，这里明确指定要调用哪个技能。
        类似 MCP 的 call_tool()：你知道要调什么，直接调。
        
        示例：
            client = A2AClient("http://localhost:5000")
            result = client.execute_skill("translate", "Hello World")
            # result: {"skill": "translate", "result": "你好世界", "status": "success"}

        Args:
            skill_name: 技能名称
            text: 输入文本

        Returns:
            执行结果字典，包含 skill、result、status 字段
        """
        try:
            import requests
            response = requests.post(
                # 技能名拼接到 URL 路径中（对应服务端的动态路由 /execute/<skill_name>）
                f"{self.server_url}/execute/{skill_name}",
                json={"text": text},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Failed to execute skill: {str(e)}", "status": "error"}

    def get_info(self) -> Dict[str, Any]:
        """获取 Agent 信息
        
        【学习笔记】
        调用 /info 端点，获取远程 Agent 的元信息。
        常用于：
        - 服务发现：检查某个 URL 上是否有 A2A Agent
        - 能力查询：了解 Agent 能做什么
        """
        try:
            import requests
            response = requests.get(f"{self.server_url}/info", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Failed to get agent info: {str(e)}"}

    def list_skills(self) -> List[str]:
        """列出 Agent 的技能
        
        【学习笔记】
        调用 /skills 端点，获取技能名称列表。
        类似 MCP 的 list_tools()，但返回的信息更简单（只有名称，没有参数 schema）。
        
        失败时返回空列表而不是抛异常，这是一种"静默失败"策略：
        - 好处：调用方不需要 try/except，代码更简洁
        - 坏处：失败时没有错误信息，可能难以调试
        """
        try:
            import requests
            response = requests.get(f"{self.server_url}/skills", timeout=10)
            response.raise_for_status()
            return response.json().get("skills", [])
        except Exception as e:
            return []


class AgentNetwork:
    """基于官方 a2a-sdk 库的 Agent 网络（概念性实现）
    
    【学习笔记 - Agent 网络管理】
    
    AgentNetwork 是一个"通讯录"，管理多个 Agent 的地址。
    
    类比：手机通讯录
    - add_agent() = 添加联系人
    - get_agent() = 找到联系人并拨打电话（返回 A2AClient）
    - list_agents() = 查看所有联系人
    - discover_agents() = 自动扫描附近的人并添加到通讯录
    
    使用场景：
    一个协调 Agent 需要调用多个专业 Agent（翻译、计算、搜索等），
    AgentNetwork 帮它管理这些 Agent 的地址，按名字查找并调用。
    
    示例：
        network = AgentNetwork("我的Agent网络")
        network.add_agent("翻译Agent", "http://localhost:5001")
        network.add_agent("计算Agent", "http://localhost:5002")
        
        # 需要翻译时，从网络中获取翻译Agent的客户端
        translator = network.get_agent("翻译Agent")
        result = translator.ask("translate hello to Chinese")
    """

    def __init__(self, name: str = "Agent Network"):
        """
        初始化 Agent 网络

        Args:
            name: 网络名称
        """
        self.name = name
        # agents 字典：Agent名称 -> Agent的URL地址
        # 本质就是一个地址簿
        self.agents = {}  # agent_name -> agent_url

    def add_agent(self, agent_name: str, agent_url: str):
        """
        添加 Agent 到网络

        【学习笔记】
        手动注册一个 Agent。需要知道 Agent 的名字和地址。
        如果同名 Agent 已存在，会被覆盖（字典的特性）。

        Args:
            agent_name: Agent 名称
            agent_url: Agent URL
        """
        self.agents[agent_name] = agent_url

    def get_agent(self, agent_name: str) -> A2AClient:
        """
        获取网络中的 Agent

        【学习笔记】
        根据名字查找 Agent，返回一个 A2AClient 实例。
        注意：每次调用都会创建新的 A2AClient（因为 HTTP 无状态，不需要复用）。
        
        这是一个工厂方法：输入名字，输出可用的客户端对象。

        Args:
            agent_name: Agent 名称

        Returns:
            A2A 客户端实例，可以直接调用 ask()、execute_skill() 等方法
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not found in network")

        return A2AClient(self.agents[agent_name])

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有 Agent
        
        【学习笔记】
        返回网络中所有已注册 Agent 的名称和地址。
        用列表推导式把字典转换为字典列表，方便序列化为 JSON。
        """
        return [
            {"name": name, "url": url}
            for name, url in self.agents.items()
        ]

    def discover_agents(self, urls: List[str]) -> int:
        """
        从 URL 列表中发现 Agent

        【学习笔记 - 服务发现】
        自动扫描一批 URL，检查哪些是活跃的 A2A Agent，并自动添加到网络。
        
        工作流程：
        1. 遍历每个 URL
        2. 创建临时 A2AClient，调用 /info 接口
        3. 如果返回了有效信息（有 name，没有 error），说明这是一个 A2A Agent
        4. 自动添加到网络中
        5. 如果连接失败或不是 A2A Agent，跳过
        
        这是一种"主动探测"式的服务发现，适合已知候选地址的场景。
        更高级的服务发现（如 ANP）支持自动注册和广播。

        Args:
            urls: 候选 URL 列表

        Returns:
            成功发现的 Agent 数量
        """
        discovered = 0
        for url in urls:
            try:
                client = A2AClient(url)
                info = client.get_info()
                # 检查返回的信息是否有效：有名字且没有错误
                if "name" in info and "error" not in info:
                    self.add_agent(info["name"], url)
                    discovered += 1
            except Exception:
                # 连接失败、超时等情况，跳过这个 URL
                continue
        return discovered


class AgentRegistry:
    """基于官方 a2a-sdk 库的 Agent 注册中心（概念性实现）
    
    【学习笔记 - 注册中心模式】
    
    AgentRegistry 是一个中心化的"登记处"，Agent 上线时来登记，下线时来注销。
    其他 Agent 可以来这里查找需要的服务。
    
    与 AgentNetwork 的区别：
    - AgentNetwork: 通讯录，手动管理，本地使用
    - AgentRegistry: 登记处，Agent 主动注册/注销，支持元数据和时间戳
    
    类比：
    - AgentNetwork = 你手机里的通讯录（你自己维护）
    - AgentRegistry = 114 查号台（服务提供者主动登记，查询者来查）
    
    在微服务架构中，这种模式叫"服务注册与发现"：
    - 注册：服务启动时，向注册中心报告自己的地址和能力
    - 发现：需要调用服务时，向注册中心查询可用的服务地址
    - 注销：服务关闭时，从注册中心移除自己
    
    常见的注册中心实现：Consul、Eureka、Zookeeper、etcd
    """

    def __init__(self, name: str = "Agent Registry", description: str = "Central agent registry"):
        """
        初始化 Agent 注册中心

        Args:
            name: 注册中心名称
            description: 注册中心描述
        """
        self.name = name
        self.description = description
        # registered_agents 字典：Agent名称 -> {url, metadata, registered_at}
        # 比 AgentNetwork 多了元数据和注册时间
        self.registered_agents = {}

    def register_agent(self, agent_name: str, agent_url: str, metadata: Optional[Dict[str, Any]] = None):
        """注册 Agent
        
        【学习笔记】
        Agent 上线时调用此方法，向注册中心报告自己的存在。
        
        __import__("datetime") 是动态导入的写法，等价于 import datetime。
        这里用动态导入是为了避免在文件顶部增加一个只用一次的 import。
        .isoformat() 生成 ISO 8601 格式的时间字符串，如 "2026-02-09T11:30:00"。
        
        Args:
            agent_name: Agent 名称
            agent_url: Agent 的访问地址
            metadata: 额外的元数据，如 {"version": "1.0", "capabilities": ["chat"]}
        """
        self.registered_agents[agent_name] = {
            "url": agent_url,
            "metadata": metadata or {},
            "registered_at": __import__("datetime").datetime.now().isoformat()
        }

    def unregister_agent(self, agent_name: str):
        """注销 Agent
        
        【学习笔记】
        Agent 下线时调用此方法，从注册中心移除自己。
        如果 Agent 名称不存在，静默忽略（不报错）。
        """
        if agent_name in self.registered_agents:
            del self.registered_agents[agent_name]

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有注册的 Agent
        
        【学习笔记】
        **info 是字典解包语法：
        {"name": "翻译Agent", **{"url": "...", "metadata": {}, "registered_at": "..."}}
        等价于：
        {"name": "翻译Agent", "url": "...", "metadata": {}, "registered_at": "..."}
        
        这样把 name 和其他信息合并到一个扁平的字典中，方便使用。
        """
        return [
            {"name": name, **info}
            for name, info in self.registered_agents.items()
        ]

    def find_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """查找特定 Agent
        
        【学习笔记】
        dict.get(key) 在 key 不存在时返回 None（而不是抛 KeyError）。
        这是一种安全的查找方式，调用方通过检查返回值是否为 None 来判断是否找到。
        """
        return self.registered_agents.get(agent_name)

    def get_info(self) -> Dict[str, Any]:
        """获取注册中心信息
        
        【学习笔记】
        返回注册中心自身的元信息，包括已注册的 Agent 数量。
        注意 registered_agents 字段返回的是数量（int），不是列表，
        避免在简单查询中暴露所有 Agent 的详细信息。
        """
        return {
            "name": self.name,
            "description": self.description,
            "protocol": "A2A",
            "type": "registry",
            "registered_agents": len(self.registered_agents)
        }


# === 示例代码 ===
# 【学习笔记】
# 下面的代码展示了如何创建一个完整的 A2A Agent，包括：
# 1. 创建 A2AServer 实例
# 2. 定义并注册技能函数
# 3. 启动服务器

def create_example_agent() -> A2AServer:
    """创建一个示例 A2A Agent
    
    【学习笔记 - 技能函数的设计】
    
    A2A 的技能函数签名非常简单：
        def skill(text: str) -> str
    
    输入一个字符串，输出一个字符串。
    这比 MCP 的 Tool 简单得多（MCP Tool 有 JSON Schema 定义参数）。
    
    简单的好处：容易实现、容易理解
    简单的代价：不支持结构化参数，所有输入都要从文本中解析
    """
    if not A2A_AVAILABLE:
        raise ImportError(
            "Cannot create example agent: a2a-sdk library not available. "
            "Install it with: pip install a2a-sdk"
        )

    server = A2AServer(
        name="Example A2A Agent",
        description="A simple example A2A agent",
        version="1.0.0",
        capabilities={"chat": True, "calculation": True}
    )

    # === 技能 1：计算器 ===
    def calculator_skill(text: str) -> str:
        """计算数学表达式
        
        【学习笔记 - 从自然语言中提取参数】
        因为技能函数只接收字符串，所以需要自己从文本中提取有用信息。
        这里用正则表达式提取 "calculate" 后面的数学表达式。
        
        安全考虑：
        eval() 可以执行任意 Python 代码，非常危险！
        这里用 allowed_chars 白名单限制只允许数字和运算符，防止代码注入。
        生产环境应该用 ast.literal_eval() 或专门的数学表达式解析库。
        """
        import re
        match = re.search(r'calculate\s+(.+)', text, re.IGNORECASE)
        if match:
            expression = match.group(1).strip()
            try:
                # 安全的表达式求值（仅支持基本运算）
                allowed_chars = set("0123456789+-*/() .")
                if not all(c in allowed_chars for c in expression):
                    return "Error: Invalid characters in expression"
                result = eval(expression)
                return f"The result is: {result}"
            except Exception as e:
                return f"Calculation error: {str(e)}"
        return "Please provide an expression to calculate"

    server.add_skill("calculate", calculator_skill)

    # === 技能 2：问候 ===
    def greeting_skill(text: str) -> str:
        """生成问候语
        
        【学习笔记】
        用正则表达式检测文本中是否包含问候词（hello/hi/greet）。
        re.IGNORECASE 让匹配不区分大小写。
        """
        import re
        match = re.search(r'hello|hi|greet', text, re.IGNORECASE)
        if match:
            return "Hello! I'm an A2A agent. How can I help you today?"
        return "Hi there!"

    server.add_skill("greet", greeting_skill)

    return server


# === 入口点 ===
# 【学习笔记 - __name__ == "__main__"】
# 这个条件判断确保：
# - 直接运行此文件时（python implementation.py）：执行下面的代码
# - 被其他文件导入时（from a2a.implementation import ...）：不执行
# 这是 Python 的标准实践，让文件既能独立运行，又能作为模块被导入。
if __name__ == "__main__":
    try:
        # 创建并运行示例 Agent
        agent = create_example_agent()
        print(f"[启动] Starting {agent.name}...")
        print(f"[描述] {agent.description}")
        print(f"[协议] Protocol: A2A")
        print(f"[版本] Version: {agent.version}")
        print(f"[技能] Skills: {list(agent.skills.keys())}")
        print()
        # run() 会阻塞在这里，直到服务器关闭（Ctrl+C）
        agent.run(host="0.0.0.0", port=5000)
    except ImportError as e:
        print(f"[错误] {e}")
        print("[提示] Install the A2A SDK: pip install a2a-sdk")
        print("[文档] Official repository: https://github.com/a2aproject/a2a-python")

