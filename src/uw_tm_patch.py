"""Ultrawide Menus - reforge (transmog) menu patch (core version 3; the reforge code is v2's, only the marker value
changed with the core's v3 blacksmith split): the appearance grid grows BOTH ways. It reaches the
left screen edge, and the 3D Geralt, the reforge panel, the price, the button and the merchant header move right by
whole cells while the grid grows right by the same amount.

The reforge tab of a master blacksmith / armorer (5.0x feature, commonMenu.ws DefineMenuItem('TransmogMenu',
"panel_reforge_title")) is its own menu: CR4TransmogMenu, gameplay\\gui_new\\swf\\repair\\panel_transmog.redswf,
document class TransmogMenu. Works on the vanilla file (r4gui.bundle) and Smooth UI Remastered's (identical layout
code; only frame-script timings differ). ABC only; the core is uw_bs_patch.patch_abc with the TRANSMOG Spec below,
so every rule of that docstring (width model, catch-all handlers, marker + refusal of any earlier version, anchors
found by pattern) applies unchanged. Only what differs is listed here.

Layout at 16:9 (stage units; one-frame root timeline):
  mcPlayerGridModuleRight  RepairGrid (ModuleBlacksmithGrid, the same class as the blacksmith's) at 135.2, 297.55:
                           mcPlayerGrid x 4.75 (9 x 9 cells, grid 139.95..715.95), mcGridMask local 0..695,
                           mcScrollBar 584.25 (invisible), mcSectionTitlesAnchor 292.45
  sections                 the script (transmogMenu.ws SetTransmogSectionDataList, every UpdateData, before the
                           appearance list) pushes ONE section, id 0, columns 0..8, label "": one border box
                           around the grid ("transmog.appear.grid.section" -> TransmogMenu.setAppearSectionsList ->
                           setItemSections + displaySection). With N columns uwSplit makes it 0..N-1.
  mcTabHandler             TransmogTabHandler at 427.5, 194.3: the weapon/armour-type tabs and the LB/RB buttons,
                           laid out centred on its own x (spawnElems); its x = grid centre - 0.45
  frame                    root sprite #604 at 115, 152 (shape #603, 622 x 380: double side lines fading down
                           + top line, bitmaps 441 / 133) around the tabs and the top of the grid
  3D Geralt                mcCharacterModelAnchor (AnchorComponent, x 452.2, y 42.8) and mcCharacterRenderer
                           (W3RenderToTextureHolder, render target 'test_nopack' 1024 x 1024, timeline x 450.7).
                           TransmogMenu.setupCharacterRender (from <init>, i.e. before configUI and before any section
                           push): new CharacterRendererController(renderer), setCenterAnchor(450, 50),
                           setDefaultAnchor(mcCharacterModelAnchor.x, 50), renderer.x/y = anchor.x/y. The controller
                           tweens the renderer to the default anchor in moveToDefault and to the centre anchor in
                           setPlayerStats ('C' stats mode); in the reforge both are unreachable (CR4TransmogMenu
                           has no OnRequestStatsData, so setPlayerStats never runs and _isCentered stays false).
  right of the grid        mcTransmogVis (reforge panel 1188..1810, its own #604 inside; ModuleTransmogVis only lays
                           out its own children), price_frame 1357..1629.2, txtPriceLabel 1372.3, txtPriceValue
                           1457.2, mcCoinIcon 1587.35, btnExecute 1412..1568, moduleMerchantInfo (header
                           1204.05..1794.6); right-most: mcTransmogVis, RIGHT_END 1810 (vanilla right margin 110).
                           No code writes their x (checked in the decompiled code of both bases).
Data: "transmog.appear.list.update" -> updateTransmogAppearList (removeAllItemData + updateItemData per item); the
renderers it fills are spawned after the section push cleared them, i.e. with the widened draw bounds.

Width model (uw_bs_patch): eL = floor((139.95 - 115.2 - rx)/64), eR = floor((x1 - 110 - 1810)/64), both clamped
0..17; default setting computes against the 21:9 rect. 3440x1440 / 2560x1080 / wider by default: 5 / 5, N 19;
5120x1440 "32:9": 15 / 15, N 39; 2:1: 2 / 1, N 12.

Changes (dL = 64*eL, S_R = 64*eR; nothing at all at 16:9):
  * mcPlayerGrid.columns = 9 + eL + eR, x -= dL (left end 139.95 - dL, right end 715.95 + S_R);
    mcSectionTitlesAnchor.x -= dL (the box follows); mcScrollBar.x += S_R; mcGridMask left bound -dL, right end
    + S_R; updateRendererBounds() at menu y 0 (showAnimation slide-in)
  * uwShift(S_R, RIGHT_X = 1100, x1, grid module, mcCharacterModelAnchor, null): every root child whose x (or, for
    a non-container, bounds' left edge) is >= 1100 moves by exactly S_R, none limited: mcTransmogVis, price_frame,
    txtPriceLabel, txtPriceValue, mcCoinIcon, btnExecute, moduleMerchantInfo. The 3D objects (x 450.7 / 452.2;
    containers, so never selected by their bounds) and CoreMenu's run-time tooltip / drag layers are never caught.
  * uwGeralt(S_R): mcCharacterModelAnchor.x += S_R; mcCharacterRenderer.x = mcCharacterModelAnchor.x (vanilla's own
    rule from setupCharacterRender); _rendererController.setDefaultAnchor(anchor.x, <y literal of
    setupCharacterRender, 50>) so a later moveToDefault would return to the moved place (the inventory's 'C'-mode
    fix). The centre anchor (450, 50) is left alone (stats mode, unreachable here). Geralt's picture is the render
    texture inside the renderer, so it moves with it; the gap Geralt -> reforge panel stays vanilla's.
  * mcTabHandler.x, tooltipAnchor.x += (S_R - dL)/2: the tabs and the gamepad default tooltip anchor (423.5, 274.45;
    ContextInfoManager reads its x/y each time a gamepad tooltip opens) stay centred over the grid. CoreMenu sorts
    its modules by x only once, in initModules (on ADDED_TO_STAGE, before configUI), so the LB/RB module order is
    the vanilla one. 21:9: eL = eR, so they do not move at all.
  * frame #604 (bounds window x 110..120, width 615..630, height 370..390): left end -dL, right end +S_R (x-scale
    2.03 at 21:9, 4.09 at the 32:9 setting). #604 carries a DefineScalingGrid (9-slice, x 17..603 of 622) with the
    side textures and corner hooks in the fixed outer slices, so they should keep vanilla's width; only the top
    line stretches (unlike the inventory's stash frame #612, which has no scaling grid).
  * hook: TransmogMenu.setAppearSectionsList, right after "getlocal0; pushscope": uwSections(arr).

Added to TransmogMenu: uwTmVersion:int = 3 (marker = core VERSION; 2 in v0.5), uwWide, uwCols, uwEL, uwER, uwDone and
the methods uwSections, uwSetup, uwSplit, uwWiden, uwShift, uwGeralt (see uw_bs_patch). The TRANSMOG Spec has no
fixed_first, so uwSplit keeps the even rule (one section: columns 0..N-1).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uw_bs_patch as core  # noqa: E402
from uw_map_patch import PatchError  # noqa: E402,F401

VERSION = core.VERSION
DEPOT = 'gameplay\\gui_new\\swf\\repair\\panel_transmog.redswf'
TRANSMOG = core.Spec('reforge', 'TransmogMenu', 'setAppearSectionsList', 'mcPlayerGridModuleRight', 'uwTmVersion',
                     [('frame lines #604', (110, 120), (615, 630), (370, 390))],
                     ['mcTabHandler', 'tooltipAnchor'], DEPOT, right_end=1810.0, right_x=1100.0,
                     geralt=('mcCharacterModelAnchor', 'mcCharacterRenderer', '_rendererController',
                             'setupCharacterRender'))


def patch_abc(abc):
    return core.patch_abc(abc, TRANSMOG)


def patch_redswf(orig, keep_input_table_crcs=False):
    return core.patch_redswf(orig, TRANSMOG, keep_input_table_crcs)


def markers(redswf):
    return core.markers(redswf, TRANSMOG)


swf_of = core.swf_of


if __name__ == '__main__':
    src_, dst = sys.argv[1], sys.argv[2]
    data = patch_redswf(open(src_, 'rb').read())
    open(dst, 'wb').write(data)
    print('wrote', dst, len(data), 'md5', hashlib.md5(data).hexdigest())
