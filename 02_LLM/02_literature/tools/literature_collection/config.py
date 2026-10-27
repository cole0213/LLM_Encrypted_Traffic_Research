"""
config.py — collection.yaml 로더.

목적: SSOT 설정(config/collection.yaml)을 읽어 dict로 반환하고,
      정규화된 config_hash(재현성용)를 계산한다.
입력: yaml 경로.
출력: (config dict, config_hash).
작성일: 2026-08-22
"""

import json
import hashlib
from pathlib import Path

import yaml


def load_config(path: str | Path) -> tuple[dict, str]:
    """yaml 설정을 로드하고 config_hash를 함께 반환한다."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 정규화 직렬화 후 해시 — 같은 설정이면 같은 해시.
    norm = json.dumps(cfg, sort_keys=True, ensure_ascii=False)
    config_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return cfg, config_hash


def project_root(cfg: dict) -> Path:
    """설정의 project.root를 Path로 반환한다."""
    return Path(cfg["project"]["root"])
