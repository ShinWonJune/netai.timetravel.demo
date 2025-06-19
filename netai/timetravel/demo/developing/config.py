# -*- coding: utf-8 -*-
"""
Configuration and sensor-rack mapping for Time Travel extension
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ConfigSettings:
    """Configuration settings for the extension"""
    DEFAULT_TIME_RANGE_DAYS: int = 7
    DEFAULT_PLAYBACK_SPEED: float = 1.0
    MIN_PLAYBACK_SPEED: float = 0.1
    MAX_PLAYBACK_SPEED: float = 1000.0
    
    # MinIO configuration
    MINIO_ENDPOINT: str = "10.79.1.0:9000"
    MINIO_ACCESS_KEY: str = "gxQHjrQB9JHKtlIlSYNe"  # 실제 액세스 키로 변경
    MINIO_SECRET_KEY: str = "Vjsd5McgcZQ9NJ3NS9sThl7gIo1ZXVRfNfLwVJ3N"  # 실제 시크릿 키로 변경
    MINIO_BUCKET: str = "fms-temphum"
    MINIO_PREFIX: str = "2025-05/"
    MINIO_SECURE: bool = False  # HTTP 사용 시 False
    
    # Local fallback path
    LOCAL_DATA_PATH: str = "data/"
    
    # Parquet file
    PARQUET_FILE: str = "week_04_20250522_20250528_kst.parquet"
    
class Config:
    """Main configuration class"""
    
    # Instance of settings
    _settings = ConfigSettings()
    
    # Make settings accessible as class attributes
    DEFAULT_TIME_RANGE_DAYS = _settings.DEFAULT_TIME_RANGE_DAYS
    DEFAULT_PLAYBACK_SPEED = _settings.DEFAULT_PLAYBACK_SPEED
    MIN_PLAYBACK_SPEED = _settings.MIN_PLAYBACK_SPEED
    MAX_PLAYBACK_SPEED = _settings.MAX_PLAYBACK_SPEED
    MINIO_ENDPOINT = _settings.MINIO_ENDPOINT
    MINIO_ACCESS_KEY = _settings.MINIO_ACCESS_KEY
    MINIO_SECRET_KEY = _settings.MINIO_SECRET_KEY
    MINIO_BUCKET = _settings.MINIO_BUCKET
    MINIO_PREFIX = _settings.MINIO_PREFIX
    MINIO_SECURE = _settings.MINIO_SECURE
    LOCAL_DATA_PATH = _settings.LOCAL_DATA_PATH
    PARQUET_FILE = _settings.PARQUET_FILE
    
    @classmethod
    def get_rack_to_sensor_map(cls) -> Dict[str, str]:
        """랙 경로에서 센서 ID로의 매핑 반환"""
        return {
            # A 구역 랙들
            "/datacenter/RACK_A1": 20,
            "/datacenter/RACK_A3": 21, 
            "/datacenter/RACK_A5": 22,
            "/datacenter/RACK_A7": 23,
            "/datacenter/RACK_A10": 24,
            "/datacenter/RACK_A12": 25,
            
            # B 구역 랙들
            "/datacenter/RACK_B1": 191,
            "/datacenter/RACK_B3": 192,
            "/datacenter/RACK_B5": 193,
            "/datacenter/RACK_B10": 194,
            "/datacenter/RACK_B12": 195, 
            "/datacenter/RACK_B14": 196,
            
            # A0, A2, A4, A6, A8, A9 구역 랙들 (01)
            "/datacenter/RACK_A0_01": 203,
            "/datacenter/RACK_A2_01": 204,
            "/datacenter/RACK_A4_01": 205,
            "/datacenter/RACK_A6_01": 206,
            "/datacenter/RACK_A8_01": 207,
            "/datacenter/RACK_A9_01": 208,
            
            # A0, A2, A4, A6, A8, A9 구역 랙들 (02)
            "/datacenter/RACK_A0_02": 197,
            "/datacenter/RACK_A2_02": 198,
            "/datacenter/RACK_A4_02": 199,
            "/datacenter/RACK_A6_02": 200,
            "/datacenter/RACK_A8_02": 201,
            "/datacenter/RACK_A9_02": 202,
        }.copy()
    
    @classmethod
    def get_sensor_to_rack_map(cls) -> Dict[str, str]:
        """센서 ID에서 랙 경로로의 역매핑 반환"""
        rack_to_sensor = cls.get_rack_to_sensor_map()
        return {sensor_id: rack_path for rack_path, sensor_id in rack_to_sensor.items()}

# Parquet file column mapping
PARQUET_COLUMN_MAPPING = {
    'timestamp': 'timestamp',
    'objid': 'objId',
    'temperature_cold': 'TEMPERATURE1',
    'temperature_hot': 'TEMPERATURE',
    'humidity_cold': 'HUMIDITY1',
    'humidity_hot': 'HUMIDITY',
    'rsctypeid': 'rsctypeId'
}