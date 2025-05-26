# controller.py - 기존 기능 유지 + 성능 모니터링 추가

from pxr import Usd, UsdGeom, Sdf
import omni.usd
import datetime
import time
import omni.timeline
import os
import csv
from datetime import datetime as dt
import random

# 성능 모니터링 임포트 (새로 추가)
from .performance_monitor import performance_monitor, monitor_performance, OperationTimer

class TimeController:
    """USD Stage의 시간을 관리하고 데이터센터 센서 데이터를 연동하는 컨트롤러 (성능 모니터링 추가)"""
    
    def __init__(self):
        """시간 컨트롤러 초기화"""
        # 성능 모니터링 시작 (새로 추가)
        with performance_monitor.start_operation("controller_init") as timer:
            
            # 기존 초기화 코드 그대로 유지
            self._usd_context = omni.usd.get_context()
            self._timeline = omni.timeline.get_timeline_interface()
            self._time_manager_path = "/World/TimeManager"
            
            # 성능 관련 설정 (새로 추가)
            self._performance_mode = True
            self._batch_size = 10
            self._data_cache = {}
            self._cache_expiry = {}
            self._cache_duration = 5.0
            self._last_update_metrics = time.time()
            
            # 기존 데이터 초기화 - 스테이지에서 랙 검색 및 속성 초기화
            self._initialize_rack_attributes()
            
            # 랙 목록 및 매핑 초기화
            self._rack_paths = []
            self._rack_to_sensor_map = {}
            self._load_rack_paths()
            
            # 센서 데이터 초기화
            self._sensor_data = {}
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
            
            # 성능 모니터링 정보 설정 (새로 추가)
            timer.set_data_info(
                rack_count=len(self._rack_to_sensor_map),
                data_points=sum(len(data) for data in self._sensor_data.values())
            )
    
    # 기존 _initialize_rack_attributes 메서드 그대로 유지
    def _initialize_rack_attributes(self):
        """스테이지에서 모든 랙을 검색하고 속성을 초기화"""
        print("[netai.timetravel.demo] 기존 랙 속성 초기화 중...")
        
        stage = self._usd_context.get_stage()
        if not stage:
            print("[netai.timetravel.demo] 스테이지를 찾을 수 없어 초기화를 건너뜁니다.")
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
                    print(f"[netai.timetravel.demo] {base_path} 경로에서 {initialized_count}개 랙 속성 초기화 완료")
                
            except Exception as e:
                print(f"[netai.timetravel.demo] 랙 검색 중 오류: {e}")
    
    # 기존 _reset_rack_attributes 메서드 그대로 유지
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
                "temperature_cold", "temperature_hot", 
                "humidity_cold", "humidity_hot"
            ]
            
            for attr_name in temp_attrs:
                if rack_prim.HasAttribute(attr_name):
                    rack_prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float).Set(float('nan'))
            
            # 메타데이터 초기화
            metadata_keys = [
                "temperature_cold", "temperature_hot", 
                "humidity_cold", "humidity_hot",
                "timestamp", "sensor_id", "data_source"
            ]
            
            for key in metadata_keys:
                rack_prim.SetCustomDataByKey(key, "N/A")
            
            rack_prim.SetCustomDataByKey("initialized", f"{datetime.datetime.now()}")
            
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙 속성 초기화 오류 ({rack_path}): {e}")
    
    # 기존 _load_rack_paths 메서드 그대로 유지
    def _load_rack_paths(self):
        """랙 경로 목록 로드"""
        try:
            rack_dir_path = os.path.join(os.path.dirname(__file__), "rack_directory.txt")
            rack_map_path = os.path.join(os.path.dirname(__file__), "rack_sensor_map.txt")
            
            print(f"[netai.timetravel.demo] 랙 디렉토리 파일 경로: {rack_dir_path}")
            print(f"[netai.timetravel.demo] 현재 작업 디렉토리: {os.getcwd()}")
            
            if os.path.exists(rack_dir_path):
                with open(rack_dir_path, 'r') as file:
                    content = file.read().strip()
                    self._rack_paths = content.split()
                
                print(f"[netai.timetravel.demo] 로드된 랙 수: {len(self._rack_paths)}")
                if self._rack_paths:
                    print(f"[netai.timetravel.demo] 첫 번째 랙 경로 예시: {self._rack_paths[0]}")
                
                # USD 스테이지에서 실제 경로 확인
                stage = self._usd_context.get_stage()
                if stage:
                    for path in self._rack_paths[:5]:
                        prim = stage.GetPrimAtPath(path)
                        print(f"[netai.timetravel.demo] 경로 확인: {path} - 존재: {prim.IsValid() if prim else False}")
                
                # 랙-센서 매핑 파일이 있는지 확인
                if os.path.exists(rack_map_path):
                    self._load_rack_sensor_map(rack_map_path)
                else:
                    print(f"[netai.timetravel.demo] 랙-센서 매핑 파일이 없어 임시 매핑을 생성합니다.")
                    self._create_temporary_mapping()
            else:
                print(f"[netai.timetravel.demo] 랙 디렉토리 파일을 찾을 수 없음: {rack_dir_path}")
                self._create_test_rack_paths()
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙 경로 로드 오류: {e}")
            self._create_test_rack_paths()
    
    # 기존 _load_rack_sensor_map 메서드 그대로 유지
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
            
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 로드 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
        except Exception as e:
            print(f"[netai.timetravel.demo] 랙-센서 매핑 파일 로드 오류: {e}")
            self._create_temporary_mapping()
    
    # 기존 _create_test_rack_paths 메서드 그대로 유지
    def _create_test_rack_paths(self):
        """테스트용 랙 경로 생성"""
        print("[netai.timetravel.demo] 테스트용 랙 경로 생성 중...")
        
        stage = self._usd_context.get_stage()
        real_paths = []
        
        if stage:
            patterns = [
                "/Root/datacenter/RACK_A{i}",
                "/Root/datacenter/RACK_B{i}",
                "/World/Root/datacenter/RACK_A{i}",
                "/World/Root/datacenter/RACK_B{i}"
            ]
            
            for pattern in patterns:
                for i in range(20):
                    path = pattern.format(i=i)
                    prim = stage.GetPrimAtPath(path)
                    if prim and prim.IsValid():
                        real_paths.append(path)
                        print(f"[netai.timetravel.demo] 실제 랙 찾음: {path}")
                        if len(real_paths) >= 24:
                            break
                if len(real_paths) >= 24:
                    break
            
            if real_paths:
                self._rack_paths = real_paths
                print(f"[netai.timetravel.demo] 실제 랙 경로 {len(real_paths)}개 찾음")
            else:
                self._rack_paths = [f"/Root/datacenter/RACK_A{i}" for i in range(24)]
                print("[netai.timetravel.demo] 실제 랙 경로를 찾지 못해 가상 경로 생성")
        else:
            self._rack_paths = [f"/Root/datacenter/RACK_A{i}" for i in range(24)]
            print("[netai.timetravel.demo] 스테이지 없음, 가상 랙 경로 생성")
            
        self._create_temporary_mapping()
        
    # 기존 _create_temporary_mapping 메서드 그대로 유지
    def _create_temporary_mapping(self):
        """임시 랙-센서 매핑 생성 (objId 20-25, 191-208 사용)"""
        sensor_ids = [str(i) for i in range(20, 26)] + [str(i) for i in range(191, 209)]
        print(f"[netai.timetravel.demo] 사용 가능한 센서 ID: {', '.join(sensor_ids)}")
        
        if self._rack_paths and sensor_ids:
            self._rack_to_sensor_map.clear()
            
            selected_racks = self._rack_paths.copy()
            if len(selected_racks) > len(sensor_ids):
                selected_racks = random.sample(selected_racks, len(sensor_ids))
            
            for i, rack_path in enumerate(selected_racks):
                if i < len(sensor_ids):
                    self._rack_to_sensor_map[rack_path] = sensor_ids[i]
            
            print(f"[netai.timetravel.demo] 임시 랙-센서 매핑 생성 완료. 매핑된 랙 수: {len(self._rack_to_sensor_map)}")
            
            for rack_path, sensor_id in self._rack_to_sensor_map.items():
                print(f"[netai.timetravel.demo] 매핑: {rack_path} -> {sensor_id}")
        else:
            print("[netai.timetravel.demo] 랙 경로 또는 센서 ID가 부족하여 매핑을 생성할 수 없음")
    
    # 기존 save_rack_sensor_map 메서드 그대로 유지
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
    
    # 기존 _load_sensor_data 메서드에 성능 모니터링만 추가
    def _load_sensor_data(self):
        """CSV 파일에서 센서 데이터 로드 (성능 모니터링 추가)"""
        with performance_monitor.start_operation("load_sensor_data") as timer:
            try:
                csv_path = os.path.join(os.path.dirname(__file__), "fms_temphum_0327.csv")
                
                if not os.path.exists(csv_path):
                    csv_path = os.path.join(os.path.dirname(__file__), "fms_temphum_objId21_last24h.csv")
                    print(f"[netai.timetravel.demo] fms_temphum_0327.csv 파일이 없습니다: {csv_path}")
                
                with open(csv_path, 'r') as file:
                    reader = csv.DictReader(file)
                    data_list = list(reader)
                
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
                
                # 각 센서 데이터를 타임스탬프 기준으로 정렬 (주석 해제!)
                for obj_id in self._sensor_data:
                    self._sensor_data[obj_id].sort(key=lambda x: x["@timestamp"])
                
                # 결과 요약
                total_entries = sum(len(data) for data in self._sensor_data.values())
                print(f"[netai.timetravel.demo] 로드된 센서 데이터: {total_entries}개, 센서 수: {len(self._sensor_data)}")
                
                sensor_ids = list(self._sensor_data.keys())
                print(f"[netai.timetravel.demo] 센서 ID: {', '.join(sensor_ids[:10])}{'...' if len(sensor_ids) > 10 else ''}")
                
                # 성능 모니터링 정보 설정
                timer.set_data_info(rack_count=0, data_points=total_entries)
                
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
            # 데이터가 없으면 속성을 비워두거나 초기화합니다
            print(f"[netai.timetravel.demo] 랙({rack_path})의 데이터 없음, 속성 초기화")
            try:
                stage = self._usd_context.get_stage()
                if not stage:
                    return
                    
                rack_prim = stage.GetPrimAtPath(rack_path)
                if not rack_prim or not rack_prim.IsValid():
                    print(f"[netai.timetravel.demo] 랙 객체를 찾을 수 없음: {rack_path}")
                    return
                
                # 기존 속성이 있으면 N/A 값으로 표시
                if rack_prim.HasAttribute("temperature_cold"):
                    rack_prim.CreateAttribute("temperature_cold", Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute("temperature_hot"):
                    rack_prim.CreateAttribute("temperature_hot", Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute("humidity_cold"):
                    rack_prim.CreateAttribute("humidity_cold", Sdf.ValueTypeNames.Float).Set(float('nan'))
                if rack_prim.HasAttribute("humidity_hot"):
                    rack_prim.CreateAttribute("humidity_hot", Sdf.ValueTypeNames.Float).Set(float('nan'))
                
                # 메타데이터도 초기화
                rack_prim.SetCustomDataByKey("temperature_cold", "N/A")
                rack_prim.SetCustomDataByKey("temperature_hot", "N/A")
                rack_prim.SetCustomDataByKey("humidity_cold", "N/A")
                rack_prim.SetCustomDataByKey("humidity_hot", "N/A")
                rack_prim.SetCustomDataByKey("timestamp", "N/A")
                rack_prim.SetCustomDataByKey("sensor_id", "None")
                
            except Exception as e:
                print(f"[netai.timetravel.demo] 객체 속성 초기화 오류 ({rack_path}): {e}")
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
            
            # 유효한 값인지 확인
            try:
                temp1 = float(temp1)
                temp2 = float(temp2)
                hum1 = float(hum1)
                hum2 = float(hum2)
            except (ValueError, TypeError):
                print(f"[netai.timetravel.demo] 유효하지 않은 데이터 값 - 기본값 사용")
                temp1 = temp2 = hum1 = hum2 = 0.0
            
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
            rack_prim.SetCustomDataByKey("timestamp", data_entry.get("@timestamp", "Unknown"))
            rack_prim.SetCustomDataByKey("sensor_id", data_entry.get("objId", "Unknown"))
            
            # 데이터 출처 명시적으로 기록
            rack_prim.SetCustomDataByKey("data_source", "sensor_data")
            
        except Exception as e:
            print(f"[netai.timetravel.demo] 객체 속성 업데이트 오류 ({rack_path}): {e}")
    
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
    
    def _update_all_racks(self):
        """모든 랙의 속성 업데이트"""
        updated_count = 0
        missing_count = 0
        
        # 모든 랙 경로 순회
        for rack_path in self._rack_paths:
            # 센서 ID 확인
            sensor_id = self.get_sensor_id_for_rack(rack_path)
            
            if sensor_id and sensor_id in self._sensor_data:
                # 센서 데이터가 있는 경우
                data_entry = self._find_closest_data_entry(self._current_time, sensor_id)
                if data_entry:
                    self._update_rack_attributes(rack_path, data_entry)
                    updated_count += 1
                else:
                    # 데이터는 없지만 센서 ID는 있는 경우
                    self._update_rack_attributes(rack_path, None)
                    missing_count += 1
            else:
                # 센서 ID가 없거나 데이터가 없는 경우
                self._update_rack_attributes(rack_path, None)
                missing_count += 1
        
        # 결과 로그
        if updated_count > 0 or missing_count > 0:
            print(f"[netai.timetravel.demo] 랙 업데이트: {updated_count}개 업데이트, {missing_count}개 데이터 없음")
        
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
                    time_prim.SetCustomDataByKey("lastUpdated", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z")
                    
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
# controller.py에 추가해야 할 성능 관련 메서드들

    def optimize_performance(self):
        """성능 최적화 수행"""
        print("[Performance] 성능 최적화 시작...")
        
        # 1. 캐시 정리
        current_time = time.time()
        expired_keys = [
            key for key, expiry_time in self._cache_expiry.items()
            if current_time > expiry_time
        ]
        
        for key in expired_keys:
            self._data_cache.pop(key, None)
            self._cache_expiry.pop(key, None)
        
        print(f"[Performance] 만료된 캐시 {len(expired_keys)}개 정리 완료")
        
        # 2. 메모리 사용량 체크
        system_metrics = performance_monitor.get_current_system_metrics()
        memory_increase = system_metrics['memory_increase_mb']
        
        if memory_increase > 200:  # 200MB 이상 증가 시
            print(f"[Performance] 메모리 사용량 높음: +{memory_increase:.1f}MB")
            
            # 캐시 크기 줄이기
            if len(self._data_cache) > 100:
                # 오래된 캐시 항목 절반 제거
                sorted_cache = sorted(
                    self._cache_expiry.items(),
                    key=lambda x: x[1]
                )
                
                keys_to_remove = [key for key, _ in sorted_cache[:len(sorted_cache)//2]]
                for key in keys_to_remove:
                    self._data_cache.pop(key, None)
                    self._cache_expiry.pop(key, None)
                
                print(f"[Performance] 캐시 항목 {len(keys_to_remove)}개 제거")

    def clear_performance_data(self):
        """성능 데이터 초기화"""
        performance_monitor.metrics_queue.clear()
        performance_monitor.operation_stats.clear()
        print("[Performance] 성능 데이터 초기화 완료")

    def export_performance_data(self, filename=None):
        """성능 데이터 내보내기"""
        if not filename:
            filename = f"performance_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 통계 데이터 수집
        export_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'overall_stats': performance_monitor.get_statistics(),
            'operation_stats': {},
            'system_info': performance_monitor.get_current_system_metrics(),
            'thresholds': performance_monitor.thresholds
        }
        
        # 각 작업별 통계
        for operation in performance_monitor.operation_stats.keys():
            export_data['operation_stats'][operation] = performance_monitor.get_statistics(operation)
        
        # JSON 파일로 저장
        import json
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"[Performance] 성능 데이터 내보내기 완료: {filename}")
        return filename

    def set_performance_mode(self, enabled: bool, batch_size: int = 10):
        """성능 모드 설정"""
        self._performance_mode = enabled
        self._batch_size = batch_size
        
        if enabled:
            print(f"[Performance] 성능 모드 활성화 (배치 크기: {batch_size})")
        else:
            print("[Performance] 성능 모드 비활성화")

    def print_performance_summary(self):
        """성능 요약 출력"""
        print("\n[Performance Summary]")
        performance_monitor.print_report()
        
        # 캐시 통계
        print(f"캐시 항목 수: {len(self._data_cache)}")
        print(f"캐시 적중률: {self._calculate_cache_hit_rate():.1f}%")

    def _calculate_cache_hit_rate(self):
        """캐시 적중률 계산 (간단한 추정)"""
        total_operations = len(performance_monitor.operation_stats.get("find_closest_data", []))
        if total_operations == 0:
            return 0.0
        
        # 캐시 크기 기반 추정 (실제로는 정확한 카운터 필요)
        estimated_hits = min(len(self._data_cache) * 2, total_operations)
        return (estimated_hits / total_operations) * 100
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
        sensor_data_map = {}
        for sensor_id in self._sensor_data.keys():
            data_entry = self._find_closest_data_entry(self._current_time, sensor_id)
            if data_entry:
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
        return len(self._sensor_data)
    
    def on_shutdown(self):
        """익스텐션 종료 시 정리 작업"""
        print("[netai.timetravel.demo] 컨트롤러 종료 중...")
        
        # 모든 랙 속성 초기화
        try:
            self._clear_all_rack_attributes()
        except Exception as e:
            print(f"[netai.timetravel.demo] 종료 시 정리 작업 오류: {e}")
    
    def _clear_all_rack_attributes(self):
        """모든 랙 속성 초기화 (종료 시 호출)"""
        print("[netai.timetravel.demo] 모든 랙 속성 초기화 중...")
        
        for rack_path in self._rack_paths:
            self._reset_rack_attributes(rack_path)
    
    

