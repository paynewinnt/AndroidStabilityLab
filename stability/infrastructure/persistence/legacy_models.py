"""Legacy monitoring ORM models owned by the stability persistence layer."""

import json
import logging

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

from stability.time_utils import utcnow

logger = logging.getLogger(__name__)

Base = declarative_base()


class MonitoringSession(Base):
    """Legacy monitoring session table mapping."""

    __tablename__ = "monitoring_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(255), nullable=False, index=True)
    device_id = Column(String(100), nullable=True, index=True)
    start_time = Column(DateTime, default=utcnow, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), default="running", nullable=False)
    config_json = Column(Text, nullable=True)
    selected_apps = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    system_performance = relationship(
        "SystemPerformance",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    app_performance = relationship(
        "AppPerformance",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    network_stats = relationship(
        "NetworkStats",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    fps_data = relationship(
        "FPSData",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    power_consumption = relationship(
        "PowerConsumption",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def set_config(self, config_dict):
        self.config_json = json.dumps(config_dict, ensure_ascii=False, default=str)

    def get_config(self):
        try:
            return json.loads(self.config_json) if self.config_json else {}
        except json.JSONDecodeError:
            logger.error("Failed to parse config JSON for session %s", self.id)
            return {}

    def set_selected_apps(self, apps_list):
        self.selected_apps = json.dumps(apps_list, ensure_ascii=False)

    def get_selected_apps(self):
        try:
            return json.loads(self.selected_apps) if self.selected_apps else []
        except json.JSONDecodeError:
            logger.error("Failed to parse selected apps JSON for session %s", self.id)
            return []


class SystemPerformance(Base):
    """Legacy system performance table mapping."""

    __tablename__ = "system_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    cpu_usage = Column(Float, nullable=True)
    cpu_temperature = Column(Float, nullable=True)
    load_1min = Column(Float, nullable=True)
    load_5min = Column(Float, nullable=True)
    load_15min = Column(Float, nullable=True)
    memory_total = Column(Float, nullable=True)
    memory_available = Column(Float, nullable=True)
    memory_used = Column(Float, nullable=True)
    memory_cached = Column(Float, nullable=True)
    memory_buffers = Column(Float, nullable=True)
    storage_total = Column(Float, nullable=True)
    storage_available = Column(Float, nullable=True)
    storage_used = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    battery_temperature = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)
    battery_health = Column(Integer, nullable=True)
    battery_status = Column(Integer, nullable=True)
    network_rx_bytes = Column(Float, nullable=True)
    network_tx_bytes = Column(Float, nullable=True)
    screen_brightness = Column(Float, nullable=True)
    screen_on = Column(Boolean, nullable=True)

    session = relationship("MonitoringSession", back_populates="system_performance")

    __table_args__ = (Index("idx_system_session_time", "session_id", "timestamp"),)


class AppPerformance(Base):
    """Legacy app performance table mapping."""

    __tablename__ = "app_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    package_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    cpu_usage = Column(Float, nullable=True)
    cpu_time_user = Column(Float, nullable=True)
    cpu_time_system = Column(Float, nullable=True)
    memory_pss = Column(Float, nullable=True)
    memory_rss = Column(Float, nullable=True)
    memory_vss = Column(Float, nullable=True)
    memory_uss = Column(Float, nullable=True)
    memory_java = Column(Float, nullable=True)
    memory_native = Column(Float, nullable=True)
    memory_graphics = Column(Float, nullable=True)
    threads_count = Column(Integer, nullable=True)
    open_files = Column(Integer, nullable=True)

    session = relationship("MonitoringSession", back_populates="app_performance")

    __table_args__ = (Index("idx_app_session_package_time", "session_id", "package_name", "timestamp"),)


class NetworkStats(Base):
    """Legacy network stats table mapping."""

    __tablename__ = "network_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    package_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    rx_bytes = Column(Float, nullable=True)
    tx_bytes = Column(Float, nullable=True)
    rx_packets = Column(Integer, nullable=True)
    tx_packets = Column(Integer, nullable=True)
    connection_count = Column(Integer, nullable=True)
    tcp_connections = Column(Integer, nullable=True)
    udp_connections = Column(Integer, nullable=True)

    session = relationship("MonitoringSession", back_populates="network_stats")

    __table_args__ = (Index("idx_network_session_package_time", "session_id", "package_name", "timestamp"),)


class FPSData(Base):
    """Legacy FPS data table mapping."""

    __tablename__ = "fps_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    package_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    fps = Column(Float, nullable=True)
    frame_time_avg = Column(Float, nullable=True)
    frame_time_max = Column(Float, nullable=True)
    frame_time_99p = Column(Float, nullable=True)
    total_frames = Column(Integer, nullable=True)
    dropped_frames = Column(Integer, nullable=True)
    jank_frames = Column(Integer, nullable=True)
    gpu_usage = Column(Float, nullable=True)
    gpu_temperature = Column(Float, nullable=True)

    session = relationship("MonitoringSession", back_populates="fps_data")

    __table_args__ = (Index("idx_fps_session_package_time", "session_id", "package_name", "timestamp"),)


class PowerConsumption(Base):
    """Legacy power consumption table mapping."""

    __tablename__ = "power_consumption"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    package_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    power_usage = Column(Float, nullable=True)
    cpu_power = Column(Float, nullable=True)
    gpu_power = Column(Float, nullable=True)
    display_power = Column(Float, nullable=True)
    camera_power = Column(Float, nullable=True)
    wifi_power = Column(Float, nullable=True)
    bluetooth_power = Column(Float, nullable=True)
    cellular_power = Column(Float, nullable=True)
    audio_power = Column(Float, nullable=True)
    video_power = Column(Float, nullable=True)
    wakelock_count = Column(Integer, nullable=True)
    wakelock_time = Column(Float, nullable=True)
    alarm_count = Column(Integer, nullable=True)

    session = relationship("MonitoringSession", back_populates="power_consumption")

    __table_args__ = (Index("idx_power_session_package_time", "session_id", "package_name", "timestamp"),)


class AppConfig(Base):
    """Legacy app config table mapping."""

    __tablename__ = "app_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_name = Column(String(255), unique=True, nullable=False, index=True)
    app_name = Column(String(255), nullable=True)
    version_name = Column(String(100), nullable=True)
    version_code = Column(Integer, nullable=True)
    monitoring_enabled = Column(Boolean, default=True, nullable=False)
    auto_start = Column(Boolean, default=False, nullable=False)
    color_code = Column(String(7), nullable=True)
    chart_visible = Column(Boolean, default=True, nullable=False)
    cpu_threshold = Column(Float, nullable=True)
    memory_threshold = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_monitored = Column(DateTime, nullable=True)


__all__ = [
    "AppConfig",
    "AppPerformance",
    "Base",
    "FPSData",
    "MonitoringSession",
    "NetworkStats",
    "PowerConsumption",
    "SystemPerformance",
]
