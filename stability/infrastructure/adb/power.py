"""Power collection and parsing helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class PowerMetricsMixin:
    def _get_app_power_stats(self, package_name: str) -> Dict[str, float]:
        power_info = {}
        
        # Method 1: Try batterystats detailed analysis
        power_data = self._get_power_via_batterystats(package_name)
        power_info.update(power_data)
        
        # Method 2: Try procstats for additional metrics
        proc_data = self._get_power_via_procstats(package_name)
        power_info.update(proc_data)
        
        # Method 3: Estimate power from CPU and other metrics
        estimated_power = self._estimate_power_consumption(package_name)
        if estimated_power is not None and 'power_consumption' not in power_info:
            power_info['power_consumption'] = estimated_power
            
        return power_info

    def _get_power_via_batterystats(self, package_name: str) -> Dict[str, float]:
        try:
            result = self._run_adb_command(f"shell dumpsys batterystats {package_name}")
            if result:
                power_info = {}
                
                # Parse various power-related metrics
                # Estimated power consumption
                power_patterns = [
                    r'Estimated power use.*?(\d+(?:\.\d+)?)mAh',
                    r'Power use \(mAh\):\s*(\d+(?:\.\d+)?)',
                    r'Total.*?(\d+(?:\.\d+)?)mAh'
                ]
                
                for pattern in power_patterns:
                    power_match = re.search(pattern, result, re.IGNORECASE)
                    if power_match:
                        power_info['power_consumption'] = float(power_match.group(1))
                        break
                
                # Wake locks
                wakelock_patterns = [
                    r'Wake lock.*?count=(\d+)',
                    r'Wakelock.*?(\d+)\s+times',
                    r'partial.*?count:\s*(\d+)'
                ]
                
                total_wakelocks = 0
                for pattern in wakelock_patterns:
                    matches = re.findall(pattern, result, re.IGNORECASE)
                    if matches:
                        total_wakelocks += sum(int(count) for count in matches)
                
                if total_wakelocks > 0:
                    power_info['wakelock_count'] = total_wakelocks
                
                # Alarms
                alarm_patterns = [
                    r'Alarm.*?count=(\d+)',
                    r'alarms:\s*(\d+)',
                    r'wakeups:\s*(\d+)'
                ]
                
                total_alarms = 0
                for pattern in alarm_patterns:
                    matches = re.findall(pattern, result, re.IGNORECASE)
                    if matches:
                        total_alarms += sum(int(count) for count in matches)
                
                if total_alarms > 0:
                    power_info['alarm_count'] = total_alarms
                
                # CPU time (can be used for power estimation)
                cpu_time_match = re.search(r'CPU:\s*(\d+)ms', result)
                if cpu_time_match:
                    cpu_time_ms = int(cpu_time_match.group(1))
                    power_info['cpu_time_ms'] = cpu_time_ms
                
                # Network activity
                network_patterns = [
                    r'Network:\s*(\d+(?:\.\d+)?)\s*KB received.*?(\d+(?:\.\d+)?)\s*KB sent',
                    r'Wifi.*?(\d+)\s*KB.*?(\d+)\s*KB',
                    r'Mobile.*?(\d+)\s*KB.*?(\d+)\s*KB'
                ]
                
                for pattern in network_patterns:
                    net_match = re.search(pattern, result, re.IGNORECASE)
                    if net_match:
                        rx_kb = float(net_match.group(1))
                        tx_kb = float(net_match.group(2))
                        power_info['network_rx_kb'] = rx_kb
                        power_info['network_tx_kb'] = tx_kb
                        break
                
                return power_info
                
        except Exception as e:
            logger.debug(f"Batterystats power method failed for {package_name}: {e}")
        return {}

    def _get_power_via_procstats(self, package_name: str) -> Dict[str, float]:
        try:
            # Get additional process statistics
            result = self._run_adb_command(f"shell dumpsys procstats {package_name}")
            if result:
                power_info = {}
                
                # Parse process runtime statistics
                runtime_match = re.search(r'TOTAL:\s*(\d+)ms', result)
                if runtime_match:
                    total_runtime = int(runtime_match.group(1))
                    power_info['total_runtime_ms'] = total_runtime
                
                # Memory usage over time (affects power)
                mem_matches = re.findall(r'(\d+)K/(\d+)K/(\d+)K', result)
                if mem_matches:
                    avg_memory = sum(int(match[1]) for match in mem_matches) / len(mem_matches)
                    power_info['avg_memory_kb'] = round(avg_memory, 2)
                
                return power_info
                
        except Exception as e:
            logger.debug(f"Procstats power method failed for {package_name}: {e}")
        return {}

    def _estimate_power_consumption(self, package_name: str) -> Optional[float]:
        """Enhanced power consumption estimation based on multiple metrics"""
        try:
            logger.debug(f"Estimating power consumption for {package_name}")
            
            # Get current performance metrics
            cpu_usage = self._get_app_cpu_usage(package_name)
            memory_info = self._get_app_memory(package_name)
            
            # Initialize power components
            total_power = 0.0
            components_found = 0
            
            # Base power for active app (varies by type)
            base_power = 5.0  # Reduced base power
            total_power += base_power
            components_found += 1
            
            # CPU-based power estimation
            if cpu_usage is not None and cpu_usage > 0:
                # More realistic CPU power model: exponential relationship
                cpu_power = min(cpu_usage * 0.8, 50)  # Cap at 50mAh for very high CPU
                total_power += cpu_power
                components_found += 1
                logger.debug(f"CPU power component: {cpu_power:.2f} mAh (CPU: {cpu_usage}%)")
            
            # Memory-based power estimation
            if memory_info and 'memory_pss' in memory_info:
                memory_mb = memory_info['memory_pss'] / 1024  # Convert to MB
                # Memory power scales with size but has diminishing returns
                memory_power = min(memory_mb * 0.02, 20)  # Cap at 20mAh
                total_power += memory_power
                components_found += 1
                logger.debug(f"Memory power component: {memory_power:.2f} mAh (Memory: {memory_mb:.1f} MB)")
            
            # Check app state for power multiplier
            foreground_multiplier = 1.0
            try:
                if self._is_app_in_foreground(package_name):
                    foreground_multiplier = 1.8  # Higher multiplier for active apps
                    logger.debug(f"App is in foreground, applying multiplier: {foreground_multiplier}")
                else:
                    foreground_multiplier = 0.4  # Background apps use less power
                    logger.debug(f"App is in background, applying multiplier: {foreground_multiplier}")
            except:
                foreground_multiplier = 1.0  # Default if detection fails
            
            # Apply activity-based adjustments
            try:
                # Check for network activity (higher power consumption)
                network_result = self._run_adb_command(f"shell dumpsys netstats detail uid | grep -i {package_name}")
                if network_result and any(keyword in network_result.lower() for keyword in ['rx', 'tx', 'bytes']):
                    network_bonus = 8.0
                    total_power += network_bonus
                    logger.debug(f"Network activity detected, adding {network_bonus} mAh")
                    components_found += 1
            except:
                pass
            
            # Apply foreground multiplier
            estimated_power = total_power * foreground_multiplier
            
            # Ensure reasonable bounds
            estimated_power = max(0.1, min(estimated_power, 150))  # Between 0.1 and 150 mAh
            
            if components_found > 1:  # Only return estimate if we have meaningful data
                logger.debug(f"Estimated power for {package_name}: {estimated_power:.2f} mAh (components: {components_found})")
                return round(estimated_power, 2)
            else:
                logger.debug(f"Insufficient data for power estimation of {package_name}")
                return None
            
        except Exception as e:
            logger.debug(f"Power estimation failed for {package_name}: {e}")
        return None

    def _parse_app_power_info(self, result: str) -> Dict[str, float]:
        """Parse app power info from batterystats output"""
        power_info = {}
        if not result or result.strip() == "":
            logger.debug("Empty power info result")
            return power_info
            
        try:
            # Log first 300 characters of batterystats output for debugging
            logger.debug(f"Batterystats output sample: {result[:300]}...")
            
            # Use compiled patterns for better performance
            for i, pattern in enumerate(self._compiled_patterns['power_consumption']):
                power_match = pattern.search(result)
                if power_match:
                    power_value = float(power_match.group(1))
                    # Validate power consumption (should be reasonable)
                    if 0 <= power_value <= 10000:  # 0 to 10000 mAh seems reasonable
                        power_info['power_consumption'] = round(power_value, 2)
                        logger.debug(f"Found power consumption: {power_value} using pattern {i}")
                        break
                    else:
                        logger.debug(f"Power value {power_value} out of range, trying next pattern")
            
            # If no power consumption found, try parsing battery usage statistics
            if 'power_consumption' not in power_info:
                logger.debug("No direct power consumption found, trying alternative parsing")
                power_info.update(self._parse_alternative_power_data(result))
            
            # Parse wakelock count with multiple patterns
            wakelock_patterns = [
                r'Wake lock.*?count=(\d+)',
                r'Wakelock.*?(\d+)\s+times',
                r'partial.*?count:\s*(\d+)',
                r'Wakelocks:\s*(\d+)',
                r'Wake locks:\s*(\d+)'
            ]
            
            for pattern in wakelock_patterns:
                wakelock_match = re.search(pattern, result, re.IGNORECASE)
                if wakelock_match:
                    wakelock_count = int(wakelock_match.group(1))
                    if 0 <= wakelock_count <= 10000:  # Reasonable range
                        power_info['wakelock_count'] = wakelock_count
                        break
            
            # If no direct power data found, try to estimate
            if 'power_consumption' not in power_info:
                estimated_power = self._estimate_power_consumption_from_stats(result)
                if estimated_power is not None:
                    power_info['power_consumption'] = estimated_power
                    logger.debug(f"Estimated power consumption: {estimated_power} mAh")
                    
        except Exception as e:
            logger.debug(f"Failed to parse app power info: {e}")
            logger.debug(f"Power result sample: {result[:200] if result else 'None'}")
        return power_info

    def _parse_app_power_info_enhanced(self, result: str, package_name: str) -> Dict[str, float]:
        """Enhanced app power info parsing with multiple fallback methods"""
        power_info = {}
        
        # First try the standard parsing
        power_info = self._parse_app_power_info(result)
        
        # If no power consumption found, try additional methods
        if 'power_consumption' not in power_info or power_info['power_consumption'] == 0:
            logger.debug(f"Standard parsing failed for {package_name}, trying enhanced methods")
            
            # Method 1: Try different batterystats command variations
            enhanced_power = self._try_alternative_batterystats_commands(package_name)
            if enhanced_power:
                power_info.update(enhanced_power)
                return power_info
            
            # Method 2: Try parsing general batterystats (without package name)
            general_batterystats = self._get_general_batterystats_for_package(package_name)
            if general_batterystats:
                power_info.update(general_batterystats)
                return power_info
                
            # Method 3: Estimate based on current app performance metrics
            estimated_power = self._estimate_power_consumption(package_name)
            if estimated_power is not None:
                power_info['power_consumption'] = estimated_power
                logger.debug(f"Using estimated power for {package_name}: {estimated_power} mAh")
        
        return power_info

    def _try_alternative_batterystats_commands(self, package_name: str) -> Dict[str, float]:
        """Try alternative batterystats commands for better power data"""
        alternative_commands = [
            f"shell dumpsys batterystats --charged {package_name}",
            f"shell dumpsys batterystats --reset {package_name}",
            f"shell dumpsys battery",  # General battery info
            f"shell cat /proc/power/wakeup_sources",  # Wakelock info
        ]
        
        for cmd in alternative_commands:
            try:
                result = self._run_adb_command(cmd)
                if result:
                    # Parse result for power information
                    power_info = self._parse_app_power_info(result)
                    if power_info and 'power_consumption' in power_info:
                        logger.debug(f"Found power data using alternative command: {cmd}")
                        return power_info
            except Exception as e:
                logger.debug(f"Alternative command failed {cmd}: {e}")
                continue
        
        return {}

    def _get_general_batterystats_for_package(self, package_name: str) -> Dict[str, float]:
        """Get power data from general batterystats and extract package-specific info"""
        try:
            # Get general batterystats
            result = self._run_adb_command("shell dumpsys batterystats")
            if result and package_name in result:
                # Extract package-specific section
                lines = result.split('\n')
                package_section = []
                in_package_section = False
                
                for line in lines:
                    if package_name in line:
                        in_package_section = True
                        package_section.append(line)
                    elif in_package_section:
                        if line.strip() and not line.startswith(' '):
                            # End of package section
                            break
                        package_section.append(line)
                
                if package_section:
                    section_text = '\n'.join(package_section)
                    power_info = self._parse_app_power_info(section_text)
                    if power_info:
                        logger.debug(f"Found power data in general batterystats for {package_name}")
                        return power_info
                        
        except Exception as e:
            logger.debug(f"General batterystats parsing failed: {e}")
        
        return {}

    def reset_battery_stats(self) -> bool:
        """Reset battery statistics to get fresh power consumption data"""
        try:
            logger.info("Resetting battery statistics for fresh power data collection")
            result = self._run_adb_command("shell dumpsys batterystats --reset")
            if result is not None:
                # Also try alternative reset methods
                self._run_adb_command("shell dumpsys battery reset")
                logger.info("Battery statistics reset successfully")
                return True
        except Exception as e:
            logger.debug(f"Failed to reset battery stats: {e}")
        return False

    def _parse_alternative_power_data(self, result: str) -> Dict[str, float]:
        """Parse alternative power data when standard patterns fail"""
        power_info = {}
        try:
            # Try to find any numeric value followed by power-related keywords
            alternative_patterns = [
                # Look for patterns with various separators and formats
                r'(\d+(?:\.\d+)?)\s*(?:mah|mAh|MAH)',
                r'battery.*?(\d+(?:\.\d+)?)',
                r'power.*?(\d+(?:\.\d+)?)',
                r'consumption.*?(\d+(?:\.\d+)?)',
                r'usage.*?(\d+(?:\.\d+)?)',
                # Look for percentage values that might indicate relative power usage
                r'(\d+(?:\.\d+)?)%.*?(?:battery|power|consumption)',
                # Look for time-based power indicators
                r'(\d+(?:\.\d+)?)\s*(?:ms|seconds?).*?cpu',
                r'wake.*?(\d+(?:\.\d+)?)',
            ]
            
            for pattern in alternative_patterns:
                matches = re.findall(pattern, result, re.IGNORECASE)
                if matches:
                    # Take the first reasonable value
                    for match_str in matches:
                        try:
                            value = float(match_str)
                            if 0.1 <= value <= 1000:  # Reasonable range for power consumption
                                power_info['power_consumption'] = round(value, 2)
                                logger.debug(f"Found alternative power value: {value} using pattern: {pattern}")
                                return power_info
                        except ValueError:
                            continue
            
            # If still no power data, try to extract from CPU/system activity
            power_info.update(self._estimate_power_from_activity(result))
            
        except Exception as e:
            logger.debug(f"Alternative power parsing failed: {e}")
        
        return power_info

    def _estimate_power_from_activity(self, result: str) -> Dict[str, float]:
        """Estimate power consumption from system activity indicators"""
        power_info = {}
        try:
            # Look for activity indicators that suggest power consumption
            activity_score = 0
            
            # CPU activity
            cpu_patterns = [r'cpu.*?(\d+(?:\.\d+)?)', r'processor.*?(\d+(?:\.\d+)?)']
            for pattern in cpu_patterns:
                matches = re.findall(pattern, result, re.IGNORECASE)
                if matches:
                    activity_score += sum(float(m) for m in matches[:3]) * 0.1  # Weight CPU activity
            
            # Network activity
            network_patterns = [r'network.*?(\d+(?:\.\d+)?)', r'wifi.*?(\d+(?:\.\d+)?)']
            for pattern in network_patterns:
                matches = re.findall(pattern, result, re.IGNORECASE)
                if matches:
                    activity_score += sum(float(m) for m in matches[:3]) * 0.05  # Weight network activity
            
            # Wake locks and alarms (high power consumers)
            wakelock_patterns = [r'wake.*?(\d+)', r'alarm.*?(\d+)']
            for pattern in wakelock_patterns:
                matches = re.findall(pattern, result, re.IGNORECASE)
                if matches:
                    activity_score += sum(float(m) for m in matches[:5]) * 0.2  # High weight for wakelocks
            
            if activity_score > 0:
                # Convert activity score to estimated power consumption (very rough approximation)
                estimated_power = min(activity_score * 0.1, 100)  # Cap at 100mAh
                power_info['power_consumption'] = round(estimated_power, 2)
                logger.debug(f"Estimated power from activity: {estimated_power} mAh (score: {activity_score})")
            
        except Exception as e:
            logger.debug(f"Activity-based power estimation failed: {e}")
        
        return power_info

    def _estimate_power_consumption_from_stats(self, result: str) -> Optional[float]:
        """Estimate power consumption from available battery stats"""
        try:
            # Look for CPU time, network activity, etc.
            cpu_time_patterns = [
                r'Cpu time:\s*(\d+(?:\.\d+)?)ms',
                r'CPU:\s*(\d+(?:\.\d+)?)ms',
                r'Process time:\s*(\d+(?:\.\d+)?)ms'
            ]
            
            cpu_time = 0
            for pattern in cpu_time_patterns:
                cpu_match = re.search(pattern, result, re.IGNORECASE)
                if cpu_match:
                    cpu_time = float(cpu_match.group(1))
                    break
            
            if cpu_time > 0:
                # Very rough estimation: 1ms CPU time ≈ 0.001 mAh
                estimated = round(cpu_time * 0.001, 2)
                return max(0.1, min(estimated, 100))  # Clamp between 0.1 and 100 mAh
                
        except Exception as e:
            logger.debug(f"Power estimation failed: {e}")
        return None
