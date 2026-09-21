"""도형 종류별 QPainterPath 생성 — 흑백 특허 도면 스타일.

모든 경로는 로컬 좌표 (0,0)-(w,h) 안에 그린다. 채움/선은 item 이 담당.
구름·사용자 아이콘은 특허 관례대로 선만 그린다.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QPainterPath

from ..core import model as M


def path_for(shape: str, w: float, h: float) -> QPainterPath:
    builders = {
        M.SHAPE_RECT: _rect,
        M.SHAPE_ROUNDED: _rounded,
        M.SHAPE_CYLINDER: _cylinder,
        M.SHAPE_CLOUD: _cloud,
        M.SHAPE_USER: _user,
    }
    fn = builders.get(shape, _rect)
    try:
        return fn(w, h)
    except Exception:  # noqa: BLE001 — 도형 하나의 오류가 앱을 마비시키지 않게 폴백
        return _rect(w, h)


def _rect(w: float, h: float) -> QPainterPath:
    p = QPainterPath()
    p.addRect(0, 0, w, h)
    return p


def _rounded(w: float, h: float) -> QPainterPath:
    p = QPainterPath()
    r = min(w, h) * 0.18
    p.addRoundedRect(0, 0, w, h, r, r)
    return p


def _cylinder(w: float, h: float) -> QPainterPath:
    """DB 원기둥: 위 타원 + 옆면."""
    p = QPainterPath()
    ry = min(h * 0.16, w * 0.5)
    top = QRectF(0, 0, w, 2 * ry)
    bot = QRectF(0, h - 2 * ry, w, 2 * ry)
    # 옆면 윤곽
    p.moveTo(0, ry)
    p.lineTo(0, h - ry)
    p.arcTo(bot, 180, 180)          # 아래 반타원(앞쪽)
    p.lineTo(w, ry)
    p.arcTo(top, 0, 360)            # 위 타원(전체)
    return p


def _cloud(w: float, h: float) -> QPainterPath:
    """네트워크/외부 서버 구름 — 여러 원호의 물결 윤곽."""
    p = QPainterPath()
    p.setFillRule(Qt.WindingFill)  # 겹친 원들의 합집합 외곽만 남기기 위함
    # 상대 좌표(0..1)로 원 배치 후 스케일
    bumps = [
        (0.50, 0.55, 0.30),   # 중앙을 채워 원들 사이 틈 제거
        (0.18, 0.62, 0.18),
        (0.34, 0.40, 0.20),
        (0.55, 0.34, 0.22),
        (0.76, 0.44, 0.19),
        (0.86, 0.66, 0.16),
        (0.66, 0.74, 0.20),
        (0.40, 0.76, 0.19),
    ]
    for cx, cy, r in bumps:
        p.addEllipse(QRectF((cx - r) * w, (cy - r) * h, 2 * r * w, 2 * r * h))
    return p.simplified()


def _user(w: float, h: float) -> QPainterPath:
    """이용자 아이콘: 머리(원) + 어깨(반원 몸통)."""
    p = QPainterPath()
    head_r = min(w, h) * 0.22
    cx = w / 2
    head_cy = head_r + h * 0.06
    p.addEllipse(QPointF(cx, head_cy), head_r, head_r)
    # 몸통(어깨): 아래쪽 반원/사다리꼴 곡선
    body_top = head_cy + head_r * 1.15
    bw = w * 0.62
    body = QPainterPath()
    body.moveTo(cx - bw / 2, h * 0.95)
    body.cubicTo(cx - bw / 2, body_top,
                 cx + bw / 2, body_top,
                 cx + bw / 2, h * 0.95)
    p.addPath(body)
    return p
