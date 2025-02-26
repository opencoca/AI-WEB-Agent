"""Proxy rotation and management for the research agent"""
import random
import time
from typing import Optional, Dict, List
import requests
from requests.exceptions import RequestException

class ProxyHandler:
    def __init__(self):
        # Free proxy list for demonstration
        self.proxies = [
            "http://165.225.38.32:10605",
            "http://165.225.38.68:10605",
            "http://164.92.105.75:8888",
            "http://51.159.115.233:3128",
            "http://20.111.54.16:8123"
        ]
        self.current_proxy: Optional[str] = None
        self.failed_proxies: set = set()
        self.success_count: Dict[str, int] = {}

    def _get_next_proxy(self) -> str:
        """Get next working proxy from the pool"""
        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            self.failed_proxies.clear()  # Reset failed proxies if all are exhausted
            available = self.proxies
        
        # Prefer proxies with successful history
        proxy = max(available, key=lambda x: self.success_count.get(x, 0))
        self.current_proxy = proxy
        return proxy

    def get_proxy_dict(self) -> Dict[str, str]:
        """Convert proxy URL to requests format"""
        proxy = self._get_next_proxy()
        return {"http": proxy, "https": proxy}

    def mark_success(self) -> None:
        """Mark current proxy as successful"""
        if self.current_proxy:
            self.success_count[self.current_proxy] = self.success_count.get(self.current_proxy, 0) + 1

    def mark_failed(self) -> None:
        """Mark current proxy as failed"""
        if self.current_proxy:
            self.failed_proxies.add(self.current_proxy)
            self.current_proxy = None

    def make_request(self, url: str, headers: Dict[str, str], max_retries: int = 3) -> Optional[requests.Response]:
        """Make request with proxy rotation and retry logic"""
        for attempt in range(max_retries):
            try:
                proxy_dict = self.get_proxy_dict()
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy_dict,
                    timeout=10,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    self.mark_success()
                    return response
                
                self.mark_failed()
                time.sleep(2 ** attempt + random.uniform(0.1, 0.5))
                
            except RequestException as e:
                print(f"Proxy request failed: {str(e)}")
                self.mark_failed()
                time.sleep(2 ** attempt + random.uniform(0.1, 0.5))
                
        return None
