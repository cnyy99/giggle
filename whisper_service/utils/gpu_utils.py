import subprocess
import json
from typing import Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

def get_gpu_info() -> Dict[str, Any]:
    """获取GPU信息"""
    try:
        # 使用nvidia-smi获取GPU信息
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, check=True)
        
        lines = result.stdout.strip().split('\n')
        gpus = []
        
        for line in lines:
            parts = [part.strip() for part in line.split(',')]
            if len(parts) >= 6:
                gpu_info = {
                    'name': parts[0],
                    'memory_total': int(parts[1]),
                    'memory_used': int(parts[2]),
                    'memory_free': int(parts[3]),
                    'utilization': int(parts[4]),
                    'temperature': int(parts[5])
                }
                gpus.append(gpu_info)
        
        return {
            'available': len(gpus) > 0,
            'count': len(gpus),
            'gpus': gpus
        }
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return {
            'available': False,
            'count': 0,
            'gpus': []
        }

def get_gpu_memory_usage() -> Dict[str, int]:
    """获取GPU内存使用情况"""
    try:
        gpu_info = get_gpu_info()
        if gpu_info['available'] and gpu_info['gpus']:
            # 返回第一个GPU的内存信息
            gpu = gpu_info['gpus'][0]
            return {
                'total': gpu['memory_total'],
                'used': gpu['memory_used'],
                'free': gpu['memory_free'],
                'percent': round((gpu['memory_used'] / gpu['memory_total']) * 100, 2)
            }
        else:
            return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
            
    except Exception as e:
        logger.error(f"Failed to get GPU memory usage: {e}")
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}

def check_gpu_availability() -> bool:
    """检查GPU是否可用"""
    gpu_info = get_gpu_info()
    return gpu_info['available']