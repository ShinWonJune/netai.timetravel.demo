"""
Time Travel Demo Extension Configuration
데이터센터 랙과 센서 ID 매핑 설정
"""

# 랙-센서 매핑 정보
RACK_SENSOR_MAPPING = {
    # A 구역 랙들
    "/datacenter/RACK_A1": "20",
    "/datacenter/RACK_A3": "21", 
    "/datacenter/RACK_A5": "22",
    "/datacenter/RACK_A7": "23",
    "/datacenter/RACK_A10": "24",
    "/datacenter/RACK_A12": "25",
    
    # B 구역 랙들
    "/datacenter/RACK_B1": "191",
    "/datacenter/RACK_B3": "192",
    "/datacenter/RACK_B5": "193",
    "/datacenter/RACK_B10": "194",
    "/datacenter/RACK_B12": "195", 
    "/datacenter/RACK_B14": "196",
    
    # A0, A2, A4, A6, A8, A9 구역 랙들 (01)
    "/datacenter/RACK_A0_01": "203",
    "/datacenter/RACK_A2_01": "204",
    "/datacenter/RACK_A4_01": "205",
    "/datacenter/RACK_A6_01": "206",
    "/datacenter/RACK_A8_01": "207",
    "/datacenter/RACK_A9_01": "208",
    
    # A0, A2, A4, A6, A8, A9 구역 랙들 (02)
    "/datacenter/RACK_A0_02": "197",
    "/datacenter/RACK_A2_02": "198",
    "/datacenter/RACK_A4_02": "199",
    "/datacenter/RACK_A6_02": "200",
    "/datacenter/RACK_A8_02": "201",
    "/datacenter/RACK_A9_02": "202",
}

# 정의된 랙 경로 목록 (매핑에서 키 값들과 동일)
PREDEFINED_RACK_PATHS = list(RACK_SENSOR_MAPPING.keys())

# USD 스테이지에서 가능한 경로 접두사들 (우선순위 순)
POSSIBLE_PATH_PREFIXES = [
    "",  # 기본 경로 (접두사 없음)
    "/Root",  # /Root 접두사
    "/World/Root",  # /World/Root 접두사
]

# 센서 데이터 파일 설정
SENSOR_DATA_CONFIG = {
    "csv_file": "fms_temphum_0327.csv",
    "timestamp_column": "@timestamp",
    "obj_id_column": "objId",
    "temperature_columns": {
        "cold": "TEMPERATURE1",
        "hot": "TEMPERATURE"
    },
    "humidity_columns": {
        "cold": "HUMIDITY1", 
        "hot": "HUMIDITY"
    }
}

# USD 속성 설정
USD_ATTRIBUTE_CONFIG = {
    "time_manager_path": "/World/TimeManager",
    "rack_attributes": {
        "temperature_cold": "temperature_cold",
        "temperature_hot": "temperature_hot", 
        "humidity_cold": "humidity_cold",
        "humidity_hot": "humidity_hot"
    },
    "metadata_keys": [
        "temperature_cold", "temperature_hot",
        "humidity_cold", "humidity_hot", 
        "timestamp", "sensor_id", "data_source"
    ]
}

# 로그 설정
LOG_PREFIX = "[netai.timetravel.demo]"

# 기본 시간 설정
DEFAULT_TIME_CONFIG = {
    "base_time": "2025-01-01T00:00:00.00Z",
    "default_start": "2025-03-26T00:00:00",
    "default_end": "2025-03-27T00:00:00"
}
