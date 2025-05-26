import os
import carb

from .csv_provider import CSVSensorDataProvider
from .server_provider import ServerSensorDataProvider

def create_data_provider(provider_type=None):
    """설정에 따라 적절한 데이터 프로바이더 인스턴스 생성"""
    settings = carb.settings.get_settings()
    
    # 프로바이더 타입이 지정되지 않은 경우 설정에서 가져옴
    if provider_type is None:
        provider_type = settings.get("/exts/netai.timetravel.demo/data_source_type")
        if provider_type is None or provider_type == "":
            provider_type = "csv"  # 기본값
    
    if provider_type == "server":
        # 서버 URL 및 인증 토큰 가져오기
        server_url = settings.get("/exts/netai.timetravel.demo/server_url")
        auth_token = settings.get("/exts/netai.timetravel.demo/auth_token")
        
        if not server_url:
            print("[netai.timetravel.demo] 서버 URL이 설정되지 않았습니다. CSV 데이터 소스로 폴백합니다.")
            return create_csv_provider()
        
        print(f"[netai.timetravel.demo] 서버 데이터 소스 사용: {server_url}")
        return ServerSensorDataProvider(server_url, auth_token)
    else:
        # 기본 CSV 데이터 프로바이더 생성
        return create_csv_provider()

def create_csv_provider(csv_path=None):
    """CSV 데이터 프로바이더 생성"""
    if csv_path is None:
        # 현재 익스텐션 디렉토리 결정
        ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 기본 CSV 파일 경로
        csv_path = os.path.join(ext_dir, "fms_temphum_0327.csv")
        
        if not os.path.exists(csv_path):
            # 대체 CSV 파일 경로
            csv_path = os.path.join(ext_dir, "fms_temphum_objId21_last24h.csv")
            print(f"[netai.timetravel.demo] 기본 CSV 파일 없음, 대체 파일 사용: {csv_path}")
    
    print(f"[netai.timetravel.demo] CSV 데이터 소스 사용: {csv_path}")
    return CSVSensorDataProvider(csv_path)