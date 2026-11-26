"""Versioned, kernel-neutral SurfWing shape-document validation and persistence.

The JSON Schema is the structural contract. This module adds semantic checks
using only the Python standard library. It is a provisional Python adapter; the
persisted schema remains independent of the Python/C++ source-of-truth decision.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
DOCUMENT_TYPE = "surfwing.shape"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / f"shape-document-{SCHEMA_VERSION}.schema.json"
_NAMESPACE = uuid.UUID("bc55f77d-7a4a-4f61-a0c7-4bcece7e7021")


class ShapeDocumentError(ValueError):
    """Shape document rejected with actionable semantic validation messages."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Shape document invalid:\n- " + "\n- ".join(errors))


def load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def convert_length(value: float, unit: str) -> float:
    """Convert one imported length to canonical mm. Unknown units fail closed."""
    if not math.isfinite(value):
        raise ValueError("Length must be finite")
    factors = {"mm": 1.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
    if unit not in factors:
        raise ValueError(f"Unsupported length unit: {unit}")
    return value * factors[unit]


def _finite_tree(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path}: non-finite number")
    elif isinstance(value, dict):
        for key, child in value.items():
            _finite_tree(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _finite_tree(child, f"{path}[{index}]", errors)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _norm(v: list[float]) -> float:
    return math.sqrt(_dot(v, v))


def _det_axes(axes: list[list[float]]) -> float:
    return _dot(axes[0], _cross(axes[1], axes[2]))


def _orient(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on_segment(a: list[float], b: list[float], p: list[float], eps: float = 1e-10) -> bool:
    return (min(a[0], b[0])-eps <= p[0] <= max(a[0], b[0])+eps
            and min(a[1], b[1])-eps <= p[1] <= max(a[1], b[1])+eps
            and abs(_orient(a, b, p)) <= eps)


def _segments_intersect(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    eps = 1e-10
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)):
        return True
    return _on_segment(a, b, c) or _on_segment(a, b, d) or _on_segment(c, d, a) or _on_segment(c, d, b)


def _polygon_errors(points: list[list[float]], curve_id: str) -> list[str]:
    errors: list[str] = []
    n = len(points)
    area2 = sum(points[i][0]*points[(i+1)%n][1] - points[(i+1)%n][0]*points[i][1] for i in range(n))
    if abs(area2) <= 1e-10:
        errors.append(f"curve {curve_id}: closed polygon has zero area")
    for i in range(n):
        a, b = points[i], points[(i+1)%n]
        if _norm([b[0]-a[0], b[1]-a[1]]) <= 1e-10:
            errors.append(f"curve {curve_id}: zero-length polygon edge at anchor {i}")
        for j in range(i+1, n):
            # Skip same edge and adjacent edges, including wrap-around.
            if j == i or j == (i+1)%n or i == (j+1)%n:
                continue
            c, d = points[j], points[(j+1)%n]
            if _segments_intersect(a, b, c, d):
                errors.append(f"curve {curve_id}: self-intersection between polygon edges {i} and {j}")
                return errors
    return errors


def _profile_eval(profile: dict[str, Any], u: float) -> float:
    kind = profile.get("kind", "flat")
    depth = float(profile.get("depth_mm", 0.0))
    a = abs(u)
    if kind == "flat":
        return 0.0
    if kind == "v":
        d = profile.get("left_depth_mm", depth) if u < 0 else profile.get("right_depth_mm", depth)
        return float(d) * a
    if kind == "single_concave":
        w = float(profile.get("half_width_u", 0.6))
        t = min(1.0, a/w)
        return -depth * (1-t*t)**2
    if kind == "double_concave":
        c, w = float(profile.get("center_u", 0.45)), float(profile.get("half_width_u", 0.6))
        d = profile.get("left_depth_mm", depth) if u < 0 else profile.get("right_depth_mm", depth)
        t = min(1.0, abs(a-c)/w)
        return -float(d) * (1-t*t)**2
    if kind == "dome":
        return depth * (1-u*u)
    if kind == "standing_area":
        edge, blend = float(profile.get("standing_half_width_u", 0.35)), float(profile.get("blend_width_u", 0.15))
        t = max(0.0, min(1.0, (a-edge)/blend))
        return depth * t*t*(3-2*t)
    raise ValueError(f"unsupported analytic profile kind {kind!r}")


def validate_document(document: dict[str, Any], *, use_json_schema: bool = True) -> list[str]:
    """Return validation errors; structural JSON Schema is applied when available."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["root must be an object"]
    _finite_tree(document, "$", errors)

    if use_json_schema:
        try:
            import jsonschema  # optional dependency
            jsonschema.Draft202012Validator(load_schema()).validate(document)
        except ImportError:
            pass
        except Exception as exc:
            errors.append(f"JSON Schema: {exc}")

    if document.get("document_type") != DOCUMENT_TYPE:
        errors.append("document_type must be surfwing.shape")
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}; migrate explicitly")
    if not document.get("model_id") or not document.get("name"):
        errors.append("model_id and name are required")
    if document.get("units") != {"length": "mm", "angle": "rad"}:
        errors.append("saved units must be canonical mm/rad")
    coord = document.get("coordinate_system", {})
    expected_coord = {"handedness":"right", "x":"nose_to_tail_positive_aft",
                      "y":"centerline_to_starboard_positive", "z":"bottom_to_deck_positive_up"}
    if coord != expected_coord:
        errors.append("coordinate_system must use the canonical right-handed X/Y/Z convention")

    kind = document.get("product_kind")
    board = document.get("board")
    foil = document.get("foil_assembly")
    if kind in {"surfboard", "wingfoil_board"} and not isinstance(board, dict):
        errors.append(f"{kind} requires a board object")
    if kind == "surfboard" and foil is not None:
        errors.append("surfboard v0.1 must not contain foil_assembly")
    if kind == "foil" and (board is not None or not isinstance(foil, dict)):
        errors.append("foil product requires foil_assembly and board=null/absent")
    if kind not in {"surfboard", "wingfoil_board", "foil"}:
        errors.append("unsupported product_kind")

    entities: dict[str, dict[str, Any]] = {}
    def register(items: Any, label: str) -> None:
        if not isinstance(items, list):
            errors.append(f"{label} must be an array")
            return
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                errors.append(f"{label}: entity missing stable id")
                continue
            entity_id = item["id"]
            if entity_id in entities:
                errors.append(f"duplicate semantic id {entity_id!r}")
            else:
                entities[entity_id] = item

    frames = document.get("frames", [])
    register(frames, "frames")
    curves = document.get("curves", [])
    register(curves, "curves")
    for curve in curves if isinstance(curves, list) else []:
        if not isinstance(curve, dict): continue
        cid = curve.get("id", "<missing>")
        dim = curve.get("dimension")
        anchors = curve.get("anchors", [])
        if dim not in (2,3):
            errors.append(f"curve {cid}: dimension must be 2 or 3")
        if curve.get("closed") and len(anchors) < 3:
            errors.append(f"curve {cid}: closed curve needs >=3 anchors")
        if not curve.get("closed") and len(anchors) < 2:
            errors.append(f"curve {cid}: open curve needs >=2 anchors")
        for anchor in anchors:
            if not isinstance(anchor, dict): continue
            aid = anchor.get("id")
            if aid:
                if aid in entities: errors.append(f"duplicate semantic id {aid!r}")
                else: entities[aid] = anchor
            p, h_in, h_out = anchor.get("position"), anchor.get("incoming_handle"), anchor.get("outgoing_handle")
            if not (isinstance(p,list) and isinstance(h_in,list) and isinstance(h_out,list) and len(p)==dim and len(h_in)==dim and len(h_out)==dim):
                errors.append(f"curve {cid} anchor {aid}: position and handles must match dimension {dim}")
                continue
            if anchor.get("continuity") in {"smooth_aligned", "symmetric"}:
                vi=[h_in[k]-p[k] for k in range(dim)]
                vo=[h_out[k]-p[k] for k in range(dim)]
                ni,no=_norm(vi),_norm(vo)
                if ni<=1e-12 or no<=1e-12:
                    errors.append(f"curve {cid} anchor {aid}: smooth handles must be non-zero")
                else:
                    cos=_dot(vi,vo)/(ni*no)
                    if cos > -1+1e-8:
                        errors.append(f"curve {cid} anchor {aid}: smooth handles are not opposed/collinear")
                    if anchor.get("continuity")=="symmetric" and abs(ni-no)>1e-8*max(1.0,ni,no):
                        errors.append(f"curve {cid} anchor {aid}: symmetric handles differ in length")
        if curve.get("closed") and dim==2 and len(anchors)>=3:
            pts=[a.get("position") for a in anchors if isinstance(a,dict)]
            if len(pts)==len(anchors): errors.extend(_polygon_errors(pts,cid))
        fid=curve.get("frame_id")
        if fid is not None and fid not in {f.get("id") for f in frames if isinstance(f,dict)}:
            errors.append(f"curve {cid}: missing frame reference {fid}")

    for frame in frames if isinstance(frames,list) else []:
        if not isinstance(frame,dict): continue
        fid=frame.get("id")
        origin, axes=frame.get("origin_mm"),frame.get("basis_axes")
        if not (isinstance(origin,list) and len(origin)==3 and isinstance(axes,list) and len(axes)==3):
            errors.append(f"frame {fid}: origin/basis shape invalid"); continue
        if any(not isinstance(a,list) or len(a)!=3 for a in axes):
            errors.append(f"frame {fid}: each basis axis must be vec3"); continue
        if any(abs(_norm(a)-1)>1e-9 for a in axes) or any(abs(_dot(axes[i],axes[j]))>1e-9 for i in range(3) for j in range(i+1,3)):
            errors.append(f"frame {fid}: basis is not orthonormal within 1e-9")
        if abs(_det_axes(axes)-1)>1e-9:
            errors.append(f"frame {fid}: basis determinant must be +1 within 1e-9")

    curve_by_id={c.get("id"):c for c in curves if isinstance(c,dict)}
    frame_ids={f.get("id") for f in frames if isinstance(f,dict)}
    station_ids=set()
    mount_ids=set()
    patch_ids=set()
    component_ids=set()
    feature_ids=set()

    if isinstance(board,dict):
        outline_id=board.get("outline_curve_id")
        outline=curve_by_id.get(outline_id)
        if not outline or outline.get("dimension")!=2 or not outline.get("closed"):
            errors.append("board outline must reference a closed 2D curve")
        for field in ("rocker_curve_id","stringer_curve_id"):
            cid=board.get(field)
            if cid is not None and cid not in curve_by_id:
                errors.append(f"board {field} references missing curve {cid}")
        sts=board.get("stations",[])
        register(sts,"board stations")
        last_x=None
        for s in sts if isinstance(sts,list) else []:
            if not isinstance(s,dict): continue
            sid=s.get("id"); station_ids.add(sid)
            x=s.get("x_mm")
            if last_x is not None and x is not None and x<=last_x: errors.append("board stations must be strictly increasing in x_mm")
            last_x=x
            if s.get("frame_id") not in frame_ids: errors.append(f"station {sid}: missing frame {s.get('frame_id')}")
            if s.get("width_mm",0)<=0 or s.get("thickness_mm",0)<=0: errors.append(f"station {sid}: width/thickness must be positive")
            if not (s.get("deck_profile",{}).get("curve_id") or s.get("bottom_profile",{}).get("curve_id")):
                try:
                    for i in range(101):
                        u=-1+2*i/100
                        bottom=s.get("bottom_z_mm",0)+_profile_eval(s.get("bottom_profile",{}),u)
                        deck=s.get("bottom_z_mm",0)+s.get("thickness_mm",0)+_profile_eval(s.get("deck_profile",{}),u)
                        if deck-bottom<=0.1: errors.append(f"station {sid}: deck-bottom crossing/thickness <=0.1 mm at u={u:.2f}"); break
                except Exception as exc: errors.append(f"station {sid}: invalid profile parameters ({exc})")
            profiles=(s.get("deck_profile",{}),s.get("bottom_profile",{}))
            for pf in profiles:
                cid=pf.get("curve_id")
                if cid:
                    section_curve=curve_by_id.get(cid)
                    if not section_curve: errors.append(f"station {sid}: profile references missing curve {cid}")
                    elif section_curve.get("dimension")!=2: errors.append(f"station {sid}: profile curve {cid} must be 2D")
            if s.get("symmetry","symmetric")=="symmetric" and not any(p.get("curve_id") for p in profiles):
                try:
                    for profile in profiles:
                        for i in range(51):
                            u=i/50
                            if abs(_profile_eval(profile,u)-_profile_eval(profile,-u))>1e-8:
                                errors.append(f"station {sid}: asymmetric profile declared symmetric")
                                raise StopIteration
                except StopIteration:
                    pass
        mounts=board.get("mounts",[])
        register(mounts,"board mounts")
        for m in mounts if isinstance(mounts,list) else []:
            if not isinstance(m,dict): continue
            mount_ids.add(m.get("id"))
            if m.get("frame_id") not in frame_ids: errors.append(f"mount {m.get('id')}: missing frame")
            target=m.get("target_id")
            if target and target not in entities: errors.append(f"mount {m.get('id')}: missing target {target}")
        for end in (board.get("nose",{}),board.get("tail",{})):
            cid=end.get("boundary_curve_id")
            if cid and cid not in curve_by_id: errors.append(f"end condition references missing boundary curve {cid}")
        for cid in board.get("rail_definition",{}).get("boundary_curve_ids",[]):
            if cid not in curve_by_id: errors.append(f"rail boundary references missing curve {cid}")

    if isinstance(foil,dict):
        register([foil],"foil assembly")
        components=foil.get("components",[])
        register(components,"foil components")
        for c in components if isinstance(components,list) else []:
            if not isinstance(c,dict): continue
            component_ids.add(c.get("id"))
            if c.get("frame_id") not in frame_ids: errors.append(f"foil component {c.get('id')}: missing frame")
            attach=c.get("attachment",{})
            q=attach.get("quaternion_wxyz",[])
            if len(q)==4 and abs(_norm(q)-1)>1e-9: errors.append(f"foil component {c.get('id')}: attachment quaternion must be unit length")
            parent=attach.get("parent_component_id")
            if parent and parent not in {x.get("id") for x in components if isinstance(x,dict)}: errors.append(f"foil component {c.get('id')}: parent component {parent} missing")
            for cid in c.get("outline_curve_ids",[]):
                outline_curve=curve_by_id.get(cid)
                if not outline_curve: errors.append(f"foil component {c.get('id')}: outline curve {cid} missing")
                elif outline_curve.get("dimension")!=2 or not outline_curve.get("closed"): errors.append(f"foil component {c.get('id')}: outline curve {cid} must be closed 2D")
            stations=c.get("stations",[])
            register(stations,f"foil stations {c.get('id')}")
            prev=None
            for st in stations if isinstance(stations,list) else []:
                if not isinstance(st,dict): continue
                if prev is not None and st.get("span_mm")<=prev: errors.append(f"foil component {c.get('id')}: span stations not strictly ordered")
                prev=st.get("span_mm")
                if st.get("frame_id") not in frame_ids: errors.append(f"foil station {st.get('id')}: missing frame")
                sc=curve_by_id.get(st.get("section_curve_id"))
                if not sc or sc.get("dimension")!=2: errors.append(f"foil station {st.get('id')}: section curve must reference 2D curve")
        # Parent attachment graph must be acyclic.
        parents={c.get("id"):c.get("attachment",{}).get("parent_component_id") for c in components if isinstance(c,dict)}
        for cid in parents:
            seen=set(); cur=cid
            while cur and cur in parents:
                if cur in seen: errors.append(f"foil attachment cycle involving component {cid}"); break
                seen.add(cur); cur=parents[cur]

    graph=document.get("feature_graph",{})
    nodes=graph.get("nodes",[]) if isinstance(graph,dict) else []
    register(nodes,"feature nodes")
    feature_ids={n.get("id") for n in nodes if isinstance(n,dict)}
    adj={fid:set() for fid in feature_ids}
    for edge in graph.get("edges",[]) if isinstance(graph,dict) else []:
        a,b=edge.get("from_node_id"),edge.get("to_node_id")
        if a not in feature_ids or b not in feature_ids: errors.append(f"feature edge references missing node {a}->{b}")
        elif a==b: errors.append(f"feature graph self-cycle at {a}")
        else: adj[a].add(b)
    for node in nodes if isinstance(nodes,list) else []:
        if not isinstance(node,dict): continue
        for inp in node.get("inputs",[]):
            if inp not in entities: errors.append(f"feature {node.get('id')}: missing semantic input {inp}")
            if inp in feature_ids: adj[inp].add(node.get("id"))
        for outid in node.get("outputs",[]):
            if outid not in entities: errors.append(f"feature {node.get('id')}: output id {outid} has no semantic entity")
    visiting=set(); visited=set()
    def dfs(node):
        if node in visiting: errors.append(f"feature graph cycle at {node}"); return
        if node in visited: return
        visiting.add(node)
        for child in adj.get(node,[]): dfs(child)
        visiting.remove(node); visited.add(node)
    for node in adj: dfs(node)

    recipe=document.get("surface_recipe",{})
    patches=recipe.get("patches",[]) if isinstance(recipe,dict) else []
    register(patches,"surface patches")
    for p in patches if isinstance(patches,list) else []:
        if not isinstance(p,dict): continue
        patch_ids.add(p.get("id"))
        for cid in p.get("boundary_curve_ids",[]):
            if cid not in curve_by_id: errors.append(f"patch {p.get('id')}: boundary curve {cid} missing")
        for sid in p.get("station_ids",[]):
            if sid not in station_ids and sid not in entities: errors.append(f"patch {p.get('id')}: station {sid} missing")
    for shared in recipe.get("shared_boundaries",[]) if isinstance(recipe,dict) else []:
        if shared.get("curve_id") not in curve_by_id: errors.append(f"shared boundary curve {shared.get('curve_id')} missing")
        for pid in shared.get("patch_ids",[]):
            if pid not in patch_ids: errors.append(f"shared boundary patch {pid} missing")

    for variant in document.get("variants",[]) if isinstance(document.get("variants"),list) else []:
        register([variant],"variants")
        for change in variant.get("changes",[]):
            target=change.get("target_id")
            if target not in entities: errors.append(f"variant {variant.get('id')}: target {target} missing")
            path=change.get("field_path",[])
            if not path or any(not isinstance(k,str) or k in {"id","model_id","document_type","schema_version"} for k in path):
                errors.append(f"variant {variant.get('id')}: field_path empty or attempts immutable identity field")
            if change.get("operation")=="set" and "value" not in change: errors.append(f"variant {variant.get('id')}: set operation requires value")
            if change.get("operation")=="remove" and "value" in change: errors.append(f"variant {variant.get('id')}: remove operation must not include value")

    tol=document.get("tolerance_profile",{})
    if isinstance(tol,dict):
        for name,value in tol.items():
            if not isinstance(value,(int,float)) or value<=0: errors.append(f"tolerance {name} must be positive")
    derived=document.get("derived",{})
    if isinstance(derived,dict):
        for prop in derived.get("properties",[]):
            if prop.get("name")=="volume_mm3" and isinstance(prop.get("value"),(int,float)) and prop["value"]<=0:
                errors.append("derived solid volume must be positive")
    return errors


def validate_shape_document(document: dict[str, Any]) -> None:
    errors=validate_document(document)
    if errors: raise ShapeDocumentError(errors)


def dumps_document(document: dict[str, Any], *, indent: int = 2) -> str:
    validate_shape_document(document)
    return json.dumps(document,indent=indent,sort_keys=True,allow_nan=False)


def loads_document(text: str) -> dict[str, Any]:
    document=json.loads(text)
    validate_shape_document(document)
    return document


def apply_variant(base_document: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    """Apply v0.1 field-level set/remove deltas to a deep copy; base is untouched."""
    result=copy.deepcopy(base_document)
    def find_target(root: Any, target_id: str):
        if isinstance(root,dict):
            if root.get("id")==target_id: return root
            for val in root.values():
                found=find_target(val,target_id)
                if found is not None: return found
        elif isinstance(root,list):
            for item in root:
                found=find_target(item,target_id)
                if found is not None: return found
        return None
    for change in variant.get("changes",[]):
        target=find_target(result,change["target_id"])
        if target is None: raise ShapeDocumentError([f"variant target {change['target_id']} missing"])
        path=change["field_path"]
        if any(k in {"id","model_id","document_type","schema_version"} for k in path):
            raise ShapeDocumentError(["variant cannot change immutable identity"])
        current=target
        for key in path[:-1]:
            if key not in current or not isinstance(current[key],dict): raise ShapeDocumentError([f"variant path {path} not found"])
            current=current[key]
        leaf=path[-1]
        if change["operation"]=="set": current[leaf]=copy.deepcopy(change["value"])
        elif change["operation"]=="remove":
            if leaf not in current: raise ShapeDocumentError([f"variant path {path} not found"])
            del current[leaf]
        else: raise ShapeDocumentError([f"unsupported variant operation {change['operation']}"])
    return result


def _stable_id(seed: str, name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{seed}:{name}"))


def import_legacy_board_json(data: dict[str, Any], *, model_id: str | None = None) -> dict[str, Any]:
    """Convert legacy BoardStation JSON to a v0.1 document without changing legacy output.

    Planform and rocker are reconstructed from station data and are marked as
    approximations. The exact legacy payload is retained under board.legacy_source.
    """
    from src.board.geometry import BoardStation, BoardDefinition

    if not isinstance(data,dict) or not isinstance(data.get("stations"),list):
        raise ValueError("legacy board JSON requires a stations array")
    allowed={"name","perimeter_samples","longitudinal_samples_per_interval","stations"}
    unknown=set(data)-allowed
    if unknown: raise ValueError(f"Unknown legacy fields: {', '.join(sorted(unknown))}")
    legacy_stations=[]
    for i,raw in enumerate(data["stations"]):
        if not isinstance(raw,dict): raise ValueError(f"legacy station {i} must be object")
        allowed_station={"x_mm","width_mm","thickness_mm","bottom_z_mm","deck_crown_mm","bottom_concave_mm"}
        unknown=set(raw)-allowed_station
        if unknown: raise ValueError(f"legacy station {i}: unknown fields {', '.join(sorted(unknown))}")
        if not {"x_mm","width_mm","thickness_mm"}.issubset(raw): raise ValueError(f"legacy station {i}: x_mm,width_mm,thickness_mm required")
        legacy_stations.append(BoardStation(**raw))
    definition=BoardDefinition(str(data.get("name","Legacy board")),tuple(legacy_stations),int(data.get("perimeter_samples",48)),int(data.get("longitudinal_samples_per_interval",8))))
    canonical=json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False)
    seed=model_id or str(uuid.uuid5(_NAMESPACE,canonical))
    model_id=seed
    def sid(label): return _stable_id(seed,label)
    frames=[]
    curves=[]
    stations=[]
    curve_ids={"outline":sid("outline"),"rocker":sid("rocker"),"stringer":sid("stringer")}
    # Global frame is used by the 2D X/Y and X/Z guide curves.
    frames.append({"id":sid("global_frame"),"origin_mm":[0,0,0],"basis_axes":[[1,0,0],[0,1,0],[0,0,1]]})
    # Cross-section frame: local axes are +Y, +Z, +X, preserving right handedness.
    for i,s in enumerate(definition.stations):
        frames.append({"id":sid(f"station_frame_{i}"),"origin_mm":[s.x_mm,0,s.bottom_z_mm],"basis_axes":[[0,1,0],[0,0,1],[1,0,0]]})
        stations.append({"id":sid(f"station_{i}"),"x_mm":s.x_mm,"frame_id":sid(f"station_frame_{i}"),"role":"tip" if s.width_mm==0 else "regular","width_mm":max(s.width_mm,0.001),"thickness_mm":s.thickness_mm,"bottom_z_mm":s.bottom_z_mm,"deck_profile":{"kind":"dome","depth_mm":s.deck_crown_mm},"bottom_profile":{"kind":"single_concave","depth_mm":s.bottom_concave_mm}})
    # Build a simple station-derived outline. Width is approximate; preserve raw input.
    nonzero=[s for s in definition.stations if s.width_mm>0]
    if len(nonzero)<2: raise ValueError("legacy board needs at least two nonzero-width stations for approximate outline")
    port=[[s.x_mm,-s.width_mm/2] for s in nonzero]
    starboard=[[s.x_mm,s.width_mm/2] for s in reversed(nonzero)]
    outline_points=port+starboard
    rocker_points=[[s.x_mm,s.bottom_z_mm] for s in definition.stations]
    stringer_points=[[s.x_mm,s.bottom_z_mm+s.thickness_mm] for s in definition.stations]
    def curve(label,role,dimension,closed,points,frame_id):
        cid=curve_ids[label]
        anchors=[]
        for i,p in enumerate(points):
            aid=sid(f"{label}_anchor_{i}")
            anchors.append({"id":aid,"position":p,"incoming_handle":p.copy(),"outgoing_handle":p.copy(),"continuity":"corner"})
        curves.append({"id":cid,"role":role,"dimension":dimension,"frame_id":frame_id,"closed":closed,"anchors":anchors,"revision":0})
    curve("outline","outline_xy",2,True,outline_points,sid("global_frame"))
    curve("rocker","rocker_xz",2,False,rocker_points,sid("global_frame"))
    curve("stringer","stringer_xz",2,False,stringer_points,sid("global_frame"))
    document={
        "document_type":DOCUMENT_TYPE,"schema_version":SCHEMA_VERSION,"model_id":model_id,"name":definition.name,"product_kind":"wingfoil_board",
        "units":{"length":"mm","angle":"rad"},
        "coordinate_system":{"handedness":"right","x":"nose_to_tail_positive_aft","y":"centerline_to_starboard_positive","z":"bottom_to_deck_positive_up"},
        "frames":frames,"curves":curves,
        "board":{"outline_curve_id":curve_ids["outline"],"rocker_curve_id":curve_ids["rocker"],"stringer_curve_id":curve_ids["stringer"],"stations":stations,
                 "rail_definition":{"boundary_curve_ids":[curve_ids["outline"]],"transition":"g0","parameters":{"legacy_approximation":True}},
                 "nose":{"shape_family":"round","boundary_curve_id":None,"parameters":{"legacy_approximation":True}},
                 "tail":{"shape_family":"round","boundary_curve_id":None,"parameters":{"legacy_approximation":True}},
                 "mounts":[],"legacy_source":copy.deepcopy(data)},
        "foil_assembly":None,"feature_graph":{"nodes":[],"edges":[]},"surface_recipe":{"patches":[],"shared_boundaries":[]},
        "tolerance_profile":{"curve_fit_mm":0.05,"section_fit_mm":0.05,"g0_mm":0.05,"g1_rad":math.radians(0.5),"g2_mm_inv":0.001,"sewing_mm":0.05,"tessellation_chord_mm":0.5,"tessellation_angle_rad":math.radians(5),"manufacturing_mm":0.5},
        "variants":[],"derived":{"source_revision":None,"properties":[],"validation":[{"code":"LEGACY_APPROX","message":"Outline, rocker and stringer reconstructed from stations; original legacy JSON retained verbatim in board.legacy_source.","severity":"warning"}]}
    }
    validate_shape_document(document)
    return document
