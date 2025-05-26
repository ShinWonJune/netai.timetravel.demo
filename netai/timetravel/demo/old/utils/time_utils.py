from datetime import datetime

def parse_timestamp(timestamp_str):
    """다양한 형식의 타임스탬프 문자열을 datetime 객체로 파싱"""
    if not timestamp_str:
        return None
        
    try:
        # 밀리초가 있는 ISO 형식 (예: 2025-03-26T06:15:48.846Z)
        if "." in timestamp_str and timestamp_str.endswith("Z"):
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        # 밀리초 없는 ISO 형식 (예: 2025-03-26T06:15:48Z)
        elif timestamp_str.endswith("Z"):
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
        # Z 접미사 없는 형식 (예: 2025-03-26T06:15:48)
        else:
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        print(f"[netai.timetravel.demo] 타임스탬프 파싱 오류: {timestamp_str} - {e}")
        return None

def format_timestamp(dt_obj, include_millis=True):
    """datetime 객체를 ISO 형식 문자열로 변환"""
    if not dt_obj:
        return None
        
    try:
        if include_millis:
            # 밀리초 포함 (예: 2025-03-26T06:15:48.123Z)
            return dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        else:
            # 밀리초 미포함 (예: 2025-03-26T06:15:48Z)
            return dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        print(f"[netai.timetravel.demo] 타임스탬프 포맷 오류: {e}")
        return None