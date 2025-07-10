# -*- coding: utf-8 -*-
import omni.ui as ui
import datetime
import omni.usd
from pxr import Usd, UsdGeom
#------------------------------------
# 세로로 콤팩트하게 정열
#------------------------------------
class TimeWindowUI:
    """Time Travel Window for Datacenter Digital Twin"""
    
    def __init__(self, controller):
        """Time window UI initialization"""
        self._controller = controller
        self._selected_rack_path = None
        self._selected_rack_data = None
        
        # 윈도우 생성
        self._window = ui.Window("Time Travel", width=550, height=500)
        
        # 선택 리스너 생성
        self._usd_context = omni.usd.get_context()
        self._selection_changed_sub = None
        self._setup_selection_listener()
        
        # 단일 열 레이아웃 구성
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
                        self._start_year.model.set_value(self._controller.get_start_time().year)
                        ui.Label("/", width=10)
                        self._start_month = ui.IntField(width=30)
                        self._start_month.model.set_value(self._controller.get_start_time().month)
                        ui.Label("/", width=10)
                        self._start_day = ui.IntField(width=30)
                        self._start_day.model.set_value(self._controller.get_start_time().day)
                        ui.Label(" ", width=10)
                        self._start_hour = ui.IntField(width=30)
                        self._start_hour.model.set_value(self._controller.get_start_time().hour)
                        ui.Label(":", width=10)
                        self._start_minute = ui.IntField(width=30)
                        self._start_minute.model.set_value(self._controller.get_start_time().minute)
                        ui.Label(":", width=10)
                        self._start_second = ui.IntField(width=30)
                        self._start_second.model.set_value(self._controller.get_start_time().second)
                    
                    # 종료 시간 입력
                    with ui.HStack(height=20):
                        ui.Label("End:", width=50)
                        self._end_year = ui.IntField(width=40)
                        self._end_year.model.set_value(self._controller.get_end_time().year)
                        ui.Label("/", width=10)
                        self._end_month = ui.IntField(width=30)
                        self._end_month.model.set_value(self._controller.get_end_time().month)
                        ui.Label("/", width=10)
                        self._end_day = ui.IntField(width=30)
                        self._end_day.model.set_value(self._controller.get_end_time().day)
                        ui.Label(" ", width=10)
                        self._end_hour = ui.IntField(width=30)
                        self._end_hour.model.set_value(self._controller.get_end_time().hour)
                        ui.Label(":", width=10)
                        self._end_minute = ui.IntField(width=30)
                        self._end_minute.model.set_value(self._controller.get_end_time().minute)
                        ui.Label(":", width=10)
                        self._end_second = ui.IntField(width=30)
                        self._end_second.model.set_value(self._controller.get_end_time().second)
                    
                    # Apply 버튼
                    with ui.HStack(height=20):
                        ui.Spacer(width=5)
                        self._apply_button = ui.Button("Apply", width=60)
                        self._apply_button.set_clicked_fn(lambda: self._on_apply_clicked())
                        ui.Spacer(width=5)
                        self._present_button = ui.Button("Present", width=60)
                        self._present_button.set_clicked_fn(lambda: self._on_present_clicked())
                    
                    # Go to time
                    with ui.HStack(height=20):
                        ui.Label("Go to:", width=50)
                        self._goto_year = ui.IntField(width=40)
                        self._goto_year.model.set_value(self._controller.get_start_time().year)
                        ui.Label("/", width=10)
                        self._goto_month = ui.IntField(width=30)
                        self._goto_month.model.set_value(self._controller.get_start_time().month)
                        ui.Label("/", width=10)
                        self._goto_day = ui.IntField(width=30)
                        self._goto_day.model.set_value(self._controller.get_start_time().day)
                        ui.Label(" ", width=10)
                        self._goto_hour = ui.IntField(width=30)
                        self._goto_hour.model.set_value(self._controller.get_start_time().hour)
                        ui.Label(":", width=10)
                        self._goto_minute = ui.IntField(width=30)
                        self._goto_minute.model.set_value(self._controller.get_start_time().minute)
                        ui.Label(":", width=10)
                        self._goto_second = ui.IntField(width=30)
                        self._goto_second.model.set_value(self._controller.get_start_time().second)
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
                    self._speed_field.model.set_value(self._controller.get_playback_speed())
                    self._speed_field.model.add_end_edit_fn(self._on_speed_changed)
                
                # 3. 수평선 추가하여 섹션 구분
                with ui.HStack(height=5):
                    ui.Spacer(width=10)
                    ui.Line(style_type_name_override="border_color", style={"color": 0xFF666666})
                    ui.Spacer(width=10)
                
                # 4. Selected Rack Info 섹션 (중간에 배치)
                with ui.HStack(height=20):
                    ui.Label("Selected Rack Info", style={"font_size": 18})
                    
                # Rack Path
                with ui.HStack(height=20):
                    ui.Label("Rack Path:", width=80)
                    # self._selected_rack_label = ui.Label("None", width=ui.Percent(100))
                    
                    # # Sensor ID - 주석 처리된 부분 복원
                    # with ui.HStack(height=25):
                    #     ui.Label("Sensor ID:", width=80)
                    #     self._sensor_id_label = ui.Label("None", width=ui.Percent(100))
                    
                    # Aisle 데이터를 가로 배치로 변경하여 공간 절약
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
                
                # 5. 수평선 추가하여 섹션 구분
                with ui.HStack(height=2):
                    ui.Spacer(width=10)
                    ui.Line(style_type_name_override="border_color", style={"color": 0xFF666666})
                    ui.Spacer(width=10)
                
                # 6. 하단 섹션: 슬라이더
                with ui.HStack(height=30):
                    # 양쪽 여백
                    ui.Spacer(width=10)
                    
                    # 슬라이더
                    self._time_slider = ui.FloatSlider(min=0.0, max=1.0, width=480)
                    self._time_slider.model.set_value(self._controller.get_progress())
                    self._time_slider.model.add_value_changed_fn(self._on_slider_changed) # 슬라이더 값 변경 시 호출 (콜백)
                    
                    # 오른쪽 여백
                    ui.Spacer(width=20)
                
                # 7. 데이터 요약 - 슬라이더 아래에 배치
                with ui.HStack(height=10):
                    ui.Spacer(width=10)
                    ui.Label("Racks Mapped:", width=90)
                    self._rack_count_label = ui.Label(f"{self._controller.get_rack_count()}", width=40)
                    ui.Spacer(width=20)
                    ui.Label("Number of sensors:", width=120)
                    self._sensor_count_label = ui.Label(f"{self._controller.get_sensor_count()}", width=40)
                    ui.Spacer(width=10)
    
    def _setup_selection_listener(self):
        """선택 이벤트 리스너 설정"""
        # Omniverse 2023 버전 이상에서는 스테이지 이벤트를 사용
        import omni.usd
        import carb
        
        # 기존 구독 정리
        if self._selection_changed_sub:
            self._selection_changed_sub = None
        
        # 스테이지 리스너 설정
        events = self._usd_context.get_stage_event_stream()
        self._selection_changed_sub = events.create_subscription_to_pop(
            self._handle_stage_event, name="selection_changed_sub"
        )
    
    def _handle_stage_event(self, event):
        """스테이지 이벤트 핸들러"""
        # 선택 변경 이벤트 필터링
        import omni.usd
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._check_selected_prim()
    
    def _check_selected_prim(self):
        """현재 선택된 프림 확인"""
        import omni.usd
        stage = self._usd_context.get_stage()
        if not stage:
            return
            
        # 현재 선택된 프림 경로 가져오기
        selection = self._usd_context.get_selection()
        selected_paths = selection.get_selected_prim_paths()
        
        if selected_paths:
            # 첫 번째 선택된 프림 경로 사용
            selected_path = selected_paths[0]
            
            # 디버깅용 로그 추가
            print(f"[netai.timetravel.demo] 선택된 프림 경로: {selected_path}")
            
            # 랙 경로인지 확인 (간단한 체크: datacenter와 RACK이 포함되어 있는지)
            if "datacenter" in selected_path and "RACK" in selected_path:
                self._selected_rack_path = selected_path
                
                # 컨트롤러에서 랙에 매핑된 센서 ID 가져오기
                sensor_id = self._controller.get_sensor_id_for_rack(selected_path)
                
                # 디버깅 로그 추가
                print(f"[netai.timetravel.demo] 선택된 랙: {selected_path}, 매핑된 센서 ID: {sensor_id}")
                
                # 정확히 매핑된 센서 ID가 없으면 경로 변형 시도
                if not sensor_id:
                    # 1. "/World" 접두사 제거 시도
                    if selected_path.startswith("/World"):
                        alt_path = selected_path[6:]  # "/World" 제거
                        sensor_id = self._controller.get_sensor_id_for_rack(alt_path)
                        print(f"[netai.timetravel.demo] 대체 경로 시도 1: {alt_path}, 결과: {sensor_id}")
                    
                    # 2. "/World" 접두사 추가 시도
                    if not sensor_id and not selected_path.startswith("/World"):
                        alt_path = "/World" + selected_path
                        sensor_id = self._controller.get_sensor_id_for_rack(alt_path)
                        print(f"[netai.timetravel.demo] 대체 경로 시도 2: {alt_path}, 결과: {sensor_id}")
                    
                    # 3. 경로 끝부분만 사용 시도
                    if not sensor_id:
                        path_parts = selected_path.split('/')
                        if len(path_parts) >= 2:
                            rack_name = path_parts[-1]
                            # 매핑에서 이 랙 이름을 포함하는 모든 경로 찾기
                            for rack_path in self._controller._rack_to_sensor_map.keys():
                                if rack_path.endswith('/' + rack_name):
                                    sensor_id = self._controller.get_sensor_id_for_rack(rack_path)
                                    print(f"[netai.timetravel.demo] 대체 경로 시도 3: {rack_path}, 결과: {sensor_id}")
                                    if sensor_id:
                                        break
                
                # UI 업데이트
                # self._selected_rack_label.text = self._get_rack_name(selected_path)
                # self._sensor_id_label.text = sensor_id if sensor_id else "None (No matching sensor)"
                
                # 현재 시간의 센서 데이터 가져오기
                self._update_selected_rack_data()
            else:
                # 랙이 아닌 경우 선택 정보 초기화
                self._selected_rack_path = None
                # self._selected_rack_label.text = "None (Not a Rack)"
                # self._sensor_id_label.text = "None"
                self._clear_sensor_data_display()
    
    def _get_rack_name(self, rack_path):
        """랙 경로에서 랙 이름 추출"""
        if rack_path:
            # 마지막 경로 부분 추출 (예: /Root/datacenter/RACK_A1 -> RACK_A1)
            parts = rack_path.split('/')
            return parts[-1] if parts else "Unknown"
        return "None"
    
    def _update_selected_rack_data(self):
        """선택된 랙의 센서 데이터 업데이트"""
        if self._selected_rack_path:
            # USD 스테이지에서 데이터 직접 읽기
            stage = self._usd_context.get_stage()
            if stage:
                prim = stage.GetPrimAtPath(self._selected_rack_path)
                if prim and prim.IsValid():
                    # 온도 및 습도 데이터 읽기
                    temp_cold = prim.GetAttribute("temperature_cold").Get() if prim.HasAttribute("temperature_cold") else None
                    temp_hot = prim.GetAttribute("temperature_hot").Get() if prim.HasAttribute("temperature_hot") else None
                    hum_cold = prim.GetAttribute("humidity_cold").Get() if prim.HasAttribute("humidity_cold") else None
                    hum_hot = prim.GetAttribute("humidity_hot").Get() if prim.HasAttribute("humidity_hot") else None
                    
                    # UI 업데이트
                    self._cold_temp_label.text = f"{temp_cold:.2f}" if temp_cold is not None else "N/A"
                    self._hot_temp_label.text = f"{temp_hot:.2f}" if temp_hot is not None else "N/A"
                    self._cold_humidity_label.text = f"{hum_cold:.2f}" if hum_cold is not None else "N/A"
                    self._hot_humidity_label.text = f"{hum_hot:.2f}" if hum_hot is not None else "N/A"
                    return
        
        # 선택된 랙이 없거나 데이터를 찾을 수 없는 경우 UI 초기화
        self._clear_sensor_data_display()
    
    def _clear_sensor_data_display(self):
        """센서 데이터 표시 초기화"""
        self._cold_temp_label.text = "N/A"
        self._hot_temp_label.text = "N/A"
        self._cold_humidity_label.text = "N/A"
        self._hot_humidity_label.text = "N/A"
    
    def destroy(self):
        """Clean up UI"""
        if self._selection_changed_sub:
            self._selection_changed_sub = None
        
        if self._window:
            self._window = None
    
    def _on_apply_clicked(self):
        """Apply button click handler"""
        # Get values from UI
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
            
            # Check that end time is after start time
            if end_time <= start_time:
                print("[netai.timetravel.demo] Error: End time must be after start time")
                return
            
            # Apply new time range
            self._controller.set_time_range(start_time, end_time)
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Time range setting error: {e}")
    
    def _on_goto_clicked(self):
        """Go to specific time handler"""
        try:
            # 년/월/일/시/분/초 모두 사용하여 새 시간 생성
            goto_time = datetime.datetime(
                self._goto_year.model.get_value_as_int(),
                self._goto_month.model.get_value_as_int(),
                self._goto_day.model.get_value_as_int(),
                self._goto_hour.model.get_value_as_int(),
                self._goto_minute.model.get_value_as_int(),
                self._goto_second.model.get_value_as_int()
            )
            
            # 시간 범위 내에 있는지 확인
            start_time = self._controller.get_start_time()
            end_time = self._controller.get_end_time()
            
            # 시간 범위 체크
            if goto_time < start_time:
                print("[netai.timetravel.demo] Error: Time is before start range")
                goto_time = start_time
            elif goto_time > end_time:
                print("[netai.timetravel.demo] Error: Time is after end range")
                goto_time = end_time
            
            # 컨트롤러에 시간 설정
            self._controller.set_current_time(goto_time)
            
            # 슬라이더 업데이트
            self._time_slider.model.set_value(self._controller.get_progress())

            # UI 업데이트
            self._update_selected_rack_data()
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Error setting specific time: {e}")
    
    def _on_present_clicked(self):
        """Present button click handler"""
        self._controller.set_to_present()
        self._time_slider.model.set_value(1.0)
    
    def _on_play_clicked(self):
        """Play button click handler"""
        self._controller.toggle_playback()
        if self._controller.is_playing():
            self._play_button.text = "Pause"
        else:
            self._play_button.text = "Play"
    
    def _on_slider_changed(self, model):
        """Slider value change handler"""
        # if not self._controller.is_playing():  # Only update when not playing
        progress = model.get_value_as_float()
        self._controller.set_progress(progress)
    
    def _on_speed_changed(self, model):
        """Speed value change handler"""
        speed = model.get_value_as_float()
        if speed <= 0:
            speed = 0.1
        self._controller.set_playback_speed(speed)
    
    def update_ui(self):
        """Update UI elements"""
        # Update stage time display
        stage_time = self._controller.get_stage_time()
        self._stage_time_label.text = stage_time
        
        # Update time slider when playing
        if self._controller.is_playing():
            self._time_slider.model.set_value(self._controller.get_progress())
        
        # Update play button text
        if self._controller.is_playing():
            self._play_button.text = "Pause"
        else:
            self._play_button.text = "Play"
            
        # Update rack data if a rack is selected
        if self._selected_rack_path:
            self._update_selected_rack_data()
        
        # Update rack and sensor counts
        self._rack_count_label.text = f"{self._controller.get_rack_count()}"
        self._sensor_count_label.text = f"{self._controller.get_sensor_count()}"