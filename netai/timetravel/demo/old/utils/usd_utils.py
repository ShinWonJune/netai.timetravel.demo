from pxr import Usd, UsdGeom, Sdf

def find_racks_in_stage(stage, patterns=None):
    """USD 스테이지에서 랙 경로 검색"""
    if not stage:
        return []
        
    if patterns is None:
        patterns = [
            "/Root/datacenter/RACK_*",
            "/World/Root/datacenter/RACK_*"
        ]
    
    found_racks = []
    
    for pattern in patterns:
        # 패턴에서 기본 경로 추출
        base_path = pattern.split("RACK_")[0]
        base_prim = stage.GetPrimAtPath(base_path)
        
        if not base_prim or not base_prim.IsValid():
            continue
            
        # 자식 프림 중 RACK_ 접두사를 가진 것 검색
        for child_prim in base_prim.GetChildren():
            if child_prim.GetName().startswith("RACK_"):
                rack_path = child_prim.GetPath().pathString
                found_racks.append(rack_path)
    
    return found_racks

# usd_utils.py에 디버깅 추가
def update_rack_attributes(stage, rack_path, sensor_data):
    """랙 객체의 센서 데이터 속성 업데이트"""
    print(f"[DEBUG] update_rack_attributes 호출: {rack_path}")
    
    if not stage or not rack_path:
        print(f"[DEBUG] stage 또는 rack_path가 없음")
        return False
        
    rack_prim = stage.GetPrimAtPath(rack_path)
    if not rack_prim or not rack_prim.IsValid():
        print(f"[netai.timetravel.demo] 랙 객체를 찾을 수 없음: {rack_path}")
        return False
    
    try:
        if not sensor_data:
            print(f"[DEBUG] 센서 데이터 없음, 속성 초기화")
            # 데이터가 없는 경우 속성 초기화
            for attr_name in ["temperature_cold", "temperature_hot", "humidity_cold", "humidity_hot"]:
                if rack_prim.HasAttribute(attr_name):
                    rack_prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float).Set(float('nan'))
            return True
            
        # 센서 데이터에서 값 추출
        temp1 = float(sensor_data.get("TEMPERATURE1", 0.0))
        temp2 = float(sensor_data.get("TEMPERATURE", 0.0))
        hum1 = float(sensor_data.get("HUMIDITY1", 0.0))
        hum2 = float(sensor_data.get("HUMIDITY", 0.0))
        
        print(f"[DEBUG] 속성 업데이트: temp1={temp1}, temp2={temp2}, hum1={hum1}, hum2={hum2}")
        
        # 속성 업데이트
        rack_prim.CreateAttribute("temperature_cold", Sdf.ValueTypeNames.Float).Set(temp1)
        rack_prim.CreateAttribute("temperature_hot", Sdf.ValueTypeNames.Float).Set(temp2)
        rack_prim.CreateAttribute("humidity_cold", Sdf.ValueTypeNames.Float).Set(hum1)
        rack_prim.CreateAttribute("humidity_hot", Sdf.ValueTypeNames.Float).Set(hum2)
        
        # 메타데이터 업데이트
        rack_prim.SetCustomDataByKey("temperature_cold", temp1)
        rack_prim.SetCustomDataByKey("temperature_hot", temp2)
        rack_prim.SetCustomDataByKey("humidity_cold", hum1)
        rack_prim.SetCustomDataByKey("humidity_hot", hum2)
        rack_prim.SetCustomDataByKey("timestamp", sensor_data.get("@timestamp", "Unknown"))
        rack_prim.SetCustomDataByKey("sensor_id", sensor_data.get("objId", "Unknown"))
        rack_prim.SetCustomDataByKey("data_source", "sensor_data")
        
        print(f"[DEBUG] 랙 속성 업데이트 성공: {rack_path}")
        return True
    except Exception as e:
        print(f"[netai.timetravel.demo] 랙 속성 업데이트 오류 ({rack_path}): {e}")
        import traceback
        traceback.print_exc()
        return False