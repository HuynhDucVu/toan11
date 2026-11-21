from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class IntervalSpec:
    left: float | None
    right: float | None
    left_closed: bool = False
    right_closed: bool = False
    label_left: str = ""
    label_right: str = ""


def generate_function_graph_tikz(
    expr_tikz: str, xmin: float = -4, xmax: float = 4, ymin: float = -4, ymax: float = 4,
    asymptote_x: float | None = None, asymptote_y_expr: str | None = None,
    shade_integral: tuple[float, float] | None = None, samples: int = 120,
) -> str:
    lines = [
        r"\begin{tikzpicture}[scale=0.85,>=stealth,font=\footnotesize]",
        f"  \\draw[->] ({xmin},0)--({xmax},0) node[below]{{$x$}};",
        f"  \\draw[->] (0,{ymin})--(0,{ymax}) node[left]{{$y$}};",
        r"  \fill (0,0) circle (1.2pt) node[below left]{$O$};",
        f"  \\clip ({xmin + 0.1},{ymin + 0.1}) rectangle ({xmax - 0.1},{ymax - 0.1});",
    ]
    if shade_integral is not None:
        a, b = shade_integral
        lines.append(f"  \\fill[blue!20,opacity=0.6] ({a},0) -- plot[domain={a}:{b},samples=60] (\\x,{{{expr_tikz}}}) -- ({b},0) -- cycle;")
    if asymptote_x is not None:
        lines.append(f"  \\draw[dashed,red!70] ({asymptote_x},{ymin})--({asymptote_x},{ymax});")
        lines.append(f"  \\draw[thick,blue,smooth,samples={samples},domain={xmin}:{asymptote_x - 0.08}] plot(\\x,{{{expr_tikz}}});")
        lines.append(f"  \\draw[thick,blue,smooth,samples={samples},domain={asymptote_x + 0.08}:{xmax}] plot(\\x,{{{expr_tikz}}});")
    else:
        lines.append(f"  \\draw[thick,blue,smooth,samples={samples},domain={xmin}:{xmax}] plot(\\x,{{{expr_tikz}}});")
    if asymptote_y_expr:
        lines.append(f"  \\draw[dashed,red!70,domain={xmin}:{xmax}] plot(\\x,{{{asymptote_y_expr}}});")
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def generate_variation_table_tikz(x_values: Sequence[str], yprime_signs: Sequence[str], y_variation: Sequence[str], func_label: str = "y") -> str:
    return "\n".join([
        r"\begin{tikzpicture}",
        f"  \\tkzTabInit[nocadre=false,lgt=1.2,espcl=2.2,deltacl=0.6]{{$x$/0.7, ${func_label}'$/0.7, ${func_label}$/2.0}}{{{', '.join(x_values)}}}",
        f"  \\tkzTabLine{{{', '.join(yprime_signs)}}}",
        f"  \\tkzTabVar{{{', '.join(y_variation)}}}",
        r"\end{tikzpicture}",
    ])


def generate_number_line_tikz(intervals: Sequence[IntervalSpec], xmin: float = -5, xmax: float = 5) -> str:
    lines = [r"\begin{tikzpicture}[scale=0.9,>=stealth,font=\footnotesize]", f"  \\draw[thick,->] ({xmin},0)--({xmax},0);"]
    for iv in intervals:
        x1 = xmin + 0.3 if iv.left is None else iv.left
        x2 = xmax - 0.3 if iv.right is None else iv.right
        lines.append(f"  \\draw[line width=2.2pt,blue] ({x1},0)--({x2},0);")
        if iv.left is not None:
            brk = "[" if iv.left_closed else "("
            lines.append(f"  \\node[blue] at ({x1},0) {{$\\mathbf{{{brk}}}$}}; \\node[below=6pt] at ({x1},0) {{${iv.label_left or f'{iv.left:g}'}$}};")
        if iv.right is not None:
            brk = "]" if iv.right_closed else ")"
            lines.append(f"  \\node[blue] at ({x2},0) {{$\\mathbf{{{brk}}}$}}; \\node[below=6pt] at ({x2},0) {{${iv.label_right or f'{iv.right:g}'}$}};")
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def generate_linear_inequality_region_tikz(inequalities: Sequence[tuple[float, float, float, str]], xmin: float = -4, xmax: float = 5, ymin: float = -4, ymax: float = 5) -> str:
    lines = [
        r"\begin{tikzpicture}[scale=0.75,>=stealth,font=\footnotesize]",
        f"  \\draw[->] ({xmin},0)--({xmax},0) node[below]{{$x$}}; \\draw[->] (0,{ymin})--(0,{ymax}) node[left]{{$y$}};",
        f"  \\clip ({xmin},{ymin}) rectangle ({xmax},{ymax});",
    ]
    for a, b, c, op in inequalities:
        style = "dashed" if op in ("<", ">") else "thick"
        if abs(b) > 1e-9:
            y1, y2 = (c - a * xmin) / b, (c - a * xmax) / b
            ty = ymax if (b > 0 and op in ("<=", "<")) or (b < 0 and op in (">=", ">")) else ymin
            lines.append(f"  \\draw[{style},blue] ({xmin},{y1:.2f})--({xmax},{y2:.2f});")
            lines.append(f"  \\fill[pattern=north east lines,pattern color=gray!60,opacity=0.45] ({xmin},{y1:.2f})--({xmax},{y2:.2f})--({xmax},{ty})--({xmin},{ty})--cycle;")
        elif abs(a) > 1e-9:
            xv = c / a
            tx = xmax if (a > 0 and op in ("<=", "<")) or (a < 0 and op in (">=", ">")) else xmin
            lines.append(f"  \\draw[{style},blue] ({xv:.2f},{ymin})--({xv:.2f},{ymax});")
            lines.append(f"  \\fill[pattern=north east lines,pattern color=gray!60,opacity=0.45] ({xv:.2f},{ymin})--({xv:.2f},{ymax})--({tx},{ymax})--({tx},{ymin})--cycle;")
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def generate_solid_geometry_tikz(solid_type: str = "pyramid_sabcd_perp", height: float = 3.5, base_w: float = 4.2, depth_dx: float = -1.4, depth_dy: float = -1.3) -> str:
    if solid_type == "pyramid_sabcd_perp":
        return "\n".join([
            r"\begin{tikzpicture}[scale=0.85,line join=round,line cap=round,font=\footnotesize]",
            f"  \\coordinate (A) at (0,0); \\coordinate (B) at ({depth_dx},{depth_dy}); \\coordinate (D) at ({base_w},0);",
            f"  \\coordinate (C) at ($(B)+(D)-(A)$); \\coordinate (S) at (0,{height});",
            r"  \draw[dashed] (S)--(A)--(B) (A)--(D);",
            r"  \draw[thick] (S)--(B)--(C)--(D)--cycle (S)--(C);",
            r"  \foreach \p/\pos in {S/above,A/left,B/below left,C/below right,D/right}{\fill (\p) circle (1.3pt) node[\pos]{$\p$};}",
            r"\end{tikzpicture}",
        ])
    if solid_type == "pyramid_sabc_perp":
        return "\n".join([
            r"\begin{tikzpicture}[scale=0.85,line join=round,line cap=round,font=\footnotesize]",
            f"  \\coordinate (A) at (0,0); \\coordinate (B) at ({depth_dx + 2.6},{depth_dy}); \\coordinate (C) at ({base_w},0);",
            f"  \\coordinate (S) at (0,{height});",
            r"  \draw[dashed] (A)--(C); \draw[thick] (S)--(A)--(B)--(C)--cycle (S)--(B);",
            r"  \foreach \p/\pos in {S/above,A/left,B/below,C/right}{\fill (\p) circle (1.3pt) node[\pos]{$\p$};}",
            r"\end{tikzpicture}",
        ])
    if solid_type == "prism_triangular":
        return "\n".join([
            r"\begin{tikzpicture}[scale=0.85,line join=round,line cap=round,font=\footnotesize]",
            f"  \\coordinate (A) at (0,0); \\coordinate (B) at ({depth_dx + 2.5},{depth_dy}); \\coordinate (C) at ({base_w},0);",
            f"  \\coordinate (A') at (0,{height}); \\coordinate (B') at ($(B)+(0,{height})$); \\coordinate (C') at ($(C)+(0,{height})$);",
            r"  \draw[dashed] (A)--(C); \draw[thick] (A)--(B)--(C) (A')--(B')--(C')--cycle (A)--(A') (B)--(B') (C)--(C');",
            r"\end{tikzpicture}",
        ])
    raise ValueError(f"Khối chưa hỗ trợ: {solid_type}")
