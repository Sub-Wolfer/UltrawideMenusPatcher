"""Ultrawide Menus - blacksmith menu patch, version 3: the item grid grows BOTH ways. It reaches the left screen
edge, and everything right of it (action column, item / price panel, merchant panel) moves right by whole cells
while the grid grows right by the same amount. v3 changes only the section split: in Repair, Remove upgrade and
Add sockets the EQUIPPED section keeps vanilla's 4 columns and OTHER gets all the rest (it can hold at most about
six equipped items, each 1 cell wide); Dismantle (EQUIPMENT | OTHER) keeps the even split of v2.

Works on any panel_blacksmith.redswf derived from the game's 5.01 file (vanilla r4gui.bundle, Smooth UI Remastered:
identical layout code, only frame-script timings differ). ABC only: no SWF tag is touched. Every hook site is found
by pattern, never by offset, and a missing anchor raises PatchError. A file that already has the marker (any
version: v1 = v0.4, v2 = v0.5, v3) is refused. The same core (patch_abc / patch_redswf with a Spec) drives the
reforge (transmog) menu, see uw_tm_patch.py; its Spec has no fixed first section, so its code is v2's (only the
marker value is 3).

One SWF serves every BlacksmithMenu state: Repair, Sockets ("Remove upgrade"), Disassemble ("Dismantle"), AddSockets
(runewright) and the stand-alone mutagen dismantling table. They all share ONE grid module, mcPlayerGridModule
(RepairGrid -> ModuleBlacksmithGrid, at stage x 244.5, y 270.05), holding:
  mcPlayerGrid (ItemsGridRef = SlotsListGrid, x 4.75; RepairGrid.__setProp: 9 columns x 9 rows, 64-px cells)
  mcGridMask   (clip mask over the grid, local 0..695 x 0..641; renderBounds = its stage bounds)
  mcScrollBar  (x 584.25, visible = false and colour-transform alpha 0; over the last column's right 10 units)
  mcSectionTitlesAnchor (x 292.45; displaySection puts the titles/borders container at anchor.x - grid.width/2,
               grid.width = UIComponent._width = 576 from the 9 x 64 placeholder, never rewritten)
The two boxes the user sees ("EQUIPPED" | "OTHER", or "EQUIPMENT" | "OTHER" when dismantling) are the section
borders (GridSegmentationRef) that displaySection draws around the script's sections: the script
(blacksmithMenu.ws SetSectionsDataList) pushes id 0 = columns 0..3 and id 1 = columns 4..8 on every UpdateData
("blacksmith.grid.section" -> BlacksmithMenu.setSectionsList -> mcPlayerGrid.setItemSections (padding map +
clearRenderers) + displaySection), BEFORE the grid data ("repair.grid.player"). Stage at 16:9: grid 249.25..840.25
(4|5 columns, 15-px section gap), boxes 245.95..507.95 and 516.95..842.95.

Right of the grid block (frame lines end 852.16), all placed by the ONE-frame root timeline; no code writes their x
(BlacksmithMenu, BlacksmithItemPanel and its four subclasses, ModuleMerchantInfo only toggle visibility, set texts and
lay out their own children; checked in the decompiled code of both bases):
  d11 / d15  #378 mirrored, narrow: frames of the action column       859.10..1044.80 / 873.59..1027.30
  panelSockets / panelRepair / panelDisassemble / panelAddSocket (x 1082..1090): ONE sprite each holding the [E]
             button in the action column (local -160, stage ~928) AND the item / price block on the merchant side
             (bounds 879.6..1496.2)
  d6 #379    soft panel behind the merchant side (bitmap 374)       1053.10..1595.10
  d7 #378    mirrored merchant frame lines                          1051.79..1669.05  <- right-most panel (RIGHT_END)
  moduleMerchantInfo (1541.4: header 1063.2..1653.75), warningDisassemble (1355.7, text 993.65..1719.8),
  mcBkBlacksmith (1410.4, an empty sprite), mcBkSockets (1536.9: faint parchment picture, alpha 0.1, AddSockets
  only, 1154.9..1918.9, i.e. it reaches the 16:9 screen edge)

Width model (stage units; r = CommonUtils.getScreenRect(); decided once per menu instance, at the first section
push, i.e. after the uwMap.ws wrapper has set uwWide):
  gate: floor(-r.x / 64) >= 1 (a whole cell of side area), else NOTHING is written (16:9, 16:10, 4:3: vanilla)
  rx = r.x, x1 = r.x + r.width; default setting ("21:9", uwWide false; also when the script is missing): rx =
      max(rx, -330), x1 = min(x1, 2250): the 3440x1440 rect, centred, so every wider screen gets the 21:9 layout
  eL = clamp(floor((GL0 - GRID_MARGIN - rx) / 64), 0, MAX_E)   left columns: the grid's left end keeps at least
       GRID_MARGIN = 115.2 (the inventory's vanilla 2-section left margin) to the visible left edge;
       GL0 = mcPlayerGridModule.x + mcPlayerGrid.x read at run time (249.25)
  eR = clamp(floor((x1 - RIGHT_MARGIN - RIGHT_END) / 64), 0, MAX_E)   right columns: the right-most panel (merchant
       frame, right end RIGHT_END = 1669.05) keeps at least RIGHT_MARGIN = 110 to the visible right edge (the
       reforge's vanilla right margin, 1920 - 1810, beside its 115 left margin)
  MAX_E = 17. N = 9 + eL + eR, dL = 64*eL, S_R = 64*eR.
  3440x1440, 2560x1080 (5120x2160 DSR), every wider screen by default: eL 7, eR 7, N 23 (EQUIPPED | OTHER 4|19,
  Dismantle 12|11); 5120x1440 "32:9": 17 / 17, N 43 (4|39, 22|21); 2:1 2160x1080: 3 / 4, N 16 (4|12, 8|8).

Added to the document class (BlacksmithMenu):
  uwBsVersion:int = 3   marker; a file that already has it (any value) is refused
  uwWide:Boolean        set by the script (uwMap.ws, before the vanilla OnConfigUI body) from Options > Mods >
                        Ultrawide Menus > "Inventory and shop size" (the same setting as the inventory)
  uwCols:int = 9        N applied (9 = nothing applied)
  uwEL:int = 0, uwER:int = 0   eL / eR applied
  uwDone:Boolean        uwSetup has run (it runs once per menu instance)

  uwSections(arr)  hook target, first thing in setSectionsList (before the vanilla setItemSections /
                   displaySection). First call: uwDone = true, uwSetup(). Then, when uwCols > 9 and arr is not
                   null, uwSplit(arr). A tab switch (Repair -> Sockets ...) pushes new section objects through the
                   same path (uwSetup does not run again). If the script never pushes sections, nothing changes.
  uwSetup()        decides eL / eR (model above); returns with nothing changed unless the screen rect, the grid
                   module, its mcPlayerGrid (still 9 columns), mcGridMask and mcSectionTitlesAnchor exist. Then
                   (uwCols / uwEL / uwER committed first; all writes are plain property sets on checked objects):
    * mcPlayerGrid.columns = N; mcPlayerGrid.x -= dL           -> left end 249.25 - dL, right end 840.25 + S_R
    * mcSectionTitlesAnchor.x -= dL                            -> boxes keep vanilla's offset to the grid
    * mcScrollBar.x += S_R                                     -> stays over the last column's right 10 units
    * mcGridMask: width += dL + S_R, then x so its left bound moves by -dL (right end + S_R)
    * uwShift(S_R, RIGHT_X = 855, x1, module, null, mcBkSockets) -> the right block (own catch-all handler)
    * emptyListIcon.x, txtEmptyList.x += (S_R - dL)/2          -> the "no items" message stays centred on the grid
    * tooltipAnchor.x -= min(dL, -rx)                          -> the gamepad default tooltip anchor (111, 1109;
                                                                  ContextInfoManager reads its x/y each time a
                                                                  gamepad tooltip opens) keeps vanilla's 111 to the
                                                                  visible left edge (v1: -dL, with dL <= -rx then)
    * uwWiden(dL, S_R, window) for the frame art at the menu root (first child in each bounds window):
        - frame lines, sprite #378 at 234.9 (617.3 x 310; double side lines fading down + top line): left end
          -dL, right end +S_R (x-scale 2.45 at 21:9, 4.53 at the 32:9 setting). #378 carries a DefineScalingGrid
          (9-slice, x 17..596.95 of 615.2) with the 8-unit side textures in the fixed outer slices, so the side
          lines should keep vanilla's width and only the top line stretches. Vanilla relies on the same grid when
          it draws #378 at x-scales 0.25 / 0.30 for the action-column frames. (The inventory's stash frame #612 has
          no scaling grid; that one does get wider side lines.)
        - soft background panel, shape #375 at 308.9 (542 x 743, bitmap 374: a smooth dark gradient, alpha <= 0.2,
          no edge): left end -dL, right end +S_R (2.65x at 21:9; the stretch of a smooth gradient is invisible).
    * mcPlayerGrid.updateRendererBounds() with the menu at y 0 for the call (CoreMenu.showAnimation has it at
      500 while it slides in; renderBounds = gridMask.getBounds(stage) is cached and copied into every renderer
      spawned later, so the new columns draw). The vanilla setItemSections that follows clears the renderers;
      every later renderer is spawned with the new bounds.
  uwShift(sr, xs, x1, skip1, skip2, lim)  every root child, except skip1 / skip2, whose x is >= xs, or which is
                   not a DisplayObjectContainer and whose bounds' left edge (getBounds(this)) is >= xs, moves by
                   exactly sr (one amount for the whole block). Only lim (the blacksmith's mcBkSockets, null in the
                   reforge) is limited: never so far that its bounds' right end passes x1, and never left
                   (3440x1440: +331.1 instead of +448; it still ends at the visible edge as in vanilla). xs = 855
                   lies in the vanilla gap between the frame lines (852.16) and the action column (859.1); the
                   registration test catches the empty mcBkBlacksmith and the four item panels whatever their
                   run-time label width, the bounds test the absolute-coordinate soft panel d6 (a Shape at x 0).
                   Containers are never selected by their bounds: CoreMenu's run-time layers (_overlayCanvas =
                   tooltips, _dragCanvas, _blackBackground; Sprite / MovieClip at x 0, added before the first push)
                   stay put even if a tooltip were showing then (review 2 F3), without touching CoreMenu's
                   protected / private members. Runs once, before anything else is moved.
  uwSplit(arr)     rewrites start/end of the k non-null ItemSectionData of the pushed array (array order = id
                   order), contiguous from 0 to N-1:
                   - EQUIPPED | OTHER (v3): when k = 2, N > 9 and this._currentInfoPanel (private member, read by
                     the trait's own QName) is not null and is (strict identity) one of the three EQUIPPED panels,
                     this.panelRepair (Repair), this.panelSockets (Remove upgrade) or this.panelAddSocket
                     (runewright Add sockets): section 0 = columns 0..3 (vanilla's 4), section 1 = columns 4..N-1.
                     23: 4|19, 43: 4|39, 16: 4|12.
                   - otherwise even: floor(N/k) columns each, the first N mod k one more. Dismantle (panelDisassemble,
                     EQUIPMENT | OTHER) 23: 12|11, 43: 22|21, 16: 8|8; also a null info panel, any other panel (none
                     exists today; review 2 F1: a future fifth state keeps the even split) and any other section
                     count.
                   Vanilla 4|5 is untouched at 16:9 (uwSplit never runs there). The script decides which items go
                   into which section (sectionId per item); the split only sets the column ranges.
                   Timing: Flash BlacksmithMenu.setMenuState(state) sets _currentInfoPanel (panelAddSocket /
                   panelSockets / panelRepair / panelDisassemble). The script calls it before every section push:
                   on open, CR4MenuBase.OnConfigUI -> SetMenuState(default state) -> Flash setMenuState runs inside
                   super.OnConfigUI(), before CR4BlacksmithMenu.OnConfigUI's ApplyMenuState(m_menuState) pushes the
                   sections; on a tab switch, CR4BlacksmithMenu.SetMenuState -> super (Flash) -> ApplyMenuState ->
                   push. Later re-pushes (Repair all, OnGlobalUpdate) keep the state. Stateless otherwise: the
                   script's fresh objects on every push give the same result for the same state.
                   setMenuState never resets _currentInfoPanel to null (an unknown state leaves it as it was), so a
                   push that came before a changed state would use the previous tab's split; no script path does
                   that (bs_design.md 9.2).
                   Anchors (checked before anything is added): _currentInfoPanel and the four panels are own
                   traits of the class; setMenuState assigns each of the four panels to _currentInfoPanel exactly
                   once ("getlocal0; getproperty panel; initproperty|setproperty _currentInfoPanel").
  uwWiden(dl, dr, xl, xh, wl, wh, hl, hh)  the first root child whose bounds in menu space have xl < x < xh,
                   wl < width < wh, hl < height < hh: width += dl + dr, then x so its right end moves by dr (its
                   left end by -dl). NaN fails every test (nothing changed).

Hook in existing code (adds a call that returns at once while nothing applies):
  BlacksmithMenu.setSectionsList  right after the opening "getlocal0; pushscope": getlocal0, getlocal1,
                                  callpropvoid uwSections,1   (the method must contain exactly one setItemSections
                                  and one displaySection call)

Left alone on purpose: the bottom button bar (common menu), the one-time tutorial highlight rectangles (fixed
screen fractions in the script, tutorial baseState.ws: GetHighlightBlacksmithItems / Sockets / Price,
GetHighlightDismantleComponents / Cost; they frame the vanilla places, each shown once per save), the popups
(stage-centred). Mouse tooltips anchor to the slot (getGlobalSlotRect) and follow on their own: a single tooltip
opens at the slot's bottom-right as in vanilla (the right-most grid column ends at 1288 at 21:9); only comparison
pairs and the panel-side slots pass stage 1920 and flip left (vanilla's getPositionAfterScale).

Every new method catches every exception and returns, so a surprise in a modded file can never stop the section
update (the vanilla body still runs after the hook).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abcrt  # noqa: E402
import cr2w   # noqa: E402
from uw_map_patch import PatchError, Ctx, add_slot, inflate_swf  # noqa: E402
from uw_inv_patch import Names, new_method, patch_body, find_seq, late_mn, swf_of, lit, container_check  # noqa: E402,F401,E501

VERSION = 3
DEPOT = 'gameplay\\gui_new\\swf\\repair\\panel_blacksmith.redswf'
MAX_E = 17                 # extra columns per side, at most
CELL = 64                  # grid cell
VANILLA_COLS = 9
GRID_MARGIN = 115.2        # the grid's left end keeps at least this to the visible left edge
RIGHT_MARGIN = 110.0       # the right-most panel keeps at least this to the visible right edge
R21_X, R21_X1 = -330.0, 2250.0   # the 3440x1440 (21:9) rect: the default setting computes against it


class Spec:
    """what differs between the menus this core patches"""

    def __init__(s, label, cls, setter, module, marker, art, centred, depot, shifted=(), right_end=0.0,
                 right_x=0.0, geralt=None, limited=None, fixed_first=None):
        s.label, s.cls, s.setter, s.module, s.marker = label, cls, setter, module, marker
        s.art = art            # [(name, (x lo, x hi), (w lo, w hi), (h lo, h hi))] bounds windows in menu space
        s.centred = centred    # members moved by (S_R - dL)/2 (centred on the grid)
        s.shifted = list(shifted)  # members moved by -min(dL, -rx) (vanilla distance to the visible left edge)
        s.depot = depot
        s.right_end = right_end    # vanilla right end of the right-most panel (stage)
        s.right_x = right_x        # uwShift threshold: root children right of it move by S_R
        s.geralt = geralt          # None or (anchor member, renderer member, controller member, setup method)
        s.limited = limited        # None or the one right-block member moved only as far as it stays on screen
        # None (even split always), or (columns, state setter, current-panel member, the panels that get the fixed
        # first section, every panel the setter assigns): with 2 sections and N > 9, section 0 gets <columns> while
        # the current panel is one of the listed panels (review 2 F1: listed, not "all but Dismantle", so any other
        # panel keeps the even split)
        s.fixed_first = fixed_first


BLACKSMITH = Spec('blacksmith', 'BlacksmithMenu', 'setSectionsList', 'mcPlayerGridModule', 'uwBsVersion',
                  [('frame lines #378', (230, 240), (605, 630), (300, 320)),
                   ('soft panel #375', (303, 315), (535, 550), (735, 750))],
                  ['emptyListIcon', 'txtEmptyList'], DEPOT, shifted=['tooltipAnchor'],
                  right_end=1669.05, right_x=855.0, limited='mcBkSockets',
                  fixed_first=(4, 'setMenuState', '_currentInfoPanel', ('panelRepair', 'panelSockets', 'panelAddSocket'),
                               ('panelAddSocket', 'panelSockets', 'panelRepair', 'panelDisassemble')))


class SpecNames(Names):
    """Names with error messages that name the patched class"""

    def __init__(s, c, ci, cls):
        super().__init__(c, ci)
        s.cls = cls

    def new_trait(s, name):
        if name in s.own:
            raise PatchError('%s already has a member called %s' % (s.cls, name))
        return super().new_trait(name)

    def __getitem__(s, name):
        if name not in s.own:
            raise PatchError('%s.%s not found' % (s.cls, name))
        return s.own[name]


def patch_abc(abc, spec=BLACKSMITH):
    c = Ctx(abc)
    ci = c.cls(spec.cls, spec.setter)
    if any(abc.mn(t.name) == spec.marker for t in abc.instances[ci]['traits']):
        raise PatchError('this %s file already contains the ultrawide patch' % spec.label)
    nm = SpecNames(c, ci, spec.cls)
    P = nm.pub
    X, W, H, Y = P('x'), P('width'), P('height'), P('y')
    mn = lambda i: abc.mn(i)  # noqa: E731
    opn = lambda t: abcrt.OPS[t[1]][0]  # noqa: E731
    is_get = lambda name: lambda t: opn(t) == 'getproperty' and mn(t[2][0]) == name  # noqa: E731
    dbl = lambda v: c.double(float(v))  # noqa: E731

    # ---- anchors in existing code (checked before anything is added) ---------------------------------------------
    st = c.body('%s::%s' % (spec.cls, spec.setter))
    st_ins = abcrt.decode(st['code'])
    calls = [mn(a[0]) for p, op, a in st_ins if abcrt.OPS[op][0] == 'callpropvoid']
    if calls.count('setItemSections') != 1 or calls.count('displaySection') != 1:
        raise PatchError('%s.%s: expected one setItemSections and one displaySection call, found %s' %
                         (spec.cls, spec.setter, calls))
    open_ = find_seq(c, st_ins, [lambda t: opn(t) == 'getlocal0', lambda t: opn(t) == 'pushscope'])
    if not open_ or open_[0][0] > 2:
        raise PatchError('%s.%s does not start with getlocal0; pushscope' % (spec.cls, spec.setter))
    for need_ in [spec.module] + spec.centred + spec.shifted + ([spec.limited] if spec.limited else []):
        nm[need_]
    if spec.fixed_first:
        # the current info panel: a variable of the class itself (its own, private QName), assigned from each panel
        # in the state setter (the Flash side of the script's SetMenuState)
        f_cols, f_setter, f_cur, f_eq, f_panels = spec.fixed_first
        if (not f_eq or len(set(f_eq)) != len(f_eq) or not set(f_eq) < set(f_panels) or
                not 0 < f_cols < VANILLA_COLS):
            raise PatchError('internal: bad fixed_first %r' % (spec.fixed_first,))
        m_cur = nm[f_cur]
        m_eq = [nm[p] for p in f_eq]
        if next(t for t in abc.instances[ci]['traits'] if t.name == m_cur).kind != 0:
            raise PatchError('%s.%s is not a variable' % (spec.cls, f_cur))
        sm_ins = abcrt.decode(c.body('%s::%s' % (spec.cls, f_setter))['code'])
        for panel in f_panels:
            m_p = nm[panel]
            hit = find_seq(c, sm_ins, [lambda t: opn(t) == 'getlocal0',
                                       lambda t: opn(t) == 'getproperty' and abc.mns[t[2][0]] == abc.mns[m_p],
                                       lambda t: opn(t) in ('initproperty', 'setproperty') and
                                       abc.mns[t[2][0]] == abc.mns[m_cur]])
            if len(hit) != 1:
                raise PatchError('%s.%s: "%s = %s" found %d times, expected once' % (spec.cls, f_setter, f_cur, panel,
                                                                                    len(hit)))
    if spec.geralt:
        g_anchor, g_render, g_ctrl, g_setup = spec.geralt
        for need_ in (g_anchor, g_render, g_ctrl):
            nm[need_]
        gs_ins = abcrt.decode(c.body('%s::%s' % (spec.cls, g_setup))['code'])
        hit = find_seq(c, gs_ins, [is_get(g_anchor), is_get('x'),
                                   lambda t: lit(abc, t[1], t[2]) is not None,
                                   lambda t: opn(t) == 'callpropvoid' and mn(t[2][0]) == 'setDefaultAnchor'])
        if len(hit) != 1:
            raise PatchError('%s.%s: setDefaultAnchor(%s.x, y) not found' % (spec.cls, g_setup, g_anchor))
        anchor_y = lit(abc, gs_ins[hit[0][2]][1], gs_ins[hit[0][2]][2])
        if anchor_y != int(anchor_y) or not 0 <= anchor_y < 0x8000:
            raise PatchError('%s.%s: unexpected default anchor y %r' % (spec.cls, g_setup, anchor_y))
        m_set_default = gs_ins[hit[0][3]][2][0]

    # ---- names ---------------------------------------------------------------------------------------------------
    cu = c.used_mn('CommonUtils', ('getlex',))
    doc = c.used_mn('DisplayObjectContainer', ('getlex',), 'pkg:flash.display::DisplayObjectContainer')
    late = late_mn(c)
    mask_str = nm.str_idx('mcGridMask')
    t_int, t_bool = c.type_mn('int'), c.type_mn('Boolean')
    like = next(t for t in abc.instances[ci]['traits'] if mn(t.name) == spec.setter and t.kind == 1)
    void = abc.methods[like.method]['ret']

    # ---- slots ---------------------------------------------------------------------------------------------------
    S = {}
    add_slot(c, ci, nm.new_trait(spec.marker), t_int, c.integer(VERSION), 0x03)
    for s, v in (('uwCols', VANILLA_COLS), ('uwEL', 0), ('uwER', 0)):
        S[s] = nm.new_trait(s)
        add_slot(c, ci, S[s], t_int, c.integer(v), 0x03)
    for s in ('uwWide', 'uwDone'):
        S[s] = nm.new_trait(s)
        add_slot(c, ci, S[s], t_bool, 0x0A, 0x0A)
    m_sec, m_setup = nm.new_trait('uwSections'), nm.new_trait('uwSetup')
    m_split, m_widen = nm.new_trait('uwSplit'), nm.new_trait('uwWiden')
    m_shift = nm.new_trait('uwShift')
    m_geralt = nm.new_trait('uwGeralt') if spec.geralt else None

    # ---- small instruction helpers --------------------------------------------------------------------------------
    def need(loc, lab='END'):
        return [(None, 'getlocal', loc), (None, 'iffalse', lab)]

    def fetch(obj, member, loc):
        return [(None, 'getlocal', obj), (None, 'getproperty', member), (None, 'coerce_a'), (None, 'setlocal', loc)]

    def put(slot, *push):
        return [(None, 'getlocal0'), *push, (None, 'setproperty', S[slot])]

    def get(slot):
        return [(None, 'getlocal0'), (None, 'getproperty', S[slot])]

    def cells(push_value, dst, cap, lab, tmp):
        """dst = (v >= 1) ? min(int(v), cap) : 0 for the Number v the instructions push (NaN -> 0)"""
        return [*push_value, (None, 'setlocal', tmp),
                (None, 'pushbyte', 0), (None, 'setlocal', dst),
                (None, 'getlocal', tmp), (None, 'pushbyte', 1), (None, 'ifnge', lab),
                (None, 'getlocal', tmp), (None, 'convert_i'), (None, 'setlocal', dst),
                (None, 'getlocal', dst), (None, 'pushbyte', cap), (None, 'ifngt', lab),
                (None, 'pushbyte', cap), (None, 'setlocal', dst),
                (lab, 'nop')]

    def window(b, prop, lo, hi, miss):
        """lo < b.<prop> < hi (locals), else jump to miss; NaN jumps"""
        return [(None, 'getlocal', b), (None, 'getproperty', prop), (None, 'getlocal', lo), (None, 'ifngt', miss),
                (None, 'getlocal', b), (None, 'getproperty', prop), (None, 'getlocal', hi), (None, 'ifnlt', miss)]

    def addx(loc, *push):
        """<loc>.x += <pushed Number>"""
        return [(None, 'getlocal', loc), (None, 'getlocal', loc), (None, 'getproperty', X), *push, (None, 'add'),
                (None, 'setproperty', X)]

    # ---- uwSections(arr): hook target ------------------------------------------------------------------------------
    src = [
        *get('uwDone'), (None, 'iftrue', 'D'),
        *put('uwDone', (None, 'pushtrue')),
        (None, 'getlocal0'), (None, 'callpropvoid', m_setup, 0),
        ('D', 'getlocal0'), (None, 'getproperty', S['uwCols']), (None, 'pushbyte', VANILLA_COLS),
        (None, 'ifngt', 'END'),
        *need(1),
        (None, 'getlocal0'), (None, 'getlocal1'), (None, 'callpropvoid', m_split, 1),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_sec, [0], void, src, 3, 2, st, 'uwbs_')

    # ---- uwSetup(): decided once per menu ----------------------------------------------------------------------------
    # locals: 1 screen rect, 2 eL (first: gate), 3 scratch, 4 module, 5 grid, 6 mask, 7 titles anchor, 8 dL,
    #         9 mask bounds x, 10 object, 11 saved y, 12 rx, 13 x1, 14 eR, 15 S_R, 16 tooltip shift
    src = [
        (None, 'getlex', cu), (None, 'callproperty', P('getScreenRect'), 0), (None, 'coerce_a'), (None, 'setlocal', 1),
        *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', X), (None, 'convert_d'), (None, 'setlocal', 12),
        (None, 'getlocal', 12), (None, 'getlocal', 1), (None, 'getproperty', W), (None, 'add'), (None, 'convert_d'),
        (None, 'setlocal', 13),
        # gate: at least one whole cell of side area (16:9, 16:10, 4:3: nothing at all is written)
        *cells([(None, 'getlocal', 12), (None, 'negate'), (None, 'pushbyte', CELL), (None, 'divide')], 2, 1, 'G', 3),
        (None, 'getlocal', 2), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        # default setting: the 21:9 rect, centred
        *get('uwWide'), (None, 'iftrue', 'WD'),
        (None, 'getlocal', 12), (None, 'pushdouble', dbl(R21_X)), (None, 'ifnlt', 'W1'),
        (None, 'pushdouble', dbl(R21_X)), (None, 'setlocal', 12),
        ('W1', 'getlocal', 13), (None, 'pushdouble', dbl(R21_X1)), (None, 'ifngt', 'WD'),
        (None, 'pushdouble', dbl(R21_X1)), (None, 'setlocal', 13),
        ('WD', 'nop'),
        # everything needed must exist before anything is written
        *fetch(0, nm[spec.module], 4), *need(4),
        *fetch(4, P('mcPlayerGrid'), 5), *need(5),
        (None, 'getlocal', 5), (None, 'getproperty', P('columns')), (None, 'pushbyte', VANILLA_COLS),
        (None, 'equals'), (None, 'iffalse', 'END'),
        (None, 'getlocal', 4), (None, 'pushstring', mask_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 6), *need(6),
        *fetch(4, P('mcSectionTitlesAnchor'), 7), *need(7),
        # eL: the grid's left end (module x + grid x) keeps GRID_MARGIN to the visible left edge
        *cells([(None, 'getlocal', 4), (None, 'getproperty', X), (None, 'getlocal', 5), (None, 'getproperty', X),
                (None, 'add'), (None, 'pushdouble', dbl(GRID_MARGIN)), (None, 'subtract'),
                (None, 'getlocal', 12), (None, 'subtract'), (None, 'pushbyte', CELL), (None, 'divide')],
               2, MAX_E, 'EL', 3),
        # eR: the right-most panel's right end keeps RIGHT_MARGIN to the visible right edge
        *cells([(None, 'getlocal', 13), (None, 'pushdouble', dbl(RIGHT_MARGIN + spec.right_end)), (None, 'subtract'),
                (None, 'pushbyte', CELL), (None, 'divide')], 14, MAX_E, 'ER', 3),
        (None, 'getlocal', 2), (None, 'getlocal', 14), (None, 'add'), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        (None, 'getlocal', 2), (None, 'pushbyte', CELL), (None, 'multiply'), (None, 'convert_d'), (None, 'setlocal', 8),
        (None, 'getlocal', 14), (None, 'pushbyte', CELL), (None, 'multiply'), (None, 'convert_d'),
        (None, 'setlocal', 15),
        # commit
        *put('uwCols', (None, 'getlocal', 2), (None, 'getlocal', 14), (None, 'add'), (None, 'pushbyte', VANILLA_COLS),
             (None, 'add'), (None, 'convert_i')),
        *put('uwEL', (None, 'getlocal', 2)),
        *put('uwER', (None, 'getlocal', 14)),
        # grid: N columns, left end -dL, right end +S_R
        (None, 'getlocal', 5), *get('uwCols'), (None, 'setproperty', P('columns')),
        (None, 'getlocal', 5), (None, 'getlocal', 5), (None, 'getproperty', X), (None, 'getlocal', 8),
        (None, 'subtract'), (None, 'setproperty', X),
        # section titles / borders follow the grid's left end
        (None, 'getlocal', 7), (None, 'getlocal', 7), (None, 'getproperty', X), (None, 'getlocal', 8),
        (None, 'subtract'), (None, 'setproperty', X),
        # the (never visible) scrollbar keeps its place over the last column
        *fetch(4, P('mcScrollBar'), 10), *need(10, 'SB'), *addx(10, (None, 'getlocal', 15)),
        ('SB', 'nop'),
        # mask: left bound -dL, right end +S_R
        (None, 'getlocal', 6), (None, 'getlocal', 4), (None, 'callproperty', P('getBounds'), 1),
        (None, 'getproperty', X), (None, 'convert_d'), (None, 'setlocal', 9),
        (None, 'getlocal', 6), (None, 'getlocal', 6), (None, 'getproperty', W), (None, 'getlocal', 8), (None, 'add'),
        (None, 'getlocal', 15), (None, 'add'), (None, 'setproperty', W),
        (None, 'getlocal', 6),
        (None, 'getlocal', 6), (None, 'getproperty', X),
        (None, 'getlocal', 9), (None, 'getlocal', 8), (None, 'subtract'),
        (None, 'getlocal', 6), (None, 'getlocal', 4), (None, 'callproperty', P('getBounds'), 1),
        (None, 'getproperty', X), (None, 'subtract'),
        (None, 'add'), (None, 'setproperty', X),
        # everything right of the grid block moves by S_R (own catch-all handler)
        (None, 'getlocal0'), (None, 'getlocal', 15), (None, 'pushdouble', dbl(spec.right_x)), (None, 'getlocal', 13),
        (None, 'getlocal', 4),
        *([(None, 'getlocal0'), (None, 'getproperty', nm[spec.geralt[0]])] if spec.geralt else [(None, 'pushnull')]),
        *([(None, 'getlocal0'), (None, 'getproperty', nm[spec.limited])] if spec.limited else [(None, 'pushnull')]),
        (None, 'callpropvoid', m_shift, 6),
    ]
    if spec.geralt:
        # 3D Geralt (anchor, renderer, the controller's default anchor) by S_R (own catch-all handler)
        src += [(None, 'getlocal0'), (None, 'getlocal', 15), (None, 'callpropvoid', m_geralt, 1)]
    # objects centred on the grid: x += (S_R - dL)/2
    for k, member in enumerate(spec.centred):
        src += [*fetch(0, nm[member], 10), *need(10, 'C%d' % k),
                *addx(10, (None, 'getlocal', 15), (None, 'getlocal', 8), (None, 'subtract'), (None, 'pushbyte', 2),
                      (None, 'divide')),
                ('C%d' % k, 'nop')]
    # objects that keep vanilla's distance to the visible left edge (gamepad tooltip anchor): x -= min(dL, -rx)
    if spec.shifted:
        src += [(None, 'getlocal', 8), (None, 'setlocal', 16),
                (None, 'getlocal', 12), (None, 'negate'), (None, 'getlocal', 16), (None, 'ifnlt', 'TS'),
                (None, 'getlocal', 12), (None, 'negate'), (None, 'convert_d'), (None, 'setlocal', 16),
                ('TS', 'nop')]
    for k, member in enumerate(spec.shifted):
        src += [*fetch(0, nm[member], 10), *need(10, 'H%d' % k),
                (None, 'getlocal', 10), (None, 'getlocal', 10), (None, 'getproperty', X), (None, 'getlocal', 16),
                (None, 'subtract'), (None, 'setproperty', X),
                ('H%d' % k, 'nop')]
    # frame art at the menu root (own catch-all handler)
    for name, (xl, xh), (wl, wh), (hl, hh) in spec.art:
        src += [(None, 'getlocal0'), (None, 'getlocal', 8), (None, 'getlocal', 15)] + \
            [(None, 'pushdouble', dbl(v)) for v in (xl, xh, wl, wh, hl, hh)] + \
            [(None, 'callpropvoid', m_widen, 8)]
    src += [
        # draw bounds at the menu's resting y
        (None, 'getlocal0'), (None, 'getproperty', Y), (None, 'convert_d'), (None, 'setlocal', 11),
        (None, 'getlocal0'), (None, 'pushbyte', 0), (None, 'setproperty', Y),
        (None, 'getlocal', 5), (None, 'callpropvoid', P('updateRendererBounds'), 0),
        (None, 'getlocal0'), (None, 'getlocal', 11), (None, 'setproperty', Y),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_setup, [], void, src, 10, 17, st, 'uwsu_')

    # ---- uwSplit(arr): the column ranges (fixed first section, else even) -------------------------------------------
    # locals: 1 arr, 2 n, 3 k, 4 i, 5 section, 6 N, 7 q, 8 r, 9 j, 10 start; fixed_first: 11 fixed, 12 current panel
    fixed_check, fixed_loop = [], []
    if spec.fixed_first:
        # fixed = (k == 2 && N > 9 && this.<current panel> && (this.<current panel> === this.<listed panel 1> || ...))
        # The null test stays first: a missing (null) listed panel must not match a null current panel.
        fixed_check = [
            (None, 'pushfalse'), (None, 'setlocal', 11),
            (None, 'getlocal', 3), (None, 'pushbyte', 2), (None, 'equals'), (None, 'iffalse', 'FX'),
            (None, 'getlocal', 6), (None, 'pushbyte', VANILLA_COLS), (None, 'ifngt', 'FX'),
            (None, 'getlocal0'), (None, 'getproperty', m_cur), (None, 'coerce_a'), (None, 'setlocal', 12),
            *need(12, 'FX'),
        ]
        for i, m_p in enumerate(m_eq):
            last = i == len(m_eq) - 1
            fixed_check += [(None, 'getlocal', 12), (None, 'getlocal0'), (None, 'getproperty', m_p),
                            (None, 'strictequals'), (None, 'iffalse', 'FX') if last else (None, 'iftrue', 'FY')]
        fixed_check += [
            ('FY', 'pushtrue'), (None, 'setlocal', 11),
            ('FX', 'nop'),
        ]
        # the first non-null section (j 0): columns 0..f_cols-1; the second (j 1): f_cols..N-1
        fixed_loop = [
            (None, 'getlocal', 11), (None, 'iffalse', 'EV'),
            (None, 'getlocal', 9), (None, 'iftrue', 'F1'),
            (None, 'getlocal', 5), (None, 'pushbyte', 0), (None, 'setproperty', P('start')),
            (None, 'getlocal', 5), (None, 'pushbyte', f_cols - 1), (None, 'setproperty', P('end')),
            (None, 'jump', 'S2'),
            ('F1', 'getlocal', 5), (None, 'pushbyte', f_cols), (None, 'setproperty', P('start')),
            (None, 'getlocal', 5), (None, 'getlocal', 6), (None, 'pushbyte', 1), (None, 'subtract'),
            (None, 'setproperty', P('end')),
            (None, 'jump', 'S2'),
        ]
    src = [
        *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', P('length')), (None, 'convert_i'), (None, 'setlocal', 2),
        (None, 'pushbyte', 0), (None, 'setlocal', 3),
        (None, 'pushbyte', 0), (None, 'setlocal', 4),
        (None, 'jump', 'C1'),
        ('L1', 'label'),
        (None, 'getlocal', 1), (None, 'getlocal', 4), (None, 'getproperty', late), (None, 'coerce_a'),
        (None, 'setlocal', 5), *need(5, 'N1'),
        (None, 'inclocal_i', 3),
        ('N1', 'inclocal_i', 4),
        ('C1', 'getlocal', 4), (None, 'getlocal', 2), (None, 'iflt', 'L1'),
        (None, 'getlocal', 3), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        *get('uwCols'), (None, 'convert_i'), (None, 'setlocal', 6),
        *fixed_check,
        (None, 'getlocal', 6), (None, 'getlocal', 3), (None, 'divide'), (None, 'convert_i'), (None, 'setlocal', 7),
        (None, 'getlocal', 7), (None, 'pushbyte', 1), (None, 'ifnge', 'END'),
        (None, 'getlocal', 6), (None, 'getlocal', 7), (None, 'getlocal', 3), (None, 'multiply'), (None, 'subtract'),
        (None, 'convert_i'), (None, 'setlocal', 8),
        (None, 'pushbyte', 0), (None, 'setlocal', 9),
        (None, 'pushbyte', 0), (None, 'setlocal', 4),
        (None, 'jump', 'C2'),
        ('L2', 'label'),
        (None, 'getlocal', 1), (None, 'getlocal', 4), (None, 'getproperty', late), (None, 'coerce_a'),
        (None, 'setlocal', 5), *need(5, 'N2'),
        *fixed_loop,
        # even: start = j*q + min(j, r); width q, +1 while j < r
        ('EV' if spec.fixed_first else None, 'getlocal', 9), (None, 'getlocal', 7), (None, 'multiply'),
        (None, 'getlocal', 9), (None, 'add'),
        (None, 'convert_i'), (None, 'setlocal', 10),
        (None, 'getlocal', 9), (None, 'getlocal', 8), (None, 'iflt', 'S1'),
        (None, 'getlocal', 9), (None, 'getlocal', 7), (None, 'multiply'), (None, 'getlocal', 8), (None, 'add'),
        (None, 'convert_i'), (None, 'setlocal', 10),
        ('S1', 'getlocal', 5), (None, 'getlocal', 10), (None, 'setproperty', P('start')),
        (None, 'getlocal', 5), (None, 'getlocal', 10), (None, 'getlocal', 7), (None, 'add'), (None, 'pushbyte', 1),
        (None, 'subtract'), (None, 'setproperty', P('end')),
        (None, 'getlocal', 9), (None, 'getlocal', 8), (None, 'ifnlt', 'S2'),
        (None, 'getlocal', 5), (None, 'getlocal', 10), (None, 'getlocal', 7), (None, 'add'),
        (None, 'setproperty', P('end')),
        ('S2', 'inclocal_i', 9),
        ('N2', 'inclocal_i', 4),
        ('C2', 'getlocal', 4), (None, 'getlocal', 2), (None, 'iflt', 'L2'),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_split, [0], void, src, 5, 13 if spec.fixed_first else 11, st, 'uwsp_')

    # ---- uwWiden(dl, dr, xl, xh, wl, wh, hl, hh): first matching root child, left end -dl, right end +dr ---------
    # locals: 1 dl, 2 dr, 3..8 bounds window, 9 child count, 10 i, 11 child, 12 bounds, 13 new right end
    src = [
        (None, 'getlocal0'), (None, 'getproperty', P('numChildren')), (None, 'convert_i'), (None, 'setlocal', 9),
        (None, 'pushbyte', 0), (None, 'setlocal', 10),
        (None, 'jump', 'C'),
        ('L', 'label'),
        (None, 'getlocal0'), (None, 'getlocal', 10), (None, 'callproperty', P('getChildAt'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 11), *need(11, 'N'),
        (None, 'getlocal', 11), (None, 'getlocal0'), (None, 'callproperty', P('getBounds'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 12), *need(12, 'N'),
        *window(12, X, 3, 4, 'N'), *window(12, W, 5, 6, 'N'), *window(12, H, 7, 8, 'N'),
        (None, 'getlocal', 12), (None, 'getproperty', X), (None, 'getlocal', 12), (None, 'getproperty', W),
        (None, 'add'), (None, 'getlocal', 2), (None, 'add'), (None, 'convert_d'), (None, 'setlocal', 13),
        (None, 'getlocal', 11), (None, 'getlocal', 11), (None, 'getproperty', W), (None, 'getlocal', 1), (None, 'add'),
        (None, 'getlocal', 2), (None, 'add'), (None, 'setproperty', W),
        (None, 'getlocal', 11), (None, 'getlocal0'), (None, 'callproperty', P('getBounds'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 12), *need(12),
        (None, 'getlocal', 11),
        (None, 'getlocal', 11), (None, 'getproperty', X),
        (None, 'getlocal', 13), (None, 'getlocal', 12), (None, 'getproperty', X), (None, 'subtract'),
        (None, 'getlocal', 12), (None, 'getproperty', W), (None, 'subtract'),
        (None, 'add'), (None, 'setproperty', X),
        (None, 'jump', 'END'),
        ('N', 'inclocal_i', 10),
        ('C', 'getlocal', 10), (None, 'getlocal', 9), (None, 'iflt', 'L'),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_widen, [0] * 8, void, src, 5, 14, st, 'uwwd_')

    # ---- uwShift(sr, xs, x1, skip1, skip2, lim): the root children right of xs move by sr ---------------------------
    # locals: 1 sr, 2 xs, 3 x1, 4 skip1, 5 skip2, 6 lim, 7 child count, 8 i, 9 child, 10 bounds, 11 dx, 12 room
    src = [
        (None, 'getlocal0'), (None, 'getproperty', P('numChildren')), (None, 'convert_i'), (None, 'setlocal', 7),
        (None, 'pushbyte', 0), (None, 'setlocal', 8),
        (None, 'jump', 'C'),
        ('L', 'label'),
        (None, 'getlocal0'), (None, 'getlocal', 8), (None, 'callproperty', P('getChildAt'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 9), *need(9, 'N'),
        (None, 'getlocal', 9), (None, 'getlocal', 4), (None, 'strictequals'), (None, 'iftrue', 'N'),
        (None, 'getlocal', 9), (None, 'getlocal', 5), (None, 'strictequals'), (None, 'iftrue', 'N'),
        (None, 'getlocal', 9), (None, 'getlocal0'), (None, 'callproperty', P('getBounds'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 10), *need(10, 'N'),
        # right of xs: its registration x, or (plain art only: never a container such as CoreMenu's run-time
        # tooltip / drag / background layers at x 0, whose content can be anywhere) its bounds' left edge
        (None, 'getlocal', 9), (None, 'getproperty', X), (None, 'getlocal', 2), (None, 'ifge', 'IN'),
        (None, 'getlocal', 9), (None, 'getlex', doc), (None, 'istypelate'), (None, 'iftrue', 'N'),
        (None, 'getlocal', 10), (None, 'getproperty', X), (None, 'getlocal', 2), (None, 'ifnge', 'N'),
        # dx = sr for the whole block; only lim is limited so its bounds' right end stays inside x1, never negative
        ('IN', 'getlocal', 1), (None, 'convert_d'), (None, 'setlocal', 11),
        (None, 'getlocal', 9), (None, 'getlocal', 6), (None, 'strictequals'), (None, 'iffalse', 'M'),
        (None, 'getlocal', 3), (None, 'getlocal', 10), (None, 'getproperty', X), (None, 'subtract'),
        (None, 'getlocal', 10), (None, 'getproperty', W), (None, 'subtract'), (None, 'convert_d'),
        (None, 'setlocal', 12),
        (None, 'getlocal', 12), (None, 'getlocal', 11), (None, 'ifnlt', 'M'),
        (None, 'getlocal', 12), (None, 'setlocal', 11),
        (None, 'getlocal', 11), (None, 'pushbyte', 0), (None, 'ifnlt', 'M'),
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal', 11),
        ('M', 'nop'), *addx(9, (None, 'getlocal', 11)),
        ('N', 'inclocal_i', 8),
        ('C', 'getlocal', 8), (None, 'getlocal', 7), (None, 'iflt', 'L'),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_shift, [0] * 6, void, src, 4, 13, st, 'uwsh_')

    # ---- uwGeralt(sr): 3D model anchor + renderer + the controller's default anchor (reforge) ----------------------
    if spec.geralt:
        # locals: 1 sr, 2 anchor, 3 renderer, 4 controller
        src = [
            *fetch(0, nm[g_anchor], 2), *need(2),
            *addx(2, (None, 'getlocal', 1)),
            *fetch(0, nm[g_render], 3), *need(3, 'RC'),
            (None, 'getlocal', 3), (None, 'getlocal', 2), (None, 'getproperty', X), (None, 'setproperty', X),
            ('RC', 'nop'),
            *fetch(0, nm[g_ctrl], 4), *need(4),
            (None, 'getlocal', 4), (None, 'getlocal', 2), (None, 'getproperty', X), (None, 'pushshort', int(anchor_y)),
            (None, 'callpropvoid', m_set_default, 2),
            ('END', 'returnvoid'),
        ]
        new_method(c, ci, m_geralt, [0], void, src, 4, 5, st, 'uwge_')

    # ---- hook --------------------------------------------------------------------------------------------------------
    patch_body(st, {open_[0][1]: [('getlocal0', []), ('getlocal1', []), ('callpropvoid', [m_sec, 1])]}, 'uwh')
    return abc


def patch_redswf(orig, spec=BLACKSMITH, keep_input_table_crcs=False):
    """keep_input_table_crcs: only the public patcher (uw_inv_patch.container_check); default strict"""
    try:
        w = cr2w.CR2W(orig)
        pe, lo, bo, bl, tail = w.swf_layout()
        fws = inflate_swf(w.chunk_data(0)[bo:bo + bl])
        abcs = abcrt.swf_abcs(fws)
        if len(abcs) != 1:
            raise PatchError('expected 1 code block, found %d' % len(abcs))
        abc = patch_abc(abcrt.ABC(abcs[0][1]), spec)
        new_abc = abc.serialize()
        abcrt.ABC(new_abc)
        out, _ = cr2w.rewrap(orig, abcrt.replace_abc(fws, new_abc))
    except PatchError:
        raise
    except (AssertionError, StopIteration, ValueError, KeyError, IndexError) as e:
        raise PatchError('the part of the %s screen it changes is different in this file (%r)' % (spec.label, e))
    container_check(orig, out, keep_input_table_crcs)
    return out


def markers(redswf, spec=BLACKSMITH):
    """{name: value} of the marker slot on the document class"""
    abc = abcrt.ABC(abcrt.swf_abcs(swf_of(redswf))[0][1])
    ci = Ctx(abc).cls(spec.cls, spec.setter)
    out = {}
    for t in abc.instances[ci]['traits']:
        n = abc.mn(t.name)
        if n == spec.marker and t.kind == 0:
            out[n] = abc.const(t.vindex, t.vkind)
    return out


if __name__ == '__main__':
    src_, dst = sys.argv[1], sys.argv[2]
    data = patch_redswf(open(src_, 'rb').read())
    open(dst, 'wb').write(data)
    print('wrote', dst, len(data), 'md5', hashlib.md5(data).hexdigest())
