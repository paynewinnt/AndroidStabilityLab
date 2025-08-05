"""FPS collection and parsing helpers."""

import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class FPSMetricsMixin:
    def _get_app_fps(self, package_name: str) -> Optional[float]:
        # Try multiple methods for FPS detection
        
        # Method 1: Try gfxinfo (most accurate for app FPS)
        fps = self._get_fps_via_gfxinfo(package_name)
        if fps is not None:
            return fps
            
        # Method 2: Try SurfaceFlinger latency
        fps = self._get_fps_via_surfaceflinger(package_name)
        if fps is not None:
            return fps
            
        # Method 3: Try dumpsys window
        fps = self._get_fps_via_window_dump(package_name)
        if fps is not None:
            return fps
            
        logger.debug(f"All FPS detection methods failed for {package_name}")
        return None

    def _get_fps_via_gfxinfo(self, package_name: str) -> Optional[float]:
        try:
            # Use gfxinfo to get frame statistics
            result = self._run_adb_command(f"shell dumpsys gfxinfo {package_name} framestats")
            if result:
                lines = result.split('\n')
                frame_times = []
                
                for line in lines:
                    if line.strip() and not line.startswith('---'):
                        parts = line.split(',')
                        if len(parts) >= 2:
                            try:
                                # Parse frame time (usually in column 1 or 2)
                                frame_start = int(parts[1])
                                frame_end = int(parts[2]) if len(parts) > 2 else frame_start
                                frame_duration = frame_end - frame_start
                                
                                if frame_duration > 0:
                                    frame_times.append(frame_duration)
                            except (ValueError, IndexError):
                                continue
                
                if len(frame_times) > 10:  # Need enough samples
                    # Calculate average frame time
                    avg_frame_time = sum(frame_times) / len(frame_times)
                    # Convert nanoseconds to FPS
                    fps = 1000000000 / avg_frame_time
                    return round(min(fps, 120), 2)  # Cap at 120 FPS
                    
        except Exception as e:
            logger.debug(f"GFXInfo FPS method failed for {package_name}: {e}")
        return None

    def _get_fps_via_surfaceflinger(self, package_name: str) -> Optional[float]:
        try:
            # Check if app is in foreground first
            window_result = self._run_adb_command("shell dumpsys window windows")
            if not (window_result and package_name in window_result):
                return None
                
            # Get current focused window surface
            surface_match = re.search(rf'{re.escape(package_name)}.*?Surface\(name=([^)]+)\)', window_result)
            if not surface_match:
                return None
                
            surface_name = surface_match.group(1)
            
            # Get FPS using surfaceflinger latency for this surface
            fps_result = self._run_adb_command(f"shell dumpsys SurfaceFlinger --latency '{surface_name}'")
            if fps_result:
                lines = fps_result.split('\n')[1:]  # Skip header
                valid_frames = []
                
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                frame_ready = int(parts[1])
                                frame_displayed = int(parts[2])
                                if frame_ready > 0 and frame_displayed > 0:
                                    valid_frames.append((frame_ready, frame_displayed))
                            except ValueError:
                                continue
                
                if len(valid_frames) > 5:
                    # Calculate frame intervals
                    intervals = []
                    for i in range(1, len(valid_frames)):
                        interval = valid_frames[i][0] - valid_frames[i-1][0]
                        if interval > 0:
                            intervals.append(interval)
                    
                    if intervals:
                        avg_interval = sum(intervals) / len(intervals)
                        fps = 1000000000 / avg_interval  # Convert from nanoseconds
                        return round(min(fps, 120), 2)
                        
        except Exception as e:
            logger.debug(f"SurfaceFlinger FPS method failed for {package_name}: {e}")
        return None

    def _get_fps_via_window_dump(self, package_name: str) -> Optional[float]:
        try:
            # Use window manager to check app activity
            result = self._run_adb_command("shell dumpsys window windows")
            if result and package_name in result:
                # Look for refresh rate information
                refresh_match = re.search(r'refreshRate=([0-9.]+)', result)
                if refresh_match:
                    refresh_rate = float(refresh_match.group(1))
                    
                    # Check if app is actively drawing
                    if 'mHasSurface=true' in result and 'mIsWallpaper=false' in result:
                        # Assume app is running at system refresh rate if actively drawing
                        return round(min(refresh_rate, 120), 2)
                        
        except Exception as e:
            logger.debug(f"Window dump FPS method failed for {package_name}: {e}")
        return None

    def _is_app_in_foreground(self, package_name: str) -> bool:
        """Check if the app is currently in the foreground"""
        try:
            # Method 1: Check current activity
            result = self._run_adb_command("shell dumpsys activity activities")
            if result and f'* Hist #{0}:' in result and package_name in result:
                return True
                
            # Method 2: Check window focus
            window_result = self._run_adb_command("shell dumpsys window windows")
            if window_result:
                focus_match = re.search(r'mCurrentFocus=.*?{.*?' + re.escape(package_name), window_result)
                if focus_match:
                    return True
                    
        except Exception as e:
            logger.debug(f"Failed to check foreground status for {package_name}: {e}")
        return False

    def _parse_app_fps(self, result: str) -> Optional[float]:
        """Parse app FPS from gfxinfo framestats output"""
        metrics = self._parse_gfxinfo_metrics(result)
        if metrics.get("fps") is not None:
            return metrics["fps"]
        return None

    def _parse_gfxinfo_metrics(self, result: str) -> Dict[str, float]:
        """Parse FPS/Jank/GPU frame metrics from modern gfxinfo output."""
        metrics: Dict[str, float] = {}
        try:
            total_match = re.search(r"Total frames rendered:\s*(\d+)", result)
            jank_match = re.search(r"Janky frames:\s*(\d+)\s*\(([0-9.]+)%\)", result)
            if total_match:
                metrics["frame_count"] = float(total_match.group(1))
            if jank_match:
                metrics["jank_frames"] = float(jank_match.group(1))
                metrics["jank_percent"] = float(jank_match.group(2))
            for percentile in ("50", "90", "95", "99"):
                gpu_match = re.search(rf"{percentile}th gpu percentile:\s*([0-9.]+)ms", result, re.IGNORECASE)
                if gpu_match:
                    metrics[f"gpu_p{percentile}_ms"] = float(gpu_match.group(1))

            lines = result.splitlines()
            header: list[str] = []
            frame_completed_values: list[int] = []
            for line in lines:
                if line.startswith("Flags,"):
                    header = [part.strip() for part in line.split(",")]
                    continue
                if not header or not line or line.startswith("---") or "," not in line:
                    continue
                parts = [part.strip() for part in line.split(",")]
                if len(parts) < len(header):
                    continue
                try:
                    completed_index = header.index("FrameCompleted")
                    completed_at = int(parts[completed_index])
                except (ValueError, IndexError):
                    continue
                if completed_at > 0:
                    frame_completed_values.append(completed_at)
            if len(frame_completed_values) > 1:
                elapsed_ns = max(frame_completed_values) - min(frame_completed_values)
                if elapsed_ns > 0:
                    fps = (len(frame_completed_values) - 1) / (elapsed_ns / 1_000_000_000)
                    if 1 <= fps <= 240:
                        metrics["fps"] = round(min(fps, 120), 1)
        except Exception as e:
            logger.debug(f"Failed to parse gfxinfo metrics: {e}")
        if "fps" not in metrics:
            fallback_fps = self._parse_fps_from_legacy_columns(result)
            if fallback_fps is not None:
                metrics["fps"] = fallback_fps
        return metrics

    def _parse_fps_from_legacy_columns(self, result: str) -> Optional[float]:
        """Best-effort fallback for old framestats formats."""
        try:
            lines = result.split('\n')
            frame_times = []
            
            for line in lines:
                if line.strip() and not line.startswith('---'):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        try:
                            # Parse frame time (usually in column 1 or 2)
                            frame_start = int(parts[1])
                            frame_end = int(parts[2]) if len(parts) > 2 else frame_start
                            frame_duration = frame_end - frame_start
                            
                            if frame_duration > 0:
                                frame_times.append(frame_duration)
                        except (ValueError, IndexError):
                            continue
            
            if frame_times and len(frame_times) > 5:
                # Calculate average frame time and convert to FPS
                avg_frame_time_ns = sum(frame_times) / len(frame_times)
                avg_frame_time_ms = avg_frame_time_ns / 1_000_000  # Convert to milliseconds
                
                if avg_frame_time_ms > 0:
                    fps = 1000 / avg_frame_time_ms  # Convert to FPS
                    fps = round(min(fps, 120), 1)  # Cap at 120 FPS
                    
                    # Validate FPS (should be reasonable)
                    if 1 <= fps <= 120:
                        logger.debug(f"Calculated FPS: {fps} from {len(frame_times)} samples")
                        return fps
                    else:
                        logger.debug(f"Invalid FPS calculated: {fps}")
            
            # If framestats parsing fails, try alternative method
            logger.debug("Framestats parsing failed, trying alternative FPS detection")
            return self._parse_fps_alternative(result)
                    
        except Exception as e:
            logger.debug(f"Failed to parse app FPS: {e}")
            logger.debug(f"FPS result sample: {result[:200] if result else 'None'}")
        return None

    def _parse_fps_alternative(self, result: str) -> Optional[float]:
        """Alternative FPS parsing method"""
        try:
            # Use compiled patterns for better performance
            for pattern in self._compiled_patterns['fps_alternative']:
                fps_match = pattern.search(result)
                if fps_match:
                    fps = float(fps_match.group(1))
                    if 1 <= fps <= 120:
                        logger.debug(f"Found FPS via alternative method: {fps}")
                        return round(fps, 1)
            
        except Exception as e:
            logger.debug(f"Alternative FPS parsing failed: {e}")
        return None
