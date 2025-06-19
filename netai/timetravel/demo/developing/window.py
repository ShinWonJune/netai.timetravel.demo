# -*- coding: utf-8 -*-
import omni.ui as ui
import datetime
import omni.usd
from pxr import Usd, UsdGeom

class TimeWindowUI:
    """Time Travel Window for Datacenter Digital Twin"""
    
    def __init__(self, controller):
        """Time window UI initialization"""
        self._controller = controller
        self._selected_rack_path = None
        self._selected_rack_data = None
        
        # 윈도우 생성
        self._window = ui.Window("Time Travel", width=550, height=500)
        
        # 선택 리스너 관련 변수
        self._usd_context = omni.usd.get_context()
        self._selection_changed_sub = None
        
        # 데이터 로딩 상태 추적
        self._last_data_load_time = None
        self._data_loading = False
        
        # UI 요소 레퍼런스 초기화
        self._start_year = None
        self._start_month = None
        self._start_day = None
        self._start_hour = None
        self._start_minute = None
        self._start_second = None
        self._end_year = None
        self._end_month = None
        self._end_day = None
        self._end_hour = None
        self._end_minute = None
        self._end_second = None
        self._goto_year = None
        self._goto_month = None
        self._goto_day = None
        self._goto_hour = None
        self._goto_minute = None
        self._goto_second = None
        self._apply_button = None
        self._present_button = None
        self._goto_button = None
        self._stage_time_label = None
        self._play_button = None
        self._speed_field = None
        self._selected_rack_label = None
        self._cold_temp_label = None
        self._cold_humidity_label = None
        self._hot_temp_label = None
        self._hot_humidity_label = None
        self._time_slider = None
        self._rack_count_label = None
        self._sensor_count_label = None
        self._data_status_label = None  # 데이터 로딩 상태 표시
        
        # UI 생성
        self._create_ui()
        
        # UI 생성 완료 후 선택 리스너 설정
        self._setup_selection_listener()
        
        # 초기 데이터 상태 확인
        self._check_initial_data_state()
    
    def _check_initial_data_state(self):
        """초기 데이터 상태 확인"""
        try:
            print(f"[netai.timetravel.demo] 초기 데이터 상태 확인 시작")
            
            # 컨트롤러 상태 확인
            if hasattr(self._controller, '_data_cache') and self._controller._data_cache:
                print(f"[netai.timetravel.demo] 데이터 캐시 존재: {self._controller._data_cache}")
                
                # 센서 ID 확인
                try:
                    sensor_ids = self._controller._data_cache.get_sensor_ids()
                    print(f"[netai.timetravel.demo] 로드된 센서 개수: {len(sensor_ids)}")
                    print(f"[netai.timetravel.demo] 센서 ID 샘플: {list(sensor_ids)[:5]}")
                except Exception as e:
                    print(f"[netai.timetravel.demo] 센서 ID 가져오기 오류: {e}")
                
                # 시간 범위 확인
                start_time = self._controller.get_start_time()
                end_time = self._controller.get_end_time()
                current_time = self._controller.get_current_time()
                
                print(f"[netai.timetravel.demo] 시간 범위: {start_time} ~ {end_time}")
                print(f"[netai.timetravel.demo] 현재 시간: {current_time}")
                
                # 랙 매핑 확인
                if hasattr(self._controller, '_rack_to_sensor_map'):
                    rack_map = self._controller._rack_to_sensor_map
                    print(f"[netai.timetravel.demo] 랙 매핑 개수: {len(rack_map)}")
                    if rack_map:
                        print(f"[netai.timetravel.demo] 랙 매핑 샘플:")
                        for i, (rack_path, sensor_id) in enumerate(list(rack_map.items())[:3]):
                            print(f"  {i+1}. {rack_path} -> {sensor_id}")
                else:
                    print(f"[netai.timetravel.demo] 랙 매핑이 없음")
            else:
                print(f"[netai.timetravel.demo] 데이터 캐시가 없음 - 초기 로딩 필요")
                
        except Exception as e:
            print(f"[netai.timetravel.demo] 초기 데이터 상태 확인 오류: {e}")
    
    def _create_ui(self):
        """UI 생성"""
        with self._window.frame:
            with ui.VStack(spacing=5):
                # 1. 상단 섹션: 제목
                with ui.HStack(height=30):
                    ui.Label("Time Setting", style={"font_size": 18})
                
                # 2. Time Window UI
                with ui.VStack(spacing=3):
                    # 시작 시간 입력
                    with ui.HStack(height=20):
                        ui.Label("Start:", width=50)
                        self._start_year = ui.IntField(width=40)
                        self._start_year.model.set_value(self._get_safe_start_time().year)
                        ui.Label("/", width=10)
                        self._start_month = ui.IntField(width=30)
                        self._start_month.model.set_value(self._get_safe_start_time().month)
                        ui.Label("/", width=10)
                        self._start_day = ui.IntField(width=30)
                        self._start_day.model.set_value(self._get_safe_start_time().day)
                        ui.Label(" ", width=10)
                        self._start_hour = ui.IntField(width=30)
                        self._start_hour.model.set_value(self._get_safe_start_time().hour)
                        ui.Label(":", width=10)
                        self._start_minute = ui.IntField(width=30)
                        self._start_minute.model.set_value(self._get_safe_start_time().minute)
                        ui.Label(":", width=10)
                        self._start_second = ui.IntField(width=30)
                        self._start_second.model.set_value(self._get_safe_start_time().second)
                    
                    # 종료 시간 입력
                    with ui.HStack(height=20):
                        ui.Label("End:", width=50)
                        self._end_year = ui.IntField(width=40)
                        self._end_year.model.set_value(self._get_safe_end_time().year)
                        ui.Label("/", width=10)
                        self._end_month = ui.IntField(width=30)
                        self._end_month.model.set_value(self._get_safe_end_time().month)
                        ui.Label("/", width=10)
                        self._end_day = ui.IntField(width=30)
                        self._end_day.model.set_value(self._get_safe_end_time().day)
                        ui.Label(" ", width=10)
                        self._end_hour = ui.IntField(width=30)
                        self._end_hour.model.set_value(self._get_safe_end_time().hour)
                        ui.Label(":", width=10)
                        self._end_minute = ui.IntField(width=30)
                        self._end_minute.model.set_value(self._get_safe_end_time().minute)
                        ui.Label(":", width=10)
                        self._end_second = ui.IntField(width=30)
                        self._end_second.model.set_value(self._get_safe_end_time().second)
                    
                    # Apply 버튼과 데이터 상태
                    with ui.HStack(height=20):
                        ui.Spacer(width=5)
                        self._apply_button = ui.Button("Apply", width=60)
                        self._apply_button.set_clicked_fn(lambda: self._on_apply_clicked())
                        ui.Spacer(width=5)
                        self._present_button = ui.Button("Present", width=60)
                        self._present_button.set_clicked_fn(lambda: self._on_present_clicked())
                        ui.Spacer(width=5)
                        # MinIO 테스트 버튼 추가
                        self._test_button = ui.Button("Test MinIO", width=80)
                        self._test_button.set_clicked_fn(lambda: self._on_test_minio_clicked())
                        ui.Spacer(width=10)
                        # 데이터 로딩 상태 표시
                        self._data_status_label = ui.Label("Ready", width=80, style={"color": 0xFF00FF00})
                    
                    # Go to time
                    with ui.HStack(height=20):
                        ui.Label("Go to:", width=50)
                        self._goto_year = ui.IntField(width=40)
                        self._goto_year.model.set_value(self._get_safe_current_time().year)
                        ui.Label("/", width=10)
                        self._goto_month = ui.IntField(width=30)
                        self._goto_month.model.set_value(self._get_safe_current_time().month)
                        ui.Label("/", width=10)
                        self._goto_day = ui.IntField(width=30)
                        self._goto_day.model.set_value(self._get_safe_current_time().day)
                        ui.Label(" ", width=10)
                        self._goto_hour = ui.IntField(width=30)
                        self._goto_hour.model.set_value(self._get_safe_current_time().hour)
                        ui.Label(":", width=10)
                        self._goto_minute = ui.IntField(width=30)
                        self._goto_minute.model.set_value(self._get_safe_current_time().minute)
                        ui.Label(":", width=10)
                        self._goto_second = ui.IntField(width=30)
                        self._goto_second.model.set_value(self._get_safe_current_time().second)
                        self._goto_button = ui.Button("Go", width=40)
                        self._goto_button.set_clicked_fn(lambda: self._on_goto_clicked())
                        
                # 3. 수평선 추가하여 섹션 구분
                with ui.HStack(height=2):
                    ui.Spacer(width=10)
                    ui.Line(style_type_name_override="border_color", style={"color": 0xFF666666})
                    ui.Spacer(width=10)    

                # USD Stage time display
                with ui.HStack(height=20):
                    ui.Label("USD Stage Time: ", width=120, style={"font_size": 18})
                    self._stage_time_label = ui.Label("", width=280, style={"font_size": 18})
                    
                # Playback controls
                with ui.HStack(height=30):
                    self._play_button = ui.Button("Play", width=60)
                    self._play_button.set_clicked_fn(lambda: self._on_play_clicked())
                    ui.Spacer(width=10)
                    ui.Label("Speed:", width=40)
                    self._speed_field = ui.FloatField(width=40)
                    self._speed_field.model.set_value(self._get_safe_playback_speed())
                    self._speed_field.model.add_end_edit_fn(self._on_speed_changed)
                
                # 수평선 추가하여 섹션 구분
                with ui.HStack(height=5):
                    ui.Spacer(width=10)
                    ui.Line(style_type_name_override="border_color", style={"color": 0xFF666666})
                    ui.Spacer(width=10)
                
                # 4. Selected Rack Info 섹션
                with ui.HStack(height=20):
                    ui.Label("Selected Rack Info", style={"font_size": 18})
                    
                # Rack Path
                with ui.HStack(height=20):
                    ui.Label("Rack Path:", width=80)
                    self._selected_rack_label = ui.Label("None", width=ui.Percent(100))
                    
                # Aisle 데이터
                with ui.HStack(height=30, spacing=10):
                    # Cold Aisle
                    with ui.CollapsableFrame("Cold Aisle", height=70, width=50):
                        with ui.VStack(spacing=5):
                            with ui.HStack(height=25):
                                ui.Label("Temperature:", width=85)
                                self._cold_temp_label = ui.Label("N/A", width=50)
                                ui.Label("°C", width=30)
                            
                            with ui.HStack(height=25):
                                ui.Label("Humidity:", width=85)
                                self._cold_humidity_label = ui.Label("N/A", width=50)
                                ui.Label("%", width=30)
                    
                    # Hot Aisle
                    with ui.CollapsableFrame("Hot Aisle", height=70, width=50):
                        with ui.VStack(spacing=5):
                            with ui.HStack(height=25):
                                ui.Label("Temperature:", width=85)
                                self._hot_temp_label = ui.Label("N/A", width=50)
                                ui.Label("°C", width=30)
                            
                            with ui.HStack(height=25):
                                ui.Label("Humidity:", width=85)
                                self._hot_humidity_label = ui.Label("N/A", width=50)
                                ui.Label("%", width=30)
                
                # 수평선 추가하여 섹션 구분
                with ui.HStack(height=2):
                    ui.Spacer(width=10)
                    ui.Line(style_type_name_override="border_color", style={"color": 0xFF666666})
                    ui.Spacer(width=10)
                
                # 6. 하단 섹션: 슬라이더
                with ui.HStack(height=30):
                    ui.Spacer(width=10)
                    self._time_slider = ui.FloatSlider(min=0.0, max=1.0, width=480)
                    self._time_slider.model.set_value(self._get_safe_time_progress())
                    self._time_slider.model.add_value_changed_fn(self._on_slider_changed)
                    ui.Spacer(width=20)
                
                # 7. 데이터 요약
                with ui.HStack(height=10):
                    ui.Spacer(width=10)
                    ui.Label("Racks Mapped:", width=90)
                    self._rack_count_label = ui.Label(f"{self._get_rack_count()}", width=40)
                    ui.Spacer(width=20)
                    ui.Label("Number of sensors:", width=120)
                    self._sensor_count_label = ui.Label(f"{self._get_sensor_count()}", width=40)
                    ui.Spacer(width=10)
    
    def _update_data_status(self, status, color=0xFF00FF00):
        """데이터 상태 업데이트"""
        if self._data_status_label:
            self._data_status_label.text = status
            self._data_status_label.style = {"color": color}
    
    # 안전한 데이터 접근 메서드들
    def _get_safe_start_time(self):
        """안전한 시작 시간 반환"""
        try:
            start_time = self._controller.get_start_time()
            if start_time:
                return start_time
        except:
            pass
        return datetime.datetime(2025, 5, 22, 0, 0, 0)
    
    def _get_safe_end_time(self):
        """안전한 종료 시간 반환"""
        try:
            end_time = self._controller.get_end_time()
            if end_time:
                return end_time
        except:
            pass
        return datetime.datetime(2025, 5, 31, 23, 59, 59)
    
    def _get_safe_current_time(self):
        """안전한 현재 시간 반환"""
        try:
            current_time = self._controller.get_current_time()
            if current_time:
                return current_time
        except:
            pass
        return self._get_safe_start_time()
    
    def _get_safe_playback_speed(self):
        """안전한 재생 속도 반환"""
        try:
            return self._controller._playback_speed
        except:
            return 1.0
    
    def _get_safe_time_progress(self):
        """안전한 시간 진행률 반환"""
        try:
            return self._controller.get_time_progress()
        except:
            return 0.0
    
    def _get_rack_count(self):
        """매핑된 랙 개수 반환"""
        try:
            if hasattr(self._controller, '_rack_to_sensor_map'):
                return len(self._controller._rack_to_sensor_map)
            return 0
        except Exception as e:
            print(f"[netai.timetravel.demo] Error getting rack count: {e}")
            return 0
    
    def _get_sensor_count(self):
        """활성 센서 개수 반환"""
        try:
            if hasattr(self._controller, '_data_cache') and self._controller._data_cache:
                sensor_ids = self._controller._data_cache.get_sensor_ids()
                return len(sensor_ids)
            return 0
        except Exception as e:
            print(f"[netai.timetravel.demo] Error getting sensor count: {e}")
            return 0
    
    def _get_rack_name(self, rack_path):
        """랙 경로에서 랙 이름 추출"""
        if rack_path:
            parts = rack_path.split('/')
            for part in reversed(parts):
                if 'RACK' in part:
                    return part
            return parts[-1] if parts else "Unknown"
        return "None"
    
    def _setup_selection_listener(self):
        """선택 이벤트 리스너 설정"""
        try:
            if self._usd_context:
                events = self._usd_context.get_stage_event_stream()
                self._selection_changed_sub = events.create_subscription_to_pop(
                    self._handle_stage_event, name="selection_changed_sub"
                )
                print("[netai.timetravel.demo] 선택 이벤트 리스너 설정 완료")
        except Exception as e:
            print(f"[netai.timetravel.demo] Error setting up selection listener: {e}")
    
    def _handle_stage_event(self, event):
        """스테이지 이벤트 핸들러"""
        try:
            import omni.usd
            if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
                self._check_selected_prim()
        except Exception as e:
            print(f"[netai.timetravel.demo] Error handling stage event: {e}")
    
    def _check_selected_prim(self):
        """현재 선택된 프림 확인"""
        try:
            if not self._usd_context:
                return
                
            stage = self._usd_context.get_stage()
            if not stage:
                return
            
            # UI가 완전히 초기화되었는지 확인
            if not self._selected_rack_label or not self._cold_temp_label:
                return
                
            # 현재 선택된 프림 경로 가져오기
            selection = self._usd_context.get_selection()
            selected_paths = selection.get_selected_prim_paths()
            
            if selected_paths:
                selected_path = selected_paths[0]
                print(f"[netai.timetravel.demo] 선택된 프림 경로: {selected_path}")
                
                # 랙 경로인지 확인 (조건 완화)
                if "RACK" in selected_path:
                    self._handle_rack_selection(selected_path)
                else:
                    self._clear_rack_selection("None (Not a Rack)")
            else:
                self._clear_rack_selection("None")
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in _check_selected_prim: {e}")
    
    def _handle_rack_selection(self, selected_path):
        """랙 선택 처리 - 개선된 매칭 및 데이터 로딩"""
        try:
            print(f"[netai.timetravel.demo] 랙 선택 처리 시작: {selected_path}")
            
            if not hasattr(self._controller, '_rack_to_sensor_map'):
                print("[netai.timetravel.demo] Controller에 rack_to_sensor_map이 없음")
                self._clear_rack_selection("Controller not ready")
                return
                
            rack_mapping = self._controller._rack_to_sensor_map
            print(f"[netai.timetravel.demo] 현재 랙 매핑 개수: {len(rack_mapping)}")
            
            # 랙 매핑이 비어있는 경우 데이터 로딩 시도
            if not rack_mapping:
                print("[netai.timetravel.demo] 랙 매핑이 비어있음 - 데이터 로딩 시도")
                self._load_data_for_current_time_range()
                return
            
            # 1단계: 정확한 경로 매칭
            if selected_path in rack_mapping:
                self._selected_rack_path = selected_path
                sensor_id = rack_mapping[selected_path]
                print(f"[netai.timetravel.demo] 정확한 매칭 성공: {selected_path} -> 센서 ID: {sensor_id}")
            else:
                # 2단계: 고급 매칭 시도
                matched_path = self._find_best_matching_rack_path(selected_path, rack_mapping)
                if matched_path:
                    self._selected_rack_path = matched_path
                    sensor_id = rack_mapping[matched_path]
                    print(f"[netai.timetravel.demo] 고급 매칭 성공: {selected_path} -> {matched_path} -> 센서 ID: {sensor_id}")
                else:
                    self._selected_rack_path = None
                    print(f"[netai.timetravel.demo] 매핑 실패: {selected_path}")
                    # 사용 가능한 랙 경로 출력
                    print(f"[netai.timetravel.demo] 사용 가능한 랙 경로들:")
                    for i, rack_path in enumerate(rack_mapping.keys(), 1):
                        print(f"  {i}. {rack_path}")
            
            # UI 업데이트
            self._update_rack_label(selected_path, rack_mapping)
            
            # 센서 데이터 업데이트
            self._update_selected_rack_data()
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error handling rack selection: {e}")
            import traceback
            print(f"[netai.timetravel.demo] Traceback: {traceback.format_exc()}")
            self._clear_rack_selection("Error")
    
    def _find_best_matching_rack_path(self, selected_path, rack_mapping):
        """최적의 매칭 랙 경로 찾기 - 6단계 매칭 로직"""
        try:
            print(f"[netai.timetravel.demo] 고급 매칭 시작: {selected_path}")
            
            # 1단계: 부분 문자열 매칭
            for rack_path in rack_mapping.keys():
                if selected_path in rack_path or rack_path in selected_path:
                    print(f"[netai.timetravel.demo] 부분 매칭 성공: {selected_path} -> {rack_path}")
                    return rack_path
            
            # 2단계: 번호 기반 매칭
            import re
            selected_number_match = re.search(r'RACK[_\-]?(\d+)', selected_path.upper())
            if selected_number_match:
                selected_number = selected_number_match.group(1)
                print(f"[netai.timetravel.demo] 선택된 랙 번호: {selected_number}")
                
                for rack_path in rack_mapping.keys():
                    rack_number_match = re.search(r'RACK[_\-]?(\d+)', rack_path.upper())
                    if rack_number_match:
                        rack_number = rack_number_match.group(1)
                        if selected_number == rack_number:
                            print(f"[netai.timetravel.demo] 번호 매칭 성공: {selected_path} -> {rack_path}")
                            return rack_path
            
            # 3단계: 랙 이름 매칭
            selected_parts = selected_path.split('/')
            selected_rack_name = None
            
            for part in reversed(selected_parts):
                if 'RACK' in part.upper():
                    selected_rack_name = part
                    break
            
            if selected_rack_name:
                print(f"[netai.timetravel.demo] 선택된 랙 이름: {selected_rack_name}")
                for rack_path in rack_mapping.keys():
                    rack_parts = rack_path.split('/')
                    for rack_part in reversed(rack_parts):
                        if 'RACK' in rack_part.upper():
                            if selected_rack_name.upper() == rack_part.upper():
                                print(f"[netai.timetravel.demo] 이름 매칭 성공: {selected_path} -> {rack_path}")
                                return rack_path
                            break
            
            # 4단계: 유사도 매칭
            best_match = None
            best_score = 0
            
            selected_parts_set = set(selected_path.split('/'))
            
            for rack_path in rack_mapping.keys():
                rack_parts_set = set(rack_path.split('/'))
                common_parts = selected_parts_set & rack_parts_set
                score = len(common_parts)
                
                # RACK 관련 부분 가중치 추가
                selected_rack_parts = [part for part in selected_parts_set if 'RACK' in part.upper()]
                rack_rack_parts = [part for part in rack_parts_set if 'RACK' in part.upper()]
                
                if selected_rack_parts and rack_rack_parts:
                    for sel_rack in selected_rack_parts:
                        for map_rack in rack_rack_parts:
                            if sel_rack.upper() == map_rack.upper():
                                score += 10
                            elif sel_rack.upper() in map_rack.upper() or map_rack.upper() in sel_rack.upper():
                                score += 5
                
                if score > best_score:
                    best_score = score
                    best_match = rack_path
            
            if best_match and best_score > 0:
                print(f"[netai.timetravel.demo] 유사도 매칭 성공 (점수 {best_score}): {selected_path} -> {best_match}")
                return best_match
            
            print(f"[netai.timetravel.demo] 모든 매칭 실패: {selected_path}")
            return None
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in matching logic: {e}")
            return None
    
    def _update_rack_label(self, selected_path, rack_mapping):
        """랙 레이블 업데이트"""
        try:
            if self._selected_rack_path:
                rack_name = self._get_rack_name(self._selected_rack_path)
                sensor_id = rack_mapping.get(self._selected_rack_path, "Unknown")
                self._selected_rack_label.text = f"{rack_name} (ID: {sensor_id})"
                print(f"[netai.timetravel.demo] 랙 레이블 업데이트: {rack_name} (ID: {sensor_id})")
            else:
                rack_name = self._get_rack_name(selected_path)
                self._selected_rack_label.text = f"{rack_name} (Not Mapped)"
                print(f"[netai.timetravel.demo] 매핑되지 않은 랙 레이블: {rack_name}")
        except Exception as e:
            print(f"[netai.timetravel.demo] Error updating rack label: {e}")
    
    def _clear_rack_selection(self, message="None"):
        """랙 선택 초기화"""
        try:
            self._selected_rack_path = None
            if self._selected_rack_label:
                self._selected_rack_label.text = message
            self._clear_sensor_data_display()
        except Exception as e:
            print(f"[netai.timetravel.demo] Error clearing rack selection: {e}")
    
    def _update_selected_rack_data(self):
        """선택된 랙의 센서 데이터 업데이트"""
        try:
            print(f"[netai.timetravel.demo] 센서 데이터 업데이트 시작")
            
            # UI 요소들이 존재하는지 확인
            if not all([self._cold_temp_label, self._hot_temp_label, 
                       self._cold_humidity_label, self._hot_humidity_label]):
                print("[netai.timetravel.demo] UI 요소가 아직 준비되지 않음")
                return
                
            if self._selected_rack_path:
                print(f"[netai.timetravel.demo] 선택된 랙 경로: {self._selected_rack_path}")
                
                # 현재 시간 확인
                current_time = self._controller.get_current_time()
                print(f"[netai.timetravel.demo] 현재 시간: {current_time}")
                
                # 컨트롤러에서 데이터 가져오기
                data = self._controller.get_rack_data_at_time(self._selected_rack_path)
                print(f"[netai.timetravel.demo] 가져온 데이터: {data}")
                
                if data and isinstance(data, dict):
                    # 필요한 키 확인
                    required_keys = ['temperature_cold', 'temperature_hot', 'humidity_cold', 'humidity_hot']
                    if all(key in data for key in required_keys):
                        # UI 업데이트
                        self._cold_temp_label.text = f"{data['temperature_cold']:.2f}"
                        self._hot_temp_label.text = f"{data['temperature_hot']:.2f}"
                        self._cold_humidity_label.text = f"{data['humidity_cold']:.2f}"
                        self._hot_humidity_label.text = f"{data['humidity_hot']:.2f}"
                        print(f"[netai.timetravel.demo] UI 업데이트 완료")
                        return
                    else:
                        print(f"[netai.timetravel.demo] 데이터에 필요한 키가 없음: {list(data.keys())}")
                else:
                    print(f"[netai.timetravel.demo] 유효하지 않은 데이터: {data}")
                    
                    # 직접 센서 데이터 가져오기 시도
                    if hasattr(self._controller, '_rack_to_sensor_map'):
                        sensor_id = self._controller._rack_to_sensor_map.get(self._selected_rack_path)
                        if sensor_id and current_time:
                            print(f"[netai.timetravel.demo] 센서 ID로 직접 데이터 가져오기: {sensor_id}")
                            direct_data = self._get_sensor_data_directly(sensor_id, current_time)
                            if direct_data:
                                self._cold_temp_label.text = f"{direct_data.get('temperature_cold', 'N/A')}"
                                self._hot_temp_label.text = f"{direct_data.get('temperature_hot', 'N/A')}"
                                self._cold_humidity_label.text = f"{direct_data.get('humidity_cold', 'N/A')}"
                                self._hot_humidity_label.text = f"{direct_data.get('humidity_hot', 'N/A')}"
                                print(f"[netai.timetravel.demo] 직접 데이터로 UI 업데이트 완료")
                                return
            
            # 데이터가 없는 경우 초기화
            print(f"[netai.timetravel.demo] 데이터 없음 - UI 초기화")
            self._clear_sensor_data_display()
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error updating selected rack data: {e}")
            import traceback
            print(f"[netai.timetravel.demo] Traceback: {traceback.format_exc()}")
            self._clear_sensor_data_display()
    
    def _get_sensor_data_directly(self, sensor_id, current_time):
        """센서 ID로 직접 데이터 가져오기"""
        try:
            if not hasattr(self._controller, '_data_cache') or not self._controller._data_cache:
                print("[netai.timetravel.demo] 데이터 캐시가 없음")
                return None
                
            cache = self._controller._data_cache
            
            # 센서 데이터 가져오기
            sensor_data = cache.get_sensor_data_at_time(sensor_id, current_time)
            print(f"[netai.timetravel.demo] 직접 가져온 센서 데이터: {sensor_data}")
            
            if sensor_data:
                return {
                    'temperature_cold': sensor_data.get('temperature_cold', sensor_data.get('temp_cold', 0)),
                    'temperature_hot': sensor_data.get('temperature_hot', sensor_data.get('temp_hot', 0)),
                    'humidity_cold': sensor_data.get('humidity_cold', sensor_data.get('hum_cold', 0)),
                    'humidity_hot': sensor_data.get('humidity_hot', sensor_data.get('hum_hot', 0))
                }
            
            return None
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error getting sensor data directly: {e}")
            return None
    
    def _clear_sensor_data_display(self):
        """센서 데이터 표시 초기화"""
        try:
            if self._cold_temp_label:
                self._cold_temp_label.text = "N/A"
            if self._hot_temp_label:
                self._hot_temp_label.text = "N/A"
            if self._cold_humidity_label:
                self._cold_humidity_label.text = "N/A"
            if self._hot_humidity_label:
                self._hot_humidity_label.text = "N/A"
        except Exception as e:
            print(f"[netai.timetravel.demo] Error clearing sensor data display: {e}")
    
    def _load_data_for_current_time_range(self):
        """현재 시간 범위에 대한 데이터 로딩"""
        try:
            if self._data_loading:
                print("[netai.timetravel.demo] 이미 데이터 로딩 중")
                return
                
            self._data_loading = True
            self._update_data_status("Loading...", 0xFFFFFF00)  # 노란색
            
            print("[netai.timetravel.demo] 현재 시간 범위에 대한 데이터 로딩 시작")
            
            # 현재 시간 범위 가져오기
            start_time = self._get_safe_start_time()
            end_time = self._get_safe_end_time()
            
            print(f"[netai.timetravel.demo] 로딩할 시간 범위: {start_time} ~ {end_time}")
            
            # 컨트롤러를 통해 데이터 로딩
            success = self._controller.load_data_for_time_range(start_time, end_time)
            
            if success:
                print("[netai.timetravel.demo] 데이터 로딩 성공")
                self._update_data_status("Ready", 0xFF00FF00)  # 녹색
                
                # UI 업데이트
                self._update_counts()
                
                # 선택된 랙이 있으면 데이터 업데이트
                if self._selected_rack_path:
                    self._update_selected_rack_data()
            else:
                print("[netai.timetravel.demo] 데이터 로딩 실패")
                self._update_data_status("Error", 0xFFFF0000)  # 빨간색
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error loading data: {e}")
            self._update_data_status("Error", 0xFFFF0000)
        finally:
            self._data_loading = False
    
    def _update_counts(self):
        """랙 및 센서 개수 업데이트"""
        try:
            if self._rack_count_label:
                self._rack_count_label.text = f"{self._get_rack_count()}"
            if self._sensor_count_label:
                self._sensor_count_label.text = f"{self._get_sensor_count()}"
        except Exception as e:
            print(f"[netai.timetravel.demo] Error updating counts: {e}")
    
    # 이벤트 핸들러들
    def _on_apply_clicked(self):
        """Apply button click handler - 데이터 로딩 포함"""
        try:
            start_time = datetime.datetime(
                self._start_year.model.get_value_as_int(),
                self._start_month.model.get_value_as_int(),
                self._start_day.model.get_value_as_int(),
                self._start_hour.model.get_value_as_int(),
                self._start_minute.model.get_value_as_int(),
                self._start_second.model.get_value_as_int()
            )
            
            end_time = datetime.datetime(
                self._end_year.model.get_value_as_int(),
                self._end_month.model.get_value_as_int(),
                self._end_day.model.get_value_as_int(),
                self._end_hour.model.get_value_as_int(),
                self._end_minute.model.get_value_as_int(),
                self._end_second.model.get_value_as_int()
            )
            
            if end_time <= start_time:
                print("[netai.timetravel.demo] Error: End time must be after start time")
                self._update_data_status("Time Error", 0xFFFF0000)
                return
            
            print(f"[netai.timetravel.demo] 시간 범위 설정: {start_time} ~ {end_time}")
            
            # 컨트롤러에 시간 범위 설정
            self._controller.set_time_range(start_time, end_time)
            
            # 새로운 시간 범위에 대한 데이터 로딩
            self._load_data_for_current_time_range()
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Time range setting error: {e}")
            self._update_data_status("Error", 0xFFFF0000)
    
    def _on_goto_clicked(self):
        """Go to specific time handler"""
        try:
            goto_time = datetime.datetime(
                self._goto_year.model.get_value_as_int(),
                self._goto_month.model.get_value_as_int(),
                self._goto_day.model.get_value_as_int(),
                self._goto_hour.model.get_value_as_int(),
                self._goto_minute.model.get_value_as_int(),
                self._goto_second.model.get_value_as_int()
            )
            
            print(f"[netai.timetravel.demo] 시간 이동: {goto_time}")
            
            # 시간 범위 검증
            start_time = self._controller.get_start_time()
            end_time = self._controller.get_end_time()
            
            if goto_time < start_time:
                goto_time = start_time
                print(f"[netai.timetravel.demo] 시간을 시작 범위로 조정: {goto_time}")
            elif goto_time > end_time:
                goto_time = end_time
                print(f"[netai.timetravel.demo] 시간을 종료 범위로 조정: {goto_time}")
            
            # 컨트롤러 시간 설정
            self._controller._current_time = goto_time
            self._controller.update_stage_time()
            
            # 슬라이더 업데이트
            if self._time_slider:
                self._time_slider.model.set_value(self._controller.get_time_progress())
            
            # 선택된 랙 데이터 업데이트
            if self._selected_rack_path:
                self._update_selected_rack_data()
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error setting specific time: {e}")
    
    def _on_present_clicked(self):
        """Present button click handler"""
        try:
            print("[netai.timetravel.demo] Present 시간으로 이동")
            self._controller.set_time_progress(1.0)
            if self._time_slider:
                self._time_slider.model.set_value(1.0)
            
            # Present 시간으로 이동 후 데이터 업데이트
            if self._selected_rack_path:
                self._update_selected_rack_data()
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in _on_present_clicked: {e}")
    
    def _on_play_clicked(self):
        """Play button click handler"""
        try:
            self._controller.toggle_playback()
            if self._play_button:
                if self._controller.is_playing():
                    self._play_button.text = "Pause"
                    print("[netai.timetravel.demo] 재생 시작")
                else:
                    self._play_button.text = "Play"
                    print("[netai.timetravel.demo] 재생 일시정지")
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in _on_play_clicked: {e}")
    
    def _on_slider_changed(self, model):
        """Slider value change handler"""
        try:
            if not self._controller.is_playing():
                progress = model.get_value_as_float()
                print(f"[netai.timetravel.demo] 슬라이더 변경: {progress:.3f}")
                self._controller.set_time_progress(progress)
                
                # 슬라이더 변경 후 데이터 업데이트
                if self._selected_rack_path:
                    self._update_selected_rack_data()
                    
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in _on_slider_changed: {e}")
    
    def _on_speed_changed(self, model):
        """Speed value change handler"""
        try:
            speed = model.get_value_as_float()
            if speed <= 0:
                speed = 0.1
            print(f"[netai.timetravel.demo] 재생 속도 변경: {speed}")
            self._controller.set_playback_speed(speed)
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in _on_speed_changed: {e}")
    
    def update_ui(self):
        """Update UI elements"""
        try:
            # Update stage time display
            current_time = self._controller.get_current_time()
            if current_time and self._stage_time_label:
                self._stage_time_label.text = current_time.strftime("%Y-%m-%d %H:%M:%S")
            elif self._stage_time_label:
                self._stage_time_label.text = "No data loaded"
            
            # Update time slider when playing
            if self._time_slider and self._controller.is_playing():
                self._time_slider.model.set_value(self._controller.get_time_progress())
            
            # Update play button text
            if self._play_button:
                if self._controller.is_playing():
                    self._play_button.text = "Pause"
                else:
                    self._play_button.text = "Play"
                    
            # Update rack data if a rack is selected (재생 중일 때도 업데이트)
            if self._selected_rack_path and self._controller.is_playing():
                self._update_selected_rack_data()
            
            # Update counts
            self._update_counts()
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error updating UI: {e}")
    
    def destroy(self):
        """Clean up UI"""
        try:
            if self._selection_changed_sub:
                self._selection_changed_sub = None
            
            if self._window:
                self._window = None
                
            print("[netai.timetravel.demo] UI 정리 완료")
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in destroy: {e}")
    
    # 새로운 이벤트 핸들러 추가
    def _on_test_minio_clicked(self):
        """MinIO 연결 및 매핑 테스트"""
        try:
            print("[netai.timetravel.demo] MinIO 테스트 시작")
            self._update_data_status("Testing...", 0xFFFFFF00)
            
            # 테스트 모듈 import 및 실행
            from .test_minio_connection import test_direct_mapping
            
            success = test_direct_mapping()
            
            if success:
                self._update_data_status("Test OK", 0xFF00FF00)
                print("[netai.timetravel.demo] ✅ MinIO 테스트 성공")
            else:
                self._update_data_status("Test Failed", 0xFFFF0000)
                print("[netai.timetravel.demo] ❌ MinIO 테스트 실패")
                
        except Exception as e:
            print(f"[netai.timetravel.demo] MinIO 테스트 오류: {e}")
            self._update_data_status("Test Error", 0xFFFF0000)