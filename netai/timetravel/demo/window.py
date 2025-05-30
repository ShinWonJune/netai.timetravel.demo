# -*- coding: utf-8 -*-
from pxr import Usd, UsdGeom
import omni.ui as ui
import omni.usd
import datetime

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
        
        # UI 컴포넌트들
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the complete UI"""
        with self._window.frame:
            with ui.VStack(spacing=5):
                
                # === Data Status Section ===
                ui.Label("Data Status", height=20, style={"font_size": 14, "font_weight": "bold"})
                with ui.HStack(height=25):
                    ui.Label("Load Status:", width=80)
                    self._load_status_label = ui.Label("No data", style={"color": 0xFF808080})
                
                ui.Separator(height=2)
                
                # === Time Range Section ===
                ui.Label("Time Range Settings", height=20, style={"font_size": 14, "font_weight": "bold"})
                
                # Start Time
                ui.Label("Start Time:", height=20)
                with ui.HStack(height=25):
                    now = datetime.datetime.now() - datetime.timedelta(days=7)
                    self._start_year = ui.IntDrag(value=now.year, min=2020, max=2030, width=60)
                    ui.Label("-", width=10)
                    self._start_month = ui.IntDrag(value=now.month, min=1, max=12, width=40)
                    ui.Label("-", width=10)
                    self._start_day = ui.IntDrag(value=now.day, min=1, max=31, width=40)
                    ui.Spacer(width=10)
                    self._start_hour = ui.IntDrag(value=now.hour, min=0, max=23, width=40)
                    ui.Label(":", width=10)
                    self._start_minute = ui.IntDrag(value=now.minute, min=0, max=59, width=40)
                    ui.Label(":", width=10)
                    self._start_second = ui.IntDrag(value=now.second, min=0, max=59, width=40)
                
                # End Time
                ui.Label("End Time:", height=20)
                with ui.HStack(height=25):
                    now = datetime.datetime.now()
                    self._end_year = ui.IntDrag(value=now.year, min=2020, max=2030, width=60)
                    ui.Label("-", width=10)
                    self._end_month = ui.IntDrag(value=now.month, min=1, max=12, width=40)
                    ui.Label("-", width=10)
                    self._end_day = ui.IntDrag(value=now.day, min=1, max=31, width=40)
                    ui.Spacer(width=10)
                    self._end_hour = ui.IntDrag(value=now.hour, min=0, max=23, width=40)
                    ui.Label(":", width=10)
                    self._end_minute = ui.IntDrag(value=now.minute, min=0, max=59, width=40)
                    ui.Label(":", width=10)
                    self._end_second = ui.IntDrag(value=now.second, min=0, max=59, width=40)
                
                # Apply Button
                with ui.HStack(height=30):
                    ui.Spacer()
                    ui.Button("Apply Time Range", width=150, height=25, clicked_fn=self._on_apply_clicked)
                    ui.Spacer()
                
                ui.Separator(height=2)
                
                # === Current Time Display ===
                ui.Label("Current Time", height=20, style={"font_size": 14, "font_weight": "bold"})
                with ui.HStack(height=25):
                    ui.Label("Stage Time:", width=80)
                    self._stage_time_label = ui.Label("Not set")
                
                ui.Separator(height=2)
                
                # === Time Control Section ===
                ui.Label("Time Control", height=20, style={"font_size": 14, "font_weight": "bold"})
                
                # Go to specific time
                ui.Label("Go to Time:", height=20)
                with ui.HStack(height=25):
                    now = datetime.datetime.now()
                    self._goto_year = ui.IntDrag(value=now.year, min=2020, max=2030, width=60)
                    ui.Label("-", width=10)
                    self._goto_month = ui.IntDrag(value=now.month, min=1, max=12, width=40)
                    ui.Label("-", width=10)
                    self._goto_day = ui.IntDrag(value=now.day, min=1, max=31, width=40)
                    ui.Spacer(width=10)
                    self._goto_hour = ui.IntDrag(value=now.hour, min=0, max=23, width=40)
                    ui.Label(":", width=10)
                    self._goto_minute = ui.IntDrag(value=now.minute, min=0, max=59, width=40)
                    ui.Label(":", width=10)
                    self._goto_second = ui.IntDrag(value=now.second, min=0, max=59, width=40)
                
                with ui.HStack(height=30):
                    ui.Button("Go to Time", width=80, height=25, clicked_fn=self._on_goto_clicked)
                    ui.Spacer(width=10)
                    ui.Button("Present", width=80, height=25, clicked_fn=self._on_present_clicked)
                    ui.Spacer()
                
                # Time Slider
                ui.Label("Time Slider:", height=20)
                self._time_slider = ui.FloatSlider(min=0.0, max=1.0, value=0.0, height=25)
                self._time_slider.model.add_value_changed_fn(self._on_slider_changed)
                
                # Playback Controls
                with ui.HStack(height=30):
                    self._play_button = ui.Button("Play", width=60, height=25, clicked_fn=self._on_play_clicked)
                    ui.Spacer(width=10)
                    ui.Label("Speed:", width=40)
                    self._speed_slider = ui.FloatSlider(min=0.1, max=10.0, value=1.0, width=150)
                    self._speed_slider.model.add_value_changed_fn(self._on_speed_changed)
                    ui.Spacer()
                
                ui.Separator(height=2)
                
                # === Selected Rack Info ===
                ui.Label("Selected Rack", height=20, style={"font_size": 14, "font_weight": "bold"})
                
                with ui.HStack(height=25):
                    ui.Label("Rack:", width=80)
                    self._selected_rack_label = ui.Label("None")
                
                # Sensor Data Display
                ui.Label("Sensor Data:", height=20)
                
                with ui.VStack():
                    with ui.HStack(height=20):
                        ui.Label("Cold Temp:", width=100)
                        self._cold_temp_label = ui.Label("N/A", style={"color": 0xFF4080FF})
                        ui.Label("°C", width=20)
                    
                    with ui.HStack(height=20):
                        ui.Label("Hot Temp:", width=100)
                        self._hot_temp_label = ui.Label("N/A", style={"color": 0xFFFF4040})
                        ui.Label("°C", width=20)
                    
                    with ui.HStack(height=20):
                        ui.Label("Cold Humidity:", width=100)
                        self._cold_humidity_label = ui.Label("N/A", style={"color": 0xFF4080FF})
                        ui.Label("%", width=20)
                    
                    with ui.HStack(height=20):
                        ui.Label("Hot Humidity:", width=100)
                        self._hot_humidity_label = ui.Label("N/A", style={"color": 0xFFFF4040})
                        ui.Label("%", width=20)
                
                ui.Separator(height=2)
                
                # === Statistics ===
                ui.Label("Statistics", height=20, style={"font_size": 14, "font_weight": "bold"})
                
                with ui.HStack(height=20):
                    ui.Label("Racks:", width=60)
                    self._rack_count_label = ui.Label("0")
                    ui.Spacer(width=20)
                    ui.Label("Sensors:", width=60)
                    self._sensor_count_label = ui.Label("0")
                
                ui.Spacer()
    
    def _setup_selection_listener(self):
        """선택 이벤트 리스너 설정"""
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
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._check_selected_prim()
    
    def _check_selected_prim(self):
        """현재 선택된 프림 확인"""
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
                self._selected_rack_label.text = self._get_rack_name(selected_path)
                self._update_selected_rack_data()
            else:
                self._selected_rack_path = None
                self._selected_rack_label.text = "None"
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
            # 컨트롤러에서 데이터 가져오기
            data = self._controller.get_rack_data_at_time(self._selected_rack_path)
            if data:
                self._cold_temp_label.text = f"{data.get('temperature_cold', 0):.1f}"
                self._hot_temp_label.text = f"{data.get('temperature_hot', 0):.1f}"
                self._cold_humidity_label.text = f"{data.get('humidity_cold', 0):.1f}"
                self._hot_humidity_label.text = f"{data.get('humidity_hot', 0):.1f}"
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
                print("[netai.timetravel.demo] End time must be after start time")
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
                print(f"[netai.timetravel.demo] Time {goto_time} is before start time {start_time}")
                return
            elif goto_time > end_time:
                print(f"[netai.timetravel.demo] Time {goto_time} is after end time {end_time}")
                return
            
            # 컨트롤러에 시간 설정
            self._controller.set_current_time(goto_time)
            
            # 슬라이더 업데이트
            progress = self._controller.get_time_progress()
            self._time_slider.model.set_value(progress)
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Go to time error: {e}")
    
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
        if not self._controller.is_playing():
            progress = model.get_value_as_float()
            self._controller.set_time_progress(progress)
    
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
        
        # Update load status
        self._load_status_label.text = self._controller.get_load_progress()
        
        # Update time slider when playing
        if self._controller.is_playing():
            progress = self._controller.get_time_progress()
            self._time_slider.model.set_value(progress)
        
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