# -*- coding: utf-8 -*-
"""
Optimized controller using high-performance data structures (no pandas)
"""
from pxr import Usd, UsdGeom, Sdf, Gf
import omni.usd
import datetime
import time
import omni.timeline
import os
import numpy as np
import json
import io
import logging
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict
from .data_model import SensorDataCache, OptimizedSensorData
from .config import Config, PARQUET_COLUMN_MAPPING

# Parquet reading without pandas
try:
    import pyarrow.parquet as pq
    import pyarrow as pa
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False
    print("[netai.timetravel.demo] PyArrow not available. Will use fallback methods.")

# MinIO imports
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    print("[netai.timetravel.demo] MinIO not available. Will use local file fallback.")

class ParquetReader:
    """Lightweight parquet reader without pandas"""
    
    @staticmethod
    def read_parquet_to_dict(file_data: bytes) -> Dict[str, List]:
        """Read parquet file and return as dictionary of lists"""
        if not PYARROW_AVAILABLE:
            raise ImportError("PyArrow is required for parquet reading")
            
        # Read parquet file
        table = pq.read_table(io.BytesIO(file_data))
        
        # Convert to dictionary of lists
        data_dict = {}
        for column in table.column_names:
            # Convert to numpy array then to list for compatibility
            column_data = table.column(column).to_numpy()
            data_dict[column] = column_data.tolist()
            
        return data_dict
    
    @staticmethod
    def apply_column_mapping(data_dict: Dict[str, List]) -> Dict[str, List]:
        """Apply column mapping to standardize column names"""
        mapped_data = {}
        
        for std_name, file_name in PARQUET_COLUMN_MAPPING.items():
            if file_name in data_dict:
                mapped_data[std_name] = data_dict[file_name]
            elif std_name in data_dict:
                mapped_data[std_name] = data_dict[std_name]
                
        # Copy unmapped columns
        for col_name, col_data in data_dict.items():
            if col_name not in mapped_data.values() and col_name not in mapped_data:
                mapped_data[col_name] = col_data
                
        return mapped_data

class DataProcessor:
    """High-performance data processing without pandas"""
    
    @staticmethod
    def parse_timestamps(timestamp_strings: List[str]) -> np.ndarray:
        """Parse timestamp strings to numpy datetime64 array"""
        # Convert to numpy datetime64 for efficient processing
        return np.array([np.datetime64(ts) for ts in timestamp_strings])
    
    @staticmethod
    def filter_by_time_range(data_dict: Dict[str, List], 
                           start_time: datetime.datetime, 
                           end_time: datetime.datetime) -> Dict[str, List]:
        """Filter data by time range using numpy operations"""
        
        # Parse timestamps
        if 'timestamp' in data_dict:
            timestamps = DataProcessor.parse_timestamps(data_dict['timestamp'])
        elif 'timestamp_utc' in data_dict:
            # Convert UTC to KST (UTC+9)
            utc_timestamps = DataProcessor.parse_timestamps(data_dict['timestamp_utc'])
            timestamps = utc_timestamps + np.timedelta64(9, 'h')
        else:
            return data_dict
        
        # Convert datetime to numpy datetime64 for comparison
        start_np = np.datetime64(start_time)
        end_np = np.datetime64(end_time)
        
        # Create mask for time range
        mask = (timestamps >= start_np) & (timestamps <= end_np)
        
        # Apply mask to all columns
        filtered_data = {}
        for col_name, col_data in data_dict.items():
            if len(col_data) == len(mask):
                col_array = np.array(col_data)
                filtered_data[col_name] = col_array[mask].tolist()
            else:
                filtered_data[col_name] = col_data
                
        # Add processed timestamps
        filtered_data['timestamp'] = timestamps[mask].astype('datetime64[s]').astype('str').tolist()
        
        return filtered_data
    
    @staticmethod
    def group_by_sensor(data_dict: Dict[str, List]) -> Dict[str, Dict[str, List]]:
        """Group data by sensor ID"""
        if 'objid' not in data_dict:
            return {}
            
        # Get unique sensor IDs
        sensor_ids = list(set(data_dict['objid']))
        grouped_data = {}
        
        for sensor_id in sensor_ids:
            if sensor_id is None:  # Skip None values
                continue
                
            # Create mask for this sensor
            objid_array = np.array(data_dict['objid'])
            mask = objid_array == sensor_id
            
            # Extract data for this sensor
            sensor_data = {}
            for col_name, col_data in data_dict.items():
                if len(col_data) == len(mask):
                    col_array = np.array(col_data)
                    sensor_data[col_name] = col_array[mask].tolist()
                    
            grouped_data[sensor_id] = sensor_data
            
        return grouped_data

class OptimizedTimeController:
    """Ultra high-performance time controller without pandas dependency"""
    
    def __init__(self):
        """Initialize the optimized controller"""
        self._stage = None
        self._timeline = omni.timeline.get_timeline_interface()
        
        # Logger setup (로거를 먼저 초기화)
        self._logger = logging.getLogger("[netai.timetravel.demo]")
        if not self._logger.handlers:  # 핸들러가 없을 때만 추가
            logging.basicConfig(level=logging.INFO)
        
        # Time range
        self._start_time = datetime.datetime.now() - datetime.timedelta(days=Config.DEFAULT_TIME_RANGE_DAYS)
        self._end_time = datetime.datetime.now()
        self._current_time = self._start_time
        
        # Playback state
        self._is_playing = False
        self._playback_speed = Config.DEFAULT_PLAYBACK_SPEED
        self._last_update_time = time.time()
        
        # MinIO configuration (optional)
        self._minio_client = None
        if MINIO_AVAILABLE:
            try:
                self._minio_client = Minio(
                    Config.MINIO_ENDPOINT,
                    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
                    secure=False
                )
            except Exception as e:
                self._logger.warning(f"MinIO connection failed: {e}")
        
        # High-performance data cache
        self._data_cache = SensorDataCache()
        self._data_lock = threading.RLock()
        
        # Rack to sensor mapping from config
        self._rack_to_sensor_map = Config.get_rack_to_sensor_map()
        self._sensor_to_rack_map = Config.get_sensor_to_rack_map()
        
        # Performance optimization
        self._batch_update_buffer = defaultdict(dict)
        self._last_batch_update = time.time()
        self._last_cache_values = {}
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._loading_future = None
        
        # Statistics
        self._load_start_time = None
        self._load_end_time = None
        
    def set_stage(self, stage):
        """Set the USD stage"""
        self._stage = stage
        self._setup_rack_attributes()
        
    def _setup_rack_attributes(self):
        """Setup temperature and humidity attributes on rack prims"""
        if not self._stage:
            return
            
        for rack_path in self._rack_to_sensor_map.keys():
            prim = self._stage.GetPrimAtPath(rack_path)
            if prim and prim.IsValid():
                # Create attributes if they don't exist
                if not prim.HasAttribute("temperature_cold"):
                    prim.CreateAttribute("temperature_cold", Sdf.ValueTypeNames.Float).Set(0.0)
                if not prim.HasAttribute("temperature_hot"):
                    prim.CreateAttribute("temperature_hot", Sdf.ValueTypeNames.Float).Set(0.0)
                if not prim.HasAttribute("humidity_cold"):
                    prim.CreateAttribute("humidity_cold", Sdf.ValueTypeNames.Float).Set(0.0)
                if not prim.HasAttribute("humidity_hot"):
                    prim.CreateAttribute("humidity_hot", Sdf.ValueTypeNames.Float).Set(0.0)

    def _load_parquet_file(self, file_path: str, start_time: datetime.datetime, end_time: datetime.datetime):
        """Load a single parquet file with optimized processing"""
        try:
            # Download file from MinIO or read local file
            if self._minio_client:
                response = self._minio_client.get_object(Config.MINIO_BUCKET, file_path)
                data = response.read()
                response.close()
                response.release_conn()
            else:
                # Fallback to local file
                with open(file_path, 'rb') as f:
                    data = f.read()
            
            # Read parquet data to dictionary
            data_dict = ParquetReader.read_parquet_to_dict(data)
            
            # Apply column mapping
            data_dict = ParquetReader.apply_column_mapping(data_dict)
            
            # Filter by objId - 매핑된 센서만 유지 (중간 변환 단계 제거)
            if 'objid' in data_dict:
                # 매핑에 있는 objId만 필터링
                valid_objids = set(self._sensor_to_rack_map.keys())
                self._logger.info(f"Found objId values: {set(data_dict['objid'])}")
                self._logger.info(f"Valid objId values: {valid_objids}")
                
                # 유효한 objId만 남기기
                valid_indices = [i for i, objid in enumerate(data_dict['objid']) 
                               if objid in valid_objids]
                
                self._logger.info(f"Valid sensor records: {len(valid_indices)} / {len(data_dict['objid'])}")
                
                # 모든 컬럼에 필터 적용
                for col_name, col_data in data_dict.items():
                    if len(col_data) == len(data_dict['objid']):
                        data_dict[col_name] = [col_data[i] for i in valid_indices]
            
            # Filter by time range
            data_dict = DataProcessor.filter_by_time_range(data_dict, start_time, end_time)
            
            # Validate required columns exist
            required_cols = ['timestamp', 'objid', 'temperature_cold', 'temperature_hot', 
                           'humidity_cold', 'humidity_hot']
            missing_cols = [col for col in required_cols if col not in data_dict]
            if missing_cols:
                self._logger.warning(f"Missing columns in {file_path}: {missing_cols}")
                return
                
            # Group by sensor (objId를 직접 사용)
            grouped_data = DataProcessor.group_by_sensor(data_dict)
            
            self._logger.info(f"Grouped data by objId: {list(grouped_data.keys())}")
            
            for objid, sensor_dict in grouped_data.items():
                if len(sensor_dict.get('timestamp', [])) > 0:
                    # objId를 직접 캐시 키로 사용
                    self._add_sensor_data_to_cache(objid, sensor_dict)
                    self._logger.info(f"Added {len(sensor_dict.get('timestamp', []))} records for objId {objid}")
                        
            record_count = len(data_dict.get('timestamp', []))
            self._logger.info(f"Loaded {record_count} records from {file_path}")
            
        except Exception as e:
            self._logger.error(f"Error loading {file_path}: {e}")
            
    def _add_sensor_data_to_cache(self, objid: int, sensor_dict: Dict[str, List]):
        """Add sensor data to cache using objId directly"""
        with self._data_lock:
            sensor_data = self._data_cache.get_sensor_data(objid)
            sensor_data.add_dataframe_dict(sensor_dict)

    def _discover_parquet_files(self, start_time: datetime.datetime, end_time: datetime.datetime) -> List[str]:
        """Discover parquet files that contain data for the time range"""
        files = []
        try:
            if self._minio_client:
                # List all parquet files in the prefix
                objects = self._minio_client.list_objects(Config.MINIO_BUCKET, prefix=Config.MINIO_PREFIX)
                for obj in objects:
                    if obj.object_name.endswith('.parquet'):
                        files.append(obj.object_name)
            else:
                # Fallback to local directory
                import glob
                local_path = os.path.join(Config.LOCAL_DATA_PATH, "*.parquet")
                files = glob.glob(local_path)
            
            # Sort files to ensure proper order
            files.sort()
            
        except Exception as e:
            self._logger.error(f"Error discovering parquet files: {e}")
            
        return files
    
    def load_data_for_time_range(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Load sensor data for the specified time range"""
        self._load_start_time = time.time()
        self._logger.info(f"Loading data from {start_time} to {end_time}")
        
        # Clear existing data
        with self._data_lock:
            self._data_cache.clear()
        
        # Discover parquet files
        parquet_files = self._discover_parquet_files(start_time, end_time)
        
        if not parquet_files:
            self._logger.warning("No parquet files found for the time range")
            return
            
        # Load files concurrently
        futures = []
        for file_path in parquet_files:
            future = self._executor.submit(self._load_parquet_file, file_path, start_time, end_time)
            futures.append(future)
        
        # Wait for all files to load
        for future in futures:
            future.result()
            
        # Optimize data structures after loading
        with self._data_lock:
            self._data_cache.optimize()
            
        self._load_end_time = time.time()
        load_duration = self._load_end_time - self._load_start_time
        self._logger.info(f"Data loading completed in {load_duration:.2f} seconds")

    def set_time_range(self, start_time: datetime.datetime, end_time: datetime.datetime):
        """Set time range and load data"""
        self._start_time = start_time
        self._end_time = end_time
        self._current_time = start_time
        
        # Load data asynchronously
        if self._loading_future:
            self._loading_future.cancel()
        self._loading_future = self._executor.submit(self.load_data_for_time_range, start_time, end_time)
        
    def set_current_time(self, target_time: datetime.datetime):
        """Set current time and update stage"""
        if target_time < self._start_time:
            target_time = self._start_time
        elif target_time > self._end_time:
            target_time = self._end_time
            
        self._current_time = target_time
        self.update_stage_time()
        
    def set_to_present(self):
        """Set time to present (end time)"""
        self.set_current_time(self._end_time)
        
    def toggle_playback(self):
        """Toggle playback state"""
        self._is_playing = not self._is_playing
        self._last_update_time = time.time()
        
    def set_playback_speed(self, speed: float):
        """Set playback speed"""
        self._playback_speed = max(Config.MIN_PLAYBACK_SPEED, 
                                  min(Config.MAX_PLAYBACK_SPEED, speed))
        
    def update_playback(self):
        """Update playback time"""
        if not self._is_playing:
            return
            
        current_real_time = time.time()
        delta_real = current_real_time - self._last_update_time
        
        # Convert real time to simulation time (speed factor)
        delta_sim = datetime.timedelta(seconds=delta_real * self._playback_speed * 60)
        
        new_time = self._current_time + delta_sim
        
        if new_time > self._end_time:
            new_time = self._end_time
            self._is_playing = False
            
        self._current_time = new_time
        self._last_update_time = current_real_time
        
    def update_stage_time(self):
        """Update USD stage with current sensor data"""
        if not self._stage:
            return
            
        with self._data_lock:
            # Batch update all racks
            updates = {}
            
            for rack_path, objid in self._rack_to_sensor_map.items():
                sensor_data = self._data_cache.get_sensor_data(objid)
                values = sensor_data.get_interpolated_at_time(self._current_time)
                
                if values:
                    # Check if values changed to avoid unnecessary updates
                    cache_key = f"{rack_path}_{self._current_time}"
                    if cache_key not in self._last_cache_values or self._last_cache_values[cache_key] != values:
                        updates[rack_path] = values
                        self._last_cache_values[cache_key] = values
            
            # Apply updates to stage
            self._apply_stage_updates(updates)
    
    def _apply_stage_updates(self, updates: Dict[str, Dict]):
        """Apply sensor value updates to USD stage efficiently"""
        if not updates:
            return
            
        for rack_path, values in updates.items():
            prim = self._stage.GetPrimAtPath(rack_path)
            if prim and prim.IsValid():
                # Batch attribute updates
                if 'temperature_cold' in values:
                    prim.GetAttribute("temperature_cold").Set(values['temperature_cold'])
                if 'temperature_hot' in values:
                    prim.GetAttribute("temperature_hot").Set(values['temperature_hot'])
                if 'humidity_cold' in values:
                    prim.GetAttribute("humidity_cold").Set(values['humidity_cold'])
                if 'humidity_hot' in values:
                    prim.GetAttribute("humidity_hot").Set(values['humidity_hot'])
    
    def get_rack_data_at_time(self, rack_path: str, target_time: datetime.datetime = None) -> Optional[Dict]:
        """Get sensor data for specific rack at given time"""
        if target_time is None:
            target_time = self._current_time
            
        objid = self._rack_to_sensor_map.get(rack_path)
        if objid is None:
            return None
            
        with self._data_lock:
            sensor_data = self._data_cache.get_sensor_data(objid)
            return sensor_data.get_interpolated_at_time(target_time)
    
    # Getter methods
    def get_start_time(self) -> datetime.datetime:
        return self._start_time
        
    def get_end_time(self) -> datetime.datetime:
        return self._end_time
        
    def get_current_time(self) -> datetime.datetime:
        return self._current_time
        
    def is_playing(self) -> bool:
        return self._is_playing
        
    def get_playback_speed(self) -> float:
        return self._playback_speed
        
    def get_time_progress(self) -> float:
        """Get current time as progress (0.0 to 1.0)"""
        if self._end_time <= self._start_time:
            return 0.0
        total_duration = (self._end_time - self._start_time).total_seconds()
        current_duration = (self._current_time - self._start_time).total_seconds()
        return min(1.0, max(0.0, current_duration / total_duration))
        
    def set_time_progress(self, progress: float):
        """Set time by progress (0.0 to 1.0)"""
        progress = min(1.0, max(0.0, progress))
        total_duration = self._end_time - self._start_time
        target_time = self._start_time + total_duration * progress
        self.set_current_time(target_time)
        
    def get_stage_time(self) -> str:
        """Get formatted stage time string"""
        return self._current_time.strftime("%Y-%m-%d %H:%M:%S")
        
    def get_rack_count(self) -> int:
        """Get total number of racks"""
        return len(self._rack_to_sensor_map)
        
    def get_sensor_count(self) -> int:
        """Get total number of sensors"""
        return len(self._sensor_to_rack_map)
        
    def is_data_loaded(self) -> bool:
        """Check if data is loaded"""
        with self._data_lock:
            return self._data_cache.get_total_records() > 0
            
    def get_load_progress(self) -> str:
        """Get data loading progress string"""
        if self._loading_future and not self._loading_future.done():
            return "Loading..."
        elif self.is_data_loaded():
            return f"Loaded ({self._data_cache.get_total_records()} records)"
        else:
            return "No data"