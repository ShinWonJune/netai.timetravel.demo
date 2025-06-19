import time
import psutil
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
import json
import csv
from datetime import datetime, timedelta

@dataclass
class PerformanceMetric:
    """성능 메트릭 데이터 클래스"""
    timestamp: float
    operation: str
    duration: float
    memory_usage: float
    cpu_usage: float
    rack_count: int
    data_points: int
    frame_rate: Optional[float] = None
    errors: int = 0
    
class PerformanceMonitor:
    """실시간 성능 모니터링 시스템"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics_queue = deque(maxlen=window_size)
        self.operation_stats = defaultdict(list)
        
        # 실시간 모니터링
        self.current_fps = 0.0
        self.frame_times = deque(maxlen=60)  # 1초간의 프레임 시간
        self.last_frame_time = time.time()
        
        # 메모리 및 CPU 모니터링
        self.process = psutil.Process()
        self.baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # 경고 임계값
        self.thresholds = {
            'frame_time_ms': 16.67,  # 60 FPS 기준
            'memory_increase_mb': 100,
            'cpu_usage_percent': 80,
            'operation_time_ms': 50
        }
        
        # 로깅
        self.log_file = f"performance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_log_file()
        
    def _init_log_file(self):
        """로그 파일 초기화"""
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'operation', 'duration_ms', 'memory_mb', 
                'cpu_percent', 'rack_count', 'data_points', 'fps', 'errors'
            ])
    
    def start_operation(self, operation_name: str) -> 'OperationTimer':
        """작업 시작 (컨텍스트 매니저 반환)"""
        return OperationTimer(self, operation_name)
    
    def record_metric(self, metric: PerformanceMetric):
        """메트릭 기록"""
        self.metrics_queue.append(metric)
        self.operation_stats[metric.operation].append(metric)
        
        # CSV 로그 기록
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                metric.timestamp, metric.operation, metric.duration * 1000,
                metric.memory_usage, metric.cpu_usage, metric.rack_count,
                metric.data_points, metric.frame_rate, metric.errors
            ])
        
        # 경고 체크
        self._check_warnings(metric)
    
    def update_frame_rate(self):
        """프레임레이트 업데이트"""
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        self.frame_times.append(frame_time)
        self.last_frame_time = current_time
        
        # FPS 계산 (최근 60프레임 평균)
        if len(self.frame_times) > 1:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            self.current_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
    
    def get_current_system_metrics(self) -> Dict:
        """현재 시스템 메트릭 반환"""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = self.process.cpu_percent()
            
            return {
                'memory_mb': memory_mb,
                'memory_increase_mb': memory_mb - self.baseline_memory,
                'cpu_percent': cpu_percent,
                'fps': self.current_fps,
                'frame_time_ms': (self.frame_times[-1] * 1000) if self.frame_times else 0
            }
        except Exception as e:
            print(f"[Performance] 시스템 메트릭 오류: {e}")
            return {'memory_mb': 0, 'memory_increase_mb': 0, 'cpu_percent': 0, 'fps': 0, 'frame_time_ms': 0}
    
    def _check_warnings(self, metric: PerformanceMetric):
        """성능 경고 체크"""
        warnings = []
        
        if metric.duration * 1000 > self.thresholds['operation_time_ms']:
            warnings.append(f"작업 시간 초과: {metric.operation} ({metric.duration*1000:.1f}ms)")
        
        if metric.memory_usage - self.baseline_memory > self.thresholds['memory_increase_mb']:
            warnings.append(f"메모리 사용량 증가: {metric.memory_usage - self.baseline_memory:.1f}MB")
        
        if metric.cpu_usage > self.thresholds['cpu_usage_percent']:
            warnings.append(f"CPU 사용률 높음: {metric.cpu_usage:.1f}%")
        
        if metric.frame_rate and metric.frame_rate < 60:
            warnings.append(f"FPS 저하: {metric.frame_rate:.1f}")
        
        for warning in warnings:
            print(f"[Performance Warning] {warning}")
    
    def get_statistics(self, operation: Optional[str] = None) -> Dict:
        """통계 정보 반환"""
        if operation:
            metrics = self.operation_stats.get(operation, [])
        else:
            metrics = list(self.metrics_queue)
        
        if not metrics:
            return {}
        
        durations = [m.duration * 1000 for m in metrics]  # ms 변환
        memory_usage = [m.memory_usage for m in metrics]
        cpu_usage = [m.cpu_usage for m in metrics]
        
        return {
            'count': len(metrics),
            'avg_duration_ms': sum(durations) / len(durations),
            'max_duration_ms': max(durations),
            'min_duration_ms': min(durations),
            'p95_duration_ms': sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations),
            'avg_memory_mb': sum(memory_usage) / len(memory_usage),
            'max_memory_mb': max(memory_usage),
            'avg_cpu_percent': sum(cpu_usage) / len(cpu_usage),
            'max_cpu_percent': max(cpu_usage),
        }
    
    def print_report(self):
        """성능 리포트 출력"""
        print("\n" + "="*60)
        print("성능 모니터링 리포트")
        print("="*60)
        
        # 전체 통계
        overall_stats = self.get_statistics()
        if overall_stats:
            print(f"전체 작업 수: {overall_stats['count']}")
            print(f"평균 작업 시간: {overall_stats['avg_duration_ms']:.2f}ms")
            print(f"최대 작업 시간: {overall_stats['max_duration_ms']:.2f}ms")
            print(f"95% 작업 시간: {overall_stats['p95_duration_ms']:.2f}ms")
            print(f"평균 메모리 사용량: {overall_stats['avg_memory_mb']:.1f}MB")
            print(f"평균 CPU 사용률: {overall_stats['avg_cpu_percent']:.1f}%")
        
        print("\n작업별 통계:")
        print("-" * 40)
        
        # 작업별 통계
        for operation in self.operation_stats.keys():
            stats = self.get_statistics(operation)
            print(f"{operation}:")
            print(f"  횟수: {stats['count']}")
            print(f"  평균: {stats['avg_duration_ms']:.2f}ms")
            print(f"  최대: {stats['max_duration_ms']:.2f}ms")
            print(f"  P95: {stats['p95_duration_ms']:.2f}ms")
        
        # 현재 시스템 상태
        current = self.get_current_system_metrics()
        print(f"\n현재 시스템 상태:")
        print(f"  FPS: {current['fps']:.1f}")
        print(f"  프레임 시간: {current['frame_time_ms']:.1f}ms")
        print(f"  메모리: {current['memory_mb']:.1f}MB (+{current['memory_increase_mb']:.1f}MB)")
        print(f"  CPU: {current['cpu_percent']:.1f}%")
        
        print("="*60)

class OperationTimer:
    """작업 시간 측정을 위한 컨텍스트 매니저"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
        self.rack_count = 0
        self.data_points = 0
        self.errors = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            system_metrics = self.monitor.get_current_system_metrics()
            
            # 에러 카운트
            if exc_type is not None:
                self.errors += 1
            
            metric = PerformanceMetric(
                timestamp=time.time(),
                operation=self.operation_name,
                duration=duration,
                memory_usage=system_metrics['memory_mb'],
                cpu_usage=system_metrics['cpu_percent'],
                rack_count=self.rack_count,
                data_points=self.data_points,
                frame_rate=system_metrics['fps'],
                errors=self.errors
            )
            
            self.monitor.record_metric(metric)
    
    def set_data_info(self, rack_count: int, data_points: int):
        """처리된 데이터 정보 설정"""
        self.rack_count = rack_count
        self.data_points = data_points

# 글로벌 모니터 인스턴스
performance_monitor = PerformanceMonitor()

# 데코레이터 함수
def monitor_performance(operation_name: str):
    """함수 성능 모니터링 데코레이터"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with performance_monitor.start_operation(operation_name) as timer:
                try:
                    result = func(*args, **kwargs)
                    
                    # 결과에서 데이터 정보 추출 (선택적)
                    if isinstance(result, dict) and 'rack_count' in result:
                        timer.set_data_info(
                            result.get('rack_count', 0),
                            result.get('data_points', 0)
                        )
                    
                    return result
                except Exception as e:
                    timer.errors += 1
                    raise
        return wrapper
    return decorator

# 사용 예시
if __name__ == "__main__":
    # 테스트 코드
    monitor = PerformanceMonitor()
    
    # 시뮬레이션된 작업
    for i in range(100):
        with monitor.start_operation("data_update") as timer:
            time.sleep(0.01)  # 10ms 작업 시뮬레이션
            timer.set_data_info(rack_count=24, data_points=100)
        
        monitor.update_frame_rate()
    
    monitor.print_report()