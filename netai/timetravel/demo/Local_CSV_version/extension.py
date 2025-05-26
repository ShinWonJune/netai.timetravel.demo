import omni.ext
import omni.ui as ui
from pxr import Usd, UsdGeom, Sdf
import datetime

# 추가 모듈 임포트
from .window import TimeWindowUI
from .controller import TimeController

class NetaiTimetravelDemoExtension(omni.ext.IExt):
    """디지털 트윈에서 시간 여행 기능을 제공하는 익스텐션"""
    
    def on_startup(self, ext_id):
        """익스텐션 시작 시 호출"""
        print("[netai.timetravel.demo] Time Travel Demo 시작")
        
        # 시간 컨트롤러 초기화
        self._time_controller = TimeController()
        
        # UI 윈도우 생성
        self._window = TimeWindowUI(self._time_controller)
        
        # 업데이트 콜백 설정
        self._update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self._on_update, name="time_travel_update"
        )
    
    def on_shutdown(self):
        """익스텐션 종료 시 호출"""
        print("[netai.timetravel.demo] Time Travel Demo 종료")
        
        # 구독 정리
        self._update_sub = None
        
        # UI 정리
        if self._window:
            self._window.destroy()
            self._window = None
        
        # 컨트롤러 정리
        self._time_controller = None
    
    def _on_update(self, e):
        """애니메이션을 위한 업데이트 콜백"""
        if self._time_controller:
            self._time_controller.update()
            
        # 윈도우 UI 업데이트 (Timer 대신 이 방식 사용)
        if self._window:
            self._window.update_ui()