"""Ultrawide Menus Patcher - keeps your other UI mods working with Ultrawide Menus.

Ultrawide Menus replaces four screen files: the world map, the inventory (also shop, loot container and stash),
the blacksmith and the reforge. A world map that already has the full-width map built in (Map Quest Insight 1.6.2
or later) is left out, so that mod's map loads. The main file's copies are built from the game's own files, so another mod that replaces the
same files (for example Gear Compare, Smooth UI Remastered or Recent Loot Tab) loses its changes to these screens.

For each of the three screens this patcher takes the copy the game would load if Ultrawide Menus were not
installed, adds the ultrawide changes to it and saves the result in Ultrawide Menus' folder. Both mods' changes
then load from that one file. Nothing of the other mods is changed or redistributed: the patching happens on your
PC, with your copy of those mods. A screen whose copy cannot be patched is left out of Ultrawide Menus' folder, so
the other mod's file loads unchanged; the patcher says so.

Usage (double-click, or from a command prompt):
  UltrawideMenusPatcher.exe                          interactive
  UltrawideMenusPatcher.exe --game "D:\\Games\\The Witcher 3" --yes
  UltrawideMenusPatcher.exe --vanilla --yes          back to the game's own screens (undo)
Exit codes: 0 done (or nothing to do), 1 done, but one or more screens were left out, 2 stopped before writing
anything, 3 unexpected error.
Test options: --out <folder> (write the result there instead of Mods\\mod0000_UltrawideMenus; it must be outside
the game folder), --mods-dir, --docs-dir, --modio-dir, --skip <Mods folder>.
Writes only inside Ultrawide Menus' folder (or --out): content\\blob0.bundle, content\\metadata.store,
UltrawideMenusPatcher.txt and patcher_backup\\<date-time>. Never the script, the strings, other mods or the game.
"""
import argparse
import ctypes
import datetime
import glob
import hashlib
import os
import re
import shutil
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w3bundle      # noqa: E402
import w3meta        # noqa: E402
import uw_inv_patch  # noqa: E402
import uw_bs_patch   # noqa: E402
import uw_tm_patch   # noqa: E402
import abcrt         # noqa: E402
import avm2verify    # noqa: E402
import uw_map_patch  # noqa: E402
from uw_map_patch import PatchError  # noqa: E402

VERSION = '1.0.0'
UW_FOLDER = 'mod0000_UltrawideMenus'
SCRIPT_DIR = os.path.join('content', 'scripts', 'local')
SCRIPT = 'uwMenus.ws'            # the script of the 1.0.0 main file
OLD_SCRIPT = 'uwMap.ws'          # the script of the test builds; with both installed the game does not start
RECORD = 'UltrawideMenus.txt'    # the main file's build record
REPORT = 'UltrawideMenusPatcher.txt'
BACKUP = 'patcher_backup'
GAME_EXE = 'witcher3.exe'
MODIO_GAME_ID = '8254'
VANILLA_INV = os.path.join('content', 'content0', 'bundles', 'startup.bundle')
VANILLA_GUI = os.path.join('content', 'content0', 'bundles', 'r4gui.bundle')
GC_REBUILD = ('Gear Compare Patcher used Ultrawide Menus\' inventory as its source. Run Gear Compare Patcher '
              'again and pick your other inventory mod by number (or v if you have none), then run this patcher '
              'again.')


class Page:
    def __init__(self, label, screens, mod, vanilla, marker):
        self.label, self.screens, self.mod, self.vanilla, self.marker = label, screens, mod, vanilla, marker
        self.depot = mod.DEPOT
        self.key = mod.DEPOT.lower()
        self.short = mod.DEPOT.split('\\')[-1]


class MapMod:
    """the world map page: uw_map_patch with the interface the other pages' modules have"""
    DEPOT = uw_map_patch.DEPOT
    VERSION = 1                  # uwApi

    @staticmethod
    def markers(redswf):
        """{uwApi: 1} for a map with the ultrawide map code, plus qmiUwApi for Map Quest Insight's own copy of it"""
        abc = abcrt.ABC(abcrt.swf_abcs(uw_inv_patch.swf_of(redswf))[0][1])
        ci = next(i for i, ins in enumerate(abc.instances) if abc.mn(ins['name']) == 'MapMenu')
        names = {abc.mn(t.name) for t in abc.instances[ci]['traits']}
        return {n: 1 for n in ('uwApi', 'qmiUwApi') if n in names}

    @staticmethod
    def patch_redswf(orig, keep_input_table_crcs=False):
        """uw_map_patch.patch_redswf, with the inventory's container check (keep_input_table_crcs: another author's
        stored table CRC is kept as they wrote it, e.g. UI Remastered Edition)"""
        if not keep_input_table_crcs:
            return uw_map_patch.patch_redswf(orig)
        M = uw_map_patch
        try:
            w = M.cr2w.CR2W(orig)
            pe, lo, bo, bl, tail = w.swf_layout()
            fws = M.inflate_swf(w.chunk_data(0)[bo:bo + bl])
            abcs = abcrt.swf_abcs(fws)
            if len(abcs) != 1:
                raise PatchError('expected 1 code block, found %d' % len(abcs))
            abc = M.patch_abc(abcrt.ABC(abcs[0][1]))
            new_abc = abc.serialize()
            abcrt.ABC(new_abc)
            out, _ = M.cr2w.rewrap(orig, abcrt.replace_abc(fws, new_abc))
        except PatchError:
            raise
        except (AssertionError, StopIteration, ValueError, KeyError, IndexError) as e:
            raise PatchError('the part of the map screen it changes is different in this file (%r)' % e)
        uw_inv_patch.container_check(orig, out, True)
        return out


PAGES = (Page('World map', 'world map', MapMod, VANILLA_GUI, 'uwApi'),
         Page('Inventory', 'inventory, shop, loot container, stash', uw_inv_patch, VANILLA_INV, 'uwInvVersion'),
         Page('Blacksmith', 'blacksmith, armorer, runewright', uw_bs_patch, VANILLA_GUI, 'uwBsVersion'),
         Page('Reforge', 'reforge', uw_tm_patch, VANILLA_GUI, 'uwTmVersion'))


# ------------------------------------------------------------------------------------------- small helpers
def say(msg=''):
    print(msg, flush=True)


def ask(prompt, default='', eof=None):
    """the answer, default for an empty answer, eof (default: default) when there is no input at all"""
    try:
        v = input(prompt).strip()
    except EOFError:
        return default if eof is None else eof
    return v or default


def md5(b):
    return hashlib.md5(b).hexdigest()


def documents_dir():
    """The real Documents folder (OneDrive-redirected included)."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16),
                        ('d', ctypes.c_ubyte * 8)]
        fid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        p = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(p)) == 0:
            path = p.value
            ctypes.windll.ole32.CoTaskMemFree(p)
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


def is_game_dir(d):
    return bool(d) and os.path.isdir(os.path.join(d, 'content', 'content0')) and os.path.isdir(os.path.join(d, 'bin'))


def find_game_dir():
    """The patcher's own folder and its parents, then Steam (every library) and GOG. Only reads the registry."""
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    d = here
    for _ in range(5):
        if is_game_dir(d):
            return d
        d = os.path.dirname(d)
    cands = []
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                               (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key) as k:
                    steam = winreg.QueryValueEx(k, val)[0]
                libs = [steam]
                vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
                if os.path.isfile(vdf):
                    libs += [m.replace('\\\\', '\\') for m in re.findall(
                        r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='replace').read())]
                cands += [os.path.join(lib, 'steamapps', 'common', 'The Witcher 3') for lib in libs]
            except OSError:
                pass
        for key in (r'SOFTWARE\WOW6432Node\GOG.com\Games\1495134320',
                    r'SOFTWARE\WOW6432Node\GOG.com\Games\1207664663'):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                    cands.append(winreg.QueryValueEx(k, 'path')[0])
            except OSError:
                pass
    except ImportError:
        pass
    for c in cands:
        if is_game_dir(c):
            return os.path.normpath(c)
    return None


def running_processes():
    """Lower-case file names of the running processes, or None if the list cannot be read."""
    try:
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                        ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                        ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32FirstW.restype = wintypes.BOOL
        k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32NextW.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)                    # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:
            return None
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            names = set()
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                names.add(e.szExeFile.lower())
                ok = k32.Process32NextW(snap, ctypes.byref(e))
            return names or None
        finally:
            k32.CloseHandle(snap)
    except Exception:
        return None


def game_running(exe=GAME_EXE):
    """True / False, or None if the process list cannot be read."""
    names = running_processes()
    return None if names is None else exe.lower() in names


def stop_if_running(exe):
    """True (and a message) when the game runs; a note when that cannot be checked."""
    r = game_running(exe)
    if r:
        say('')
        say('The Witcher 3 is running (%s). Close the game, then run this patcher again.' % exe)
        say('Nothing was changed.')
        return True
    if r is None:
        say('Note: could not check whether the game is running. Close it before you continue.')
    return False


# ------------------------------------------------------------------------------------------- load order
def mods_settings(docs):
    """mods.settings -> {mod folder (lower): (enabled, priority or None)}"""
    out = {}
    p = os.path.join(docs, 'The Witcher 3', 'mods.settings')
    if not os.path.isfile(p):
        return out
    cur = None
    for line in open(p, encoding='utf-8-sig', errors='replace'):
        line = line.strip()
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            cur = m.group(1).lower()
            out[cur] = [True, None]
        elif cur and '=' in line:
            k, v = [x.strip() for x in line.split('=', 1)]
            if k.lower() == 'enabled':
                out[cur][0] = v != '0'
            elif k.lower() == 'priority':
                try:
                    out[cur][1] = int(v)
                except ValueError:
                    pass
    return {k: tuple(v) for k, v in out.items()}


def order_key(name, settings):
    """Load order: folders with a mods.settings Priority first (lower number first), then the rest by name,
    case-insensitive. The first folder wins a file conflict."""
    pri = settings.get(name.lower(), (True, None))[1]
    return (0, pri, name.lower()) if pri is not None else (1, 0, name.lower())


def local_mods(mods_dir, settings, skip):
    """(enabled Mods folders in load order, disabled ones). Only folders whose name starts with "mod" load."""
    names = [n for n in (os.listdir(mods_dir) if os.path.isdir(mods_dir) else [])
             if os.path.isdir(os.path.join(mods_dir, n)) and n.lower().startswith('mod') and n.lower() not in skip]
    enabled = [n for n in names if settings.get(n.lower(), (True, None))[0]]
    disabled = sorted([n for n in names if n not in enabled], key=str.lower)
    return sorted(enabled, key=lambda n: order_key(n, settings)), disabled


def content_bundles(content):
    if not os.path.isdir(content):
        return []
    return [os.path.join(content, n) for n in sorted(os.listdir(content), key=str.lower)
            if n.lower().endswith('.bundle') and os.path.isfile(os.path.join(content, n))]


def find_pages(content, problems, keys=None, bad=None):
    """{depot (lower): (bundle path, entry)} of the three screens in one content folder; the first bundle (by name)
    that has a screen wins inside a folder. Only the bundles' tables of contents are read. A bundle that cannot be
    read is reported and its path appended to bad (the screens it may hold are then unknown)."""
    keys = keys or {p.key for p in PAGES}
    out = {}
    for bp in content_bundles(content):
        try:
            b = w3bundle.read_bundle(bp, load_payload=False)
        except Exception as e:
            problems.append('could not read %s (%s)' % (bp, e))
            if bad is not None:
                bad.append(bp)
            continue
        for e in b.entries:
            k = e.name.lower()
            if k in keys and k not in out:
                out[k] = (bp, e)
    return out


def bundle_entry(bp, key):
    """the entry of one depot path in one bundle (table of contents only), or None"""
    try:
        b = w3bundle.read_bundle(bp, load_payload=False)
    except Exception:
        return None
    for e in b.entries:
        if e.name.lower() == key:
            return e
    return None


def read_entry(path, e):
    with open(path, 'rb') as f:
        f.seek(e.offset)
        e.payload = f.read(e.zsize)
    return e.data()


def modio_mods(docs, base):
    """[(label, content folder)] of the enabled mod.io mods. They always load before the Mods folder."""
    cfg = os.path.join(docs, 'The Witcher 3', 'modioModsConfig.json')
    enabled = None
    if os.path.isfile(cfg):
        txt = open(cfg, encoding='utf-8', errors='replace').read()
        enabled = {m.group(1) for m in re.finditer(r'"modID"\s*:\s*(\d+)\s*,\s*"isEnabled"\s*:\s*true', txt)}
    hits = []
    for mod_id in (sorted(os.listdir(base)) if os.path.isdir(base) else []):
        if enabled is not None and mod_id not in enabled:
            continue
        for content in sorted(glob.glob(os.path.join(base, mod_id, '*', '*', 'content'))):
            hits.append(('%s (mod.io %s)' % (os.path.basename(os.path.dirname(content)), mod_id), content))
    return hits


# ------------------------------------------------------------------------------------------- the installed mod
def find_uw(mods_dir):
    """(Ultrawide Menus' folder name or None, [problems that must stop a real run], record version or None)"""
    names = [n for n in (os.listdir(mods_dir) if os.path.isdir(mods_dir) else [])
             if os.path.isdir(os.path.join(mods_dir, n)) and n.lower().startswith('mod')]   # only these load
    new = [n for n in names if os.path.isfile(os.path.join(mods_dir, n, SCRIPT_DIR, SCRIPT))]
    old = [n for n in names if os.path.isfile(os.path.join(mods_dir, n, SCRIPT_DIR, OLD_SCRIPT))]
    named = [n for n in names if n.lower() == UW_FOLDER.lower()]
    problems = []
    if new:
        new.sort(key=lambda n: (n.lower() != UW_FOLDER.lower(), n.lower()))
        uw = new[0]
    else:
        uw = named[0] if named else None
    if len(new) > 1:
        problems.append('%s is in more than one Mods folder (%s). The game does not start with two copies of '
                        'Ultrawide Menus. Keep only one folder, then run this patcher again.' % (SCRIPT, ', '.join(new)))
    if old:
        problems.append('Mods\\%s holds %s, the script of a test build of Ultrawide Menus. Delete that folder '
                        'and extract the Ultrawide Menus %s main file again, then run this patcher again. A test '
                        'build and %s together stop the game from starting.' % (old[0], OLD_SCRIPT, VERSION, SCRIPT))
    if uw is None:
        problems.append('Ultrawide Menus is not installed (no Mods\\%s\\%s\\%s). Install the main file first.' % (
            UW_FOLDER, SCRIPT_DIR, SCRIPT))
    elif not new:
        if not old:
            problems.append('Mods\\%s has no %s\\%s. Extract the Ultrawide Menus %s main file again first.' % (
                uw, SCRIPT_DIR, SCRIPT, VERSION))
    version = None
    if uw:
        try:
            first = open(os.path.join(mods_dir, uw, RECORD), encoding='utf-8', errors='replace').readline()
            m = re.match(r'^Ultrawide Menus (\S+) - build record', first)
            version = m.group(1) if m else None
        except OSError:
            pass
    if version and version.split('.')[:2] != VERSION.split('.')[:2]:
        problems.append('The installed Ultrawide Menus is version %s; this patcher is version %s. Use the patcher '
                        'that matches the main file.' % (version, VERSION))
    return uw, problems, version


# ------------------------------------------------------------------------------------------- per screen
class Result:
    def __init__(self, page):
        self.page = page
        self.source = None        # text: 'Mods\\X\\content\\blob0.bundle' or the game's bundle
        self.folder = None        # Mods folder of the source, None = the game's own file
        self.name = page.depot    # exact entry name of the source
        self.orig = None
        self.data = None          # patched file, None = left out
        self.reason = None
        self.notes = []
        self.warnings = []
        self.shippers = []        # Mods folders shipping this screen (load order; Ultrawide Menus excluded)
        self.modio = []
        self.marked = False       # the source already carries an ultrawide marker
        self.expected = False     # left out on purpose: the loading copy already has it (Map Quest Insight's map)

    def why(self):
        return self.reason.rstrip('.') + '.'

    def fallback(self):
        """what the game loads for a screen that is left out"""
        first = self.modio[0] if self.modio else (self.shippers[0] if self.shippers else None)
        if not first:
            return 'the game\'s own screen loads, not widened'
        return 'the game loads %s\'s copy of this screen unchanged%s' % (first, '' if self.marked else
                                                                         ', not widened')


def safe_markers(page, data):
    try:
        return page.mod.markers(data)
    except Exception:
        return None


def code_check(redswf):
    """The bytecode check the builds pass (avm2verify): [] when every method body and reference is valid, else up to
    three error texts. A patched file from another mod is only used when this is []."""
    abc = abcrt.ABC(abcrt.swf_abcs(uw_inv_patch.swf_of(redswf))[0][1])
    errs = []
    for b in abc.bodies:
        e = avm2verify.verify_body(abc, b)['errors']
        if e:
            errs.append('method %d: %s' % (b['method'], e[0]))
            if len(errs) >= 3:
                return errs
    return errs + avm2verify.verify_abc_refs(abc)[:3]


def analyse(game, uw_name, order, settings, found, modio_found, vanilla, unreadable=()):
    """unreadable: Mods folders (load order) with a bundle that could not be read"""
    results = []
    uw_key = order_key(uw_name or UW_FOLDER, settings)
    for page in PAGES:
        r = Result(page)
        r.shippers = [f for f in order if page.key in found.get(f, {})]
        r.modio = [label for label, hits in modio_found if page.key in hits]
        if not vanilla:
            # a mod whose bundle cannot be read and that loads before the source may hold this screen: unknown
            src_pos = order.index(r.shippers[0]) if r.shippers else len(order)
            doubt = [f for f in unreadable if f in order and order.index(f) <= src_pos]
            if doubt:
                r.reason = ('a bundle of %s could not be read, so it may hold this screen. Fix or disable that mod, '
                            'then run this patcher again' % doubt[0])
                results.append(r)
                continue
        if r.shippers and not vanilla:
            r.folder = r.shippers[0]
            bp, e = found[r.folder][page.key]
            r.source = 'Mods\\%s\\content\\%s' % (r.folder, os.path.basename(bp))
            cs = min(r.shippers)
            if cs != r.folder and all(settings.get(f.lower(), (True, None))[1] is None for f in r.shippers):
                # the game's folder order for names that differ only in letter case / "_" is not confirmed:
                # never guess which copy loads
                r.reason = ('%s and %s both replace this screen, and which one loads first depends on how the game '
                            'sorts upper/lower case and "_" in folder names. Give the one you use a Priority in '
                            'Documents\\The Witcher 3\\mods.settings (a lower number loads first), then run this '
                            'patcher again' % (r.folder, cs))
                results.append(r)
                continue
        else:
            bp = os.path.join(game, page.vanilla)
            r.source = '%s (the game\'s own file)' % page.vanilla
            e = bundle_entry(bp, page.key)
            if e is None:
                r.reason = 'the game\'s own file was not found in %s (is the game version 5.0x, next-gen?)' % \
                    page.vanilla
                results.append(r)
                continue
        say('%s: reading %s ...' % (page.label, r.source))
        try:
            r.name = e.name
            r.orig = read_entry(bp, e)
        except Exception as ex:
            r.reason = 'could not read the file (%s)' % ex
            results.append(r)
            continue
        mk = safe_markers(page, r.orig)
        if mk and page.marker in mk:
            r.marked = True
            if page.mod is MapMod and 'qmiUwApi' in mk:
                r.expected = True
                r.reason = ('%s\'s world map already has the full-width map built in (Map Quest Insight 1.6.2 or later, '
                            'menu page "Ultrawide map"), so it is left out here and that map loads as it is'
                            % (r.folder or 'the game'))
            elif page.mod is uw_inv_patch and 'gcUiVersion' in mk:
                r.reason = 'this file already contains the ultrawide patch. ' + GC_REBUILD
            elif r.folder:
                r.reason = ('this file already contains the ultrawide patch (an old copy of Ultrawide Menus, or a '
                            'file built from it). Remove that copy or reinstall %s, then run this patcher again'
                            % r.folder)
            else:
                r.reason = 'the game\'s own file already contains the ultrawide patch (the game files were changed)'
        else:
            try:
                r.data = page.mod.patch_redswf(r.orig, keep_input_table_crcs=True)
                for t in uw_inv_patch.container_check(r.orig, r.data, True):
                    r.notes.append('%s stores a non-standard checksum for its %s table; kept as is (the game '
                                   'accepts it)' % (r.folder or 'the game\'s file', t))
            except PatchError as ex:
                r.data = None
                r.reason = str(ex) + ('' if r.folder else ' (is the game version 5.0x, next-gen?)')
            except Exception as ex:          # never let one screen stop the others
                r.data = None
                r.reason = 'unexpected error (%r)' % ex
            if r.data is not None:
                try:
                    errs = code_check(r.data)
                except Exception as ex:
                    errs = ['the check could not run (%r)' % ex]
                if errs:
                    r.data = None
                    r.reason = 'the patched file failed the code check (%s)' % '; '.join(errs)
        if r.data is not None and mk and 'gcUiVersion' in mk:
            r.notes.append('includes Gear Compare (gcUiVersion %s)' % mk['gcUiVersion'])
        first = r.shippers[0] if r.shippers else None
        if first and order_key(first, settings) < uw_key:
            r.warnings.append('%s loads before %s, so the game uses %s\'s %s screen, not the wide one. To use '
                              'the wide one, %s must load first: in Documents\\The Witcher 3\\mods.settings, give '
                              'it a Priority that puts it before %s (a lower number loads first).'
                              % (first, uw_name or UW_FOLDER, first, page.label.lower(), uw_name or UW_FOLDER,
                                 first))
        for m in r.modio:
            r.warnings.append('%s replaces the %s screen. mod.io mods load before the Mods folder, so Ultrawide '
                              'Menus\' copy is not used. Disable it in the in-game Mods menu if you want the wide '
                              '%s screen.' % (m, page.label.lower(), page.label.lower()))
        results.append(r)
    return results


def show(results, vanilla, current):
    for r in results:
        say('')
        say('%s (%s): %s' % (r.page.label, r.page.screens, r.page.short))
        if r.shippers:
            say('  Mods that replace it (load order): %s' % ', '.join(r.shippers))
        else:
            say('  No other mod in the Mods folder replaces it.')
        say('  Source: %s%s' % (r.source, '   (you chose the game\'s own screens)' if vanilla and r.shippers else ''))
        if r.data is not None:
            same = current.get(r.page.key) == r.data
            say('  Can be patched: yes%s' % ('   (the same as the file installed now)' if same else ''))
        else:
            if r.expected:
                say('  Not needed: %s' % r.why())
            else:
                say('  Can be patched: NO - %s' % r.why())
                say('  Left out: %s.' % r.fallback())
        for n in r.notes:
            say('  Note: ' + n)
        for w in r.warnings:
            say('  WARNING: ' + w)


# ------------------------------------------------------------------------------------------- writing
def current_entries(target, problems):
    """{depot (lower): data} of the bundle in the target folder now ({} if there is none)"""
    bp = os.path.join(target, 'content', 'blob0.bundle')
    if not os.path.isfile(bp):
        return {}, {}
    try:
        b = w3bundle.read_bundle(bp)
        return {e.name.lower(): e.data() for e in b.entries}, {e.name.lower(): e.name for e in b.entries}
    except Exception as e:
        problems.append('could not read the current %s (%s); it will be replaced' % (bp, e))
        return {}, {}


def build_bundle(results):
    built = [r for r in results if r.data is not None]
    entries = [w3bundle.make_entry(r.name, r.data, w3bundle.COMP_ZLIB) for r in built]
    return w3bundle.build_bundle_bytes(entries, alignment=16, pad_end=False, pad_file_to=0, gap_fill=None)


def restore(content, target, backup, had):
    """Put the previous files back after a failed write. True when every previous file is in place again."""
    ok = True
    for rel, existed in had.items():
        p = os.path.join(target, rel)
        try:
            if existed:
                b = os.path.join(backup, os.path.basename(rel))
                if not (os.path.isfile(p) and open(p, 'rb').read() == open(b, 'rb').read()):
                    shutil.copy2(b, p)
            elif os.path.isfile(p):
                os.remove(p)
        except OSError:
            ok = False
    for n in ('blob0.bundle.new', 'metadata.store.new'):
        try:
            if os.path.isfile(os.path.join(content, n)):
                os.remove(os.path.join(content, n))
        except OSError:
            pass
    return ok


class WriteError(Exception):
    def __init__(self, err, restored):
        super().__init__(str(err))
        self.err, self.restored = err, restored


def install(target, results, bundle_bytes):
    """Backs up, writes and reads back. Returns (backup folder or None, bundle md5 or None, store md5 or None)."""
    content = os.path.join(target, 'content')
    try:
        os.makedirs(content, exist_ok=True)
    except OSError as e:
        raise WriteError(e, True)
    bpath = os.path.join(content, 'blob0.bundle')
    mpath = os.path.join(content, 'metadata.store')
    rels = [os.path.join('content', 'blob0.bundle'), os.path.join('content', 'metadata.store'), REPORT]
    had = {rel: os.path.isfile(os.path.join(target, rel)) for rel in rels}
    backup = None
    if any(had.values()):
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = os.path.join(target, BACKUP, stamp)
        k = 1
        while os.path.exists(backup):
            k += 1
            backup = os.path.join(target, BACKUP, '%s-%d' % (stamp, k))
        try:
            os.makedirs(backup)
            for rel, existed in had.items():
                if existed:
                    shutil.copy2(os.path.join(target, rel), os.path.join(backup, os.path.basename(rel)))
        except OSError as e:                    # nothing of the mod was changed yet
            raise WriteError(e, True)
    built = [r for r in results if r.data is not None]
    try:
        if built:
            with open(bpath + '.new', 'wb') as f:
                f.write(bundle_bytes)
            store = w3meta.write_store(w3meta.generate([('blob0.bundle', bpath + '.new')]))
            with open(mpath + '.new', 'wb') as f:
                f.write(store)
            os.replace(bpath + '.new', bpath)
            os.replace(mpath + '.new', mpath)
            read_back(content, built)
        else:                                   # no screen: no bundle (an empty bundle is not a proven file)
            for p in (bpath, mpath):
                if os.path.isfile(p):
                    os.remove(p)
    except OSError as e:
        raise WriteError(e, restore(content, target, backup, had))
    except BaseException:
        restore(content, target, backup, had)
        raise
    if not built:
        return backup, None, None
    return backup, md5(open(bpath, 'rb').read()), md5(open(mpath, 'rb').read())


def read_back(content, built):
    """The written bundle holds exactly the patched files, each with its marker, each refuses a second patch, and
    metadata.store is the one the bundle gives."""
    bpath = os.path.join(content, 'blob0.bundle')
    back = {e.name: e.data() for e in w3bundle.read_bundle(bpath).entries}
    if sorted(back) != sorted(r.name for r in built):
        raise RuntimeError('read-back: the bundle holds %s' % sorted(back))
    for r in built:
        if back[r.name] != r.data:
            raise RuntimeError('read-back: %s differs' % r.page.label)
        mk = r.page.mod.markers(back[r.name])
        if mk.get(r.page.marker) != r.page.mod.VERSION:
            raise RuntimeError('read-back: %s marker %r' % (r.page.label, mk))
        try:
            r.page.mod.patch_redswf(back[r.name], keep_input_table_crcs=True)
            raise RuntimeError('read-back: %s accepted a second patch' % r.page.label)
        except PatchError:
            pass
    regen = w3meta.write_store(w3meta.generate([('blob0.bundle', bpath)]))
    if regen != open(os.path.join(content, 'metadata.store'), 'rb').read():
        raise RuntimeError('read-back: metadata.store does not match the bundle')


def write_report(target, game, mods_dir, results, vanilla, removed, warnings, backup, bundle_md5, store_md5, notes):
    out = []
    w = out.append
    w('Ultrawide Menus Patcher %s - %s' % (VERSION, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    w('Game folder: %s' % game)
    if os.path.normcase(os.path.abspath(mods_dir)) != os.path.normcase(os.path.join(os.path.abspath(game), 'Mods')):
        w('Mods folder: %s' % mods_dir)
    w('Written to: %s' % os.path.join(target, 'content'))
    w('Built from: %s' % ('the game\'s own screens (you chose v: the same files as the main file)' if vanilla else
                          'the copies the game would load without Ultrawide Menus'))
    built = [r for r in results if r.data is not None]
    if built:
        w('content\\blob0.bundle md5 %s (%d screens)' % (bundle_md5, len(built)))
        w('content\\metadata.store md5 %s' % store_md5)
    else:
        w('content\\blob0.bundle and metadata.store removed: no screen could be patched')
    w('')
    for r in results:
        if r.data is not None:
            w('%s built from: %s (entry md5 %s, patched md5 %s)' % (r.page.label, r.source, md5(r.orig),
                                                                   md5(r.data)))
        else:
            fb = r.fallback()
            w('%s %s: %s' % (r.page.label, 'not needed' if r.expected else 'LEFT OUT', r.why()))
            w('  %s%s.' % (fb[0].upper(), fb[1:]))
        w('  %s (%s)' % (r.name, r.page.screens))
        w('  Mods that replace it (load order): %s%s' % (
            ', '.join(r.shippers) or 'none (the game\'s own file)',
            '; Ultrawide Menus\' copy is loaded instead of all of them' if r.shippers and r.data is not None and
            not r.warnings else ''))
        for n in r.notes:
            w('  Note: %s' % n)
        for x in r.warnings:
            w('  WARNING: %s' % x)
    for name in removed:
        w('Removed from the bundle: %s (not part of Ultrawide Menus %s; the file of the mod that ships it, or the '
          'game\'s own, now loads)' % (name, VERSION))
    for x in warnings:
        w('WARNING: %s' % x)
    for x in notes:
        w('Note: %s' % x)
    w('Previous files: %s' % (backup or 'none (there was nothing to back up)'))
    w('%s in this folder describes the main file as downloaded. This patcher %s blob0.bundle and '
      'metadata.store.' % (RECORD, 'wrote' if built else 'removed'))
    w('')
    w('Run this patcher again after you install, update or remove a mod that changes these screens, and after')
    w('every run of Gear Compare Patcher. Until then the copy here hides that mod\'s newer file.')
    w('To undo: run it and choose v (the game\'s own screens, the same as the main file), or copy the files')
    w('of a %s folder back into content.' % BACKUP)
    with open(os.path.join(target, REPORT), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(out) + '\n')


# ------------------------------------------------------------------------------------------- main work
def run(args):
    say('Ultrawide Menus Patcher %s' % VERSION)
    say('=' * 60)
    game = args.game or find_game_dir()
    while not is_game_dir(game):
        if args.yes or args.game:
            say('Could not find The Witcher 3%s. Pass --game "<game folder>".' % (' in %s' % game if game else ''))
            return 2
        game = ask('Could not find The Witcher 3. Paste the game folder path (the one with "bin" and '
                   '"content"): ').strip('"')
        if not game:
            say('No changes made.')
            return 2
    game = os.path.normpath(os.path.abspath(game))
    say('Game folder: %s' % game)
    if stop_if_running(args.check_process):
        return 2
    mods_dir = os.path.abspath(args.mods_dir) if args.mods_dir else os.path.join(game, 'Mods')
    docs = os.path.abspath(args.docs_dir) if args.docs_dir else documents_dir()
    modio_base = os.path.abspath(args.modio_dir) if args.modio_dir else os.path.join(
        os.environ.get('PUBLIC', r'C:\Users\Public'), 'mod.io', MODIO_GAME_ID, 'mods')
    if args.mods_dir:
        say('Mods folder: %s' % mods_dir)

    uw_name, problems, version = find_uw(mods_dir)
    out = os.path.abspath(args.out) if args.out else None
    if out:
        g = os.path.normcase(game) + os.sep
        if os.path.normcase(out + os.sep).startswith(g):
            say('--out must be a folder outside the game folder.')
            return 2
        say('Test mode: the result goes to %s; nothing is written in the game folder.' % out)
        for p in problems:
            say('Note (test mode, not stopped): ' + p)
        target = out
    else:
        if problems:
            say('')
            for p in problems:
                say(p)
            say('Nothing was changed.')
            return 2
        target = os.path.join(mods_dir, uw_name)
    if uw_name:
        say('Ultrawide Menus: Mods\\%s%s' % (uw_name, ' (main file %s)' % version if version else ''))

    settings = mods_settings(docs)
    skip = {s.lower() for s in args.skip} | {UW_FOLDER.lower()} | ({uw_name.lower()} if uw_name else set())
    order, disabled = local_mods(mods_dir, settings, skip)
    general = []          # warnings for the screen and the report
    scan_notes = []
    if uw_name and not settings.get(uw_name.lower(), (True, None))[0]:
        general.append('mods.settings disables %s (Enabled=0), so the game does not load it.' % uw_name)
    if args.skip:
        scan_notes.append('treated as not installed (--skip): %s' % ', '.join(args.skip))
    found = {}
    unreadable = []
    for f in order:
        bad = []
        hits = find_pages(os.path.join(mods_dir, f, 'content'), scan_notes, bad=bad)
        if hits:
            found[f] = hits
        if bad:
            unreadable.append(f)
    modio_found = []
    for label, content in modio_mods(docs, modio_base):
        hits = find_pages(content, scan_notes)
        if hits:
            modio_found.append((label, hits))

    vanilla = args.vanilla
    say('')
    say('Reading the screens the game would load without Ultrawide Menus%s ...' % (
        ' (you chose the game\'s own screens)' if vanilla else ''))
    results = analyse(game, uw_name, order, settings, found, modio_found, vanilla, unreadable)
    cur_problems = []
    current, current_names = current_entries(target, cur_problems)
    show(results, vanilla, current)
    for x in general:
        say('')
        say('WARNING: ' + x)
    for x in scan_notes + cur_problems:
        say('Note: ' + x)

    if not args.yes and not args.dry_run:
        built = [r for r in results if r.data is not None]
        say('')
        say('What should be written to %s?' % (('Mods\\%s' % uw_name) if not out else out))
        if built:
            say('  [Enter] the %s above%s' % ('screens' if len(built) > 1 else 'screen',
                                            ' (recommended)' if not vanilla else ''))
        else:
            say('  [Enter] no screen can be patched: remove Ultrawide Menus\' screen files, so the other mods\' '
                'files load')
        if not vanilla:
            say('  v       the game\'s own screens instead (undo: the same files as the main file)')
        say('  q       quit without changes')
        while True:
            c = ask('> ', '', eof='q').lower()          # no input at all (no console): quit, never write
            if c in ('', 'q') or (c == 'v' and not vanilla):
                break
            say('Press Enter%s or type q.' % (', type v' if not vanilla else ''))
        if c == 'q':
            say('No changes made.')
            return 0
        if c == 'v':
            vanilla = True
            say('')
            say('Reading the game\'s own screens ...')
            results = analyse(game, uw_name, order, settings, found, modio_found, vanilla, unreadable)
            show(results, vanilla, current)

    left_out = [r for r in results if r.data is None and not r.expected]
    keys = {p.key for p in PAGES}
    removed = sorted(current_names[k].split('\\')[-1] for k in current if k not in keys)
    built = [r for r in results if r.data is not None]
    bundle_bytes = build_bundle(results) if built else None
    cur_bundle = os.path.join(target, 'content', 'blob0.bundle')
    cur_store = os.path.join(target, 'content', 'metadata.store')
    if removed:
        say('')
        say('Removed from Ultrawide Menus\' bundle: %s (not part of %s; the backup keeps it).' % (
            ', '.join(removed), VERSION))
    if args.dry_run:
        say('')
        say('Dry run: nothing written.')
        return 1 if left_out else 0
    up_to_date = (built and os.path.isfile(cur_bundle) and os.path.isfile(cur_store) and
                  open(cur_bundle, 'rb').read() == bundle_bytes and
                  open(cur_store, 'rb').read() == w3meta.write_store(w3meta.generate([('blob0.bundle', cur_bundle)])))
    if up_to_date or (not built and not os.path.isfile(cur_bundle) and not os.path.isfile(cur_store)):
        say('')
        say('%s\\content already holds exactly these files. Nothing was written.' % target)
        return 1 if left_out else 0
    if stop_if_running(args.check_process):          # again: the game may have been started meanwhile
        return 2
    try:
        backup, bundle_md5, store_md5 = install(target, results, bundle_bytes)
    except WriteError as e:
        say('')
        say('Could not write to %s:' % target)
        say('  %s' % e.err)
        say('The previous files are in place.' if e.restored else
            'Some previous files could not be put back; copy them from the newest %s folder into content.' % BACKUP)
        say('If Windows (Controlled Folder Access) or your antivirus blocked the patcher, allow')
        say('UltrawideMenusPatcher.exe there and run it again.')
        if isinstance(e.err, PermissionError) or getattr(e.err, 'winerror', None) == 5:
            say('If the game is installed in a protected folder (for example Program Files), you can also run the')
            say('patcher as administrator (right-click > Run as administrator).')
        return 2
    try:
        write_report(target, game, mods_dir, results, vanilla, removed, general, backup, bundle_md5, store_md5,
                     scan_notes)
    except OSError as e:
        say('')
        say('Note: the screens were written, but the report %s could not be written (%s).' % (REPORT, e))
    say('')
    if built:
        say('Done. Saved to %s\\content (%s).' % (target, ', '.join(r.page.label for r in built)))
    else:
        say('Done. No screen could be patched, so Ultrawide Menus\' screen files were removed from %s\\content.'
            % target)
    say('Previous files: %s' % (backup or 'none'))
    say('Report: %s' % os.path.join(target, REPORT))
    for r in left_out:
        fb = r.fallback()
        say('Left out: %s. %s%s.' % (r.page.label, fb[0].upper(), fb[1:]))
    say('Start the game to use it. Run this patcher again after you install, update or remove a mod that changes')
    say('these screens, and after every run of Gear Compare Patcher.')
    return 1 if left_out else 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        prog='UltrawideMenusPatcher',
        description='Rebuilds Ultrawide Menus\' inventory, blacksmith and reforge screens from the copies your '
                    'other mods install, so both mods work. Run it with no options for the interactive mode.')
    ap.add_argument('--game', help='The Witcher 3 folder (found automatically if not given)')
    ap.add_argument('--yes', action='store_true', help='no questions: build and write (from your mods, or from '
                                                       'the game\'s own screens with --vanilla)')
    ap.add_argument('--vanilla', action='store_true', help='build from the game\'s own screens (undo)')
    ap.add_argument('--dry-run', action='store_true', help='patch in memory only, write nothing')
    ap.add_argument('--version', action='version', version='Ultrawide Menus Patcher %s' % VERSION)
    # test options (not shown in --help: --out replaces the two files in any folder outside the game; see the
    # module docstring)
    ap.add_argument('--out', metavar='FOLDER', help=argparse.SUPPRESS)
    ap.add_argument('--mods-dir', metavar='FOLDER', help=argparse.SUPPRESS)
    ap.add_argument('--docs-dir', metavar='FOLDER', help=argparse.SUPPRESS)
    ap.add_argument('--modio-dir', metavar='FOLDER', help=argparse.SUPPRESS)
    ap.add_argument('--skip', action='append', default=[], metavar='MODFOLDER', help=argparse.SUPPRESS)
    ap.add_argument('--check-process', default=GAME_EXE, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        code = run(args)
    except KeyboardInterrupt:
        say('\nStopped. Nothing was changed unless "Done" was shown above.')
        code = 3
    except Exception:
        say('\nUnexpected error. Nothing was changed unless "Done" was shown above:')
        say(traceback.format_exc())
        code = 3
    if not args.yes:
        ask('\nPress Enter to close.')
    return code


if __name__ == '__main__':
    sys.exit(main())
