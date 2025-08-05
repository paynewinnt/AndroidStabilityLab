"""System metric collection and parsing helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class SystemMetricsMixin:
    def get_system_performance(self) -> Dict[str, float]:
        """优化的系统性能数据获取 - 使用批量ADB命令和智能缓存"""
        current_time = time.time()
        
        # 检查缓存
        if (current_time - self._last_collection_time['system_performance'] < 
            self._collection_intervals['system_performance']):
            cached_data = self.enhanced_cache.get('system_performance')
            if cached_data:
                return cached_data
        
        # 使用批量数据获取方法
        try:
            batch_data = self._get_system_batch_data()
            if batch_data:
                # 缓存结果
                self.enhanced_cache.put('system_performance', batch_data, current_time)
                self._last_collection_time['system_performance'] = current_time
                return batch_data
        except Exception as e:
            logger.debug(f"Batch system performance failed, using fallback: {e}")
            
        # 回退到原有方法
        return self._get_system_performance_fallback()

    def _get_system_performance_fallback(self) -> Dict[str, float]:
        """系统性能数据获取回退方案"""
        current_time = time.time()
        data = {}
        
        try:
            # 获取基础系统数据
            cpu_usage = self._get_system_cpu_usage()
            if cpu_usage is not None:
                data['cpu_usage'] = cpu_usage
                
            memory_data = self._get_system_memory()
            data.update(memory_data)
            
            battery_level = self._get_battery_level()
            if battery_level is not None:
                data['battery_level'] = battery_level
                
            # 缓存结果
            self.enhanced_cache.put('system_performance', data, current_time)
            self._last_collection_time['system_performance'] = current_time
            
        except Exception as e:
            logger.debug(f"Fallback system performance collection failed: {e}")
            
        return data

    def _get_system_batch_data(self) -> Dict[str, Any]:
        """批量获取系统数据 - 性能优化，包含网络流量"""
        try:
            # 分别获取各项数据（避免复杂批量命令问题）
            cpu_data = {}
            memory_data = {}
            battery_data = {}
            network_data = {}
            
            # 获取CPU数据（包含详细分解）
            cpu_breakdown = self.get_cpu_usage_with_breakdown()
            if cpu_breakdown:
                # 保持向后兼容性，同时添加详细信息
                cpu_data = {'cpu_usage': cpu_breakdown.get('total', 0)}
                if 'user' in cpu_breakdown:
                    cpu_data['cpu_user'] = cpu_breakdown['user']
                    cpu_data['cpu_breakdown'] = cpu_breakdown
            
            # 获取内存数据
            memory_result = self._run_adb_command("shell cat /proc/meminfo", use_cache=False)
            if memory_result:
                memory_data = self._parse_memory_data(memory_result)
            
            # 获取电池数据
            battery_result = self._run_adb_command("shell dumpsys battery", use_cache=True)
            if battery_result:
                battery_data = self._parse_battery_data(battery_result)
            
            # 获取网络数据，使用多种方法尝试
            network_data = self._get_network_data_with_fallback()
            
            # 获取CPU温度
            cpu_temp = self._get_cpu_temperature()
            temp_data = {}
            if cpu_temp is not None:
                temp_data['cpu_temperature'] = cpu_temp
            
            # 获取系统负载
            load_result = self._run_adb_command("shell cat /proc/loadavg", use_cache=True)
            load_data = {}
            if load_result:
                load_data = self._parse_load_data(load_result)
            
            # 合并所有数据
            system_data = {}
            system_data.update(cpu_data)
            system_data.update(memory_data)
            system_data.update(battery_data)
            system_data.update(network_data)
            system_data.update(temp_data)
            system_data.update(load_data)
            
            return system_data if system_data else self._get_system_data_fallback()
            
        except Exception as e:
            logger.debug(f"Batch system data collection failed: {e}")
            return self._get_system_data_fallback()

    def _parse_cpu_data(self, cpu_output: str) -> Dict[str, float]:
        """解析CPU数据"""
        try:
            lines = cpu_output.strip().split('\n')
            cpu_line = lines[0]  # First line is total CPU
            values = cpu_line.split()[1:]
            values = [int(v) for v in values]
            
            total = sum(values)
            idle = values[3]  # idle time
            usage = ((total - idle) / total) * 100
            return {'cpu_usage': round(usage, 2)}
        except Exception:
            return {}

    def _parse_memory_data(self, memory_output: str) -> Dict[str, float]:
        """解析内存数据"""
        try:
            memory_info = {}
            total_kb = None
            available_kb = None
            
            for line in memory_output.strip().split('\n'):
                if 'MemTotal:' in line:
                    total_kb = int(re.findall(r'\d+', line)[0])
                    memory_info['memory_system_total'] = round(total_kb / 1024, 2)
                elif 'MemAvailable:' in line:
                    available_kb = int(re.findall(r'\d+', line)[0])
                    memory_info['memory_system_available'] = round(available_kb / 1024, 2)
            
            # 计算内存使用百分比
            if total_kb is not None and available_kb is not None:
                used_kb = total_kb - available_kb
                usage_percent = (used_kb / total_kb) * 100
                memory_info['memory_usage_percent'] = round(usage_percent, 2)
                memory_info['memory_percent'] = round(usage_percent, 2)  # 保持兼容性
                memory_info['memory_system_used'] = round(used_kb / 1024, 2)
                
            return memory_info
        except Exception:
            return {}

    def _parse_battery_data(self, battery_output: str) -> Dict[str, float]:
        """解析电池数据"""
        try:
            for line in battery_output.strip().split('\n'):
                if 'level:' in line.lower():
                    level = float(re.findall(r'\d+', line)[0])
                    return {'battery_level': level}
        except Exception:
            pass
        return {}

    def _parse_load_data(self, load_output: str) -> Dict[str, float]:
        """解析系统负载数据"""
        try:
            parts = load_output.strip().split()
            if len(parts) >= 3:
                return {
                    'load_1min': round(float(parts[0]), 2),
                    'load_5min': round(float(parts[1]), 2),
                    'load_15min': round(float(parts[2]), 2)
                }
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse load data: {e}")
            pass
        return {}

    def _get_system_data_fallback(self) -> Dict[str, Any]:
        """系统数据获取回退方案"""
        data = {}
        
        # 分别获取各项数据（原有方式）
        cpu_usage = self._get_system_cpu_usage()
        if cpu_usage is not None:
            data['cpu_usage'] = cpu_usage
            
        memory_data = self._get_system_memory()
        data.update(memory_data)
        
        battery_level = self._get_battery_level()
        if battery_level is not None:
            data['battery_level'] = battery_level
            
        # 获取网络数据
        network_data = self._get_system_network_stats()
        data.update(network_data)
        
        # 获取CPU温度
        cpu_temp = self._get_cpu_temperature()
        if cpu_temp is not None:
            data['cpu_temperature'] = cpu_temp
        
        # 获取系统负载
        load_result = self._run_adb_command("shell cat /proc/loadavg")
        if load_result:
            load_data = self._parse_load_data(load_result)
            data.update(load_data)
            
        return data

    def _get_system_cpu_usage(self) -> Optional[float]:
        try:
            # First try to get detailed CPU info from dumpsys cpuinfo
            result = self._run_adb_command("shell dumpsys cpuinfo")
            if result:
                total_cpu = self._parse_dumpsys_cpuinfo_total(result)
                if total_cpu is not None:
                    return total_cpu
            
            # Fallback to /proc/stat
            result = self._run_adb_command("shell cat /proc/stat")
            if result:
                lines = result.split('\n')
                cpu_line = lines[0]  # First line is total CPU
                values = cpu_line.split()[1:]
                values = [int(v) for v in values]
                
                total = sum(values)
                idle = values[3]  # idle time
                usage = ((total - idle) / total) * 100
                return round(usage, 2)
        except Exception as e:
            logger.debug(f"Failed to get system CPU usage: {e}")
        return None

    def _parse_dumpsys_cpuinfo_total(self, cpuinfo_output: str) -> Optional[float]:
        """Parse total CPU usage from dumpsys cpuinfo output
        Example: 87% TOTAL: 54% user + 29% kernel + 0% iowait + 3.1% irq + 0.8% softirq
        """
        try:
            lines = cpuinfo_output.split('\n')
            for line in lines:
                if 'TOTAL:' in line and '%' in line:
                    # Extract the total percentage before 'TOTAL:'
                    parts = line.split('TOTAL:')
                    if len(parts) >= 1:
                        total_part = parts[0].strip()
                        # Look for percentage pattern
                        import re
                        match = re.search(r'(\d+(?:\.\d+)?)%', total_part)
                        if match:
                            return float(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to parse dumpsys cpuinfo: {e}")
        return None

    def get_cpu_usage_with_breakdown(self) -> Dict[str, float]:
        """Get CPU usage with detailed breakdown from dumpsys cpuinfo
        Returns: {'total': 87.0, 'user': 54.0, 'kernel': 29.0, 'iowait': 0.0, 'irq': 3.1, 'softirq': 0.8}
        """
        try:
            result = self._run_adb_command("shell dumpsys cpuinfo")
            if result:
                lines = result.split('\n')
                for line in lines:
                    if 'TOTAL:' in line and '%' in line:
                        # Parse line like: 87% TOTAL: 54% user + 29% kernel + 0% iowait + 3.1% irq + 0.8% softirq
                        import re
                        
                        # Extract total
                        total_match = re.search(r'(\d+(?:\.\d+)?)%\s*TOTAL:', line)
                        if not total_match:
                            continue
                            
                        total = float(total_match.group(1))
                        
                        # Extract breakdown components
                        breakdown = {'total': total}
                        
                        # Find user, kernel, iowait, irq, softirq values
                        components = ['user', 'kernel', 'iowait', 'irq', 'softirq']
                        for component in components:
                            pattern = rf'(\d+(?:\.\d+)?)%\s*{component}'
                            match = re.search(pattern, line)
                            if match:
                                breakdown[component] = float(match.group(1))
                        
                        return breakdown
        except Exception as e:
            logger.debug(f"Failed to get CPU breakdown: {e}")
        
        # Fallback to basic CPU usage
        cpu_usage = self._get_system_cpu_usage()
        if cpu_usage is not None:
            return {'total': cpu_usage}
        return {}

    def _get_system_memory(self) -> Dict[str, float]:
        try:
            result = self._run_adb_command("shell cat /proc/meminfo")
            if result:
                memory_info = {}
                for line in result.split('\n'):
                    if 'MemTotal:' in line:
                        total_kb = int(re.findall(r'\d+', line)[0])
                        memory_info['memory_system_total'] = round(total_kb / 1024, 2)
                    elif 'MemAvailable:' in line:
                        available_kb = int(re.findall(r'\d+', line)[0])
                        memory_info['memory_system_available'] = round(available_kb / 1024, 2)
                return memory_info
        except Exception as e:
            logger.debug(f"Failed to get system memory: {e}")
        return {}

    def _get_battery_level(self) -> Optional[float]:
        try:
            result = self._run_adb_command("shell dumpsys battery")
            if result:
                match = re.search(r'level: (\d+)', result)
                if match:
                    return float(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to get battery level: {e}")
        return None

    def _get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature if available"""
        try:
            # Try different temperature sources
            temp_sources = [
                'shell cat /sys/class/thermal/thermal_zone0/temp',
                'shell cat /sys/class/thermal/thermal_zone1/temp',
                'shell cat /sys/devices/system/cpu/cpu0/cpufreq/cpu_temp',
                'shell cat /proc/stat | grep cpu_temp'
            ]
            
            for source in temp_sources:
                result = self._run_adb_command(source)
                if result and result.strip().isdigit():
                    temp = int(result.strip())
                    # Convert from millidegrees to degrees if needed
                    if temp > 1000:
                        temp = temp / 1000.0
                    if 0 < temp < 150:  # Reasonable temperature range
                        return round(temp, 1)
                        
        except Exception as e:
            logger.debug(f"Failed to get CPU temperature: {e}")
        return None

    def _get_storage_info(self) -> Dict[str, float]:
        """Get storage usage information"""
        try:
            result = self._run_adb_command('shell df /data')
            if result:
                lines = result.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if '/data' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            total_kb = int(parts[1])
                            used_kb = int(parts[2])
                            available_kb = int(parts[3])
                            
                            return {
                                'storage_total_mb': round(total_kb / 1024, 2),
                                'storage_used_mb': round(used_kb / 1024, 2),
                                'storage_available_mb': round(available_kb / 1024, 2),
                                'storage_usage_percent': round((used_kb / total_kb) * 100, 2)
                            }
        except Exception as e:
            logger.debug(f"Failed to get storage info: {e}")
        return {}

    def _get_battery_info(self) -> Dict[str, float]:
        """Get comprehensive battery information"""
        try:
            result = self._run_adb_command('shell dumpsys battery')
            if result:
                battery_info = {}
                
                # Battery level
                level_match = re.search(r'level: (\d+)', result)
                if level_match:
                    battery_info['battery_level'] = float(level_match.group(1))
                
                # Battery temperature
                temp_match = re.search(r'temperature: (\d+)', result)
                if temp_match:
                    temp_celsius = int(temp_match.group(1)) / 10.0  # Usually in tenths of degrees
                    battery_info['battery_temperature'] = round(temp_celsius, 1)
                
                # Battery voltage
                voltage_match = re.search(r'voltage: (\d+)', result)
                if voltage_match:
                    voltage_mv = int(voltage_match.group(1))
                    battery_info['battery_voltage'] = round(voltage_mv / 1000.0, 2)  # Convert to volts
                
                # Battery health
                health_match = re.search(r'health: (\d+)', result)
                if health_match:
                    battery_info['battery_health'] = int(health_match.group(1))
                
                # Charging status
                status_match = re.search(r'status: (\d+)', result)
                if status_match:
                    battery_info['battery_status'] = int(status_match.group(1))
                
                return battery_info
                
        except Exception as e:
            logger.debug(f"Failed to get battery info: {e}")
        return {}

    def _get_system_load(self) -> Dict[str, float]:
        """Get system load information"""
        try:
            # Get load average
            result = self._run_adb_command('shell cat /proc/loadavg')
            if result:
                parts = result.strip().split()
                if len(parts) >= 3:
                    return {
                        'load_1min': float(parts[0]),
                        'load_5min': float(parts[1]),
                        'load_15min': float(parts[2])
                    }
                    
        except Exception as e:
            logger.debug(f"Failed to get system load: {e}")
            
        # Alternative: get process count as load indicator
        try:
            result = self._run_adb_command('shell ps | wc -l')
            if result and result.strip().isdigit():
                process_count = int(result.strip())
                return {'process_count': process_count}
        except Exception as e:
            logger.debug(f"Failed to get process count: {e}")
            
        return {}

    def _get_display_info(self) -> Dict[str, float]:
        """Get display-related information"""
        try:
            display_info = {}
            
            # Screen brightness
            brightness_result = self._run_adb_command('shell settings get system screen_brightness')
            if brightness_result and brightness_result.strip().isdigit():
                brightness = int(brightness_result.strip())
                # Normalize to percentage (usually 0-255)
                brightness_percent = round((brightness / 255.0) * 100, 2)
                display_info['screen_brightness'] = brightness_percent
            
            # Screen timeout
            timeout_result = self._run_adb_command('shell settings get system screen_off_timeout')
            if timeout_result and timeout_result.strip().isdigit():
                timeout_ms = int(timeout_result.strip())
                timeout_sec = timeout_ms / 1000.0
                display_info['screen_timeout_sec'] = timeout_sec
            
            # Display size and density
            display_result = self._run_adb_command('shell wm size')
            if display_result:
                size_match = re.search(r'(\d+)x(\d+)', display_result)
                if size_match:
                    width = int(size_match.group(1))
                    height = int(size_match.group(2))
                    display_info['screen_width'] = width
                    display_info['screen_height'] = height
            
            density_result = self._run_adb_command('shell wm density')
            if density_result:
                density_match = re.search(r'(\d+)', density_result)
                if density_match:
                    display_info['screen_density'] = int(density_match.group(1))
                    
            # Screen state (on/off)
            screen_state = self._run_adb_command('shell dumpsys power | grep "Display Power"')
            if screen_state:
                if 'ON' in screen_state.upper():
                    display_info['screen_on'] = 1.0
                else:
                    display_info['screen_on'] = 0.0
                    
            return display_info
            
        except Exception as e:
            logger.debug(f"Failed to get display info: {e}")
        return {}
    
    # Optimized parser methods for parallel execution

    def _parse_cpu_usage(self, result: str) -> Optional[float]:
        """Parse CPU usage from /proc/stat output"""
        try:
            lines = result.split('\n')
            cpu_line = lines[0]  # First line is total CPU
            values = cpu_line.split()[1:]
            values = [int(v) for v in values]
            
            total = sum(values)
            idle = values[3]  # idle time
            usage = ((total - idle) / total) * 100
            return round(usage, 2)
        except:
            return None

    def _parse_cpu_temperature(self, result: str) -> Optional[float]:
        """Parse CPU temperature from thermal zone"""
        try:
            temp = int(result.strip()) / 1000.0  # Convert from millidegrees
            return round(temp, 1)
        except:
            return None

    def _parse_memory_info(self, result: str) -> Dict[str, float]:
        """Parse memory info from /proc/meminfo"""
        memory_info = {}
        try:
            for line in result.split('\n'):
                if 'MemTotal:' in line:
                    total_match = re.search(r'(\d+)', line)
                    if total_match:
                        memory_info['memory_total'] = round(int(total_match.group(1)) / 1024, 2)
                elif 'MemAvailable:' in line:
                    avail_match = re.search(r'(\d+)', line)
                    if avail_match:
                        memory_info['memory_available'] = round(int(avail_match.group(1)) / 1024, 2)
                elif 'MemFree:' in line:
                    free_match = re.search(r'(\d+)', line)
                    if free_match:
                        memory_info['memory_free'] = round(int(free_match.group(1)) / 1024, 2)
                        
            # Calculate used memory and usage percentage
            if 'memory_total' in memory_info and 'memory_available' in memory_info:
                memory_info['memory_used'] = round(memory_info['memory_total'] - memory_info['memory_available'], 2)
                memory_info['memory_system_available'] = memory_info['memory_available']
                # 计算内存使用百分比
                usage_percent = (memory_info['memory_used'] / memory_info['memory_total']) * 100
                memory_info['memory_usage_percent'] = round(usage_percent, 2)
                
        except Exception as e:
            logger.debug(f"Failed to parse memory info: {e}")
        return memory_info

    def _parse_storage_info(self, result: str) -> Dict[str, float]:
        """Parse storage info from df output"""
        storage_info = {}
        try:
            lines = result.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    total_kb = int(parts[1])
                    used_kb = int(parts[2])
                    avail_kb = int(parts[3])
                    
                    storage_info['storage_total'] = round(total_kb / 1024, 2)
                    storage_info['storage_used'] = round(used_kb / 1024, 2)
                    storage_info['storage_available'] = round(avail_kb / 1024, 2)
                    storage_info['storage_usage_percent'] = round((used_kb / total_kb) * 100, 2)
        except Exception as e:
            logger.debug(f"Failed to parse storage info: {e}")
        return storage_info

    def _parse_battery_info(self, result: str) -> Dict[str, float]:
        """Parse battery info from dumpsys battery"""
        battery_info = {}
        try:
            for line in result.split('\n'):
                if 'level:' in line:
                    level_match = re.search(r'level: (\d+)', line)
                    if level_match:
                        battery_info['battery_level'] = float(level_match.group(1))
                elif 'temperature:' in line:
                    temp_match = re.search(r'temperature: (\d+)', line)
                    if temp_match:
                        battery_info['battery_temperature'] = round(int(temp_match.group(1)) / 10.0, 1)
                elif 'voltage:' in line:
                    volt_match = re.search(r'voltage: (\d+)', line)
                    if volt_match:
                        battery_info['battery_voltage'] = round(int(volt_match.group(1)) / 1000.0, 3)
        except Exception as e:
            logger.debug(f"Failed to parse battery info: {e}")
        return battery_info

    def _parse_load_info(self, result: str) -> Dict[str, float]:
        """Parse system load from /proc/loadavg"""
        load_info = {}
        try:
            parts = result.strip().split()
            if len(parts) >= 3:
                load_info['load_1min'] = float(parts[0])
                load_info['load_5min'] = float(parts[1])
                load_info['load_15min'] = float(parts[2])
        except Exception as e:
            logger.debug(f"Failed to parse load info: {e}")
        return load_info

    def _parse_display_info(self, result: str) -> Dict[str, float]:
        """Parse display info from wm size output"""
        display_info = {}
        try:
            if 'x' in result:
                size_match = re.search(r'(\d+)x(\d+)', result)
                if size_match:
                    display_info['screen_width'] = float(size_match.group(1))
                    display_info['screen_height'] = float(size_match.group(2))
        except Exception as e:
            logger.debug(f"Failed to parse display info: {e}")
        return display_info

    def _parse_uptime_info(self, result: str) -> Dict[str, float]:
        """Parse uptime info from /proc/uptime"""
        uptime_info = {}
        try:
            # /proc/uptime format: "uptime_seconds idle_seconds"
            # Example: "12345.67 98765.43"
            parts = result.strip().split()
            if len(parts) >= 2:
                uptime_seconds = float(parts[0])
                idle_seconds = float(parts[1])
                
                # Convert to more readable formats
                uptime_info['uptime_seconds'] = round(uptime_seconds, 2)
                uptime_info['uptime_hours'] = round(uptime_seconds / 3600, 2)
                uptime_info['uptime_days'] = round(uptime_seconds / 86400, 2)
                
                # Calculate system load percentage (100% - idle percentage)
                if uptime_seconds > 0:
                    idle_percentage = (idle_seconds / uptime_seconds) * 100
                    system_load_percentage = 100 - idle_percentage
                    uptime_info['system_load_percentage'] = round(max(0, min(100, system_load_percentage)), 2)
                    uptime_info['idle_percentage'] = round(min(100, idle_percentage), 2)
                
                # Add idle time info
                uptime_info['idle_seconds'] = round(idle_seconds, 2)
                
        except Exception as e:
            logger.debug(f"Failed to parse uptime info: {e}")
        return uptime_info
    
    # App-specific parser methods
