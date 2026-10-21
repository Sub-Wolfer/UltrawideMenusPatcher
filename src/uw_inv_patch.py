"""Ultrawide Menus - inventory patch, version 3 (per-mode layout, even sections, 21:9 / 32:9 width setting; v3: in
shop / container / stash the player grid reaches the left screen edge and the merchant / container grid grows right).

Works on any panel_inventory.redswf derived from the game's 5.01 file (vanilla, HoodSlots, Gear Compare output,
Hoods, Recent Loot Tab, Smooth UI). ABC only: no SWF tag is touched. Every hook site is found by pattern, never
by offset (HoodSlots and Gear Compare are recompiled), and a missing anchor raises PatchError. A file that already
has uwInvVersion (any version: v1, v2, v3) is refused.

Width model (stage units, Scaleform show-all on the 1920x1080 stage, r = CommonUtils.getScreenRect(),
x1 = r.x + r.width). Decided ONCE per menu instance, at the first setInventoryMode (the script has set uwWide by
then, see "Call order"):
  eL  = clamp(floor(-r.x / 64), 0, 15)               whole 64-px cells in the left side area
  eRs = clamp(floor((x1 - 1920) / 64), 0, 15)         whole cells in the right side area
  uwWide false (default, "21:9"; also when the script is missing): eL = min(eL, 5), eR = min(eRs, 5).
      This is the 21:9 layout; on wider screens it simply stays centred on the 16:9 core.
  uwWide true ("32:9"): eL as computed (up to 15). The pinned-crafting panel goes to the right screen edge
      (its right end PIN_EDGE = 24 from x1) when that is further right than its 21:9 place, and eR grows to the
      largest value whose paperdoll keeps the 8-px gap to the moved panel (PIN_CLEAR rule below), never above eRs.
      On 21:9 and narrower screens the panel's 21:9 place is already further right, so both settings give the
      identical layout. 5120x1440: eL 15, eR 9, panel module x 2371.45 (panel 2381.2..2856.05).
  Pinned panel shift pd = max(0, 64*eR - PIN_CLEAR) (eR 5: +34, as in v1); wide: max(that, x1 - 24 - 484.55 - x).
  eS (v3, shop / container / stash player grid extra columns): clamp(floor((SHOP_L - r.x) / 64), 0, MAX_S = 17),
      SHOP_L = 155: the grid keeps its vanilla right end (3 sections 868.7, 2 sections 861.2) and its 3-section left
      end 868.7 - (64N + 30) stays at least 107.7 (player mode's vanilla left margin) inside the screen. Default
      setting: at most SHOP_NARROW = 7, i.e. computed against the 21:9 rect (r.x -330). 3440x1440, 2560x1080 and
      every wider screen by default: 7 (16 columns); 5120x1440 "32:9": 17 (26); 2:1: 4 (13).
  eM (v3, merchant / container grid extra columns): the frame (right #612 of mcShopBackground, right end
      SHOP_R = 1642.42 at 8 columns, + 64*eM) stays SHOP_EDGE = 20 inside x1 (default setting: inside the 21:9
      rect's 2250) and, while the pinned panel's left edge (module x + pd + 9.75) is on screen, PIN_GAP = 8 left of
      it; clamp(.., 0, 15). The pinned panel is filled in shop instances only; the container (loot) branch is the
      same Flash code (setInventoryMode case 801) and gets the same rule. 3440x1440 / 2560x1080 / every wider screen
      by default: 7 (15 columns, frame to 2090.4, panel at 2116.2); 5120x1440 "32:9": 11 (19, panel 2381.2);
      2:1: 5 (13, panel off screen).
  Stash extra columns e2: the stash frame's right end (STASH_R = 1644.4 at 8 columns, + 64*e2) stays
      STASH_EDGE = 20 inside x1 (the pinned panel is only ever filled in shop instances, so it is no limit here),
      capped at STASH_NARROW = 8 unless "32:9" is on AND the right side area holds more than 5 cells (user's pick
      2026-10-21). 3440x1440 / 2560x1080 / 5120x1440 narrow, either setting on 21:9: 8 (16 columns);
      5120x1440 wide: 15 (23 columns).
  eL + eR = 0 (16:9, 16:10, 4:3): nothing is decided and nothing changes; every hook below adds 0 or returns.

Per mode (applied by uwLayout at the top of setInventoryMode, before vanilla positions anything):
  player (IMS_Player 0):          N = 9 + eL + eR, grid centre C = 32*(eR - eL), scrollbar +64*eR (both sides)
  shop 1 / container 2 / stash 4: N = 9 + eS, C = -32*eS, scrollbar +0: the grid grows LEFT ONLY, its right end,
                                  the module x (vanilla playerGridInitX + playerGridXOffset = 260) and everything
                                  right of it stay where vanilla puts them
  horse 3 (tab disabled by commonMenu.ws:236) and anything else: the current layout is kept, nothing changes.
  21:9: player 19, shop/container/stash 16 (merchant/container 15, stash 16); 5120x1440 default the same;
  5120x1440 "32:9": player 33, shop/container/stash 26 (merchant/container 19, stash 23).

Call order (checked in code; inv_selftest.py re-checks the createContainerGridModule / setInventoryMode part on
every base, original and patched):
  MenuInventory.configUI: super.configUI() (showAnimation: menu at y 500, tweening to 0 over 0.8 s) -> 11 sections
  -> mcPlayerInventory.setItemSections(L2) [hook: uwSecs = L2] -> initDataBindings -> dispatch 'OnConfigUI'.
  Script CR4InventoryMenu.OnConfigUI: the uwMap.ws wrapper sets uwWide BEFORE wrappedMethod(); the vanilla body then
  (setDefaultTab, PaperdollUpdateAll, ...) ends in ApplyMenuState -> SetInventoryState -> setInventoryMode(mode).
  setInventoryMode: _inventoryMode = mode [hook: uwLayout(mode)] -> case code positions the module, then
  (shop/container/stash) mcShopBackground / mcStashBackground.visible = true -> createContainerGridModule(mode):
  'if (!mcContainerGridModule)' { construct, mcPlayerGrid.ignoreValidationOpt = true [hook: uwCont(mode)],
  addChild, validateNow (configUI -> createInitRenderers from rows x columns), swapChildren } then active, x = 1046,
  y = 217, dropMode, dropEnabled. So uwCont runs once per menu, after uwSetup decided e2 / eM and before the grid
  builds its renderers or is placed. Then setTabData -> the tab list's first INDEX_CHANGE -> onTabListItemSelected
  -> mcPlayerGrid.setItemSections (updateColumnsPaddingMap + clearRenderers) -> data request -> populateData.
  Nothing selects a tab or populates the player grid before setTabData (the tab list has no data provider and no
  INDEX_CHANGE listener until setupTabData). The mode is fixed in OnConfigUI (_defaultInventoryState); later
  setInventoryMode calls come from commonMenu.ws:704 (sub-tab clicked again: same mode, uwLayout returns at once)
  or the disabled horse tab. The merchant header (moduleMerchantInfo) is filled later by the script
  (UpdateMerchantData -> setMerchantInfo -> populateData, which writes texts and visibility only).

Added to MenuInventory (the document class):
  uwInvVersion:int = 3   marker; a file that already has uwInvVersion is refused
  uwWide:Boolean = false  set by the script (Options > Mods > Ultrawide Menus > Inventory and shop size)
  uwCols:int = 9          player grid N currently applied (9 = nothing applied; Recent Loot Tab can read it)
  uwStashCols:int = 8     stash grid columns once widened
  uwShopCols:int = 8      merchant / container grid columns once widened (v3)
  uwReady:Boolean         widths decided (uwSetup ran past every check)
  uwKind:int = 0          layout currently applied: 0 none, 1 player, 2 shop/container/stash
  uwEL, uwER, uwE2, uwES, uwEM:int   eL, eR, e2, eS, eM as decided
  uwSecs:*                the GridTabSections configUI passed to mcPlayerInventory.setItemSections
  uwSR:Number             S_R = 64*eR (player cluster shift; paperdoll literal, player sort popup, tooltip anchor)
  uwC, uwSB:Number        grid-centre shift and scrollbar shift currently applied (module space)
  uwPD:Number             pinned panel shift applied
  uwCX0, uwTA0, uwTL0, uwMX0, uwMW0, uwMB0:Number  vanilla mcListContainer.x, mcSectionTitlesAnchor.x,
                          mcTabList.x, mask x / width / bounds x (none of them is written by vanilla code)
  uwTipX, uwRX, uwRW:Number  vanilla tooltipLeftAnchor.x; screen rect x / width

  uwLayout(mode)   kind = 1 for mode 0, 2 for modes 1/2/4, else return. Runs uwSetup once. Returns when uwKind
                   already equals kind (repeat call, no re-flow). L = eL, R = eR for kind 1; L = eS, R = 0 for kind 2.
                   Otherwise, every value written from the stored originals or as a difference to what is applied,
                   so it can run again for another mode:
    * uwKind, uwCols, uwC, uwSB committed first (the literal hooks then agree with whatever part got applied)
    * uwSplit(N); mcPlayerGrid.columns = N
    * mcListContainer.x = uwCX0 + C, mcSectionTitlesAnchor.x = uwTA0 + C, mcTabList.x = uwTL0 + C
      (grid, section titles/borders and the auto-aligned tabs are all centred on these)
    * mcTabBackground (null in the shipped InventoryGridRef): x += dC only while it is not inside mcListContainer
    * mcScrollbar: x += dSB - dC inside mcListContainer, x += dSB if not yet reparented (addToListContainer keeps
      the absolute position, so both configUI orders and a later reparent end at the same stage x)
    * mcGridMask: x = uwMX0, width = uwMW0 + 64*(L+R), then x moved so its left bound is uwMB0 - 64*L
    * forced re-flow when the grid was already populated with another count (currentlySelectedTabIndex >= 0;
      unreachable with the shipped scripts, see above): mcPlayerGrid.setItemSections(uwSecs.getTabSections(idx))
      (padding map + clearRenderers) and grid x = -(64N + 15(k-1))/2 as onTabListItemSelected does; vanilla's
      following setTabData -> updateSubData(current tab) re-requests the data. Section titles keep the old width
      until the next tab change.
    Draw bounds are refreshed by uwPlace, which every reachable case calls right after it sets the module x.
  uwSetup()        decides eL, eR, pd, e2, eS, eM (model above); returns with nothing changed unless the screen rect,
                   mcPlayerInventory, its mcPlayerGrid, mcListContainer, mcScrollbar, mcGridMask and uwSecs.sections
                   exist. Commits uwEL/uwER/uwSR/uwE2/uwES/uwEM/uwPD/uwRX/uwRW and the originals, sets uwReady, then
                   once per menu (these objects are shown in player mode only, the pinned panel in shop mode):
    * dropSlot, mcVitalityStat, mcToxicityStat, tooltipPaperdollAnchor, mcCharacterModelAnchor: x += S_R, then
      _rendererController.setDefaultAnchor(anchor.x, <y literal from <init>>) (the 'C' stats mode returns there)
    * pinnedCraftingModule.x += pd (narrow eR 5: +34; wide 5120x1440: +299). The paperdoll's right-column slot
      name / GC durability text reaches 1787.9 + 64*eR; the panel's left edge is its icon at module x + 9.75
      (2082.2 vanilla), its right end module x + 484.55. No code moves the panel (it only toggles visible; the
      shipped scripts fill it in shop instances only: inventoryMenu.ws OnConfigUI shop branch, BuyItem, SellItem,
      Full Refund), so this is the only write.
    * uwDim(r), uwShopMask() (own catch-all handlers)
    * uwHit(mcPanelGeneralStats, r.x - HIT_PAD, false), uwHit(mcPanelDetailedStats, x1 + HIT_PAD, true) (own
      catch-all handler; skipped for a base without these members)
  uwSplit(N)      even sections per tab: the k sections of one tab (array order = id order = column order) get
                   floor(N/k) columns each, the first N mod k one more, contiguous from 0. Stateless (only count and
                   order are read), so a second call for another N never compounds. 19: 10|9, 7|6|6; 16: 8|8,
                   6|5|5; 26: 13|13, 9|9|8; 33: 17|16, 11|11|11; 13: 7|6, 5|4|4. A single-section tab (Recent Loot
                   Tab's) gets all N. Never called at 16:9, so vanilla 4|5 etc. stay untouched there.
  uwCont(mode)     called by createContainerGridModule right after "ignoreValidationOpt = true" (see Call order).
                   e = e2 for stash (4), eM for shop (1) / container (2), else return; e > 0 and the vanilla
                   8-column ContainerGrid only, d = 64*e:
    * mcPlayerGrid.columns = 8 + e (grid 1086.7..1598.7 + d); no draw bounds needed (ignoreValidationOpt)
    * uwStashCols (stash) / uwShopCols (shop, container) = 8 + e
    * mcGridMask: width += d, x so its left bound stays; mcScrollBar.x += d
    * mcStateDropTarget (drag highlight, centred registration): width += d, x += d/2
    * stash: uwFrameBg(mcStashBackground, d, -300); shop / container: uwFrameBg(mcShopBackground, d, -506) and
      uwMerch(d)
  uwFrameBg(bg, d, x0)  widens the frame-lines sprite #612 of a background: the child with x0 < x < x0 + 10 and
                   600 < width < 640 gets width += d, i.e. it is scaled about its left edge: the top line spans the
                   wider grid, the right side lines move with the scrollbar, the 8-px side textures become
                   8*(618.2+d)/618.2 px (two 1-px lines become about 2 px; 15 columns: 13.9 px). The bitmap shapes
                   stay unscaled at their vanilla place (scaling them would visibly stretch the art):
      - mcStashBackground: #615 (chest illustration bitmap 614 + soft panel bitmap 607) stays; #612 at -296.7
        (stage 1026.2..1644.4) is widened.
      - mcShopBackground (#613 at 1525.55): #608 (one shape: both soft panels, bitmap 607 twice; the right copy is
        mirrored: alpha 0.20 at its left end (1040..1160), fading to <= 2/255 at its right end 1566.75, so the wider
        grid shows no edge there; the stash's #615 fades the same way to 1568.8; uw\dbg\r6\soft2.py), #610 divider,
        #612 at -1274.3 (left panel, sx 1.0195, masked by uwShopMask) stay; the right #612 at -501.35 (stage
        1024.2..1642.4) is widened.
  uwMerch(d)       merchant header (moduleMerchantInfo #536 at 1515.95, one frame, no code writes a child's x):
                   titleStroke (#529 = shape #528, ONE solid #45362d rectangle 590.5 x 75.5, alpha 151/256, no
                   bitmap; stage 1037.75..1628.25) width += d, only if its width is 580..600: the bar spans the wider
                   grid with vanilla's 14.2 to the frame's right end; txtLevelValue / txtType (merchant level, e.g.
                   "Grand Master" = _data.level / type, e.g. "BLACKSMITH"; right-aligned fields; the header has no
                   name field) x += d: their right ends keep vanilla's 24.7 / 23.7 to the bar's end; txtMoney
                   (right-aligned) and mcCoinIcon stay at the bar's left (969.7..1188). In container instances the
                   header is never filled (UpdateMerchantData needs _shopNpc), so nothing there is visible.
  uwDim(r)         mcSelectionMode.mcBackgroundHitTest ("select a slot" dimming, 1920 wide) -> x r.x, width r.width
  uwShopMask()     masks mcShopBackground with a sprite covering stage x >= 1000 (CDPR's createSolidColorSprite,
                   added at the bottom of the menu, mouse-disabled): the single bitmap shape holds both shop frames;
                   the player-side one (335..877) and the divider would sit under the wider player grid, the
                   merchant/container frame (1024..1642 + d) stays. Order addChildAt, then .mask = (as CDPR's
                   InputFeedbackButton.SpawnHoldAnimationMask). The mask reaches stage x 5000.
  uwHit(panel, t, right)  'C' stats mode (review2 F1). There the grid, paperdoll and stats only fade to alpha 0
                   (CharacterRendererController.fadeOutObj) and mcPlayerInventory.enabled = false clears only the
                   module's own mouseEnabled, so vanilla relies on the two stats panels (depth 640 / 643, above the
                   grid 169 and the paperdoll 434) to take the mouse: child 0 of each is a transparent full-height
                   hit shape (#305 x 1.5..1029.7, #293 856.9..1919; fill alpha 0, identical in all six bases). The
                   panels are visible only while the stats are up (visible = false in the leftInfoPanel /
                   rightInfoPanel setters and in onFadeInComplete), so the shapes change nothing at any other time.
                   On a wide screen the moved/extended parts (grid columns left of 1.5, paperdoll right column, toxicity
                   up to 2079.5 at 21:9) would stay live under them. uwHit widens child 0 outwards only, the general
                   panel's to start at r.x - HIT_PAD (right end kept), the detailed panel's to end at x1 + HIT_PAD
                   (left end kept): width scaled by the new / old bound width, then x corrected so the kept end stays
                   (getBounds(this) before and after; the ratio width / bounds width converts to parent units).
                   HIT_PAD 10 covers the panels' +-5 FADE_OUT_X_OFFSET slide. Only a child at least HIT_MIN_H high
                   and HIT_MIN_W wide is touched; a NaN or inward t changes nothing.
  uwPlace(player) called by setInventoryMode right after each "mcPlayerInventory.x = ..." (player: true, stash and
                   shop/container: false): tooltipLeftAnchor.x = uwTipX (+ uwSR in player mode); the sort popup's
                   own 1920-wide modal dimming -> x = uwRX - mcSortingMode.x, width = uwRW; then
                   mcPlayerGrid.updateRendererBounds() with the menu at y 0 for the call (showAnimation has it at
                   500; vanilla's own refresh there goes to the null mcSlotList).

Hooks in existing code (all add 0 / return while nothing is applied; unchanged since v2):
  configUI               after "callpropvoid setItemSections,1": getlocal0, getlocal<K>, setproperty uwSecs
  createPaperdollModule  <lit 856> (paperdoll x)                  -> + uwSR
  setInventoryMode       after "getlocal0; getlocal1; set/initproperty _inventoryMode": getlocal0, getlocal1,
                         callpropvoid uwLayout,1
                         <lit 314.75 / 500.65> (player sort buttons)        -> + uwC
                         <lit 422 / 608>, twice each (stash, shop/container) -> + uwC (= -32*eS there)
                         mcSortingMode.x = <lit 0> (player)                 -> + uwSR
                         (mcSortingMode.x = 170 in the other modes: vanilla, the grid's right end does not move)
                         after "x = playerGridInitX"                        -> uwPlace(true)
                         after "x = playerGridInitX + playerGridXOffset" x2 -> uwPlace(false)
  createContainerGridModule  after "pushtrue; setproperty ignoreValidationOpt": getlocal0, getlocal1,
                         callpropvoid uwCont,1

Left alone on purpose: the module highlight (gamepad-only LB/RB strip) of both grids, tooltipRightAnchor (no code
reads it), the selection-mode bar, the merchant money / coin, the soft panel bitmaps of both backgrounds, the 3D shop
paperdoll anchor (no code uses it), horse mode.

All new methods catch every exception and return, so a surprise in a modded file can never stop configUI,
setInventoryMode or createContainerGridModule.
"""
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abcrt  # noqa: E402
import cr2w   # noqa: E402
from uw_map_patch import PatchError, Ctx, add_method, add_slot, inflate_swf  # noqa: E402

VERSION = 3
DEPOT = 'gameplay\\gui_new\\swf\\inventory\\panel_inventory.redswf'
MAX_E = 15                 # extra columns per side, at most
NARROW = 5                 # per-side cap of the default ("21:9") setting
R21_X, R21_X1 = -330, 2250  # the 21:9 rect (3440x1440): the default setting lays wider screens out as if this were it
SHOP_L = 155               # shop/container/stash player grid: 3-section left end 868.7 - (64N + 30) >= r.x + 107.7
                           # (player mode's vanilla left margin), i.e. N - 9 <= (155 - r.x) / 64
MAX_S = 17                 # shop-side player grid extra columns, at most (32:9: 17 -> 26 columns)
SHOP_NARROW = (SHOP_L - R21_X) // 64   # = 7: default setting, computed against the 21:9 rect (16 columns)
SHOP_R = 1642.42           # merchant/container frame (right #612 of mcShopBackground) right end at 8 columns
                           # (1024.2 + 615.2 * 1.0049 = 1642.414, rounded up)
SHOP_EDGE = 20             # merchant/container frame right end at least this far inside the screen
SHOP_BG_X0 = -506          # the right #612 of mcShopBackground: local x in -506..-496 (vanilla -501.35)
STASH_BG_X0 = -300         # the #612 of mcStashBackground: local x in -300..-290 (vanilla -296.7)
TITLE_W = (580, 600)       # merchant header bar titleStroke (solid #45362d rectangle, 590.5 wide) width window
PIN_CLEAR = 286            # pinned shift needed for eR: 64*eR - 286 (1787.9 + 64*eR + 8 - 2082.2, rounded up)
PIN_L, PIN_R = 9.75, 484.55  # pinned panel's left / right end relative to its module x (2082.2 / 2557.0 vanilla)
PIN_EDGE = 24              # wide setting: pinned panel's right end this far inside the screen
PIN_GAP = 8                # stash frame right end at least this far left of the pinned panel
STASH_R = 1644.4           # stash frame (border strip #612) right end at 8 columns
STASH_EDGE = 20            # stash frame right end at least this far inside the screen
STASH_NARROW = 8           # stash extra columns at most, unless "32:9" on a screen wider than 21:9 (16-column stash)
SHOP_MASK_X = 1000         # shop background shows only x >= this (merchant frame starts at 1024)
HIT_PAD = 10               # stats-panel hit shapes reach this far past the screen edge (covers the +-5 slide)
HIT_MIN_H, HIT_MIN_W = 1000, 900   # only a full-height hit shape (#305 1028.2 x 1080, #293 1062.1 x 1080) is widened
DEBUG_OPS = {0xef, 0xf0, 0xf1}


def lit(abc, op, args):
    """numeric value of a push literal, else None"""
    n = abcrt.OPS[op][0]
    if n == 'pushbyte':
        return args[0] - 256 if args[0] > 127 else args[0]
    if n == 'pushshort':
        v = args[0] & 0xFFFF
        return v - 0x10000 if v & 0x8000 else v
    if n == 'pushint':
        return abc.ints[args[0]]
    if n == 'pushdouble':
        return struct.unpack('<d', abc.doubles[args[0]])[0]
    return None


class Names:
    """multinames: MenuInventory's own traits by their exact QName, everything else public"""

    def __init__(s, c, ci):
        s.c, s.abc = c, c.abc
        s.own = {s.abc.mn(t.name): t.name for t in s.abc.instances[ci]['traits']}
        x = c.used_mn('x', ('getproperty', 'setproperty'), 'pkg:::x')
        s.pub_ns = s.abc.mns[x][1]

    def str_idx(s, text):
        b = text.encode()
        try:
            return s.abc.strings.index(b, 1)
        except ValueError:
            s.abc.strings.append(b)
            return len(s.abc.strings) - 1

    def pub(s, name):
        abc = s.abc
        for i, m in enumerate(abc.mns):
            if i and m[0] == 0x07 and abc.str(m[2]) == name and abc.nsname(m[1]) == 'pkg:':
                return i
        abc.mns.append((0x07, s.pub_ns, s.str_idx(name)))
        return len(abc.mns) - 1

    def new_trait(s, name):
        if name in s.own:
            raise PatchError('MenuInventory already has a member called %s' % name)
        abc = s.abc
        abc.mns.append((0x07, s.pub_ns, s.str_idx(name)))
        s.own[name] = len(abc.mns) - 1
        return s.own[name]

    def __getitem__(s, name):
        if name not in s.own:
            raise PatchError('MenuInventory.%s not found' % name)
        return s.own[name]


def late_mn(c):
    """a MultinameL (array index access) the compiler already uses for arr[i]"""
    abc = c.abc
    for owner in ('GridTabSections::getTabSections', None):
        bodies = [c.body(owner)] if owner and len(c.by.get(owner, [])) == 1 else abc.bodies
        for b in bodies:
            for pos, op, args in abcrt.decode(b['code']):
                if abcrt.OPS[op][0] == 'getproperty' and abc.mns[args[0]][0] == 0x1B:
                    return args[0]
    raise PatchError('no array index access (MultinameL) found')


def real(ins):
    """indices of non-debug instructions"""
    return [i for i, (p, op, a) in enumerate(ins) if op not in DEBUG_OPS]


def patch_body(b, after, tag):
    """after: {instruction index: [(op, args), ...]} inserted right after that instruction; branches into the
    original code keep their targets, exception ranges are remapped"""
    ins = abcrt.decode(b['code'])
    out = []
    for i, it in enumerate(ins):
        out.append(it)
        for j, (op, a) in enumerate(after.get(i, ())):
            out.append(['%s_%d_%d' % (tag, i, j), abcrt.NAME2OP[op], list(a)])
    enc, newpos = abcrt.encode(out)
    end_old = len(b['code'])
    remap = lambda p: len(enc) if p == end_old else newpos[p]  # noqa: E731
    b['exceptions'] = [[remap(e[0]), remap(e[1]), remap(e[2]), e[3], e[4]] for e in b['exceptions']]
    b['code'] = enc
    b['max_stack'] += 2


def new_method(c, ci, mn_name, params, ret, src, max_stack, locals_, like_body, prefix):
    """add_method, after checking the labels: unique, and none of add_method's own (P0, P1, CATCH, CRET), which
    would move the catch-all range or a branch target"""
    labs = [it[0] for it in src if it[0]]
    dup = sorted({x for x in labs if labs.count(x) > 1} | (set(labs) & {'P0', 'P1', 'CATCH', 'CRET'}))
    if dup:
        raise PatchError('internal: label(s) %s reused in %s' % (', '.join(dup), prefix))
    return add_method(c, ci, mn_name, params, ret, src, max_stack, locals_, like_body, prefix)


def find_seq(c, ins, preds):
    """indices (into ins) of every run of non-debug instructions matching preds"""
    r = real(ins)
    hits = []
    for k in range(len(r) - len(preds) + 1):
        if all(p(ins[r[k + j]]) for j, p in enumerate(preds)):
            hits.append([r[k + j] for j in range(len(preds))])
    return hits


def patch_abc(abc):
    c = Ctx(abc)
    ci = c.cls('MenuInventory', 'setInventoryMode')
    if any(abc.mn(t.name) == 'uwInvVersion' for t in abc.instances[ci]['traits']):
        raise PatchError('this inventory file already contains the ultrawide patch')
    nm = Names(c, ci)
    P = nm.pub
    X, W, Y = P('x'), P('width'), P('y')
    mn = lambda i: abc.mn(i)  # noqa: E731
    opn = lambda t: abcrt.OPS[t[1]][0]  # noqa: E731
    is_get = lambda name: lambda t: opn(t) == 'getproperty' and mn(t[2][0]) == name  # noqa: E731
    set_x = lambda t: opn(t) == 'setproperty' and mn(t[2][0]) == 'x'  # noqa: E731

    # ---- anchors in existing code (checked before anything is added) ---------------------------------------------
    cfg = c.body('MenuInventory::configUI')
    cfg_ins = abcrt.decode(cfg['code'])
    sis = [i for i, (p, op, a) in enumerate(cfg_ins)
           if abcrt.OPS[op][0] == 'callpropvoid' and mn(a[0]) == 'setItemSections']
    if len(sis) != 1:
        raise PatchError('MenuInventory.configUI: expected one setItemSections call, found %d' % len(sis))
    r_cfg = real(cfg_ins)
    prev = cfg_ins[r_cfg[r_cfg.index(sis[0]) - 1]]
    pn = abcrt.OPS[prev[1]][0]
    if pn in ('getlocal0', 'getlocal1', 'getlocal2', 'getlocal3'):
        sect_reg = int(pn[-1])
    elif pn == 'getlocal':
        sect_reg = prev[2][0]
    else:
        raise PatchError('MenuInventory.configUI: setItemSections argument is not a local register')

    init_ins = abcrt.decode(c.body('MenuInventory::<init>')['code'])
    hit = find_seq(c, init_ins, [is_get('mcCharacterModelAnchor'), is_get('x'),
                                 lambda t: lit(abc, t[1], t[2]) is not None,
                                 lambda t: opn(t) == 'callpropvoid' and mn(t[2][0]) == 'setDefaultAnchor'])
    if len(hit) != 1:
        raise PatchError('MenuInventory.<init>: setDefaultAnchor(mcCharacterModelAnchor.x, y) not found')
    anchor_y = lit(abc, init_ins[hit[0][2]][1], init_ins[hit[0][2]][2])
    if anchor_y != int(anchor_y) or not 0 <= anchor_y < 0x8000:
        raise PatchError('MenuInventory.<init>: unexpected default anchor y %r' % anchor_y)
    m_set_default = init_ins[hit[0][3]][2][0]

    pdm = c.body('MenuInventory::createPaperdollModule')
    pdm_ins = abcrt.decode(pdm['code'])
    pd_hits = find_seq(c, pdm_ins, [lambda t: lit(abc, t[1], t[2]) == 856, set_x])
    if len(pd_hits) != 1:
        raise PatchError('createPaperdollModule: expected one "x = 856", found %d' % len(pd_hits))

    ccg = c.body('MenuInventory::createContainerGridModule')
    ccg_ins = abcrt.decode(ccg['code'])
    iv_hits = find_seq(c, ccg_ins, [lambda t: opn(t) == 'pushtrue',
                                    lambda t: opn(t) == 'setproperty' and mn(t[2][0]) == 'ignoreValidationOpt'])
    if len(iv_hits) != 1:
        raise PatchError('createContainerGridModule: expected one "ignoreValidationOpt = true", found %d' %
                         len(iv_hits))

    sim = c.body('MenuInventory::setInventoryMode')
    sim_ins = abcrt.decode(sim['code'])
    mode_hits = find_seq(c, sim_ins, [lambda t: opn(t) == 'getlocal0', lambda t: opn(t) == 'getlocal1',
                                      lambda t: opn(t) in ('setproperty', 'initproperty') and
                                      mn(t[2][0]) == '_inventoryMode'])
    if len(mode_hits) != 1:
        raise PatchError('setInventoryMode: expected one "_inventoryMode = mode", found %d' % len(mode_hits))

    def lit_x(owner, value):
        return find_seq(c, sim_ins, [is_get(owner),
                                     lambda t: lit(abc, t[1], t[2]) is not None and
                                     abs(lit(abc, t[1], t[2]) - value) < 1e-9,
                                     set_x])

    sites = {}   # instruction index -> slot name to add
    for owner, value, slot, want in (('btnSort', 314.75, 'uwC', 1), ('btnSortChange', 500.65, 'uwC', 1),
                                     ('btnSort', 422, 'uwC', 2), ('btnSortChange', 608, 'uwC', 2),
                                     ('mcSortingMode', 0, 'uwSR', 1)):
        h = lit_x(owner, value)
        if len(h) != want:
            raise PatchError('setInventoryMode: expected %d x %s.x = %s, found %d' % (want, owner, value, len(h)))
        for seq in h:
            sites[seq[1]] = slot
    place_p = find_seq(c, sim_ins, [is_get('playerGridInitX'), set_x])
    place_o = find_seq(c, sim_ins, [is_get('playerGridXOffset'), lambda t: opn(t) == 'add', set_x])
    if len(place_p) != 1 or len(place_o) != 2:
        raise PatchError('setInventoryMode: expected 1 + 2 grid module x assignments, found %d + %d' %
                         (len(place_p), len(place_o)))

    # ---- names ---------------------------------------------------------------------------------------------------
    cu = c.used_mn('CommonUtils', ('getlex',))
    rect = c.used_mn('Rectangle', ('constructprop',))
    late = late_mn(c)
    mask_str = nm.str_idx('mcGridMask')
    hit_str = nm.str_idx('mcBackgroundHitTest')
    t_num, t_int, t_bool = c.type_mn('Number'), c.type_mn('int'), c.type_mn('Boolean')
    like = next(t for t in abc.instances[ci]['traits'] if mn(t.name) == 'setInventoryMode' and t.kind == 1)
    void = abc.methods[like.method]['ret']
    for need_ in ('mcPlayerInventory', 'dropSlot', 'mcVitalityStat', 'mcToxicityStat', 'tooltipPaperdollAnchor',
                  'tooltipLeftAnchor', 'mcCharacterModelAnchor', '_rendererController', 'mcSelectionMode',
                  'mcShopBackground', 'mcSortingMode', 'mcContainerGridModule', 'mcStashBackground',
                  'moduleMerchantInfo'):
        nm[need_]
    title_str = nm.str_idx('titleStroke')
    pin = nm.own.get('pinnedCraftingModule')   # optional: a base without it gets no pinned-panel step
    gen = nm.own.get('mcPanelGeneralStats')    # optional: 'C' stats panels (their hit shapes are widened)
    det = nm.own.get('mcPanelDetailedStats')

    # ---- slots ---------------------------------------------------------------------------------------------------
    S = {}
    add_slot(c, ci, nm.new_trait('uwInvVersion'), t_int, c.integer(VERSION), 0x03)
    for s, v in (('uwCols', 9), ('uwStashCols', 8), ('uwShopCols', 8), ('uwKind', 0), ('uwEL', 0), ('uwER', 0),
                 ('uwE2', 0), ('uwES', 0), ('uwEM', 0)):
        S[s] = nm.new_trait(s)
        add_slot(c, ci, S[s], t_int, c.integer(v), 0x03)
    for s in ('uwWide', 'uwReady'):
        S[s] = nm.new_trait(s)
        add_slot(c, ci, S[s], t_bool, 0x0A, 0x0A)
    S['uwSecs'] = nm.new_trait('uwSecs')
    add_slot(c, ci, S['uwSecs'], 0, 0, 0)
    d0 = c.double(0.0)
    for s in ('uwSR', 'uwC', 'uwSB', 'uwPD', 'uwCX0', 'uwTA0', 'uwTL0', 'uwMX0', 'uwMW0', 'uwMB0', 'uwTipX', 'uwRX',
              'uwRW'):
        S[s] = nm.new_trait(s)
        add_slot(c, ci, S[s], t_num, d0, 0x06)
    m_layout, m_setup, m_split = nm.new_trait('uwLayout'), nm.new_trait('uwSetup'), nm.new_trait('uwSplit')
    m_cont, m_bg, m_place = nm.new_trait('uwCont'), nm.new_trait('uwFrameBg'), nm.new_trait('uwPlace')
    m_dim, m_mask, m_hit = nm.new_trait('uwDim'), nm.new_trait('uwShopMask'), nm.new_trait('uwHit')
    m_merch = nm.new_trait('uwMerch')

    # ---- small instruction helpers --------------------------------------------------------------------------------
    def need(loc, lab='END'):
        return [(None, 'getlocal', loc), (None, 'iffalse', lab)]

    def fetch(obj, member, loc):
        return [(None, 'getlocal', obj), (None, 'getproperty', member), (None, 'coerce_a'), (None, 'setlocal', loc)]

    def addx(obj, member, delta, lab, tmp):
        """obj.<member>.x += local <delta> when the member is not null (local <tmp> = scratch)"""
        return [*fetch(obj, member, tmp), *need(tmp, lab),
                (None, 'getlocal', tmp), (None, 'getlocal', tmp), (None, 'getproperty', X), (None, 'getlocal', delta),
                (None, 'add'), (None, 'setproperty', X),
                (lab, 'nop')]

    def cells(push_value, dst, cap, lab, tmp):
        """dst = (v >= 1) ? min(int(v), cap) : 0 for the Number v the instructions push (NaN -> 0)"""
        return [*push_value, (None, 'setlocal', tmp),
                (None, 'pushbyte', 0), (None, 'setlocal', dst),
                (None, 'getlocal', tmp), (None, 'pushbyte', 1), (None, 'ifnge', lab),
                (None, 'getlocal', tmp), (None, 'convert_i'), (None, 'setlocal', dst),
                (None, 'getlocal', dst), (None, 'pushbyte', cap), (None, 'ifngt', lab),
                (None, 'pushbyte', cap), (None, 'setlocal', dst),
                (lab, 'nop')]

    def put(slot, *push):
        """this.<slot> = value pushed by push"""
        return [(None, 'getlocal0'), *push, (None, 'setproperty', S[slot])]

    def get(slot):
        return [(None, 'getlocal0'), (None, 'getproperty', S[slot])]

    # ---- uwSetup(): widths decided once per menu, player cluster, pinned panel --------------------------------------
    # locals: 1 screen rect, 2 eL, 3 eR, 4 eRs, 5 x1, 6 scratch, 7 pinned panel, 8 pd, 9 module, 10 grid,
    #         11 list container, 12 scrollbar, 13 mask, 14 uwSecs, 15 object, 16 controller, 17 e2, 18 stash right
    #         limit, 19 S_R, 20 eS, 21 eM, 22 merchant frame right limit, 23 pinned panel left edge
    src = [
        (None, 'getlex', cu), (None, 'callproperty', P('getScreenRect'), 0), (None, 'coerce_a'), (None, 'setlocal', 1),
        *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', X), (None, 'getlocal', 1), (None, 'getproperty', W), (None, 'add'),
        (None, 'convert_d'), (None, 'setlocal', 5),
        *cells([(None, 'getlocal', 1), (None, 'getproperty', X), (None, 'negate'), (None, 'pushbyte', 64),
                (None, 'divide')], 2, MAX_E, 'EL', 6),
        *cells([(None, 'getlocal', 5), (None, 'pushshort', 1920), (None, 'subtract'), (None, 'pushbyte', 64),
                (None, 'divide')], 4, MAX_E, 'ER', 6),
        # default setting: the 21:9 layout (5 cells a side)
        *get('uwWide'), (None, 'iftrue', 'WL'),
        (None, 'getlocal', 2), (None, 'pushbyte', NARROW), (None, 'ifngt', 'WL'),
        (None, 'pushbyte', NARROW), (None, 'setlocal', 2),
        ('WL', 'getlocal', 4), (None, 'setlocal', 3),
        (None, 'getlocal', 3), (None, 'pushbyte', NARROW), (None, 'ifngt', 'NR'),
        (None, 'pushbyte', NARROW), (None, 'setlocal', 3),
        ('NR', 'getlocal', 2), (None, 'getlocal', 3), (None, 'add'), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        # shop / container / stash player grid (right end kept): as many columns as fit with player mode's vanilla
        # left margin; default setting: against the 21:9 rect (r.x -330 -> 7 extra, 16 columns)
        *cells([(None, 'pushshort', SHOP_L), (None, 'getlocal', 1), (None, 'getproperty', X), (None, 'subtract'),
                (None, 'pushbyte', 64), (None, 'divide')], 20, MAX_S, 'ES', 6),
        *get('uwWide'), (None, 'iftrue', 'ESW'),
        (None, 'getlocal', 20), (None, 'pushbyte', SHOP_NARROW), (None, 'ifngt', 'ESW'),
        (None, 'pushbyte', SHOP_NARROW), (None, 'setlocal', 20),
        ('ESW', 'nop'),
        # everything needed must exist before anything is decided
        *fetch(0, nm['mcPlayerInventory'], 9), *need(9),
        *fetch(9, P('mcPlayerGrid'), 10), *need(10),
        *fetch(9, P('mcListContainer'), 11), *need(11),
        *fetch(9, P('mcScrollbar'), 12), *need(12),
        (None, 'getlocal', 9), (None, 'pushstring', mask_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 13), *need(13),
        *fetch(0, S['uwSecs'], 14), *need(14),
        (None, 'getlocal', 14), (None, 'getproperty', P('sections')), (None, 'iffalse', 'END'),
        # pinned panel shift: 21:9 rule, or (wide) its right end PIN_EDGE inside the screen; eR follows
        *([(None, 'getlocal0'), (None, 'getproperty', pin)] if pin else [(None, 'pushnull')]),
        (None, 'coerce_a'), (None, 'setlocal', 7),
        (None, 'getlocal', 3), (None, 'pushbyte', 64), (None, 'multiply'), (None, 'pushshort', PIN_CLEAR),
        (None, 'subtract'), (None, 'convert_d'), (None, 'setlocal', 8),
        (None, 'getlocal', 8), (None, 'pushbyte', 0), (None, 'ifnlt', 'PZ'),
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal', 8),
        ('PZ', 'getlocal0'), (None, 'getproperty', S['uwWide']), (None, 'iffalse', 'PW'),
        *need(7, 'PW'),
        (None, 'getlocal', 5), (None, 'pushdouble', c.double(PIN_EDGE + PIN_R)), (None, 'subtract'),
        (None, 'getlocal', 7), (None, 'getproperty', X), (None, 'subtract'), (None, 'convert_d'), (None, 'setlocal', 6),
        (None, 'getlocal', 6), (None, 'getlocal', 8), (None, 'ifngt', 'PW'),
        (None, 'getlocal', 6), (None, 'setlocal', 8),
        (None, 'getlocal', 8), (None, 'pushshort', PIN_CLEAR), (None, 'add'), (None, 'pushbyte', 64), (None, 'divide'),
        (None, 'convert_i'), (None, 'setlocal', 6),
        (None, 'getlocal', 6), (None, 'getlocal', 4), (None, 'ifngt', 'E1'),
        (None, 'getlocal', 4), (None, 'setlocal', 6),
        ('E1', 'getlocal', 6), (None, 'getlocal', 3), (None, 'ifngt', 'PW'),
        (None, 'getlocal', 6), (None, 'setlocal', 3),
        ('PW', 'nop'),
        # stash: frame right end STASH_EDGE inside the screen (the pinned panel is only ever filled in shops, so it is
        # not a limit here); default setting, or a screen no wider than 21:9: at most STASH_NARROW extra columns,
        # so every 21:9-and-wider screen gets the same 16-column stash and both settings match on 21:9
        (None, 'getlocal', 5), (None, 'pushbyte', STASH_EDGE), (None, 'subtract'), (None, 'convert_d'),
        (None, 'setlocal', 18),
        *cells([(None, 'getlocal', 18), (None, 'pushdouble', c.double(STASH_R)), (None, 'subtract'),
                (None, 'pushbyte', 64), (None, 'divide')], 17, MAX_E, 'E2', 6),
        (None, 'getlocal0'), (None, 'getproperty', S['uwWide']), (None, 'iffalse', 'SC'),
        (None, 'getlocal', 4), (None, 'pushbyte', NARROW), (None, 'ifngt', 'SC'), (None, 'jump', 'ST'),
        ('SC', 'getlocal', 17), (None, 'pushbyte', STASH_NARROW), (None, 'ifngt', 'ST'),
        (None, 'pushbyte', STASH_NARROW), (None, 'setlocal', 17),
        ('ST', 'nop'),
        # merchant / container grid: frame right end SHOP_EDGE inside the screen (default setting: inside the 21:9
        # rect) and, while the pinned panel's left edge is on screen, PIN_GAP left of it (the panel at its moved place)
        (None, 'getlocal', 5), (None, 'pushbyte', SHOP_EDGE), (None, 'subtract'), (None, 'convert_d'),
        (None, 'setlocal', 22),
        *get('uwWide'), (None, 'iftrue', 'MW'),
        (None, 'getlocal', 22), (None, 'pushshort', R21_X1 - SHOP_EDGE), (None, 'ifngt', 'MW'),
        (None, 'pushshort', R21_X1 - SHOP_EDGE), (None, 'convert_d'), (None, 'setlocal', 22),
        ('MW', 'nop'),
        *need(7, 'MP'),
        (None, 'getlocal', 7), (None, 'getproperty', X), (None, 'getlocal', 8), (None, 'add'),
        (None, 'pushdouble', c.double(PIN_L)), (None, 'add'), (None, 'convert_d'), (None, 'setlocal', 23),
        (None, 'getlocal', 23), (None, 'getlocal', 5), (None, 'ifnlt', 'MP'),
        (None, 'getlocal', 23), (None, 'pushbyte', PIN_GAP), (None, 'subtract'), (None, 'getlocal', 22),
        (None, 'ifnlt', 'MP'),
        (None, 'getlocal', 23), (None, 'pushbyte', PIN_GAP), (None, 'subtract'), (None, 'convert_d'),
        (None, 'setlocal', 22),
        ('MP', 'nop'),
        *cells([(None, 'getlocal', 22), (None, 'pushdouble', c.double(SHOP_R)), (None, 'subtract'),
                (None, 'pushbyte', 64), (None, 'divide')], 21, MAX_E, 'EM', 6),
        # commit (decisions, then the vanilla originals the per-mode layout is computed from)
        (None, 'getlocal', 3), (None, 'pushbyte', 64), (None, 'multiply'), (None, 'convert_d'), (None, 'setlocal', 19),
        *put('uwEL', (None, 'getlocal', 2)), *put('uwER', (None, 'getlocal', 3)), *put('uwE2', (None, 'getlocal', 17)),
        *put('uwES', (None, 'getlocal', 20)), *put('uwEM', (None, 'getlocal', 21)),
        *put('uwSR', (None, 'getlocal', 19)), *put('uwPD', (None, 'getlocal', 8)),
        *put('uwRX', (None, 'getlocal', 1), (None, 'getproperty', X), (None, 'convert_d')),
        *put('uwRW', (None, 'getlocal', 1), (None, 'getproperty', W), (None, 'convert_d')),
        *put('uwCX0', (None, 'getlocal', 11), (None, 'getproperty', X), (None, 'convert_d')),
        *fetch(9, P('mcSectionTitlesAnchor'), 15), *need(15, 'O1'),
        *put('uwTA0', (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'convert_d')),
        ('O1', 'nop'),
        *fetch(9, P('mcTabList'), 15), *need(15, 'O2'),
        *put('uwTL0', (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'convert_d')),
        ('O2', 'nop'),
        *put('uwMX0', (None, 'getlocal', 13), (None, 'getproperty', X), (None, 'convert_d')),
        *put('uwMW0', (None, 'getlocal', 13), (None, 'getproperty', W), (None, 'convert_d')),
        *put('uwMB0', (None, 'getlocal', 13), (None, 'getlocal', 9), (None, 'callproperty', P('getBounds'), 1),
             (None, 'getproperty', X), (None, 'convert_d')),
        *fetch(0, nm['tooltipLeftAnchor'], 15), *need(15, 'O3'),
        *put('uwTipX', (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'convert_d')),
        ('O3', 'nop'),
        *put('uwReady', (None, 'pushtrue')),
        # player-mode cluster right of the grid: S_R, once per menu
        *addx(0, nm['dropSlot'], 19, 'R1', 15),
        *addx(0, nm['mcVitalityStat'], 19, 'R2', 15),
        *addx(0, nm['mcToxicityStat'], 19, 'R3', 15),
        *addx(0, nm['tooltipPaperdollAnchor'], 19, 'R4', 15),
        *fetch(0, nm['mcCharacterModelAnchor'], 15), *need(15, 'RC'),
        (None, 'getlocal', 15), (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'getlocal', 19), (None, 'add'),
        (None, 'setproperty', X),
        *fetch(0, nm['_rendererController'], 16), *need(16, 'RC'),
        (None, 'getlocal', 16), (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'pushshort', int(anchor_y)),
        (None, 'callpropvoid', m_set_default, 2),
        ('RC', 'nop'),
        # pinned crafting panel
        *need(7, 'PC'),
        (None, 'getlocal', 8), (None, 'pushbyte', 0), (None, 'ifngt', 'PC'),
        (None, 'getlocal', 7), (None, 'getlocal', 7), (None, 'getproperty', X), (None, 'getlocal', 8), (None, 'add'),
        (None, 'setproperty', X),
        ('PC', 'getlocal0'), (None, 'getlocal', 1), (None, 'callpropvoid', m_dim, 1),
        (None, 'getlocal0'), (None, 'callpropvoid', m_mask, 0),
        # 'C' stats mode: the panels' transparent hit shapes reach the screen edges again (own catch-all handler)
        *([(None, 'getlocal0'), (None, 'getlocal0'), (None, 'getproperty', gen), (None, 'getlocal', 1),
           (None, 'getproperty', X), (None, 'pushbyte', HIT_PAD), (None, 'subtract'), (None, 'pushfalse'),
           (None, 'callpropvoid', m_hit, 3)] if gen else []),
        *([(None, 'getlocal0'), (None, 'getlocal0'), (None, 'getproperty', det), (None, 'getlocal', 5),
           (None, 'pushbyte', HIT_PAD), (None, 'add'), (None, 'pushtrue'),
           (None, 'callpropvoid', m_hit, 3)] if det else []),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_setup, [], void, src, 6, 24, cfg, 'uwsu_')

    # ---- uwLayout(mode): the grid for this mode ----------------------------------------------------------------------
    # locals: 1 mode, 2 kind, 3 L, 4 R, 5 N, 6 C, 7 SB, 8 dC, 9 dSB, 10 module, 11 grid, 12 list container,
    #         13 scrollbar, 14 mask, 15 object, 16 tab index, 17 tab sections
    src = [
        (None, 'pushbyte', 2), (None, 'setlocal', 2),
        (None, 'getlocal', 1), (None, 'pushbyte', 0), (None, 'equals'), (None, 'iffalse', 'K1'),
        (None, 'pushbyte', 1), (None, 'setlocal', 2), (None, 'jump', 'K9'),
        ('K1', 'getlocal', 1), (None, 'pushbyte', 1), (None, 'equals'), (None, 'iftrue', 'K9'),
        (None, 'getlocal', 1), (None, 'pushbyte', 2), (None, 'equals'), (None, 'iftrue', 'K9'),
        (None, 'getlocal', 1), (None, 'pushbyte', 4), (None, 'equals'), (None, 'iftrue', 'K9'),
        (None, 'jump', 'END'),                                   # horse (3) or anything else: keep the layout
        ('K9', 'getlocal0'), (None, 'getproperty', S['uwReady']), (None, 'iftrue', 'RD'),
        (None, 'getlocal0'), (None, 'callpropvoid', m_setup, 0),
        *get('uwReady'), (None, 'iffalse', 'END'),
        ('RD', 'getlocal0'), (None, 'getproperty', S['uwKind']), (None, 'getlocal', 2), (None, 'equals'),
        (None, 'iftrue', 'END'),
        # shop / container / stash: L = eS, R = 0 (grows left only); player: L = eL, R = eR
        *get('uwES'), (None, 'convert_i'), (None, 'setlocal', 3),
        (None, 'pushbyte', 0), (None, 'setlocal', 4),
        (None, 'getlocal', 2), (None, 'pushbyte', 1), (None, 'equals'), (None, 'iffalse', 'NP'),
        *get('uwEL'), (None, 'convert_i'), (None, 'setlocal', 3),
        *get('uwER'), (None, 'convert_i'), (None, 'setlocal', 4),
        ('NP', 'getlocal', 3), (None, 'getlocal', 4), (None, 'add'), (None, 'pushbyte', 9), (None, 'add'),
        (None, 'convert_i'), (None, 'setlocal', 5),
        (None, 'getlocal', 4), (None, 'getlocal', 3), (None, 'subtract'), (None, 'pushbyte', 32), (None, 'multiply'),
        (None, 'convert_d'), (None, 'setlocal', 6),
        (None, 'getlocal', 4), (None, 'pushbyte', 64), (None, 'multiply'), (None, 'convert_d'), (None, 'setlocal', 7),
        *fetch(0, nm['mcPlayerInventory'], 10), *need(10),
        *fetch(10, P('mcPlayerGrid'), 11), *need(11),
        *fetch(10, P('mcListContainer'), 12), *need(12),
        *fetch(10, P('mcScrollbar'), 13), *need(13),
        (None, 'getlocal', 10), (None, 'pushstring', mask_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 14), *need(14),
        (None, 'getlocal', 6), *get('uwC'), (None, 'subtract'), (None, 'convert_d'), (None, 'setlocal', 8),
        (None, 'getlocal', 7), *get('uwSB'), (None, 'subtract'), (None, 'convert_d'), (None, 'setlocal', 9),
        # commit first: the setInventoryMode hooks then follow whatever part below got applied
        *put('uwKind', (None, 'getlocal', 2)), *put('uwCols', (None, 'getlocal', 5)),
        *put('uwC', (None, 'getlocal', 6)), *put('uwSB', (None, 'getlocal', 7)),
        (None, 'getlocal0'), (None, 'getlocal', 5), (None, 'callpropvoid', m_split, 1),
        (None, 'getlocal', 11), (None, 'getlocal', 5), (None, 'setproperty', P('columns')),
        # grid centre (container), section titles and tabs: absolute from the originals
        (None, 'getlocal', 12), *get('uwCX0'), (None, 'getlocal', 6), (None, 'add'), (None, 'setproperty', X),
        *fetch(10, P('mcSectionTitlesAnchor'), 15), *need(15, 'A1'),
        (None, 'getlocal', 15), *get('uwTA0'), (None, 'getlocal', 6), (None, 'add'), (None, 'setproperty', X),
        ('A1', 'nop'),
        *fetch(10, P('mcTabList'), 15), *need(15, 'A2'),
        (None, 'getlocal', 15), *get('uwTL0'), (None, 'getlocal', 6), (None, 'add'), (None, 'setproperty', X),
        ('A2', 'nop'),
        *fetch(10, P('mcTabBackground'), 15), *need(15, 'TB'),
        (None, 'getlocal', 15), (None, 'getproperty', P('parent')), (None, 'getlocal', 12), (None, 'strictequals'),
        (None, 'iftrue', 'TB'),
        (None, 'getlocal', 15), (None, 'getlocal', 15), (None, 'getproperty', X), (None, 'getlocal', 8), (None, 'add'),
        (None, 'setproperty', X),
        # scrollbar: relative to what is applied, whichever parent it has now
        ('TB', 'getlocal', 13), (None, 'getproperty', P('parent')), (None, 'getlocal', 12), (None, 'strictequals'),
        (None, 'iffalse', 'SBM'),
        (None, 'getlocal', 13), (None, 'getlocal', 13), (None, 'getproperty', X), (None, 'getlocal', 9),
        (None, 'add'), (None, 'getlocal', 8), (None, 'subtract'), (None, 'setproperty', X),
        (None, 'jump', 'MASK'),
        ('SBM', 'getlocal', 13), (None, 'getlocal', 13), (None, 'getproperty', X), (None, 'getlocal', 9),
        (None, 'add'), (None, 'setproperty', X),
        # mask: 64*L wider on the left, 64*R on the right of the vanilla mask
        ('MASK', 'getlocal', 14), *get('uwMX0'), (None, 'setproperty', X),
        (None, 'getlocal', 14), *get('uwMW0'), (None, 'getlocal', 3), (None, 'getlocal', 4), (None, 'add'),
        (None, 'pushbyte', 64), (None, 'multiply'), (None, 'add'), (None, 'setproperty', W),
        (None, 'getlocal', 14),
        (None, 'getlocal', 14), (None, 'getproperty', X),
        *get('uwMB0'), (None, 'getlocal', 3), (None, 'pushbyte', 64), (None, 'multiply'), (None, 'subtract'),
        (None, 'getlocal', 14), (None, 'getlocal', 10), (None, 'callproperty', P('getBounds'), 1),
        (None, 'getproperty', X), (None, 'subtract'),
        (None, 'add'), (None, 'setproperty', X),
        # re-flow a grid that was already populated with another column count
        (None, 'getlocal', 10), (None, 'getproperty', P('currentlySelectedTabIndex')), (None, 'convert_i'),
        (None, 'setlocal', 16),
        (None, 'getlocal', 16), (None, 'pushbyte', 0), (None, 'iflt', 'END'),
        *get('uwSecs'), (None, 'getlocal', 16), (None, 'callproperty', P('getTabSections'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 17), *need(17),
        (None, 'getlocal', 17), (None, 'getproperty', P('length')), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        (None, 'getlocal', 11), (None, 'getlocal', 17), (None, 'callpropvoid', P('setItemSections'), 1),
        (None, 'getlocal', 11),
        (None, 'getlocal', 5), (None, 'pushbyte', 64), (None, 'multiply'),
        (None, 'getlocal', 17), (None, 'getproperty', P('length')), (None, 'pushbyte', 1), (None, 'subtract'),
        (None, 'pushbyte', 15), (None, 'multiply'), (None, 'add'), (None, 'negate'), (None, 'pushbyte', 2),
        (None, 'divide'), (None, 'setproperty', X),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_layout, [0], void, src, 8, 18, cfg, 'uwl_')

    # ---- uwSplit(N): even sections per tab ---------------------------------------------------------------------------
    # locals: 1 N, 2 sections array, 3 n, 4 i, 5 entry, 6 section, 7 tab, 8 k, 9 j, 10 i2, 11 entry2, 12 q, 13 r,
    #         14 start
    src = [
        *fetch(0, S['uwSecs'], 2), *need(2),
        *fetch(2, P('sections'), 2), *need(2),
        (None, 'getlocal', 2), (None, 'getproperty', P('length')), (None, 'convert_i'), (None, 'setlocal', 3),
        (None, 'pushbyte', 0), (None, 'setlocal', 4),
        (None, 'jump', 'C1'),
        ('L1', 'label'),
        (None, 'getlocal', 2), (None, 'getlocal', 4), (None, 'getproperty', late), (None, 'coerce_a'),
        (None, 'setlocal', 5), *need(5, 'N1'),
        *fetch(5, P('item'), 6), *need(6, 'N1'),
        *fetch(5, P('tabIdx'), 7),
        (None, 'pushbyte', 0), (None, 'setlocal', 8),
        (None, 'pushbyte', 0), (None, 'setlocal', 9),
        (None, 'pushbyte', 0), (None, 'setlocal', 10),
        (None, 'jump', 'C2'),
        ('L2', 'label'),
        (None, 'getlocal', 2), (None, 'getlocal', 10), (None, 'getproperty', late), (None, 'coerce_a'),
        (None, 'setlocal', 11), *need(11, 'N2'),
        (None, 'getlocal', 11), (None, 'getproperty', P('item')), (None, 'iffalse', 'N2'),
        (None, 'getlocal', 11), (None, 'getproperty', P('tabIdx')), (None, 'getlocal', 7), (None, 'equals'),
        (None, 'iffalse', 'N2'),
        (None, 'inclocal_i', 8),
        (None, 'getlocal', 10), (None, 'getlocal', 4), (None, 'ifnlt', 'N2'),
        (None, 'inclocal_i', 9),
        ('N2', 'inclocal_i', 10),
        ('C2', 'getlocal', 10), (None, 'getlocal', 3), (None, 'iflt', 'L2'),
        # q = floor(N/k), r = N mod k; section j: start = j*q + min(j, r), width q (+1 while j < r)
        (None, 'getlocal', 1), (None, 'getlocal', 8), (None, 'divide'), (None, 'convert_i'), (None, 'setlocal', 12),
        (None, 'getlocal', 1), (None, 'getlocal', 12), (None, 'getlocal', 8), (None, 'multiply'), (None, 'subtract'),
        (None, 'convert_i'), (None, 'setlocal', 13),
        (None, 'getlocal', 9), (None, 'getlocal', 12), (None, 'multiply'), (None, 'getlocal', 13), (None, 'add'),
        (None, 'convert_i'), (None, 'setlocal', 14),
        (None, 'getlocal', 9), (None, 'getlocal', 13), (None, 'ifnlt', 'S1'),
        (None, 'getlocal', 9), (None, 'getlocal', 12), (None, 'multiply'), (None, 'getlocal', 9), (None, 'add'),
        (None, 'convert_i'), (None, 'setlocal', 14),
        ('S1', 'getlocal', 6), (None, 'getlocal', 14), (None, 'setproperty', P('start')),
        (None, 'getlocal', 6), (None, 'getlocal', 14), (None, 'getlocal', 12), (None, 'add'), (None, 'pushbyte', 1),
        (None, 'subtract'), (None, 'setproperty', P('end')),
        (None, 'getlocal', 9), (None, 'getlocal', 13), (None, 'ifnlt', 'N1'),
        (None, 'getlocal', 6), (None, 'getlocal', 14), (None, 'getlocal', 12), (None, 'add'),
        (None, 'setproperty', P('end')),
        ('N1', 'inclocal_i', 4),
        ('C1', 'getlocal', 4), (None, 'getlocal', 3), (None, 'iflt', 'L1'),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_split, [0], void, src, 6, 15, cfg, 'uwsp_')

    # ---- uwCont(mode): stash (e2) and merchant / container (eM) grid grows right ---------------------------------------
    # locals: 1 mode, 2 e, 3 d, 4 container module, 5 grid, 6 mask, 7 mask bounds x, 8 scrollbar, 9 drop target
    src = [
        (None, 'getlocal', 1), (None, 'pushbyte', 4), (None, 'equals'), (None, 'iffalse', 'MS'),
        *get('uwE2'), (None, 'convert_i'), (None, 'setlocal', 2), (None, 'jump', 'GO'),
        ('MS', 'getlocal', 1), (None, 'pushbyte', 1), (None, 'equals'), (None, 'iftrue', 'MM'),
        (None, 'getlocal', 1), (None, 'pushbyte', 2), (None, 'equals'), (None, 'iffalse', 'END'),
        ('MM', 'getlocal0'), (None, 'getproperty', S['uwEM']), (None, 'convert_i'), (None, 'setlocal', 2),
        ('GO', 'getlocal', 2), (None, 'pushbyte', 0), (None, 'ifngt', 'END'),
        (None, 'getlocal', 2), (None, 'pushbyte', 64), (None, 'multiply'), (None, 'convert_d'), (None, 'setlocal', 3),
        *fetch(0, nm['mcContainerGridModule'], 4), *need(4),
        *fetch(4, P('mcPlayerGrid'), 5), *need(5),
        (None, 'getlocal', 5), (None, 'getproperty', P('columns')), (None, 'pushbyte', 8), (None, 'equals'),
        (None, 'iffalse', 'END'),
        (None, 'getlocal', 4), (None, 'pushstring', mask_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 6), *need(6),
        *fetch(4, P('mcScrollBar'), 8), *need(8),
        *fetch(4, P('mcStateDropTarget'), 9),
        (None, 'getlocal', 1), (None, 'pushbyte', 4), (None, 'equals'), (None, 'iffalse', 'CS'),
        *put('uwStashCols', (None, 'getlocal', 2), (None, 'pushbyte', 8), (None, 'add'), (None, 'convert_i')),
        (None, 'jump', 'CC'),
        ('CS', 'nop'),
        *put('uwShopCols', (None, 'getlocal', 2), (None, 'pushbyte', 8), (None, 'add'), (None, 'convert_i')),
        ('CC', 'getlocal', 5), (None, 'getlocal', 2), (None, 'pushbyte', 8), (None, 'add'),
        (None, 'setproperty', P('columns')),
        (None, 'getlocal', 6), (None, 'getlocal', 4), (None, 'callproperty', P('getBounds'), 1),
        (None, 'getproperty', X), (None, 'convert_d'), (None, 'setlocal', 7),
        (None, 'getlocal', 6), (None, 'getlocal', 6), (None, 'getproperty', W), (None, 'getlocal', 3), (None, 'add'),
        (None, 'setproperty', W),
        (None, 'getlocal', 6),
        (None, 'getlocal', 6), (None, 'getproperty', X), (None, 'getlocal', 7), (None, 'add'),
        (None, 'getlocal', 6), (None, 'getlocal', 4), (None, 'callproperty', P('getBounds'), 1),
        (None, 'getproperty', X), (None, 'subtract'), (None, 'setproperty', X),
        (None, 'getlocal', 8), (None, 'getlocal', 8), (None, 'getproperty', X), (None, 'getlocal', 3), (None, 'add'),
        (None, 'setproperty', X),
        *need(9, 'BG'),
        (None, 'getlocal', 9), (None, 'getlocal', 9), (None, 'getproperty', W), (None, 'getlocal', 3), (None, 'add'),
        (None, 'setproperty', W),
        (None, 'getlocal', 9), (None, 'getlocal', 9), (None, 'getproperty', X), (None, 'getlocal', 3),
        (None, 'pushbyte', 2), (None, 'divide'), (None, 'add'), (None, 'setproperty', X),
        # frame lines: the stash's #612, or the shop's right #612 plus the merchant header (both are shop/container art;
        # the header is only ever filled in shops)
        ('BG', 'getlocal', 1), (None, 'pushbyte', 4), (None, 'equals'), (None, 'iffalse', 'SH'),
        (None, 'getlocal0'), (None, 'getlocal0'), (None, 'getproperty', nm['mcStashBackground']), (None, 'getlocal', 3),
        (None, 'pushdouble', c.double(float(STASH_BG_X0))), (None, 'callpropvoid', m_bg, 3),
        (None, 'jump', 'END'),
        ('SH', 'getlocal0'), (None, 'getlocal0'), (None, 'getproperty', nm['mcShopBackground']), (None, 'getlocal', 3),
        (None, 'pushdouble', c.double(float(SHOP_BG_X0))), (None, 'callpropvoid', m_bg, 3),
        (None, 'getlocal0'), (None, 'getlocal', 3), (None, 'callpropvoid', m_merch, 1),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_cont, [0], void, src, 6, 10, cfg, 'uwc_')

    # ---- uwFrameBg(bg, d, x0): a frame-lines sprite (#612) spans the wider grid ------------------------------------
    # the child of bg with x0 < x < x0 + 10 and 600 < width < 640: width += d (scaled about its left edge)
    # locals: 1 background, 2 d, 3 x0, 4 child count, 5 i, 6 child
    src = [
        *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', P('numChildren')), (None, 'convert_i'), (None, 'setlocal', 4),
        (None, 'pushbyte', 0), (None, 'setlocal', 5),
        (None, 'jump', 'C'),
        ('L', 'label'),
        (None, 'getlocal', 1), (None, 'getlocal', 5), (None, 'callproperty', P('getChildAt'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 6), *need(6, 'N'),
        (None, 'getlocal', 6), (None, 'getproperty', X), (None, 'getlocal', 3), (None, 'subtract'), (None, 'pushbyte', 0),
        (None, 'ifngt', 'N'),
        (None, 'getlocal', 6), (None, 'getproperty', X), (None, 'getlocal', 3), (None, 'subtract'),
        (None, 'pushbyte', 10), (None, 'ifnlt', 'N'),
        (None, 'getlocal', 6), (None, 'getproperty', W), (None, 'pushshort', 600), (None, 'ifngt', 'N'),
        (None, 'getlocal', 6), (None, 'getproperty', W), (None, 'pushshort', 640), (None, 'ifnlt', 'N'),
        (None, 'getlocal', 6), (None, 'getlocal', 6), (None, 'getproperty', W), (None, 'getlocal', 2), (None, 'add'),
        (None, 'setproperty', W),
        (None, 'jump', 'END'),
        ('N', 'inclocal_i', 5),
        ('C', 'getlocal', 5), (None, 'getlocal', 4), (None, 'iflt', 'L'),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_bg, [0, 0, 0], void, src, 5, 7, cfg, 'uwb_')

    # ---- uwMerch(d): merchant header over the wider merchant grid -----------------------------------------------------
    # titleStroke (one solid-colour rectangle, no bitmap) width += d, so the bar spans the grid as in vanilla; the
    # right-aligned level / type fields move right by d; money and coin icon stay at the bar's left end.
    # locals: 1 d, 2 header module, 3 child
    src = [
        *fetch(0, nm['moduleMerchantInfo'], 2), *need(2),
        (None, 'getlocal', 2), (None, 'pushstring', title_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 3), *need(3, 'T1'),
        (None, 'getlocal', 3), (None, 'getproperty', W), (None, 'pushshort', TITLE_W[0]), (None, 'ifngt', 'T1'),
        (None, 'getlocal', 3), (None, 'getproperty', W), (None, 'pushshort', TITLE_W[1]), (None, 'ifnlt', 'T1'),
        (None, 'getlocal', 3), (None, 'getlocal', 3), (None, 'getproperty', W), (None, 'getlocal', 1), (None, 'add'),
        (None, 'setproperty', W),
        ('T1', 'nop'),
        *addx(2, P('txtLevelValue'), 1, 'T2', 3),
        *addx(2, P('txtType'), 1, 'T3', 3),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_merch, [0], void, src, 4, 4, cfg, 'uwmi_')

    # ---- uwDim(r): selection-mode dimming over the whole visible screen ------------------------------------------
    src = [
        *fetch(0, nm['mcSelectionMode'], 2), *need(2),
        *fetch(2, P('mcBackgroundHitTest'), 3), *need(3), *need(1),
        (None, 'getlocal', 3), (None, 'getlocal', 1), (None, 'getproperty', X), (None, 'setproperty', X),
        (None, 'getlocal', 3), (None, 'getlocal', 1), (None, 'getproperty', W), (None, 'setproperty', W),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_dim, [0], void, src, 3, 4, cfg, 'uwd_')

    # ---- uwShopMask(): shop/container background shows only the merchant-side frame (x >= 1000) -------------------
    src = [
        *fetch(0, nm['mcShopBackground'], 1), *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', P('mask')), (None, 'iftrue', 'END'),
        (None, 'getlex', cu), (None, 'findpropstrict', rect),
        (None, 'pushshort', SHOP_MASK_X), (None, 'pushshort', 1000), (None, 'negate'), (None, 'pushshort', 4000),
        (None, 'pushshort', 3080), (None, 'constructprop', rect, 4),
        (None, 'pushbyte', 0), (None, 'pushbyte', 1), (None, 'callproperty', P('createSolidColorSprite'), 3),
        (None, 'coerce_a'), (None, 'setlocal', 2), *need(2),
        (None, 'getlocal', 2), (None, 'pushfalse'), (None, 'setproperty', P('mouseEnabled')),
        (None, 'getlocal', 2), (None, 'pushfalse'), (None, 'setproperty', P('mouseChildren')),
        (None, 'getlocal0'), (None, 'getlocal', 2), (None, 'pushbyte', 0), (None, 'callpropvoid', P('addChildAt'), 2),
        (None, 'getlocal', 1), (None, 'getlocal', 2), (None, 'setproperty', P('mask')),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_mask, [], void, src, 6, 3, cfg, 'uwm_')

    # ---- uwHit(panel, t, right): a stats panel's transparent hit shape reaches stage x t (left or right end) --------
    # locals: 1 panel, 2 t, 3 right, 4 shape, 5 bounds, 6 new left, 7 new right, 8 new bounds
    src = [
        *need(1),
        (None, 'getlocal', 1), (None, 'getproperty', P('numChildren')), (None, 'pushbyte', 1), (None, 'ifnge', 'END'),
        (None, 'getlocal', 1), (None, 'pushbyte', 0), (None, 'callproperty', P('getChildAt'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 4), *need(4),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'callproperty', P('getBounds'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 5), *need(5),
        # only the full-height hit shape (child 0 of both panels in all six bases)
        (None, 'getlocal', 5), (None, 'getproperty', P('height')), (None, 'pushshort', HIT_MIN_H), (None, 'ifnge', 'END'),
        (None, 'getlocal', 5), (None, 'getproperty', W), (None, 'pushshort', HIT_MIN_W), (None, 'ifnge', 'END'),
        (None, 'getlocal', 5), (None, 'getproperty', X), (None, 'convert_d'), (None, 'setlocal', 6),
        (None, 'getlocal', 5), (None, 'getproperty', X), (None, 'getlocal', 5), (None, 'getproperty', W), (None, 'add'),
        (None, 'convert_d'), (None, 'setlocal', 7),
        # only ever outwards (NaN t: no change)
        (None, 'getlocal', 3), (None, 'iffalse', 'LFT'),
        (None, 'getlocal', 2), (None, 'getlocal', 7), (None, 'ifngt', 'END'),
        (None, 'getlocal', 2), (None, 'convert_d'), (None, 'setlocal', 7), (None, 'jump', 'SET'),
        ('LFT', 'getlocal', 2), (None, 'getlocal', 6), (None, 'ifnlt', 'END'),
        (None, 'getlocal', 2), (None, 'convert_d'), (None, 'setlocal', 6),
        # width in proportion, then x so the left end lands on the new left (parent units = width / bounds width)
        ('SET', 'getlocal', 4),
        (None, 'getlocal', 4), (None, 'getproperty', W), (None, 'getlocal', 7), (None, 'getlocal', 6), (None, 'subtract'),
        (None, 'multiply'), (None, 'getlocal', 5), (None, 'getproperty', W), (None, 'divide'), (None, 'setproperty', W),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'callproperty', P('getBounds'), 1), (None, 'coerce_a'),
        (None, 'setlocal', 8), *need(8),
        (None, 'getlocal', 4),
        (None, 'getlocal', 4), (None, 'getproperty', X),
        (None, 'getlocal', 6), (None, 'getlocal', 8), (None, 'getproperty', X), (None, 'subtract'),
        (None, 'getlocal', 4), (None, 'getproperty', W), (None, 'multiply'), (None, 'getlocal', 8), (None, 'getproperty', W),
        (None, 'divide'), (None, 'add'), (None, 'setproperty', X),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_hit, [0, 0, 0], void, src, 5, 9, cfg, 'uwht_')

    # ---- uwPlace(player): per-mode tooltip anchor, sort popup dimming, draw bounds after the module moved ----------
    # locals: 1 player, 2 object, 3 scratch Number / saved y, 4 popup dimming
    src = [
        (None, 'getlocal0'), (None, 'getproperty', S['uwCols']), (None, 'pushbyte', 9), (None, 'equals'),
        (None, 'iftrue', 'END'),
        *fetch(0, nm['tooltipLeftAnchor'], 2), *need(2, 'SRT'),
        (None, 'pushbyte', 0), (None, 'convert_d'), (None, 'setlocal', 3),
        (None, 'getlocal', 1), (None, 'iffalse', 'TIP'),
        (None, 'getlocal0'), (None, 'getproperty', S['uwSR']), (None, 'convert_d'), (None, 'setlocal', 3),
        ('TIP', 'getlocal', 2), (None, 'getlocal0'), (None, 'getproperty', S['uwTipX']), (None, 'getlocal', 3),
        (None, 'add'), (None, 'setproperty', X),
        # sort popup's modal dimming: whole visible screen, wherever the popup now sits
        ('SRT', 'nop'),
        *fetch(0, nm['mcSortingMode'], 2), *need(2, 'BND'),
        (None, 'getlocal', 2), (None, 'pushstring', hit_str), (None, 'callproperty', P('getChildByName'), 1),
        (None, 'coerce_a'), (None, 'setlocal', 4), *need(4, 'BND'),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'getproperty', S['uwRX']), (None, 'getlocal', 2),
        (None, 'getproperty', X), (None, 'subtract'), (None, 'setproperty', X),
        (None, 'getlocal', 4), (None, 'getlocal0'), (None, 'getproperty', S['uwRW']), (None, 'setproperty', W),
        # draw bounds at the menu's resting y
        ('BND', 'nop'),
        *fetch(0, nm['mcPlayerInventory'], 2), *need(2),
        *fetch(2, P('mcPlayerGrid'), 2), *need(2),
        (None, 'getlocal0'), (None, 'getproperty', Y), (None, 'convert_d'), (None, 'setlocal', 3),
        (None, 'getlocal0'), (None, 'pushbyte', 0), (None, 'setproperty', Y),
        (None, 'getlocal', 2), (None, 'callpropvoid', P('updateRendererBounds'), 0),
        (None, 'getlocal0'), (None, 'getlocal', 3), (None, 'setproperty', Y),
        ('END', 'returnvoid'),
    ]
    new_method(c, ci, m_place, [0], void, src, 4, 5, cfg, 'uwp_')

    # ---- hooks -----------------------------------------------------------------------------------------------------
    patch_body(cfg, {sis[0]: [('getlocal0', []), ('getlocal', [sect_reg]), ('setproperty', [S['uwSecs']])]}, 'uwh')
    patch_body(pdm, {pd_hits[0][0]: [('getlocal0', []), ('getproperty', [S['uwSR']]), ('add', [])]}, 'uwpd')
    patch_body(ccg, {iv_hits[0][1]: [('getlocal0', []), ('getlocal1', []), ('callpropvoid', [m_cont, 1])]}, 'uwcg')
    after = {i: [('getlocal0', []), ('getproperty', [S[s]]), ('add', [])] for i, s in sites.items()}
    after[mode_hits[0][2]] = [('getlocal0', []), ('getlocal1', []), ('callpropvoid', [m_layout, 1])]
    after[place_p[0][1]] = [('getlocal0', []), ('pushtrue', []), ('callpropvoid', [m_place, 1])]
    for seq in place_o:
        after[seq[2]] = [('getlocal0', []), ('pushfalse', []), ('callpropvoid', [m_place, 1])]
    patch_body(sim, after, 'uws')
    return abc


CR2W_TABLES = ('strings', 'names', 'imports', 'props', 'chunks', 'buffers', 'embedded')   # as cr2w.checks
CR2W_TABLE_SIZES = (1, 8, 8, 16, 24, 24, 24)


def container_check(orig, out, keep_input_table_crcs=False):
    """The container check of a patched file; raises PatchError, returns the tables whose stored CRC was kept.
    Strict (default; uw_build and the self-tests): every cr2w.checks row of out must pass.
    keep_input_table_crcs (only the public patcher, release plan 3.2): the CRC row of a table that cr2w.rewrap does
    not rewrite (strings, names, imports, props, buffers, embedded) may fail in out only when the same row failed in
    orig with the same stored value and the table's bytes are equal in orig and out, i.e. the other author's stored
    value is kept as they wrote it (UI Remastered Edition stores the props table CRC over 8 of its 16 bytes). Every
    other row (chunk table, chunk data, header CRC, sizes, name hashes) must still pass."""
    bad = [r for r in cr2w.checks(cr2w.CR2W(out)) if r[1] != r[2]]
    if not keep_input_table_crcs:
        if bad:
            raise PatchError('container check failed: %s' % bad[0][0])
        return []
    wi, wo = cr2w.CR2W(orig), cr2w.CR2W(out)
    rows_in = {r[0]: r for r in cr2w.checks(wi)}
    kept = []
    for r in bad:
        table = r[0][len('table '):-len(' crc32')] if r[0].startswith('table ') and r[0].endswith(' crc32') else None
        if table in CR2W_TABLES and table != 'chunks':
            i = CR2W_TABLES.index(table)
            ri = rows_in.get(r[0])
            if ri is not None and ri[1] != ri[2] and ri[1] == r[1] and \
                    wi.table_bytes(i, CR2W_TABLE_SIZES[i]) == wo.table_bytes(i, CR2W_TABLE_SIZES[i]):
                kept.append(table)
                continue
        raise PatchError('container check failed: %s' % r[0])
    return kept


def patch_redswf(orig, keep_input_table_crcs=False):
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
        raise PatchError('the part of the inventory screen it changes is different in this file (%r)' % e)
    container_check(orig, out, keep_input_table_crcs)
    return out


def swf_of(redswf):
    """FWS bytes of a .redswf (for disassembly / verification)"""
    w = cr2w.CR2W(redswf)
    pe, lo, bo, bl, tail = w.swf_layout()
    return inflate_swf(w.chunk_data(0)[bo:bo + bl])


def markers(redswf):
    """{name: value} of uwInvVersion / gcUiVersion slots on MenuInventory"""
    abc = abcrt.ABC(abcrt.swf_abcs(swf_of(redswf))[0][1])
    ci = Ctx(abc).cls('MenuInventory', 'setInventoryMode')
    out = {}
    for t in abc.instances[ci]['traits']:
        n = abc.mn(t.name)
        if n in ('uwInvVersion', 'gcUiVersion') and t.kind == 0:
            out[n] = abc.const(t.vindex, t.vkind)
    return out


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    data = patch_redswf(open(src, 'rb').read())
    open(dst, 'wb').write(data)
    print('wrote', dst, len(data), 'md5', hashlib.md5(data).hexdigest())
