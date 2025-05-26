from abc import ABC, abstractmethod
from datetime import datetime

class SensorDataProvider(ABC):
    """센서 데이터 접근을 위한 추상 인터페이스"""
    
    @abstractmethod
    def load_data(self):
        """데이터 초기 로드"""
        pass
    
    @abstractmethod
    def get_sensor_ids(self):
        """사용 가능한 모든 센서 ID 목록 반환"""
        pass
    
    @abstractmethod
    def get_time_range(self):
        """데이터의 시작 및 종료 시간 반환"""
        pass
    
    @abstractmethod
    def find_data_at_time(self, sensor_id, target_time):
        """특정 시간에 해당하는 센서 데이터 찾기"""
        pass
    
    @abstractmethod
    def get_data_in_range(self, sensor_id, start_time, end_time):
        """특정 시간 범위 내의 센서 데이터 찾기"""
        pass