# -*- coding: utf-8 -*-
"""
Time Travel UI Window
"""
import omni.ui as ui
import omni.usd
import datetime
from typing import Optional

class TimeWindowUI:
    """Time Travel Control Window"""
    
    def __init__(self, controller):
        self._controller = controller
        self._window = None
        self._usd_context = omni.usd.get_context()
        
        # UI 컨트롤 레퍼런스
        self._time_slider = None
        self._start_date_field = None
        self._end_date_field = None
        self._current_time_label = None
        self._play_button = None
        self._speed_slider = None
        self._selected_rack_label = None
        
        # 센서 데이터 표시 UI
        self._temp_cold_label = None
        self._temp_hot_label = None
        self._humidity_cold_label = None
        self._humidity_hot_label = None
        
        # 데이터 확인 UI 추가
        self._load_status_label = None
        self._total_records_label = None
        self._data_range_label = None
        self._sensors_count_label = None
        self._memory_usage_label = None
        
        # 상태
        self._selected_rack_path = None
        self._last_update_time = 0
        
        self._create_window()
        
    def _create_window(self):
        """Create the main window"""
        self._window = ui.Window("Time Travel Control", width=420, height=700)
        
        with self._window.frame:
            with ui.VStack(spacing=10):
                self._create_data_loading_section()
                ui.Separator()
                self._create_data_status_section()  # 새로 추가
                ui.Separator()
                self._create_time_control_section()
                ui.Separator()
                self._create_playback_section()
                ui.Separator()
                self._create_rack_selection_section()
                ui.Separator()
                self._create_sensor_data_section()
                
    def _create_data_loading_section(self):
        """데이터 로딩 섹션"""
        with ui.CollapsableFrame("Data Loading", collapsed=False):
            with ui.VStack(spacing=5):
                ui.Label("Date Range:")
                
                with ui.HStack(spacing=5):
                    ui.Label("Start:", width=50)
                    self._start_date_field = ui.StringField()
                    self._start_date_field.model.set_value("2025-05-22")
                    
                with ui.HStack(spacing=5):
                    ui.Label("End:", width=50)
                    self._end_date_field = ui.StringField()
                    self._end_date_field.model.set_value("2025-05-31")
                
                ui.Button("Load Data", clicked_fn=self._on_load_data)
                
                self._load_status_label = ui.Label("Status: Ready to load")

    def _create_data_status_section(self):
        """데이터 상태 확인 섹션 (새로 추가)"""
        with ui.CollapsableFrame("Data Status", collapsed=False):
            with ui.VStack(spacing=5):
                # 로딩 진행 상태
                ui.Label("Loading Progress:", style={"font_weight": "bold"})
                self._loading_progress_label = ui.Label("Not started")
                
                ui.Separator()
                
                # 데이터 통계
                ui.Label("Data Statistics:", style={"font_weight": "bold"})
                self._total_records_label = ui.Label("Total Records: 0")
                self._sensors_count_label = ui.Label("Active Sensors: 0/24")
                self._data_range_label = ui.Label("Time Range: No data")
                
                ui.Separator()
                
                # 센서별 데이터 개수 (스크롤 가능)
                ui.Label("Sensor Data Count:", style={"font_weight": "bold"})
                with ui.ScrollingFrame(height=120):
                    with ui.VStack():
                        self._sensor_details_stack = ui.VStack()
                        # 초기에는 비어있음, 데이터 로드 후 업데이트
                        
                ui.Separator()
                
                # 메모리 사용량
                ui.Label("Performance:", style={"font_weight": "bold"})
                self._memory_usage_label = ui.Label("Memory Usage: --")
                self._load_time_label = ui.Label("Load Time: --")
                
                # 새로고침 버튼
                ui.Button("Refresh Status", clicked_fn=self._on_refresh_status, height=25)
                
    def _create_time_control_section(self):
        """시간 제어 섹션"""
        with ui.CollapsableFrame("Time Control", collapsed=False):
            with ui.VStack(spacing=5):
                ui.Label("Current Time:")
                self._current_time_label = ui.Label("No data loaded")
                
                ui.Label("Time Position:")
                self._time_slider = ui.FloatSlider(
                    min=0.0, max=1.0, step=0.001,
                    height=30
                )
                self._time_slider.model.add_value_changed_fn(self._on_time_slider_changed)
                
                with ui.HStack(spacing=5):
                    ui.Button("Start", clicked_fn=self._on_go_to_start, width=80)
                    ui.Button("Present", clicked_fn=self._on_go_to_present, width=80)
                    
    def _create_playback_section(self):
        """재생 제어 섹션"""
        with ui.CollapsableFrame("Playback Control", collapsed=False):
            with ui.VStack(spacing=5):
                with ui.HStack(spacing=5):
                    self._play_button = ui.Button("Play", clicked_fn=self._on_toggle_playback, width=80)
                    ui.Button("Stop", clicked_fn=self._on_stop_playback, width=80)
                
                ui.Label("Playback Speed:")
                with ui.HStack(spacing=5):
                    ui.Label("0.1x", width=30)
                    self._speed_slider = ui.FloatSlider(
                        min=0.1, max=10.0, step=0.1, height=20
                    )
                    self._speed_slider.model.set_value(1.0)
                    self._speed_slider.model.add_value_changed_fn(self._on_speed_changed)
                    ui.Label("10x", width=30)
                
                self._speed_label = ui.Label("Speed: 1.0x")
                
    def _create_rack_selection_section(self):
        """랙 선택 섹션"""
        with ui.CollapsableFrame("Rack Selection", collapsed=False):
            with ui.VStack(spacing=5):
                ui.Label("Selected Rack:")
                self._selected_rack_label = ui.Label("None")
                
                ui.Label("Available Racks:")
                with ui.ScrollingFrame(height=100):
                    with ui.VStack():
                        # 매핑된 모든 랙 버튼 생성
                        rack_mapping = self._controller._rack_to_sensor_map
                        for rack_path in sorted(rack_mapping.keys()):
                            rack_name = rack_path.split('/')[-1]  # 경로에서 랙 이름만 추출
                            ui.Button(
                                rack_name, 
                                clicked_fn=lambda rp=rack_path: self._on_select_rack(rp),
                                height=25
                            )
                
    def _create_sensor_data_section(self):
        """센서 데이터 표시 섹션"""
        with ui.CollapsableFrame("Sensor Data", collapsed=False):
            with ui.VStack(spacing=5):
                ui.Label("Temperature (°C):")
                with ui.HStack(spacing=10):
                    with ui.VStack(spacing=2):
                        ui.Label("Cold Aisle:", style={"color": 0xFF4080FF})
                        self._temp_cold_label = ui.Label("--.-°C", style={"font_size": 16})
                    with ui.VStack(spacing=2):
                        ui.Label("Hot Aisle:", style={"color": 0xFFFF4040})
                        self._temp_hot_label = ui.Label("--.-°C", style={"font_size": 16})
                
                ui.Separator()
                
                ui.Label("Humidity (%):")
                with ui.HStack(spacing=10):
                    with ui.VStack(spacing=2):
                        ui.Label("Cold Aisle:", style={"color": 0xFF4080FF})
                        self._humidity_cold_label = ui.Label("--.-%", style={"font_size": 16})
                    with ui.VStack(spacing=2):
                        ui.Label("Hot Aisle:", style={"color": 0xFFFF4040})
                        self._humidity_hot_label = ui.Label("--.-%", style={"font_size": 16})
    
    # 이벤트 핸들러들
    def _on_load_data(self):
        """데이터 로드 버튼 클릭"""
        try:
            start_str = self._start_date_field.model.get_value_as_string()
            end_str = self._end_date_field.model.get_value_as_string()
            
            start_time = datetime.datetime.strptime(start_str, "%Y-%m-%d")
            end_time = datetime.datetime.strptime(end_str, "%Y-%m-%d") + datetime.timedelta(days=1)
            
            self._load_status_label.text = "Loading data..."
            self._loading_progress_label.text = "Starting data load..."
            
            # 데이터 로드 시작
            self._controller.set_time_range(start_time, end_time)
            
            # 로드 완료 후 상태 업데이트
            self._load_status_label.text = f"Data loaded: {start_str} to {end_str}"
            self._loading_progress_label.text = "Load completed"
            self._update_data_status()
            
        except ValueError as e:
            self._load_status_label.text = f"Error: Invalid date format ({e})"
            self._loading_progress_label.text = f"Error: {e}"
            
    def _on_refresh_status(self):
        """상태 새로고침 버튼 클릭"""
        self._update_data_status()
        
    def _update_data_status(self):
        """데이터 상태 정보 업데이트"""
        if not self._controller.is_data_loaded():
            self._total_records_label.text = "Total Records: 0"
            self._sensors_count_label.text = "Active Sensors: 0/24"
            self._data_range_label.text = "Time Range: No data"
            self._memory_usage_label.text = "Memory Usage: --"
            self._load_time_label.text = "Load Time: --"
            return
            
        # 기본 통계
        total_records = self._controller._data_cache.get_total_records()
        sensor_ids = self._controller._data_cache.get_sensor_ids()
        active_sensors = len(sensor_ids)
        
        self._total_records_label.text = f"Total Records: {total_records:,}"
        self._sensors_count_label.text = f"Active Sensors: {active_sensors}/24"
        
        # 시간 범위
        start_time = self._controller.get_start_time()
        end_time = self._controller.get_end_time()
        if start_time and end_time:
            self._data_range_label.text = f"Range: {start_time.strftime('%m-%d')} to {end_time.strftime('%m-%d')}"
        
        # 로드 시간 정보
        if hasattr(self._controller, '_load_start_time') and hasattr(self._controller, '_load_end_time'):
            if self._controller._load_start_time and self._controller._load_end_time:
                load_duration = self._controller._load_end_time - self._controller._load_start_time
                self._load_time_label.text = f"Load Time: {load_duration:.2f}s"
        
        # 메모리 사용량 (대략적 계산)
        estimated_memory_mb = (total_records * 32) / (1024 * 1024)  # 32 bytes per record
        self._memory_usage_label.text = f"Memory Usage: ~{estimated_memory_mb:.1f} MB"
        
        # 센서별 상세 정보 업데이트
        self._update_sensor_details(sensor_ids)
        
    def _update_sensor_details(self, sensor_ids):
        """센서별 데이터 개수 업데이트"""
        # 기존 센서 정보 제거
        self._sensor_details_stack.clear()
        
        if not sensor_ids:
            with self._sensor_details_stack:
                ui.Label("No sensor data loaded")
            return
            
        # 센서별 정보 표시
        with self._sensor_details_stack:
            for sensor_id in sorted(sensor_ids):
                sensor_data = self._controller._data_cache.get_sensor_data(sensor_id)
                record_count = sensor_data.size
                
                # 해당 센서의 랙 이름 찾기
                rack_name = "Unknown"
                for rack_path, mapped_id in self._controller._rack_to_sensor_map.items():
                    if mapped_id == sensor_id:
                        rack_name = rack_path.split('/')[-1]
                        break
                
                # 센서 정보 레이블
                with ui.HStack():
                    ui.Label(f"ID {sensor_id}:", width=60)
                    ui.Label(f"{rack_name}", width=100)
                    ui.Label(f"{record_count:,} records", width=80)
        
    def _on_time_slider_changed(self, model):
        """시간 슬라이더 변경"""
        progress = model.get_value_as_float()
        self._controller.set_time_progress(progress)
        
    def _on_toggle_playback(self):
        """재생/정지 토글"""
        self._controller.toggle_playback()
        if self._controller.is_playing():
            self._play_button.text = "Pause"
        else:
            self._play_button.text = "Play"
            
    def _on_stop_playback(self):
        """재생 정지"""
        if self._controller.is_playing():
            self._controller.toggle_playback()
        self._play_button.text = "Play"
        
    def _on_speed_changed(self, model):
        """재생 속도 변경"""
        speed = model.get_value_as_float()
        self._controller.set_playback_speed(speed)
        self._speed_label.text = f"Speed: {speed:.1f}x"
        
    def _on_go_to_start(self):
        """시작 시점으로 이동"""
        self._controller.set_time_progress(0.0)
        
    def _on_go_to_present(self):
        """현재 시점으로 이동"""
        self._controller.set_time_progress(1.0)
        
    def _on_select_rack(self, rack_path: str):
        """랙 선택"""
        self._selected_rack_path = rack_path
        rack_name = rack_path.split('/')[-1]
        self._selected_rack_label.text = rack_name
        self._update_selected_rack_data()
        
    def update_ui(self):
        """UI 업데이트 (정기적으로 호출됨)"""
        current_time = self._controller.get_current_time()
        if current_time:
            self._current_time_label.text = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 시간 슬라이더 업데이트 (무한 루프 방지)
            if self._time_slider and not self._controller.is_playing():
                progress = self._controller.get_time_progress()
                self._time_slider.model.set_value(progress)
        
        # 선택된 랙의 센서 데이터 업데이트
        self._update_selected_rack_data()
        
        # 로딩 중인 경우 진행 상태 업데이트
        if hasattr(self._controller, '_loading_future') and self._controller._loading_future:
            if not self._controller._loading_future.done():
                self._loading_progress_label.text = "Loading data files..."
            else:
                self._loading_progress_label.text = "Load completed"
        
    def _update_selected_rack_data(self):
        """선택된 랙의 센서 데이터 업데이트"""
        if not self._selected_rack_path:
            return
            
        data = self._controller.get_rack_data_at_time(self._selected_rack_path)
        
        if data:
            self._temp_cold_label.text = f"{data['temperature_cold']:.1f}°C"
            self._temp_hot_label.text = f"{data['temperature_hot']:.1f}°C"
            self._humidity_cold_label.text = f"{data['humidity_cold']:.1f}%"
            self._humidity_hot_label.text = f"{data['humidity_hot']:.1f}%"
        else:
            self._temp_cold_label.text = "--.-°C"
            self._temp_hot_label.text = "--.-°C"
            self._humidity_cold_label.text = "--.-%"
            self._humidity_hot_label.text = "--.-%"
            
    def destroy(self):
        """윈도우 정리"""
        if self._window:
            self._window.destroy()
            self._window = None