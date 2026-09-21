"""레거시 .pbd(기존 프로토타입) → 우리 Document 변환.

기존 포맷: { boxes:[{id,x,y,w,h,text,shape,z}], arrows:[{id,from,to,style,z}],
            tags:[{id,boxId,label,dx,dy,z}], nextId }
연결선/태그는 후속 단계에서 완성되므로 도형 위주로 우선 변환한다.
"""
from __future__ import annotations

import json
from typing import Any

from ..core import model as M

_SHAPE_MAP = {
    "rect": M.SHAPE_RECT,
    "rounded": M.SHAPE_ROUNDED,
    "cylinder": M.SHAPE_CYLINDER,
    "cloud": M.SHAPE_CLOUD,
    "user": M.SHAPE_USER,
}


def import_pbd(text: str) -> M.Document:
    raw: dict[str, Any] = json.loads(text)
    doc = M.Document()
    idmap: dict[Any, str] = {}

    for b in raw.get("boxes", []):
        eid = doc.new_id()
        idmap[b.get("id")] = eid
        doc.add(M.Element(
            id=eid, type=M.TYPE_SHAPE,
            shape=_SHAPE_MAP.get(b.get("shape", "rect"), M.SHAPE_RECT),
            x=float(b.get("x", 0)), y=float(b.get("y", 0)),
            w=float(b.get("w", 120)), h=float(b.get("h", 60)),
            text=str(b.get("text", "")), z=int(b.get("z", 0)),
        ))

    for a in raw.get("arrows", []):
        f = idmap.get(a.get("from"))
        t = idmap.get(a.get("to"))
        if not (f and t):
            continue
        doc.add(M.Element(
            id=doc.new_id(), type=M.TYPE_CONNECTOR,
            from_id=f, to_id=t,
            route=(M.ROUTE_ORTHO if a.get("style") == "ortho" else M.ROUTE_STRAIGHT),
            z=int(a.get("z", 0)),
            style=M.Style(arrow="end"),
        ))

    for t in raw.get("tags", []):
        tgt = idmap.get(t.get("boxId"))
        if not tgt:
            continue
        doc.add(M.Element(
            id=doc.new_id(), type=M.TYPE_TAG, target=tgt,
            label=str(t.get("label", "")),
            dx=float(t.get("dx", 0)), dy=float(t.get("dy", 0)),
            z=int(t.get("z", 0)),
        ))

    return doc
