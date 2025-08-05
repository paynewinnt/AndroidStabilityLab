"""Caching helpers for the ADB collector."""

import time
from collections import defaultdict

class EnhancedCache:
    """多级缓存系统"""
    def __init__(self):
        self.l1_cache = {}  # 热数据缓存 (TTL: 30s)
        self.l2_cache = {}  # 温数据缓存 (TTL: 60s)  
        self.cache_stats = defaultdict(int)
        self.max_l1_size = 100
        self.max_l2_size = 500
        
    def get(self, key: str, fetch_func=None, ttl: int = 30):
        current_time = time.time()
        
        # L1缓存检查
        if key in self.l1_cache:
            if current_time - self.l1_cache[key]['time'] < ttl:
                self.cache_stats['l1_hit'] += 1
                return self.l1_cache[key]['data']
            else:
                del self.l1_cache[key]
                
        # L2缓存检查
        if key in self.l2_cache:
            if current_time - self.l2_cache[key]['time'] < ttl * 2:
                # 提升到L1
                self.l1_cache[key] = self.l2_cache[key]
                del self.l2_cache[key]
                self.cache_stats['l2_hit'] += 1
                return self.l1_cache[key]['data']
            else:
                del self.l2_cache[key]
        
        # 缓存未命中
        if fetch_func:
            data = fetch_func()
            self.put(key, data, current_time)
            self.cache_stats['miss'] += 1
            return data
            
        self.cache_stats['miss'] += 1
        return None
        
    def put(self, key: str, data, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
            
        # L1缓存管理
        if len(self.l1_cache) >= self.max_l1_size:
            # 移除最老的条目到L2
            oldest_key = min(self.l1_cache.keys(), 
                           key=lambda k: self.l1_cache[k]['time'])
            self.l2_cache[oldest_key] = self.l1_cache[oldest_key]
            del self.l1_cache[oldest_key]
            
        self.l1_cache[key] = {'data': data, 'time': timestamp}
        
        # L2缓存大小管理
        if len(self.l2_cache) >= self.max_l2_size:
            oldest_key = min(self.l2_cache.keys(),
                           key=lambda k: self.l2_cache[k]['time'])
            del self.l2_cache[oldest_key]
    
    def get_stats(self):
        total_requests = sum(self.cache_stats.values())
        if total_requests == 0:
            return {"hit_rate": 0, "l1_hit_rate": 0, "l2_hit_rate": 0}
            
        hit_rate = (self.cache_stats['l1_hit'] + self.cache_stats['l2_hit']) / total_requests
        return {
            "hit_rate": hit_rate,
            "l1_hit_rate": self.cache_stats['l1_hit'] / total_requests,
            "l2_hit_rate": self.cache_stats['l2_hit'] / total_requests,
            "total_requests": total_requests
        }
