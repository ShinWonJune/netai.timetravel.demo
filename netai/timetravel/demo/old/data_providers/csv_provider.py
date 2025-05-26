import csv
import os
from datetime import datetime

from . import SensorDataProvider
from ..utils.time_utils import parse_timestamp

class CSVSensorDataProvider(SensorDataProvider):
    """CSV 파일에서 센서 데이터를 로드하는 구현체"""
    
    def __init__(self, csv_path):
        self._csv_path = csv_path
        self._sensor_data = {}  # objId별 데이터 저장
        self._time_range = (None, None)
    
    def load_data(self):
        """CSV 파일에서 센서 데이터 로드"""
        try:
            print(f"[DEBUG] CSV 파일 로드 시도: {self._csv_path}")
            
            if not os.path.exists(self._csv_path):
                print(f"[ERROR] CSV 파일을 찾을 수 없음: {self._csv_path}")
                return False
            
            with open(self._csv_path, 'r') as file:
                reader = csv.DictReader(file)
                data_list = list(reader)
            
            print(f"[DEBUG] CSV에서 {len(data_list)}개 행 로드됨")
            
            # objId 기준으로 데이터 그룹화
            for entry in data_list:
                obj_id = entry.get("objId", "21")
                
                # 숫자 형식으로 변환
                for field in ["TEMPERATURE1", "TEMPERATURE", "HUMIDITY1", "HUMIDITY"]:
                    if field in entry:
                        try:
                            entry[field] = float(entry[field])
                        except (ValueError, TypeError):
                            entry[field] = 0.0
                
                if obj_id not in self._sensor_data:
                    self._sensor_data[obj_id] = []
                self._sensor_data[obj_id].append(entry)
            
            # 각 센서 데이터를 타임스탬프 기준으로 정렬
            for obj_id in self._sensor_data:
                self._sensor_data[obj_id].sort(key=lambda x: x["@timestamp"])
            
            # 시간 범위 계산
            self._calculate_time_range()
            
            print(f"[netai.timetravel.demo] CSV 데이터 로드 완료: {len(self._sensor_data)} 센서, {sum(len(data) for data in self._sensor_data.values())} 데이터 포인트")
            print(f"[DEBUG] 센서 ID 목록: {list(self._sensor_data.keys())}")
            
            return True
        except Exception as e:
            print(f"[netai.timetravel.demo] 센서 데이터 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _calculate_time_range(self):
        """데이터의 시간 범위 계산"""
        all_timestamps = []
        for sensor_data in self._sensor_data.values():
            if sensor_data:
                all_timestamps.extend([entry["@timestamp"] for entry in sensor_data])
        
        if all_timestamps:
            all_timestamps.sort()
            first_timestamp = parse_timestamp(all_timestamps[0])
            last_timestamp = parse_timestamp(all_timestamps[-1])
            self._time_range = (first_timestamp, last_timestamp)
    
    def get_sensor_ids(self):
        """사용 가능한 센서 ID 목록 반환"""
        return list(self._sensor_data.keys())
    
    def get_time_range(self):
        """데이터의 시작 및 종료 시간 반환"""
        return self._time_range
    
    def find_data_at_time(self, sensor_id, target_time):
        """특정 시간에 해당하는 센서 데이터 찾기"""
        print(f"[DEBUG] 데이터 검색: 센서={sensor_id}, 시간={target_time}")
        
        if sensor_id not in self._sensor_data or not self._sensor_data[sensor_id]:
            print(f"[DEBUG] 센서 {sensor_id}의 데이터 없음")
            return None
        
        data_list = self._sensor_data[sensor_id]
        
        # 선형 검색으로 가장 가까운 시간 찾기
        best_idx = 0
        best_diff = float('inf')
        
        for i, entry in enumerate(data_list):
            entry_time = parse_timestamp(entry["@timestamp"])
            if not entry_time:
                continue
                
            diff = abs((target_time - entry_time).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        
        result = data_list[best_idx]
        print(f"[DEBUG] 검색 결과: {result.get('@timestamp', 'unknown')}")
        return result
    
    def get_data_in_range(self, sensor_id, start_time, end_time):
        """특정 시간 범위 내의 센서 데이터 찾기"""
        if sensor_id not in self._sensor_data:
            return []
            
        result = []
        for entry in self._sensor_data[sensor_id]:
            entry_time = parse_timestamp(entry["@timestamp"])
            if entry_time and start_time <= entry_time <= end_time:
                result.append(entry)
        
        return result