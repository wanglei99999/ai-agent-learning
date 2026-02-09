"""
基于 agent-connect 库的 ANP 协议实现

使用 agent-connect 库 (v0.3.7) 实现 Agent Network Protocol 功能。

注意：agent-connect 是一个底层的网络协议库，提供了加密、认证等功能。
这里我们创建一个简化的包装器，使其更易于使用。
"""

from typing import Dict, Any, List, Optional
import asyncio
import json


# 由于 agent-connect 的 API 比较底层，我们创建一个简化的实现
# 实际使用时可以根据需要调用 agent-connect 的具体模块

class ServiceInfo:
    """
    服务信息类
    
    用于封装服务的基本信息，包括服务ID、类型、端点地址等。
    这是ANP协议中服务发现机制的核心数据结构。
    """

    def __init__(
        self,
        service_id: str,
        service_type: str,
        endpoint: str,
        service_name: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        初始化服务信息
        
        Args:
            service_id: 服务的唯一标识符
            service_type: 服务类型（如 "agent", "tool", "api" 等）
            endpoint: 服务的网络端点地址（如 "http://localhost:8080"）
            service_name: 服务的可读名称，默认使用 service_id
            capabilities: 服务支持的能力列表（如 ["chat", "search"]）
            metadata: 服务的额外元数据信息
        """
        self.service_id = service_id
        self.service_type = service_type
        self.endpoint = endpoint
        self.service_name = service_name or service_id
        self.capabilities = capabilities or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        将服务信息转换为字典格式
        
        用于序列化服务信息，便于网络传输或持久化存储。
        
        Returns:
            包含所有服务信息字段的字典
        """
        return {
            "service_id": self.service_id,
            "service_type": self.service_type,
            "endpoint": self.endpoint,
            "service_name": self.service_name,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceInfo':
        """
        从字典数据创建服务信息对象
        
        用于反序列化服务信息，从网络接收或存储中恢复对象。
        
        Args:
            data: 包含服务信息的字典
            
        Returns:
            ServiceInfo 实例
        """
        return cls(
            service_id=data["service_id"],
            service_type=data["service_type"],
            endpoint=data["endpoint"],
            service_name=data.get("service_name"),
            capabilities=data.get("capabilities"),
            metadata=data.get("metadata", {})
        )


class ANPDiscovery:
    """
    ANP 服务发现类
    
    实现服务的注册、注销和发现功能。
    服务发现是分布式系统中的关键组件，允许服务动态地注册自己并被其他服务发现。
    
    主要功能：
    - 服务注册：将服务信息添加到注册表
    - 服务注销：从注册表中移除服务
    - 服务发现：根据类型或条件查找服务
    - 服务查询：获取特定服务的详细信息
    """
    
    def __init__(self):
        """
        初始化服务发现管理器
        
        创建一个空的服务注册表，使用字典存储服务ID到服务信息的映射。
        """
        # 服务注册表：service_id -> ServiceInfo
        self._services: Dict[str, ServiceInfo] = {}
        
    def register_service(self, service: ServiceInfo) -> bool:
        """
        注册服务到发现系统
        
        将服务信息添加到注册表中，使其可以被其他服务发现。
        如果服务ID已存在，会覆盖原有的服务信息。
        
        Args:
            service: 要注册的服务信息对象
            
        Returns:
            bool: 注册是否成功（当前实现总是返回 True）
        """
        self._services[service.service_id] = service
        return True
        
    def unregister_service(self, service_id: str) -> bool:
        """
        从发现系统中注销服务
        
        将服务从注册表中移除，使其不再能被发现。
        通常在服务关闭或不再可用时调用。
        
        Args:
            service_id: 要注销的服务ID
            
        Returns:
            bool: 如果服务存在并成功注销返回 True，否则返回 False
        """
        if service_id in self._services:
            del self._services[service_id]
            return True
        return False
        
    def discover_services(
        self,
        service_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ServiceInfo]:
        """
        发现符合条件的服务
        
        支持按服务类型和元数据条件进行过滤查询。
        这是服务发现的核心方法，允许客户端找到所需的服务。
        
        Args:
            service_type: 要查找的服务类型（如 "agent"），为 None 则不按类型过滤
            filters: 元数据过滤条件字典，只返回元数据匹配所有条件的服务
            
        Returns:
            List[ServiceInfo]: 符合条件的服务信息列表
            
        示例:
            # 查找所有 agent 类型的服务
            agents = discovery.discover_services(service_type="agent")
            
            # 查找角色为 worker 的服务
            workers = discovery.discover_services(filters={"role": "worker"})
        """
        # 获取所有服务的副本
        services = list(self._services.values())
        
        # 第一步：按服务类型过滤
        if service_type:
            services = [s for s in services if s.service_type == service_type]
            
        # 第二步：按元数据过滤
        if filters:
            def matches_filters(service: ServiceInfo) -> bool:
                """检查服务的元数据是否匹配所有过滤条件"""
                for key, value in filters.items():
                    if service.metadata.get(key) != value:
                        return False
                return True
            services = [s for s in services if matches_filters(s)]
            
        return services
        
    def get_service(self, service_id: str) -> Optional[ServiceInfo]:
        """
        根据服务ID获取服务信息
        
        用于精确查询特定服务的详细信息。
        
        Args:
            service_id: 要查询的服务ID
            
        Returns:
            Optional[ServiceInfo]: 服务信息对象，如果服务不存在则返回 None
        """
        return self._services.get(service_id)
        
    def list_all_services(self) -> List[ServiceInfo]:
        """
        列出所有已注册的服务
        
        返回注册表中的所有服务，不进行任何过滤。
        
        Returns:
            List[ServiceInfo]: 所有服务信息的列表
        """
        return list(self._services.values())


class ANPNetwork:
    """
    ANP 网络管理类
    
    管理 Agent 网络的拓扑结构，包括节点管理、连接管理和消息路由。
    这是 ANP 协议的核心组件，负责维护网络状态和处理节点间通信。
    
    主要功能：
    - 节点管理：添加、删除网络节点
    - 连接管理：建立节点之间的连接关系
    - 消息路由：在节点间路由消息
    - 消息广播：向多个节点广播消息
    - 网络监控：提供网络统计和节点状态信息
    """
    
    def __init__(self, network_id: str = "default"):
        """
        初始化网络管理器
        
        创建一个新的 ANP 网络实例，初始化节点和连接的存储结构。
        
        Args:
            network_id: 网络的唯一标识符，用于区分不同的网络实例
        """
        self.network_id = network_id
        # 节点存储：node_id -> {node_id, endpoint, metadata, status}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # 连接关系：node_id -> [connected_node_ids]
        # 表示从某个节点到其他节点的连接列表
        self._connections: Dict[str, List[str]] = {}
        
    def add_node(self, node_id: str, endpoint: str, metadata: Optional[Dict[str, Any]] = None):
        """
        添加节点到网络
        
        将一个新节点注册到网络中，初始化其状态为活跃，并创建空的连接列表。
        
        Args:
            node_id: 节点的唯一标识符
            endpoint: 节点的网络端点地址（如 "http://localhost:8001"）
            metadata: 节点的元数据信息（如 {"type": "agent", "role": "worker"}）
        """
        self._nodes[node_id] = {
            "node_id": node_id,
            "endpoint": endpoint,
            "metadata": metadata or {},
            "status": "active"  # 节点状态：active（活跃）或其他自定义状态
        }
        # 初始化该节点的连接列表为空
        self._connections[node_id] = []
        
    def remove_node(self, node_id: str) -> bool:
        """
        从网络中移除节点
        
        删除节点及其所有相关的连接关系。
        这包括：
        1. 删除节点本身的信息
        2. 删除该节点发起的所有连接
        3. 删除其他节点到该节点的连接
        
        Args:
            node_id: 要移除的节点ID
            
        Returns:
            bool: 如果节点存在并成功移除返回 True，否则返回 False
        """
        if node_id in self._nodes:
            # 删除节点信息
            del self._nodes[node_id]
            # 删除该节点的连接列表
            del self._connections[node_id]
            # 清理其他节点到此节点的连接引用
            for connections in self._connections.values():
                if node_id in connections:
                    connections.remove(node_id)
            return True
        return False
        
    def connect_nodes(self, from_node: str, to_node: str):
        """
        建立两个节点之间的连接
        
        创建从源节点到目标节点的单向连接。
        注意：这是单向连接，如果需要双向通信，需要调用两次此方法。
        
        Args:
            from_node: 源节点ID（连接的起点）
            to_node: 目标节点ID（连接的终点）
            
        注意:
            - 只有当两个节点都存在时才会建立连接
            - 如果连接已存在，不会重复添加
        """
        # 检查两个节点是否都存在
        if from_node in self._connections and to_node in self._nodes:
            # 避免重复连接
            if to_node not in self._connections[from_node]:
                self._connections[from_node].append(to_node)
                
    def route_message(
        self,
        from_node: str,
        to_node: str,
        message: Dict[str, Any]
    ) -> Optional[List[str]]:
        """
        计算从源节点到目标节点的消息路由路径
        
        实现了简单的路由算法：
        1. 首先尝试直接路由（源节点直接连接到目标节点）
        2. 如果直接路由不可行，尝试通过一个中间节点转发
        
        Args:
            from_node: 消息源节点ID
            to_node: 消息目标节点ID
            message: 消息内容（当前实现中未使用，预留用于更复杂的路由决策）
            
        Returns:
            Optional[List[str]]: 路由路径的节点ID列表，如 ["node1", "node2"] 或 ["node1", "node3", "node2"]
                               如果无法找到路径则返回 None
                               
        注意:
            当前实现只支持最多一跳的路由，更复杂的多跳路由需要使用图搜索算法（如 BFS）
        """
        # 检查源节点和目标节点是否都存在
        if from_node not in self._nodes or to_node not in self._nodes:
            return None
            
        # 策略1：尝试直接路由
        if to_node in self._connections.get(from_node, []):
            return [from_node, to_node]
            
        # 策略2：尝试通过一跳中转节点路由
        for intermediate in self._connections.get(from_node, []):
            if to_node in self._connections.get(intermediate, []):
                return [from_node, intermediate, to_node]
                
        # 无法找到路由路径
        return None
        
    def broadcast_message(self, from_node: str, message: Dict[str, Any]) -> List[str]:
        """
        从指定节点广播消息到所有直接连接的节点
        
        广播是一对多的通信方式，消息会发送给源节点的所有邻居节点。
        
        Args:
            from_node: 广播源节点ID
            message: 要广播的消息内容（当前实现中未使用，预留用于消息处理）
            
        Returns:
            List[str]: 接收广播消息的节点ID列表
                      如果源节点不存在或没有连接，返回空列表
        """
        if from_node not in self._connections:
            return []
            
        # 返回所有直接连接节点的副本
        return self._connections[from_node].copy()
        
    def get_network_stats(self) -> Dict[str, Any]:
        """
        获取网络的统计信息
        
        提供网络的整体状态概览，包括节点数量、连接数量等关键指标。
        用于监控和调试网络状态。
        
        Returns:
            Dict[str, Any]: 包含以下字段的统计信息字典：
                - network_id: 网络ID
                - total_nodes: 总节点数
                - active_nodes: 活跃节点数
                - total_connections: 总连接数（所有节点的出站连接总和）
                - nodes: 所有节点ID的列表
        """
        # 计算总连接数：累加所有节点的出站连接数
        total_connections = sum(len(conns) for conns in self._connections.values())
        # 统计活跃节点数
        active_nodes = sum(1 for node in self._nodes.values() if node["status"] == "active")
        
        return {
            "network_id": self.network_id,
            "total_nodes": len(self._nodes),
            "active_nodes": active_nodes,
            "total_connections": total_connections,
            "nodes": list(self._nodes.keys())
        }
        
    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定节点的详细信息
        
        返回节点的完整信息，包括基本属性和连接关系。
        
        Args:
            node_id: 要查询的节点ID
            
        Returns:
            Optional[Dict[str, Any]]: 节点信息字典，包含：
                - node_id: 节点ID
                - endpoint: 节点端点地址
                - metadata: 节点元数据
                - status: 节点状态
                - connections: 该节点连接到的其他节点ID列表
                如果节点不存在则返回 None
        """
        if node_id in self._nodes:
            # 复制节点基本信息
            node_info = self._nodes[node_id].copy()
            # 添加连接信息
            node_info["connections"] = self._connections[node_id].copy()
            return node_info
        return None


def create_example_network() -> ANPNetwork:
    """
    创建一个示例 ANP 网络用于演示
    
    构建一个包含3个节点的简单网络拓扑：
    - node1: 协调者角色，连接到 node2 和 node3
    - node2: 工作者角色，连接到 node3
    - node3: 工作者角色
    
    网络拓扑:
        node1 (coordinator)
         /  \\
        v    v
      node2 -> node3
      (worker) (worker)
    
    Returns:
        ANPNetwork: 配置好的网络实例
    """
    # 创建网络实例
    network = ANPNetwork(network_id="example_network")
    
    # 添加三个节点到网络
    # node1: 协调者节点，负责任务分配和协调
    network.add_node("node1", "http://localhost:8001", {"type": "agent", "role": "coordinator"})
    # node2: 工作者节点，执行具体任务
    network.add_node("node2", "http://localhost:8002", {"type": "agent", "role": "worker"})
    # node3: 工作者节点，执行具体任务
    network.add_node("node3", "http://localhost:8003", {"type": "agent", "role": "worker"})
    
    # 建立节点间的连接关系
    # 协调者可以直接与两个工作者通信
    network.connect_nodes("node1", "node2")
    network.connect_nodes("node1", "node3")
    # 工作者之间也可以相互通信
    network.connect_nodes("node2", "node3")
    
    return network


if __name__ == "__main__":
    """
    主程序：演示 ANP 网络的基本功能
    
    包括：
    1. 创建网络并添加节点
    2. 查看网络统计信息
    3. 测试消息路由功能
    4. 测试消息广播功能
    """
    # 步骤1: 创建示例网络
    network = create_example_network()
    print(f"ANP Network: {network.network_id}")
    print(f"Network Stats:")
    stats = network.get_network_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    print()
    
    # 步骤2: 测试点对点消息路由
    print("Testing message routing:")
    path = network.route_message("node1", "node2", {"type": "test", "content": "Hello"})
    print(f"   Route from node1 to node2: {' -> '.join(path) if path else 'No route found'}")
    
    # 步骤3: 测试消息广播
    print("\nTesting broadcast:")
    recipients = network.broadcast_message("node1", {"type": "broadcast", "content": "Hello all"})
    print(f"   Broadcast from node1 to: {', '.join(recipients)}")

