"""Ultrawide Menus - world map patch.

Works on any panel_worldmap.redswf derived from the game's (vanilla 5.01, Smooth UI, Map Quest Insight, Map Redraw,
World Map Merger output, ...). Adds to MapMenu (the document class):

  uwApi:int = 1                 marker the script checks before calling uwSetUiPos
  uwOffL, uwOffR:Number = 0     how far the left / right side panels are currently moved (stage units)
  uwFitScreen()                 called from MapMenu.configUI right after super.configUI(), i.e. before the menu tells the
                                script it is ready (the script then sends SetMapSettings, which reads mcVisibleArea)
  uwSetUiPos(f:Number)          moves the side panels f (0..1) of the way to the screen edges; the script sends the
                                "Map side panels position" setting through it before the vanilla OnConfigUI body

uwFitScreen: at 16:9 or narrower (screen rect width <= 1922 stage units) it returns at once, nothing changes.
Wider, with L = screen rect x and W = screen rect width (3440x1440: L -330, W 2580; 5120x1440: L -960, W 3840):
  * root clip layer (1920 x 880 at x -2.25, clips the map containers)  -> x L, width W   (top/bottom untouched)
  * black backing under the map (1924.2 x 855 at x 0)                   -> x L-2, width W+4
  * edge-darkening frame (bitmap sprite 2930.5 x 1053.5 at x -524)      -> x L-524, width W+1010.5, so its left/right
    dark bands stay off-screen exactly as at 16:9 and only the top/bottom darkening shows
  * mcVisibleArea (tile loading + pin culling + user-pin panel bounds)   -> width W (stays centred on x 960)
  * mcMapHitArea (mouse drag / wheel)                                    -> width W+40 if it is narrower
  * mcPointersCanvas background (off-screen pin arrows)                  -> width W-20 (vanilla margins), then
    PinPointersManager.init(canvas) again so the arrows use the new edges
  * side panels to the screen edges (uwSetUiPos(1); the script then applies the setting)
  The three unnamed root objects are found by size and x, so a file that changed them is simply left alone.

uwSetUiPos: left panels (mapName = region name, mcHubMapPinPanel = filter list) move by L*f, right panels
(mcQTButtons, mcHubMapQuestTracker, mcWorldMapButton, and mcHubMap.mcHubMapPreviewAnchor which the minimap lines up
with when SetMapSettings runs) by (L+W-1920)*f. Moves are relative to the last call, so it can run more than once.
The filter list's own show/hide code (enableCategoryPanel, SetHubMapPinPanelVisibleWithAnim) sets x to 146 / -300;
uwOffL is added there.

Both new methods catch every exception and return, so a surprise in a modded file can never stop configUI.
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abcrt  # noqa: E402
import cr2w   # noqa: E402

API = 1
DEPOT = 'gameplay\\gui_new\\swf\\worldmap\\panel_worldmap.redswf'
BRANCHES = ('jump', 'iffalse', 'iftrue', 'ifngt', 'ifnlt', 'ifnge', 'ifnle', 'ifgt', 'iflt', 'ifge', 'ifle')
PANEL_SHOWN, PANEL_HIDDEN = 146, 0xFFFFFED4          # pushshort 146 / pushshort -300 in the filter list code


class PatchError(Exception):
    pass


class Ctx:
    def __init__(s, abc):
        s.abc = abc
        own = abc.owners()
        s.by = {}
        for k, v in own.items():
            s.by.setdefault(v, []).append(k)

    def body(s, owner):
        ms = s.by.get(owner, [])
        if len(ms) != 1:
            raise PatchError('%s: expected one method, found %d' % (owner, len(ms)))
        return s.abc.body_of[ms[0]]

    def cls(s, name, must_have=None):
        hits = [ci for ci, x in enumerate(s.abc.instances) if s.abc.mn(x['name']) == name and
                (must_have is None or any(s.abc.mn(t.name) == must_have for t in x['traits']))]
        if len(hits) != 1:
            raise PatchError('class %s: found %d' % (name, len(hits)))
        return hits[0]

    def trait_mn(s, traits, name, kinds=(0, 1)):
        for t in traits:
            if t.kind in kinds and s.abc.mn(t.name) == name:
                return t.name
        raise PatchError('member %s not found' % name)

    def used_mn(s, name, ops, full=None):
        """multiname index of an existing <op> <name> instruction (optionally with this full name)"""
        abc = s.abc
        for b in abc.bodies:
            for pos, op, args in abcrt.decode(b['code']):
                if abcrt.OPS[op][0] in ops and args and abc.mn(args[0]) == name and \
                        (full is None or (abc.mns[args[0]][0] == 0x07 and abc.mn(args[0], True) == full)):
                    return args[0]
        raise PatchError('no existing reference to %s' % name)

    def type_mn(s, tname):
        for x in s.abc.instances:
            for t in x['traits']:
                if t.kind == 0 and s.abc.mns[t.type_name][0] == 0x07 and s.abc.mn(t.type_name, True) == 'pkg:::' + tname:
                    return t.type_name
        raise PatchError('type %s not found' % tname)

    def double(s, v):
        raw = struct.pack('<d', v)
        for i, d in enumerate(s.abc.doubles):
            if i and d == raw:
                return i
        s.abc.doubles.append(raw)
        return len(s.abc.doubles) - 1

    def integer(s, v):
        if v not in s.abc.ints[1:]:
            s.abc.ints.append(v)
        return s.abc.ints.index(v, 1)

    def new_name(s, like_mn, text):
        m = s.abc.mns[like_mn]
        if m[0] != 0x07:
            raise PatchError('unexpected name kind')
        s.abc.strings.append(text.encode())
        s.abc.mns.append((0x07, m[1], len(s.abc.strings) - 1))
        return len(s.abc.mns) - 1


def assemble(src, prefix):
    """[(label|None, opname, args...)] -> abcrt instruction list; branch args are label names"""
    out = []
    for n, item in enumerate(src):
        lab, op, args = item[0], item[1], list(item[2:])
        if op in BRANCHES:
            args = [prefix + args[0]]
        out.append([prefix + (lab or 'i%d' % n), abcrt.NAME2OP[op], args])
    return out


def add_method(c, ci, mn_name, params, ret, src, max_stack, locals_, like_body, prefix):
    """new instance method; the whole body is guarded by a catch-all handler that just returns"""
    code = [[prefix + 'P0', abcrt.NAME2OP['getlocal0'], []], [prefix + 'P1', abcrt.NAME2OP['pushscope'], []]] + \
        assemble(src, prefix) + \
        [[prefix + 'CATCH', abcrt.NAME2OP['pop'], []], [prefix + 'CRET', abcrt.NAME2OP['returnvoid'], []]]
    enc, newpos = abcrt.encode(code)
    abc = c.abc
    abc.methods.append({'ret': ret, 'params': params, 'name': 0, 'flags': 0, 'options': None, 'pnames': None})
    mi = len(abc.methods) - 1
    exc = [[newpos[prefix + 'P0'], newpos[prefix + 'CATCH'], newpos[prefix + 'CATCH'], 0, 0]]
    abc.bodies.append({'method': mi, 'max_stack': max_stack + 1, 'locals': locals_,
                       'init_scope': like_body['init_scope'], 'max_scope': like_body['init_scope'] + 1,
                       'code': enc, 'exceptions': exc, 'traits': []})
    abc.body_of[mi] = abc.bodies[-1]
    t = abcrt.Trait()
    t.name, t.kind, t.attr, t.disp_id, t.method = mn_name, 1, 0, 0, mi
    abc.instances[ci]['traits'].append(t)
    return mi


def add_slot(c, ci, mn_name, mn_type, vindex, vkind):
    t = abcrt.Trait()
    t.name, t.kind, t.attr, t.slot_id = mn_name, 0, 0, 0
    t.type_name, t.vindex, t.vkind = mn_type, vindex, vkind
    c.abc.instances[ci]['traits'].append(t)


def in_range(loc, mn, lo, hi, miss, off=0):
    """lo < child.<mn> + off < hi, else jump to miss (off keeps every constant positive for pushshort)"""
    get = [(None, 'getlocal', loc), (None, 'getproperty', mn)] + \
        ([(None, 'pushshort', off), (None, 'add')] if off else [])
    return get + [(None, 'pushshort', lo), (None, 'ifngt', miss)] + \
        get + [(None, 'pushshort', hi), (None, 'ifnlt', miss)]


def move_x(holder, mn, delta_loc):
    """holder.<mn>.x += local <delta_loc>; holder = list of instructions that push the parent object"""
    return holder + [(None, 'getproperty', mn), (None, 'dup'), (None, 'getproperty', 'X'),
                     (None, 'getlocal', delta_loc), (None, 'add'), (None, 'setproperty', 'X')]


def patch_abc(abc):
    c = Ctx(abc)
    ci = c.cls('MapMenu')
    mtraits = abc.instances[ci]['traits']
    if any(abc.mn(t.name) == 'uwApi' for t in mtraits):
        raise PatchError('this map file already contains the ultrawide patch')

    # ---- names ----------------------------------------------------------------------------------------------------
    pub = lambda n, ops: c.used_mn(n, ops, 'pkg:::' + n)
    mn_x = pub('x', ('getproperty', 'setproperty'))
    mn_w = pub('width', ('getproperty', 'setproperty'))
    mn_h = pub('height', ('getproperty', 'setproperty'))
    mn_num = pub('numChildren', ('getproperty',))
    mn_gca = pub('getChildAt', ('callproperty',))
    mn_cu = c.used_mn('CommonUtils', ('getlex',))
    mn_gsr = c.used_mn('getScreenRect', ('callproperty',))
    M = {n: c.trait_mn(mtraits, n, (0,)) for n in ('mcVisibleArea', 'mcMapHitArea', 'mcPointersCanvas', 'mapName',
                                                   'mcHubMapPinPanel', 'mcQTButtons', 'mcHubMapQuestTracker',
                                                   'mcWorldMapButton', 'mcHubMap')}
    hci = c.cls('HubMap', 'mcHubMapPreviewAnchor')
    mn_anchor = c.trait_mn(abc.instances[hci]['traits'], 'mcHubMapPreviewAnchor', (0,))
    pci = c.cls('PinPointersManager')
    mn_gi = c.trait_mn(abc.classes[pci]['traits'], 'getInstance', (1,))
    mn_init = c.trait_mn(abc.instances[pci]['traits'], 'init', (1,))
    mn_ppm = abc.instances[pci]['name']
    like = next(t for t in mtraits if abc.mn(t.name) == 'SetMapSettings' and t.kind == 1)
    void = abc.methods[like.method]['ret']
    cfg = c.body('MapMenu::configUI')
    t_num, t_int = c.type_mn('Number'), c.type_mn('int')

    # ---- slots ----------------------------------------------------------------------------------------------------
    mn_api = c.new_name(like.name, 'uwApi')
    mn_offl = c.new_name(like.name, 'uwOffL')
    mn_offr = c.new_name(like.name, 'uwOffR')
    mn_fit = c.new_name(like.name, 'uwFitScreen')
    mn_pos = c.new_name(like.name, 'uwSetUiPos')
    add_slot(c, ci, mn_api, t_int, c.integer(API), 0x03)
    d0 = c.double(0.0)
    add_slot(c, ci, mn_offl, t_num, d0, 0x06)
    add_slot(c, ci, mn_offr, t_num, d0, 0x06)

    def fix_x(src):          # 'X' placeholder -> the public x name
        return [tuple(mn_x if a == 'X' else a for a in it) for it in src]

    # ---- uwSetUiPos(f) --------------------------------------------------------------------------------------------
    # locals: 1 f, 2 screen rect, 3 dl, 4 dr, 5 ddl, 6 ddr
    me = [(None, 'getlocal0')]
    hub = [(None, 'getlocal0'), (None, 'getproperty', M['mcHubMap'])]
    src = [
        (None, 'getlocal1'), (None, 'pushbyte', 0), (None, 'ifge', 'F1'),        # NaN / negative -> 0
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal1'),
        ('F1', 'getlocal1'), (None, 'pushbyte', 1), (None, 'ifngt', 'F2'),       # > 1 -> 1
        (None, 'pushbyte', 1), (None, 'convert_d'), (None, 'setlocal1'),
        ('F2', 'getlex', mn_cu), (None, 'callproperty', mn_gsr, 0), (None, 'coerce_a'), (None, 'setlocal2'),
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal3'),
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal', 4),
        (None, 'getlocal2'), (None, 'getproperty', mn_w), (None, 'pushshort', 1922), (None, 'ifngt', 'APPLY'),
        (None, 'getlocal2'), (None, 'getproperty', mn_x), (None, 'getlocal1'), (None, 'multiply'),
        (None, 'convert_d'), (None, 'setlocal3'),
        (None, 'getlocal2'), (None, 'getproperty', mn_x), (None, 'getlocal2'), (None, 'getproperty', mn_w),
        (None, 'add'), (None, 'pushshort', 1920), (None, 'subtract'), (None, 'getlocal1'), (None, 'multiply'),
        (None, 'convert_d'), (None, 'setlocal', 4),
        ('APPLY', 'getlocal3'), (None, 'getlocal0'), (None, 'getproperty', mn_offl), (None, 'subtract'),
        (None, 'convert_d'), (None, 'setlocal', 5),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'getproperty', mn_offr), (None, 'subtract'),
        (None, 'convert_d'), (None, 'setlocal', 6),
        (None, 'getlocal0'), (None, 'getlocal3'), (None, 'setproperty', mn_offl),
        (None, 'getlocal0'), (None, 'getlocal', 4), (None, 'setproperty', mn_offr),
        *move_x(me, M['mapName'], 5), *move_x(me, M['mcHubMapPinPanel'], 5),
        *move_x(me, M['mcQTButtons'], 6), *move_x(me, M['mcHubMapQuestTracker'], 6),
        *move_x(me, M['mcWorldMapButton'], 6), *move_x(hub, mn_anchor, 6),
        (None, 'returnvoid'),
    ]
    add_method(c, ci, mn_pos, [t_num], void, fix_x(src), 4, 7, cfg, 'uwp_')

    # ---- uwFitScreen() --------------------------------------------------------------------------------------------
    # locals: 1 screen rect, 2 L, 3 W, 4 child index, 5 child
    d_frame = c.double(1010.5)
    src = [
        (None, 'getlex', mn_cu), (None, 'callproperty', mn_gsr, 0), (None, 'coerce_a'), (None, 'setlocal1'),
        (None, 'getlocal1'), (None, 'getproperty', mn_x), (None, 'convert_d'), (None, 'setlocal2'),
        (None, 'getlocal1'), (None, 'getproperty', mn_w), (None, 'convert_d'), (None, 'setlocal3'),
        (None, 'getlocal3'), (None, 'pushshort', 1922), (None, 'ifngt', 'END'),
        (None, 'pushbyte', 0), (None, 'setlocal', 4),
        ('LOOP', 'label'),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'getproperty', mn_num), (None, 'ifnlt', 'AFTER'),
        (None, 'getlocal0'), (None, 'getlocal', 4), (None, 'callproperty', mn_gca, 1), (None, 'coerce_a'),
        (None, 'setlocal', 5),
        # clip layer 1920 wide at x -2.25 (x tests use +1000 so the constants stay positive). No height test: Map
        # Quest Insight's qmiFade may already have given it the full screen height (it changes only y/height, this
        # only x/width, so either order works)
        *in_range(5, mn_w, 1918, 1922, 'NOCLIP'),
        *in_range(5, mn_x, 996, 1000, 'NOCLIP', 1000),
        (None, 'getlocal', 5), (None, 'getlocal3'), (None, 'setproperty', mn_w),
        (None, 'getlocal', 5), (None, 'getlocal2'), (None, 'setproperty', mn_x),
        (None, 'jump', 'NEXT'),
        # black backing 1924.2 x 855 at x 0
        ('NOCLIP', 'nop'),
        *in_range(5, mn_w, 1921, 1927, 'NOBACK'), *in_range(5, mn_h, 852, 858, 'NOBACK'),
        *in_range(5, mn_x, 998, 1002, 'NOBACK', 1000),
        (None, 'getlocal', 5), (None, 'getlocal3'), (None, 'pushbyte', 4), (None, 'add'), (None, 'setproperty', mn_w),
        (None, 'getlocal', 5), (None, 'getlocal2'), (None, 'pushbyte', 2), (None, 'subtract'),
        (None, 'setproperty', mn_x),
        (None, 'jump', 'NEXT'),
        # edge-darkening frame 2930.5 x 1053.5 at x -524
        ('NOBACK', 'nop'),
        *in_range(5, mn_w, 2927, 2934, 'NEXT'), *in_range(5, mn_h, 1050, 1057, 'NEXT'),
        *in_range(5, mn_x, 474, 478, 'NEXT', 1000),
        (None, 'getlocal', 5), (None, 'getlocal3'), (None, 'pushdouble', d_frame), (None, 'add'),
        (None, 'setproperty', mn_w),
        (None, 'getlocal', 5), (None, 'getlocal2'), (None, 'pushshort', 524), (None, 'subtract'),
        (None, 'setproperty', mn_x),
        ('NEXT', 'inclocal_i', 4),
        (None, 'jump', 'LOOP'),
        ('AFTER', 'getlocal0'), (None, 'getproperty', M['mcVisibleArea']), (None, 'getlocal3'),
        (None, 'setproperty', mn_w),
        # mouse area: only ever grows
        (None, 'getlocal0'), (None, 'getproperty', M['mcMapHitArea']), (None, 'getproperty', mn_w),
        (None, 'getlocal3'), (None, 'pushbyte', 40), (None, 'add'), (None, 'ifnlt', 'PTR'),
        (None, 'getlocal0'), (None, 'getproperty', M['mcMapHitArea']), (None, 'getlocal3'), (None, 'pushbyte', 40),
        (None, 'add'), (None, 'setproperty', mn_w),
        # off-screen pin arrows
        ('PTR', 'getlocal0'), (None, 'getproperty', M['mcPointersCanvas']), (None, 'getproperty', mn_num),
        (None, 'pushbyte', 0), (None, 'ifngt', 'SIDES'),
        (None, 'getlocal0'), (None, 'getproperty', M['mcPointersCanvas']), (None, 'pushbyte', 0),
        (None, 'callproperty', mn_gca, 1),
        (None, 'getlocal3'), (None, 'pushbyte', 20), (None, 'subtract'), (None, 'setproperty', mn_w),
        (None, 'getlex', mn_ppm), (None, 'callproperty', mn_gi, 0), (None, 'getlocal0'),
        (None, 'getproperty', M['mcPointersCanvas']), (None, 'callpropvoid', mn_init, 1),
        # side panels to the screen edges until the script sends the setting
        ('SIDES', 'getlocal0'), (None, 'pushbyte', 1), (None, 'convert_d'), (None, 'callpropvoid', mn_pos, 1),
        ('END', 'returnvoid'),
    ]
    add_method(c, ci, mn_fit, [], void, src, 4, 6, cfg, 'uwf_')

    # ---- hook: MapMenu.configUI, right after super.configUI() -------------------------------------------------------
    ins = abcrt.decode(cfg['code'])
    k = next((i for i, (pos, op, args) in enumerate(ins[:8])
              if abcrt.OPS[op][0] == 'callsupervoid' and abc.mn(args[0]) == 'configUI'), None)
    if k is None:
        raise PatchError('MapMenu.configUI does not start with super.configUI()')
    out = ins[:k + 1] + [['uwh0', abcrt.NAME2OP['getlocal0'], []],
                         ['uwh1', abcrt.NAME2OP['callpropvoid'], [mn_fit, 0]]] + ins[k + 1:]
    cfg['code'], _ = abcrt.encode(out)
    cfg['max_stack'] = max(cfg['max_stack'], 1)

    # ---- filter list show/hide: add uwOffL to its fixed x positions ------------------------------------------------
    for owner in ('MapMenu::enableCategoryPanel', 'MapMenu::SetHubMapPinPanelVisibleWithAnim'):
        b = c.body(owner)
        ins = abcrt.decode(b['code'])
        out, n = [], 0
        for pos, op, args in ins:
            out.append([pos, op, args])
            if abcrt.OPS[op][0] == 'pushshort' and args[0] in (PANEL_SHOWN, PANEL_HIDDEN):
                out += [['uwo%d_%d' % (n, j), abcrt.NAME2OP[o], a] for j, (o, a) in
                        enumerate((('getlocal0', []), ('getproperty', [mn_offl]), ('add', [])))]
                n += 1
        if n != 2:
            raise PatchError('%s: expected 2 filter-list positions, found %d' % (owner, n))
        b['code'], _ = abcrt.encode(out)
        b['max_stack'] += 1
    return abc


def inflate_swf(cfx):
    import zlib
    if cfx[:3] in (b'FWS', b'GFX'):
        return b'FWS' + cfx[3:]
    declared = struct.unpack_from('<I', cfx, 4)[0]
    d = zlib.decompressobj()
    body = d.decompress(cfx[8:])
    if not d.eof and len(body) + 8 < declared:
        raise PatchError('map file is cut short')
    return b'FWS' + cfx[3:8] + body


def patch_redswf(orig):
    try:
        w = cr2w.CR2W(orig)
        pe, lo, bo, bl, tail = w.swf_layout()
        fws = inflate_swf(w.chunk_data(0)[bo:bo + bl])
        abcs = abcrt.swf_abcs(fws)
        if len(abcs) != 1:
            raise PatchError('expected 1 code block, found %d' % len(abcs))
        abc = patch_abc(abcrt.ABC(abcs[0][1]))
        new_abc = abc.serialize()
        abcrt.ABC(new_abc)
        out, _ = cr2w.rewrap(orig, abcrt.replace_abc(fws, new_abc))
    except PatchError:
        raise
    except (AssertionError, StopIteration, ValueError, KeyError, IndexError) as e:
        raise PatchError('the part of the map screen it changes is different in this file (%r)' % e)
    bad = [r for r in cr2w.checks(cr2w.CR2W(out)) if r[1] != r[2]]
    if bad:
        raise PatchError('container check failed: %s' % bad[0][0])
    return out


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    data = patch_redswf(open(src, 'rb').read())
    open(dst, 'wb').write(data)
    print('wrote', dst, len(data))
