"""데이터 모델 — UI(PySide6)에 의존하지 않는 순수 파이썬.

설계 원칙(통합 대비):
- 도형/연결선/도면부호를 `Element` 하나로 통일하고 `type` 으로 구분한다.
  나중에 3D 투영선(type="edge")을 같은 문서/씬에 그대로 얹기 위함.
- 좌표 단위와 레이어를 문서 수준에서 관리한다(가시선/은선/중심선/부호 분리).
- style 은 토큰(선굵기/선종/채움)으로만 표현한다. 특허 도면은 흑백 고정이라 색상은 없다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

SCHEMA = "pds-doc/1"

# 선종: 실선(가시선) / 점선(은선) / 일점쇄선(중심선)
DASH_SOLID = "solid"
DASH_DASHED = "dashed"
DASH_DASHDOT = "dashdot"
DASH_CYCLE = (DASH_SOLID, DASH_DASHED, DASH_DASHDOT)

# 채움: 없음 / 흰색(뒤 선 가리기). 해칭·색상 없음(블록도).
FILL_NONE = "none"
FILL_WHITE = "white"

# 도형 종류
SHAPE_RECT = "rect"
SHAPE_ROUNDED = "rounded"
SHAPE_CYLINDER = "cylinder"   # DB
SHAPE_CLOUD = "cloud"         # 네트워크/외부 서버
SHAPE_USER = "user"           # 이용자 아이콘
SHAPES = (SHAPE_RECT, SHAPE_ROUNDED, SHAPE_CYLINDER, SHAPE_CLOUD, SHAPE_USER)

# 요소 타입
TYPE_SHAPE = "shape"
TYPE_CONNECTOR = "connector"
TYPE_TAG = "tag"

# 연결선 경로
ROUTE_STRAIGHT = "straight"
ROUTE_ORTHO = "ortho"

# 지시선 종류(도면부호)
LEADER_WAVE = "wave"     # 물결(~) — 특허 관례
LEADER_STRAIGHT = "line"


class TextAlign(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass
class Style:
    line: float = 1.0            # 선 굵기(pt 상당)
    dash: str = DASH_SOLID       # 선종
    fill: str = FILL_NONE        # 채움
    arrow: str = "none"          # 연결선 화살촉: none|end|both

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict[str, Any]]) -> "Style":
        d = d or {}
        return cls(
            line=float(d.get("line", 1.0)),
            dash=str(d.get("dash", DASH_SOLID)),
            fill=str(d.get("fill", FILL_NONE)),
            arrow=str(d.get("arrow", "none")),
        )


@dataclass
class Element:
    """도형·연결선·도면부호를 통일한 요소.

    geometry(x,y,w,h,rotation)는 도형/태그가 쓰고,
    연결선은 from_id/to_id 로 두 도형을 참조한다.
    """
    id: str
    type: str = TYPE_SHAPE
    shape: str = SHAPE_RECT          # type==shape 일 때만 유효
    layer: str = "L1"
    z: int = 0

    # 배치(도형/태그 공통; 태그는 dx,dy 로 target 기준 상대배치)
    x: float = 0.0
    y: float = 0.0
    w: float = 120.0
    h: float = 60.0
    rotation: float = 0.0            # 도(°), PPT식 회전

    # 텍스트(도형)
    text: str = ""
    text_align: str = TextAlign.CENTER.value

    # 연결선(type==connector)
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    route: str = ROUTE_ORTHO
    waypoint_ratio: float = 0.5      # 직각 연결선 꺾임 위치(비율)

    # 도면부호(type==tag)
    target: Optional[str] = None     # 가리키는 요소 id
    label: str = ""
    dx: float = 0.0
    dy: float = 0.0
    leader: str = LEADER_WAVE

    style: Style = field(default_factory=Style)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["style"] = self.style.to_dict()
        # None/기본값이라도 명시 저장(가독성·마이그레이션 안전). 필요시 후에 축약.
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Element":
        return cls(
            id=str(d["id"]),
            type=str(d.get("type", TYPE_SHAPE)),
            shape=str(d.get("shape", SHAPE_RECT)),
            layer=str(d.get("layer", "L1")),
            z=int(d.get("z", 0)),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            w=float(d.get("w", 120.0)),
            h=float(d.get("h", 60.0)),
            rotation=float(d.get("rotation", 0.0)),
            text=str(d.get("text", "")),
            text_align=str(d.get("text_align", TextAlign.CENTER.value)),
            from_id=_opt_str(d.get("from_id")),
            to_id=_opt_str(d.get("to_id")),
            route=str(d.get("route", ROUTE_ORTHO)),
            waypoint_ratio=float(d.get("waypoint_ratio", 0.5)),
            target=_opt_str(d.get("target")),
            label=str(d.get("label", "")),
            dx=float(d.get("dx", 0.0)),
            dy=float(d.get("dy", 0.0)),
            leader=str(d.get("leader", LEADER_WAVE)),
            style=Style.from_dict(d.get("style")),
        )


@dataclass
class Layer:
    id: str = "L1"
    name: str = "블록도"
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Layer":
        return cls(
            id=str(d.get("id", "L1")),
            name=str(d.get("name", "블록도")),
            visible=bool(d.get("visible", True)),
        )


@dataclass
class Page:
    w: float = 297.0
    h: float = 210.0
    orient: str = "landscape"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict[str, Any]]) -> "Page":
        d = d or {}
        return cls(
            w=float(d.get("w", 297.0)),
            h=float(d.get("h", 210.0)),
            orient=str(d.get("orient", "landscape")),
        )


@dataclass
class Document:
    schema: str = SCHEMA
    unit: str = "mm"
    page: Page = field(default_factory=Page)
    layers: list[Layer] = field(default_factory=lambda: [Layer()])
    elements: list[Element] = field(default_factory=list)
    _next_id: int = 1

    # --- id 발급 ------------------------------------------------------------
    def new_id(self) -> str:
        eid = f"e{self._next_id}"
        self._next_id += 1
        return eid

    # --- 요소 접근 ----------------------------------------------------------
    def get(self, eid: str) -> Optional[Element]:
        for el in self.elements:
            if el.id == eid:
                return el
        return None

    def add(self, el: Element) -> Element:
        self.elements.append(el)
        return el

    def remove(self, eid: str) -> None:
        self.elements = [e for e in self.elements if e.id != eid]
        # 삭제된 요소를 참조하던 연결선/태그도 정리
        self.elements = [
            e for e in self.elements
            if not (e.type == TYPE_CONNECTOR and (e.from_id == eid or e.to_id == eid))
            and not (e.type == TYPE_TAG and e.target == eid)
        ]

    def max_z(self) -> int:
        return max((e.z for e in self.elements), default=0)

    # --- 직렬화 -------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "unit": self.unit,
            "page": self.page.to_dict(),
            "layers": [l.to_dict() for l in self.layers],
            "elements": [e.to_dict() for e in self.elements],
            "nextId": self._next_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Document":
        doc = cls(
            schema=str(d.get("schema", SCHEMA)),
            unit=str(d.get("unit", "mm")),
            page=Page.from_dict(d.get("page")),
            layers=[Layer.from_dict(x) for x in d.get("layers", [])] or [Layer()],
            elements=[Element.from_dict(x) for x in d.get("elements", [])],
            _next_id=int(d.get("nextId", 1)),
        )
        # nextId 가 누락/오염돼도 충돌하지 않도록 보정
        doc._next_id = max(doc._next_id, _highest_numeric_id(doc.elements) + 1)
        return doc

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "Document":
        return cls.from_dict(json.loads(text))


def _opt_str(v: Any) -> Optional[str]:
    return None if v is None else str(v)


def _highest_numeric_id(elements: list[Element]) -> int:
    hi = 0
    for e in elements:
        if e.id.startswith("e") and e.id[1:].isdigit():
            hi = max(hi, int(e.id[1:]))
    return hi
