# Requirements
- Visual studio, with Desktop development with C++ (for USD package installation)
- Omniverse Launcher
- Omniverse Kit
- USD package
	- https://github.com/PixarAnimationStudios/OpenUSD?tab=readme-ov-file
	- PySide6,PyOpenGL
```cmd
pip install PyOpenGL
pip install PySide6
```
- 환경 변수 추가
	- pip show PySide6 : location 환경 변수 추가
	- where pyside6-uic : 환경 변수 추가
	- 근데 계속 PyOpenGL 설치 안된다함.
	- 그래서 일시적인 path 추가를 해봄.
```cmd
set PYTHONPATH=C:\Users\wonjune\Anaconda3\Lib\site-packages;%PYTHONPATH%
# PYTHONPATH가 기존의 PATH들, %PATH% 앞에 참조하게 설정
# 프롬프트를 다시 시작하면 되돌이됨
```
	- 환경 변수에 PYTHONPATH 새로 생성하고 경로 추가해주면 됐었다.
- 이제야 USD 빌드 스크립트 실행됨 (**x64 Native Tools Command Prompt에서 실행**)
```x64 Native Tools Command Prompt
C:\> python OpenUSD\build_scripts\build_usd.py "C:\path\to\my_usd_install_dir"
```
