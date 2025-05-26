# -*- coding: utf-8 -*-
import omni.ui as ui
import datetime

class TimeWindowUI:
    """Time Travel Window UI"""
    
    def __init__(self, controller):
        """Time window UI initialization"""
        self._controller = controller
        
        # Create window
        self._window = ui.Window("Time Travel", width=400, height=350)  # 높이 증가
        
        # Build UI
        with self._window.frame:
            with ui.VStack(spacing=5):
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
                
                # # 시간 윈도우 적용 버튼
                # with ui.HStack(height=30):
                    self._apply_button = ui.Button("Apply", width=100)
                    self._apply_button.set_clicked_fn(lambda: self._on_apply_clicked())


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
                with ui.HStack(height=30):

                    ui.Spacer(width=10)
                    
                    self._present_button = ui.Button("Present", width=100)
                    self._present_button.set_clicked_fn(lambda: self._on_present_clicked())
                
                ui.Spacer(height=10)
                
                # USD Stage time display
                with ui.HStack(height=30):
                    ui.Label("Current Time: ", width=120, style={"font_size": 18})
                    self._stage_time_label = ui.Label("", width=280, style={"font_size": 18})

                
                ui.Spacer(height=10)
                
                # Time slider
                with ui.HStack(height=30):
                    self._time_slider = ui.FloatSlider(min=0, max=1, width=ui.Percent(100))
                    self._time_slider.model.set_value(self._controller.get_progress())
                    self._time_slider.model.add_value_changed_fn(self._on_slider_changed)
                
                ui.Spacer(height=10)
                # 새로 추가: 온도와 습도를 표시하는 UI 영역
                with ui.HStack(height=30):
                    ui.Label("Temperature: ", width=120, style={"font_size": 18})
                    self._temperature_label = ui.Label("", width=80, style={"font_size": 18})
                    ui.Spacer(width=20)
                    ui.Label("Humidity: ", width=120, style={"font_size": 18})
                    self._humidity_label = ui.Label("", width=80, style={"font_size": 18})
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
    
    # 새로 추가: 특정 시간으로 이동하는 함수
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
    
    # 기존 메서드들 유지...
    def destroy(self):
        """Clean up UI"""
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
        # 현재 시간을 TimeController에서 가져와 문자열로 변환 후 표시
        current_time = self._controller.get_current_time()
        if current_time:
            self._stage_time_label.text = current_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            self._stage_time_label.text = "N/A"
        
        # 온도와 습도 정보 업데이트
        sensor_data = self._controller.get_current_sensor_data()
        if sensor_data is not None:
            self._temperature_label.text = str(sensor_data["TEMPERATURE1"])
            self._humidity_label.text = str(sensor_data["HUMIDITY1"])
        else:
            self._temperature_label.text = "N/A"
            self._humidity_label.text = "N/A"
        
        # 슬라이더 및 플레이 버튼 업데이트
        if self._controller.is_playing():
            self._time_slider.model.set_value(self._controller.get_progress())
            self._play_button.text = "Pause"
        else:
            self._play_button.text = "Play"
