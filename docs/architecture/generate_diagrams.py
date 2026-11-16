#!/usr/bin/env python3
"""Generate the MXC/Claude Code solution architecture as SVG and draw.io from one model."""
from html import escape as h
from xml.sax.saxutils import quoteattr

W, H = 1500, 960
FONT = "Segoe UI, Helvetica, Arial, sans-serif"

STY = {  # fill, stroke, dashed, stroke-width
    "frame_host": ("#F7F9FC", "#5B6B7F", False, 1.5),
    "frame_net":  ("#F6F8F3", "#6B7F5B", False, 1.5),
    "actor":      ("#FFFFFF", "#334155", False, 1.5),
    "mxc":        ("#EEF2FF", "#4F46E5", False, 1.5),
    "proxy":      ("#FFF7ED", "#EA580C", False, 1.8),
    "enforce":    ("#E0E7FF", "#3730A3", False, 1.5),
    "container":  ("#FBFBFF", "#4F46E5", True, 2.0),
    "agent":      ("#FFFFFF", "#4F46E5", False, 2.4),
    "child":      ("#FFFFFF", "#64748B", False, 1.2),
    "rw":         ("#ECFDF5", "#059669", False, 1.5),
    "ro":         ("#EFF6FF", "#2563EB", False, 1.5),
    "deny":       ("#FEF2F2", "#DC2626", False, 1.5),
    "allow":      ("#ECFDF5", "#059669", False, 1.3),
    "optional":   ("#FFFFFF", "#059669", True, 1.3),
    "blocked":    ("#FEF2F2", "#DC2626", True, 1.3),
    "note":       ("#F8FAFC", "#94A3B8", False, 1.0),
}
EDGE = {  # color, dashed, width
    "flow": ("#334155", False, 1.5),
    "net": ("#EA580C", False, 1.8),
    "rw": ("#059669", False, 1.8),
    "ro": ("#2563EB", False, 1.8),
    "deny": ("#DC2626", True, 1.6),
}

# id, kind, x, y, w, h, lines, align ('c' or 'l'), title_pos ('mid' or 'top')
B = [
    ("host", "frame_host", 20, 70, 1070, 870, ["Developer workstation · Windows 11 24H2+"], "l", "top"),
    ("net", "frame_net", 1110, 70, 370, 870, ["Internet / corporate network", "reachable only if listed in allowlist.txt"], "l", "top"),

    ("dev", "actor", 45, 110, 190, 74, ["Developer", "PowerShell / Windows Terminal"], "c", "mid"),
    ("launch", "mxc", 275, 110, 230, 74, ["Start-ClaudeSandbox.ps1", "builds policy.json · env block", "starts proxy · runs wxc-exec"], "c", "mid"),
    ("wxc", "mxc", 545, 110, 200, 74, ["wxc-exec.exe", "MXC runner (@microsoft/mxc-sdk)", "--probe · Learn · Audit"], "c", "mid"),
    ("proxy", "proxy", 800, 110, 265, 90, ["egress-proxy.mjs", "127.0.0.1:18080 (host side)", "hostname allowlist · no TLS MITM", "every decision → egress.jsonl"], "c", "mid"),

    ("band", "enforce", 45, 234, 1020, 62, ["MXC enforcement layer  (Windows kernel / PSEC)",
        "AppContainer file ACLs · WFP filter: egress → proxy only",
        "job object: all child processes inherit · UI, clipboard, input off"], "l", "mid"),

    ("box", "container", 45, 320, 630, 330, ["MXC ProcessContainer (AppContainer, destroyOnExit)"], "l", "top"),
    ("agent", "agent", 75, 365, 280, 74, ["Claude Code (claude.exe)", "interactive TUI via shared console", "CLAUDE_CONFIG_DIR → sandbox state"], "c", "mid"),
    ("env", "note", 385, 365, 260, 74, ["Clean environment block", "no host env vars or tokens", "HTTP(S)_PROXY injected by MXC", "no git credential helper"], "c", "mid"),
    ("git", "child", 75, 475, 180, 66, ["Git Bash + git", "commits locally, no push creds"], "c", "mid"),
    ("mcp", "child", 270, 475, 185, 66, ["node / npx", "stdio MCP servers"], "c", "mid"),
    ("plug", "child", 470, 475, 175, 66, ["Plugins · skills · hooks", "installed in sandbox config"], "c", "mid"),
    ("tools", "child", 75, 562, 570, 58, ["Build & test tools", "dotnet, python, npm scripts …  (toolchains added read-only via -ExtraReadOnly)"], "c", "mid"),

    ("ws", "rw", 710, 330, 355, 62, ["Project workspace — read/write", "C:\\src\\<repo>  (incl. .git;  .env denied)"], "c", "mid"),
    ("state", "rw", 710, 405, 355, 92, ["Sandbox state — read/write, private", "%LOCALAPPDATA%\\agent-sandboxes\\<name>", "home · .claude (plugins, MCP, login) · tmp", "npm-cache · gitconfig · policy.json · logs"], "c", "mid"),
    ("ro", "ro", 710, 510, 355, 62, ["Host toolchain — read-only", "claude.exe · Git for Windows · Node.js · extras"], "c", "mid"),
    ("deny", "deny", 710, 585, 355, 72, ["User profile — no access", ".ssh  .azure  .aws  .kube  ·  host ~\\.claude", "Credential Manager · browser profiles"], "c", "mid"),

    ("tune", "note", 45, 690, 560, 96, ["Policy tuning loop",
        "-Mode Learn  →  enforce + record blocked access (denials.json)",
        "-Mode Audit  →  allow + record + Adjusted_*.json (trusted runs only)",
        "egress.jsonl denies  →  edit allowlist.txt (hot reload)"], "c", "mid"),
    ("human", "actor", 635, 690, 430, 96, ["Human in the loop", "reviews diff & local commits on the host",
        "⑦ git push with the developer's own credentials", "(the sandbox has none)"], "c", "mid"),

    ("steps", "note", 45, 808, 1020, 118, ["Flow",
        "①  Developer starts the launcher for a workspace          ②  Launcher starts the allowlisting egress proxy on loopback",
        "③  Launcher writes policy.json, checks it with wxc-exec --probe, runs wxc-exec          ④  MXC creates the ProcessContainer",
        "⑤  Claude Code and every child process get only the granted paths: workspace + private state (RW), toolchain (RO)",
        "⑥  No direct sockets: all HTTP(S) goes through the proxy, which only forwards to allowlisted hostnames          ⑦  Humans push"], "l", "mid"),

    ("api", "allow", 1135, 125, 325, 56, ["api.anthropic.com", "Claude API (model calls)"], "c", "mid"),
    ("login", "allow", 1135, 195, 325, 56, ["claude.ai · platform.claude.com", "OAuth /login (omit when using an API key)"], "c", "mid"),
    ("gh", "allow", 1135, 265, 325, 80, ["GitHub", "github.com · api.github.com · codeload", "raw/objects.githubusercontent.com", "git fetch · plugin marketplaces"], "c", "mid"),
    ("npm", "allow", 1135, 360, 325, 56, ["registry.npmjs.org", "npx MCP servers · npm install"], "c", "mid"),
    ("int", "optional", 1135, 430, 325, 62, ["Internal Git / Artifactory mirror", "recommended: allowlist only these"], "c", "mid"),
    ("blk", "blocked", 1135, 510, 325, 62, ["Everything else (incl. raw IPs)", "403 from proxy · logged as deny"], "c", "mid"),
    ("nr", "note", 1135, 600, 325, 80, ["Not reachable from the sandbox", "Docker Desktop · localhost databases", "IDE extension (localhost WebSocket)", "→ use MXC wslc backend if needed"], "c", "mid"),

    ("legend", "note", 1135, 700, 325, 160, ["Legend"], "l", "top"),
]

# kind, points, label, label_xy, label_anchor
E = [
    ("flow", [(235, 147), (275, 147)], "①", (255, 139), "middle"),
    ("flow", [(390, 110), (390, 88), (932, 88), (932, 110)], "② start proxy", (660, 88), "middle"),
    ("flow", [(505, 147), (545, 147)], "③", (525, 139), "middle"),
    ("flow", [(600, 184), (600, 320)], "④ create container per policy", (608, 218), "start"),
    ("net", [(650, 320), (650, 308), (932, 308), (932, 200)], "⑥ HTTP(S) only via proxy", (800, 308), "middle"),
    ("deny", [(120, 320), (120, 296)], "✕ direct sockets blocked (WFP)", (130, 310), "start"),
    ("flow", [(215, 439), (215, 457), (165, 457), (165, 475)], "", None, None),
    ("flow", [(215, 457), (362, 457), (362, 475)], "", None, None),
    ("flow", [(362, 457), (557, 457), (557, 475)], "", None, None),
    ("flow", [(165, 541), (165, 562)], "", None, None),
    ("rw", [(675, 361), (710, 361)], "⑤", (692, 354), "middle"),
    ("rw", [(675, 451), (710, 451)], "", None, None),
    ("ro", [(675, 541), (710, 541)], "", None, None),
    ("deny", [(675, 621), (710, 621)], "✕", (692, 614), "middle"),
    ("net", [(1065, 155), (1100, 155), (1100, 153), (1135, 153)], "", None, None),
    ("net", [(1100, 155), (1100, 223), (1135, 223)], "", None, None),
    ("net", [(1100, 223), (1100, 305), (1135, 305)], "", None, None),
    ("net", [(1100, 305), (1100, 388), (1135, 388)], "", None, None),
    ("net", [(1100, 388), (1100, 461), (1135, 461)], "", None, None),
    ("deny", [(1065, 188), (1112, 188), (1112, 541), (1135, 541)], "", None, None),
    ("flow", [(1065, 738), (1123, 738), (1123, 330), (1135, 330)], "⑦", (1094, 731), "middle"),
]

LEGEND = [("rw", "read/write access"), ("ro", "read-only access"), ("deny", "denied / blocked"),
          ("net", "network via egress proxy"), ("flow", "control flow")]

# ---------------------------------------------------------------- SVG
def svg():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         '<defs>']
    for k, (c, _, _) in EDGE.items():
        o.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                 f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    o.append('</defs>')
    o.append(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')
    o.append(f'<text x="20" y="36" font-size="20" font-weight="700" fill="#0F172A">Claude Code in a Microsoft Execution Containers (MXC) sandbox</text>')
    o.append(f'<text x="20" y="57" font-size="12" fill="#475569">Solution architecture · native Windows developer workstation · ProcessContainer backend with loopback egress proxy</text>')

    for bid, kind, x, y, w, hh, lines, align, tpos in B:
        fill, stroke, dashed, sw = STY[kind]
        da = ' stroke-dasharray="7 4"' if dashed else ''
        r = 12 if kind.startswith("frame") or kind == "container" else 8
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>')
        if tpos == "top":
            tx = x + 14
            o.append(f'<text x="{tx}" y="{y+22}" font-size="13" font-weight="700" fill="{stroke}">{h(lines[0])}</text>')
            for i, ln in enumerate(lines[1:]):
                o.append(f'<text x="{tx}" y="{y+39+i*14}" font-size="11" fill="#475569">{h(ln)}</text>')
            continue
        n = len(lines)
        total = 16 + 15 * (n - 1)
        ty = y + hh / 2 - total / 2 + 12
        tx, anchor = (x + w / 2, "middle") if align == "c" else (x + 16, "start")
        for i, ln in enumerate(lines):
            if i == 0:
                o.append(f'<text x="{tx}" y="{ty:.1f}" text-anchor="{anchor}" font-size="13" font-weight="700" fill="#0F172A">{h(ln)}</text>')
            else:
                o.append(f'<text x="{tx}" y="{ty+4+i*15:.1f}" text-anchor="{anchor}" font-size="11" fill="#334155">{h(ln)}</text>')

    for kind, pts, label, lxy, anc in E:
        c, dashed, sw = EDGE[kind]
        da = ' stroke-dasharray="6 4"' if dashed else ''
        d = "M" + " L".join(f"{px},{py}" for px, py in pts)
        mid_bus = kind == "flow" and label == "" and pts[0] in [(215, 457), (362, 457)]
        o.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}"{da} marker-end="url(#a-{kind})"/>')
    for kind, pts, label, lxy, anc in E:
        if not label:
            continue
        c = EDGE[kind][0]
        lx, ly = lxy
        est = len(label) * 6.3 + 10
        rx = lx - est / 2 if anc == "middle" else lx - 4
        o.append(f'<rect x="{rx:.1f}" y="{ly-11}" width="{est:.1f}" height="16" rx="3" fill="#FFFFFF" opacity="0.95"/>')
        o.append(f'<text x="{lx}" y="{ly+1}" text-anchor="{anc}" font-size="11" font-weight="600" fill="{c}">{h(label)}</text>')

    lx, ly = 1152, 745
    for i, (k, txt) in enumerate(LEGEND):
        c, dashed, sw = EDGE[k]
        da = ' stroke-dasharray="6 4"' if dashed else ''
        yy = ly + i * 22
        o.append(f'<path d="M{lx},{yy} L{lx+44},{yy}" stroke="{c}" stroke-width="{sw}"{da} marker-end="url(#a-{k})"/>')
        o.append(f'<text x="{lx+58}" y="{yy+4}" font-size="11" fill="#334155">{h(txt)}</text>')
    o.append('</svg>')
    return "\n".join(o)

# ---------------------------------------------------------------- draw.io
def drawio():
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    nid = [100]

    def new_id():
        nid[0] += 1
        return f"c{nid[0]}"

    def vertex(cid, value, style, x, y, w, hh):
        cells.append(f'<mxCell id="{cid}" value={quoteattr(value)} style="{style}" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{hh}" as="geometry"/></mxCell>')

    vertex("title", f'<b style="font-size:20px">Claude Code in a Microsoft Execution Containers (MXC) sandbox</b><br>'
                    f'<span style="color:#475569">Solution architecture · native Windows developer workstation · ProcessContainer backend with loopback egress proxy</span>',
           "text;html=1;align=left;verticalAlign=top;fontSize=12;fontColor=#0F172A;whiteSpace=wrap;", 20, 14, 1100, 50)

    for bid, kind, x, y, w, hh, lines, align, tpos in B:
        fill, stroke, dashed, sw = STY[kind]
        arc = 3 if kind.startswith("frame") or kind == "container" else 8
        st = (f"rounded=1;arcSize={arc};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
              f"strokeWidth={sw};fontFamily=Segoe UI;fontSize=11;fontColor=#334155;")
        if dashed:
            st += "dashed=1;dashPattern=7 4;"
        if tpos == "top":
            st += "verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;"
            val = f'<b style="font-size:13px;color:{stroke}">{h(lines[0])}</b>' + "".join(
                f'<br><span style="color:#475569">{h(l)}</span>' for l in lines[1:])
        else:
            st += "verticalAlign=middle;" + ("align=center;" if align == "c" else "align=left;spacingLeft=14;")
            val = f'<b style="font-size:13px;color:#0F172A">{h(lines[0])}</b>' + "".join(f"<br>{h(l)}" for l in lines[1:])
        vertex(bid, val, st, x, y, w, hh)

    def edge(kind, pts):
        c, dashed, sw = EDGE[kind]
        st = (f"html=1;edgeStyle=none;rounded=0;endArrow=block;endFill=1;endSize=7;strokeColor={c};strokeWidth={sw};")
        if dashed:
            st += "dashed=1;dashPattern=6 4;"
        (sx, sy), (tx, ty) = pts[0], pts[-1]
        mids = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts[1:-1])
        arr = f'<Array as="points">{mids}</Array>' if mids else ""
        cells.append(f'<mxCell id="{new_id()}" value="" style="{st}" edge="1" parent="1">'
                     f'<mxGeometry relative="1" as="geometry"><mxPoint x="{sx}" y="{sy}" as="sourcePoint"/>'
                     f'<mxPoint x="{tx}" y="{ty}" as="targetPoint"/>{arr}</mxGeometry></mxCell>')

    for kind, pts, label, lxy, anc in E:
        edge(kind, pts)
    for kind, pts, label, lxy, anc in E:
        if not label:
            continue
        c = EDGE[kind][0]
        lx, ly = lxy
        est = len(label) * 6.6 + 12
        x = lx - est / 2 if anc == "middle" else lx - 4
        vertex(new_id(), h(label),
               f"text;html=1;align={'center' if anc == 'middle' else 'left'};verticalAlign=middle;fontStyle=1;fontSize=11;"
               f"fontColor={c};labelBackgroundColor=#FFFFFF;fontFamily=Segoe UI;", round(x, 1), ly - 10, round(est, 1), 18)

    lx, ly = 1152, 745
    for i, (k, txt) in enumerate(LEGEND):
        yy = ly + i * 22
        edge(k, [(lx, yy), (lx + 44, yy)])
        vertex(new_id(), h(txt), "text;html=1;align=left;verticalAlign=middle;fontSize=11;fontColor=#334155;fontFamily=Segoe UI;",
               lx + 54, yy - 9, 230, 18)

    model = (f'<mxGraphModel dx="1500" dy="1020" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
             f'fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0"><root>'
             + "".join(cells) + "</root></mxGraphModel>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="app.diagrams.net" agent="Claude" version="24.7.17">'
            f'<diagram id="mxc-claude-code" name="MXC sandbox architecture">{model}</diagram></mxfile>\n')

if __name__ == "__main__":
    import sys
    out = sys.argv[1]
    open(f"{out}/claude-code-mxc-architecture.svg", "w", encoding="utf-8").write(svg())
    open(f"{out}/claude-code-mxc-architecture.drawio", "w", encoding="utf-8").write(drawio())
    print("ok")
