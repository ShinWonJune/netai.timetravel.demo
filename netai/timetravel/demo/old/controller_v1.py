from pxr import Usd, UsdGeom, Sdf
import omni.usd
import datetime
import time
import omni.timeline
import os
import csv
from datetime import datetime as dt

class TimeController:
    """USD Stage의 시간을 관리하고 온도/습도 데이터를 연동하는 컨트롤러"""
    
    def __init__(self):
        """시간 컨트롤러 초기화"""
        # 현재 USD 컨텍스트 가져오기
        self._usd_context = omni.usd.get_context()
        
        # 타임라인 인터페이스 가져오기
        self._timeline = omni.timeline.get_timeline_interface()
        
        # 센서 데이터 초기화
        self._sensor_data = []
        self._load_sensor_data()
        
        # 센서 데이터 기반으로 시간 범위 초기화
        if self._sensor_data:
            # 타임스탬프 형식 자동 감지 및 파싱
            first_timestamp = self._sensor_data[0]["@timestamp"]
            last_timestamp = self._sensor_data[-1]["@timestamp"]
            
            # 타임스탬프 파싱 처리
            try:
                self._start_time = self._parse_timestamp(first_timestamp)
                self._end_time = self._parse_timestamp(last_timestamp)
                
                if self._start_time and self._end_time:
                    self._current_time = self._start_time
                    print(f"[netai.timetravel.demo] 시간 범위 설정: {self._start_time} ~ {self._end_time}")
                else:
                    raise ValueError("Invalid timestamp format")
            except Exception as e:
                print(f"[netai.timetravel.demo] 타임스탬프 파싱 오류: {e}")
                # 오류 발생 시 기본값 사용
                self._start_time = dt(2025, 4, 1, 0, 0, 0)
                self._end_time = dt(2025, 4, 2, 0, 0, 0)
                self._current_time = self._start_time
        else:
            # 센서 데이터가 없는 경우 기본값 설정
            self._start_time = dt(2025, 4, 1, 0, 0, 0)
            self._end_time = dt(2025, 4, 2, 0, 0, 0)
            self._current_time = self._start_time
        
        # 재생 상태 초기화
        self._is_playing = False
        self._playback_speed = 1.0
        self._last_update_time = time.time()
        
        # 시간 관리자 경로 초기화 (Stage에 존재한다고 가정)
        self._time_manager_path = "/World/TimeManager"
        
        # 타겟 오브젝트 경로 초기화
        self._target_object_path = "/World/Object_445/Object_275"
        
        # 시간 관리자에 baseTime 설정 확인 및 설정
        self._ensure_base_time()
        
        # 초기 데이터 적용
        self._update_stage_time()
    
    def _load_sensor_data(self):
        """CSV 파일에서 센서 데이터 로드"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), "fms_temphum_objId21_last24h.csv")
            
            with open(csv_path, 'r') as file:
                reader = csv.DictReader(file)
                self._sensor_data = list(reader)
            
            # 값을 숫자 형식으로 변환
            for entry in self._sensor_data:
                entry["HUMIDITY1"] = float(entry["HUMIDITY1"])
                entry["TEMPERATURE1"] = float(entry["TEMPERATURE1"])
            
            print(f"[netai.timetravel.demo] 로드된 센서 데이터: {len(self._sensor_data)}개")
        except Exception as e:
            print(f"[netai.timetravel.demo] 센서 데이터 로드 오류: {e}")
            self._sensor_data = []
    
    def _parse_timestamp(self, timestamp_str):
        """타임스탬프 문자열을 datetime으로 파싱"""
        try:
            # 밀리초가 있는 ISO 형식 (예: 2025-03-26T06:15:48.846Z)
            if "." in timestamp_str and timestamp_str.endswith("Z"):
                return dt.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            # 밀리초 없는 ISO 형식 (예: 2025-03-26T06:15:48Z)
            elif timestamp_str.endswith("Z"):
                return dt.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
            # Z 접미사 없는 형식 (예: 2025-03-26T06:15:48)
            else:
                return dt.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            print(f"[netai.timetravel.demo] 타임스탬프 파싱 오류: {e}")
            return None
    
    def _ensure_base_time(self):
        """시간 관리자에 baseTime이 설정되어 있는지 확인하고, 없으면 설정"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return
                
            time_prim = stage.GetPrimAtPath(self._time_manager_path)
            if not time_prim or not time_prim.IsValid():
                print(f"[netai.timetravel.demo] 시간 관리자를 찾을 수 없음: {self._time_manager_path}")
                return
                
            # baseTime이 없으면 설정
            if not time_prim.GetCustomDataByKey("baseTime"):
                base_time = datetime.datetime(2025, 1, 1)
                # 소수점 둘째 자리까지 포함한 시간 포맷 사용
                base_time_str = base_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"  # .00Z 형식으로 저장
                time_prim.SetCustomDataByKey("baseTime", base_time_str)
                print(f"[netai.timetravel.demo] baseTime 설정: {base_time_str}")
        except Exception as e:
            print(f"[netai.timetravel.demo] baseTime 설정 오류: {e}")
    
    def _find_closest_data_entry(self, target_time):
        """주어진 시간에 가장 가까운 데이터 항목 찾기"""
        if not self._sensor_data:
            return None
        
        # 선형 검색으로 가장 가까운 시간 찾기 (이진 검색보다 안정적)
        best_idx = 0
        best_diff = float('inf')
        
        for i, entry in enumerate(self._sensor_data):
            entry_time = self._parse_timestamp(entry["@timestamp"])
            if not entry_time:
                continue
                
            diff = abs((target_time - entry_time).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        
        return self._sensor_data[best_idx]
    
    def _update_object_attributes(self, data_entry):
        """타겟 오브젝트의 속성 업데이트"""
        if not data_entry:
            return
            
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return
                
            obj_prim = stage.GetPrimAtPath(self._target_object_path)
            if not obj_prim or not obj_prim.IsValid():
                print(f"[netai.timetravel.demo] 타겟 오브젝트를 찾을 수 없음: {self._target_object_path}")
                return
                
            # 온도 속성 업데이트
            temp_attr = obj_prim.CreateAttribute("temperature", Sdf.ValueTypeNames.Float)
            temp_attr.Set(data_entry["TEMPERATURE1"])
            
            # 습도 속성 업데이트
            hum_attr = obj_prim.CreateAttribute("humidity", Sdf.ValueTypeNames.Float)
            hum_attr.Set(data_entry["HUMIDITY1"])
            
            # 메타데이터에도 값 추가
            obj_prim.SetCustomDataByKey("temperature", data_entry["TEMPERATURE1"])
            obj_prim.SetCustomDataByKey("humidity", data_entry["HUMIDITY1"])
            obj_prim.SetCustomDataByKey("timestamp", data_entry["@timestamp"])
            
            print(f"[netai.timetravel.demo] 오브젝트 업데이트 - 온도: {data_entry['TEMPERATURE1']}, 습도: {data_entry['HUMIDITY1']}")
        except Exception as e:
            print(f"[netai.timetravel.demo] 오브젝트 속성 업데이트 오류: {e}")
    
    def _datetime_to_timecode_value(self, dt_obj):
        """datetime을 USD 타임코드 값(실수)으로 변환"""
        stage = self._usd_context.get_stage()
        if not stage:
            return 0.0
        
        time_prim = stage.GetPrimAtPath(self._time_manager_path)
        if not time_prim or not time_prim.IsValid():
            return 0.0
        
        base_time_str = time_prim.GetCustomDataByKey("baseTime")
        if not base_time_str:
            return 0.0
        
        try:
            # 기준 시간 문자열도 동일한 파싱 함수 사용
            base_dt = self._parse_timestamp(base_time_str)
            if not base_dt:
                raise ValueError(f"Invalid base time format: {base_time_str}")
                
            delta_seconds = (dt_obj - base_dt).total_seconds()
            return delta_seconds
        except Exception as e:
            print(f"[netai.timetravel.demo] 시간 변환 오류: {e}")
            return 0.0
    
    def _update_stage_time(self):
        """현재 시간에 따라 USD Stage 시간 업데이트 및 센서 데이터 적용"""
        # 날짜/시간에서 타임코드 값(실수)으로 직접 변환
        timecode_value = self._datetime_to_timecode_value(self._current_time)
        
        # 타임라인 인터페이스를 통한 시간 설정
        try:
            self._timeline.set_current_time(timecode_value)
            print(f"[netai.timetravel.demo] 타임라인 시간 설정: {timecode_value}")
        except Exception as e:
            print(f"[netai.timetravel.demo] 타임라인 업데이트 오류: {e}")
        
        # 시간 관리자 업데이트 (메타데이터)
        try:
            stage = self._usd_context.get_stage()
            if stage:
                time_prim = stage.GetPrimAtPath(self._time_manager_path)
                if time_prim and time_prim.IsValid():
                    # 소수점 둘째 자리까지 포함한 시간 포맷 사용
                    time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
                    time_prim.SetCustomDataByKey("currentTime", time_str)
                    
                    # 현재 시간에 해당하는 센서 데이터 찾기 및 적용
                    data_entry = self._find_closest_data_entry(self._current_time)
                    if data_entry:
                        self._update_object_attributes(data_entry)
        except Exception as e:
            print(f"[netai.timetravel.demo] 시간 관리자 업데이트 오류: {e}")
    
    def set_time_range(self, start_time, end_time):
        """시간 범위 설정"""
        self._start_time = start_time
        self._end_time = end_time
        # 현재 시간이 범위 내에 있는지 확인
        if self._current_time < self._start_time:
            self._current_time = self._start_time
        elif self._current_time > self._end_time:
            self._current_time = self._end_time
        self._update_stage_time()
    
    def set_current_time(self, current_time):
        """현재 시간 설정"""
        if current_time < self._start_time:
            self._current_time = self._start_time
        elif current_time > self._end_time:
            self._current_time = self._end_time
        else:
            self._current_time = current_time
        self._update_stage_time()
    
    def set_progress(self, progress):
        """진행도(0.0-1.0)를 기반으로 현재 시간 설정"""
        if progress < 0.0:
            progress = 0.0
        elif progress > 1.0:
            progress = 1.0
        
        # 진행도에 따른 시간 계산
        delta = self._end_time - self._start_time
        seconds = delta.total_seconds() * progress
        self._current_time = self._start_time + datetime.timedelta(seconds=seconds)
        self._update_stage_time()
    
    def get_progress(self):
        """현재 진행도(0.0-1.0) 가져오기"""
        if self._end_time == self._start_time:
            return 0.0
        
        delta = self._current_time - self._start_time
        total_delta = self._end_time - self._start_time
        
        return delta.total_seconds() / total_delta.total_seconds()
    
    def set_to_present(self):
        """가장 최근 시간(종료 시간)으로 설정"""
        self._current_time = self._end_time
        self._update_stage_time()
    
    def toggle_playback(self):
        """재생 상태 토글"""
        self._is_playing = not self._is_playing
        if self._is_playing:
            self._last_update_time = time.time()
    
    def set_playback_speed(self, speed):
        """재생 속도 설정"""
        self._playback_speed = speed
    
    def update(self):
        """애니메이션을 위한 프레임별 업데이트 함수"""
        if not self._is_playing:
            return
        
        # 경과 시간 계산
        current_time = time.time()
        elapsed = (current_time - self._last_update_time) * self._playback_speed
        self._last_update_time = current_time
        
        # 현재 시간 업데이트
        delta = datetime.timedelta(seconds=elapsed)
        new_time = self._current_time + delta
        
        # 종료 시간 도달 확인
        if new_time >= self._end_time:
            self._current_time = self._end_time
            self._is_playing = False  # 재생 중지
        else:
            self._current_time = new_time
        
        # Stage 업데이트
        self._update_stage_time()
    
    # Getter 메서드들
    def get_start_time(self):
        return self._start_time
    
    def get_end_time(self):
        return self._end_time
    
    def get_current_time(self):
        return self._current_time
    
    def is_playing(self):
        return self._is_playing
    
    def get_playback_speed(self):
        return self._playback_speed
    
    def get_current_sensor_data(self):
        """현재 시간에 해당하는 센서 데이터 가져오기"""
        return self._find_closest_data_entry(self._current_time)
    
    def get_stage_time(self):
        """현재 Stage 시간 가져오기"""
        stage = self._usd_context.get_stage()
        if not stage:
            return "Stage를 찾을 수 없음"
        
        time_prim = stage.GetPrimAtPath(self._time_manager_path)
        if not time_prim or not time_prim.IsValid():
            return "TimeManager를 찾을 수 없음"
        
        current_time_str = time_prim.GetCustomDataByKey("currentTime")
        if not current_time_str:
            return "알 수 없는 시간"
        
        return current_time_str