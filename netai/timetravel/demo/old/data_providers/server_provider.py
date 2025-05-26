import requests
from datetime import datetime

from . import SensorDataProvider
from ..utils.time_utils import parse_timestamp

class ServerSensorDataProvider(SensorDataProvider):
    """서버 API에서 센서 데이터를 가져오는 구현체"""
    
    def __init__(self, api_url, auth_token=None):
        self._api_url = api_url
        self._auth_token = auth_token
        self._cache = {}  # 성능 향상을 위한 데이터 캐싱
        self._time_range = (None, None)
        self._sensor_ids = []
    
    def load_data(self):
        """서버에서 초기 메타데이터 로드 (시간 범위, 센서 ID 등)"""
        try:
            # 서버에서 메타데이터 요청
            headers = {"Authorization": f"Bearer {self._auth_token}"} if self._auth_token else {}
            response = requests.get(f"{self._api_url}/metadata", headers=headers)
            
            if response.status_code == 200:
                metadata = response.json()
                # 시간 범위 설정
                start_time = parse_timestamp(metadata.get("startTime"))
                end_time = parse_timestamp(metadata.get("endTime"))
                self._time_range = (start_time, end_time)
                
                # 센서 ID 목록 미리 로드
                self.get_sensor_ids()
                
                print(f"[netai.timetravel.demo] 서버 메타데이터 로드 완료: {len(self._sensor_ids)} 센서, 기간 {start_time} ~ {end_time}")
                return True
            else:
                print(f"[netai.timetravel.demo] 서버 메타데이터 로드 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[netai.timetravel.demo] 서버 연결 오류: {e}")
            return False
    
    def get_sensor_ids(self):
        """사용 가능한 센서 ID 목록 반환"""
        try:
            # 캐시된 센서 ID가 있으면 사용
            if self._sensor_ids:
                return self._sensor_ids
                
            # 없으면 서버에 요청
            headers = {"Authorization": f"Bearer {self._auth_token}"} if self._auth_token else {}
            response = requests.get(f"{self._api_url}/sensors", headers=headers)
            
            if response.status_code == 200:
                self._sensor_ids = response.json().get("sensors", [])
                return self._sensor_ids
            else:
                print(f"[netai.timetravel.demo] 센서 ID 로드 실패: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[netai.timetravel.demo] 센서 ID 요청 오류: {e}")
            return []
    
    def get_time_range(self):
        """데이터의 시작 및 종료 시간 반환"""
        return self._time_range
    
    def find_data_at_time(self, sensor_id, target_time):
        """특정 시간에 해당하는 센서 데이터 찾기"""
        # [이전 코드와 동일한 서버 데이터 요청 로직]
        try:
            # 캐시 키 생성
            cache_key = f"{sensor_id}_{target_time.isoformat()}"
            
            # 캐시된 데이터가 있으면 사용
            if cache_key in self._cache:
                return self._cache[cache_key]
                
            # 없으면 서버에 요청
            headers = {"Authorization": f"Bearer {self._auth_token}"} if self._auth_token else {}
            params = {
                "time": target_time.isoformat(),
                "approximation": "closest"  # 가장 가까운 데이터 요청
            }
            response = requests.get(f"{self._api_url}/sensors/{sensor_id}/data", 
                                 headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # 캐시에 저장
                self._cache[cache_key] = data
                return data
            else:
                print(f"[netai.timetravel.demo] 데이터 로드 실패: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[netai.timetravel.demo] 데이터 요청 오류: {e}")
            return None
    
    def get_data_in_range(self, sensor_id, start_time, end_time):
        """특정 시간 범위 내의 센서 데이터 찾기"""
        # [이전 코드와 동일한 서버 데이터 범위 요청 로직]
        pass