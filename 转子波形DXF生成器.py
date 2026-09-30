# -*- coding: utf-8 -*-
"""
波形转子（等半径圆弧）轮廓 DXF 生成器
=========================================
输入：外接圆直径、内接圆直径、中心内径（可选）、极对数 n
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

用法
----
  交互式：  py 转子波形DXF生成器.py
  命令行：  py 转子波形DXF生成器.py -o 64 -i 54 -n 3 --bore 20
  图形界面：py 转子波形DXF生成器.py --gui
常用参数：--phase 旋转角(度，默认0=极顶朝正上，逆时针为正)  --name 文件名  --outdir 输出目录  --svg 同时出 SVG
"""
import math
import os
import sys
import argparse
from pathlib import Path


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


def check_simple(arcs, per=160):
    """用「极角是否单调」判断轮廓是否自交（星形域判据）。"""
    pts = []
    for ar in arcs:
        th0 = math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0])
        d = math.radians(ar["delta"])
        for k in range(per + 1):
            th = th0 + ar["dir"] * d * k / per
            pts.append((ar["C"][0] + ar["r"] * math.cos(th),
                        ar["C"][1] + ar["r"] * math.sin(th)))
    prev, total = None, 0.0
    for x, y in pts:
        ang = math.atan2(y, x)
        if prev is None:
            prev = ang
            continue
        d = ang - prev
        while d <= -math.pi:
            d += 2 * math.pi
        while d > math.pi:
            d -= 2 * math.pi
        if d < -1e-9:
            return False, total
        total += d
        prev = ang
    return (total > 2 * math.pi - 1e-6), total


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
      0, "TABLE", 2, "LAYER", 70, 4)
    for name, color in (("0", 7), ("WAVE", 7), ("AUX", 8), ("BORE", 7)):
        a(0, "LAYER", 2, name, 70, 0, 62, color, 6, "CONTINUOUS")
    a(0, "ENDTAB", 0, "ENDSEC", 0, "SECTION", 2, "ENTITIES")
    for ar in arcs:
        a(0, "ARC", 8, "WAVE",
          10, fmt(ar["C"][0]), 20, fmt(ar["C"][1]), 30, "0.0",
          40, fmt(R), 50, fmt(ar["sDeg"]), 51, fmt(ar["eDeg"]))
    for rr in (r1, r2):
        a(0, "CIRCLE", 8, "AUX", 10, "0.0", 20, "0.0", 30, "0.0", 40, fmt(rr))
    if bore and bore > 0:
        a(0, "CIRCLE", 8, "BORE", 10, "0.0", 20, "0.0", 30, "0.0", 40, fmt(bore / 2.0))
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
    ok, total = check_simple(arcs)
    rmax, rmin = sample_extremes(R, arcs)
    folder = Path(outdir) if outdir else DEFAULT_OUTDIR
    folder.mkdir(parents=True, exist_ok=True)
    stem = name or ("波形转子_OD%s_ID%s" % ("%g" % outer, "%g" % inner))
    dxf_path = unique_path(folder, stem, ".dxf")
    dxf_path.write_text(dxf_text(R, arcs, r1, r2, bore), encoding="ascii")
    svg_path = None
    if want_svg:
        svg_path = unique_path(folder, stem, ".svg")
        svg_path.write_text(svg_text(R, arcs, r1, r2, bore), encoding="utf-8")
    crest = arcs[0]["delta"]
    valley = arcs[1]["delta"]
    info = {
        "outer": outer, "inner": inner, "pairs": int(pairs), "phase": phase, "bore": bore,
        "R": R, "a": a, "b": b,
        "crest_span": crest, "valley_span": valley,
        "rmax": rmax, "rmin": rmin,
        "junctions": [ar["src"] for ar in arcs],
        "simple": ok, "turn": math.degrees(total),
        "arcs": arcs, "dxf": str(dxf_path), "svg": str(svg_path) if svg_path else None,
    }
    return info


def print_report(info):
    print("=" * 62)
    _bore = info.get("bore") or 0.0
    print("  外接圆 φ%g   内接圆 φ%g   内径 %s   %d 对极   相位 %g°"
          % (info["outer"], info["inner"],
             ("φ%g" % _bore) if _bore > 0 else "无", info["pairs"], info["phase"]))
    print("-" * 62)
    print("  公共圆弧半径 R      = %.10f" % info["R"])
    print("  嵴顶弧圆心距中心 a  = %.10f" % info["a"])
    print("  过渡弧圆心距中心 b  = %.10f" % info["b"])
    print("  嵴顶弧包角          = %.6f°  (%d 段)" % (info["crest_span"], info["pairs"]))
    print("  过渡弧包角          = %.6f°  (%d 段)" % (info["valley_span"], info["pairs"]))
    print("  轮廓实测 rmax/rmin  = %.10f / %.10f" % (info["rmax"], info["rmin"]))
    print("  自交检查            = %s" % ("通过（星形，不自交）" if info["simple"] else "!! 不通过：轮廓自交"))
    print("  总转角              = %.6f°" % info["turn"])
    print("-" * 62)
    for ar in info["arcs"]:
        print("  %-6s@%3d  C=(%10.6f, %10.6f)  R=%.6f  起 %9.5f 止 %9.5f"
              % (("嵴顶" if ar["kind"] == "crest" else "过渡"), ar["j"],
                 ar["C"][0], ar["C"][1], ar["r"], ar["sDeg"], ar["eDeg"]))
    print("-" * 62)
    print("  已写出：%s" % info["dxf"])
    if info["svg"]:
        print("  已写出：%s" % info["svg"])
    if info["crest_span"] > 180.0:
        print("  注：嵴顶弧包角 > 180°，属深波形（局部倒扣），请确认工艺上可用。")
    if info["valley_span"] < 3.0:
        print("  注：过渡弧包角 < 3°，已接近尖角，注意刀具/电极圆角。")
    if not info["simple"]:
        print("  ⚠ 该组参数下轮廓会自交，实体不能直接用；请加大内径或减少极对数。")
    print("=" * 62)


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
    print("—— 波形转子 DXF 生成器（回车使用[]内默认值）——")
    if outer is None:
        outer = ask_float("外接圆直径 (mm)：")
    if inner is None:
        inner = ask_float("内接圆直径 (mm)：")
    if pairs is None:
        pairs = int(ask_float("极对数 n："))
    bore = 0.0
    if getattr(args, "bore", None) is None:
        b = input("中心内径 (mm，0 或直接回车 = 无中孔)：").strip()
        bore = float(b) if b else 0.0
    else:
        bore = float(args.bore or 0.0)
    info = generate(outer, inner, pairs, args.phase, args.name, args.outdir, args.svg, bore)
    print_report(info)
    return info


def run_gui():
    """图形界面：浅色工业风 —— 白底画布 + 淡蓝填充 #7AC0FF + 黑色描边，参数改动即时预览。"""
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    BG, PANEL, CANVAS = "#F0F0F0", "#FAFAFA", "#FFFFFF"
    FILL, OUTLINE, AUX = "#7AC0FF", "#000000", "#2A3B4D"
    GREEN, TEXT, MUTED = "#90EE90", "#1F1F1F", "#606060"
    BORDER = "#D6D9DC"
    UI = ("Microsoft YaHei UI", 11)
    MONO = ("Consolas", 11)

    root = tk.Tk()
    root.title("波形转子 DXF 生成器")
    for _n in ("波形转子.ico",):
        _ip = _resource_path(_n)
        if _ip:
            try:
                root.iconbitmap(default=_ip)
            except Exception:
                pass
            break
    root.configure(bg=BG)
    root.minsize(1100, 700)
    # 打开时居中于屏幕
    _W, _H = 1180, 740
    _sw, _sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry("%dx%d+%d+%d" % (_W, _H, max(0, (_sw - _W) // 2), max(0, (_sh - _H) // 2)))
    root.rowconfigure(1, weight=1)
    root.columnconfigure(0, weight=1)

    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure(".", background=BG, foreground=TEXT, font=UI)
    st.configure("TFrame", background=BG)
    st.configure("TEntry", fieldbackground="#FFFFFF", foreground=TEXT)
    st.configure("TButton", font=UI, padding=(10, 4))
    st.configure("Go.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(18, 7))

    # ---- 顶部工具条 ----
    bar = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
    bar.columnconfigure(11, weight=1)
    fields = [("外接圆 φ", "64"), ("内接圆 φ", "54"), ("极对数 n", "3"),
              ("相位 °", "0"), ("中心内径 φ", "35")]
    ents = []
    for i, (lab, dft) in enumerate(fields):
        tk.Label(bar, text=lab, bg=PANEL, fg=MUTED, font=UI).grid(
            row=0, column=i * 2, padx=(12 if i == 0 else 16, 5), pady=9)
        e = ttk.Entry(bar, width=8, justify="center")
        e.insert(0, dft)
        e.grid(row=0, column=i * 2 + 1, pady=9)
        ents.append(e)

    out_dir = tk.StringVar(value=str(DEFAULT_OUTDIR))
    out_name = tk.StringVar(value="")
    svgv = tk.BooleanVar(value=False)
    row2 = tk.Frame(bar, bg=PANEL)
    row2.grid(row=1, column=0, columnspan=11, sticky="w", pady=(0, 9))
    tk.Label(row2, text="输出目录", bg=PANEL, fg=MUTED, font=UI).grid(row=0, column=0, padx=(12, 5))
    ttk.Entry(row2, textvariable=out_dir, width=30).grid(row=0, column=1)
    ttk.Button(row2, text="浏览…", command=lambda: out_dir.set(filedialog.askdirectory() or out_dir.get())).grid(row=0, column=2, padx=6)
    tk.Label(row2, text="文件名", bg=PANEL, fg=MUTED, font=UI).grid(row=0, column=3, padx=(16, 5))
    ttk.Entry(row2, textvariable=out_name, width=14).grid(row=0, column=4)
    ttk.Checkbutton(row2, text="同时生成 SVG", variable=svgv).grid(row=0, column=5, padx=14)

    # ---- 主体：左信息栏 + 右画布 ----
    body = tk.Frame(root, bg=BG)
    body.grid(row=1, column=0, sticky="nsew", padx=10)
    body.rowconfigure(0, weight=1)
    body.columnconfigure(1, weight=1)

    left = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
    tk.Label(left, text="计算参数 / 结果", bg=PANEL, fg=MUTED, font=UI, anchor="w").pack(
        fill="x", padx=12, pady=(10, 6))
    info_box = tk.Text(left, width=44, height=20, bg="#FFFFFF", fg=TEXT, font=MONO,
                       relief="flat", highlightthickness=1, highlightbackground="#E2E4E6",
                       state="disabled", wrap="none")
    info_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    cv = tk.Canvas(body, bg=CANVAS, highlightthickness=1, highlightbackground=BORDER)
    cv.grid(row=0, column=1, sticky="nsew")

    # ---- 底部状态栏 + 绿色进度条 ----
    foot = tk.Frame(root, bg=BG)
    foot.grid(row=2, column=0, sticky="ew")
    prog = tk.Canvas(foot, height=6, bg="#E4E6E8", highlightthickness=0)
    prog.pack(fill="x", padx=10, pady=(8, 4))
    pbar = prog.create_rectangle(0, 0, 0, 6, fill=GREEN, width=0)
    status = tk.StringVar(value="就绪 —— 填好参数后点「生成 DXF」")
    tk.Label(foot, textvariable=status, bg=BG, fg=MUTED, font=UI, anchor="w").pack(
        fill="x", padx=10, pady=(0, 8))

    def draw_preview():
        cv.delete("all")
        W, H = cv.winfo_width(), cv.winfo_height()
        if W < 20 or H < 20:
            return
        try:
            o = float(ents[0].get())
            i2 = float(ents[1].get())
            n = int(float(ents[2].get()))
            ph = float(ents[3].get())
            if o <= i2 or i2 <= 0 or n < 2:
                raise ValueError
        except Exception:
            cv.create_text(W / 2, H / 2, text="参数无效", fill=MUTED, font=UI)
            return
        r1, r2 = o / 2.0, i2 / 2.0
        # 与 generate() 保持一致：对外 0° = 极顶朝正上（内部基准 +Y）
        _R, _a, _b, arcs = build_profile(r1, r2, n, ph + 90.0)
        k = min((W - 60.0) / (2 * r1), (H - 60.0) / (2 * r1))
        cx, cy = W / 2.0, H / 2.0
        pts = []
        for ar in arcs:
            th0 = math.atan2(ar["src"][1] - ar["C"][1], ar["src"][0] - ar["C"][0])
            dd = math.radians(ar["delta"])
            for t in range(121):
                th = th0 + ar["dir"] * dd * t / 120
                pts.append(cx + (ar["C"][0] + ar["r"] * math.cos(th)) * k)
                pts.append(cy - (ar["C"][1] + ar["r"] * math.sin(th)) * k)
        cv.create_polygon(pts, fill=FILL, outline=OUTLINE, width=1.6)
        # 中心内径：不填色，画成通孔（底色挖空 + 黑边）
        try:
            _bore = float(ents[4].get() or 0)
        except Exception:
            _bore = 0.0
        if _bore > 0 and _bore < i2:
            rb = _bore / 2.0
            cv.create_oval(cx - rb * k, cy - rb * k, cx + rb * k, cy + rb * k,
                           fill=CANVAS, outline=OUTLINE, width=1.6)
        # 内外切圆辅助线画在填充之上，否则内切圆会被填充遮住
        for rr in (r1, r2):
            cv.create_oval(cx - rr * k, cy - rr * k, cx + rr * k, cy + rr * k,
                           outline=AUX, dash=(5, 3), width=1.2)

    progress = {"v": 0.0}

    def redraw_progress():
        prog.coords(pbar, 0, 0, int(prog.winfo_width() * progress["v"]), 6)

    prog.bind("<Configure>", lambda e: redraw_progress())

    def fill_info(inf):
        _b = inf.get("bore") or 0.0
        lines = [
            "内径       = %s" % (("φ%g（中孔不填色）" % _b) if _b > 0 else "无中孔"),
            "R          = %.10f" % inf["R"],
            "a  嵴圆心  = %.10f" % inf["a"],
            "b  谷圆心  = %.10f" % inf["b"],
            "嵴顶弧包角 = %.6f°   (%d 段)" % (inf["crest_span"], inf["pairs"]),
            "过渡弧包角 = %.6f°   (%d 段)" % (inf["valley_span"], inf["pairs"]),
            "rmax/rmin  = %.8f / %.8f" % (inf["rmax"], inf["rmin"]),
            "自交检查   = %s" % ("通过（星形，不自交）" if inf["simple"] else "不通过：轮廓自交"),
            "",
        ]
        for ar in inf["arcs"]:
            lines.append("%s@%3d  C=(%9.5f,%9.5f)  %9.4f → %9.4f"
                         % ("嵴顶" if ar["kind"] == "crest" else "过渡", ar["j"],
                            ar["C"][0], ar["C"][1], ar["sDeg"], ar["eDeg"]))
        lines += ["", "已写出：" + inf["dxf"]]
        if inf["svg"]:
            lines.append("已写出：" + inf["svg"])
        info_box.configure(state="normal")
        info_box.delete("1.0", "end")
        info_box.insert("1.0", "\n".join(lines))
        info_box.configure(state="disabled")

    def do():
        progress["v"] = 0.0
        redraw_progress()
        try:
            _bore = float(ents[4].get() or 0)
            inf = generate(float(ents[0].get()), float(ents[1].get()),
                           int(float(ents[2].get())), float(ents[3].get()),
                           out_name.get().strip() or None,
                           out_dir.get().strip() or None, svgv.get(), _bore)
        except Exception as ex:
            messagebox.showerror("出错", str(ex))
            status.set("出错：" + str(ex))
            return
        fill_info(inf)
        draw_preview()
        progress["v"] = 1.0
        redraw_progress()
        status.set(("✓ 已写出 " if inf["simple"] else "⚠ 轮廓自交，仍已写出 ") + inf["dxf"])

    ttk.Button(bar, text="生成 DXF", style="Go.TButton", command=do).grid(
        row=0, column=11, rowspan=2, padx=16, sticky="e")
    cv.bind("<Configure>", lambda e: draw_preview())
    root.after(80, draw_preview)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="波形转子等半径圆弧轮廓 DXF 生成器")
    ap.add_argument("-o", "--outer", type=float, help="外接圆直径 mm")
    ap.add_argument("-i", "--inner", type=float, help="内接圆直径 mm")
    ap.add_argument("-n", "--pairs", type=int, help="极对数（几对嵴）")
    ap.add_argument("--phase", type=float, default=0.0, help="旋转角(度)，默认 0 = 极顶朝正上（左右对称），逆时针为正")
    ap.add_argument("--bore", type=float, default=0.0, help="中心内径 mm（转子中孔，不填色，必须小于内接圆）")
    ap.add_argument("--name", help="文件名（不含扩展名）")
    ap.add_argument("--outdir", help="输出目录，默认桌面")
    ap.add_argument("--svg", action="store_true", help="同时输出 SVG 预览")
    ap.add_argument("--gui", action="store_true", help="打开图形界面")
    args = ap.parse_args()
    if args.gui or len(sys.argv) == 1:
        run_gui()
        return
    run_cli(args)


if __name__ == "__main__":
    main()
