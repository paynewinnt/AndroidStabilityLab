"""ADB command execution and collector performance helpers."""

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from stability.infrastructure.command_runner import ADBCommandRunner

from .cache import EnhancedCache

logger = logging.getLogger(__name__)

class BatchADBExecutor:
    """批量ADB命令执行器"""
    def __init__(self, device_id: str = None, max_workers: int = 6):
        self.device_id = device_id
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.command_queue = queue.Queue()
        self.batch_results = {}
        
    def execute_batch(self, commands: List[Tuple[str, str]], timeout: int = 10) -> Dict[str, str]:
        """
        批量执行ADB命令
        commands: [(command_id, command), ...]
        返回: {command_id: result, ...}
        """
        futures = {}
        
        for cmd_id, command in commands:
            future = self.executor.submit(self._execute_single_command, command, timeout)
            futures[cmd_id] = future
            
        results = {}
        for cmd_id, future in futures.items():
            try:
                results[cmd_id] = future.result(timeout=timeout + 2)
            except Exception as e:
                logger.debug(f"Command {cmd_id} failed: {e}")
                results[cmd_id] = None
                
        return results
        
    def _execute_single_command(self, command: str, timeout: int) -> Optional[str]:
        """执行单个ADB命令"""
        result = ADBCommandRunner(device_id=self.device_id).run_adb(command.split(), timeout_seconds=timeout)
        if result.ok:
            return result.stdout.strip()
        return None


class ADBCommandMixin:
    def _run_adb_command(self, command: str, shell: bool = False, log_errors: bool = True, use_cache: bool = False) -> Optional[str]:
        # Check cache first if enabled
        if use_cache:
            cache_key = f"{command}_{self.device_id}"
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result
        
        runner = ADBCommandRunner(device_id=self.device_id)

        for attempt in range(self.retry_count):
            result = runner.run_adb(command.split(), timeout_seconds=self.timeout)
            if result.ok:
                output = result.stdout.strip()

                # Cache the result if caching is enabled
                if use_cache and output:
                    self._cache_result(cache_key, output)

                return output
            if result.timed_out:
                if log_errors and attempt == self.retry_count - 1:  # Only log on final attempt
                    logger.warning(f"ADB command timeout: {command}")
            elif result.returncode not in {0, None}:
                if log_errors and attempt == self.retry_count - 1:  # Only log on final attempt
                    logger.debug(
                        "ADB command failed: %s, returncode=%s, stderr=%s",
                        command,
                        result.returncode,
                        (result.stderr or "").strip(),
                    )
                
            # Shorter sleep between retries for faster recovery
            if attempt < self.retry_count - 1:
                time.sleep(0.1)
                
        return None
    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """Get cached result if still valid"""
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if time.time() - cached_data['timestamp'] < self._cache_timeout:
                return cached_data['result']
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
        return None
    def _cache_result(self, cache_key: str, result: str):
        """Cache a result with timestamp"""
        self._cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
    def _run_adb_commands_parallel(self, commands: List[str], log_errors: bool = True) -> Dict[str, Optional[str]]:
        """Run multiple ADB commands in parallel using threading with performance tracking"""
        results = {}
        threads = []
        result_queue = queue.Queue()
        start_time = time.time()
        
        def run_command(cmd, cmd_key):
            cmd_start = time.time()
            result = self._run_adb_command(cmd, log_errors=log_errors)
            cmd_time = time.time() - cmd_start
            
            # Track command performance
            self._command_times[cmd_key] = cmd_time
            if cmd_time > self.timeout * 2:  # Mark as slow if takes >2x expected time
                self._slow_commands.add(cmd.split()[0])
                logger.debug(f"Slow command detected: {cmd} took {cmd_time:.1f}s")
            
            result_queue.put((cmd_key, result, cmd_time))
        
        # Start threads for each command
        for i, command in enumerate(commands):
            cmd_key = f"cmd_{i}_{command.split()[0]}"  # Create unique key
            thread = threading.Thread(target=run_command, args=(command, cmd_key))
            thread.daemon = True
            threads.append(thread)
            thread.start()
        
        # Collect results with improved timeout handling
        completed_threads = 0
        for thread in threads:
            # Use a reasonable timeout per thread
            timeout_per_thread = min(self.timeout + 2, 8)  # Max 8 seconds per thread
            thread.join(timeout=timeout_per_thread)
            if thread.is_alive():
                logger.warning(f"Thread still running after {timeout_per_thread}s timeout")
            else:
                completed_threads += 1
        
        # Get all results from queue with timeout
        collected_results = 0
        queue_timeout = time.time() + 2  # 2 seconds to collect results
        while not result_queue.empty() and time.time() < queue_timeout:
            try:
                cmd_key, result, cmd_time = result_queue.get(timeout=0.1)
                results[cmd_key] = result
                collected_results += 1
            except queue.Empty:
                break
        
        total_time = time.time() - start_time
        logger.debug(f"Parallel execution: {completed_threads}/{len(threads)} threads completed, "
                    f"{collected_results} results collected in {total_time:.1f}s")
        
        return results
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        cache_stats = self.enhanced_cache.get_stats()
        
        return {
            'cache_performance': cache_stats,
            'command_execution_times': dict(self._performance_stats),
            'slow_commands': list(self._slow_commands),
            'collection_intervals': self._collection_intervals,
            'last_collection_times': dict(self._last_collection_time)
        }
    def optimize_collection_intervals(self):
        """动态优化采集间隔"""
        stats = self.get_performance_stats()
        
        # 根据缓存命中率调整间隔
        hit_rate = stats['cache_performance']['hit_rate']
        
        if hit_rate > 0.8:  # 命中率高，可以增加间隔
            for key in self._collection_intervals:
                self._collection_intervals[key] *= 1.1
        elif hit_rate < 0.3:  # 命中率低，减少间隔
            for key in self._collection_intervals:
                self._collection_intervals[key] *= 0.9
                
        # 限制间隔范围
        for key in self._collection_intervals:
            self._collection_intervals[key] = max(1.0, 
                min(self._collection_intervals[key], 10.0))
    def reset_performance_tracking(self):
        """重置性能跟踪"""
        self._performance_stats.clear()
        self._slow_commands.clear()
        self.enhanced_cache = EnhancedCache()
        self._last_collection_time.clear()
    def cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        
        # 清理L1缓存
        expired_keys = []
        for key, data in self.enhanced_cache.l1_cache.items():
            if current_time - data['time'] > 60:  # 60秒过期
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.enhanced_cache.l1_cache[key]
            
        # 清理L2缓存
        expired_keys = []
        for key, data in self.enhanced_cache.l2_cache.items():
            if current_time - data['time'] > 120:  # 120秒过期
                expired_keys.append(key)
                
        for key in expired_keys:
            del self.enhanced_cache.l2_cache[key]
