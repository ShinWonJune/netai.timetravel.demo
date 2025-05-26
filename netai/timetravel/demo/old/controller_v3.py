from pxr import Usd, UsdGeom, Sdf
import omni.usd
import datetime
import time
import omni.timeline
import os
import csv
from datetime import datetime as dt
import random

# --------------------------------------------------------
# Controller discripsion
# Time manager 생성기능을 _ensure_base_time() 에 추가
# sensor id 24개를 임의로 rack과 매핑.

# 센서 데이터 로딩 및 그룹화:
# CSV 파일에서 센서 데이터가 로드되어 센서 ID별로 그룹화되어 있습니다.
# 이 데이터는 _sensor_data 딕셔너리에 저장되며, 키는 센서 ID이고 값은 해당 센서의 데이터 목록입니다.

# --------------------------------------------------------


class TimeController:
    """USD Stage의 시간을 관리하고 데이터센터 센서 데이터를 연동하는 컨트롤러"""
    
    def __init__(self):
        """시간 컨트롤러 초기화"""
        # 현재 USD 컨텍스트 가져오기
        self._usd_context = omni.usd.get_context()
        
        # 타임라인 인터페이스 가져오기
        self._timeline = omni.timeline.get_timeline_interface()
        
        # 시간 관리자 경로 초기화
        self._time_manager_path = "/World/TimeManager"
        
        # 랙 목록 및 매핑 초기화
        self._rack_paths = []
        self._rack_to_sensor_map = {}  # 랙 경로 -> 센서 ID 매핑
        self._load_rack_paths()
        
        # 센서 데이터 초기화
        self._sensor_data = {}  # objId 기준으로 그룹화된 센서 데이터
        self._load_sensor_data()
        
        # 센서 데이터 기반으로 시간 범위 초기화
        self._initialize_time_range()
        
        # 재생 상태 초기화
        self._is_playing = False
        self._playback_speed = 1.0
        self._last_update_time = time.time()
        
        # 시간 관리자에 baseTime 설정 확인 및 설정
        self._ensure_base_time()
        
        # 초기 데이터 적용
        self._update_stage_time()
        
        # 매핑된 랙 수 출력
        print(f"[netai.timetravel.demo] 초기화 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}, 데이터가 있는 센서 수: {len(self._sensor_data)}")
    
    
    def _load_rack_paths(self):
        """랙 경로 목록 로드"""
        try:
            rack_dir_path = os.path.join(os.path.dirname(__file__), "rack_directory.txt")
            rack_map_path = os.path.join(os.path.dirname(__file__), "rack_sensor_map.txt")
            
            if os.path.exists(rack_dir_path):
                with open(rack_dir_path, 'r') as file:
                    content = file.read().strip()
                    self._rack_paths = content.split()
                
                print(f"[netai.timetravel.demo] 로드된 랙 수: {len(self._rack_paths)}")
                
                # 랙-센서 매핑 파일이 있는지 확인
                if os.path.exists(rack_map_path):
                    self._load_rack_sensor_map(rack_map_path)
                else:
                    # 임시 매핑 생성
                    self._create_temporary_mapping()
            else:
                print(f"[netai.timetravel.demo] 랙 디렉토리 파일을 찾을 수 없음: {rack_dir_path}")
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙 경로 로드 오류: {e}")
            self._rack_paths = []
    
    def _load_rack_sensor_map(self, map_file_path):
        """랙-센서 매핑 파일 로드"""
        try:
            with open(map_file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue  # 빈 줄이나 주석 무시
                    
                    # 형식: 랙_경로 센서ID
                    parts = line.split()
                    if len(parts) >= 2:
                        rack_path = parts[0]
                        sensor_id = parts[1]
                        self._rack_to_sensor_map[rack_path] = sensor_id
            
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 로드 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 로드 오류: {e}")
            # 오류 시 임시 매핑 생성
            self._create_temporary_mapping()
    
    def _create_temporary_mapping(self):
        """임시 랙-센서 매핑 생성 (objId 20-25, 191-208 사용)"""
        # 센서 ID 목록 생성 (요구사항에 따라 20-25, 191-208)
        sensor_ids = [str(i) for i in range(20, 26)] + [str(i) for i in range(191, 209)]
        print(f"[netai.timetravel.demo] 사용 가능한 센서 ID: {', '.join(sensor_ids)}")
        
        # 랙 경로 목록이 있고 센서 ID가 충분하면 매핑 진행
        if self._rack_paths and sensor_ids:
            # 랙 경로 중 최대 24개 (센서 ID 개수만큼) 랜덤 선택
            import random
            selected_racks = self._rack_paths.copy()
            if len(selected_racks) > len(sensor_ids):
                selected_racks = random.sample(selected_racks, len(sensor_ids))
            
            # 선택된 랙과 센서 ID 매핑
            for i, rack_path in enumerate(selected_racks):
                if i < len(sensor_ids):
                    self._rack_to_sensor_map[rack_path] = sensor_ids[i]
            
            print(f"[netai.timetravel.demo] 임시 랙-센서 매핑 생성 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
            
            # 매핑 정보 로그 출력 (처음 5개만)
            log_count = min(5, len(self._rack_to_sensor_map))
            sample_mappings = list(self._rack_to_sensor_map.items())[:log_count]
            mapping_str = ", ".join([f"{rack} -> {sensor}" for rack, sensor in sample_mappings])
            print(f"[netai.timetravel.demo] 샘플 매핑: {mapping_str}...")
        else:
            print("[netai.timetravel.demo] 랙 경로 또는 센서 ID가 부족하여 매핑을 생성할 수 없음")
            
    def save_rack_sensor_map(self, file_path=None):
        """현재 랙-센서 매핑을 파일로 저장"""
        if not file_path:
            file_path = os.path.join(os.path.dirname(__file__), "rack_sensor_map.txt")
            
        try:
            with open(file_path, 'w') as file:
                file.write("# 랙 경로와 센서 ID 매핑\n")
                file.write("# 형식: 랙_경로 센서ID\n\n")
                
                for rack_path, sensor_id in self._rack_to_sensor_map.items():
                    file.write(f"{rack_path} {sensor_id}\n")
                    
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 저장 완료: {file_path}")
            return True
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 저장 오류: {e}")
            return False
    
    def _load_sensor_data(self):
        """CSV 파일에서 센서 데이터 로드"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), "fms_temphum_03260406.csv")
            
            if not os.path.exists(csv_path):
                # 테스트를 위해 기존 CSV 파일로 폴백
                csv_path = os.path.join(os.path.dirname(__file__), "fms_temphum_objId21_last24h.csv")
                print(f"[netai.timetravel.demo] fms_temphum_03260406.csv 파일이 없어 대체 파일을 사용합니다: {csv_path}")
            
            with open(csv_path, 'r') as file:
                reader = csv.DictReader(file)
                data_list = list(reader)
            
            # objId 기준으로 데이터 그룹화
            for entry in data_list:
                # 컬럼이 존재하는지 확인하고 필요하면 기본값 설정
                obj_id = entry.get("objId", "21")  # objId가 없으면 "21"을 기본값으로 사용
                
                # 숫자 형식으로 변환
                for field in ["TEMPERATURE1", "TEMPERATURE", "HUMIDITY1", "HUMIDITY"]:
                    if field in entry:
                        try:
                            entry[field] = float(entry[field])
                        except (ValueError, TypeError):
                            entry[field] = 0.0  # 변환 실패 시 기본값
                
                # 해당 objId의 데이터 리스트에 추가
                if obj_id not in self._sensor_data:
                    self._sensor_data[obj_id] = []
                self._sensor_data[obj_id].append(entry)
            
            # 각 센서 데이터를 타임스탬프 기준으로 정렬
            for obj_id in self._sensor_data:
                self._sensor_data[obj_id].sort(key=lambda x: x["@timestamp"])
            
            # 결과 요약
            total_entries = sum(len(data) for data in self._sensor_data.values())
            print(f"[netai.timetravel.demo] 로드된 센서 데이터: {total_entries}개, 센서 수: {len(self._sensor_data)}")
            
            # 센서 ID 목록 출력
            sensor_ids = list(self._sensor_data.keys())
            print(f"[netai.timetravel.demo] 센서 ID: {', '.join(sensor_ids[:10])}{'...' if len(sensor_ids) > 10 else ''}")
            
        except Exception as e:
            print(f"[netai.timetravel.demo] 센서 데이터 로드 오류: {e}")
            self._sensor_data = {}
    
    def _initialize_time_range(self):
        """센서 데이터 기반으로 시간 범위 초기화"""
        try:
            # 모든 센서 데이터에서 최초/최후 타임스탬프 찾기
            all_timestamps = []
            
            for sensor_id, data_list in self._sensor_data.items():
                if data_list:
                    all_timestamps.extend([entry["@timestamp"] for entry in data_list])
            
            if all_timestamps:
                all_timestamps.sort()
                first_timestamp = all_timestamps[0]
                last_timestamp = all_timestamps[-1]
                
                # 타임스탬프 파싱
                self._start_time = self._parse_timestamp(first_timestamp)
                self._end_time = self._parse_timestamp(last_timestamp)
                self._current_time = self._start_time
                
                print(f"[netai.timetravel.demo] 시간 범위 설정: {self._start_time} ~ {self._end_time}")
            else:
                raise ValueError("센서 데이터가 없습니다")
        except Exception as e:
            print(f"[netai.timetravel.demo] 시간 범위 초기화 오류: {e}")
            # 기본값 설정
            self._start_time = dt(2025, 3, 26, 0, 0, 0)
            self._end_time = dt(2025, 3, 27, 0, 0, 0)
            self._current_time = self._start_time
            print(f"[netai.timetravel.demo] 기본 시간 범위로 설정: {self._start_time} ~ {self._end_time}")
    
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
        """시간 관리자가 존재하는지 확인하고, 없으면 생성하고 baseTime 설정"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                print("[netai.timetravel.demo] USD Stage를 찾을 수 없음")
                return
                
            # TimeManager가 존재하는지 확인
            time_prim = stage.GetPrimAtPath(self._time_manager_path)
            
            # TimeManager가 없으면 생성
            if not time_prim or not time_prim.IsValid():
                print(f"[netai.timetravel.demo] TimeManager가 없음. 생성 중: {self._time_manager_path}")
                
                # 경로 분리 및 부모 경로 확인
                parent_path = os.path.dirname(self._time_manager_path)
                if parent_path != "/":
                    parent_prim = stage.GetPrimAtPath(parent_path)
                    if not parent_prim or not parent_prim.IsValid():
                        # 부모 경로가 없으면 생성
                        print(f"[netai.timetravel.demo] 부모 경로 생성 중: {parent_path}")
                        parent_prim = UsdGeom.Xform.Define(stage, parent_path)
                
                # TimeManager 생성
                time_prim = UsdGeom.Xform.Define(stage, self._time_manager_path)
                
                # TimeManager 설명 추가
                time_prim.SetCustomDataByKey("description", "시간 관리 및 동기화를 위한 객체")
                time_prim.SetCustomDataByKey("created", dt.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                
                print(f"[netai.timetravel.demo] TimeManager 생성 완료: {self._time_manager_path}")
            
            # baseTime이 없으면 설정
            if not time_prim.GetCustomDataByKey("baseTime"):
                base_time = datetime.datetime(2025, 1, 1)
                # 소수점 둘째 자리까지 포함한 시간 포맷 사용
                base_time_str = base_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"  # .00Z 형식으로 저장
                time_prim.SetCustomDataByKey("baseTime", base_time_str)
                print(f"[netai.timetravel.demo] baseTime 설정: {base_time_str}")
            
            # 현재 시간도 초기화
            current_time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
            time_prim.SetCustomDataByKey("currentTime", current_time_str)
            
            return True
            
        except Exception as e:
            print(f"[netai.timetravel.demo] TimeManager 초기화 오류: {e}")
            return False
    
    def _find_closest_data_entry(self, target_time, sensor_id):
        """주어진 센서 ID와 시간에 가장 가까운 데이터 항목 찾기"""
        if sensor_id not in self._sensor_data or not self._sensor_data[sensor_id]:
            return None
        
        data_list = self._sensor_data[sensor_id]
        
        # 선형 검색으로 가장 가까운 시간 찾기
        best_idx = 0
        best_diff = float('inf')
        
        for i, entry in enumerate(data_list):
            entry_time = self._parse_timestamp(entry["@timestamp"])
            if not entry_time:
                continue
                
            diff = abs((target_time - entry_time).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        
        return data_list[best_idx]
    
    def _update_rack_attributes(self, rack_path, data_entry):
        """랙 객체의 속성 업데이트"""
        if not data_entry:
            return
            
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return
                
            rack_prim = stage.GetPrimAtPath(rack_path)
            if not rack_prim or not rack_prim.IsValid():
                print(f"[netai.timetravel.demo] 랙 객체를 찾을 수 없음: {rack_path}")
                return
            
            # 모든 필드가 있는지 확인하고 기본값 설정
            temp1 = data_entry.get("TEMPERATURE1", 0.0)
            temp2 = data_entry.get("TEMPERATURE", 0.0)
            hum1 = data_entry.get("HUMIDITY1", 0.0)
            hum2 = data_entry.get("HUMIDITY", 0.0)
            
            # 속성 업데이트
            # Cold Aisle 온도
            temp1_attr = rack_prim.CreateAttribute("temperature_cold", Sdf.ValueTypeNames.Float)
            temp1_attr.Set(temp1)
            
            # Hot Aisle 온도
            temp2_attr = rack_prim.CreateAttribute("temperature_hot", Sdf.ValueTypeNames.Float)
            temp2_attr.Set(temp2)
            
            # Cold Aisle 습도
            hum1_attr = rack_prim.CreateAttribute("humidity_cold", Sdf.ValueTypeNames.Float)
            hum1_attr.Set(hum1)
            
            # Hot Aisle 습도
            hum2_attr = rack_prim.CreateAttribute("humidity_hot", Sdf.ValueTypeNames.Float)
            hum2_attr.Set(hum2)
            
            # 메타데이터에도 값 추가
            rack_prim.SetCustomDataByKey("temperature_cold", temp1)
            rack_prim.SetCustomDataByKey("temperature_hot", temp2)
            rack_prim.SetCustomDataByKey("humidity_cold", hum1)
            rack_prim.SetCustomDataByKey("humidity_hot", hum2)
            rack_prim.SetCustomDataByKey("timestamp", data_entry["@timestamp"])
            rack_prim.SetCustomDataByKey("sensor_id", data_entry.get("objId", "unknown"))
            
        except Exception as e:
            print(f"[netai.timetravel.demo] 객체 속성 업데이트 오류 ({rack_path}): {e}")
    
    def _update_all_racks(self):
        """모든 랙의 속성 업데이트"""
        updated_count = 0
        for rack_path, sensor_id in self._rack_to_sensor_map.items():
            # 센서 ID로 데이터 찾기
            if sensor_id in self._sensor_data:
                data_entry = self._find_closest_data_entry(self._current_time, sensor_id)
                if data_entry:
                    self._update_rack_attributes(rack_path, data_entry)
                    updated_count += 1
        
        return updated_count
    
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
                    
                    # 모든 랙 업데이트
                    updated_count = self._update_all_racks()
                    print(f"[netai.timetravel.demo] 업데이트된 랙 수: {updated_count}")
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
    
    def get_rack_count(self):
        """매핑된 랙 수 가져오기"""
        return len(self._rack_to_sensor_map)
    
    def get_sensor_count(self):
        """센서 데이터가 있는 센서 수 가져오기"""
        return len(self._sensor_data)