import colorsys, io, os, re

# Run from anywhere: paths resolve from this file, not the current folder.
CSS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'css')

BG = {'background', 'background-color', 'background-image'}
FG = {'color', 'fill', 'stroke', 'caret-color', 'accent-color', 'text-decoration-color'}
SHADOW = {'box-shadow', 'text-shadow'}
LINE = {'border', 'border-top', 'border-right', 'border-bottom', 'border-left', 'border-color',
        'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
        'outline', 'outline-color', 'column-rule', 'column-rule-color', 'scrollbar-color'}
COLOR_PROPS = BG | FG | SHADOW | LINE
HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')

def unpack(raw):
    body = raw[1:]
    if len(body) in (3, 4):
        body = ''.join(ch * 2 for ch in body)
    if len(body) not in (6, 8):
        return None
    alpha = body[6:8]
    r, g, b = (int(body[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b) + (alpha,)

def pack(hue, light, sat, alpha):
    r, g, b = colorsys.hls_to_rgb(hue, max(0.0, min(1.0, light)), max(0.0, min(1.0, sat)))
    return '#' + ''.join(format(max(0, min(255, round(v * 255))), '02x') for v in (r, g, b)) + alpha

def recolour(raw, kind):
    parts = unpack(raw)
    if parts is None:
        return raw
    hue, light, sat, alpha = parts
    if kind == 'shadow':
        # A glow would read as a mistake. Shadows stay shadows, alpha intact.
        return '#000000' + (alpha or '40')
    if kind == 'bg':
        # A surface that was already dark by design stays dark, only deeper.
        light = 0.09 + (1.0 - light) * 0.15 if light > 0.55 else light * 0.72
        sat = min(sat, 0.34)
    elif kind == 'fg':
        # Light text was already sitting on something dark; leave it alone.
        if light < 0.52:
            light = 1.0 - light * 0.72
        sat = min(sat, 0.62)
    else:
        light = 0.11 + (1.0 - light) * 0.42 if light > 0.5 else min(1.0, light + 0.20)
        sat = min(sat, 0.45)
    return pack(hue, light, sat, alpha)

def split_top(text, sep):
    out, depth, buf = [], 0, []
    for ch in text:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == sep and depth == 0:
            out.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append(''.join(buf))
    return out

def blocks(css):
    i, n, out = 0, len(css), []
    while i < n:
        j = css.find('{', i)
        if j < 0:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == '{':
                depth += 1
            elif css[k] == '}':
                depth -= 1
            k += 1
        out.append((prelude, css[j + 1:k - 1]))
        i = k
    return out

def scope(selector):
    stripped = selector.strip()
    if stripped in (':root', 'html', 'html:root'):
        return ':root[data-theme="dark"]'
    return ':root[data-theme="dark"] ' + stripped

def convert_rule(selector, body):
    kept = []
    for decl in split_top(body, ';'):
        if ':' not in decl:
            continue
        prop, _, value = decl.partition(':')
        name = prop.strip().lower()
        if name not in COLOR_PROPS or not HEX.search(value):
            continue
        kind = 'bg' if name in BG else 'fg' if name in FG else 'shadow' if name in SHADOW else 'line'
        new_value = HEX.sub(lambda m: recolour(m.group(0), kind), value)
        if new_value.strip() == value.strip():
            continue
        kept.append('%s:%s' % (name, new_value.strip()))
    if not kept:
        return ''
    scoped = ', '.join(scope(p) for p in split_top(selector, ',') if p.strip())
    return '%s { %s; }\n' % (scoped, '; '.join(kept))

def convert(css):
    out = []
    for prelude, body in blocks(css):
        low = prelude.lower()
        if low.startswith(('@media', '@supports', '@container')):
            inner = convert(body)
            if inner.strip():
                out.append('%s {\n%s}\n' % (prelude, inner))
        elif low.startswith('@'):
            continue
        else:
            out.append(convert_rule(prelude, body))
    return ''.join(out)

head = """/* Generated dark theme. Each rule mirrors one in the light stylesheets with
   its colours remapped by property type, scoped to data-theme="dark".
   Do not hand-edit: regenerate with tools/make_dark_theme.py */
:root[data-theme="dark"] { color-scheme: dark; }
:root[data-theme="dark"] body { background:#10151c; }
:root[data-theme="dark"] input, :root[data-theme="dark"] select, :root[data-theme="dark"] textarea { background:#19202b; color:#dfe6ef; border-color:#2b3442; }
:root[data-theme="dark"] input::placeholder, :root[data-theme="dark"] textarea::placeholder { color:#7d8794; }
:root[data-theme="dark"] ::-webkit-calendar-picker-indicator { filter:invert(.85); }
"""
parts = [head]
for name in ['workspace.css', 'planner.css', 'login.css', 'dashboard.css', 'groups.css']:
    css = re.sub(r'/\*.*?\*/', '', io.open(os.path.join(CSS_DIR, name), encoding='utf-8').read(), flags=re.S)
    parts.append('\n/* ---- from %s ---- */\n%s' % (name, convert(css)))
target = os.path.join(CSS_DIR, 'theme-dark.css')
io.open(target, 'w', encoding='utf-8').write(''.join(parts))
print(target, os.path.getsize(target), 'bytes')
