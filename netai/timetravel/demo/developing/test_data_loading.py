# -*- coding: utf-8 -*-
"""
Test script to verify data loading and column mapping
"""
import pandas as pd
import datetime
from config import PARQUET_COLUMN_MAPPING, SENSOR_ID_MAPPING

def test_column_mapping():
    """Test column mapping with sample data"""
    
    # Sample data matching the CSV format
    sample_data = {
        "TEMPERATURE": [24.88, 22.91, 21.88, 21.75],
        "HUMIDITY": [35.87, 39.09, 42.49, 42.03],
        "TEMPERATURE1": [19.44, 20.72, 19.59, 20.38],
        "HUMIDITY1": [49.36, 45.67, 47.4, 46.88],
        "objId": [193, 206, 197, 205],
        "rsctypeId": ["FTH", "FTH", "FTH", "FTH"],
        "@timestamp": [
            "2025-05-27 00:00:03.421",
            "2025-05-27 00:00:03.425",
            "2025-05-27 00:00:05.462",
            "2025-05-27 00:00:07.461"
        ],
        "@timestamp_utc": [
            "2025-05-26T15:00:03.421Z",
            "2025-05-26T15:00:03.425Z",
            "2025-05-26T15:00:05.462Z",
            "2025-05-26T15:00:07.461Z"
        ]
    }
    
    # Create DataFrame
    df = pd.DataFrame(sample_data)
    print("Original DataFrame:")
    print(df.head())
    print("\nColumns:", df.columns.tolist())
    
    # Apply column mapping
    rename_map = {}
    for std_name, file_name in PARQUET_COLUMN_MAPPING.items():
        if file_name in df.columns and file_name != std_name:
            rename_map[file_name] = std_name
    
    print("\nRename mapping:", rename_map)
    df_mapped = df.rename(columns=rename_map)
    
    # Convert objId to sensor names
    df_mapped['objid'] = df_mapped['objid'].map(SENSOR_ID_MAPPING)
    
    # Parse timestamp
    df_mapped['timestamp'] = pd.to_datetime(df_mapped['timestamp'])
    
    print("\nMapped DataFrame:")
    print(df_mapped[['timestamp', 'objid', 'temperature_cold', 'temperature_hot', 
                     'humidity_cold', 'humidity_hot']].head())
    
    # Verify cold/hot aisle mapping
    print("\nData verification:")
    print("Cold Aisle (TEMPERATURE1):", df_mapped['temperature_cold'].tolist())
    print("Hot Aisle (TEMPERATURE):", df_mapped['temperature_hot'].tolist())
    print("Cold Aisle (HUMIDITY1):", df_mapped['humidity_cold'].tolist())
    print("Hot Aisle (HUMIDITY):", df_mapped['humidity_hot'].tolist())
    
    return df_mapped

if __name__ == "__main__":
    test_column_mapping()