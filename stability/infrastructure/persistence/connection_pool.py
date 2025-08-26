from __future__ import annotations

import logging
import threading
from queue import Empty, Queue

from sqlalchemy import text

logger = logging.getLogger(__name__)


class OptimizedConnectionPool:
    """优化的数据库连接池"""

    def __init__(self, connection_manager, max_size: int = 20):
        self.connection_manager = connection_manager
        self.max_size = max_size
        self.pool = Queue(maxsize=max_size)
        self.active_connections = set()
        self.lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        if not hasattr(self.connection_manager, "SessionLocal") or self.connection_manager.SessionLocal is None:
            logger.debug("SessionLocal未就绪，跳过连接池预初始化")
            return
        if not self.connection_manager.is_connected():
            logger.debug("数据库未连接，跳过连接池预初始化")
            return

        for _ in range(min(5, self.max_size)):
            try:
                session = self.connection_manager.SessionLocal()
                session.execute(text("SELECT 1"))
                self.pool.put(session, block=False)
                logger.debug("连接池预创建1个连接")
            except Exception as exc:
                logger.error(f"初始化连接池失败: {exc}")
                break

        logger.info(f"连接池初始化完成，预创建了 {self.pool.qsize()} 个连接")

    def get_session(self):
        if not hasattr(self.connection_manager, "SessionLocal") or self.connection_manager.SessionLocal is None:
            raise RuntimeError("数据库未初始化，SessionLocal不可用")

        try:
            session = self.pool.get(block=True, timeout=5)
            with self.lock:
                self.active_connections.add(session)
            return session
        except Empty:
            if len(self.active_connections) < self.max_size:
                try:
                    session = self.connection_manager.SessionLocal()
                    session.execute(text("SELECT 1"))
                    with self.lock:
                        self.active_connections.add(session)
                    return session
                except Exception as exc:
                    logger.error(f"创建新数据库连接失败: {exc}")
                    raise RuntimeError(f"无法创建数据库连接: {exc}")
            raise RuntimeError("连接池已满，无法获取新连接")

    def return_session(self, session):
        with self.lock:
            if session in self.active_connections:
                self.active_connections.remove(session)

        try:
            if not self.pool.full():
                session.rollback()
                session.expunge_all()
                self.pool.put(session, block=False)
            else:
                session.close()
        except Exception as exc:
            logger.error(f"返还连接失败: {exc}")
            session.close()

    def close_all(self):
        with self.lock:
            for session in list(self.active_connections):
                session.close()
            self.active_connections.clear()

        while not self.pool.empty():
            try:
                session = self.pool.get(block=False)
                session.close()
            except Empty:
                break
