"""Token 池管理"""

import random
from typing import Dict, List, Optional, Iterator, Set

from app.services.token.models import TokenInfo, TokenStatus, TokenPoolStats


class _TokenBucket:
    """高性能随机选取桶 (O(1) add/remove/random)."""

    def __init__(self):
        self.items: List[str] = []
        self.index: Dict[str, int] = {}

    def add(self, token: str):
        if token in self.index:
            return
        self.index[token] = len(self.items)
        self.items.append(token)

    def remove(self, token: str):
        idx = self.index.pop(token, None)
        if idx is None:
            return
        last = self.items.pop()
        if idx < len(self.items):
            self.items[idx] = last
            self.index[last] = idx

    def pick(self, exclude: Optional[Set[str]] = None) -> Optional[str]:
        if not self.items:
            return None
        if not exclude:
            return random.choice(self.items)
        # Try a few random picks first
        tries = min(5, len(self.items))
        for _ in range(tries):
            candidate = random.choice(self.items)
            if candidate not in exclude:
                return candidate
        # Fallback to linear scan (exclude set is usually tiny)
        for token in self.items:
            if token not in exclude:
                return token
        return None

    def __len__(self) -> int:
        return len(self.items)


class TokenPool:
    """Token 池（管理一组 Token）"""

    def __init__(self, name: str):
        self.name = name
        self._tokens: Dict[str, TokenInfo] = {}
        self._quota_buckets: Dict[int, _TokenBucket] = {}
        self._non_empty_quotas: Set[int] = set()

    def _bucket_for_quota(self, quota: int) -> _TokenBucket:
        bucket = self._quota_buckets.get(quota)
        if bucket is None:
            bucket = _TokenBucket()
            self._quota_buckets[quota] = bucket
        return bucket

    def _index_add(self, token: TokenInfo):
        if token.status != TokenStatus.ACTIVE or token.quota <= 0:
            return
        bucket = self._bucket_for_quota(token.quota)
        bucket.add(token.token)
        self._non_empty_quotas.add(token.quota)

    def _index_remove(self, token_str: str, quota: int, status: TokenStatus):
        if status != TokenStatus.ACTIVE or quota <= 0:
            return
        bucket = self._quota_buckets.get(quota)
        if not bucket:
            return
        bucket.remove(token_str)
        if len(bucket) == 0:
            self._non_empty_quotas.discard(quota)

    def update_index(self, token: TokenInfo, old_quota: int, old_status: TokenStatus):
        """增量更新索引"""
        self._index_remove(token.token, old_quota, old_status)
        self._index_add(token)

    def add(self, token: TokenInfo):
        """添加 Token"""
        self._tokens[token.token] = token
        self._index_add(token)

    def remove(self, token_str: str) -> bool:
        """删除 Token"""
        if token_str in self._tokens:
            token = self._tokens[token_str]
            self._index_remove(token_str, token.quota, token.status)
            del self._tokens[token_str]
            return True
        return False

    def get(self, token_str: str) -> Optional[TokenInfo]:
        """获取 Token"""
        return self._tokens.get(token_str)

    def select(self, exclude: set = None) -> Optional[TokenInfo]:
        """
        选择一个可用 Token
        策略:
        1. 选择 active 状态且有配额的 token
        2. 优先选择剩余额度最多的
        3. 如果额度相同，随机选择（避免并发冲突）
        """
        if not self._non_empty_quotas:
            return None

        quotas = sorted(self._non_empty_quotas, reverse=True)
        for quota in quotas:
            bucket = self._quota_buckets.get(quota)
            if not bucket:
                continue
            token_str = bucket.pick(exclude)
            if not token_str:
                continue
            token = self._tokens.get(token_str)
            if not token:
                continue
            if token.status != TokenStatus.ACTIVE or token.quota <= 0:
                continue
            return token
        return None

    def count(self) -> int:
        """Token 数量"""
        return len(self._tokens)

    def list(self) -> List[TokenInfo]:
        """获取所有 Token"""
        return list(self._tokens.values())

    def get_stats(self) -> TokenPoolStats:
        """获取池统计信息"""
        stats = TokenPoolStats(total=len(self._tokens))

        for token in self._tokens.values():
            stats.total_quota += token.quota

            if token.status == TokenStatus.ACTIVE:
                stats.active += 1
            elif token.status == TokenStatus.DISABLED:
                stats.disabled += 1
            elif token.status == TokenStatus.EXPIRED:
                stats.expired += 1
            elif token.status == TokenStatus.COOLING:
                stats.cooling += 1

        if stats.total > 0:
            stats.avg_quota = stats.total_quota / stats.total

        return stats

    def _rebuild_index(self):
        """重建索引（预留接口，用于加载时调用）"""
        self._quota_buckets = {}
        self._non_empty_quotas = set()
        for token in self._tokens.values():
            self._index_add(token)

    def __iter__(self) -> Iterator[TokenInfo]:
        return iter(self._tokens.values())


__all__ = ["TokenPool"]
