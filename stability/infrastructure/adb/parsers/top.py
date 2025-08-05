"""Top command parsers for the ADB collector."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class TopParserMixin:
    def _parse_top_system(self, top_output: str) -> Dict[str, float]:
        """解析系统级别的top命令输出"""
        data = {}
        
        try:
            lines = top_output.strip().split('\n')
            
            for line in lines:
                # 解析CPU总体使用率
                if 'CPU:' in line or '%cpu' in line.lower():
                    # 示例: CPU: 15%usr 5%sys 0%nic 75%idle 5%io 0%irq 0%sirq
                    cpu_match = re.search(r'(\d+(?:\.\d+)?)%idle', line)
                    if cpu_match:
                        idle_percent = float(cpu_match.group(1))
                        data['top_cpu_usage'] = 100.0 - idle_percent
                
                # 解析内存使用情况
                elif 'Mem:' in line or 'KiB Mem' in line:
                    # 示例: Mem: 1024000k total, 800000k used, 224000k free
                    mem_parts = re.findall(r'(\d+)k?\s+(\w+)', line.lower())
                    total_mem = used_mem = 0
                    
                    for value, unit in mem_parts:
                        if 'total' in unit:
                            total_mem = int(value)
                        elif 'used' in unit:
                            used_mem = int(value)
                    
                    if total_mem > 0:
                        data['top_memory_usage_percent'] = (used_mem / total_mem) * 100
                        data['top_memory_total_kb'] = total_mem
                        data['top_memory_used_kb'] = used_mem
                        
        except Exception as e:
            logger.warning("解析top系统输出失败: %s", e)
            
        return data

    def _parse_top_cpu(self, top_output: str) -> Dict[str, float]:
        """Compatibility wrapper for the pre-split top CPU parser helper."""
        return self._parse_top_system(top_output)

    def _parse_top_app(self, top_output: str, package_name: str) -> Dict[str, float]:
        """解析应用级别的top命令输出"""
        data = {}
        
        try:
            lines = top_output.strip().split('\n')
            
            for line in lines:
                if package_name in line:
                    # 跳过grep命令本身的行
                    if 'grep' in line or 'sh -c' in line:
                        continue
                        
                    # 典型的top输出格式:
                    # PID USER     PR  NI  VIRT  RES  SHR S %CPU %MEM     TIME+ COMMAND
                    # 1234 u0_a123  20   0  1.2G 100M  50M S  5.0  2.5   0:10.23 com.example.app
                    
                    parts = line.split()
                    if len(parts) >= 11 and (parts[-1] == package_name or parts[-1].startswith(package_name + '.')):
                        # 匹配精确包名或以包名开头的进程名（如 com.example.app.service）
                        try:
                            cpu_percent = float(parts[8].replace('%', ''))
                            mem_percent = float(parts[9].replace('%', ''))
                            
                            data['top_cpu_usage'] = cpu_percent
                            data['top_memory_percent'] = mem_percent
                            
                            # 解析内存大小（RES列）
                            if len(parts) >= 6:
                                res_mem = parts[5]  # RES列
                                mem_kb = self._parse_memory_size(res_mem)
                                if mem_kb:
                                    data['top_memory_res_kb'] = mem_kb
                                    
                        except (ValueError, IndexError) as e:
                            logger.warning("解析top应用数据失败: %s", e)
                            
        except Exception as e:
            logger.warning("解析top应用输出失败: %s", e)
            
        return data

    def _get_actual_process_name_from_top(self, top_output: str, package_name: str) -> Optional[str]:
        """从top输出中获取实际的进程名"""
        try:
            lines = top_output.strip().split('\n')
            
            for line in lines:
                if package_name in line:
                    # 跳过grep命令本身的行
                    if 'grep' in line or 'sh -c' in line:
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 11:
                        # 最后一列是进程名
                        process_name = parts[-1]
                        if process_name.startswith(package_name):
                            return process_name
                            
        except Exception as e:
            logger.debug(f"获取实际进程名失败 {package_name}: {e}")
            
        return None

    def _parse_memory_size(self, mem_str: str) -> float:
        """解析内存大小字符串，返回KB"""
        try:
            if not mem_str:
                return 0
                
            mem_str = mem_str.upper().strip()
            
            if mem_str.endswith('K'):
                return float(mem_str[:-1])
            elif mem_str.endswith('M'):
                return float(mem_str[:-1]) * 1024
            elif mem_str.endswith('G'):
                return float(mem_str[:-1]) * 1024 * 1024
            else:
                # 假设是字节
                return float(mem_str) / 1024
                
        except (ValueError, AttributeError):
            return 0
