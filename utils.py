"""
유틸리티 함수: 재현성, 로깅, 센서 범위(온톨로지) 관리
"""
import os
import random
import numpy as np
import torch

import config


def set_seed(seed: int = config.RANDOM_SEED):
    """재현성을 위한 전역 시드 설정"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def count_parameters(model) -> dict:
    """모델 파라미터 수 집계"""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen = total - trainable
    return {"total": total, "trainable": trainable, "frozen": frozen}


def get_sensor_ranges_by_cycle_state(cycle_state: int) -> dict:
    """
    Process Ontology 기반 센서 허용 범위 반환 (Knowledge Infusion).

    NSF-MAP 논문에서는 Neo4j 기반 동적 온톨로지를 사용하지만,
    여기서는 도메인 전문가 지식을 딕셔너리로 간소화한다.
    실제 사용 시 FF Dataset의 센서 통계에서 추출해야 한다.

    Returns:
        dict[sensor_idx, (min, max)] - 센서별 정상 범위
    """
    # 예시 (실제 데이터 분석 후 값을 채워야 함)
    ranges = {
        4: {  # cycle state 4
            0: (5500, 8500),   # 포텐셔미터 (Robot 1)
            1: (1400, 1550),   # 로드셀
        },
        9: {  # cycle state 9
            0: (3000, 6000),
            1: (1350, 1500),
        },
    }
    return ranges.get(cycle_state, {})


def ensure_dirs():
    """필요한 디렉토리를 생성한다."""
    for d in [config.DATA_DIR, config.PROCESSED_DIR, config.IMAGE_DIR,
              config.CHECKPOINT_DIR, config.RESULT_DIR]:
        os.makedirs(d, exist_ok=True)
