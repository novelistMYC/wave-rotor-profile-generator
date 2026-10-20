# -*- coding: utf-8 -*-
"""
波形转子（等半径圆弧）轮廓 DXF 生成器  v2.0
=================================================
输入：外接圆直径、内接圆直径、极对数 n，可选中心内径与相位
输出：DXF（默认存桌面）—— n 段凸「嵴顶弧」+ n 段凹「过渡弧」，
      共 2n 段圆弧，半径完全相同、两两相切；
      另含内外接圆辅助圆，以及中心内径通孔（不填色，必须小于内接圆）。

几何原理
--------
· 嵴顶弧要凸到外接圆 r1：圆心在「嵴轴」上、距中心 a = r1 - R；
· 过渡弧要凹到内接圆 r2：圆心在「谷轴」上、距中心 b = r2 + R；
· 两弧等半径、曲率相反 ⇒ 只能外切 ⇒ 圆心距 = 2R；
· 嵴轴与相邻谷轴夹角 θ = π/n，由余弦定理：
      (r1-R)^2 + (r2+R)^2 - 2(r1-R)(r2+R)·cosθ = (2R)^2
  整理为 R 的一元二次（半角形式）：
      R^2 + cot^2(θ/2)·(r1-r2)·R - [ (r1-r2)^2/(4·sin^2(θ/2)) + r1·r2 ] = 0
  取正根即公共半径 R。

v2.0 相对 v1 的改动（2026-10-20）
--------------------------------
1. 校验拆成互不顶替的两条（v1 把它们混为一谈，实测会误报）：
   · 星形域判据（极角是否单调）——只说明轮廓有没有局部倒扣，
     **不再冒充「自交」**；
   · 自交检测——真正逐段求交，只有检出交点才报「轮廓自交」。
2. 判据不通过时也给出真实「总转角」（v1 在这时会显示 0.000000°）。
3. 图形界面支持**实时预览**：改动任一参数立即重算重绘（120 ms 防抖）；
   v1 只在窗口缩放或点「生成 DXF」时刷新。
4. 信息栏只显示文件名，完整路径放状态栏；新增「打开输出目录」按钮。
5. 命令行新增 --version。
几何算法、DXF/SVG 输出格式与 v1 **逐字节一致**（同参数同内容）。

用法
----
  交互式：  py 转子波形DXF生成器_v2.py
  命令行：  py 转子波形DXF生成器_v2.py -o 64 -i 54 -n 3 --bore 20
  图形界面：py 转子波形DXF生成器_v2.py --gui
常用参数：--phase 旋转角(度，默认0=极顶朝正上，逆时针为正)  --name 文件名
          --outdir 输出目录  --svg 同时出 SVG  --version 版本号
"""
import math
import os
import sys
import argparse
from pathlib import Path

VERSION = "2.0"
CROSS_CAP = 32          # 自交检测最多记这么多处交点（再多也只是"很多"）
LAYER_SHAPE = "WAVE"    # DXF 图层：轮廓（2n 段圆弧 + 中心通孔）
LAYER_AUX = "AUX"       # DXF 图层：内外接圆辅助线（默认关闭，图元与图层都保留）


# PyInstaller 的 --windowed 模式下 stdout/stderr 可能为 None，先兜底，避免 print 崩溃
class _NullStream(object):
    def write(self, *a):
        pass

    def flush(self):
        pass

    def isatty(self):
        return False


if sys.stdout is None:
    sys.stdout = _NullStream()
if sys.stderr is None:
    sys.stderr = _NullStream()
# 控制台/重定向到 GBK 文件时，告警里的 ⚠ 等符号不应该把程序弄崩
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass


def _resource_path(name):
    """PyInstaller 打包后资源在 sys._MEIPASS；未打包时在本文件同目录。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, name)
    return p if os.path.exists(p) else None


DEFAULT_OUTDIR = Path.home() / "Desktop"

# ---------------------------------------------------------------- 几何 ----
def solve_R(r1, r2, n):
    """等半径外切条件解公共圆弧半径 R。"""
    half = math.pi / (2.0 * n)                 # θ/2
    cot = 1.0 / math.tan(half)
    B = (cot ** 2) * (r1 - r2)
    C = -(((r1 - r2) ** 2) / (4.0 * math.sin(half) ** 2) + r1 * r2)
    disc = B * B - 4.0 * C
    if disc < 0:
        return None
    return (-B + math.sqrt(disc)) / 2.0


def _mid(p, q):
    return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)


def build_profile(r1, r2, n, phase_deg=0.0):
    """返回 (R, a, b, arcs)。arcs 按遍历顺序：嵴顶@0, 过渡@0, 嵴顶@1, 过渡@1 ..."""
    R = solve_R(r1, r2, n)
    if R is None or R <= 0:
        raise ValueError("无有效解（请检查内外径与极对数）")
    a = r1 - R
    b = r2 + R
    ph = math.radians(phase_deg)
    step = 2.0 * math.pi / n
    Cc, Cv = [], []
    for j in range(n):
        al = ph + j * step
        be = al + math.pi / n
        Cc.append((a * math.cos(al), a * math.sin(al)))
        Cv.append((b * math.cos(be), b * math.sin(be)))
    Pstart, Pend = [], []
    for j in range(n):
        Pstart.append(_mid(Cv[j - 1], Cc[j]))
        Pend.append(_mid(Cc[j], Cv[j]))
    arcs = []
    for j in range(n):
        arcs.append(dict(kind="crest", j=j, C=Cc[j], r=R,
                         src=Pstart[j], dst=Pend[j], dir=1))
        arcs.append(dict(kind="valley", j=j, C=Cv[j], r=R,
                         src=Pend[j], dst=Pstart[(j + 1) % n], dir=-1))
    for ar in arcs:
        aF = math.degrees(math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0]))
        aT = math.degrees(math.atan2(ar["dst"][1] - ar["C"][1], ar["dst"][0] - ar["C"][0]))
        s, e = (aF, aT) if ar["dir"] > 0 else (aT, aF)
        ar["sDeg"] = s % 360.0
        ar["eDeg"] = e % 360.0
        ar["delta"] = (ar["eDeg"] - ar["sDeg"]) % 360.0
    return R, a, b, arcs


def sample_contour(arcs, per=160):
    """按 2n 段的遍历顺序采样成闭合折线（每段含起点、不含终点，段间共用接点）。"""
    per = max(2, int(per))
    pts = []
    for ar in arcs:
        th0 = math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0])
        step = math.radians(ar["delta"]) / per
        for k in range(per):
            th = th0 + ar["dir"] * step * k
            pts.append((ar["C"][0] + ar["r"] * math.cos(th),
                        ar["C"][1] + ar["r"] * math.sin(th)))
    return pts


def check_star(pts):
    """星形域判据：极角是否单调递增（不单调 ⇒ 有局部倒扣，**不等于**自交）。
    返回 (是否单调, 总转角)。总转角始终按整圈累计（v1 判据失败时直接返回 0，
    报告里会显示 0.000000°，看起来像数据坏了）。"""
    if len(pts) < 3:
        return False, 0.0
    prev = math.atan2(pts[0][1], pts[0][0])
    total = 0.0
    mono = True
    for x, y in pts[1:] + [pts[0]]:
        ang = math.atan2(y, x)
        d = ang - prev
        while d <= -math.pi:
            d += 2.0 * math.pi
        while d > math.pi:
            d -= 2.0 * math.pi
        if d < -1e-9:
            mono = False
        total += d
        prev = ang
    return (mono and abs(total - 2.0 * math.pi) < 1e-6), total


def _seg_hit(p1, p2, p3, p4, eps=1e-12):
    """两条线段是否真正相交（端点相接、共线重叠不算）。"""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)
    return (((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and
            ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)))


def find_crossings(arcs, per=None, cap=CROSS_CAP):
    """真·自交检测：把轮廓采样成折线后逐段求交，返回交点所在的段号对（最多 cap 个）。
    用均匀网格粗筛，避免大 n 时 O(n^2) 变慢。"""
    m_arc = len(arcs)
    if per is None:
        per = max(16, min(96, 2400 // max(1, m_arc)))
    pts = sample_contour(arcs, per)
    m = len(pts)
    if m < 6:
        return []
    segs = [(pts[i], pts[(i + 1) % m]) for i in range(m)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    cell = span / 40.0
    grid = {}
    for i, (p, q) in enumerate(segs):
        cx0 = int(math.floor(min(p[0], q[0]) / cell))
        cx1 = int(math.floor(max(p[0], q[0]) / cell))
        cy0 = int(math.floor(min(p[1], q[1]) / cell))
        cy1 = int(math.floor(max(p[1], q[1]) / cell))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                grid.setdefault((cx, cy), []).append(i)
    seen = set()
    hits = []
    for ids in grid.values():
        L = len(ids)
        for u in range(L):
            i = ids[u]
            for v in range(u + 1, L):
                j = ids[v]
                if abs(i - j) <= 1 or (i == 0 and j == m - 1):
                    continue                      # 相邻段共用接点，不算交点
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                seen.add(key)
                if _seg_hit(segs[i][0], segs[i][1], segs[j][0], segs[j][1]):
                    hits.append(key)
                    if len(hits) >= cap:
                        return hits
    return hits


def sample_extremes(R, arcs):
    """采样得到轮廓真实的最大 / 最小半径。"""
    rmax, rmin = 0.0, float("inf")
    for ar in arcs:
        th0 = math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0])
        d = math.radians(ar["delta"])
        for k in range(2001):
            th = th0 + ar["dir"] * d * k / 2000
            rr = math.hypot(ar["C"][0] + ar["r"] * math.cos(th),
                            ar["C"][1] + ar["r"] * math.sin(th))
            rmax = max(rmax, rr)
            rmin = min(rmin, rr)
    return rmax, rmin


# ---------------------------------------------------------------- 校验 ----
def cross_text(info, short=False):
    """自交检测结论的统一说法。"""
    c = info.get("crossing_count") or 0
    if not c:
        return "未检出交点"
    tail = "以上" if info.get("crossing_capped") else ""
    return "检出 %d 处%s交点%s" % (c, tail, "！" if short else "")


def analyze(outer, inner, pairs, phase=0.0, bore=0.0):
    """只算不写：几何解 + 两条独立校验 + 告警清单。"""
    if outer <= 0 or inner <= 0:
        raise ValueError("直径必须为正数")
    if outer <= inner:
        raise ValueError("外接圆直径必须大于内接圆直径")
    if pairs < 2:
        raise ValueError("极对数至少为 2（1 对会退化成无效轮廓）")
    bore = float(bore or 0.0)
    if bore < 0:
        raise ValueError("内径不能为负数")
    if bore > 0 and bore >= inner:
        raise ValueError("内径必须小于内接圆直径（φ%g 应 < φ%g）" % (bore, inner))
    r1, r2 = outer / 2.0, inner / 2.0
    # 对外相位以「极顶朝正上」为 0°；内部几何基准是 +Y（90°），故加 90
    R, a, b, arcs = build_profile(r1, r2, int(pairs), phase + 90.0)
    pts = sample_contour(arcs, 160)
    star, turn = check_star(pts)
    crossings = find_crossings(arcs)
    rmax, rmin = sample_extremes(R, arcs)
    crest, valley = arcs[0]["delta"], arcs[1]["delta"]

    capped = len(crossings) >= CROSS_CAP
    warn = []
    if crossings:
        warn.append("⚠ 轮廓自交（检出 %d 处%s真实交点），实体不能直接用；"
                    "请加大内径或减少极对数。" % (len(crossings), "以上" if capped else ""))
    elif not star:
        warn.append("注：非星形域（极角不单调）——轮廓本身**不自交**，但存在局部倒扣，"
                    "冲裁/线割前请确认工艺可行。")
    if crest > 180.0:
        warn.append("注：嵴顶弧包角 > 180°，属深波形（局部倒扣），请确认工艺上可用。")
    if valley < 3.0:
        warn.append("注：过渡弧包角 < 3°，已接近尖角，注意刀具/电极圆角。")

    return {
        "outer": outer, "inner": inner, "pairs": int(pairs), "phase": phase, "bore": bore,
        "r1": r1, "r2": r2, "R": R, "a": a, "b": b,
        "crest_span": crest, "valley_span": valley,
        "rmax": rmax, "rmin": rmin,
        "junctions": [ar["src"] for ar in arcs],
        "star": star, "turn": math.degrees(turn),
        "crossings": crossings, "crossing_count": len(crossings),
        "crossing_capped": capped,
        "simple": (not crossings),          # 兼容 v1 字段名：simple = 无自交
        "warnings": warn,
        "arcs": arcs,
        "dxf": None, "svg": None,
    }


# ---------------------------------------------------------------- 输出 ----
def fmt(x):
    s = "%.10f" % x
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def dxf_text(R, arcs, r1, r2, bore=0.0):
    L = []

    def a(*xs):
        L.extend(str(v) for v in xs)

    a(0, "SECTION", 2, "HEADER", 9, "$ACADVER", 1, "AC1009",
      9, "$INSBASE", 10, "0.0", 20, "0.0", 30, "0.0",
      9, "$EXTMIN", 10, fmt(-r1), 20, fmt(-r1), 30, "0.0",
      9, "$EXTMAX", 10, fmt(r1), 20, fmt(r1), 30, "0.0",
      0, "ENDSEC", 0, "SECTION", 2, "TABLES",
      0, "TABLE", 2, "LAYER", 70, 2)
    # 只保留两个图层，且都不为空：
    #   WAVE —— 2n 段轮廓圆弧 + 中心通孔
    #   AUX  —— 内外接圆辅助线；颜色码取负值 = 图层 Off（默认隐藏，图元与图层都保留）
    for name, color in ((LAYER_SHAPE, 7), (LAYER_AUX, -8)):
        a(0, "LAYER", 2, name, 70, 0, 62, color, 6, "CONTINUOUS")
    a(0, "ENDTAB", 0, "ENDSEC", 0, "SECTION", 2, "ENTITIES")
    for ar in arcs:
        a(0, "ARC", 8, LAYER_SHAPE,
          10, fmt(ar["C"][0]), 20, fmt(ar["C"][1]), 30, "0.0",
          40, fmt(R), 50, fmt(ar["sDeg"]), 51, fmt(ar["eDeg"]))
    for rr in (r1, r2):
        a(0, "CIRCLE", 8, LAYER_AUX, 10, "0.0", 20, "0.0", 30, "0.0", 40, fmt(rr))
    if bore and bore > 0:
        a(0, "CIRCLE", 8, LAYER_SHAPE, 10, "0.0", 20, "0.0", 30, "0.0", 40, fmt(bore / 2.0))
    a(0, "ENDSEC", 0, "EOF")
    return "\n".join(L) + "\n"


def svg_text(R, arcs, r1, r2, bore=0.0):
    d = "M %s %s" % (fmt(arcs[0]["src"][0]), fmt(arcs[0]["src"][1]))
    for ar in arcs:
        large = 1 if ar["delta"] > 180 else 0
        sweep = 1 if ar["dir"] > 0 else 0
        d += " A %s %s 0 %d %d %s %s" % (
            fmt(R), fmt(R), large, sweep, fmt(ar["dst"][0]), fmt(ar["dst"][1]))
    d += " Z"
    big = r1 + 1
    bore_svg = ('<circle r="%s" fill="#FFFFFF" stroke="#000000" stroke-width="0.12"/>\n'
                % fmt(bore / 2.0)) if bore and bore > 0 else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s %s %s %s" '
            'width="1020" height="1020">\n<g transform="scale(1,-1)" fill="none">\n'
            '<circle r="%s" stroke="#808080" stroke-width="0.07"/>\n'
            '<circle r="%s" stroke="#808080" stroke-width="0.07"/>\n'
            '<path d="%s" stroke="#000000" stroke-width="0.12" stroke-linejoin="round"/>\n'
            '%s'
            '</g>\n</svg>\n') % (fmt(-big), fmt(-big), fmt(2 * big), fmt(2 * big),
                                fmt(r1), fmt(r2), d, bore_svg)


def unique_path(folder, stem, ext):
    """绝不覆盖：同名已存在则自动加 _2 / _3 ..."""
    p = folder / (stem + ext)
    k = 2
    while p.exists():
        p = folder / ("%s_%d%s" % (stem, k, ext))
        k += 1
    return p


# ---------------------------------------------------------------- 主流程 ----
def generate(outer, inner, pairs, phase=0.0, name=None, outdir=None, want_svg=False, bore=0.0):
    info = analyze(outer, inner, pairs, phase, bore)
    folder = Path(outdir) if outdir else DEFAULT_OUTDIR
    folder.mkdir(parents=True, exist_ok=True)
    stem = name or ("波形转子_OD%s_ID%s" % ("%g" % outer, "%g" % inner))
    dxf_path = unique_path(folder, stem, ".dxf")
    dxf_path.write_text(dxf_text(info["R"], info["arcs"], info["r1"], info["r2"], info["bore"]),
                        encoding="ascii")   # 图层名是英文，纯 ASCII，任何环境都不会乱码
    svg_path = None
    if want_svg:
        svg_path = unique_path(folder, stem, ".svg")
        svg_path.write_text(svg_text(info["R"], info["arcs"], info["r1"], info["r2"], info["bore"]),
                            encoding="utf-8")
    info["dxf"] = str(dxf_path)
    info["svg"] = str(svg_path) if svg_path else None
    return info


def print_report(info):
    print("=" * 66)
    _bore = info.get("bore") or 0.0
    print("  波形转子轮廓生成器 v%s" % VERSION)
    print("  外接圆 φ%g   内接圆 φ%g   内径 %s   %d 对极   相位 %g°"
          % (info["outer"], info["inner"],
             ("φ%g" % _bore) if _bore > 0 else "无", info["pairs"], info["phase"]))
    print("-" * 66)
    print("  公共圆弧半径 R      = %.10f" % info["R"])
    print("  嵴顶弧圆心距中心 a  = %.10f" % info["a"])
    print("  过渡弧圆心距中心 b  = %.10f" % info["b"])
    print("  嵴顶弧包角          = %.6f°  (%d 段)" % (info["crest_span"], info["pairs"]))
    print("  过渡弧包角          = %.6f°  (%d 段)" % (info["valley_span"], info["pairs"]))
    print("  轮廓实测 rmax/rmin  = %.10f / %.10f" % (info["rmax"], info["rmin"]))
    print("  星形域判据(极角单调)= %s" % ("通过" if info["star"] else "不通过（存在局部倒扣）"))
    print("  自交检测(逐段求交)  = %s" % cross_text(info))
    print("  总转角              = %.6f°" % info["turn"])
    print("-" * 66)
    for ar in info["arcs"]:
        print("  %-6s@%3d  C=(%10.6f, %10.6f)  R=%.6f  起 %9.5f 止 %9.5f"
              % (("嵴顶" if ar["kind"] == "crest" else "过渡"), ar["j"],
                 ar["C"][0], ar["C"][1], ar["r"], ar["sDeg"], ar["eDeg"]))
    print("-" * 66)
    if info.get("dxf"):
        print("  已写出：%s" % info["dxf"])
    if info.get("svg"):
        print("  已写出：%s" % info["svg"])
    for w in info.get("warnings") or []:
        print("  " + w)
    print("=" * 66)


def ask_float(msg, default=None):
    while True:
        s = input(msg).strip()
        if not s and default is not None:
            return default
        try:
            return float(s)
        except ValueError:
            print("  请输入数字。")


def run_cli(args):
    outer, inner, pairs = args.outer, args.inner, args.pairs
    print("—— 波形转子 DXF 生成器 v%s（回车使用[]内默认值）——" % VERSION)
    if outer is None:
        outer = ask_float("外接圆直径 (mm)：")
    if inner is None:
        inner = ask_float("内接圆直径 (mm)：")
    if pairs is None:
        pairs = int(ask_float("极对数 n："))
    if getattr(args, "bore", None) is None:
        b = input("中心内径 (mm，0 或直接回车 = 无中孔)：").strip()
        bore = float(b) if b else 0.0
    else:
        bore = float(args.bore or 0.0)
    info = generate(outer, inner, pairs, args.phase, args.name, args.outdir, args.svg, bore)
    print_report(info)
    return info


# ---------------------------------------------------------------- 图形界面 ----
def run_gui():
    """图形界面：声明 DPI 感知 + 全部尺寸按 DPI 缩放，高分屏上不发虚；字号按 11pt 基准。"""
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    # ---- 先声明 DPI 感知：否则 200% 缩放下 Windows 会整块放大位图（发虚、发糊）----
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    root = tk.Tk()
    try:
        _dpi = float(root.winfo_fpixels("1i"))
    except Exception:
        _dpi = 96.0
    if not (72.0 <= _dpi <= 480.0):
        _dpi = 96.0
    S = max(1.0, min(3.0, _dpi / 96.0))
    try:
        root.tk.call("tk", "scaling", _dpi / 72.0)   # 字号按 DPI 放大
    except Exception:
        pass

    def p(n):
        """把设计稿的“96 DPI 像素”换算成本机像素。"""
        return int(round(n * S))

    # ---------- 设计令牌 ----------
    PAGE, CARD = "#F1F3F6", "#FFFFFF"
    LINE, FIELD = "#E4E8EE", "#F9FAFB"
    INPUT = "#DCE1E8"
    TEXT, MUTED, FAINT = "#1A1D21", "#8A9199", "#AEB4BD"
    ACCENT, ACCENT_D = "#2563EB", "#1D4ED8"
    OK, BAD, AMBER = "#12B76A", "#E5484D", "#B45309"
    OK_BG, BAD_BG, AMBER_BG = "#F3FBF6", "#FFF5F5", "#FFF8EE"
    FILL, EDGE, AUX = "#7AC0FF", "#111827", "#C9D0DA"
    SM = ("Microsoft YaHei UI", 10)
    SMB = ("Microsoft YaHei UI", 10, "bold")
    UI = ("Microsoft YaHei UI", 11)
    TITLE = ("Microsoft YaHei UI", 17, "bold")
    BTN = ("Microsoft YaHei UI", 10, "bold")
    NUM = ("Consolas", 11)
    NUMS = ("Consolas", 10)

    root.title("波形转子 DXF 生成器")
    for _n in ("波形转子.ico",):
        _ip = _resource_path(_n)
        if _ip:
            try:
                root.iconbitmap(default=_ip)
            except Exception:
                pass
            break
    root.configure(bg=PAGE)
    _sw, _sh = root.winfo_screenwidth(), root.winfo_screenheight()
    _W = min(p(1240), int(_sw * 0.94))
    _H = min(p(780), int(_sh * 0.90))
    root.geometry("%dx%d+%d+%d" % (_W, _H, max(0, (_sw - _W) // 2), max(0, (_sh - _H) // 2)))
    root.minsize(p(1040), p(660))
    root.rowconfigure(2, weight=1)
    root.columnconfigure(0, weight=1)

    # ---------- ttk 样式 ----------
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure(".", background=CARD, foreground=TEXT, font=UI)

    def sty(name, **kw):
        try:
            st.configure(name, **kw)
        except Exception:
            pass

    def smap(name, **kw):
        try:
            st.map(name, **kw)
        except Exception:
            pass

    sty("Clean.TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT,
        bordercolor=INPUT, lightcolor=INPUT, darkcolor=INPUT, padding=p(7), relief="flat")
    smap("Clean.TEntry", bordercolor=[("focus", ACCENT)],
         lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])
    sty("Accent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
        lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT, relief="flat",
        borderwidth=0, padding=(p(24), p(11)), font=BTN)
    smap("Accent.TButton",
         background=[("pressed", ACCENT_D), ("active", ACCENT_D)],
         bordercolor=[("pressed", ACCENT_D), ("active", ACCENT_D)],
         lightcolor=[("pressed", ACCENT_D), ("active", ACCENT_D)],
         darkcolor=[("pressed", ACCENT_D), ("active", ACCENT_D)])
    sty("Ghost.TButton", background=CARD, foreground="#4B5563", bordercolor=INPUT,
        lightcolor=CARD, darkcolor=CARD, relief="solid", borderwidth=1,
        padding=(p(16), p(9)), font=SM)
    smap("Ghost.TButton", background=[("active", "#F3F5F8")],
         bordercolor=[("active", "#D8DEE6")],
         lightcolor=[("active", "#F3F5F8")], darkcolor=[("active", "#F3F5F8")])
    sty("Mini.TButton", background=CARD, foreground=MUTED, bordercolor=INPUT,
        lightcolor=CARD, darkcolor=CARD, relief="solid", borderwidth=1,
        padding=(p(11), p(5)), font=SM)
    smap("Mini.TButton", background=[("active", "#F3F5F8")],
         bordercolor=[("active", "#D8DEE6")],
         lightcolor=[("active", "#F3F5F8")], darkcolor=[("active", "#F3F5F8")])
    sty("Clean.TCheckbutton", background=CARD, foreground=MUTED, font=SM, focusthickness=0)
    smap("Clean.TCheckbutton", background=[("active", CARD)])
    sty("Flat.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
        rowheight=p(28), borderwidth=0, font=NUMS)
    sty("Flat.Treeview.Heading", background=CARD, foreground=MUTED, font=SMB,
        relief="flat", borderwidth=0, padding=(p(8), p(7)))
    smap("Flat.Treeview", background=[("selected", "#EDF3FE")],
         foreground=[("selected", TEXT)])
    try:
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    except Exception:
        pass

    # ---------- 顶栏 ----------
    head = tk.Frame(root, bg=CARD)
    head.grid(row=0, column=0, sticky="ew")
    head.columnconfigure(1, weight=1)
    tb = tk.Frame(head, bg=CARD)
    tb.grid(row=0, column=0, sticky="w", padx=p(24), pady=p(16))
    tk.Label(tb, text="波形转子 DXF 生成器", bg=CARD, fg=TEXT, font=TITLE).pack(anchor="w")
    tk.Label(tb, text="等半径圆弧轮廓 · 解析解 · 输出 DXF", bg=CARD, fg=MUTED,
             font=SM).pack(anchor="w", pady=(p(4), 0))
    btns = tk.Frame(head, bg=CARD)
    btns.grid(row=0, column=2, sticky="e", padx=p(24))
    btn_gen = ttk.Button(btns, text="生成 DXF", style="Accent.TButton")
    btn_gen.pack(side="right")
    btn_open = ttk.Button(btns, text="打开输出目录", style="Ghost.TButton")
    btn_open.pack(side="right", padx=(0, p(12)))
    tk.Frame(root, bg=LINE, height=1).grid(row=1, column=0, sticky="ew")

    # ---------- 主体 ----------
    body = tk.Frame(root, bg=PAGE)
    body.grid(row=2, column=0, sticky="nsew", padx=p(20), pady=p(20))
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, minsize=p(360), weight=0)
    body.columnconfigure(1, weight=1)

    # 左栏
    left = tk.Frame(body, bg=CARD, highlightbackground=LINE, highlightthickness=1)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, p(20)))

    tk.Label(left, text="参数", bg=CARD, fg=MUTED, font=SM).pack(
        anchor="w", padx=p(22), pady=(p(18), p(12)))
    pg = tk.Frame(left, bg=CARD)
    pg.pack(fill="x", padx=p(22))
    pg.columnconfigure(0, weight=1, uniform="p")
    pg.columnconfigure(1, weight=1, uniform="p")

    fields = [("外接圆 φ", "64"), ("内接圆 φ", "54"), ("极对数 n", "3"),
              ("相位 °", "0"), ("中心内径 φ", "35")]
    vars_ = []
    for i, (lab, dft) in enumerate(fields):
        r, c = divmod(i, 2)
        cell = tk.Frame(pg, bg=CARD)
        cell.grid(row=r, column=c, sticky="ew", pady=(0, p(14)),
                  padx=(0 if c == 0 else p(14), 0))
        if i == len(fields) - 1:
            cell.grid_configure(columnspan=2, padx=0)
        tk.Label(cell, text=lab, bg=CARD, fg=MUTED, font=SM).pack(anchor="w", pady=(0, p(6)))
        v = tk.StringVar(value=dft)
        vars_.append(v)
        ttk.Entry(cell, textvariable=v, width=1, style="Clean.TEntry",
                  font=NUM).pack(fill="x")

    tk.Frame(left, bg=LINE, height=1).pack(fill="x", padx=p(22), pady=(p(4), 0))
    tk.Label(left, text="输出", bg=CARD, fg=MUTED, font=SM).pack(
        anchor="w", padx=p(22), pady=(p(18), p(12)))
    ob = tk.Frame(left, bg=CARD)
    ob.pack(fill="x", padx=p(22))

    tk.Label(ob, text="目录", bg=CARD, fg=MUTED, font=SM).pack(anchor="w", pady=(0, p(6)))
    orow = tk.Frame(ob, bg=CARD)
    orow.pack(fill="x", pady=(0, p(14)))
    out_dir = tk.StringVar(value=str(DEFAULT_OUTDIR))
    ttk.Entry(orow, textvariable=out_dir, width=1, style="Clean.TEntry",
              font=SM).pack(side="left", fill="x", expand=True)
    ttk.Button(orow, text="浏览", style="Ghost.TButton",
               command=lambda: out_dir.set(filedialog.askdirectory() or out_dir.get())
               ).pack(side="left", padx=(p(10), 0))

    tk.Label(ob, text="文件名（留空则自动命名）", bg=CARD, fg=MUTED,
             font=SM).pack(anchor="w", pady=(0, p(6)))
    out_name = tk.StringVar(value="")
    ttk.Entry(ob, textvariable=out_name, width=1, style="Clean.TEntry",
              font=SM).pack(fill="x", pady=(0, p(14)))
    svgv = tk.BooleanVar(value=False)
    ttk.Checkbutton(ob, text="同时输出 SVG 预览", variable=svgv,
                    style="Clean.TCheckbutton").pack(anchor="w")

    tk.Label(left, text="输出永不覆盖：同名自动追加 _2、_3", bg=CARD, fg=FAINT,
             font=SM).pack(side="bottom", anchor="w", padx=p(22), pady=p(16))

    # 右栏
    right = tk.Frame(body, bg=CARD, highlightbackground=LINE, highlightthickness=1)
    right.grid(row=0, column=1, sticky="nsew")
    right.rowconfigure(2, weight=1)
    right.columnconfigure(0, weight=1)

    ph = tk.Frame(right, bg=CARD)
    ph.grid(row=0, column=0, sticky="ew", padx=p(22), pady=(p(16), p(12)))
    tk.Label(ph, text="预览", bg=CARD, fg=MUTED, font=SM).pack(side="left")
    cap_var = tk.StringVar(value="")
    tk.Label(ph, textvariable=cap_var, bg=CARD, fg=TEXT, font=UI).pack(
        side="left", padx=(p(14), 0))
    btn_detail = ttk.Button(ph, text="明细", style="Mini.TButton")
    btn_detail.pack(side="right")
    badges = tk.Frame(ph, bg=CARD)
    badges.pack(side="right", padx=(0, p(16)))
    b_star = tk.Label(badges, text="● 星形域", bg=CARD, fg=FAINT, font=SM)
    b_star.pack(side="left", padx=(0, p(18)))
    b_cross = tk.Label(badges, text="● 无自交", bg=CARD, fg=FAINT, font=SM)
    b_cross.pack(side="left")

    banner = tk.Frame(right, bg=AMBER_BG)
    banner_lb = tk.Label(banner, text="", bg=AMBER_BG, fg=AMBER, font=SM,
                         anchor="w", justify="left", wraplength=p(760))
    banner_lb.pack(fill="x", padx=p(16), pady=p(9))

    cv = tk.Canvas(right, bg=CARD, highlightthickness=0, bd=0)
    cv.grid(row=2, column=0, sticky="nsew", padx=p(22), pady=(0, p(14)))

    stats = tk.Frame(right, bg=CARD)
    stats.grid(row=3, column=0, sticky="ew", padx=p(22), pady=(0, p(18)))
    metrics = [("R", "公共圆弧 R"), ("a", "嵴顶圆心距 a"), ("b", "过渡圆心距 b"),
               ("crest", "嵴顶弧包角"), ("valley", "过渡弧包角"), ("mm", "实测 rmax / rmin")]
    stat_lb = {}
    for i, (key, lab) in enumerate(metrics):
        if i:
            tk.Frame(stats, bg=LINE, width=1, height=p(38)).pack(side="left", fill="y", padx=p(16))
        cell = tk.Frame(stats, bg=CARD)
        cell.pack(side="left")
        tk.Label(cell, text=lab, bg=CARD, fg=MUTED, font=SM).pack(anchor="w")
        lb = tk.Label(cell, text="—", bg=CARD, fg=TEXT, font=NUM)
        lb.pack(anchor="w", pady=(p(4), 0))
        stat_lb[key] = lb

    detail = tk.Frame(right, bg=CARD)
    detail_sep = tk.Frame(right, bg=LINE, height=1)
    cols = ("seg", "cx", "cy", "a0", "a1", "span", "pad")
    heads = (("seg", "段", 110, "w"), ("cx", "圆心 X", 128, "e"),
             ("cy", "圆心 Y", 128, "e"), ("a0", "起角 °", 110, "e"),
             ("a1", "止角 °", 110, "e"), ("span", "包角 °", 110, "e"),
             ("pad", "", 8, "w"))
    tv = ttk.Treeview(detail, columns=cols, show="headings", height=5,
                      style="Flat.Treeview", selectmode="browse")
    for key, text, w, anchor in heads:
        tv.heading(key, text=text, anchor=anchor)
        tv.column(key, width=p(w), minwidth=p(w), anchor=anchor, stretch=(key == "pad"))
    tv.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(detail, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    sb.grid(row=0, column=1, sticky="ns")
    detail.rowconfigure(0, weight=1)
    detail.columnconfigure(0, weight=1)
    tv.tag_configure("odd", background="#FAFBFC")

    # ---------- 底栏 ----------
    tk.Frame(root, bg=LINE, height=1).grid(row=3, column=0, sticky="ew")
    foot = tk.Frame(root, bg=CARD)
    foot.grid(row=4, column=0, sticky="ew")
    fin = tk.Frame(foot, bg=CARD)
    fin.pack(fill="x", padx=p(24), pady=p(12))
    dot = tk.Canvas(fin, width=p(10), height=p(10), bg=CARD, highlightthickness=0)
    dot.pack(side="left")
    dot_id = dot.create_oval(1, 1, p(8), p(8), fill=OK, outline="")
    status = tk.StringVar(value="就绪 —— 改参数即时预览，点「生成 DXF」写出文件")
    tk.Label(fin, textvariable=status, bg=CARD, fg=MUTED, font=SM).pack(
        side="left", padx=(p(10), 0))
    tk.Label(fin, text="v%s" % VERSION, bg=CARD, fg=FAINT, font=SM).pack(side="right")

    state = {"inf": None, "pending": None, "detail": False}

    # ---------- 交互 ----------
    def _dot(color):
        try:
            dot.itemconfigure(dot_id, fill=color)
        except Exception:
            pass

    def _open_dir():
        d = out_dir.get().strip() or str(DEFAULT_OUTDIR)
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
            os.startfile(d)
        except Exception as ex:
            messagebox.showerror("打不开", str(ex))

    def _params():
        return (float(vars_[0].get()), float(vars_[1].get()),
                int(float(vars_[2].get())), float(vars_[3].get()),
                float(vars_[4].get() or 0))

    def _banner(text, bg, fg):
        if not text:
            banner.grid_remove()
            return
        banner.configure(bg=bg)
        banner_lb.configure(text=text, bg=bg, fg=fg)
        banner.grid(row=1, column=0, sticky="ew", padx=p(22), pady=(0, p(12)))

    def _badges(star_ok, cross_ok, cross_txt=""):
        b_star.configure(text="● 星形域通过" if star_ok else "● 非星形域",
                         fg=OK if star_ok else AMBER)
        if cross_ok:
            b_cross.configure(text="● 无自交", fg=OK)
        else:
            b_cross.configure(text="● %s" % (cross_txt or "自交"), fg=BAD)

    def draw(inf):
        cv.delete("all")
        W, H = cv.winfo_width(), cv.winfo_height()
        if W < p(20) or H < p(20):
            return
        r1 = inf["r1"]
        k = min((W - p(56)) / (2 * r1), (H - p(56)) / (2 * r1))
        cx, cy = W / 2.0, H / 2.0
        pts = []
        for ar in inf["arcs"]:
            th0 = math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0])
            dd = math.radians(ar["delta"])
            for t in range(121):
                th = th0 + ar["dir"] * dd * t / 120
                pts.append(cx + (ar["C"][0] + ar["r"] * math.cos(th)) * k)
                pts.append(cy - (ar["C"][1] + ar["r"] * math.sin(th)) * k)
        cv.create_polygon(pts, fill=FILL, outline=EDGE, width=max(1.6, S * 1.6))
        _bore = inf.get("bore") or 0.0
        if _bore > 0 and _bore < inf["inner"]:
            rb = _bore / 2.0
            cv.create_oval(cx - rb * k, cy - rb * k, cx + rb * k, cy + rb * k,
                           fill=CARD, outline=EDGE, width=max(1.6, S * 1.6))
        # 辅助圆：Tk 的 create_oval 不认 dash 长度（始终画它那套固定小虚线），
        # 所以用折线画圆，虚线长度才按设定生效
        for rr in (r1, inf["r2"]):
            ring = []
            seg = 720
            for q in range(seg + 1):
                th = 2.0 * math.pi * q / seg
                ring.append(cx + rr * k * math.cos(th))
                ring.append(cy - rr * k * math.sin(th))
            cv.create_line(ring, fill=AUX, width=max(1, S), dash=(p(22), p(11)))

    def _fill_stats(inf):
        if not inf:
            for lb in stat_lb.values():
                lb.configure(text="—", fg=FAINT)
            return
        for lb in stat_lb.values():
            lb.configure(fg=TEXT)
        stat_lb["R"].configure(text="%.6f" % inf["R"])
        stat_lb["a"].configure(text="%.6f" % inf["a"])
        stat_lb["b"].configure(text="%.6f" % inf["b"])
        stat_lb["crest"].configure(text="%.4f°" % inf["crest_span"])
        stat_lb["valley"].configure(text="%.4f°" % inf["valley_span"])
        stat_lb["mm"].configure(text="%.3f / %.3f" % (inf["rmax"], inf["rmin"]))

    def _fill_table(inf):
        for iid in tv.get_children():
            tv.delete(iid)
        if not inf:
            return
        for i, ar in enumerate(inf["arcs"]):
            kind = "嵴顶" if ar["kind"] == "crest" else "过渡"
            tv.insert("", "end", values=(
                "%s %d" % (kind, ar["j"]),
                "%8.4f" % ar["C"][0], "%8.4f" % ar["C"][1],
                "%7.3f" % ar["sDeg"], "%7.3f" % ar["eDeg"], "%7.3f" % ar["delta"],
            ), tags=("odd",) if i % 2 else ())

    def refresh(*_a):
        state["pending"] = None
        try:
            outer, inner, n, ph, bore = _params()
            inf = analyze(outer, inner, n, ph, bore)
        except Exception as ex:
            cv.delete("all")
            W, H = cv.winfo_width(), cv.winfo_height()
            if W > p(20) and H > p(20):
                cv.create_text(W / 2, H / 2, text="参数无效：%s" % ex,
                               fill=MUTED, font=UI)
            cap_var.set("")
            b_star.configure(text="● 星形域", fg=FAINT)
            b_cross.configure(text="● 无自交", fg=FAINT)
            _banner(str(ex), BAD_BG, BAD)
            _fill_stats(None)
            _fill_table(None)
            _dot(BAD)
            status.set("参数无效：%s" % ex)
            state["inf"] = None
            return
        state["inf"] = inf
        draw(inf)
        cap_var.set("φ%g × φ%g · %d 对极 · 相位 %g°"
                    % (inf["outer"], inf["inner"], inf["pairs"], inf["phase"]))
        _badges(bool(inf["star"]), not inf["crossing_count"], cross_text(inf))
        if inf["crossing_count"]:
            _banner("；".join(inf["warnings"]), BAD_BG, BAD)
        elif inf["warnings"]:
            _banner("；".join(inf["warnings"]), AMBER_BG, AMBER)
        else:
            _banner("", AMBER_BG, AMBER)
        _fill_stats(inf)
        _fill_table(inf)
        _dot(BAD if inf["crossing_count"] else (AMBER if inf["warnings"] else OK))
        status.set("实时预览：φ%g × φ%g · %d 对极 —— 点「生成 DXF」写出文件"
                   % (inf["outer"], inf["inner"], inf["pairs"]))

    def schedule(*_a):
        if state["pending"] is not None:
            try:
                root.after_cancel(state["pending"])
            except Exception:
                pass
        state["pending"] = root.after(120, refresh)

    for v in vars_:
        v.trace_add("write", schedule)

    def toggle_detail():
        state["detail"] = not state["detail"]
        if state["detail"]:
            detail_sep.grid(row=4, column=0, sticky="ew", padx=p(22))
            detail.grid(row=5, column=0, sticky="nsew", padx=p(22), pady=(p(12), p(18)))
            btn_detail.configure(text="收起")
        else:
            detail_sep.grid_remove()
            detail.grid_remove()
            btn_detail.configure(text="明细")

    def do():
        try:
            outer, inner, n, ph, bore = _params()
            inf = generate(outer, inner, n, ph,
                           out_name.get().strip() or None,
                           out_dir.get().strip() or None, svgv.get(), bore)
        except Exception as ex:
            messagebox.showerror("出错", str(ex))
            status.set("出错：" + str(ex))
            _dot(BAD)
            return
        state["inf"] = inf
        draw(inf)
        cap_var.set("φ%g × φ%g · %d 对极 · 相位 %g°"
                    % (inf["outer"], inf["inner"], inf["pairs"], inf["phase"]))
        _badges(bool(inf["star"]), not inf["crossing_count"], cross_text(inf))
        if inf["crossing_count"]:
            _banner("；".join(inf["warnings"]), BAD_BG, BAD)
        elif inf["warnings"]:
            _banner("；".join(inf["warnings"]), AMBER_BG, AMBER)
        else:
            _banner("", AMBER_BG, AMBER)
        _fill_stats(inf)
        _fill_table(inf)
        _dot(BAD if inf["crossing_count"] else (AMBER if inf["warnings"] else OK))
        status.set(("✓ 已写出 " if not inf["crossing_count"] else "⚠ 轮廓自交，仍已写出 ")
                   + inf["dxf"])

    btn_gen.configure(command=do)
    btn_open.configure(command=_open_dir)
    btn_detail.configure(command=toggle_detail)
    cv.bind("<Configure>", lambda e: (draw(state["inf"]) if state["inf"] else refresh()))
    root.bind("<Return>", lambda e: do())
    root.bind("<F5>", lambda e: refresh())
    root.after(80, refresh)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="波形转子等半径圆弧轮廓 DXF 生成器 v%s" % VERSION)
    ap.add_argument("-o", "--outer", type=float, help="外接圆直径 mm")
    ap.add_argument("-i", "--inner", type=float, help="内接圆直径 mm")
    ap.add_argument("-n", "--pairs", type=int, help="极对数（几对嵴）")
    ap.add_argument("--phase", type=float, default=0.0,
                    help="旋转角(度)，默认 0 = 极顶朝正上（左右对称），逆时针为正")
    ap.add_argument("--bore", type=float, default=0.0,
                    help="中心内径 mm（转子中孔，不填色，必须小于内接圆）")
    ap.add_argument("--name", help="文件名（不含扩展名）")
    ap.add_argument("--outdir", help="输出目录，默认桌面")
    ap.add_argument("--svg", action="store_true", help="同时输出 SVG 预览")
    ap.add_argument("--gui", action="store_true", help="打开图形界面")
    ap.add_argument("--version", action="store_true", help="打印版本号后退出")
    args = ap.parse_args()
    if args.version:
        print("波形转子 DXF 生成器 v%s" % VERSION)
        return
    if args.gui or len(sys.argv) == 1:
        run_gui()
        return
    run_cli(args)


if __name__ == "__main__":
    main()
