# -*- coding: utf-8 -*-
"""
MinIO connection and parquet data mapping test (PyArrow only, no pandas)
"""

from datetime import datetime
from typing import Dict, Optional, Set, List
from .config import Config
import tempfile
import os

# Try to use PyArrow
try:
    import pyarrow.parquet as pq
    import pyarrow as pa
    PYARROW_AVAILABLE = True
    print("[MinIO Test] PyArrow library available")
except ImportError:
    PYARROW_AVAILABLE = False
    print("[MinIO Test] PyArrow library not available")

# Try to use MinIO
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
    print("[MinIO Test] MinIO library available")
except ImportError:
    MINIO_AVAILABLE = False
    print("[MinIO Test] MinIO library not available")

def test_minio_connection():
    """MinIO connection test"""
    if not MINIO_AVAILABLE:
        print("[MinIO Test] MinIO library not installed")
        return False
    
    try:
        print(f"[MinIO Test] Attempting MinIO connection: {Config.MINIO_ENDPOINT}")
        
        client = Minio(
            endpoint=Config.MINIO_ENDPOINT,
            access_key=Config.MINIO_ACCESS_KEY,
            secret_key=Config.MINIO_SECRET_KEY,
            secure=Config.MINIO_SECURE
        )
        
        # Check bucket existence
        if client.bucket_exists(Config.MINIO_BUCKET):
            print(f"[MinIO Test] ✅ Bucket '{Config.MINIO_BUCKET}' exists")
        else:
            print(f"[MinIO Test] ❌ Bucket '{Config.MINIO_BUCKET}' not found")
            return False
        
        # List files
        print(f"[MinIO Test] Files in '{Config.MINIO_PREFIX}' folder:")
        objects = client.list_objects(Config.MINIO_BUCKET, prefix=Config.MINIO_PREFIX)
        
        parquet_files = []
        for obj in objects:
            print(f"  - {obj.object_name} (size: {obj.size} bytes)")
            if obj.object_name.endswith('.parquet'):
                parquet_files.append(obj.object_name)
        
        if parquet_files:
            print(f"[MinIO Test] ✅ Found {len(parquet_files)} parquet files")
            return True, client, parquet_files
        else:
            print(f"[MinIO Test] ❌ No parquet files found")
            return False, None, []
        
    except Exception as e:
        print(f"[MinIO Test] ❌ Connection error: {e}")
        import traceback
        print(f"[MinIO Test] Detailed error: {traceback.format_exc()}")
        return False, None, []

def download_and_analyze_parquet(client, file_path: str):
    """Download parquet file and analyze with PyArrow"""
    if not PYARROW_AVAILABLE:
        print("[MinIO Test] Cannot analyze parquet file without PyArrow")
        return False, None, set()
    
    temp_file = None
    try:
        print(f"[MinIO Test] Attempting to download parquet file: {file_path}")
        
        # Create temporary file
        temp_fd, temp_file = tempfile.mkstemp(suffix='.parquet')
        os.close(temp_fd)  # Close file descriptor
        
        # Download file from MinIO
        client.fget_object(Config.MINIO_BUCKET, file_path, temp_file)
        print(f"[MinIO Test] ✅ File download completed: {temp_file}")
        
        # Read file with PyArrow
        table = pq.read_table(temp_file)
        print(f"[MinIO Test] 📊 Data analysis:")
        print(f"  - Rows: {table.num_rows:,}")
        print(f"  - Columns: {table.num_columns}")
        print(f"  - Column names: {table.column_names}")
        
        # Check objId column
        if 'objId' not in table.column_names:
            print(f"[MinIO Test] ❌ objId column not found")
            return False, table, set()
        
        # Extract and analyze objId data
        objid_column = table.column('objId')
        unique_objids = set()
        
        # Convert PyArrow Array to Python list
        objid_values = objid_column.to_pylist()
        unique_objids = set(objid_values)
        
        print(f"  - Unique objId count: {len(unique_objids)}")
        print(f"  - objId samples: {sorted(list(unique_objids))[:10]}")
        
        # Timestamp information
        if '@timestamp' in table.column_names:
            timestamp_column = table.column('@timestamp')
            timestamps = timestamp_column.to_pylist()
            if timestamps:
                print(f"  - Time range: {min(timestamps)} ~ {max(timestamps)}")
        
        # Check mapped objIds
        rack_mapping = Config.get_rack_to_sensor_map()
        mapped_objids = set(rack_mapping.values())
        found_objids = set(unique_objids) & mapped_objids
        
        print(f"  - Configured mapping objIds: {sorted(mapped_objids)}")
        print(f"  - Found mapping objIds in data: {sorted(found_objids)}")
        
        if len(mapped_objids) > 0:
            match_rate = len(found_objids) / len(mapped_objids) * 100
            print(f"  - Match rate: {len(found_objids)}/{len(mapped_objids)} ({match_rate:.1f}%)")
        else:
            print(f"  - No mapping configuration found")
        
        return True, table, found_objids
        
    except Exception as e:
        print(f"[MinIO Test] ❌ File processing error: {e}")
        import traceback
        print(f"[MinIO Test] Detailed error: {traceback.format_exc()}")
        return False, None, set()
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                print(f"[MinIO Test] Temporary file deleted: {temp_file}")
            except:
                pass

def analyze_sensor_data(table, found_objids: Set):
    """Detailed sensor data analysis"""
    try:
        print(f"\n[Data Analysis] Detailed sensor data analysis")
        
        if not found_objids:
            print("[Data Analysis] No mapped sensor data found")
            return False
        
        rack_mapping = Config.get_rack_to_sensor_map()
        sensor_mapping = Config.get_sensor_to_rack_map()
        
        # Analyze data for each sensor
        for objid in sorted(list(found_objids))[:5]:  # First 5 only
            rack_path = sensor_mapping.get(objid, "Unknown")
            print(f"\n  📊 objId {objid} ({rack_path}):")
            
            # Filter data for this objId
            objid_filter = pa.compute.equal(table.column('objId'), objid)
            filtered_table = table.filter(objid_filter)
            
            print(f"    - Data rows: {filtered_table.num_rows:,}")
            
            if filtered_table.num_rows > 0:
                # Sample data from first row
                sample_data = {}
                for col_name in filtered_table.column_names:
                    col_data = filtered_table.column(col_name).to_pylist()
                    if col_data:
                        sample_data[col_name] = col_data[0]
                
                print(f"    - Timestamp: {sample_data.get('@timestamp', 'N/A')}")
                print(f"    - TEMPERATURE (Cold): {sample_data.get('TEMPERATURE', 'N/A')}")
                print(f"    - TEMPERATURE1 (Hot): {sample_data.get('TEMPERATURE1', 'N/A')}")
                print(f"    - HUMIDITY (Cold): {sample_data.get('HUMIDITY', 'N/A')}")
                print(f"    - HUMIDITY1 (Hot): {sample_data.get('HUMIDITY1', 'N/A')}")
                
                # Check temperature/humidity ranges
                if 'TEMPERATURE' in filtered_table.column_names:
                    temp_values = filtered_table.column('TEMPERATURE').to_pylist()
                    temp_values = [v for v in temp_values if v is not None]
                    if temp_values:
                        print(f"    - TEMPERATURE range: {min(temp_values):.1f} ~ {max(temp_values):.1f}°C")
                
                if 'HUMIDITY' in filtered_table.column_names:
                    hum_values = filtered_table.column('HUMIDITY').to_pylist()
                    hum_values = [v for v in hum_values if v is not None]
                    if hum_values:
                        print(f"    - HUMIDITY range: {min(hum_values):.1f} ~ {max(hum_values):.1f}%")
        
        return True
        
    except Exception as e:
        print(f"[Data Analysis] X Analysis error: {e}")
        import traceback
        print(f"[Data Analysis] Detailed error: {traceback.format_exc()}")
        return False

def test_rack_mapping_display():
    """Display rack mapping configuration"""
    try:
        print(f"\n[Rack Mapping] Configured rack mappings:")
        
        rack_mapping = Config.get_rack_to_sensor_map()
        
        if not rack_mapping:
            print("[Rack Mapping] X No rack mapping configuration found")
            return False
        
        print(f"[Rack Mapping] Total {len(rack_mapping)} rack mappings:")
        for i, (rack_path, objid) in enumerate(rack_mapping.items(), 1):
            print(f"  {i:2d}. {rack_path}")
            print(f"      -> objId: {objid}")
        
        return True
        
    except Exception as e:
        print(f"[Rack Mapping] X Error: {e}")
        return False

def run_full_test():
    """Run complete test suite"""
    print("=" * 80)
    print("MinIO Connection and Rack Mapping Test (Using PyArrow)")
    print("=" * 80)
    
    # 0. Check libraries
    if not PYARROW_AVAILABLE:
        print("X PyArrow not installed")
        return False
    
    if not MINIO_AVAILABLE:
        print("X MinIO client not installed")
        return False
    
    # 1. Check rack mapping configuration
    mapping_ok = test_rack_mapping_display()
    if not mapping_ok:
        return False
    
    # 2. MinIO connection test
    connection_result = test_minio_connection()
    if isinstance(connection_result, tuple):
        success, client, parquet_files = connection_result
        if not success:
            return False
    else:
        return False
    
    # 3. Find target file
    target_file = None
    for file_path in parquet_files:
        if Config.PARQUET_FILE in file_path:
            target_file = file_path
            break
    
    if not target_file:
        print(f"\n[Test] X Target file '{Config.PARQUET_FILE}' not found")
        print(f"[Test] Available files:")
        for file_path in parquet_files:
            print(f"  - {file_path}")
        
        # Test with first parquet file instead
        if parquet_files:
            target_file = parquet_files[0]
            print(f"[Test] Testing with first file instead: {target_file}")
        else:
            return False
    
    # 4. Download and analyze file
    download_success, table, found_objids = download_and_analyze_parquet(client, target_file)
    if not download_success:
        return False
    
    # 5. Detailed sensor data analysis
    analysis_success = analyze_sensor_data(table, found_objids)
    
    # 6. Result summary
    print("\n" + "=" * 80)
    if analysis_success and len(found_objids) > 0:
        print("O Complete test SUCCESS!")
        print(f"   - MinIO connection: O")
        print(f"   - Parquet file reading: O")
        print(f"   - Mapped sensors found: {len(found_objids)}")
        print("   - Conclusion: MinIO data can be mapped to USD racks!")
    else:
        print("X Test PARTIAL SUCCESS")
        print(f"   - MinIO connection: O")
        print(f"   - Parquet file reading: {'O' if table else 'X'}")
        print(f"   - Mapped sensors found: {len(found_objids)}")
        if len(found_objids) == 0:
            print("   - Issue: Configured objIds do not match data objIds")
    print("=" * 80)
    
    return analysis_success and len(found_objids) > 0

def test_direct_mapping():
    """Test function that can be called directly from UI"""
    try:
        return run_full_test()
    except Exception as e:
        print(f"[Test] Complete test error: {e}")
        import traceback
        print(f"[Test] Detailed error: {traceback.format_exc()}")
        return False

# Simple test function (library check only)
def test_libraries_only():
    """Test only library availability"""
    print("[Library Test] Library check:")
    print(f"  - PyArrow: {'O' if PYARROW_AVAILABLE else 'X'}")
    print(f"  - MinIO: {'O' if MINIO_AVAILABLE else 'X'}")
    
    if PYARROW_AVAILABLE and MINIO_AVAILABLE:
        print("O All required libraries available")
        return True
    else:
        print("X Required libraries missing")
        return False

if __name__ == "__main__":
    run_full_test()