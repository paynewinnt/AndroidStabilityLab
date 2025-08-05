"""Device connection, metadata, and installed-app helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class DeviceInfoMixin:
    def check_adb_connection(self) -> bool:
        try:
            result = self._run_adb_command("devices")
            if result and "device" in result:
                devices = self._parse_devices(result)
                if devices:
                    self.device_id = devices[0]
                    logger.info(f"ADB connected to device: {self.device_id}")
                    return True
            logger.warning("No ADB devices found")
            return False
        except Exception as e:
            logger.error(f"ADB connection check failed: {e}")
            return False

    def get_installed_apps(self) -> List[Dict[str, str]]:
        try:
            # Get all packages and third-party packages in parallel for speed
            commands = [
                "shell pm list packages",
                "shell pm list packages -3"
            ]
            results = self._run_adb_commands_parallel(commands, log_errors=False)
            
            all_packages_result = None
            third_party_result = None
            
            for cmd_key, result in results.items():
                if "cmd_1" in cmd_key:  # Second command is "shell pm list packages -3"
                    third_party_result = result
                elif "cmd_0" in cmd_key:  # First command is "shell pm list packages"
                    all_packages_result = result
            
            if not all_packages_result:
                return []
                
            # Create set of third-party packages for fast lookup
            third_party_packages = set()
            if third_party_result:
                for line in third_party_result.strip().split('\n'):
                    if line.startswith('package:'):
                        package_name = line.replace('package:', '').strip()
                        third_party_packages.add(package_name)
                
            apps = []
            package_lines = all_packages_result.strip().split('\n')
            
            # 系统应用黑名单（过滤掉一些不需要监控的系统应用）
            system_blacklist = {
                'com.android.providers', 'com.android.server', 'com.android.systemui',
                'com.android.shell', 'com.android.bluetooth', 'com.android.nfc',
                'com.android.carrierconfig', 'com.android.cts', 'com.android.inputmethod',
                'com.android.keychain', 'com.android.location', 'com.android.externalstorage',
                'com.android.documentsui', 'com.android.onetimeinitializer', 'com.android.proxyhandler',
                'com.android.defcontainer', 'com.android.backupconfirm', 'com.android.sharedstoragebackup'
            }
            
            for line in package_lines:
                if line.startswith('package:'):
                    package_name = line.replace('package:', '').strip()
                    if package_name:
                        # 过滤掉黑名单中的系统应用
                        should_skip = False
                        for blacklist_pattern in system_blacklist:
                            if package_name.startswith(blacklist_pattern):
                                should_skip = True
                                break
                        
                        if should_skip:
                            continue
                            
                        # Use package name as display name for speed (avoid expensive pm dump calls)
                        # Try to make it more readable
                        display_name = self._make_readable_app_name(package_name)
                        
                        # 只添加有意义的应用（排除一些明显的系统内部组件）
                        if not package_name.endswith('.test') and not package_name.startswith('android.'):
                            apps.append({
                                'package_name': package_name,
                                'app_name': display_name,
                                'is_system': package_name not in third_party_packages
                            })
                        
            # 按应用名排序
            apps.sort(key=lambda x: x['app_name'].lower())
            logger.info(f"Found {len(apps)} installed apps")
            return apps
            
        except Exception as e:
            logger.error(f"Failed to get installed apps: {e}")
            return []

    def _make_readable_app_name(self, package_name: str) -> str:
        """Convert package name to more readable format without expensive ADB calls"""
        # Remove common prefixes
        if package_name.startswith('com.'):
            parts = package_name.split('.')
            if len(parts) > 2:
                # Use the last part as app name, with some cleanup
                app_name = parts[-1]
                # Handle cases like com.company.appname
                if len(parts) > 3:
                    app_name = parts[-1]
                else:
                    app_name = parts[1]  # company name
                
                # Capitalize and clean up
                app_name = app_name.replace('_', ' ').title()
                return app_name
        
        # For other packages, just use the package name
        return package_name

    def _is_third_party_app(self, package_name: str) -> bool:
        """判断是否是第三方应用"""
        try:
            result = self._run_adb_command(f"shell pm list packages -3 {package_name}")
            return result and package_name in result
        except:
            return False

    def get_device_info(self) -> Dict[str, str]:
        """获取设备信息"""
        device_info = {}
        
        try:
            # 获取设备属性
            props = [
                ('ro.product.model', 'model'),
                ('ro.product.brand', 'brand'), 
                ('ro.product.manufacturer', 'manufacturer'),
                ('ro.build.version.release', 'android_version'),
                ('ro.build.version.sdk', 'api_level'),
                ('ro.product.cpu.abi', 'cpu_abi'),
                ('ro.build.id', 'build_id')
            ]
            
            for prop, key in props:
                result = self._run_adb_command(f"shell getprop {prop}")
                if result:
                    device_info[key] = result.strip()
                    
            # 获取屏幕信息
            screen_info = self._run_adb_command("shell wm size")
            if screen_info and "Physical size:" in screen_info:
                screen_size = screen_info.split("Physical size:")[-1].strip()
                device_info['screen_size'] = screen_size
                
            # 获取密度信息  
            density_info = self._run_adb_command("shell wm density")
            if density_info and "Physical density:" in density_info:
                density = density_info.split("Physical density:")[-1].strip()
                device_info['screen_density'] = density
                
            logger.info(f"Device info collected: {device_info.get('model', 'Unknown')}")
            return device_info
            
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {'error': str(e)}

    def _parse_devices(self, devices_output: str) -> List[str]:
        devices = []
        lines = devices_output.strip().split('\n')[1:]  # Skip header
        for line in lines:
            if '\tdevice' in line:
                device_id = line.split('\t')[0]
                devices.append(device_id)
        return devices

    def _get_app_name(self, package_name: str) -> Optional[str]:
        try:
            result = self._run_adb_command(f"shell pm dump {package_name}")
            if result:
                # Look for application label
                match = re.search(r'applicationLabel=(.+)', result)
                if match:
                    return match.group(1).strip()
        except Exception:
            pass
        return None
