"""Application performance aggregation helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AppMetricsMixin:
    def get_app_performance(self, package_name: str) -> Dict[str, float]:
        """优化的应用性能数据获取"""
        data = {'app_package': package_name}
        current_time = time.time()
        
        # 检查缓存
        cache_key = f"app_performance_{package_name}"
        if (current_time - self._last_collection_time.get(cache_key, 0) < 
            self._collection_intervals['app_basic']):
            cached_data = self.enhanced_cache.get(cache_key)
            if cached_data:
                return cached_data
        
        # 批量执行应用性能命令
        batch_commands = [
            ("cpuinfo", "shell dumpsys cpuinfo"),
            ("meminfo", f"shell dumpsys meminfo {package_name}"),
            ("gfxinfo", f"shell dumpsys gfxinfo {package_name} framestats"),
            ("batterystats", f"shell dumpsys batterystats {package_name}"),
            ("top_app", f"shell top -n 1 -b | grep {package_name}")
        ]
        
        start_time = time.time()
        results = self.batch_executor.execute_batch(batch_commands, timeout=10)
        execution_time = time.time() - start_time
        
        # 记录性能统计
        self._performance_stats[f'app_collection_time_{package_name}'] = execution_time
        
        data.update(self._parse_app_performance_batch(results, package_name))
        
        # 缓存结果
        self.enhanced_cache.put(cache_key, data, current_time)
        self._last_collection_time[cache_key] = current_time
        
        return data

    def get_multiple_app_performance(self, package_names: List[str]) -> Dict[str, Dict[str, float]]:
        """批量获取多个应用的性能数据 - 新增优化方法"""
        if not package_names:
            return {}
            
        current_time = time.time()
        results = {}
        
        # 检查哪些应用需要更新数据
        apps_to_update = []
        for package_name in package_names:
            cache_key = f"app_performance_{package_name}"
            if (current_time - self._last_collection_time.get(cache_key, 0) >= 
                self._collection_intervals['app_basic']):
                apps_to_update.append(package_name)
            else:
                # 从缓存获取
                cached_data = self.enhanced_cache.get(cache_key)
                if cached_data:
                    results[package_name] = cached_data
        
        if not apps_to_update:
            return results
            
        # 第一步：获取所有应用的基础信息
        batch_commands_phase1 = [
            ("cpuinfo_all", "shell dumpsys cpuinfo"),
            ("top_all", "shell top -n 1 -b")
        ]
        
        phase1_results = self.batch_executor.execute_batch(batch_commands_phase1, timeout=10)
        all_cpu_info = phase1_results.get('cpuinfo_all', '')
        all_top_info = phase1_results.get('top_all', '')
        
        # 第二步：基于top输出获取实际进程名，然后构建第二批命令
        batch_commands_phase2 = []
        actual_process_names = {}
        
        for package_name in apps_to_update:
            # 从top输出中找到实际的进程名
            actual_process_name = self._get_actual_process_name_from_top(all_top_info, package_name)
            actual_process_names[package_name] = actual_process_name or package_name
            
            # 使用实际进程名构建命令
            batch_commands_phase2.extend([
                (f"meminfo_{package_name}", f"shell dumpsys meminfo {actual_process_names[package_name]}"),
                (f"gfxinfo_{package_name}", f"shell dumpsys gfxinfo {package_name} framestats"),
                (f"batterystats_{package_name}", f"shell dumpsys batterystats {package_name}")
            ])
        
        # 批量执行第二阶段命令
        start_time = time.time()
        batch_results = self.batch_executor.execute_batch(batch_commands_phase2, timeout=15)
        execution_time = time.time() - start_time
        
        # 记录性能统计
        self._performance_stats['multi_app_collection_time'] = execution_time
        
        # 解析结果
        for package_name in apps_to_update:
            app_data = {'app_package': package_name}
            
            # 解析各项数据
            if all_cpu_info:
                cpu_usage = self._parse_app_cpu_usage(all_cpu_info, package_name)
                if cpu_usage is not None:
                    app_data['cpu_usage'] = cpu_usage
            
            meminfo_result = batch_results.get(f"meminfo_{package_name}")
            if meminfo_result:
                memory_info = self._parse_app_memory_info(meminfo_result)
                app_data.update(memory_info)
            
            gfxinfo_result = batch_results.get(f"gfxinfo_{package_name}")
            if gfxinfo_result:
                app_data.update(self._parse_gfxinfo_metrics(gfxinfo_result))
            
            batterystats_result = batch_results.get(f"batterystats_{package_name}")
            if batterystats_result:
                power_info = self._parse_app_power_info(batterystats_result)
                app_data.update(power_info)
            
            # 解析top命令结果（使用第一阶段的结果）
            if all_top_info:
                top_data = self._parse_top_app(all_top_info, package_name)
                if top_data:
                    app_data.update(top_data)
            
            # 缓存结果
            cache_key = f"app_performance_{package_name}"
            self.enhanced_cache.put(cache_key, app_data, current_time)
            self._last_collection_time[cache_key] = current_time
            
            results[package_name] = app_data
        
        return results

    def _parse_app_performance_batch(self, results: Dict[str, str], package_name: str) -> Dict[str, float]:
        """批量解析应用性能数据"""
        data = {}
        
        try:
            # CPU使用率
            if results.get('cpuinfo'):
                cpu_usage = self._parse_app_cpu_usage(results['cpuinfo'], package_name)
                if cpu_usage is not None:
                    data['cpu_usage'] = cpu_usage
            
            # TOP命令解析（应用级别）
            if results.get('top_app'):
                top_data = self._parse_top_app(results['top_app'], package_name)
                if top_data:
                    data.update(top_data)
                    
            # 内存信息
            if results.get('meminfo'):
                memory_info = self._parse_app_memory_info(results['meminfo'])
                data.update(memory_info)
                
            # FPS信息
            if results.get('gfxinfo'):
                data.update(self._parse_gfxinfo_metrics(results['gfxinfo']))
                    
            # 功耗信息 - 使用增强的解析方法
            if results.get('batterystats'):
                power_info = self._parse_app_power_info_enhanced(results['batterystats'], package_name)
                data.update(power_info)
            else:
                # 如果没有batterystats结果，尝试估算功耗
                estimated_power = self._estimate_power_consumption(package_name)
                if estimated_power is not None:
                    data['power_consumption'] = estimated_power
                
        except Exception as e:
            logger.error(f"解析应用性能数据失败 {package_name}: {e}")
            
        return data

    def _get_app_cpu_usage(self, package_name: str) -> Optional[float]:
        try:
            # First get full cpuinfo, then search for package
            result = self._run_adb_command("shell dumpsys cpuinfo")
            if result and package_name in result:
                # Find lines containing the package name
                lines = result.split('\n')
                for line in lines:
                    if package_name in line and '%' in line:
                        # Parse CPU usage from the line
                        match = re.search(r'(\d+(?:\.\d+)?)%', line)
                        if match:
                            return float(match.group(1))
        except Exception as e:
            logger.debug(f"Failed to get app CPU usage for {package_name}: {e}")
        return None

    def _get_app_memory(self, package_name: str) -> Dict[str, float]:
        try:
            result = self._run_adb_command(f"shell dumpsys meminfo {package_name}")
            if result:
                memory_info = {}
                
                # Parse PSS memory
                pss_match = re.search(r'TOTAL\s+(\d+)', result)
                if pss_match:
                    memory_info['memory_pss'] = round(int(pss_match.group(1)) / 1024, 2)
                
                # Parse Java heap
                java_match = re.search(r'Java Heap:\s+(\d+)', result)
                if java_match:
                    memory_info['memory_java'] = round(int(java_match.group(1)) / 1024, 2)
                
                # Parse Native heap
                native_match = re.search(r'Native Heap:\s+(\d+)', result)
                if native_match:
                    memory_info['memory_native'] = round(int(native_match.group(1)) / 1024, 2)
                
                return memory_info
        except Exception as e:
            logger.debug(f"Failed to get app memory for {package_name}: {e}")
        return {}

    def _parse_app_cpu_usage(self, result: str, package_name: str) -> Optional[float]:
        """Parse app CPU usage from cpuinfo output"""
        try:
            if package_name in result:
                lines = result.split('\n')
                for line in lines:
                    if package_name in line and '%' in line:
                        match = re.search(r'(\d+(?:\.\d+)?)%', line)
                        if match:
                            return float(match.group(1))
        except:
            return None
        return None

    def _parse_app_memory_info(self, result: str) -> Dict[str, float]:
        """Parse app memory info from meminfo output"""
        memory_info = {}
        try:
            # Parse PSS memory
            pss_match = re.search(r'TOTAL\s+(\d+)', result)
            if pss_match:
                memory_info['memory_pss'] = round(int(pss_match.group(1)) / 1024, 2)
            
            # Parse Java heap
            java_match = re.search(r'Java Heap:\s+(\d+)', result)
            if java_match:
                memory_info['memory_java'] = round(int(java_match.group(1)) / 1024, 2)
            
            # Parse Native heap
            native_match = re.search(r'Native Heap:\s+(\d+)', result)
            if native_match:
                memory_info['memory_native'] = round(int(native_match.group(1)) / 1024, 2)
                
        except Exception as e:
            logger.debug(f"Failed to parse app memory info: {e}")
        return memory_info
