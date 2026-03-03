"""
实时查看对话日志工具

这是一个命令行工具，用于查看和监控 NPC 对话日志
提供三种功能：
1. 实时查看日志（类似 Linux 的 tail -f）
2. 查看完整日志文件
3. 列出所有历史日志文件

使用方法：
    python view_logs.py tail   # 实时查看今天的日志
    python view_logs.py view   # 查看今天的完整日志
    python view_logs.py list   # 列出所有日志文件
"""

import os
import time
from pathlib import Path
from datetime import datetime

# ===================================================================
# 日志文件配置
# ===================================================================

# 日志目录路径（相对于当前文件）
LOGS_DIR = Path(__file__).parent / "logs"

# 获取今天的日期（格式：YYYY-MM-DD）
today = datetime.now().strftime("%Y-%m-%d")

# 今天的日志文件路径
LOG_FILE = LOGS_DIR / f"dialogue_{today}.log"

# ===================================================================
# 日志查看函数
# ===================================================================

def tail_log_file(filename, interval=1):
    """
    实时查看日志文件（类似 Linux 的 tail -f 命令）
    
    持续监控日志文件，当有新内容写入时立即显示
    适合用于实时监控 NPC 对话过程
    
    Args:
        filename: 日志文件路径（Path 对象）
        interval: 检查新内容的间隔时间（秒），默认 1 秒
    
    工作原理：
        1. 打开文件并移动到文件末尾
        2. 循环读取新增的行
        3. 如果没有新内容，等待 interval 秒后再检查
        4. 按 Ctrl+C 可以停止查看
    """
    
    print("\n" + "="*60)
    print(f"实时查看对话日志")
    print(f"日志文件: {filename}")
    print("="*60)
    print("\n按 Ctrl+C 停止查看\n")
    
    # 如果文件不存在，等待创建
    # 这种情况发生在应用还没有产生任何日志时
    while not filename.exists():
        print(f"等待日志文件创建: {filename}")
        time.sleep(interval)
    
    # 打开文件（只读模式，UTF-8 编码）
    with open(filename, 'r', encoding='utf-8') as f:
        # 移动到文件末尾（跳过已有内容）
        # seek(0, 2) 表示从文件末尾偏移 0 字节
        f.seek(0, 2)
        
        try:
            # 无限循环，持续监控新内容
            while True:
                # 尝试读取一行
                line = f.readline()
                if line:
                    # 有新内容，立即打印（不添加额外换行）
                    print(line, end='')
                else:
                    # 没有新内容，等待一段时间后再检查
                    time.sleep(interval)
        except KeyboardInterrupt:
            # 用户按 Ctrl+C 时优雅退出
            print("\n\n停止查看日志")

def view_full_log(filename):
    """
    查看完整日志文件
    
    一次性读取并显示整个日志文件的内容
    适合用于查看历史对话记录
    
    Args:
        filename: 日志文件路径（Path 对象）
    
    注意：
        - 如果日志文件很大，可能会占用较多内存
        - 建议用于查看单日的日志文件
    """
    
    print("\n" + "="*60)
    print(f"查看完整对话日志")
    print(f"日志文件: {filename}")
    print("="*60 + "\n")
    
    # 检查文件是否存在
    if not filename.exists():
        print(f"错误: 日志文件不存在: {filename}")
        return
    
    # 读取并打印整个文件内容
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        print(content)
    
    print("\n" + "="*60)
    print("日志查看完成")
    print("="*60 + "\n")

def list_log_files():
    """
    列出所有日志文件
    
    扫描日志目录，显示所有对话日志文件的信息
    包括文件名、大小、最后修改时间
    
    文件按日期倒序排列（最新的在前）
    
    显示信息：
        - 文件名（包含日期）
        - 文件大小（KB）
        - 最后修改时间
    """
    
    print("\n" + "="*60)
    print(f"日志文件列表")
    print(f"目录: {LOGS_DIR}")
    print("="*60 + "\n")
    
    # 检查日志目录是否存在
    if not LOGS_DIR.exists():
        print("错误: 日志目录不存在")
        return
    
    # 查找所有对话日志文件（dialogue_*.log）
    # sorted(..., reverse=True) 按文件名倒序排列（最新日期在前）
    log_files = sorted(LOGS_DIR.glob("dialogue_*.log"), reverse=True)
    
    # 检查是否有日志文件
    if not log_files:
        print("暂无日志文件")
        return
    
    # 遍历并显示每个日志文件的信息
    for i, log_file in enumerate(log_files, 1):
        # 获取文件大小（字节）
        size = log_file.stat().st_size
        # 转换为 KB
        size_kb = size / 1024
        # 获取最后修改时间
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        
        # 打印文件信息
        print(f"{i}. {log_file.name}")
        print(f"   大小: {size_kb:.2f} KB")
        print(f"   修改时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

# ===================================================================
# 主程序入口
# ===================================================================

if __name__ == "__main__":
    import sys
    
    # 检查是否提供了命令行参数
    if len(sys.argv) > 1:
        # 获取第一个参数作为命令
        command = sys.argv[1]
        
        if command == "tail":
            # 实时查看今天的日志
            tail_log_file(LOG_FILE)
        elif command == "view":
            # 查看今天的完整日志
            view_full_log(LOG_FILE)
        elif command == "list":
            # 列出所有历史日志文件
            list_log_files()
        else:
            # 未知命令，显示帮助信息
            print(f"错误: 未知命令: {command}")
            print("\n使用方法:")
            print("  python view_logs.py tail   # 实时查看日志")
            print("  python view_logs.py view   # 查看完整日志")
            print("  python view_logs.py list   # 列出所有日志文件")
    else:
        # 没有提供参数，默认实时查看今天的日志
        tail_log_file(LOG_FILE)

