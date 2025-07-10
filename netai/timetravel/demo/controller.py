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
정확한 timestamp 매칭 + last known value 방식으로 센서 데이터 업데이트
'''
# Config import
from .config import (
    RACK_SENSOR_MAPPING,
    PREDEFINED_RACK_PATHS,
    POSSIBLE_PATH_PREFIXES,
    SENSOR_DATA_CONFIG,
    USD_ATTRIBUTE_CONFIG,
    LOG_PREFIX,
    DEFAULT_TIME_CONFIG,
    objid_to_airrack,
)

def update_dynamic_colormap(temperature, color_rgba_cl,prefix_prim_path):
    """
    Updates the colormap based on the given temperature.
    
    The temperature is assumed to be in °C and clamped between 15°C (cold) and 30°C (hot).
    It interpolates between the static cold and hot colormaps.
    
    Static colormaps (flat RGBA arrays) are defined as follows:
    
      Static Cold:
         flat_rgba_cold = [
             0.943, 0.961, 0.961, 0.7, 
             0.569, 0.906, 0.271, 1.0,
             0.258, 0.816, 0.915, 0.9, 
             0.085, 0.373, 0.876, 1.0   
         ]
    
      Static Hot:
         flat_rgba_hot = [
             0.943, 0.961, 0.961, 0.7,  
             0.569, 0.906, 0.271, 1.0,
             0.931, 0.814, 0.115, 1.0, 
             0.907, 0.060, 0.060, 1.0   
         ]
    
    The xPoints (positions) remain fixed.
    """
    print("Updating dynamic colormap for temperature:", temperature)
    
    # Clamp temperature to the [15, 30] range:
    # T_min = 15.0
    # T_max = 30.0
    # T = max(T_min, min(temperature, T_max))
    # alpha = (T - T_min) / (T_max - T_min)
    
   
    flat_rgba = [
        0.943, 0.961, 0.961, 0.7,  
        0.569, 0.906, 0.271, 1.0,
        0.931, 0.814, 0.115, 1.0, 
        0.907, 0.060, 0.060, 1.0   
    ]
    colormap_prim_paths = [
        "/Steam_01/flowOffscreen/colormap",
        "/Steam_02/flowOffscreen/colormap",
        "/Steam_03/flowOffscreen/colormap"
    ]
    #Interpolate between cold and hot for each stop.
    ind = 0
    for ind in range(3):
        steam_temperature = temperature - ind*0.8
        if ind > 0:
            computed_color = compute_color_from_temperature(steam_temperature)
        else:
            computed_color = color_rgba_cl
        flat_rgba[-4:] = list(computed_color)
        
        # Convert flat_rgba into a list of Gf.Vec4f objects.
        from pxr import Vt, Gf
        vec_list = [Gf.Vec4f(flat_rgba[i], flat_rgba[i+1], flat_rgba[i+2], flat_rgba[i+3])
                    for i in range(0, len(flat_rgba), 4)]
        new_rgbaPoints = Vt.Vec4fArray(vec_list)

    
        new_xPoints = [0.1563, 0.3885, 0.5862, 0.80139]
        
        prm_path = prefix_prim_path+colormap_prim_paths[ind]

        # Update the USD attributes on the colormap prim
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prm_path)
        if not prim.IsValid():
            print("Colormap prim not found at:", prm_path)
            return
        
        xPoints_attr = prim.GetAttribute("xPoints")
        if xPoints_attr.IsValid():
            xPoints_attr.Set(new_xPoints)
            print("xPoints updated:", new_xPoints)
        else:
            print("xPoints attribute not found on prim.")
        
        rgbaPoints_attr = prim.GetAttribute("rgbaPoints")
        if rgbaPoints_attr.IsValid():
            rgbaPoints_attr.Set(new_rgbaPoints)
            print("rgbaPoints updated:", new_rgbaPoints)
        else:
            print("rgbaPoints attribute not found on prim.")
        
        
# --- Color‐mapping function (unchanged) ---
def compute_color_from_temperature(T):
    # Clamp input to [19.0, 24.0]
    if T < 19.0:
        T = 19.0
    elif T > 24.0:
        T = 24.0

    stops = [
        (19.0, (0.085, 0.373, 0.876, 1.0)),
        (20.0, (0.258, 0.816, 0.915, 0.9)),
        (21.0, (0.500, 0.900, 0.600, 1.0)),
        (22.0, (0.569, 0.906, 0.271, 1.0)),
        (23.0, (0.931, 0.814, 0.115, 1.0)),
        (24.0, (0.907, 0.060, 0.060, 1.0))
    ]

    for i in range(len(stops) - 1):
        T_low, color_low = stops[i]
        T_high, color_high = stops[i + 1]
        if T_low <= T <= T_high:
            f = (T - T_low) / (T_high - T_low)
            r = (1 - f) * color_low[0] + f * color_high[0]
            g = (1 - f) * color_low[1] + f * color_high[1]
            b = (1 - f) * color_low[2] + f * color_high[2]
            a = (1 - f) * color_low[3] + f * color_high[3]
            return (r, g, b, a)


class TimeController:
    """USD Stage의 시간을 관리하고 데이터센터 센서 데이터를 연동하는 컨트롤러"""
    
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

        # 고성능 사전 계산된 타임라인
        self._second_timeline = {}  # 모든 초에 대해 사전 계산된 데이터


        # 센서 데이터 초기화
        self._sensor_data = {}  # 정규화된 timestamp 기준으로 그룹화된 센서 데이터
        self._sorted_timestamps = []  # 정렬된 timestamp 목록
        self._last_known_values = {}  # 각 랙의 마지막 알려진 값 저장
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
        unique_sensors = set()
        if self._sensor_data:
            for sensors in self._sensor_data.values():
                unique_sensors.update(sensors.keys())
        
        print(f"{LOG_PREFIX} 초기화 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}, 데이터가 있는 센서 수: {len(unique_sensors)}")
        
        # 디버깅: 매핑 상태 출력
        self._debug_mapping_status()
    
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
            try:
                base_path = pattern.split("RACK_")[0]
                
                if not stage.GetPrimAtPath(base_path).IsValid():
                    continue
                
                datacenter_prim = stage.GetPrimAtPath(base_path)
                if not datacenter_prim.IsValid():
                    continue
                
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
            
            print(f"{LOG_PREFIX} 랙 디렉토리 파일 경로: {rack_dir_path}")
            
            if os.path.exists(rack_dir_path):
                with open(rack_dir_path, 'r') as file:
                    content = file.read().strip()
                    self._rack_paths = content.split()
                
                print(f"{LOG_PREFIX} 로드된 랙 수: {len(self._rack_paths)}")
                
                # 랙-센서 매핑 파일 확인
                if os.path.exists(rack_map_path):
                    self._load_rack_sensor_map(rack_map_path)
                else:
                    print(f"{LOG_PREFIX} 랙-센서 매핑 파일이 없어 정의된 매핑을 생성합니다.")
                    self._create_predefined_mapping()
            else:
                print(f"{LOG_PREFIX} 랙 디렉토리 파일을 찾을 수 없음: {rack_dir_path}")
                self._create_test_rack_paths()
                
        except Exception as e:
            print(f"{LOG_PREFIX} 랙 경로 로드 오류: {e}")
            self._create_test_rack_paths()
    
    def _load_rack_sensor_map(self, map_file_path):
        """랙-센서 매핑 파일 로드"""
        try:
            with open(map_file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 2:
                        rack_path = parts[0]
                        sensor_id = parts[1]
                        self._rack_to_sensor_map[rack_path] = sensor_id
            
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 로드 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        except Exception as e:
            print(f"{LOG_PREFIX} 랙-센서 매핑 파일 로드 오류: {e}")
            self._create_predefined_mapping()
    
    def _create_test_rack_paths(self):
        """정의된 랙 경로를 기반으로 실제 랙 경로 찾기"""
        print(f"{LOG_PREFIX} 정의된 랙 경로 검색 중...")
        
        stage = self._usd_context.get_stage()
        real_paths = []
        
        if stage:
            for defined_path in PREDEFINED_RACK_PATHS:
                possible_paths = [prefix + defined_path for prefix in POSSIBLE_PATH_PREFIXES]
                
                for path in possible_paths:
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        real_paths.append(path)
                        print(f"{LOG_PREFIX} 실제 랙 찾음: {path}")
                        break
            
            if real_paths:
                self._rack_paths = real_paths
                print(f"{LOG_PREFIX} 실제 랙 경로 {len(real_paths)}개 찾음")
            else:
                self._rack_paths = [POSSIBLE_PATH_PREFIXES[1] + path for path in PREDEFINED_RACK_PATHS]
                print(f"{LOG_PREFIX} 실제 랙 경로를 찾지 못해 기본 경로 사용")
        else:
            self._rack_paths = [POSSIBLE_PATH_PREFIXES[1] + path for path in PREDEFINED_RACK_PATHS]
            print(f"{LOG_PREFIX} 스테이지 없음, 기본 랙 경로 사용")
            
        self._create_predefined_mapping()
        
    def _create_predefined_mapping(self):
        """정의된 랙-센서 매핑 생성"""
        predefined_mapping = RACK_SENSOR_MAPPING
        self._rack_to_sensor_map.clear()
        
        stage = self._usd_context.get_stage()
        mapped_count = 0
        
        for defined_path, sensor_id in predefined_mapping.items():
            possible_paths = [prefix + defined_path for prefix in POSSIBLE_PATH_PREFIXES]
            
            for path in possible_paths:
                if stage:
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        self._rack_to_sensor_map[path] = sensor_id
                        mapped_count += 1
                        print(f"{LOG_PREFIX} 매핑 성공: {path} -> {sensor_id}")
                        break
                else:
                    self._rack_to_sensor_map[path] = sensor_id
                    mapped_count += 1
                    break
        
        print(f"{LOG_PREFIX} 정의된 랙-센서 매핑 생성 완료. 매핑된 랙 수: {mapped_count}")
        
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
        """센서 데이터 CSV 파일 로드 - timestamp를 센티초 단위로 정규화"""
        try:
            csv_path = os.path.join(os.path.dirname(__file__), SENSOR_DATA_CONFIG["csv_file"])
            
            with open(csv_path, 'r') as file:
                reader = csv.DictReader(file)
                data_list = list(reader)
            
            # timestamp 기준으로 데이터 그룹화 + 정규화
            for entry in data_list:
                original_timestamp = entry.get(SENSOR_DATA_CONFIG["timestamp_column"])
                if not original_timestamp:
                    continue
                
                # 🚀 핵심: timestamp를 센티초 단위로 정규화
                normalized_timestamp = self._normalize_timestamp_to_seconds(original_timestamp)
                if not normalized_timestamp:
                    continue
                
                obj_id = entry.get(SENSOR_DATA_CONFIG["obj_id_column"], "unknown")
                
                # 숫자 형식으로 변환
                temp_columns = SENSOR_DATA_CONFIG["temperature_columns"]
                hum_columns = SENSOR_DATA_CONFIG["humidity_columns"]
                
                for field in [temp_columns["cold"], temp_columns["hot"], hum_columns["cold"], hum_columns["hot"]]:
                    if field in entry:
                        try:
                            entry[field] = float(entry[field])
                        except (ValueError, TypeError):
                            entry[field] = 0.0
                
                # 원본 timestamp도 보관 (디버깅용)
                entry['original_timestamp'] = original_timestamp
                entry['normalized_timestamp'] = normalized_timestamp
                
                # 정규화된 timestamp를 key로 사용하여 데이터 저장
                if normalized_timestamp not in self._sensor_data:
                    self._sensor_data[normalized_timestamp] = {}
                
                self._sensor_data[normalized_timestamp][obj_id] = entry
            
            # 🚀 정규화된 timestamp 정렬
            # self._sorted_timestamps = sorted(self._sensor_data.keys())
            self._sorted_timestamps = list(self._sensor_data.keys())
            
            # 결과 요약
            total_timestamps = len(self._sensor_data)
            total_entries = sum(len(sensors) for sensors in self._sensor_data.values())
            unique_sensors = set()
            for sensors in self._sensor_data.values():
                unique_sensors.update(sensors.keys())
            
            print(f"{LOG_PREFIX} 로드된 센서 데이터: {total_entries}개 데이터, {total_timestamps}개 정규화된 타임스탬프, {len(unique_sensors)}개 센서")
            
            if self._sorted_timestamps:
                print(f"{LOG_PREFIX} 정규화된 시간 범위: {self._sorted_timestamps[0]} ~ {self._sorted_timestamps[-1]}")
            
            # 🚀 핵심: 사전 계산 실행
            self.precompute_cumulative_lkv_timeline()
            # self.precompute_second_timeline()
            
        except Exception as e:
            print(f"{LOG_PREFIX} 센서 데이터 로드 오류: {e}")
            self._sensor_data = {}
            self._sorted_timestamps = []

    def precompute_cumulative_lkv_timeline(self):
        """센서별 누적 LKV로 초단위 타임라인 사전 계산"""
        print(f"{LOG_PREFIX} === 센서별 누적 LKV 타임라인 계산 시작 ===")
        
        if not self._sorted_timestamps:
            print(f"{LOG_PREFIX} 센서 데이터가 없어 사전 계산을 건너뜁니다.")
            return
        
        # 1. 모든 센서 ID 수집
        all_sensor_ids = set()
        for sensors in self._sensor_data.values():
            all_sensor_ids.update(sensors.keys())
        
        print(f"{LOG_PREFIX} 전체 센서 수: {len(all_sensor_ids)}")
        print(f"{LOG_PREFIX} 센서 ID들: {sorted(all_sensor_ids)}")
        
        # 2. 시간 범위 설정
        start_dt = self._parse_timestamp(self._sorted_timestamps[0])
        end_dt = self._parse_timestamp(self._sorted_timestamps[-1])
        
        if not start_dt or not end_dt:
            print(f"{LOG_PREFIX} 시간 파싱 실패")
            return
        
        print(f"{LOG_PREFIX} 계산 범위: {start_dt} ~ {end_dt}")
        
        # 3. 센서별 LKV 저장소 초기화
        sensor_lkv = {}  # {sensor_id: 최신_데이터}
        
        # 4. 초기 LKV 설정 - 각 센서의 첫 번째 데이터로 초기화
        print(f"{LOG_PREFIX} 센서별 초기 LKV 설정 중...")
        for sensor_id in all_sensor_ids:
            # 각 센서의 첫 번째 등장 시점 찾기
            for timestamp in self._sorted_timestamps:
                if sensor_id in self._sensor_data[timestamp]:
                    sensor_lkv[sensor_id] = self._sensor_data[timestamp][sensor_id]
                    print(f"{LOG_PREFIX}   {sensor_id}: 초기 LKV 설정 ({timestamp})")
                    break
            
            if sensor_id not in sensor_lkv:
                print(f"{LOG_PREFIX}   ⚠️  {sensor_id}: 초기 데이터를 찾을 수 없음")
        
        # 5. 매 초마다 누적 LKV 계산
        self._second_timeline = {}
        current_time = start_dt
        total_seconds = 0
        update_events = 0
        
        print(f"{LOG_PREFIX} 매 초 누적 LKV 계산 시작...")
        
        while current_time <= end_dt:
            second_key = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # 현재 시점에 실제 데이터가 있으면 해당 센서들의 LKV 업데이트
            if second_key in self._sensor_data:
                current_updates = self._sensor_data[second_key]
                
                for sensor_id, new_data in current_updates.items():
                    if sensor_id in sensor_lkv:  # 알려진 센서만 업데이트
                        sensor_lkv[sensor_id] = new_data
                        update_events += 1
                
                if len(current_updates) > 0:
                    updated_sensors = list(current_updates.keys())
                    print(f"{LOG_PREFIX} {second_key}: {len(current_updates)}개 센서 업데이트 {updated_sensors}")
            
            # 현재 시점의 모든 센서 LKV를 second_timeline에 저장
            self._second_timeline[second_key] = sensor_lkv.copy()  # 깊은 복사 중요!
            
            total_seconds += 1
            current_time += datetime.timedelta(seconds=1)
            
            # 진행 상황 출력 (1000초마다)
            if total_seconds % 1000 == 0:
                print(f"{LOG_PREFIX} 진행: {total_seconds:,}초 처리 완료...")
        
        print(f"{LOG_PREFIX} === 누적 LKV 계산 완료 ===")
        print(f"{LOG_PREFIX} 총 처리 초 수: {total_seconds:,}")
        print(f"{LOG_PREFIX} 센서 업데이트 이벤트: {update_events:,}")
        print(f"{LOG_PREFIX} 센서별 평균 업데이트: {update_events/len(all_sensor_ids):.1f}회")
        
        # 6. 검증: 몇 개 시점 확인
        print(f"\n{LOG_PREFIX} === 누적 LKV 검증 ===")
        sample_times = [start_dt + datetime.timedelta(seconds=i) for i in [0, 60, 300, 600]]
        
        for sample_time in sample_times:
            sample_key = sample_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            sample_data = self._second_timeline.get(sample_key)
            
            if sample_data:
                print(f"{LOG_PREFIX} {sample_key}: ✅ {len(sample_data)}개 센서 (전체 센서 커버)")
                
                # 첫 3개 센서 샘플 값 확인
                for i, (sensor_id, data) in enumerate(list(sample_data.items())[:3]):
                    temp_val = data.get('TEMPERATURE1', 'N/A')
                    print(f"{LOG_PREFIX}   {sensor_id}: TEMPERATURE1={temp_val}")
            else:
                print(f"{LOG_PREFIX} {sample_key}: ❌ 데이터 없음")
                
    def _normalize_timestamp_to_seconds(self, timestamp_str):
        """타임스탬프를 센티초 단위로 정규화"""
        try:
            # 1. 원본 timestamp 파싱
            dt = self._parse_timestamp(timestamp_str)
            if not dt:
                return None
            
            # 2. 센티초 단위로 변환 (마이크로초 뒤 4자리 제거)
            # normalized = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
            normalized = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return normalized
            
        except Exception as e:
            print(f"{LOG_PREFIX} 타임스탬프 정규화 오류 ({timestamp_str}): {e}")
            return None
        
    def precompute_second_timeline(self):
        """모든 초에 대해 LKV 데이터 미리 할당 - 고성능 사전 계산"""
        print(f"{LOG_PREFIX} === 초단위 타임라인 사전 계산 시작 ===")
        
        if not self._sorted_timestamps:
            print(f"{LOG_PREFIX} 센서 데이터가 없어 사전 계산을 건너뜁니다.")
            return
        
        self._second_timeline = {}
        current_lkv_data = None
        
        # 시작/끝 시간 확인
        start_dt = self._parse_timestamp(self._sorted_timestamps[0])
        end_dt = self._parse_timestamp(self._sorted_timestamps[-1])
        
        if not start_dt or not end_dt:
            print(f"{LOG_PREFIX} 시작/끝 시간 파싱 실패")
            return
        
        print(f"{LOG_PREFIX} 사전 계산 범위: {start_dt} ~ {end_dt}")
        
        # 시작 시간부터 끝 시간까지 모든 초 순회
        current_time = start_dt
        total_seconds = 0
        actual_data_count = 0
        lkv_count = 0
        
        while current_time <= end_dt:
            second_key = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # 실제 센서 데이터가 있으면 LKV 업데이트
            if second_key in self._sensor_data:
                current_lkv_data = self._sensor_data[second_key]
                actual_data_count += 1
                print(f"{LOG_PREFIX} 실제 데이터 발견: {second_key} ({len(current_lkv_data)}개 센서)")
            
            # 현재 초에 LKV 할당 (실제 데이터 또는 이전 데이터)
            if current_lkv_data:
                self._second_timeline[second_key] = current_lkv_data
                if second_key not in self._sensor_data:
                    lkv_count += 1
            else:
                # 아직 데이터가 없는 경우 (시작 지점)
                self._second_timeline[second_key] = None
            
            total_seconds += 1
            current_time += datetime.timedelta(seconds=1)
        
        print(f"{LOG_PREFIX} === 사전 계산 완료 ===")
        print(f"{LOG_PREFIX} 총 초 수: {total_seconds:,}개")
        print(f"{LOG_PREFIX} 실제 데이터: {actual_data_count:,}개")
        print(f"{LOG_PREFIX} LKV 할당: {lkv_count:,}개")
        print(f"{LOG_PREFIX} 압축 비율: {actual_data_count}/{total_seconds} = {actual_data_count/total_seconds*100:.1f}%")
        
        # 메모리 사용량 추정
        estimated_mb = total_seconds * 0.5 / 1024  # 대략적 추정
        print(f"{LOG_PREFIX} 예상 메모리 사용량: ~{estimated_mb:.1f} MB")

        
    def _initialize_time_range(self):
        """센서 데이터 기반으로 시간 범위 초기화"""
        try:
            if self._sorted_timestamps:
                first_timestamp = self._sorted_timestamps[0]
                last_timestamp = self._sorted_timestamps[-1]
                
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
            if "." in timestamp_str and timestamp_str.endswith("Z"):
                return dt.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            elif timestamp_str.endswith("Z"):
                return dt.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
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
                
            time_prim = stage.GetPrimAtPath(self._time_manager_path)
            
            if not time_prim or not time_prim.IsValid():
                print(f"{LOG_PREFIX} TimeManager가 없음. 생성 중: {self._time_manager_path}")
                
                parent_path = os.path.dirname(self._time_manager_path)
                if parent_path != "/":
                    parent_prim = stage.GetPrimAtPath(parent_path)
                    if not parent_prim or not parent_prim.IsValid():
                        print(f"{LOG_PREFIX} 부모 경로 생성 중: {parent_path}")
                        parent_prim = UsdGeom.Xform.Define(stage, parent_path)
                
                time_prim = UsdGeom.Xform.Define(stage, self._time_manager_path)
                time_prim.SetCustomDataByKey("description", "시간 관리 및 동기화를 위한 객체")
                time_prim.SetCustomDataByKey("created", dt.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                print(f"{LOG_PREFIX} TimeManager 생성 완료: {self._time_manager_path}")
            
            if not time_prim.GetCustomDataByKey("baseTime"):
                base_time_str = DEFAULT_TIME_CONFIG["base_time"]
                time_prim.SetCustomDataByKey("baseTime", base_time_str)
                print(f"{LOG_PREFIX} baseTime 설정: {base_time_str}")
            
            current_time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
            time_prim.SetCustomDataByKey("currentTime", current_time_str)
            
            return True
            
        except Exception as e:
            print(f"{LOG_PREFIX} TimeManager 초기화 오류: {e}")
            return False
    
    def _update_rack_attributes(self, rack_path, data_entry):
        """랙 객체의 속성 업데이트"""
        if not data_entry:
            try:
                stage = self._usd_context.get_stage()
                if not stage:
                    return
                    
                rack_prim = stage.GetPrimAtPath(rack_path)
                if not rack_prim or not rack_prim.IsValid():
                    return              
                #print(f"{rack_path}=====CheckingRACK===  ")
                attr_config = USD_ATTRIBUTE_CONFIG["rack_attributes"]
                for attr_name in [attr_config["temperature_cold"], attr_config["temperature_hot"], 
                                attr_config["humidity_cold"], attr_config["humidity_hot"]]:
                    if rack_prim.HasAttribute(attr_name):
                        rack_prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float).Set(float('nan'))
                
                # 메타데이터 초기화
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
            
            temp_columns = SENSOR_DATA_CONFIG["temperature_columns"]
            hum_columns = SENSOR_DATA_CONFIG["humidity_columns"]
            
            temp1 = data_entry.get(temp_columns["cold"], 0.0)
            temp2 = data_entry.get(temp_columns["hot"], 0.0)
            hum1 = data_entry.get(hum_columns["cold"], 0.0)
            hum2 = data_entry.get(hum_columns["hot"], 0.0)
            
            try:
                temp1 = float(temp1)
                temp2 = float(temp2)
                hum1 = float(hum1)
                hum2 = float(hum2)
            except (ValueError, TypeError):
                print(f"{LOG_PREFIX} 유효하지 않은 데이터 값 - 기본값 사용")
                temp1 = temp2 = hum1 = hum2 = 0.0
            
            attr_config = USD_ATTRIBUTE_CONFIG["rack_attributes"]
            
            # 속성 설정
            rack_prim.CreateAttribute(attr_config["temperature_cold"], Sdf.ValueTypeNames.Float).Set(temp1)
            rack_prim.CreateAttribute(attr_config["temperature_hot"], Sdf.ValueTypeNames.Float).Set(temp2)
            rack_prim.CreateAttribute(attr_config["humidity_cold"], Sdf.ValueTypeNames.Float).Set(hum1)
            rack_prim.CreateAttribute(attr_config["humidity_hot"], Sdf.ValueTypeNames.Float).Set(hum2)
            
            # 메타데이터 설정
            rack_prim.SetCustomDataByKey("temperature_cold", temp1)
            rack_prim.SetCustomDataByKey("temperature_hot", temp2)
            rack_prim.SetCustomDataByKey("humidity_cold", hum1)
            rack_prim.SetCustomDataByKey("humidity_hot", hum2)
            rack_prim.SetCustomDataByKey("timestamp", data_entry.get('normalized_timestamp', "Unknown"))
            rack_prim.SetCustomDataByKey("sensor_id", data_entry.get(SENSOR_DATA_CONFIG["obj_id_column"], "Unknown"))
            rack_prim.SetCustomDataByKey("data_source", "sensor_data")
            rack_prim.SetCustomDataByKey("last_updated", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
            normalized_path = rack_path.replace("/Root", "")

            # Step 2: Lookup and convert obj_id
            obj_id_str = RACK_SENSOR_MAPPING.get(normalized_path)
            if obj_id_str is not None:
                try:
                    obj_id = int(obj_id_str)
                except ValueError:
                    print(f"Invalid obj_id format for path {normalized_path}")
                    obj_id = None
            else:
                print(f"Rack path not found in mapping: {normalized_path}")
                obj_id = None

            if obj_id is not None:
                # Step 3: Use temp1 directly
                t1_value = temp1

                # Step 4: Compute color
                rgba_col = compute_color_from_temperature(t1_value)

                # Step 5: Optionally update dynamic colormap
                if obj_id < 26:
                    path = objid_to_airrack[obj_id]
                    update_dynamic_colormap(t1_value, rgba_col, path)
        
        except Exception as e:
            print(f"{LOG_PREFIX} 객체 속성 업데이트 오류 ({rack_path}): {e}")
    
    def get_sensor_id_for_rack(self, rack_path):
        """특정 랙에 매핑된 센서 ID 가져오기"""
        # 직접 매핑 확인
        if rack_path in self._rack_to_sensor_map:
            return self._rack_to_sensor_map.get(rack_path)
        
        # 끝부분 비교
        rack_name = rack_path.split('/')[-1] if '/' in rack_path else rack_path
        for path, sensor_id in self._rack_to_sensor_map.items():
            if path.endswith('/' + rack_name):
                return sensor_id
        
        # 경로 변형 시도
        variations = []
        if rack_path.startswith('/World/'):
            variations.append(rack_path[6:])
        elif not rack_path.startswith('/World'):
            variations.append('/World' + rack_path)
        
        for var_path in variations:
            if var_path in self._rack_to_sensor_map:
                return self._rack_to_sensor_map.get(var_path)
        
        return None
    
    def _update_all_racks(self):
        """고성능 초단위 사전 계산된 데이터로 랙 업데이트"""
        
        # # 🎯 핵심: 센티초 무시하고 초단위로 변환
        # current_second = self._current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # print(f"{LOG_PREFIX} [고성능] 현재 초: {current_second}")
        
        # # 🚀 O(1) 직접 조회 - 가장 빠름!
        # second_data = self._second_timeline.get(current_second)
        
        # if second_data:
        #     print(f"{LOG_PREFIX} [고성능] ⚡ 사전 계산된 데이터 발견: {len(second_data)}개 센서")
        #     updated_count = 0
        #     maintained_count = 0
            
        #     # 모든 랙에 빠르게 적용
        #     for rack_path in self._rack_paths:
        #         sensor_id = self.get_sensor_id_for_rack(rack_path)

        #         # 여기 sensor_id 가 None 이어서 LKV 사용하는건가? 결국 데이터 할당문제
        #         print(f"[DEBUG] {rack_path} -> sensor_id: {sensor_id}")

        #         if sensor_id and sensor_id in second_data:
        #             # 사전 계산된 데이터 직접 사용
        #             rack_data = second_data[sensor_id]
        #             self._last_known_values[rack_path] = rack_data  # LKV 업데이트
        #             self._update_rack_attributes(rack_path, rack_data)
        #             updated_count += 1
        #             print(f"[DEBUG] ✅ 업데이트 성공: {rack_path}")
                    
        #         elif rack_path in self._last_known_values:
        #             # 기존 LKV 유지
        #             rack_data = self._last_known_values[rack_path]
        #             self._update_rack_attributes(rack_path, rack_data)
        #             maintained_count += 1
                    
        #         else:
        #             # 데이터 없음
        #             self._update_rack_attributes(rack_path, None)
            
        #     print(f"{LOG_PREFIX} [고성능] ⚡ 업데이트 완료: {updated_count}개 새 데이터, {maintained_count}개 LKV 유지")
        #     return updated_count
            
        # else:
        #     print(f"{LOG_PREFIX} [고성능] ❌ 사전 계산된 데이터 없음: {current_second}")
            
        #     # 🔍 디버깅: 사용 가능한 시간 확인
        #     available_times = list(self._second_timeline.keys())[:5]
        #     print(f"{LOG_PREFIX} [고성능] 사용 가능한 시간 (예시): {available_times}")
            
        #     return 0             
        return self._update_all_racks_with_debug()
    
    def debug_specific_time_data(self, target_time=None):
        """특정 시점의 second_data 상세 분석"""
        if target_time is None:
            target_time = self._current_time
        
        # 시간 문자열 변환
        if isinstance(target_time, str):
            time_str = target_time
            target_dt = self._parse_timestamp(target_time)
        else:
            time_str = target_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            target_dt = target_time
        
        print(f"\n{LOG_PREFIX} ========== 특정 시점 데이터 분석 ==========")
        print(f"{LOG_PREFIX} 분석 시점: {time_str}")
        print(f"{LOG_PREFIX} 현재 컨트롤러 시간: {self._current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        
        # 1. _second_timeline에서 데이터 조회
        second_data = self._second_timeline.get(time_str)
        
        print(f"\n{LOG_PREFIX} === _second_timeline 조회 결과 ===")
        if second_data is None:
            print(f"{LOG_PREFIX} ❌ second_data: None (데이터 없음)")
        else:
            print(f"{LOG_PREFIX} ✅ second_data: {len(second_data)}개 센서 데이터")
            print(f"{LOG_PREFIX} 센서 ID 목록: {list(second_data.keys())}")
            
            # 각 센서 데이터 미리보기
            for sensor_id, data in list(second_data.items()):  # 처음 3개만
                # temp_cold = data.get('temp1', 'N/A')
                # temp_hot = data.get('temp2', 'N/A')
                print(f"{LOG_PREFIX}   {sensor_id}: data={data}")
        
        # 2. 원본 _sensor_data 확인
        print(f"\n{LOG_PREFIX} === 원본 _sensor_data 확인 ===")
        original_data = self._sensor_data.get(time_str)
        if original_data:
            print(f"{LOG_PREFIX} ✅ 원본 데이터: {len(original_data)}개 센서")
            print(f"{LOG_PREFIX} 원본 센서 ID: {list(original_data.keys())}")
        else:
            print(f"{LOG_PREFIX} ❌ 원본 데이터: 없음")
        
        # 3. 랙 매핑 상태 확인
        print(f"\n{LOG_PREFIX} === 랙 매핑 상태 확인 ===")
        mapped_racks = 0
        data_available_racks = 0
        
        for rack_path in self._rack_paths[:5]:  # 처음 5개 랙만 확인
            sensor_id = self.get_sensor_id_for_rack(rack_path)
            
            if sensor_id:
                mapped_racks += 1
                rack_name = rack_path.split('/')[-1]
                
                if second_data and sensor_id in second_data:
                    data_available_racks += 1
                    rack_data = second_data[sensor_id]
                    temp1 = rack_data.get('temp1', 'N/A')
                    temp2 = rack_data.get('temp2', 'N/A')
                    print(f"{LOG_PREFIX}   ✅ {rack_name} -> {sensor_id}: temp1={temp1}, temp2={temp2}")
                else:
                    print(f"{LOG_PREFIX}   ❌ {rack_name} -> {sensor_id}: 데이터 없음")
            else:
                print(f"{LOG_PREFIX}   ❌ {rack_path}: 센서 매핑 없음")
        
        print(f"\n{LOG_PREFIX} === 요약 ===")
        print(f"{LOG_PREFIX} 전체 랙 수: {len(self._rack_paths)}")
        print(f"{LOG_PREFIX} 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        print(f"{LOG_PREFIX} 확인한 랙 중 매핑 성공: {mapped_racks}/5")
        print(f"{LOG_PREFIX} 확인한 랙 중 데이터 있음: {data_available_racks}/5")
        
        # 4. _update_all_racks() 시뮬레이션
        print(f"\n{LOG_PREFIX} == _update_all_racks() 시뮬레이션 ==")
        if second_data:
            print(f"{LOG_PREFIX} ✅ if second_data: 조건 통과 (업데이트 실행됨)")
            
            updated_count = 0
            for rack_path in self._rack_paths:
                sensor_id = self.get_sensor_id_for_rack(rack_path)
                if sensor_id and sensor_id in second_data:
                    updated_count += 1
            
            print(f"{LOG_PREFIX} 예상 업데이트 랙 수: {updated_count}/{len(self._rack_paths)}")
        else:
            print(f"{LOG_PREFIX} ❌ if second_data: 조건 실패 (업데이트 안됨)")
        
        return {
            'time_str': time_str,
            'second_data_exists': second_data is not None,
            'second_data_sensor_count': len(second_data) if second_data else 0,
            'original_data_exists': original_data is not None,
            'would_update': second_data is not None
        }   
    def debug_time_movement(self, from_time, to_time):
        """시간 이동 전후 데이터 비교"""
        print(f"\n{LOG_PREFIX} ========== 시간 이동 디버깅 ==========")
        
        # 이동 전 상태
        print(f"{LOG_PREFIX} === 이동 전: {from_time} ===")
        before_result = self.debug_specific_time_data(from_time)
        
        # 시간 이동
        if isinstance(to_time, str):
            to_dt = self._parse_timestamp(to_time)
        else:
            to_dt = to_time
        
        print(f"\n{LOG_PREFIX} === 시간 이동 실행: {from_time} -> {to_time} ===")
        self.set_current_time(to_dt)
        
        # 이동 후 상태
        print(f"{LOG_PREFIX} === 이동 후: {to_time} ===")
        after_result = self.debug_specific_time_data(to_time)
        
        # 비교 결과
        print(f"\n{LOG_PREFIX} === 이동 결과 비교 ===")
        print(f"{LOG_PREFIX} 이동 전 데이터 있음: {before_result['would_update']}")
        print(f"{LOG_PREFIX} 이동 후 데이터 있음: {after_result['would_update']}")
        
        if before_result['would_update'] != after_result['would_update']:
            print(f"{LOG_PREFIX} ⚠️  데이터 상태 변화 감지!")
        
        return before_result, after_result       
    
    def _update_all_racks_with_debug(self):
        """디버깅이 추가된 _update_all_racks"""
        current_second = self._current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        print(f"\n{LOG_PREFIX} == _update_all_racks 실행 ==")
        print(f"{LOG_PREFIX} 현재 시간: {current_second}")
        
        # second_data 조회
        second_data = self._second_timeline.get(current_second)
        
        if second_data:
            print(f"{LOG_PREFIX} ✅ second_data 발견: {len(second_data)}개 센서")
            updated_count = 0
            maintained_count = 0
            failed_count = 0
            
            for rack_path in self._rack_paths: # 이런거 병령처리 되나?
                sensor_id = self.get_sensor_id_for_rack(rack_path) 
                
                if sensor_id and sensor_id in second_data:
                    rack_data = second_data[sensor_id]
                    self._last_known_values[rack_path] = rack_data
                    self._update_rack_attributes(rack_path, rack_data)
                    updated_count += 1
                    
                elif rack_path in self._last_known_values:
                    rack_data = self._last_known_values[rack_path]
                    self._update_rack_attributes(rack_path, rack_data)
                    maintained_count += 1
                    
                else:
                    self._update_rack_attributes(rack_path, None)
                    failed_count += 1
            
            print(f"{LOG_PREFIX} 업데이트 결과: 새 데이터 {updated_count}, LKV 유지 {maintained_count}, 실패 {failed_count}")
            return updated_count
            
        else:
            print(f"{LOG_PREFIX} ❌ second_data 없음: {current_second}")
            
            # # 주변 시간 확인
            # target_dt = self._current_time
            # for offset in [-2, -1, 1, 2]:
            #     check_time = target_dt + datetime.timedelta(seconds=offset)
            #     check_str = check_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            #     check_data = self._second_timeline.get(check_str)
            #     status = "있음" if check_data else "없음"
            #     print(f"{LOG_PREFIX} {offset:+2d}초 ({check_str}): {status}")
            # target_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            # target_data = self._second_timeline.get(target_str)

            # if target_data:
            #     print(f"{LOG_PREFIX} ✅ {target_str}: {len(target_data)}개 센서")
            #     # 센서 ID들도 출력하고 싶다면
            #     sensor_ids = list(target_data.keys())[:3]  # 처음 3개만
            #     print(f"{LOG_PREFIX}   센서 예시: {sensor_ids}")
            # else:
            #     print(f"{LOG_PREFIX} ❌ {target_str}: 데이터 없음")
            # return 0
    
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
            base_dt = self._parse_timestamp(base_time_str)
            if not base_dt:
                raise ValueError(f"Invalid base time format: {base_time_str}")
                
            delta_seconds = (dt_obj - base_dt).total_seconds()
            return delta_seconds
        except Exception as e:
            print(f"{LOG_PREFIX} 시간 변환 오류: {e}")
            return 0.0
    
    def _update_stage_time(self):
        """현재 시간에 따라 USD Stage 시간 업데이트 및 센서 데이터 적용"""
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
                    # 센티초 단위 시간 포맷 사용
                    time_str = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
                    time_prim.SetCustomDataByKey("currentTime", time_str)
                    time_prim.SetCustomDataByKey("lastUpdated", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                    
                    # 모든 랙 업데이트 (새로운 정확한 매칭 방식)
                    updated_count = self._update_all_racks()
                    if updated_count > 0:
                        print(f"{LOG_PREFIX} 새로 업데이트된 랙 수: {updated_count}")
        except Exception as e:
            print(f"{LOG_PREFIX} 시간 관리자 업데이트 오류: {e}")
    
    # ========== 시간 제어 메서드들 ==========
    
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
        # """현재 시간 설정"""
        # if current_time < self._start_time:
        #     self._current_time = self._start_time
        # elif current_time > self._end_time:
        #     self._current_time = self._end_time
        # else:
        #     self._current_time = current_time
        # self._update_stage_time()
    
        """현재 시간 설정 - 디버깅 추가"""
        if current_time < self._start_time:
            self._current_time = self._start_time
        elif current_time > self._end_time:
            self._current_time = self._end_time
        else:
            self._current_time = current_time
        
        # 🔍 디버깅 추가
        print(f"{LOG_PREFIX} === 타임 슬라이더 이동: {self._current_time.strftime('%Y-%m-%dT%H:%M:%SZ')} ===")
        self.debug_specific_time_data()  # 자동 디버깅
        
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
    
    # ========== Getter 메서드들 ==========
    
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
        unique_sensors = set()
        for sensors_at_time in self._sensor_data.values():
            unique_sensors.update(sensors_at_time.keys())
        return len(unique_sensors)
    
    # ========== 디버깅 및 정보 메서드들 ==========
    
    def get_exact_match_data(self, target_time_str):
        """특정 시간에 정확히 매칭되는 데이터 반환 (디버깅용)"""
        return self._sensor_data.get(target_time_str, {})
    
    def get_available_timestamps_around(self, target_time_str, window=5):
        """특정 시간 주변의 사용 가능한 timestamp 반환 (디버깅용)"""
        if target_time_str in self._sorted_timestamps:
            idx = self._sorted_timestamps.index(target_time_str)
            start = max(0, idx - window)
            end = min(len(self._sorted_timestamps), idx + window + 1)
            return self._sorted_timestamps[start:end]
        return []
    
    def get_last_known_values_summary(self):
        """Last known values 상태 요약 (디버깅용)"""
        summary = {
            "total_racks": len(self._rack_paths),
            "racks_with_last_known": len(self._last_known_values),
            "racks_without_data": len(self._rack_paths) - len(self._last_known_values)
        }
        return summary
    
    def force_refresh_all_racks(self):
        """모든 랙의 last known values를 강제로 새로고침"""
        print(f"{LOG_PREFIX} 모든 랙 강제 새로고침 시작...")
        self._last_known_values.clear()
        updated_count = self._update_all_racks()
        print(f"{LOG_PREFIX} 강제 새로고침 완료: {updated_count}개 랙 업데이트")
        return updated_count
    
    def get_current_matching_status(self):
        """현재 시간의 매칭 상태 정보 반환 (디버깅용)"""
        current_stage_time = self._current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"
        
        status = {
            "current_stage_time": current_stage_time,
            "exact_match_exists": current_stage_time in self._sensor_data,
            "sensor_count_at_time": len(self._sensor_data.get(current_stage_time, {})),
            "total_timestamps": len(self._sorted_timestamps),
            "last_known_values_count": len(self._last_known_values)
        }
        
        if status["exact_match_exists"]:
            status["available_sensors"] = list(self._sensor_data[current_stage_time].keys())
        
        return status
    
    def print_timestamp_samples(self, count=10):
        """사용 가능한 timestamp 샘플 출력 (디버깅용)"""
        print(f"{LOG_PREFIX} === 사용 가능한 Timestamp 샘플 (처음 {count}개) ===")
        for i, ts in enumerate(self._sorted_timestamps[:count]):
            sensor_count = len(self._sensor_data[ts])
            print(f"{LOG_PREFIX} {i+1:2d}. {ts} ({sensor_count}개 센서)")
        
        if len(self._sorted_timestamps) > count:
            print(f"{LOG_PREFIX} ... (총 {len(self._sorted_timestamps)}개 timestamp)")
    
    # ========== 종료 및 정리 메서드들 ==========
    
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
        """매핑 상태 디버깅 정보 출력"""
        print(f"{LOG_PREFIX} === 매핑 상태 디버깅 ===")
        print(f"{LOG_PREFIX} 총 랙 경로 수: {len(self._rack_paths)}")
        print(f"{LOG_PREFIX} 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        print(f"{LOG_PREFIX} 센서 데이터 타임스탬프 수: {len(self._sensor_data)}")
        print(f"{LOG_PREFIX} 정렬된 타임스탬프 수: {len(self._sorted_timestamps)}")
        
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
        
        # 첫 번째와 마지막 타임스탬프 정보
        if self._sorted_timestamps:
            print(f"{LOG_PREFIX} 첫 번째 타임스탬프: {self._sorted_timestamps[0]}")
            print(f"{LOG_PREFIX} 마지막 타임스탬프: {self._sorted_timestamps[-1]}")
            
            # 첫 번째 타임스탬프의 센서 데이터 확인
            first_timestamp = self._sorted_timestamps[0]
            sensors_at_first_time = self._sensor_data[first_timestamp]
            print(f"{LOG_PREFIX} 첫 번째 타임스탬프 ({first_timestamp})의 센서: {list(sensors_at_first_time.keys())[:5]}")
        
        # Last known values 상태
        summary = self.get_last_known_values_summary()
        print(f"{LOG_PREFIX} Last Known Values: {summary['racks_with_last_known']}/{summary['total_racks']} 랙")
        # controller.py에 추가할 테스트 함수들

    