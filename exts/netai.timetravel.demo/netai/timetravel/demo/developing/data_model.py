# -*- coding: utf-8 -*-
"""
Optimized data structures for high-performance time travel (no pandas)
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import datetime

@dataclass
class SensorReading:
    """Single sensor reading"""
    timestamp: datetime.datetime
    temperature_cold: float
    temperature_hot: float
    humidity_cold: float
    humidity_hot: float
    
class OptimizedSensorData:
    """
    Optimized sensor data storage using numpy arrays for performance
    """
    def __init__(self, sensor_id: Union[int, str]):
        self.sensor_id = sensor_id
        
        # Pre-allocate numpy arrays for performance (한달치 데이터 고려)
        self.capacity = 50000  # 1분마다 * 60 * 24 * 31일 = 약 45,000개
        self.size = 0
        
        # Time stored as int64 (nanoseconds since epoch)
        self.timestamps = np.zeros(self.capacity, dtype=np.int64)
        
        # Sensor values
        self.temp_cold = np.zeros(self.capacity, dtype=np.float32)
        self.temp_hot = np.zeros(self.capacity, dtype=np.float32)
        self.humidity_cold = np.zeros(self.capacity, dtype=np.float32)
        self.humidity_hot = np.zeros(self.capacity, dtype=np.float32)
        
        # 정렬 상태 추적
        self._is_sorted = True
        
    def add_data(self, timestamp: datetime.datetime, temp_cold: float, temp_hot: float, 
                 hum_cold: float, hum_hot: float):
        """Add a single data point"""
        if self.size >= self.capacity:
            self._grow_arrays()
            
        # Convert timestamp to nanoseconds
        ts_ns = int(timestamp.timestamp() * 1_000_000_000)
        
        # 정렬 상태 체크 (새 데이터가 이전 데이터보다 작으면 정렬 깨짐)
        if self.size > 0 and ts_ns < self.timestamps[self.size - 1]:
            self._is_sorted = False
        
        self.timestamps[self.size] = ts_ns
        self.temp_cold[self.size] = temp_cold
        self.temp_hot[self.size] = temp_hot
        self.humidity_cold[self.size] = hum_cold
        self.humidity_hot[self.size] = hum_hot
        
        self.size += 1
        
    def add_dataframe_dict(self, data_dict: Dict[str, List]):
        """Add data from dictionary format (replacing pandas DataFrame)"""
        timestamps = data_dict.get('timestamp', [])
        temp_cold = data_dict.get('temperature_cold', [])
        temp_hot = data_dict.get('temperature_hot', [])
        hum_cold = data_dict.get('humidity_cold', [])
        hum_hot = data_dict.get('humidity_hot', [])
        
        n_rows = len(timestamps)
        if n_rows == 0:
            return
            
        if self.size + n_rows > self.capacity:
            self._grow_arrays(self.size + n_rows)
        
        # 배치로 데이터 추가 (성능 최적화)
        start_idx = self.size
        valid_count = 0
        
        for i in range(n_rows):
            try:
                if isinstance(timestamps[i], str):
                    # Parse ISO format timestamp - KST 기준
                    dt_str = timestamps[i].replace('Z', '+09:00') if 'Z' in timestamps[i] else timestamps[i]
                    dt = datetime.datetime.fromisoformat(dt_str)
                    ts_ns = int(dt.timestamp() * 1_000_000_000)
                else:
                    # Assume already a datetime object
                    ts_ns = int(timestamps[i].timestamp() * 1_000_000_000)
                    
                self.timestamps[start_idx + valid_count] = ts_ns
                self.temp_cold[start_idx + valid_count] = float(temp_cold[i]) if i < len(temp_cold) else 0.0
                self.temp_hot[start_idx + valid_count] = float(temp_hot[i]) if i < len(temp_hot) else 0.0
                self.humidity_cold[start_idx + valid_count] = float(hum_cold[i]) if i < len(hum_cold) else 0.0
                self.humidity_hot[start_idx + valid_count] = float(hum_hot[i]) if i < len(hum_hot) else 0.0
                
                valid_count += 1
                
            except (ValueError, IndexError):
                # Skip invalid data points
                continue
                
        self.size += valid_count
        self._is_sorted = False  # 새 데이터 추가 후 정렬 필요
        
    def _ensure_sorted(self):
        """데이터가 정렬되어 있는지 확인하고 필요시 정렬"""
        if not self._is_sorted and self.size > 0:
            # 모든 배열을 시간순으로 정렬
            sort_indices = np.argsort(self.timestamps[:self.size])
            
            self.timestamps[:self.size] = self.timestamps[sort_indices]
            self.temp_cold[:self.size] = self.temp_cold[sort_indices]
            self.temp_hot[:self.size] = self.temp_hot[sort_indices]
            self.humidity_cold[:self.size] = self.humidity_cold[sort_indices]
            self.humidity_hot[:self.size] = self.humidity_hot[sort_indices]
            
            self._is_sorted = True
        
    def _grow_arrays(self, min_capacity=None):
        """Grow arrays when capacity is reached"""
        new_capacity = max(self.capacity * 2, min_capacity or self.capacity)
        
        # Create new arrays
        new_timestamps = np.zeros(new_capacity, dtype=np.int64)
        new_temp_cold = np.zeros(new_capacity, dtype=np.float32)
        new_temp_hot = np.zeros(new_capacity, dtype=np.float32)
        new_humidity_cold = np.zeros(new_capacity, dtype=np.float32)
        new_humidity_hot = np.zeros(new_capacity, dtype=np.float32)
        
        # Copy existing data
        if self.size > 0:
            new_timestamps[:self.size] = self.timestamps[:self.size]
            new_temp_cold[:self.size] = self.temp_cold[:self.size]
            new_temp_hot[:self.size] = self.temp_hot[:self.size]
            new_humidity_cold[:self.size] = self.humidity_cold[:self.size]
            new_humidity_hot[:self.size] = self.humidity_hot[:self.size]
        
        # Replace arrays
        self.timestamps = new_timestamps
        self.temp_cold = new_temp_cold
        self.temp_hot = new_temp_hot
        self.humidity_cold = new_humidity_cold
        self.humidity_hot = new_humidity_hot
        self.capacity = new_capacity
        
    def get_interpolated_at_time(self, target_time: datetime.datetime) -> Optional[Dict]:
        """Get interpolated sensor values at specific time (최고 성능)"""
        if self.size == 0:
            return None
            
        # 정렬 보장
        self._ensure_sorted()
            
        # Convert target time to nanoseconds
        target_ns = int(target_time.timestamp() * 1_000_000_000)
        
        # Binary search on timestamps (O(log n))
        idx = np.searchsorted(self.timestamps[:self.size], target_ns)
        
        # Handle edge cases
        if idx == 0:
            return self._get_values_at_index(0)
        elif idx >= self.size:
            return self._get_values_at_index(self.size - 1)
        else:
            # Linear interpolation between two closest points
            t0 = self.timestamps[idx - 1]
            t1 = self.timestamps[idx]
            
            if t1 == t0:  # Avoid division by zero
                return self._get_values_at_index(idx - 1)
                
            alpha = (target_ns - t0) / (t1 - t0)
            
            return {
                'temperature_cold': self._lerp(self.temp_cold[idx-1], self.temp_cold[idx], alpha),
                'temperature_hot': self._lerp(self.temp_hot[idx-1], self.temp_hot[idx], alpha),
                'humidity_cold': self._lerp(self.humidity_cold[idx-1], self.humidity_cold[idx], alpha),
                'humidity_hot': self._lerp(self.humidity_hot[idx-1], self.humidity_hot[idx], alpha)
            }
            
    def _get_values_at_index(self, idx: int) -> Dict:
        """Get values at specific index"""
        return {
            'temperature_cold': float(self.temp_cold[idx]),
            'temperature_hot': float(self.temp_hot[idx]),
            'humidity_cold': float(self.humidity_cold[idx]),
            'humidity_hot': float(self.humidity_hot[idx])
        }
        
    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        """Linear interpolation"""
        return a + (b - a) * t
        
    def clear(self):
        """Clear all data"""
        self.size = 0
        self._is_sorted = True
        
    def trim_to_size(self):
        """Trim arrays to actual size to save memory"""
        if self.size < self.capacity:
            self._ensure_sorted()  # 정렬 후 트림
            
            self.timestamps = self.timestamps[:self.size].copy()
            self.temp_cold = self.temp_cold[:self.size].copy()
            self.temp_hot = self.temp_hot[:self.size].copy()
            self.humidity_cold = self.humidity_cold[:self.size].copy()
            self.humidity_hot = self.humidity_hot[:self.size].copy()
            self.capacity = self.size

class SensorDataCache:
    """
    High-performance cache for all sensor data
    """
    def __init__(self):
        self._sensors: Dict[int, OptimizedSensorData] = {}
        
    def get_sensor_data(self, sensor_id: int) -> OptimizedSensorData:
        """Get or create sensor data container using objId"""
        if sensor_id not in self._sensors:
            self._sensors[sensor_id] = OptimizedSensorData(sensor_id)
        return self._sensors[sensor_id]
        
    def clear(self):
        """Clear all sensor data"""
        for sensor_data in self._sensors.values():
            sensor_data.clear()
            
    def optimize(self):
        """Optimize memory usage by trimming arrays and sorting"""
        for sensor_data in self._sensors.values():
            sensor_data._ensure_sorted()
            sensor_data.trim_to_size()
            
    def get_total_records(self) -> int:
        """Get total number of records across all sensors"""
        return sum(sensor_data.size for sensor_data in self._sensors.values())
        
    def get_sensor_ids(self) -> List[int]:
        """Get list of all sensor IDs"""
        return list(self._sensors.keys())