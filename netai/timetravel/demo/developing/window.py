from pxr import Usd, UsdGeom, Sdf
import omni.usd
import datetime
import time
import omni.timeline
import os
import csv
from datetime import datetime as dt
import random
'''
개선된 LKV (Last Known Value) 방식 TimeController
target_time에 정확히 일치하는 timestamp가 있을 때만 데이터 업데이트
없으면 기존 LKV 값 유지 - 성능 최적화
'''
# Config import
from .config import (
    RACK_SENSOR_MAPPING,
    PREDEFINED_RACK_PATHS,
    POSSIBLE_PATH_PREFIXES,
    SENSOR_DATA_CONFIG,
    USD_ATTRIBUTE_CONFIG,
    LOG_PREFIX,
    DEFAULT_TIME_CONFIG
)

class TimeController:
    """USD Stage의 시간을 관리하고 데이터센터 센서 데이터를 연동하는 컨트롤러 (개선된 LKV 방식)"""
    
    def __init__(self):
        """시간 컨트롤러 초기화"""
        # 현재 USD 컨텍스트 가져오기
        self._usd_context = omni.usd.get_context()
        
        # 타임라인 인터페이스 가져오기
        self._timeline = omni.timeline.get_timeline_interface()
        
        # 시간 관리자 경로 초기화
        self._time_manager_path = USD_ATTRIBUTE_CONFIG["time_manager_path"]
        
        # 기존 데이터 초기화 - 스테이지에서 랙 검색 및 속성 초기화
        self._initialize_rack_attributes()
        
        # 랙 목록 및 매핑 초기화
        self._rack_paths = []
        self._rack_to_sensor_map = {}  # 랙 경로 -> 센서 ID 매핑
        self._load_rack_paths()
        
        # 센서 데이터 초기화
        self._sensor_data = {}  # timestamp 기준으로 그룹화된 센서 데이터
        self._load_sensor_data()
        
        # 센서 데이터 기반으로 시간 범위 초기화
        self._initialize_time_range()
        
        # 재생 상태 초기화
        self._is_playing = False
        self._playback_speed = 1.0
        self._last_update_time = time.time()
        
        # === 단순 LKV 관련 속성들 ===
        self._last_known_values = {}  # 각 센서별 마지막으로 알려진 값 {sensor_id: data_entry}
        self._sensor_last_update_time = {}  # 각 센서별 마지막 업데이트 시간 {sensor_id: datetime}
        
        # 시간 관리자에 baseTime 설정 확인 및 설정
        self._ensure_base_time()
        
        # LKV 시스템 초기화
        self._initialize_lkv_system()
        
        # 초기 데이터 적용
        self._update_stage_time()
        
        # 매핑된 랙 수 출력
        print(f"{LOG_PREFIX} 초기화 완료 (단순 LKV 방식). 매핑된 랙 수: {len(self._rack_to_sensor_map)}, 데이터가 있는 센서 수: {len(self._sensor_data)}")
        
        # 디버깅: 매핑 상태 출력
        self._debug_mapping_status()
    
    def _initialize_lkv_system(self):
        """Last Known Value 시스템 초기화"""
        print(f"{LOG_PREFIX} 단순 LKV 시스템 초기화 중...")
        
        # 모든 센서의 초기 상태를 "데이터 없음"으로 설정
        all_sensor_ids = set()
        for sensors_at_time in self._sensor_data.values():
            all_sensor_ids.update(sensors_at_time.keys())
        
        for sensor_id in all_sensor_ids:
            self._last_known_values[sensor_id] = None
            self._sensor_last_update_time[sensor_id] = None
        
        print(f"{LOG_PREFIX} 단순 LKV 시스템 초기화 완료. 추적 중인 센서: {len(all_sensor_ids)}개")
    
    def _find_latest_data_before_or_at(self, target_time):
        """target_time 이전 또는 같은 시간 중에서 가장 최근 데이터를 가진 타임스탬프들 찾기"""
        if not self._sensor_data:
            return {}
        
        # 모든 타임스탬프를 datetime으로 변환하여 정렬
        timestamp_pairs = []
        for timestamp_str in self._sensor_data.keys():
            timestamp_dt = self._parse_timestamp(timestamp_str)
            if timestamp_dt and timestamp_dt <= target_time:
                timestamp_pairs.append((timestamp_dt, timestamp_str))
        
        if not timestamp_pairs:
            return {}
        
        # 시간순 정렬
        timestamp_pairs.sort()
        
        # 각 센서별로 가장 최근 데이터 찾기
        sensor_latest_data = {}
        
        for timestamp_dt, timestamp_str in timestamp_pairs:
            sensors_at_time = self._sensor_data[timestamp_str]
            
            # 이 시간에 데이터가 있는 센서들의 값을 최신으로 업데이트
            for sensor_id, data_entry in sensors_at_time.items():
                sensor_latest_data[sensor_id] = {
                    'data': data_entry,
                    'timestamp': timestamp_dt,
                    'timestamp_str': timestamp_str
                }
        
        return sensor_latest_data
    
    def _format_target_time_to_sensor_format(self, target_time):
        """target_time을 센서 데이터의 실제 형식에 맞춰 변환 - 밀리초 3자리"""
        # 센서 데이터 형식: 2025-03-27T00:00:01.018Z (밀리초 3자리)
        return target_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    def _find_exact_timestamp_match(self, target_time):
        """정확히 일치하는 타임스탬프 찾기 (디버깅용)"""
        formatted_time = self._format_target_time_to_sensor_format(target_time)
        
        if formatted_time in self._sensor_data:
            return formatted_time
        
        # 다른 가능한 형식들도 시도
        alternative_formats = [
            target_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),  # 마이크로초 6자리
            target_time.strftime("%Y-%m-%dT%H:%M:%SZ"),      # 밀리초 없음
            target_time.strftime("%Y-%m-%dT%H:%M:%S")        # Z 없음
        ]
        
        for alt_format in alternative_formats:
            if alt_format in self._sensor_data:
                return alt_format
        
        return None
    
    def _update_lkv_for_target_time(self, target_time):
        """target_time에 정확히 일치하는 데이터가 있으면 LKV 업데이트 (소수점 2자리 방식)"""
        # target_time을 소수점 아래 2자리 형식으로 변환
        target_time_str = target_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
        
        # 정확한 타임스탬프 매치 확인 - O(1) 해시 검색
        if target_time_str in self._sensor_data:
            # 해당 시간의 센서 데이터 가져오기
            sensors_at_time = self._sensor_data[target_time_str]
            updated_sensors = []
            
            # 해당 시간에 데이터가 있는 센서들만 LKV 업데이트
            for sensor_id, data_entry in sensors_at_time.items():
                self._last_known_values[sensor_id] = data_entry
                self._sensor_last_update_time[sensor_id] = target_time
                updated_sensors.append(sensor_id)
            
            if updated_sensors:
                print(f"{LOG_PREFIX} LKV 업데이트 ({target_time_str}): {len(updated_sensors)}개 센서 - {updated_sensors[:5]}{'...' if len(updated_sensors) > 5 else ''}")
        else:
            # 해당 시간에 데이터가 없으면 LKV는 변경하지 않음
            print(f"{LOG_PREFIX} 타임스탬프 데이터 없음 ({target_time_str}): LKV 유지")
    
    
    def _update_all_racks_with_lkv(self):
        """LKV를 사용하여 모든 랙의 속성 업데이트"""
        updated_count = 0
        missing_count = 0
        
        # 모든 랙 경로 순회
        for rack_path in self._rack_paths:
            # 센서 ID 확인
            sensor_id = self.get_sensor_id_for_rack(rack_path)
            
            if sensor_id and sensor_id in self._last_known_values:
                # 해당 센서의 LKV 가져오기
                data_entry = self._last_known_values[sensor_id]
                last_update_time = self._sensor_last_update_time[sensor_id]
                
                if data_entry and last_update_time:
                    # LKV가 있는 경우
                    self._update_rack_attributes(rack_path, data_entry)
                    updated_count += 1
                else:
                    # LKV가 없는 경우 (아직 데이터가 나타나지 않음)
                    self._update_rack_attributes(rack_path, None)
                    missing_count += 1
            else:
                # 센서 ID가 없거나 추적되지 않는 센서
                self._update_rack_attributes(rack_path, None)
                missing_count += 1
        
        # 결과 로그 (변경사항이 있을 때만)
        if updated_count > 0 or missing_count > 0:
            print(f"{LOG_PREFIX} 랙 업데이트 (단순 LKV): {updated_count}개 업데이트, {missing_count}개 데이터 없음")
        
        return updated_count
    
    # 기존 메서드들 (변경 없음)
    def _initialize_rack_attributes(self):
        """스테이지에서 모든 랙을 검색하고 속성을 초기화"""
        print(f"{LOG_PREFIX} 기존 랙 속성 초기화 중...")
        
        stage = self._usd_context.get_stage()
        if not stage:
            print(f"{LOG_PREFIX} 스테이지를 찾을 수 없어 초기화를 건너뜁니다.")
            return
        
        # 가능한 랙 경로 패턴
        rack_patterns = [
            "/Root/datacenter/RACK_*",
            "/World/Root/datacenter/RACK_*"
        ]
        
        for pattern in rack_patterns:
            # 패턴과 일치하는 모든 프림 찾기
            try:
                # USD는 직접적인 글로브 패턴을 지원하지 않아 단순 방법으로 처리
                base_path = pattern.split("RACK_")[0]  # "/Root/datacenter/" 또는 "/World/Root/datacenter/"
                
                if not stage.GetPrimAtPath(base_path).IsValid():
                    continue  # 기본 경로가 없으면 다음 패턴으로
                
                # 모든 자식 프림 탐색
                datacenter_prim = stage.GetPrimAtPath(base_path)
                if not datacenter_prim.IsValid():
                    continue
                
                # 모든 자식 프림 중 RACK_으로 시작하는 이름 찾기
                initialized_count = 0
                for child_prim in datacenter_prim.GetChildren():
                    child_name = child_prim.GetName()
                    if child_name.startswith("RACK_"):
                        rack_path = f"{base_path}{child_name}"
                        self._reset_rack_attributes(rack_path)
                        initialized_count += 1
                
                if initialized_count > 0:
                    print(f"{LOG_PREFIX} {base_path} 경로에서 {initialized_count}개 랙 속성 초기화 완료")
                
            except Exception as e:
                print(f"{LOG_PREFIX} 랙 검색 중 오류: {e}")
    
    def _reset_rack_attributes(self, rack_path):
        """특정 랙의 속성을 초기화"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return
                
            rack_prim = stage.GetPrimAtPath(rack_path)
            if not rack_prim or not rack_prim.IsValid():
                return
            
            # 기존 속성 초기화
            temp_attrs = [
                USD_ATTRIBUTE_CONFIG["rack_attributes"]["temperature_cold"],
                USD_ATTRIBUTE_CONFIG["rack_attributes"]["temperature_hot"],
                USD_ATTRIBUTE_CONFIG["rack_attributes"]["humidity_cold"],
                USD_ATTRIBUTE_CONFIG["rack_attributes"]["humidity_hot"]
            ]
            
            for attr_name in temp_attrs:
                if rack_prim.HasAttribute(attr_name):
                    # 기존 속성이 있으면 초기화
                    rack_prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float).Set(float('nan'))
            
            # 메타데이터 초기화
            metadata_keys = USD_ATTRIBUTE_CONFIG["metadata_keys"]
            
            for key in metadata_keys:
                rack_prim.SetCustomDataByKey(key, "N/A")
            
            # 초기화 표시
            rack_prim.SetCustomDataByKey("initialized", f"{datetime.datetime.now()}")
            
        except Exception as e:
            print(f"{LOG_PREFIX} 랙 속성 초기화 오류 ({rack_path}): {e}")
    
    def _load_rack_paths(self):
        """랙 경로 목록 로드"""
        try:
            rack_dir_path = os.path.join(os.path.dirname(__file__), "rack_directory.txt")
            rack_map_path = os.path.join(os.path.dirname(__file__), "rack_sensor_map.txt")
            
            # 경로 확인 로그
            print(f"{LOG_PREFIX} 랙 디렉토리 파일 경로: {rack_dir_path}")
            print(f"{LOG_PREFIX} 현재 작업 디렉토리: {os.getcwd()}")
            
            if os.path.exists(rack_dir_path):
                with open(rack_dir_path, 'r') as file:
                    content = file.read().strip()
                    self._rack_paths = content.split()
                
                print(f"{LOG_PREFIX} 로드된 랙 수: {len(self._rack_paths)}")
                if self._rack_paths:
                    print(f"{LOG_PREFIX} 첫 번째 랙 경로 예시: {self._rack_paths[0]}")
                
                # USD 스테이지에서 실제 경로 확인
                stage = self._usd_context.get_stage()
                if stage:
                    # 경로 중 하나가 실제로 존재하는지 확인
                    for path in self._rack_paths[:5]:  # 처음 5개만 확인
                        prim = stage.GetPrimAtPath(path)
                        print(f"{LOG_PREFIX} 경로 확인: {path} - 존재: {prim.IsValid() if prim else False}")
                
                # 랙-센서 매핑 파일이 있는지 확인
                if os.path.exists(rack_map_path):
                    self._load_rack_sensor_map(rack_map_path)
                else:
                    print(f"{LOG_PREFIX} 랙-센서 매핑 파일이 없어 정의된 매핑을 생성합니다.")
                    # 정의된 매핑 생성
                    self._create_predefined_mapping()
            else:
                print(f"{LOG_PREFIX} 랙 디렉토리 파일을 찾을 수 없음: {rack_dir_path}")
                
                # 테스트용 랙 경로 생성
                self._create_test_rack_paths()
        except Exception as e:
            print(f"{LOG_PREFIX} 랙 경로 로드 오류: {e}")
            
            # 오류 발생 시 테스트 데이터 생성
            self._create_test_rack_paths()
    
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
            
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 로드 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        except Exception as e:
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 로드 오류: {e}")
            # 오류 시 정의된 매핑 생성
            self._create_predefined_mapping()
    
    def _create_test_rack_paths(self):
        """정의된 랙 경로를 기반으로 실제 랙 경로 찾기"""
        print(f"{LOG_PREFIX} 정의된 랙 경로 검색 중...")
        
        # USD 스테이지에서 실제 존재하는 경로 찾기
        stage = self._usd_context.get_stage()
        real_paths = []
        
        if stage:
            for defined_path in PREDEFINED_RACK_PATHS:
                # 가능한 경로 변형들
                possible_paths = [prefix + defined_path for prefix in POSSIBLE_PATH_PREFIXES]
                
                # 각 경로 변형 시도
                for path in possible_paths:
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        real_paths.append(path)
                        print(f"{LOG_PREFIX} 실제 랙 찾음: {path}")
                        break  # 첫 번째로 찾은 유효한 경로만 사용
            
            if real_paths:
                self._rack_paths = real_paths
                print(f"{LOG_PREFIX} 실제 랙 경로 {len(real_paths)}개 찾음")
            else:
                # 실제 경로를 찾지 못했으면 기본 경로 사용
                self._rack_paths = [POSSIBLE_PATH_PREFIXES[1] + path for path in PREDEFINED_RACK_PATHS]  # /Root 접두사 사용
                print(f"{LOG_PREFIX} 실제 랙 경로를 찾지 못해 기본 경로 사용")
        else:
            # 스테이지가 없으면 기본 경로 사용
            self._rack_paths = [POSSIBLE_PATH_PREFIXES[1] + path for path in PREDEFINED_RACK_PATHS]  # /Root 접두사 사용
            print(f"{LOG_PREFIX} 스테이지 없음, 기본 랙 경로 사용")
            
        # 정의된 매핑 생성
        self._create_predefined_mapping()
        
    def _create_predefined_mapping(self):
        """정의된 랙-센서 매핑 생성"""
        # Config에서 정의된 랙-센서 매핑 사용
        predefined_mapping = RACK_SENSOR_MAPPING
        
        # 이전 매핑 초기화
        self._rack_to_sensor_map.clear()
        
        # USD 스테이지에서 실제 존재하는 랙 경로 확인 및 매핑
        stage = self._usd_context.get_stage()
        mapped_count = 0
        
        for defined_path, sensor_id in predefined_mapping.items():
            # 가능한 경로 변형들
            possible_paths = [prefix + defined_path for prefix in POSSIBLE_PATH_PREFIXES]
            
            # 각 경로 변형 시도
            for path in possible_paths:
                if stage:
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        self._rack_to_sensor_map[path] = sensor_id
                        mapped_count += 1
                        print(f"{LOG_PREFIX} 매핑 성공: {path} -> {sensor_id}")
                        break  # 첫 번째로 찾은 유효한 경로만 사용
                else:
                    # 스테이지가 없는 경우 모든 경로를 추가
                    self._rack_to_sensor_map[path] = sensor_id
                    mapped_count += 1
                    break
        
        print(f"{LOG_PREFIX} 정의된 랙-센서 매핑 생성 완료. 매핑된 랙 수: {mapped_count}")
        
        # 센서 데이터가 있는 센서 ID와 매핑 비교
        available_sensors = set()
        for sensors_at_time in self._sensor_data.values():
            available_sensors.update(sensors_at_time.keys())
        mapped_sensors = set(self._rack_to_sensor_map.values())
        
        print(f"{LOG_PREFIX} 사용 가능한 센서 ID: {sorted(available_sensors)}")
        print(f"{LOG_PREFIX} 매핑된 센서 ID: {sorted(mapped_sensors)}")
        
        # 매핑되었지만 데이터가 없는 센서
        missing_data = mapped_sensors - available_sensors
        if missing_data:
            print(f"{LOG_PREFIX} 데이터가 없는 센서 ID: {sorted(missing_data)}")
        
        # 데이터는 있지만 매핑되지 않은 센서
        unmapped_sensors = available_sensors - mapped_sensors
        if unmapped_sensors:
            print(f"{LOG_PREFIX} 매핑되지 않은 센서 ID: {sorted(unmapped_sensors)}")
        
        # 생성된 매핑을 파일로 저장
        if mapped_count > 0:
            self.save_rack_sensor_map()
                
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
                    
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 저장 완료: {file_path}")
            return True
        except Exception as e:
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 저장 오류: {e}")
            return False
    
    def _load_sensor_data(self):
        """센서 데이터 CSV 파일 로드 - timestamp 기준으로 그룹화 (소수점 2자리로 정규화)"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), SENSOR_DATA_CONFIG["csv_file"])
            
            with open(csv_path, 'r') as file:
                reader = csv.DictReader(file)
                data_list = list(reader)
            
            # timestamp 기준으로 데이터 그룹화
            for entry in data_list:
                # 타임스탬프 가져오기
                timestamp = entry.get(SENSOR_DATA_CONFIG["timestamp_column"])
                if not timestamp:
                    continue  # 타임스탬프가 없으면 건너뜀기
                
                # 타임스탬프를 소수점 2자리로 정규화
                normalized_timestamp = self._normalize_timestamp_to_2_decimals(timestamp)
                if not normalized_timestamp:
                    continue
                
                # objId 가져오기
                obj_id = entry.get(SENSOR_DATA_CONFIG["obj_id_column"], "unknown")
                
                # 숫자 형식으로 변환
                temp_columns = SENSOR_DATA_CONFIG["temperature_columns"]
                hum_columns = SENSOR_DATA_CONFIG["humidity_columns"]
                
                for field in [temp_columns["cold"], temp_columns["hot"], hum_columns["cold"], hum_columns["hot"]]:
                    if field in entry:
                        try:
                            entry[field] = float(entry[field])
                        except (ValueError, TypeError):
                            entry[field] = 0.0  # 변환 실패 시 기본값
                
                # 정규화된 timestamp를 key로 사용하여 데이터 저장
                if normalized_timestamp not in self._sensor_data:
                    self._sensor_data[normalized_timestamp] = {}  # 해당 시간의 모든 센서 데이터
                
                # 해당 시간에 센서 ID별 데이터 저장
                self._sensor_data[normalized_timestamp][obj_id] = entry
            
            # 결과 요약
            total_timestamps = len(self._sensor_data)
            total_entries = sum(len(sensors) for sensors in self._sensor_data.values())
            unique_sensors = set()
            for sensors in self._sensor_data.values():
                unique_sensors.update(sensors.keys())
            
            print(f"{LOG_PREFIX} 로드된 센서 데이터 (2자리 정규화): {total_entries}개 데이터, {total_timestamps}개 타임스탬프, {len(unique_sensors)}개 센서")
            
            # 센서 ID 목록 출력
            sensor_ids = sorted(unique_sensors)
            print(f"{LOG_PREFIX} 센서 ID: {', '.join(sensor_ids[:10])}{'...' if len(sensor_ids) > 10 else ''}")
            
            # 시간 범위 출력 (정규화된 형식)
            if self._sensor_data:
                timestamps = sorted(self._sensor_data.keys())
                print(f"{LOG_PREFIX} 시간 범위 (2자리): {timestamps[0]} ~ {timestamps[-1]}")
            
        except Exception as e:
            print(f"{LOG_PREFIX} 센서 데이터 로드 오류: {e}")
            self._sensor_data = {}
    
    def _normalize_timestamp_to_2_decimals(self, timestamp_str):
        """타임스탬프를 소수점 아래 2자리로 정규화"""
        try:
            # 원본 타임스탬프 파싱
            if "." in timestamp_str and timestamp_str.endswith("Z"):
                # 2025-03-27T00:00:01.018Z → datetime으로 파싱
                dt_obj = self._parse_timestamp(timestamp_str)
                if dt_obj:
                    # 소수점 아래 2자리로 재포맷
                    # %f는 마이크로초 6자리 → 앞 2자리만 사용
                    normalized = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
                    return normalized
            elif timestamp_str.endswith("Z"):
                # 밀리초 없는 경우: 2025-03-27T00:00:01Z → 2025-03-27T00:00:01.00Z
                return timestamp_str[:-1] + ".00Z"
            else:
                # Z 없는 경우
                return timestamp_str + ".00Z"
                
        except Exception as e:
            print(f"{LOG_PREFIX} 타임스탬프 정규화 오류 ({timestamp_str}): {e}")
            return None
    
    def _initialize_time_range(self):
        """센서 데이터 기반으로 시간 범위 초기화"""
        try:
            # timestamp key들에서 최초/최후 타임스탬프 찾기
            if self._sensor_data:
                timestamps = sorted(self._sensor_data.keys())
                first_timestamp = timestamps[0]
                last_timestamp = timestamps[-1]
                
                # 타임스탬프 파싱
                self._start_time = self._parse_timestamp(first_timestamp)
                self._end_time = self._parse_timestamp(last_timestamp)
                self._current_time = self._start_time
                
                print(f"{LOG_PREFIX} 시간 범위 설정: {self._start_time} ~ {self._end_time}")
            else:
                raise ValueError("센서 데이터가 없습니다")
        except Exception as e:
            print(f"{LOG_PREFIX} 시간 범위 초기화 오류: {e}")
            # 기본값 설정
            default_start = dt.strptime(DEFAULT_TIME_CONFIG["default_start"], "%Y-%m-%dT%H:%M:%S")
            default_end = dt.strptime(DEFAULT_TIME_CONFIG["default_end"], "%Y-%m-%dT%H:%M:%S")
            self._start_time = default_start
            self._end_time = default_end
            self._current_time = self._start_time
            print(f"{LOG_PREFIX} 기본 시간 범위로 설정: {self._start_time} ~ {self._end_time}")
    
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
            print(f"{LOG_PREFIX} 타임스탬프 파싱 오류: {e}")
            return None
    
    def _ensure_base_time(self):
        """시간 관리자가 존재하는지 확인하고, 없으면 생성하고 baseTime 설정"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                print(f"{LOG_PREFIX} USD Stage를 찾을 수 없음")
                return
                
            # TimeManager가 존재하는지 확인
            time_prim = stage.GetPrimAtPath(self._time_manager_path)
            
            # TimeManager가 없으면 생성
            if not time_prim or not time_prim.IsValid():
                print(f"{LOG_PREFIX} TimeManager가 없음. 생성 중: {self._time_manager_path}")
                
                # 경로 분리 및 부모 경로 확인
                parent_path = os.path.dirname(self._time_manager_path)
                if parent_path != "/":
                    parent_prim = stage.GetPrimAtPath(parent_path)
                    if not parent_prim or not parent_prim.IsValid():
                        # 부모 경로가 없으면 생성
                        print(f"{LOG_PREFIX} 부모 경로 생성 중: {parent_path}")
                        parent_prim = UsdGeom.Xform.Define(stage, parent_path)
                
                # TimeManager 생성
                time_prim = UsdGeom.Xform.Define(stage, self._time_manager_path)
                
                # TimeManager 설명 추가
                time_prim.SetCustomDataByKey("description", "시간 관리 및 동기화를 위한 객체")
                time_prim.SetCustomDataByKey("created", dt.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                
                print(f"{LOG_PREFIX} TimeManager 생성 완료: {self._time_manager_path}")
            
            # baseTime이 없으면 설정
            if not time_prim.GetCustomDataByKey("baseTime"):
                base_time_str = DEFAULT_TIME_CONFIG["base_time"]
                time_prim.SetCustomDataByKey("baseTime", base_time_str)
                print(f"{LOG_PREFIX} baseTime 설정: {base_time_str}")
            
            # 현재 시간도 초기화
            current_time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
            time_prim.SetCustomDataByKey("currentTime", current_time_str)
            
            return True
            
        except Exception as e:
            print(f"{LOG_PREFIX} TimeManager 초기화 오류: {e}")
            return False
    
    def _update_rack_attributes(self, rack_path, data_entry):
        """랙 객체의 속성 업데이트"""
        if not data_entry:
            # 데이터가 없으면 속성을 비워두거나 초기화합니다
            try:
                stage = self._usd_context.get_stage()
                if not stage:
                    return
                    
                rack_prim = stage.GetPrimAtPath(rack_path)
                if not rack_prim or not rack_prim.IsValid():
                    return
                
                # 기존 속성이 있으면 N/A 값으로 표시
                attr_config = USD_ATTRIBUTE_CONFIG["rack_attributes"]
                if rack_prim.HasAttribute(attr_config["temperature_cold"]):
                    rack_prim.CreateAttribute(attr_config["temperature_cold"], Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute(attr_config["temperature_hot"]):
                    rack_prim.CreateAttribute(attr_config["temperature_hot"], Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute(attr_config["humidity_cold"]):
                    rack_prim.CreateAttribute(attr_config["humidity_cold"], Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute(attr_config["humidity_hot"]):
                    rack_prim.CreateAttribute(attr_config["humidity_hot"], Sdf.ValueTypeNames.Float).Set(float('nan'))
                
                # 메타데이터도 초기화
                rack_prim.SetCustomDataByKey("temperature_cold", "N/A")
                rack_prim.SetCustomDataByKey("temperature_hot", "N/A")
                rack_prim.SetCustomDataByKey("humidity_cold", "N/A")
                rack_prim.SetCustomDataByKey("humidity_hot", "N/A")
                rack_prim.SetCustomDataByKey("timestamp", "N/A")
                rack_prim.SetCustomDataByKey("sensor_id", "None")
                
            except Exception as e:
                print(f"{LOG_PREFIX} 객체 속성 초기화 오류 ({rack_path}): {e}")
            return
            
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return
                
            rack_prim = stage.GetPrimAtPath(rack_path)
            if not rack_prim or not rack_prim.IsValid():
                print(f"{LOG_PREFIX} 랙 객체를 찾을 수 없음: {rack_path}")
                return
            
            # 모든 필드가 있는지 확인하고 기본값 설정
            temp_columns = SENSOR_DATA_CONFIG["temperature_columns"]
            hum_columns = SENSOR_DATA_CONFIG["humidity_columns"]
            
            temp1 = data_entry.get(temp_columns["cold"], 0.0)
            temp2 = data_entry.get(temp_columns["hot"], 0.0)
            hum1 = data_entry.get(hum_columns["cold"], 0.0)
            hum2 = data_entry.get(hum_columns["hot"], 0.0)
            
            # 유효한 값인지 확인
            try:
                temp1 = float(temp1)
                temp2 = float(temp2)
                hum1 = float(hum1)
                hum2 = float(hum2)
            except (ValueError, TypeError):
                print(f"{LOG_PREFIX} 유효하지 않은 데이터 값 - 기본값 사용")
                temp1 = temp2 = hum1 = hum2 = 0.0
            
            # 속성 업데이트
            attr_config = USD_ATTRIBUTE_CONFIG["rack_attributes"]
            
            # Cold Aisle 온도
            temp1_attr = rack_prim.CreateAttribute(attr_config["temperature_cold"], Sdf.ValueTypeNames.Float)
            temp1_attr.Set(temp1)
            
            # Hot Aisle 온도
            temp2_attr = rack_prim.CreateAttribute(attr_config["temperature_hot"], Sdf.ValueTypeNames.Float)
            temp2_attr.Set(temp2)
            
            # Cold Aisle 습도
            hum1_attr = rack_prim.CreateAttribute(attr_config["humidity_cold"], Sdf.ValueTypeNames.Float)
            hum1_attr.Set(hum1)
            
            # Hot Aisle 습도
            hum2_attr = rack_prim.CreateAttribute(attr_config["humidity_hot"], Sdf.ValueTypeNames.Float)
            hum2_attr.Set(hum2)
            
            # 메타데이터에도 값 추가
            rack_prim.SetCustomDataByKey("temperature_cold", temp1)
            rack_prim.SetCustomDataByKey("temperature_hot", temp2)
            rack_prim.SetCustomDataByKey("humidity_cold", hum1)
            rack_prim.SetCustomDataByKey("humidity_hot", hum2)
            rack_prim.SetCustomDataByKey("timestamp", data_entry.get(SENSOR_DATA_CONFIG["timestamp_column"], "Unknown"))
            rack_prim.SetCustomDataByKey("sensor_id", data_entry.get(SENSOR_DATA_CONFIG["obj_id_column"], "Unknown"))
            
            # 데이터 출처 명시적으로 기록
            rack_prim.SetCustomDataByKey("data_source", "sensor_data_simple_lkv")
            
        except Exception as e:
            print(f"{LOG_PREFIX} 객체 속성 업데이트 오류 ({rack_path}): {e}")
    
    def get_sensor_id_for_rack(self, rack_path):
        """특정 랙에 매핑된 센서 ID 가져오기"""
        # 직접 매핑 확인
        if rack_path in self._rack_to_sensor_map:
            return self._rack_to_sensor_map.get(rack_path)
        
        # 경로 검색 시도
        # 1. 끝부분 비교
        rack_name = rack_path.split('/')[-1] if '/' in rack_path else rack_path
        for path, sensor_id in self._rack_to_sensor_map.items():
            if path.endswith('/' + rack_name):
                return sensor_id
        
        # 2. 몇 가지 경로 변형 시도
        variations = []
        
        # '/World' 접두사가 있으면 제거
        if rack_path.startswith('/World/'):
            variations.append(rack_path[6:])  # '/World/' 제거
        # '/World' 접두사가 없으면 추가
        elif not rack_path.startswith('/World'):
            variations.append('/World' + rack_path)
        
        # 각 변형에 대해 매핑 확인
        for var_path in variations:
            if var_path in self._rack_to_sensor_map:
                return self._rack_to_sensor_map.get(var_path)
        
        # 매핑을 찾지 못한 경우
        return None
    
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
            print(f"{LOG_PREFIX} 시간 변환 오류: {e}")
            return 0.0
    
    def _update_stage_time(self):
        """현재 시간에 따라 USD Stage 시간 업데이트 및 센서 데이터 적용 (단순 LKV 방식)"""
        # 단순 LKV 시스템으로 현재 시간의 데이터 확인 및 업데이트
        self._update_lkv_for_target_time(self._current_time)
        
        # 날짜/시간에서 타임코드 값(실수)으로 직접 변환
        timecode_value = self._datetime_to_timecode_value(self._current_time)
        
        # 타임라인 인터페이스를 통한 시간 설정
        try:
            self._timeline.set_current_time(timecode_value)
            print(f"{LOG_PREFIX} 타임라인 시간 설정: {timecode_value}")
        except Exception as e:
            print(f"{LOG_PREFIX} 타임라인 업데이트 오류: {e}")
        
        # 시간 관리자 업데이트 (메타데이터)
        try:
            stage = self._usd_context.get_stage()
            if stage:
                time_prim = stage.GetPrimAtPath(self._time_manager_path)
                if time_prim and time_prim.IsValid():
                    # 소수점 둘째 자리까지 포함한 시간 포맷 사용
                    time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
                    time_prim.SetCustomDataByKey("currentTime", time_str)
                    time_prim.SetCustomDataByKey("lastUpdated", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                    
                    # 단순 LKV를 사용하여 모든 랙 업데이트
                    updated_count = self._update_all_racks_with_lkv()
                    print(f"{LOG_PREFIX} 업데이트된 랙 수 (단순 LKV): {updated_count}")
        except Exception as e:
            print(f"{LOG_PREFIX} 시간 관리자 업데이트 오류: {e}")
    
    # 시간 제어 메서드들 (단순화됨 - LKV 상태 리셋 로직 제거)
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
        """현재 시간 설정 (단순 LKV 방식)"""
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
        """애니메이션을 위한 프레임별 업데이트 함수 (단순 LKV 방식)"""
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
        
        # Stage 업데이트 (단순 LKV 방식 적용)
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
        """현재 시간에 해당하는 센서 데이터 가져오기 (단순 LKV 방식)"""
        sensor_data_map = {}
        
        # LKV에서 현재 유효한 센서 데이터 가져오기
        for sensor_id, data_entry in self._last_known_values.items():
            if data_entry and self._sensor_last_update_time.get(sensor_id):
                sensor_data_map[sensor_id] = data_entry
        
        return sensor_data_map
    
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
        unique_sensors = set()
        for sensors_at_time in self._sensor_data.values():
            unique_sensors.update(sensors_at_time.keys())
        return len(unique_sensors)
    
    def get_lkv_status(self):
        """LKV 상태 정보 가져오기 (디버깅용)"""
        status = {
            "total_sensors": len(self._last_known_values),
            "sensors_with_data": sum(1 for v in self._last_known_values.values() if v is not None),
            "total_timestamps": len(self._sensor_data)
        }
        return status
    
    def on_shutdown(self):
        """익스텐션 종료 시 정리 작업"""
        print(f"{LOG_PREFIX} 컨트롤러 종료 중...")
        
        # 모든 랙 속성 초기화
        try:
            self._clear_all_rack_attributes()
        except Exception as e:
            print(f"{LOG_PREFIX} 종료 시 정리 작업 오류: {e}")
    
    def _clear_all_rack_attributes(self):
        """모든 랙 속성 초기화 (종료 시 호출)"""
        print(f"{LOG_PREFIX} 모든 랙 속성 초기화 중...")
        
        for rack_path in self._rack_paths:
            self._reset_rack_attributes(rack_path)
    
    def _debug_mapping_status(self):
        """매핑 상태 디버깅 정보 출력 - 타임스탬프 형식 확인 추가"""
        print(f"{LOG_PREFIX} === 매핑 상태 디버깅 (단순 LKV 방식) ===")
        print(f"{LOG_PREFIX} 총 랙 경로 수: {len(self._rack_paths)}")
        print(f"{LOG_PREFIX} 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        print(f"{LOG_PREFIX} 센서 데이터 타임스탬프 수: {len(self._sensor_data)}")
        print(f"{LOG_PREFIX} LKV 추적 센서 수: {len(self._last_known_values)}")
        
        # 실제 타임스탬프 형식 확인
        if self._sensor_data:
            sample_timestamps = list(self._sensor_data.keys())[:5]
            print(f"{LOG_PREFIX} 실제 센서 데이터 타임스탬프 형식:")
            for ts in sample_timestamps:
                sensor_count = len(self._sensor_data[ts])
                print(f"{LOG_PREFIX}   '{ts}' ({sensor_count}개 센서)")
            
            # 타임스탬프 길이 분석
            ts_lengths = [len(ts) for ts in sample_timestamps]
            print(f"{LOG_PREFIX} 타임스탬프 길이들: {ts_lengths}")
            
            # 소수점 부분 분석
            for ts in sample_timestamps[:3]:
                if '.' in ts:
                    decimal_part = ts.split('.')[1].replace('Z', '')
                    print(f"{LOG_PREFIX} 소수점 부분: '{decimal_part}' (길이: {len(decimal_part)})")
        
        # 현재 시간으로 테스트 포맷
        current_time = self._current_time
        test_format = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        print(f"{LOG_PREFIX} 현재 시간 테스트 포맷: '{test_format}'")
        print(f"{LOG_PREFIX} 테스트 포맷이 실제 데이터에 존재: {test_format in self._sensor_data}")
        
        # 사용 가능한 센서 ID 확인
        available_sensors = set()
        for sensors_at_time in self._sensor_data.values():
            available_sensors.update(sensors_at_time.keys())
        print(f"{LOG_PREFIX} 사용 가능한 센서 ID: {sorted(available_sensors)}")
        
        # 매핑 상세 정보
        print(f"{LOG_PREFIX} 랙-센서 매핑:")
        for rack_path, sensor_id in list(self._rack_to_sensor_map.items())[:5]:  # 처음 5개만
            has_data = sensor_id in available_sensors
            print(f"{LOG_PREFIX}   {rack_path} -> {sensor_id} (데이터: {'O' if has_data else 'X'})")
        
        if len(self._rack_to_sensor_map) > 5:
            print(f"{LOG_PREFIX}   ... (총 {len(self._rack_to_sensor_map)}개 매핑)")
        
        # LKV 상태
        lkv_status = self.get_lkv_status()
        print(f"{LOG_PREFIX} LKV 상태: {lkv_status}")
        
        # 첫 번째 타임스탬프의 데이터 확인
        if self._sensor_data:
            first_timestamp = sorted(self._sensor_data.keys())[0]
            sensors_at_first_time = self._sensor_data[first_timestamp]
            print(f"{LOG_PREFIX} 첫 번째 타임스탬프 ({first_timestamp})의 센서: {list(sensors_at_first_time.keys())[:5]}")
        
        # *** 추가: 실제 타임스탬프와 포맷 비교 ***
        if self._sensor_data and current_time:
            print(f"{LOG_PREFIX} === 타임스탬프 형식 비교 ===")
            actual_ts = list(self._sensor_data.keys())[0]
            formatted_ts = test_format
            
            print(f"{LOG_PREFIX} 실제 데이터:   '{actual_ts}'")
            print(f"{LOG_PREFIX} 포맷된 시간: '{formatted_ts}'")
            print(f"{LOG_PREFIX} 길이 비교: 실제={len(actual_ts)}, 포맷={len(formatted_ts)}")
            
            if '.' in actual_ts and '.' in formatted_ts:
                actual_decimal = actual_ts.split('.')[1].replace('Z', '')
                formatted_decimal = formatted_ts.split('.')[1].replace('Z', '')
                print(f"{LOG_PREFIX} 소수점 부분 비교:")
                print(f"{LOG_PREFIX}   실제: '{actual_decimal}' (길이: {len(actual_decimal)})")
                print(f"{LOG_PREFIX}   포맷: '{formatted_decimal}' (길이: {len(formatted_decimal)})")
    
    # 단순 LKV 관련 유틸리티 메서드
    def reset_lkv_state(self):
        """LKV 상태를 완전히 리셋 (수동 호출용)"""
        print(f"{LOG_PREFIX} LKV 상태 수동 리셋")
        for sensor_id in self._last_known_values:
            self._last_known_values[sensor_id] = None
            self._sensor_last_update_time[sensor_id] = None
        
        # 현재 시간 기준으로 다시 업데이트
        self._update_stage_time()
    
    def get_sensor_lkv_info(self, sensor_id):
        """특정 센서의 LKV 정보 가져오기 (디버깅용)"""
        if sensor_id in self._last_known_values:
            return {
                "has_data": self._last_known_values[sensor_id] is not None,
                "last_update": self._sensor_last_update_time[sensor_id],
                "data": self._last_known_values[sensor_id]
            }
        return None
    
    def get_available_timestamps(self):
        """사용 가능한 모든 타임스탬프 목록 가져오기 (정렬됨)"""
        return sorted(self._sensor_data.keys())
    
    def has_data_at_time(self, target_time):
        """특정 시간에 데이터가 있는지 확인 (소수점 2자리 방식)"""
        target_time_str = target_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
        return target_time_str in self._sensor_data
    
    def get_sensors_at_time(self, target_time):
        """특정 시간의 센서 데이터 가져오기 (소수점 2자리 방식)"""
        target_time_str = target_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
        return self._sensor_data.get(target_time_str, {})
    
    def debug_lkv_state_at_time(self, target_time):
        """특정 시간의 LKV 상태 디버깅 (소수점 2자리 방식)"""
        print(f"{LOG_PREFIX} === LKV 상태 디버깅 ({target_time}) ===")
        
        # 타임스탬프 포맷 확인 (소수점 2자리)
        target_time_str = target_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z"
        has_exact_data = target_time_str in self._sensor_data
        
        print(f"{LOG_PREFIX} 포맷된 시간 (2자리): {target_time_str}")
        print(f"{LOG_PREFIX} 정확한 데이터 존재: {has_exact_data}")
        
        if has_exact_data:
            sensor_count = len(self._sensor_data[target_time_str])
            print(f"{LOG_PREFIX} 해당 시간 센서 수: {sensor_count}개")
        
        # 실제 센서 데이터의 타임스탬프 형식 샘플 확인
        if self._sensor_data:
            sample_timestamps = list(self._sensor_data.keys())[:3]
            print(f"{LOG_PREFIX} 실제 센서 데이터 타임스탬프 샘플 (2자리 정규화됨):")
            for ts in sample_timestamps:
                sensor_count = len(self._sensor_data[ts])
                print(f"{LOG_PREFIX}   {ts} ({sensor_count}개 센서)")
        
        # 현재 LKV 상태
        lkv_count = sum(1 for v in self._last_known_values.values() if v is not None)
        print(f"{LOG_PREFIX} 현재 LKV 상태: {lkv_count}개 센서에 데이터 있음")
        
        # 매핑된 랙 중 LKV가 있는 것들
        mapped_with_data = 0
        for rack_path, sensor_id in self._rack_to_sensor_map.items():
            if sensor_id in self._last_known_values and self._last_known_values[sensor_id] is not None:
                mapped_with_data += 1
        
        print(f"{LOG_PREFIX} 매핑된 랙 중 데이터가 있는 랙: {mapped_with_data}/{len(self._rack_to_sensor_map)}개")
        
        return has_exact_data