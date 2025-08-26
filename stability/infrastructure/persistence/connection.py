# -*- coding: utf-8 -*-
"""Database connection manager owned by the new stability runtime."""

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from queue import Empty, Queue
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

try:
    import pymysql

    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

from .legacy_models import Base
from .legacy_models import (
    AppPerformance,
    FPSData,
    MonitoringSession,
    NetworkStats,
    PowerConsumption,
    SystemPerformance,
)
from . import models as _stability_models  # noqa: F401
from .connection_pool import OptimizedConnectionPool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """优化的数据库连接管理器"""

    def __init__(self, config_file: str = None):
        self.config_file = config_file or os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "config",
            "database.json",
        )
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self.config: Dict[str, Any] = {}
        self.raw_config: Dict[str, Any] = {}
        self.connection_pool: Optional[OptimizedConnectionPool] = None
        self.batch_queue = Queue()
        self.batch_thread = None
        self.batch_processing = False
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as handle:
                    self.raw_config = json.load(handle)
                    self.config = self._normalize_config(self.raw_config)
            else:
                self.raw_config = self.get_default_config()
                self.config = self._normalize_config(self.raw_config)
                self.save_config()
        except Exception as exc:
            logger.error(f"加载数据库配置失败: {exc}")
            self.raw_config = self.get_default_config()
            self.config = self._normalize_config(self.raw_config)

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "type": "sqlite",
            "sqlite": {"path": "data/android_metrics.db"},
            "mysql": {
                "host": "localhost",
                "port": 3306,
                "username": "metrics_user",
                "password": "metrics_pass",
                "database": "android_metrics",
                "charset": "utf8mb4",
            },
            "connection_pool": {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
            },
            "data_retention": {"days": 3, "auto_cleanup": True},
            "echo": False,
        }

    def _project_root(self) -> str:
        return os.path.abspath(os.path.join(os.path.dirname(self.config_file), ".."))

    def _resolve_sqlite_path(self, sqlite_path: str) -> str:
        if os.path.isabs(sqlite_path):
            return sqlite_path
        return os.path.abspath(os.path.join(self._project_root(), sqlite_path))

    def _relativize_sqlite_path(self, sqlite_path: str) -> str:
        try:
            project_root = self._project_root()
            relative_path = os.path.relpath(sqlite_path, project_root)
            if not relative_path.startswith(".."):
                return relative_path
        except Exception:
            pass
        return sqlite_path

    def _normalize_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {
            "type": config_data.get("type"),
            "echo": config_data.get("echo", False),
        }

        if not normalized["type"]:
            if "sqlite" in config_data:
                normalized["type"] = "sqlite"
            elif "mysql" in config_data:
                normalized["type"] = "mysql"
            else:
                normalized["type"] = "sqlite"

        pool_config = config_data.get("connection_pool", {})
        normalized.update(
            {
                "pool_size": pool_config.get("pool_size", 5),
                "max_overflow": pool_config.get("max_overflow", 10),
                "pool_timeout": pool_config.get("pool_timeout", 30),
                "pool_recycle": pool_config.get("pool_recycle", 3600),
                "data_retention_days": config_data.get("data_retention", {}).get("days", 3),
            }
        )

        sqlite_config = config_data.get("sqlite", {})
        sqlite_path = sqlite_config.get("path", config_data.get("path", "data/android_metrics.db"))
        normalized["sqlite_path"] = self._resolve_sqlite_path(sqlite_path)

        mysql_source = config_data.get("mysql", config_data)
        normalized.update(
            {
                "host": mysql_source.get("host", "localhost"),
                "port": mysql_source.get("port", 3306),
                "username": mysql_source.get("username", "metrics_user"),
                "password": mysql_source.get("password", "metrics_pass"),
                "database": mysql_source.get("database", "android_metrics"),
                "charset": mysql_source.get("charset", "utf8mb4"),
            }
        )
        return normalized

    def _build_persisted_config(self) -> Dict[str, Any]:
        return {
            "type": self.config.get("type", "sqlite"),
            "sqlite": {
                "path": self._relativize_sqlite_path(
                    self.config.get("sqlite_path", self._resolve_sqlite_path("data/android_metrics.db"))
                )
            },
            "mysql": {
                "host": self.config.get("host", "localhost"),
                "port": self.config.get("port", 3306),
                "username": self.config.get("username", "metrics_user"),
                "password": self.config.get("password", "metrics_pass"),
                "database": self.config.get("database", "android_metrics"),
                "charset": self.config.get("charset", "utf8mb4"),
            },
            "connection_pool": {
                "pool_size": self.config.get("pool_size", 5),
                "max_overflow": self.config.get("max_overflow", 10),
                "pool_timeout": self.config.get("pool_timeout", 30),
                "pool_recycle": self.config.get("pool_recycle", 3600),
            },
            "data_retention": {
                "days": self.config.get("data_retention_days", 3),
                "auto_cleanup": True,
            },
            "echo": self.config.get("echo", False),
        }

    def _is_sqlite(self) -> bool:
        return self.config.get("type", "sqlite") == "sqlite"

    def _is_mysql(self) -> bool:
        return self.config.get("type") == "mysql"

    def save_config(self):
        try:
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as handle:
                json.dump(self._build_persisted_config(), handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error(f"保存数据库配置失败: {exc}")

    def update_config(self, new_config: Dict[str, Any]):
        self.config.update(new_config)
        if "sqlite_path" in self.config:
            self.config["sqlite_path"] = self._resolve_sqlite_path(self.config["sqlite_path"])
        self.save_config()
        if self.engine:
            self.disconnect()
            self.connect()

    def get_connection_string(self) -> str:
        if self._is_sqlite():
            return f"sqlite:///{self.config['sqlite_path']}"
        return (
            f"mysql+pymysql://{self.config['username']}:{self.config['password']}"
            f"@{self.config['host']}:{self.config['port']}"
            f"/{self.config['database']}"
            f"?charset={self.config['charset']}"
        )

    def test_connection(self) -> Tuple[bool, str]:
        try:
            if self._is_mysql() and not PYMYSQL_AVAILABLE:
                return False, "未安装 PyMySQL，无法连接 MySQL"

            engine_kwargs = {"echo": False}
            if self._is_sqlite():
                engine_kwargs["connect_args"] = {"check_same_thread": False}
            else:
                engine_kwargs["pool_timeout"] = 10

            test_engine = create_engine(self.get_connection_string(), **engine_kwargs)
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1")).fetchone()
            test_engine.dispose()
            return True, "连接成功"
        except OperationalError as exc:
            if self._is_sqlite():
                return False, f"SQLite 连接错误: {str(exc)}"
            if "Access denied" in str(exc):
                return False, "用户名或密码错误"
            if "Unknown database" in str(exc):
                return False, f"数据库 '{self.config['database']}' 不存在"
            if "Can't connect to MySQL server" in str(exc):
                return False, f"无法连接到MySQL服务器 {self.config['host']}:{self.config['port']}"
            return False, f"数据库连接错误: {str(exc)}"
        except Exception as exc:
            return False, f"连接测试失败: {str(exc)}"

    def create_database_if_not_exists(self) -> bool:
        try:
            if self._is_sqlite():
                sqlite_dir = os.path.dirname(self.config["sqlite_path"])
                if sqlite_dir:
                    os.makedirs(sqlite_dir, exist_ok=True)
                return True

            if not PYMYSQL_AVAILABLE:
                logger.error("未安装 PyMySQL，无法初始化 MySQL 数据库")
                return False

            server_config = self.config.copy()
            connection_string = (
                f"mysql+pymysql://{server_config['username']}:{server_config['password']}"
                f"@{server_config['host']}:{server_config['port']}"
                f"?charset={server_config['charset']}"
            )
            server_engine = create_engine(connection_string, echo=False)
            with server_engine.connect() as conn:
                result = conn.execute(text(f"SHOW DATABASES LIKE '{self.config['database']}'"))
                if not result.fetchone():
                    conn.execute(
                        text(
                            f"CREATE DATABASE `{self.config['database']}` "
                            f"CHARACTER SET {self.config['charset']} "
                            f"COLLATE {self.config['charset']}_unicode_ci"
                        )
                    )
                    conn.commit()
                    logger.info(f"数据库 '{self.config['database']}' 创建成功")
            server_engine.dispose()
            return True
        except Exception as exc:
            logger.error(f"创建数据库失败: {exc}")
            return False

    def connect(self) -> bool:
        try:
            if self.engine:
                return True
            if not self.create_database_if_not_exists():
                return False

            engine_kwargs = {
                "echo": self.config.get("echo", False),
                "poolclass": QueuePool,
                "pool_size": self.config.get("pool_size", 10),
                "max_overflow": self.config.get("max_overflow", 20),
                "pool_timeout": self.config.get("pool_timeout", 30),
                "pool_recycle": self.config.get("pool_recycle", 3600),
                "pool_pre_ping": True,
            }
            if self._is_sqlite():
                engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            else:
                engine_kwargs["connect_args"] = {
                    "charset": "utf8mb4",
                    "connect_timeout": 10,
                    "read_timeout": 30,
                    "write_timeout": 30,
                }

            self.engine = create_engine(self.get_connection_string(), **engine_kwargs)
            if self._is_sqlite():
                self._configure_sqlite_engine()

            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            success, message = self.test_connection()
            if not success:
                self.disconnect()
                logger.error(f"数据库连接测试失败: {message}")
                return False

            self.create_tables()
            self.connection_pool = OptimizedConnectionPool(self, max_size=20)
            self.connection_pool._initialize_pool()
            self.start_batch_processing()
            logger.info("数据库连接成功")
            return True
        except Exception as exc:
            logger.error(f"数据库连接失败: {exc}")
            self.disconnect()
            return False

    def _configure_sqlite_engine(self):
        if not self.engine or not self._is_sqlite():
            return

        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            if not isinstance(dbapi_connection, sqlite3.Connection):
                return
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    def disconnect(self):
        try:
            self.stop_batch_processing()
            if self.connection_pool:
                self.connection_pool.close_all()
                self.connection_pool = None
            if self.engine:
                self.engine.dispose()
                self.engine = None
            self.SessionLocal = None
            logger.info("数据库连接已断开")
        except Exception as exc:
            logger.error(f"断开数据库连接时出错: {exc}")

    def start_batch_processing(self):
        if not self.batch_processing:
            self.batch_processing = True
            self.batch_thread = threading.Thread(target=self._batch_worker, daemon=True)
            self.batch_thread.start()
            logger.info("批量处理线程已启动")

    def stop_batch_processing(self):
        if self.batch_processing:
            self.batch_processing = False
            if self.batch_thread and self.batch_thread.is_alive():
                self.batch_thread.join(timeout=5)
            logger.info("批量处理线程已停止")

    def _batch_worker(self):
        batch_data = []
        last_flush_time = time.time()
        batch_size = 50
        flush_interval = 5.0

        while self.batch_processing:
            try:
                try:
                    batch_data.append(self.batch_queue.get(timeout=1.0))
                except Empty:
                    pass

                current_time = time.time()
                should_flush = len(batch_data) >= batch_size or (
                    batch_data and current_time - last_flush_time >= flush_interval
                )
                if should_flush and batch_data:
                    self._flush_batch(batch_data)
                    batch_data.clear()
                    last_flush_time = current_time
            except Exception as exc:
                logger.error(f"批量处理出错: {exc}")
                time.sleep(1)

        if batch_data:
            self._flush_batch(batch_data)

    def _flush_batch(self, batch_data):
        if not batch_data:
            return
        try:
            session = self.connection_pool.get_session()
            try:
                grouped_data = {}
                for item in batch_data:
                    grouped_data.setdefault(item["table"], []).append(item["data"])

                for table_name, data_list in grouped_data.items():
                    if table_name == "system_performance":
                        session.bulk_insert_mappings(SystemPerformance, data_list)
                    elif table_name == "app_performance":
                        session.bulk_insert_mappings(AppPerformance, data_list)
                    elif table_name == "network_stats":
                        session.bulk_insert_mappings(NetworkStats, data_list)
                    elif table_name == "fps_data":
                        session.bulk_insert_mappings(FPSData, data_list)
                    elif table_name == "power_consumption":
                        session.bulk_insert_mappings(PowerConsumption, data_list)
                session.commit()
                logger.debug(f"批量提交了 {len(batch_data)} 条数据")
            except Exception as exc:
                session.rollback()
                logger.error(f"批量提交失败: {exc}")
                raise
            finally:
                self.connection_pool.return_session(session)
        except Exception as exc:
            logger.error(f"批量刷新失败: {exc}")

    def add_to_batch(self, table_name: str, data: Dict[str, Any]):
        if self.batch_processing:
            try:
                self.batch_queue.put(
                    {"table": table_name, "data": data, "timestamp": time.time()},
                    block=False,
                )
            except Exception:
                logger.warning("批量队列已满，直接写入数据库")
                self._flush_batch([{"table": table_name, "data": data}])

    def flush_pending_batch_queue(self):
        pending_items = []
        while True:
            try:
                pending_items.append(self.batch_queue.get(block=False))
            except Empty:
                break
        if pending_items:
            logger.info(f"同步刷新批量队列中的 {len(pending_items)} 条数据")
            self._flush_batch(pending_items)

    def create_tables(self):
        if not self.engine:
            raise RuntimeError("数据库未连接")
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据表创建/更新完成")

    @contextmanager
    def get_session(self) -> Session:
        if not self.SessionLocal:
            raise RuntimeError("数据库未连接，请先调用 connect() 方法")
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(f"数据库操作失败: {exc}")
            raise
        finally:
            session.close()

    def get_session_sync(self) -> Session:
        if not self.SessionLocal:
            raise RuntimeError("数据库未连接，请先调用 connect() 方法")
        return self.SessionLocal()

    def is_connected(self) -> bool:
        if not self.engine:
            return False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_database_info(self) -> Dict[str, Any]:
        if not self.is_connected():
            return {"connected": False}
        try:
            with self.engine.connect() as conn:
                if self._is_sqlite():
                    version = conn.execute(text("SELECT sqlite_version()")).fetchone()[0]
                    table_count = conn.execute(
                        text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                    ).fetchone()[0]
                    sqlite_path = self.config["sqlite_path"]
                    size_mb = 0.0
                    if os.path.exists(sqlite_path):
                        size_mb = round(os.path.getsize(sqlite_path) / 1024 / 1024, 2)
                    return {
                        "connected": True,
                        "database_type": "sqlite",
                        "database": os.path.basename(sqlite_path),
                        "path": sqlite_path,
                        "version": version,
                        "size_mb": float(size_mb),
                        "table_count": table_count,
                        "retention_days": self.config.get("data_retention_days", 3),
                    }

                version = conn.execute(text("SELECT VERSION()")).fetchone()[0]
                size = conn.execute(
                    text(
                        f"SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) "
                        f"FROM information_schema.tables WHERE table_schema = '{self.config['database']}'"
                    )
                ).fetchone()[0] or 0
                table_count = conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM information_schema.tables "
                        f"WHERE table_schema = '{self.config['database']}'"
                    )
                ).fetchone()[0]
                return {
                    "connected": True,
                    "database_type": "mysql",
                    "database": self.config["database"],
                    "host": self.config["host"],
                    "port": self.config["port"],
                    "version": version,
                    "size_mb": float(size),
                    "table_count": table_count,
                    "retention_days": self.config.get("data_retention_days", 3),
                }
        except Exception as exc:
            logger.error(f"获取数据库信息失败: {exc}")
            return {"connected": False, "error": str(exc)}

    def cleanup_old_data(self) -> int:
        if not self.is_connected():
            return 0
        try:
            from datetime import timedelta
            from stability.time_utils import utcnow

            retention_days = self.config.get("data_retention_days", 3)
            with self.get_session() as session:
                cutoff_date = utcnow() - timedelta(days=retention_days)
                deleted_count = session.query(MonitoringSession).filter(
                    MonitoringSession.start_time < cutoff_date
                ).delete(synchronize_session=False)
                logger.info(f"清理了 {deleted_count} 条过期监控记录")
                return deleted_count
        except Exception as exc:
            logger.error(f"清理过期数据失败: {exc}")
            return 0

    def __enter__(self):
        if not self.connect():
            raise RuntimeError("无法连接到数据库")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


db_manager = DatabaseConnectionManager()
