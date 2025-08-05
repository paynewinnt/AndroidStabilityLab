"""Regex pattern initialization for the ADB collector."""

import logging
import re

logger = logging.getLogger(__name__)

class RegexPatternMixin:
    def _init_regex_patterns(self):
        """Initialize compiled regex patterns for better performance"""
        self._compiled_patterns = {
            'memory_pss': [
                re.compile(r'TOTAL\s+(\d+)', re.IGNORECASE),
                re.compile(r'TOTAL PSS:\s+(\d+)', re.IGNORECASE),
                re.compile(r'Total\s+PSS:\s+(\d+)', re.IGNORECASE),
                re.compile(r'PSS\s+Total:\s+(\d+)', re.IGNORECASE)
            ],
            'power_consumption': [
                # Original patterns
                re.compile(r'Estimated power use.*?(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                re.compile(r'Power use \(mAh\):\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
                re.compile(r'Total.*?(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                re.compile(r'Consumption:\s*(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                # Additional patterns for different Android versions
                re.compile(r'Power:\s*(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                re.compile(r'Battery drain:\s*(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                re.compile(r'mAh:\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
                re.compile(r'(\d+(?:\.\d+)?)\s*mAh', re.IGNORECASE),
                # Pattern for newer Android versions
                re.compile(r'Estimated power.*?(\d+(?:\.\d+)?)mAh', re.IGNORECASE),
                re.compile(r'App battery usage.*?(\d+(?:\.\d+)?)', re.IGNORECASE),
                # Pattern without "mAh" unit for percentage-based power
                re.compile(r'Power usage:\s*(\d+(?:\.\d+)?)%', re.IGNORECASE),
                re.compile(r'Battery:\s*(\d+(?:\.\d+)?)%', re.IGNORECASE)
            ],
            'fps_alternative': [
                re.compile(r'RefreshRate[:\s]+(\d+(?:\.\d+)?)', re.IGNORECASE),
                re.compile(r'FPS[:\s]+(\d+(?:\.\d+)?)', re.IGNORECASE),
                re.compile(r'Frame rate[:\s]+(\d+(?:\.\d+)?)', re.IGNORECASE)
            ],
            'uid_lookup': re.compile(r'userId=(\d+)', re.IGNORECASE)
        }
