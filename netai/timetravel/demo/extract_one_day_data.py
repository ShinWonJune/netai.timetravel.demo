import csv
import os
from datetime import datetime

def extract_one_day_data(input_file, output_file, target_date='2025-03-27'):
    """
    fms_temphum_03260406.csv 파일에서 특정 날짜(기본값: 2025-03-27)의 데이터만 추출하여
    새로운 CSV 파일로 저장합니다.
    
    Args:
        input_file (str): 입력 CSV 파일 경로
        output_file (str): 출력 CSV 파일 경로
        target_date (str): 추출할 날짜 (YYYY-MM-DD 형식)
    
    Returns:
        int: 추출된 행 수
    """
    try:
        if not os.path.exists(input_file):
            print(f"입력 파일을 찾을 수 없습니다: {input_file}")
            return 0
        
        # 데이터 로드 및 필터링
        filtered_rows = []
        headers = None
        
        with open(input_file, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            
            # 헤더 읽기
            headers = next(reader)
            
            # 타임스탬프 필드 인덱스 찾기
            timestamp_idx = headers.index('@timestamp') if '@timestamp' in headers else 0
            
            # 행 필터링
            for row in reader:
                if len(row) <= timestamp_idx:
                    continue  # 잘못된 행 건너뛰기
                
                # 타임스탬프에서 날짜 추출
                timestamp = row[timestamp_idx]
                try:
                    # 타임스탬프 파싱
                    if '.' in timestamp and timestamp.endswith('Z'):
                        dt_obj = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                    elif timestamp.endswith('Z'):
                        dt_obj = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                    else:
                        dt_obj = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
                    
                    # 날짜만 추출 (YYYY-MM-DD)
                    row_date = dt_obj.strftime("%Y-%m-%d")
                    
                    # 타겟 날짜와 일치하면 추가
                    if row_date == target_date:
                        filtered_rows.append(row)
                except (ValueError, TypeError) as e:
                    print(f"타임스탬프 파싱 오류: {timestamp}, 오류: {e}")
                    continue
        
        # 결과 저장
        if filtered_rows:
            with open(output_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)  # 헤더 쓰기
                writer.writerows(filtered_rows)  # 필터링된 데이터 쓰기
            
            print(f"데이터 추출 완료: {len(filtered_rows)}개 행이 {output_file}에 저장되었습니다.")
            return len(filtered_rows)
        else:
            print(f"지정한 날짜({target_date})의 데이터가 없습니다.")
            return 0
    
    except Exception as e:
        print(f"데이터 추출 중 오류 발생: {e}")
        return 0

def main():
    # 현재 스크립트 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 입출력 파일 경로
    input_file = os.path.join(script_dir, "fms_temphum_03260406.csv")
    output_file = os.path.join(script_dir, "fms_temphum_0327.csv")
    
    # 데이터 추출 (2025-03-27 하루치 데이터)
    extract_one_day_data(input_file, output_file, "2025-03-27")

if __name__ == "__main__":
    main()