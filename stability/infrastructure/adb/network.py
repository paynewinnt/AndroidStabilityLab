"""System and app network metric helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class NetworkMetricsMixin:
    def _get_default_network_data(self) -> Dict[str, float]:
        """Return default network data when parsing fails"""
        return {
            'network_rx_total': 0.0,
            'network_tx_total': 0.0,
            'network': 0.0,
            'network_rx': 0.0,
            'network_tx': 0.0
        }

    def _get_network_data_with_fallback(self) -> Dict[str, float]:
        """Get network data with multiple fallback methods"""
        # Method 1: Try /proc/net/dev (preferred)
        try:
            network_result = self._run_adb_command("shell cat /proc/net/dev", use_cache=True)
            if network_result and network_result.strip():
                network_data = self._parse_network_data(network_result)
                if network_data and any(v > 0 for k, v in network_data.items() if 'total' in k):
                    logger.debug("Network data successfully obtained from /proc/net/dev")
                    return network_data
        except Exception as e:
            logger.debug(f"Failed to get network data from /proc/net/dev: {e}")
        
        # Method 2: Try alternative network statistics
        try:
            netstats_result = self._run_adb_command("shell dumpsys netstats", use_cache=True)
            if netstats_result:
                network_data = self._parse_netstats_data(netstats_result)
                if network_data:
                    logger.debug("Network data obtained from dumpsys netstats")
                    return network_data
        except Exception as e:
            logger.debug(f"Failed to get network data from dumpsys netstats: {e}")
        
        # Method 3: Try /proc/net/netstat
        try:
            netstat_result = self._run_adb_command("shell cat /proc/net/netstat", use_cache=True)
            if netstat_result:
                # This method doesn't provide total bytes but can indicate network activity
                logger.debug("Network activity detected from /proc/net/netstat")
        except Exception as e:
            logger.debug(f"Failed to get network data from /proc/net/netstat: {e}")
        
        logger.debug("All network data collection methods failed, returning default data")
        return self._get_default_network_data()

    def _parse_netstats_data(self, netstats_output: str) -> Dict[str, float]:
        """Parse network data from dumpsys netstats"""
        try:
            # Simple parsing of netstats - look for total bytes
            import re
            rx_matches = re.findall(r'rx.*?(\d+)\s*bytes', netstats_output, re.IGNORECASE)
            tx_matches = re.findall(r'tx.*?(\d+)\s*bytes', netstats_output, re.IGNORECASE)
            
            if rx_matches or tx_matches:
                total_rx = sum(int(x) for x in rx_matches)
                total_tx = sum(int(x) for x in tx_matches)
                
                current_time = time.time()
                rx_kb = total_rx / 1024
                tx_kb = total_tx / 1024
                
                network_data = {
                    'network_rx_total': round(rx_kb, 2),
                    'network_tx_total': round(tx_kb, 2)
                }
                
                # Calculate speeds
                if hasattr(self, '_last_system_network'):
                    time_diff = current_time - self._last_system_network['time']
                    if time_diff > 0:
                        rx_speed = (rx_kb - self._last_system_network['rx']) / time_diff
                        tx_speed = (tx_kb - self._last_system_network['tx']) / time_diff
                        network_data['network_rx'] = round(max(0, rx_speed), 2)
                        network_data['network_tx'] = round(max(0, tx_speed), 2)
                        network_data['network'] = round(max(0, rx_speed + tx_speed), 2)
                else:
                    network_data['network'] = 0.0
                    network_data['network_rx'] = 0.0
                    network_data['network_tx'] = 0.0
                
                # Store for next calculation
                self._last_system_network = {
                    'time': current_time,
                    'rx': rx_kb,
                    'tx': tx_kb
                }
                
                return network_data
        except Exception as e:
            logger.debug(f"Failed to parse netstats data: {e}")
        return {}

    def _parse_network_data(self, network_output: str) -> Dict[str, float]:
        """解析网络数据"""
        try:
            if not network_output or not network_output.strip():
                logger.debug("Empty network output")
                return self._get_default_network_data()
                
            lines = network_output.strip().split('\n')
            logger.debug(f"Network output lines: {len(lines)}")
            
            if len(lines) < 3:  # Need header + at least one interface
                logger.debug("Insufficient network data lines")
                return self._get_default_network_data()
                
            # Skip first 2 lines (headers)
            data_lines = lines[2:]
            total_rx = total_tx = 0
            interface_count = 0
            
            for line in data_lines:
                if ':' in line and line.strip():
                    try:
                        # Split by ':' to separate interface name and stats
                        parts = line.split(':')
                        if len(parts) < 2:
                            continue
                        
                        interface_name = parts[0].strip()
                        # Skip loopback interface
                        if interface_name == 'lo':
                            continue
                            
                        # Parse stats (columns: rx_bytes, rx_packets, ..., tx_bytes, tx_packets, ...)
                        stats = parts[1].split()
                        if len(stats) >= 9:
                            rx_bytes = int(stats[0])
                            tx_bytes = int(stats[8])
                            total_rx += rx_bytes
                            total_tx += tx_bytes
                            interface_count += 1
                            logger.debug(f"Interface {interface_name}: rx={rx_bytes}, tx={tx_bytes}")
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse network line: {line}, error: {e}")
                        continue
            
            logger.debug(f"Total interfaces processed: {interface_count}, total_rx: {total_rx}, total_tx: {total_tx}")
            
            # Convert to KB and calculate rates
            current_time = time.time()
            rx_kb = total_rx / 1024
            tx_kb = total_tx / 1024
            
            network_data = {
                'network_rx_total': round(rx_kb, 2),
                'network_tx_total': round(tx_kb, 2)
            }
            
            # Calculate network speed if we have previous data
            if hasattr(self, '_last_system_network'):
                time_diff = current_time - self._last_system_network['time']
                if time_diff > 0:
                    rx_speed = (rx_kb - self._last_system_network['rx']) / time_diff
                    tx_speed = (tx_kb - self._last_system_network['tx']) / time_diff
                    # Calculate individual speeds
                    network_data['network_rx'] = round(max(0, rx_speed), 2)
                    network_data['network_tx'] = round(max(0, tx_speed), 2)
                    # Use total network speed (rx + tx) for main display
                    total_speed = max(0, rx_speed + tx_speed)
                    network_data['network'] = round(total_speed, 2)
            else:
                # First time - provide default values
                network_data['network'] = 0.0
                network_data['network_rx'] = 0.0
                network_data['network_tx'] = 0.0
            
            # Store for next calculation
            self._last_system_network = {
                'time': current_time,
                'rx': rx_kb,
                'tx': tx_kb
            }
            
            return network_data
            
        except Exception as e:
            logger.debug(f"Failed to parse network data: {e}")
            return self._get_default_network_data()

    def _get_system_network_stats(self) -> Dict[str, float]:
        try:
            result = self._run_adb_command("shell cat /proc/net/dev")
            if result:
                lines = result.split('\n')[2:]  # Skip headers
                total_rx = total_tx = 0
                
                for line in lines:
                    if ':' in line:
                        parts = line.split(':')[1].split()
                        rx_bytes = int(parts[0])
                        tx_bytes = int(parts[8])
                        total_rx += rx_bytes
                        total_tx += tx_bytes
                
                # Convert to KB
                current_time = time.time()
                rx_kb = total_rx / 1024
                tx_kb = total_tx / 1024
                
                # Calculate speed if we have previous data
                network_data = {
                    'network_rx_total': round(rx_kb, 2),
                    'network_tx_total': round(tx_kb, 2)
                }
                
                if hasattr(self, '_last_system_network'):
                    time_diff = current_time - self._last_system_network['time']
                    if time_diff > 0:
                        rx_speed = (rx_kb - self._last_system_network['rx']) / time_diff
                        tx_speed = (tx_kb - self._last_system_network['tx']) / time_diff
                        network_data['network_rx'] = round(max(0, rx_speed), 2)
                        network_data['network_tx'] = round(max(0, tx_speed), 2)
                
                self._last_system_network = {
                    'time': current_time,
                    'rx': rx_kb,
                    'tx': tx_kb
                }
                
                return network_data
        except Exception as e:
            logger.debug(f"Failed to get system network stats: {e}")
        return {}

    def _get_app_network_stats(self, package_name: str) -> Dict[str, float]:
        """Get app network statistics with caching and optimized fallback methods"""
        # Check cache first
        cache_key = f"network_{package_name}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            try:
                return eval(cached_result)  # Convert string back to dict
            except:
                pass
        
        network_data = {}
        
        # Get UID first with caching (most expensive operation)
        uid = self._get_cached_uid(package_name)
        if uid is None:
            logger.debug(f"Could not get UID for {package_name}")
            return {}
        
        # Try methods in order of efficiency
        methods = [
            ('traffic_stats', self._get_network_via_traffic_stats_optimized),
            ('netstats', self._get_network_via_netstats_optimized),
            ('qtaguid', self._get_network_via_qtaguid_optimized)
        ]
        
        for method_name, method_func in methods:
            if method_name in self._slow_commands:
                continue  # Skip known slow methods
                
            try:
                network_data = method_func(package_name, uid)
                if network_data:
                    # Cache successful result
                    self._cache_result(cache_key, str(network_data))
                    logger.debug(f"Network stats via {method_name} for {package_name}")
                    return network_data
            except Exception as e:
                logger.debug(f"Network method {method_name} failed for {package_name}: {e}")
                continue
        
        logger.debug(f"All network stat methods failed for {package_name}")
        return {}

    def _get_cached_uid(self, package_name: str) -> Optional[str]:
        """Get UID for package with caching"""
        if package_name in self._uid_cache:
            cached_data = self._uid_cache[package_name]
            if time.time() - cached_data['timestamp'] < 30:  # Cache UIDs for 30 seconds
                return cached_data['uid']
        
        try:
            # Use faster pm command instead of full dumpsys
            result = self._run_adb_command(f"shell pm list packages -U {package_name}")
            if result:
                # Format: package:com.example.app uid:10123
                uid_match = re.search(r'uid:(\d+)', result)
                if uid_match:
                    uid = uid_match.group(1)
                    self._uid_cache[package_name] = {
                        'uid': uid,
                        'timestamp': time.time()
                    }
                    return uid
            
            # Fallback to compiled pattern
            result = self._run_adb_command(f"shell dumpsys package {package_name}")
            if result:
                uid_match = self._compiled_patterns['uid_lookup'].search(result)
                if uid_match:
                    uid = uid_match.group(1)
                    self._uid_cache[package_name] = {
                        'uid': uid,
                        'timestamp': time.time()
                    }
                    return uid
                    
        except Exception as e:
            logger.debug(f"Failed to get UID for {package_name}: {e}")
        
        return None

    def _get_network_via_traffic_stats_optimized(self, package_name: str, uid: str) -> Dict[str, float]:
        """Optimized traffic stats collection"""
        try:
            # Use targeted netstats query
            result = self._run_adb_command(f"shell dumpsys netstats detail uid {uid}")
            if not result:
                return {}
            
            # Parse with compiled patterns for better performance
            pattern = rf'uid={uid}.*?rb=(\d+).*?tb=(\d+)'
            matches = re.findall(pattern, result, re.DOTALL)
            
            if matches:
                total_rx = total_tx = 0
                for match in matches:
                    total_rx += int(match[0])
                    total_tx += int(match[1])
                
                current_time = time.time()
                rx_kb = total_rx / 1024
                tx_kb = total_tx / 1024
                
                # Calculate rates if we have previous data
                if package_name in self._last_network_stats:
                    last_data = self._last_network_stats[package_name]
                    time_diff = current_time - last_data['timestamp']
                    
                    if time_diff > 0:
                        rx_rate = max(0, (rx_kb - last_data['rx_kb']) / time_diff)
                        tx_rate = max(0, (tx_kb - last_data['tx_kb']) / time_diff)
                    else:
                        rx_rate = tx_rate = 0
                else:
                    rx_rate = tx_rate = 0
                
                # Store current stats for next calculation
                self._last_network_stats[package_name] = {
                    'rx_kb': rx_kb,
                    'tx_kb': tx_kb,
                    'timestamp': current_time
                }
                
                return {
                    'network_rx_kb': rx_kb,
                    'network_tx_kb': tx_kb,
                    'network_rx_rate': round(rx_rate, 2),
                    'network_tx_rate': round(tx_rate, 2)
                }
                
        except Exception as e:
            logger.debug(f"Traffic stats method failed for {package_name}: {e}")
        
        return {}

    def _get_network_via_netstats_optimized(self, package_name: str, uid: str) -> Dict[str, float]:
        """Optimized netstats collection"""
        try:
            # Use more targeted command
            result = self._run_adb_command(f"shell cat /proc/net/xt_qtaguid/stats | grep {uid}")
            if not result:
                return {}
            
            lines = result.strip().split('\n')
            total_rx = total_tx = 0
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 8 and parts[3] == uid:
                    total_rx += int(parts[5])
                    total_tx += int(parts[7])
            
            if total_rx > 0 or total_tx > 0:
                return {
                    'network_rx_kb': round(total_rx / 1024, 2),
                    'network_tx_kb': round(total_tx / 1024, 2),
                    'network_rx_rate': 0,  # Rate calculation would need history
                    'network_tx_rate': 0
                }
                
        except Exception as e:
            logger.debug(f"Netstats method failed for {package_name}: {e}")
        
        return {}

    def _get_network_via_qtaguid_optimized(self, package_name: str, uid: str) -> Dict[str, float]:
        """Optimized qtaguid collection"""
        # This method is often slow and requires root, so make it very simple
        return {}

    def _get_network_via_traffic_stats(self, package_name: str) -> Dict[str, float]:
        try:
            # Get app UID first
            uid_result = self._run_adb_command(f"shell dumpsys package {package_name}")
            if not uid_result:
                return {}
                
            uid_match = re.search(r'userId=(\d+)', uid_result)
            if not uid_match:
                return {}
                
            uid = uid_match.group(1)
            
            # Use dumpsys netstats
            result = self._run_adb_command(f"shell dumpsys netstats detail")
            if result and uid in result:
                # Parse network usage from netstats
                pattern = rf'uid={uid}.*?rb=(\d+).*?tb=(\d+)'
                matches = re.findall(pattern, result, re.DOTALL)
                
                if matches:
                    total_rx = total_tx = 0
                    for match in matches:
                        total_rx += int(match[0])
                        total_tx += int(match[1])
                    
                    current_time = time.time()
                    rx_kb = total_rx / 1024
                    tx_kb = total_tx / 1024
                    
                    network_data = {
                        'network_rx_total': round(rx_kb, 2),
                        'network_tx_total': round(tx_kb, 2)
                    }
                    
                    # Calculate speed
                    key = f"{package_name}_traffic"
                    if key in self._last_network_stats:
                        time_diff = current_time - self._last_network_stats[key]['time']
                        if time_diff > 0:
                            rx_speed = (rx_kb - self._last_network_stats[key]['rx']) / time_diff
                            tx_speed = (tx_kb - self._last_network_stats[key]['tx']) / time_diff
                            network_data['network_rx'] = round(max(0, rx_speed), 2)
                            network_data['network_tx'] = round(max(0, tx_speed), 2)
                    
                    self._last_network_stats[key] = {
                        'time': current_time,
                        'rx': rx_kb,
                        'tx': tx_kb
                    }
                    
                    return network_data
                    
        except Exception as e:
            logger.debug(f"Traffic stats method failed for {package_name}: {e}")
        return {}

    def _get_network_via_netstats(self, package_name: str) -> Dict[str, float]:
        try:
            # Try using package manager to get network usage
            result = self._run_adb_command(f"shell dumpsys package {package_name}")
            if result:
                # Look for network usage in package dump
                rx_match = re.search(r'networkLocationRequests.*?(\d+)', result)
                tx_match = re.search(r'dataActivity.*?(\d+)', result)
                
                if rx_match or tx_match:
                    rx_bytes = int(rx_match.group(1)) if rx_match else 0
                    tx_bytes = int(tx_match.group(1)) if tx_match else 0
                    
                    return {
                        'network_rx_total': round(rx_bytes / 1024, 2),
                        'network_tx_total': round(tx_bytes / 1024, 2)
                    }
                    
        except Exception as e:
            logger.debug(f"Netstats method failed for {package_name}: {e}")
        return {}

    def _get_network_via_qtaguid(self, package_name: str) -> Dict[str, float]:
        try:
            # Get app UID first
            uid_result = self._run_adb_command(f"shell dumpsys package {package_name}")
            if not uid_result:
                return {}
                
            uid_match = re.search(r'userId=(\d+)', uid_result)
            if not uid_match:
                return {}
                
            uid = uid_match.group(1)
            
            # Try to read xt_qtaguid stats (may not exist on newer Android versions)
            result = self._run_adb_command("shell cat /proc/net/xt_qtaguid/stats", log_errors=False)
            if result and uid in result:
                total_rx = total_tx = 0
                for line in result.split('\n'):
                    if line.strip() and uid in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                rx_bytes = int(parts[5])
                                tx_bytes = int(parts[7])
                                total_rx += rx_bytes
                                total_tx += tx_bytes
                            except (ValueError, IndexError):
                                continue
                
                current_time = time.time()
                rx_kb = total_rx / 1024
                tx_kb = total_tx / 1024
                
                network_data = {
                    'network_rx_total': round(rx_kb, 2),
                    'network_tx_total': round(tx_kb, 2)
                }
                
                # Calculate speed
                key = f"{package_name}_qtaguid"
                if key in self._last_network_stats:
                    time_diff = current_time - self._last_network_stats[key]['time']
                    if time_diff > 0:
                        rx_speed = (rx_kb - self._last_network_stats[key]['rx']) / time_diff
                        tx_speed = (tx_kb - self._last_network_stats[key]['tx']) / time_diff
                        network_data['network_rx'] = round(max(0, rx_speed), 2)
                        network_data['network_tx'] = round(max(0, tx_speed), 2)
                
                self._last_network_stats[key] = {
                    'time': current_time,
                    'rx': rx_kb,
                    'tx': tx_kb
                }
                
                return network_data
                
        except Exception as e:
            logger.debug(f"QTagUID method failed for {package_name}: {e}")
        
        # xt_qtaguid is not available on newer Android versions or requires root
        logger.debug(f"xt_qtaguid stats not available for {package_name} (normal on Android 7+ or non-root devices)")
        return {}

    def _parse_network_stats(self, result: str) -> Dict[str, float]:
        """Parse network stats from /proc/net/dev"""
        network_data = {}
        try:
            lines = result.split('\n')[2:]  # Skip headers
            total_rx = total_tx = 0
            
            for line in lines:
                if ':' in line:
                    parts = line.split(':')[1].split()
                    rx_bytes = int(parts[0])
                    tx_bytes = int(parts[8])
                    total_rx += rx_bytes
                    total_tx += tx_bytes
            
            # Convert to KB
            current_time = time.time()
            rx_kb = total_rx / 1024
            tx_kb = total_tx / 1024
            
            network_data = {
                'network_rx_total': round(rx_kb, 2),
                'network_tx_total': round(tx_kb, 2)
            }
            
            # Calculate speed if we have previous data
            if hasattr(self, '_last_system_network'):
                time_diff = current_time - self._last_system_network['time']
                if time_diff > 0:
                    rx_speed = (rx_kb - self._last_system_network['rx']) / time_diff
                    tx_speed = (tx_kb - self._last_system_network['tx']) / time_diff
                    network_data['network_rx'] = round(max(0, rx_speed), 2)
                    network_data['network_tx'] = round(max(0, tx_speed), 2)
            
            self._last_system_network = {
                'time': current_time,
                'rx': rx_kb,
                'tx': tx_kb
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse network stats: {e}")
        return network_data
