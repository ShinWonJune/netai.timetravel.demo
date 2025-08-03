# -*- coding: utf-8 -*-
import omni.ext
import omni.kit.app
import subprocess
import sys
import importlib.util

class NetaiTimetravelDemoExtension(omni.ext.IExt):
    
    def on_startup(self, ext_id):
        print("[netai.timetravel.demo] Extension startup")
        
        # 필요한 패키지들 확인 및 설치
        self._ensure_dependencies()
        
        # 나머지 초기화 코드...
        self._setup_extension()
    
    def _ensure_dependencies(self):
        """필요한 dependency들 확인 및 설치"""
        required_packages = {
            'pyarrow': 'pyarrow',
            'minio': 'minio', 
            'requests': 'requests'
        }
        
        print("[netai.timetravel.demo] Checking dependencies...")
        
        for import_name, package_name in required_packages.items():
            if not self._is_package_available(import_name):
                print(f"[netai.timetravel.demo] Installing {package_name}...")
                success = self._install_package(package_name)
                if success:
                    print(f"[netai.timetravel.demo] ✅ {package_name} installed")
                else:
                    print(f"[netai.timetravel.demo] ❌ Failed to install {package_name}")
            else:
                print(f"[netai.timetravel.demo] ✅ {import_name} already available")
    
    def _is_package_available(self, package_name):
        """패키지 사용 가능 여부 확인"""
        try:
            spec = importlib.util.find_spec(package_name)
            return spec is not None
        except ImportError:
            return False
    
    def _install_package(self, package_name):
        """Omniverse Python 환경에 패키지 설치"""
        try:
            # Omniverse Python executable 경로
            python_exe = sys.executable
            print(f"[netai.timetravel.demo] Using Python: {python_exe}")
            
            # pip install 실행
            cmd = [python_exe, "-m", "pip", "install", package_name, "--user", "--quiet"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print(f"[netai.timetravel.demo] Successfully installed {package_name}")
                return True
            else:
                print(f"[netai.timetravel.demo] Installation failed for {package_name}:")
                print(f"  stdout: {result.stdout}")
                print(f"  stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"[netai.timetravel.demo] Installation timeout for {package_name}")
            return False
        except Exception as e:
            print(f"[netai.timetravel.demo] Installation error for {package_name}: {e}")
            return False
    
    def _setup_extension(self):
        """Extension 설정"""
        try:
            # 이제 패키지들이 설치되었으므로 import 시도
            from .controller import TimeController
            from .window import TimeWindowUI
            
            # Extension 초기화
            self._controller = TimeController()
            self._window_ui = TimeWindowUI(self._controller)
            
            print("[netai.timetravel.demo] Extension setup completed")
            
        except ImportError as e:
            print(f"[netai.timetravel.demo] Import error after installation: {e}")
            print("[netai.timetravel.demo] Please restart Omniverse to use new packages")
        except Exception as e:
            print(f"[netai.timetravel.demo] Setup error: {e}")
    
    def on_shutdown(self):
        print("[netai.timetravel.demo] Extension shutdown")
        
        # 정리
        if hasattr(self, '_window_ui'):
            self._window_ui.destroy()
        if hasattr(self, '_controller'):
            self._controller.destroy()