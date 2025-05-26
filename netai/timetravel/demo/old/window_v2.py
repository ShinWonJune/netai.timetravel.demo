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
        
        # Create window
        self._window = ui.Window("Time Travel", width=500, height=450)
        
        # Create selection listener
        self._usd_context = omni.usd.get_context()
        self._selection_changed_sub = None
        self._setup_selection_listener()
        
        # Build UI
        with self._window.frame:
            with ui.VStack(spacing=5):
                # Title
                ui.Label("Time Window", height=30, style={"font_size": 18})
                
                # Start time input
                with ui.HStack(height=30):
                    ui.Label("Start:", width=50)
                    
                    # Start date & time input
                    self._start_year = ui.IntField(width=50)
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
                
                # End time input
                with ui.HStack(height=30):
                    ui.Label("End:", width=50)
                    
                    # End date & time input
                    self._end_year = ui.IntField(width=50)
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
                
                # 시간 윈도우 적용 버튼
                with ui.HStack(height=30):
                    self._apply_button = ui.Button("Apply", width=100)
                    self._apply_button.set_clicked_fn(lambda: self._on_apply_clicked())

                    ui.Spacer(width=20)
                    
                    self._present_button = ui.Button("Present", width=100)
                    self._present_button.set_clicked_fn(lambda: self._on_present_clicked())
                
                # 새로 추가: 특정 시간 입력 필드
                with ui.HStack(height=30):
                    ui.Label("Go to:", width=50)
                    
                    # 년,월,일,시,분,초 입력 (start 값 기본값)
                    self._goto_year = ui.IntField(width=50)
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

                    self._goto_button = ui.Button("Go to Time", width=100)
                    self._goto_button.set_clicked_fn(lambda: self._on_goto_clicked())
                
                ui.Spacer(height=10)
                
                # USD Stage time display
                with ui.HStack(height=30):
                    ui.Label("USD Stage Time: ", width=120, style={"font_size": 18})
                    self._stage_time_label = ui.Label("", width=380, style={"font_size": 18})
                
                ui.Spacer(height=10)
                
                # Time slider
                with ui.HStack(height=30):
                    self._time_slider = ui.FloatSlider(min=0, max=1, width=ui.Percent(100))
                    self._time_slider.model.set_value(self._controller.get_progress())
                    self._time_slider.model.add_value_changed_fn(self._on_slider_changed)
                
                ui.Spacer(height=10)
                
                # Playback controls
                with ui.HStack(height=30):
                    self._play_button = ui.Button("Play", width=80)
                    self._play_button.set_clicked_fn(lambda: self._on_play_clicked())
                    
                    ui.Spacer(width=20)
                    
                    ui.Label("Speed:", width=50)
                    self._speed_field = ui.FloatField(width=80)
                    self._speed_field.model.set_value(self._controller.get_playback_speed())
                    self._speed_field.model.add_end_edit_fn(self._on_speed_changed)
                
                ui.Spacer(height=20)
                
                # 선택된 랙 정보 표시 섹션
                ui.Label("Selected Rack Info", height=30, style={"font_size": 18})
                
                with ui.HStack(height=30):
                    ui.Label("Rack Path:", width=80)
                    self._selected_rack_label = ui.Label("None", width=ui.Percent(100))
                
                with ui.HStack(height=30):
                    ui.Label("Sensor ID:", width=80)
                    self._sensor_id_label = ui.Label("None", width=ui.Percent(100))
                
                # Cold Aisle 정보
                with ui.CollapsableFrame("Cold Aisle Data", height=80):
                    with ui.VStack(spacing=5):
                        with ui.HStack(height=25):
                            ui.Label("Temperature:", width=100)
                            self._cold_temp_label = ui.Label("N/A", width=100)
                            ui.Label("°C", width=30)
                        
                        with ui.HStack(height=25):
                            ui.Label("Humidity:", width=100)
                            self._cold_humidity_label = ui.Label("N/A", width=100)
                            ui.Label("%", width=30)
                
                # Hot Aisle 정보
                with ui.CollapsableFrame("Hot Aisle Data", height=80):
                    with ui.VStack(spacing=5):
                        with ui.HStack(height=25):
                            ui.Label("Temperature:", width=100)
                            self._hot_temp_label = ui.Label("N/A", width=100)
                            ui.Label("°C", width=30)
                        
                        with ui.HStack(height=25):
                            ui.Label("Humidity:", width=100)
                            self._hot_humidity_label = ui.Label("N/A", width=100)
                            ui.Label("%", width=30)
                
                # 데이터 요약
                with ui.HStack(height=30):
                    ui.Label("Racks Mapped:", width=110)
                    self._rack_count_label = ui.Label(f"{self._controller.get_rack_count()}", width=40)
                    
                    ui.Spacer(width=20)
                    
                    ui.Label("Sensors with Data:", width=120)
                    self._sensor_count_label = ui.Label(f"{self._controller.get_sensor_count()}", width=40)
    
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
            
            # 랙 경로인지 확인 (간단한 체크: datacenter와 RACK이 포함되어 있는지)
            if "datacenter" in selected_path and "RACK" in selected_path:
                self._selected_rack_path = selected_path
                
                # 컨트롤러에서 랙에 매핑된 센서 ID 가져오기
                sensor_id = self._controller.get_sensor_id_for_rack(selected_path)
                
                # UI 업데이트
                self._selected_rack_label.text = self._get_rack_name(selected_path)
                self._sensor_id_label.text = sensor_id if sensor_id else "None"
                
                # 현재 시간의 센서 데이터 가져오기
                self._update_selected_rack_data()
            else:
                # 랙이 아닌 경우 선택 정보 초기화
                self._selected_rack_path = None
                self._selected_rack_label.text = "None (Not a Rack)"
                self._sensor_id_label.text = "None"
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
        if not self._controller.is_playing():  # Only update when not playing
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