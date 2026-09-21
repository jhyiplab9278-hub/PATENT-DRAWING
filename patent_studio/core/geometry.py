"""회전을 고려한 리사이즈 기하 — UI 비의존 순수 함수.

도형은 (top-left P=(x,y), w, h, angle°)로 표현하고 **중심을 축으로 회전**한다
(Qt QGraphicsItem 의 transformOrigin=center 와 일치). 핸들을 끌 때 반대편 코너를
화면상 고정한 채 크기를 바꾸는 PPT식 동작을 회전 해제 좌표계에서 계산한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_SIZE = 8.0  # 최소 폭/높이

# 코너 오프셋(중심 기준, 단위벡터). +x=오른쪽, +y=아래
_CORNER_SIGN = {
    "nw": (-1, -1),
    "ne": (+1, -1),
    "se": (+1, +1),
    "sw": (-1, +1),
}

# 핸들 -> (앵커 코너, freex, freey). 성장방향 dir 은 앵커 오프셋의 반대.
_HANDLES = {
    "se": ("nw", True, True),
    "ne": ("sw", True, True),
    "nw": ("se", True, True),
    "sw": ("ne", True, True),
    "e":  ("nw", True, False),
    "w":  ("ne", True, False),
    "s":  ("nw", False, True),
    "n":  ("sw", False, True),
}

HANDLE_KEYS = ("nw", "n", "ne", "e", "se", "s", "sw", "w")


@dataclass(frozen=True)
class Pt:
    x: float
    y: float

    def __add__(self, o: "Pt") -> "Pt":
        return Pt(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Pt") -> "Pt":
        return Pt(self.x - o.x, self.y - o.y)


def rot(v: Pt, deg: float) -> Pt:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return Pt(v.x * c - v.y * s, v.x * s + v.y * c)


def center_of(x: float, y: float, w: float, h: float) -> Pt:
    return Pt(x + w / 2, y + h / 2)


def corner_scene(name: str, x: float, y: float, w: float, h: float, angle: float) -> Pt:
    """중심 기준 회전을 반영한 코너의 씬 좌표."""
    c = center_of(x, y, w, h)
    sx, sy = _CORNER_SIGN[name]
    off = Pt(sx * w / 2, sy * h / 2)
    return c + rot(off, angle)


def resize(
    handle: str,
    x: float, y: float, w: float, h: float, angle: float,
    mouse: Pt,
    *, keep_ratio: bool = False,
) -> tuple[float, float, float, float]:
    """핸들 드래그 결과로 새 (x, y, w, h) 를 반환. angle 유지, 앵커 코너는 화면상 고정."""
    anchor_name, freex, freey = _HANDLES[handle]
    ax, ay = _CORNER_SIGN[anchor_name]
    dirx, diry = -ax, -ay  # 성장 방향

    As = corner_scene(anchor_name, x, y, w, h, angle)
    u = rot(mouse - As, -angle)  # 앵커 기준 로컬 벡터

    new_w = max(MIN_SIZE, dirx * u.x) if freex else w
    new_h = max(MIN_SIZE, diry * u.y) if freey else h

    if keep_ratio and freex and freey and w > 0 and h > 0:
        ratio = w / h
        if new_w / new_h > ratio:
            new_w = new_h * ratio
        else:
            new_h = new_w / ratio

    # 새 중심: 앵커는 As 로 고정. 앵커의 새 중심대비 오프셋 = (ax*new_w/2, ay*new_h/2)
    c_new = As - rot(Pt(ax * new_w / 2, ay * new_h / 2), angle)
    return c_new.x - new_w / 2, c_new.y - new_h / 2, new_w, new_h


def rotation_from_mouse(cx: float, cy: float, mouse: Pt, *, snap: bool = False) -> float:
    """중심(cx,cy) 기준 마우스 각도(°). 위쪽(12시)이 0°."""
    ang = math.degrees(math.atan2(mouse.x - cx, -(mouse.y - cy)))
    if snap:
        ang = round(ang / 15.0) * 15.0
    return ang % 360.0


def snap_to_grid(v: float, step: float) -> float:
    return round(v / step) * step
