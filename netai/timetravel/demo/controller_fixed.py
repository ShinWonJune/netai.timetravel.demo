# 수정된 부분들만 - 기존 controller.py에서 이 부분들만 교체하세요

# 1. __init__() 수정 - _second_timeline 초기화 위치 변경
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
    self._sensor_data = {}  # 정규화된 timestamp 기준으로 그룹화된 센서 데이터
    self._sorted_timestamps = []  # 정렬된 timestamp 목록
    self._last_known_values = {}  # 각 랙의 마지막 알려진 값 저장
    
    # 🚀 수정: 고성능 타임라인을 먼저 초기화
    self._second_timeline = {}  # 모든 초에 대해 사전 계산된 데이터
    
    # 센서 데이터 로드 (여기서 precompute_second_timeline() 호출됨)
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
    print(f"{LOG_PREFIX} 사전 계산된 타임라인: {len(self._second_timeline)}개 초")
    
    # 디버깅: 매핑 상태 출력
    self._debug_mapping_status()

# 2. _load_sensor_data() 수정 - 올바른 함수 호출
def _load_sensor_data(self):
    """센서 데이터 CSV 파일 로드 - timestamp를 초 단위로 정규화"""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), SENSOR_DATA_CONFIG["csv_file"])
        
        with open(csv_path, 'r') as file:
            reader = csv.DictReader(file)
            data_list = list(reader)
        
        print(f"{LOG_PREFIX} CSV 데이터 로드: {len(data_list)}개 행")
        
        # timestamp 기준으로 데이터 그룹화 + 정규화
        for entry in data_list:
            original_timestamp = entry.get(SENSOR_DATA_CONFIG["timestamp_column"])
            if not original_timestamp:
                continue
            
            # 🚀 수정: 올바른 함수 호출 (초단위 정규화)
            normalized_timestamp = self._normalize_to_seconds(original_timestamp)
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
        
        # 삽입 순서 그대로 사용
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
        
        # 🚀 핵심: 센서 데이터 로드 완료 후 사전 계산 실행
        if self._sorted_timestamps:
            self.precompute_second_timeline()
        else:
            print(f"{LOG_PREFIX} 센서 데이터가 없어 사전 계산을 건너뜁니다.")
        
    except Exception as e:
        print(f"{LOG_PREFIX} 센서 데이터 로드 오류: {e}")
        self._sensor_data = {}
        self._sorted_timestamps = []

# 3. 새로운 정규화 함수 추가 (기존 함수와 별도)
def _normalize_to_seconds(self, timestamp_str):
    """타임스탬프를 초 단위로 정규화 (센티초/밀리초 제거)"""
    try:
        # 1. 원본 timestamp 파싱
        dt = self._parse_timestamp(timestamp_str)
        if not dt:
            return None
        
        # 2. 초 단위로 변환 (센티초/밀리초 완전 제거)
        normalized = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return normalized
        
    except Exception as e:
        print(f"{LOG_PREFIX} 초단위 정규화 오류 ({timestamp_str}): {e}")
        return None

# 4. precompute_second_timeline() 개선 (에러 체크 강화)
def precompute_second_timeline(self):
    """모든 초에 대해 LKV 데이터 미리 할당 - 고성능 사전 계산"""
    print(f"{LOG_PREFIX} === 초단위 타임라인 사전 계산 시작 ===")
    
    if not self._sorted_timestamps:
        print(f"{LOG_PREFIX} ❌ 센서 데이터가 없어 사전 계산을 건너뜁니다.")
        return
    
    if not self._sensor_data:
        print(f"{LOG_PREFIX} ❌ 센서 데이터 딕셔너리가 비어있습니다.")
        return
    
    # 기존 타임라인 초기화
    self._second_timeline = {}
    current_lkv_data = None
    
    # 시작/끝 시간 확인
    start_dt = self._parse_timestamp(self._sorted_timestamps[0])
    end_dt = self._parse_timestamp(self._sorted_timestamps[-1])
    
    if not start_dt or not end_dt:
        print(f"{LOG_PREFIX} ❌ 시작/끝 시간 파싱 실패")
        print(f"{LOG_PREFIX} 시작 timestamp: {self._sorted_timestamps[0]}")
        print(f"{LOG_PREFIX} 끝 timestamp: {self._sorted_timestamps[-1]}")
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
            if actual_data_count <= 5:  # 처음 5개만 출력
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
        
        # 진행상황 출력 (매 1000초마다)
        if total_seconds % 1000 == 0:
            print(f"{LOG_PREFIX} 사전 계산 진행: {total_seconds:,}초 완료...")
    
    print(f"{LOG_PREFIX} === 사전 계산 완료 ===")
    print(f"{LOG_PREFIX} 총 초 수: {total_seconds:,}개")
    print(f"{LOG_PREFIX} 실제 데이터: {actual_data_count:,}개")
    print(f"{LOG_PREFIX} LKV 할당: {lkv_count:,}개")
    
    if total_seconds > 0:
        print(f"{LOG_PREFIX} 압축 비율: {actual_data_count}/{total_seconds} = {actual_data_count/total_seconds*100:.1f}%")
        
        # 메모리 사용량 추정
        estimated_mb = total_seconds * 0.5 / 1024  # 대략적 추정
        print(f"{LOG_PREFIX} 예상 메모리 사용량: ~{estimated_mb:.1f} MB")
        
        # 샘플 확인
        sample_keys = list(self._second_timeline.keys())[:3]
        print(f"{LOG_PREFIX} 샘플 키: {sample_keys}")
    else:
        print(f"{LOG_PREFIX} ❌ 사전 계산된 초가 없습니다!")
