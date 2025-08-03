# -*- coding: utf-8 -*-
import omni.ui as ui
import time
import statistics
from collections import deque

class PerformanceMonitorWindow:
    """Go To 성능 측정 전용 윈도우"""
    
    def __init__(self, controller, time_window=None):
        """성능 모니터 윈도우 초기화"""
        self._controller = controller
        self._time_window = time_window
        self._is_monitoring = False
        
        # Go To 측정 데이터
        self._goto_measurements = deque(maxlen=100)
        
        # 측정 상태
        self._measuring = False
        self._measurement_start_time = None
        
        # 윈도우 생성
        self._window = ui.Window("Go To Performance Monitor", width=600, height=600)
        self._build_ui()
        
        # 초기 로그
        self._add_log("Go To Performance Monitor initialized.")
        self._add_log("Measuring: Go button click → Time Window rack data change")
        
        # Time Window 찾기 시도
        self._find_time_window()
    
    def _find_time_window(self):
        """Time Window 인스턴스 찾기 - controller를 통한 역추적"""
        if self._time_window:
            self._add_log("Time Window already provided")
            self._time_window_status.text = "Provided"
            return
        
        try:
            # 방법 1: UI 윈도우 매니저를 통해 찾기
            import omni.ui as ui
            
            # 모든 윈도우 검색
            found_windows = []
            try:
                # 현재 열린 모든 UI 윈도우 검색
                for i in range(1000):  # 임의의 큰 수로 검색
                    try:
                        window = ui.Window.get_window(f"Time Travel")
                        if window:
                            found_windows.append(window)
                            break
                    except:
                        continue
            except:
                pass
            
            # 방법 2: 전역 객체 검색
            # Python의 gc 모듈을 사용해서 TimeWindowUI 인스턴스 찾기
            import gc
            for obj in gc.get_objects():
                if hasattr(obj, '__class__') and obj.__class__.__name__ == 'TimeWindowUI':
                    # 같은 controller를 사용하는 TimeWindowUI 찾기
                    if hasattr(obj, '_controller') and obj._controller is self._controller:
                        self._time_window = obj
                        self._add_log("Time Window found via garbage collection!")
                        self._time_window_status.text = "Found (GC)"
                        return
            
            # 방법 3: 모듈 검색
            import sys
            for module_name, module in sys.modules.items():
                if 'timetravel' in module_name.lower() or 'window' in module_name.lower():
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name, None)
                        if (hasattr(attr, '__class__') and 
                            attr.__class__.__name__ == 'TimeWindowUI' and
                            hasattr(attr, '_controller') and 
                            attr._controller is self._controller):
                            self._time_window = attr
                            self._add_log("Time Window found via module search!")
                            self._time_window_status.text = "Found (Module)"
                            return
            
            self._add_log("Time Window not found - will use alternative hooks")
            self._time_window_status.text = "Not Found"
            
        except Exception as e:
            self._add_log(f"Time Window search error: {e}")
            self._time_window_status.text = "Search Error"
    
    def set_time_window(self, time_window):
        """Time Window 인스턴스 설정 (나중에 호출 가능)"""
        self._time_window = time_window
        self._add_log("Time Window instance set externally")
        if self._is_monitoring:
            self._setup_event_hooks()
    
    def _add_log(self, message):
        """로그 추가"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            log_message = f"[{timestamp}] {message}"
            
            with self._log_layout:
                ui.Label(log_message, style={"font_size": 10})
                
            print(f"[Go To Monitor] {log_message}")
        except Exception as e:
            print(f"[Go To Monitor] Log error: {e}")
    
    def _build_ui(self):
        """UI 구성"""
        with self._window.frame:
            with ui.VStack(spacing=10):
                # 제목
                ui.Label("Go To Performance Monitor", style={"font_size": 18})
                ui.Label("Measures: Go Click → Time Window Data Change", style={"font_size": 12, "color": 0xFF888888})
                ui.Separator()
                
                # 제어 버튼
                with ui.HStack(height=30):
                    self._monitor_button = ui.Button("Start Monitoring", width=150)
                    self._monitor_button.set_clicked_fn(self._toggle_monitoring)
                    
                    ui.Spacer(width=10)
                    self._clear_button = ui.Button("Clear Data", width=100)
                    self._clear_button.set_clicked_fn(self._clear_measurements)
                    
                    ui.Spacer(width=10)
                    self._find_window_button = ui.Button("Find Time Window", width=120)
                    self._find_window_button.set_clicked_fn(self._manual_find_time_window)
                
                # 현재 상태
                ui.Separator()
                with ui.HStack(height=25):
                    ui.Label("Time Window:", width=100, style={"font_size": 12, "color": 0xFFFFFF00})
                    self._time_window_status = ui.Label("Not Found", width=100, style={"font_size": 12})
                
                with ui.HStack(height=25):
                    ui.Label("Status:", width=100, style={"font_size": 12, "color": 0xFFFFFF00})
                    self._status_label = ui.Label("Ready", width=150, style={"font_size": 12})
                
                with ui.HStack(height=25):
                    ui.Label("Measuring:", width=100, style={"font_size": 12, "color": 0xFFFFFF00})
                    self._measuring_label = ui.Label("No", width=100, style={"font_size": 12})
                
                with ui.HStack(height=25):
                    ui.Label("Hooks Active:", width=100, style={"font_size": 12, "color": 0xFFFFFF00})
                    self._hooks_label = ui.Label("None", width=300, style={"font_size": 10})
                
                ui.Separator()
                
                # Go To 통계
                ui.Label("Performance Statistics:", style={"font_size": 16, "color": 0xFFFFFF00})
                
                with ui.HStack(height=25):
                    ui.Label("Measurements:", width=100)
                    self._count_label = ui.Label("0", width=50)
                    ui.Spacer(width=20)
                    ui.Label("Average:", width=60)
                    self._avg_label = ui.Label("0.00 ms", width=80)
                
                with ui.HStack(height=25):
                    ui.Label("Min:", width=100)
                    self._min_label = ui.Label("0.00 ms", width=80)
                    ui.Spacer(width=20)
                    ui.Label("Max:", width=60)
                    self._max_label = ui.Label("0.00 ms", width=80)
                
                with ui.HStack(height=25):
                    ui.Label("Last:", width=100)
                    self._last_label = ui.Label("0.00 ms", width=80)
                    ui.Spacer(width=20)
                    ui.Label("Std Dev:", width=60)
                    self._std_label = ui.Label("0.00 ms", width=80)
                
                ui.Separator()
                
                # 실시간 로그
                ui.Label("Real-time Log:", style={"font_size": 14})
                with ui.ScrollingFrame(height=200):
                    self._log_layout = ui.VStack()
    
    def _setup_alternative_hooks(self):
        """Time Window가 없을 때 대안 후킹 시스템"""
        hooks_active = []
        
        # 1. Controller의 set_current_time 직접 후킹 (Go 버튼 대신)
        if self._setup_set_current_time_hook():
            hooks_active.append("set_current_time")
        
        # 2. Controller의 _update_all_racks 후킹 (데이터 변화 감지)
        if self._setup_rack_update_hook():
            hooks_active.append("Rack Update")
        
        # 3. Controller의 _update_stage_time 후킹
        if self._setup_controller_hook():
            hooks_active.append("Stage Update")
        
        return hooks_active
    
    def _setup_set_current_time_hook(self):
        """Controller의 set_current_time 메서드 후킹 (Go 버튼 대신)"""
        try:
            if hasattr(self._controller, 'set_current_time'):
                if not hasattr(self, '_original_set_current_time'):
                    self._original_set_current_time = self._controller.set_current_time
                
                def hooked_set_current_time(current_time):
                    if self._is_monitoring:
                        self._on_go_equivalent_event()
                    
                    return self._original_set_current_time(current_time)
                
                self._controller.set_current_time = hooked_set_current_time
                self._add_log("Controller set_current_time hooked (Go equivalent)")
                return True
            else:
                self._add_log("Controller set_current_time method not found")
                return False
        except Exception as e:
            self._add_log(f"set_current_time hook error: {e}")
            return False
    
    def _on_go_equivalent_event(self):
        """Go 버튼과 동등한 이벤트 (set_current_time 호출)"""
        self._measurement_start_time = time.time()
        self._measuring = True
        self._measuring_label.text = "Yes"
        
        self._add_log("=== SET_CURRENT_TIME CALLED (Go equivalent) ===")
        self._add_log("Measurement started - waiting for data change event...")
    
    def _toggle_monitoring(self):
        """모니터링 on/off"""
        self._is_monitoring = not self._is_monitoring
        
        if self._is_monitoring:
            self._monitor_button.text = "Stop Monitoring"
            self._status_label.text = "Monitoring Active"
            self._add_log("=== MONITORING STARTED ===")
            self._setup_event_hooks()
        else:
            self._monitor_button.text = "Start Monitoring"
            self._status_label.text = "Monitoring Stopped"
            self._measuring_label.text = "No"
            self._add_log("=== MONITORING STOPPED ===")
            self._remove_event_hooks()
            
            # 진행 중인 측정 중지
            if self._measuring:
                self._measuring = False
                self._measurement_start_time = None
    
    def _setup_event_hooks(self):
        """이벤트 후킹 설정"""
        hooks_active = []
        
        # Time Window가 있는 경우 - 직접 후킹
        if self._time_window:
            if self._setup_go_button_hook():
                hooks_active.append("Go Button")
            if self._setup_data_update_hook():
                hooks_active.append("Time Window Update")
            self._add_log("Using direct Time Window hooks")
        else:
            # Time Window가 없는 경우 - 대안 후킹
            self._add_log("Time Window not available - using alternative hooks")
            alt_hooks = self._setup_alternative_hooks()
            hooks_active.extend(alt_hooks)
        
        # 공통 후킹 (항상 설정)
        if self._setup_controller_hook():
            hooks_active.append("Controller Update")
        
        if self._setup_rack_update_hook():
            hooks_active.append("Rack Update")
        
        self._hooks_label.text = ", ".join(hooks_active) if hooks_active else "None"
        self._add_log(f"Active hooks: {', '.join(hooks_active)}")
        
        if not hooks_active:
            self._add_log("WARNING: No hooks active! Monitoring may not work.")
        else:
            self._add_log("SUCCESS: Hooks are active and ready!")
    
    def _manual_find_time_window(self):
        """수동으로 Time Window 찾기"""
        self._find_time_window()
        
        # 찾았으면 다시 후킹 설정
        if self._time_window and self._is_monitoring:
            self._add_log("Re-setting up hooks with found Time Window...")
            self._remove_event_hooks()
            self._setup_event_hooks()
    
    def _setup_go_button_hook(self):
        """Go 버튼 후킹"""
        try:
            if self._time_window and hasattr(self._time_window, '_goto_button'):
                button = self._time_window._goto_button
                
                if not hasattr(self, '_original_goto_callback'):
                    self._original_goto_callback = self._time_window._on_goto_clicked
                
                def hooked_goto_callback():
                    if self._is_monitoring:
                        self._on_go_button_clicked()
                    
                    try:
                        return self._original_goto_callback()
                    except Exception as e:
                        self._add_log(f"Go button callback error: {e}")
                        raise
                
                button.set_clicked_fn(hooked_goto_callback)
                self._add_log("Go button hooked successfully")
                self._time_window_status.text = "Found & Hooked"
                return True
            else:
                self._add_log("ERROR: Go button not found!")
                return False
        except Exception as e:
            self._add_log(f"Go button hooking error: {e}")
            return False
    
    def _setup_data_update_hook(self):
        """Time Window 데이터 업데이트 메서드 후킹"""
        try:
            if self._time_window and hasattr(self._time_window, '_update_selected_rack_data'):
                if not hasattr(self, '_original_update_rack_data'):
                    self._original_update_rack_data = self._time_window._update_selected_rack_data
                
                def hooked_update_rack_data():
                    result = self._original_update_rack_data()
                    
                    if self._is_monitoring and self._measuring:
                        self._on_time_window_data_update()
                    
                    return result
                
                self._time_window._update_selected_rack_data = hooked_update_rack_data
                self._add_log("Time Window data update method hooked")
                return True
            else:
                self._add_log("Time Window data update method not found")
                return False
        except Exception as e:
            self._add_log(f"Data update hook error: {e}")
            return False
    
    def _setup_controller_hook(self):
        """Controller 업데이트 메서드 후킹"""
        try:
            if hasattr(self._controller, '_update_stage_time'):
                if not hasattr(self, '_original_update_stage_time'):
                    self._original_update_stage_time = self._controller._update_stage_time
                
                def hooked_update_stage_time():
                    result = self._original_update_stage_time()
                    
                    if self._is_monitoring and self._measuring:
                        self._on_controller_update_event()
                    
                    return result
                
                self._controller._update_stage_time = hooked_update_stage_time
                self._add_log("Controller _update_stage_time hooked")
                return True
            else:
                self._add_log("Controller _update_stage_time method not found")
                return False
        except Exception as e:
            self._add_log(f"Controller hook error: {e}")
            return False
    
    def _setup_rack_update_hook(self):
        """Controller의 랙 업데이트 메서드 후킹"""
        try:
            if hasattr(self._controller, '_update_all_racks'):
                if not hasattr(self, '_original_update_all_racks'):
                    self._original_update_all_racks = self._controller._update_all_racks
                
                def hooked_update_all_racks():
                    result = self._original_update_all_racks()
                    
                    if self._is_monitoring and self._measuring:
                        self._on_rack_update_event()
                    
                    return result
                
                self._controller._update_all_racks = hooked_update_all_racks
                self._add_log("Controller _update_all_racks hooked")
                return True
            else:
                self._add_log("Controller _update_all_racks method not found")
                return False
        except Exception as e:
            self._add_log(f"Rack update hook error: {e}")
            return False
    
    def _remove_event_hooks(self):
        """이벤트 후킹 해제"""
        try:
            # Go 버튼 후킹 해제
            if hasattr(self, '_original_goto_callback') and self._time_window:
                self._time_window._goto_button.set_clicked_fn(self._original_goto_callback)
            
            # Time Window 데이터 업데이트 후킹 해제
            if hasattr(self, '_original_update_rack_data') and self._time_window:
                self._time_window._update_selected_rack_data = self._original_update_rack_data
            
            # Controller 후킹 해제
            if hasattr(self, '_original_update_stage_time'):
                self._controller._update_stage_time = self._original_update_stage_time
            
            # Rack 업데이트 후킹 해제
            if hasattr(self, '_original_update_all_racks'):
                self._controller._update_all_racks = self._original_update_all_racks
            
            # set_current_time 후킹 해제
            if hasattr(self, '_original_set_current_time'):
                self._controller.set_current_time = self._original_set_current_time
            
            self._hooks_label.text = "None"
            self._add_log("All hooks removed")
        except Exception as e:
            self._add_log(f"Hook removal error: {e}")
    
    def _on_go_button_clicked(self):
        """Go 버튼 클릭 이벤트"""
        self._measurement_start_time = time.time()
        self._measuring = True
        self._measuring_label.text = "Yes"
        
        self._add_log("=== GO BUTTON CLICKED ===")
        self._add_log("Measurement started - waiting for data change event...")
    
    def _on_time_window_data_update(self):
        """Time Window 데이터 업데이트 이벤트"""
        if not self._measuring or not self._measurement_start_time:
            return
        
        end_time = time.time()
        delay = (end_time - self._measurement_start_time) * 1000  # ms
        
        self._complete_measurement(delay, "Time Window Data Update")
    
    def _on_controller_update_event(self):
        """Controller 업데이트 이벤트"""
        if not self._measuring or not self._measurement_start_time:
            return
        
        end_time = time.time()
        delay = (end_time - self._measurement_start_time) * 1000  # ms
        
        self._complete_measurement(delay, "Controller Stage Update")
    
    def _on_rack_update_event(self):
        """Rack 업데이트 이벤트"""
        if not self._measuring or not self._measurement_start_time:
            return
        
        end_time = time.time()
        delay = (end_time - self._measurement_start_time) * 1000  # ms
        
        self._complete_measurement(delay, "Rack Data Update")
    
    def _complete_measurement(self, delay, event_type):
        """측정 완료"""
        # 측정 결과 저장
        measurement = {
            'delay_ms': delay,
            'timestamp': time.time(),
            'event_type': event_type
        }
        
        self._goto_measurements.append(measurement)
        
        # 로그 출력
        self._add_log("=== MEASUREMENT COMPLETED ===")
        self._add_log(f"Event type: {event_type}")
        self._add_log(f"Go To delay: {delay:.2f}ms")
        self._add_log(f"Total measurements: {len(self._goto_measurements)}")
        
        # 상태 초기화
        self._measuring = False
        self._measurement_start_time = None
        self._measuring_label.text = "No"
        
        # UI 업데이트
        self._update_statistics()
    
    def _update_statistics(self):
        """통계 UI 업데이트"""
        try:
            count = len(self._goto_measurements)
            if count > 0:
                delays = [m['delay_ms'] for m in self._goto_measurements]
                
                self._count_label.text = str(count)
                self._avg_label.text = f"{statistics.mean(delays):.2f} ms"
                self._min_label.text = f"{min(delays):.2f} ms"
                self._max_label.text = f"{max(delays):.2f} ms"
                self._last_label.text = f"{delays[-1]:.2f} ms"
                self._std_label.text = f"{statistics.stdev(delays) if len(delays) > 1 else 0:.2f} ms"
                
                self._add_log(f"Statistics updated: avg={statistics.mean(delays):.2f}ms")
            else:
                self._count_label.text = "0"
                self._avg_label.text = "0.00 ms"
                self._min_label.text = "0.00 ms"
                self._max_label.text = "0.00 ms"
                self._last_label.text = "0.00 ms"
                self._std_label.text = "0.00 ms"
        except Exception as e:
            self._add_log(f"Statistics update error: {e}")
    
    def _clear_measurements(self):
        """측정 데이터 초기화"""
        self._goto_measurements.clear()
        self._update_statistics()
        
        # 로그도 초기화
        try:
            self._log_layout.clear()
            self._add_log("Measurement data cleared.")
        except:
            pass
    
    def destroy(self):
        """윈도우 정리"""
        self._is_monitoring = False
        self._remove_event_hooks()
        
        if self._window:
            self._window = None