# -*- coding: utf-8 -*-
import omni.ext
import omni.usd
import omni.timeline
from .optimized_controller import OptimizedTimeController
from .window import TimeWindowUI

class NetaiTimetravelDemoExtension(omni.ext.IExt):
    """Time Travel Extension for Datacenter Digital Twin"""
    
    def on_startup(self, ext_id):
        """Called when extension is starting up"""
        print("[netai.timetravel.demo] Time Travel Extension startup")
        
        # Create optimized controller
        self._controller = OptimizedTimeController()
        
        # Get USD context and stage
        self._usd_context = omni.usd.get_context()
        stage = self._usd_context.get_stage()
        if stage:
            self._controller.set_stage(stage)
        
        # Setup stage listener for future stage changes
        self._setup_stage_listener()
        
        # Create UI window
        self._window = TimeWindowUI(self._controller)
        
        # Setup update loop for real-time updates
        self._setup_update_loop()
        
        print("[netai.timetravel.demo] Extension started successfully")
        
    def _setup_stage_listener(self):
        """Setup listener for stage events"""
        try:
            # Subscribe to stage events
            self._stage_event_sub = self._usd_context.get_stage_event_stream().create_subscription_to_pop(
                self._on_stage_event, name="time_travel_stage_event"
            )
        except Exception as e:
            print(f"[netai.timetravel.demo] Failed to setup stage listener: {e}")
            self._stage_event_sub = None
    
    def _on_stage_event(self, event):
        """Handle stage events"""
        try:
            # Handle stage opening/closing
            if event.type == int(omni.usd.StageEventType.OPENED):
                stage = self._usd_context.get_stage()
                if stage and self._controller:
                    self._controller.set_stage(stage)
                    print("[netai.timetravel.demo] Stage opened, controller updated")
            elif event.type == int(omni.usd.StageEventType.CLOSED):
                if self._controller:
                    self._controller.set_stage(None)
                    print("[netai.timetravel.demo] Stage closed")
        except Exception as e:
            print(f"[netai.timetravel.demo] Error handling stage event: {e}")
            
    def _setup_update_loop(self):
        """Setup update loop for playback and UI updates"""
        try:
            # Get timeline interface for update events
            self._timeline = omni.timeline.get_timeline_interface()
            
            # Subscribe to timeline events for regular updates
            self._timeline_event_sub = self._timeline.get_timeline_event_stream().create_subscription_to_pop(
                self._on_timeline_event, name="time_travel_timeline_event"
            )
            
            # Also setup a regular update using Omniverse's update stream
            import omni.kit.app
            self._app_update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
                self._on_update, name="time_travel_update"
            )
            
        except Exception as e:
            print(f"[netai.timetravel.demo] Failed to setup update loop: {e}")
            self._timeline_event_sub = None
            self._app_update_sub = None
            
    def _on_timeline_event(self, event):
        """Handle timeline events"""
        try:
            # Update controller on timeline events
            if self._controller:
                self._controller.update_playback()
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in timeline event: {e}")
            
    def _on_update(self, event):
        """Handle regular update events"""
        try:
            # Update controller playback
            if self._controller:
                self._controller.update_playback()
            
            # Update UI
            if self._window:
                self._window.update_ui()
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error in update loop: {e}")

    def on_shutdown(self):
        """Called when extension is shutting down"""
        print("[netai.timetravel.demo] Time Travel Extension shutdown")
        
        try:
            # Cleanup subscriptions
            if hasattr(self, '_stage_event_sub') and self._stage_event_sub:
                self._stage_event_sub = None
                
            if hasattr(self, '_timeline_event_sub') and self._timeline_event_sub:
                self._timeline_event_sub = None
                
            if hasattr(self, '_app_update_sub') and self._app_update_sub:
                self._app_update_sub = None
            
            # Cleanup UI window
            if hasattr(self, '_window') and self._window:
                self._window.destroy()
                self._window = None
            
            # Cleanup controller
            if hasattr(self, '_controller') and self._controller:
                # Could add cleanup method to controller if needed
                self._controller = None
                
        except Exception as e:
            print(f"[netai.timetravel.demo] Error during shutdown: {e}")