"""AVM2 method-body verifier (structural): operand-stack depth, scope depth, registers, branch targets,
exception table, constant-pool references.  Abstract interpretation over all reachable paths
(entry + every exception handler), merging at branch targets.

  python -I avm2verify.py <swf> [Owner::method ...]     verify the named bodies (or all bodies)

Checks per body:
  * every reachable branch/switch target is an instruction boundary inside the code
  * stack depth is identical on every edge into an instruction (merge consistency), never < 0
  * computed max stack  <= declared max_stack
  * scope depth never < 0, computed max scope <= max_scope_depth - init_scope_depth,
    getscopeobject index < current scope depth
  * register indices < declared local_count
  * control never falls off the end of the code
  * exception entries: from < to <= len, target is a boundary, exc_type/var_name valid multinames
  * every pool index used by an operand is in range (strings, ints, uints, doubles, namespaces,
    multinames, methods, classes)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import abcrt as A  # noqa: E402

# fixed (pops, pushes) for opcodes without multiname/arg-count dependent effects
FIX = {
    0x01: (0, 0), 0x02: (0, 0), 0x03: (1, 0), 0x07: (1, 0), 0x09: (0, 0), 0x1c: (1, 0), 0x1d: (0, 0),
    0x1e: (2, 1), 0x1f: (2, 1), 0x20: (0, 1), 0x21: (0, 1), 0x23: (2, 1), 0x24: (0, 1), 0x25: (0, 1),
    0x26: (0, 1), 0x27: (0, 1), 0x28: (0, 1), 0x29: (1, 0), 0x2a: (1, 2), 0x2b: (2, 2), 0x2c: (0, 1),
    0x2d: (0, 1), 0x2e: (0, 1), 0x2f: (0, 1), 0x30: (1, 0), 0x31: (0, 1), 0x32: (0, 1),
    0x35: (1, 1), 0x36: (1, 1), 0x37: (1, 1), 0x38: (1, 1), 0x39: (1, 1),
    0x3a: (2, 0), 0x3b: (2, 0), 0x3c: (2, 0), 0x3d: (2, 0), 0x3e: (2, 0),
    0x40: (0, 1), 0x47: (0, 0), 0x48: (1, 0), 0x50: (1, 1), 0x51: (1, 1), 0x52: (1, 1), 0x57: (0, 1),
    0x58: (1, 1), 0x5a: (0, 1), 0x62: (0, 1), 0x63: (1, 0), 0x64: (0, 1), 0x65: (0, 1), 0x67: (0, 1),
    0x6c: (1, 1), 0x6d: (2, 0), 0x6e: (0, 1), 0x6f: (1, 0),
    0x70: (1, 1), 0x71: (1, 1), 0x72: (1, 1), 0x73: (1, 1), 0x74: (1, 1), 0x75: (1, 1), 0x76: (1, 1),
    0x77: (1, 1), 0x78: (1, 1), 0x80: (1, 1), 0x81: (1, 1), 0x82: (1, 1), 0x83: (1, 1), 0x84: (1, 1),
    0x85: (1, 1), 0x86: (1, 1), 0x87: (2, 1), 0x88: (1, 1), 0x89: (1, 1),
    0x90: (1, 1), 0x91: (1, 1), 0x92: (0, 0), 0x93: (1, 1), 0x94: (0, 0), 0x95: (1, 1), 0x96: (1, 1),
    0x97: (1, 1), 0xa0: (2, 1), 0xa1: (2, 1), 0xa2: (2, 1), 0xa3: (2, 1), 0xa4: (2, 1), 0xa5: (2, 1),
    0xa6: (2, 1), 0xa7: (2, 1), 0xa8: (2, 1), 0xa9: (2, 1), 0xaa: (2, 1), 0xab: (2, 1), 0xac: (2, 1),
    0xad: (2, 1), 0xae: (2, 1), 0xaf: (2, 1), 0xb0: (2, 1), 0xb1: (2, 1), 0xb2: (1, 1), 0xb3: (2, 1),
    0xb4: (2, 1), 0xc0: (1, 1), 0xc1: (1, 1), 0xc2: (0, 0), 0xc3: (0, 0), 0xc4: (1, 1), 0xc5: (2, 1),
    0xc6: (2, 1), 0xc7: (2, 1), 0xd0: (0, 1), 0xd1: (0, 1), 0xd2: (0, 1), 0xd3: (0, 1), 0xd4: (1, 0),
    0xd5: (1, 0), 0xd6: (1, 0), 0xd7: (1, 0), 0xef: (0, 0), 0xf0: (0, 0), 0xf1: (0, 0), 0xf2: (0, 0),
    0xf3: (0, 1), 0x06: (0, 0), 0x08: (0, 0), 0x60: (0, 1),
    # branches (conditional pop operands)
    0x0c: (2, 0), 0x0d: (2, 0), 0x0e: (2, 0), 0x0f: (2, 0), 0x10: (0, 0), 0x11: (1, 0), 0x12: (1, 0),
    0x13: (2, 0), 0x14: (2, 0), 0x15: (2, 0), 0x16: (2, 0), 0x17: (2, 0), 0x18: (2, 0), 0x19: (2, 0),
    0x1a: (2, 0), 0x1b: (1, 0),
}
REG_OPS = {0x62: 0, 0x63: 0, 0x08: 0, 0x92: 0, 0x94: 0, 0xc2: 0, 0xc3: 0}
REG_FIXED = {0xd0: 0, 0xd1: 1, 0xd2: 2, 0xd3: 3, 0xd4: 0, 0xd5: 1, 0xd6: 2, 0xd7: 3}
TERMINAL = {0x03, 0x10, 0x47, 0x48, 0x1b}


def mn_rt(abc, i):
    """number of runtime operands a multiname needs on the stack"""
    k = abc.mns[i][0]
    if k in (0x0F, 0x10):
        return 1          # RTQName: namespace
    if k in (0x11, 0x12):
        return 2          # RTQNameL: namespace + name
    if k in (0x1B, 0x1C):
        return 1          # MultinameL: name
    return 0


def effect(abc, op, args):
    if op in FIX and op not in (0x06,):
        return FIX[op]
    rt = lambda: mn_rt(abc, args[0])  # noqa: E731
    if op in (0x66,):                      # getproperty
        return 1 + rt(), 1
    if op in (0x61, 0x68):                 # setproperty / initproperty
        return 2 + rt(), 0
    if op == 0x6a:                         # deleteproperty
        return 1 + rt(), 1
    if op == 0x04:                         # getsuper
        return 1 + rt(), 1
    if op == 0x05:                         # setsuper
        return 2 + rt(), 0
    if op == 0x59:                         # getdescendants
        return 1 + rt(), 1
    if op in (0x5d, 0x5e):                 # findpropstrict / findproperty
        return rt(), 1
    if op == 0x5f:                         # finddef
        return 0, 1
    if op in (0x46, 0x4c, 0x45):           # callproperty / callproplex / callsuper
        return 1 + rt() + args[1], 1
    if op in (0x4f, 0x4e):                 # callpropvoid / callsupervoid
        return 1 + rt() + args[1], 0
    if op == 0x4a:                         # constructprop
        return 1 + rt() + args[1], 1
    if op == 0x41:                         # call: function, receiver, args
        return 2 + args[0], 1
    if op == 0x42:                         # construct
        return 1 + args[0], 1
    if op == 0x49:                         # constructsuper
        return 1 + args[0], 0
    if op in (0x43, 0x44):                 # callmethod / callstatic
        return 1 + args[1], 1
    if op == 0x53:                         # applytype
        return 1 + args[0], 1
    if op == 0x55:                         # newobject
        return 2 * args[0], 1
    if op == 0x56:                         # newarray
        return args[0], 1
    if op == 0x06:
        return 0, 0
    raise ValueError('no stack effect for opcode 0x%02x' % op)


def check_pool_refs(abc, op, args, errs, pos):
    name, kinds = A.OPS[op]
    lim = {'mn': len(abc.mns), 'str': len(abc.strings), 'int': len(abc.ints), 'uint': len(abc.uints),
           'dbl': len(abc.doubles), 'ns': len(abc.nss), 'meth': len(abc.methods), 'cls': len(abc.instances)}
    for k, a in zip(kinds, args):
        if k in lim:
            lo = 0 if k in ('meth', 'cls') else 1
            if not (lo <= a < lim[k]):
                errs.append('@%d %s: %s index %d out of range [%d,%d)' % (pos, name, k, a, lo, lim[k]))


def verify_body(abc, b):
    errs = []
    code = b['code']
    try:
        ins = A.decode(code)
    except Exception as ex:  # noqa: BLE001
        return {'errors': ['decode failed: %s' % ex], 'max_stack': None, 'max_scope': None}
    at = {p: k for k, (p, op, args) in enumerate(ins)}
    end = len(code)
    scope_cap = b['max_scope'] - b['init_scope']
    m_ = abc.methods[b['method']] if 'method' in b and b['method'] < len(abc.methods) else None
    if m_ is not None:   # AVM2: the register file holds this + every parameter (+ rest / arguments)
        need = 1 + len(m_['params']) + (1 if m_['flags'] & 0x05 else 0)
        if b['locals'] < need:
            errs.append('locals %d < this + %d parameter(s)%s' % (b['locals'], len(m_['params']),
                                                                    ' + rest/arguments' if m_['flags'] & 0x05 else ''))
    for e in b['exceptions']:
        frm, to, tgt, et, vn = e
        if not (frm in at and (to in at or to == end) and frm < to and tgt in at):
            errs.append('exception entry %r has non-boundary/invalid offsets' % (e,))
        for mi in (et, vn):
            if mi and not (0 < mi < len(abc.mns)):
                errs.append('exception entry %r has bad multiname %d' % (e, mi))
    state = {}   # instruction index -> (stack, scope)
    work = []

    def push_state(idx, st, sc, src):
        if idx is None:
            errs.append('branch from %s to non-boundary' % src)
            return
        if idx in state:
            if state[idx] != (st, sc):
                errs.append('merge mismatch at @%d: %r vs %r (from %s)' % (ins[idx][0], state[idx], (st, sc), src))
            return
        state[idx] = (st, sc)
        work.append(idx)

    push_state(0, 0, 0, 'entry')
    for e in b['exceptions']:
        if e[2] in at:
            push_state(at[e[2]], 1, 0, 'handler')
    mx_st = 0
    mx_sc = 0
    while work:
        k = work.pop()
        st, sc = state[k]
        while True:
            pos, op, args = ins[k]
            check_pool_refs(abc, op, args, errs, pos)
            # registers
            reg = None
            if op in REG_FIXED:
                reg = REG_FIXED[op]
            elif op in REG_OPS:
                reg = args[0]
            elif op == 0x32:
                reg = max(args)
            if reg is not None and reg >= b['locals']:
                errs.append('@%d register %d >= locals %d' % (pos, reg, b['locals']))
            try:
                pops, pushes = effect(abc, op, args)
            except Exception as ex:  # noqa: BLE001
                errs.append('@%d %s' % (pos, ex))
                break
            if st - pops < 0:
                errs.append('@%d %s stack underflow (%d - %d)' % (pos, A.OPS[op][0], st, pops))
                break
            st = st - pops + pushes
            mx_st = max(mx_st, st)
            if op in (0x30, 0x1c):
                sc += 1
            elif op == 0x1d:
                sc -= 1
                if sc < 0:
                    errs.append('@%d popscope below 0' % pos)
                    break
            elif op == 0x65 and args[0] >= sc:
                errs.append('@%d getscopeobject %d >= scope depth %d' % (pos, args[0], sc))
            mx_sc = max(mx_sc, sc)
            kinds = A.OPS[op][1]
            if kinds and kinds[0] == 'br':
                push_state(at.get(args[0]), st, sc, '@%d' % pos)
            elif op == 0x1b:
                push_state(at.get(args[0]), st, sc, '@%d default' % pos)
                for c in args[1]:
                    push_state(at.get(c), st, sc, '@%d case' % pos)
            if op in TERMINAL:
                if op in (0x47, 0x48, 0x03) and st != 0 and False:
                    pass
                break
            k += 1
            if k >= len(ins):
                errs.append('control falls off the end after @%d' % pos)
                break
            if k in state:
                if state[k] != (st, sc):
                    errs.append('merge mismatch at @%d: %r vs %r (fallthrough)' % (ins[k][0], state[k], (st, sc)))
                break
            state[k] = (st, sc)
    if mx_st > b['max_stack']:
        errs.append('computed max stack %d > declared %d' % (mx_st, b['max_stack']))
    if mx_sc > scope_cap:
        errs.append('computed max scope %d > declared max_scope-init_scope %d' % (mx_sc, scope_cap))
    return {'errors': errs, 'max_stack': mx_st, 'max_scope': mx_sc, 'reachable': len(state), 'ins': len(ins)}


def verify_abc_refs(abc):
    """structural reference checks outside method bodies"""
    errs = []
    nm, nmeth, ncls = len(abc.mns), len(abc.methods), len(abc.instances)

    def tr(traits, where):
        for t in traits:
            if not (0 < t.name < nm):
                errs.append('%s: trait name %d' % (where, t.name))
            if t.kind in (0, 6) and not (0 <= t.type_name < nm):
                errs.append('%s: trait type %d' % (where, t.type_name))
            if t.kind in (1, 2, 3) and not (0 <= t.method < nmeth):
                errs.append('%s: trait method %d' % (where, t.method))
            if t.kind == 4 and not (0 <= t.classi < ncls):
                errs.append('%s: trait class %d' % (where, t.classi))
    for ci, (i, c) in enumerate(zip(abc.instances, abc.classes)):
        tr(i['traits'], 'instance %d' % ci)
        tr(c['traits'], 'class %d' % ci)
        if not (0 <= i['iinit'] < nmeth and 0 <= c['cinit'] < nmeth):
            errs.append('class %d init index' % ci)
    for mi, m in enumerate(abc.methods):
        for p in m['params'] + [m['ret']]:
            if not (0 <= p < nm):
                errs.append('method %d param/ret multiname %d' % (mi, p))
    seen = set()
    for b in abc.bodies:
        if not (0 <= b['method'] < nmeth):
            errs.append('body for bad method %d' % b['method'])
        if b['method'] in seen:
            errs.append('duplicate body for method %d' % b['method'])
        seen.add(b['method'])
    # every method that a class trait / init references must have a body (non-native)
    need = set()
    for i, c in zip(abc.instances, abc.classes):
        need.add(c['cinit'])
        if i['flags'] & 0x04:      # interface: instance methods are abstract (no bodies)
            continue
        need.add(i['iinit'])
        for t in i['traits'] + c['traits']:
            if t.kind in (1, 2, 3):
                need.add(t.method)
    missing = [m for m in need if m not in seen and not (abc.methods[m]['flags'] & 0x20)]
    if missing:
        errs.append('methods without bodies: %r' % missing[:10])
    return errs


def run(path, owners=None, quiet=False):
    data = A.load(path)
    abc = A.ABC(A.swf_abcs(data)[0][1])
    own = abc.owners()
    bad = 0
    n = 0
    results = {}
    for b in abc.bodies:
        o = own.get(b['method'], '#%d' % b['method'])
        if owners and o not in owners:
            continue
        r = verify_body(abc, b)
        n += 1
        results[o] = r
        if r['errors']:
            bad += 1
            if not quiet or owners:
                print('FAIL %s: %s' % (o, '; '.join(r['errors'][:5])))
        elif owners:
            print('OK   %-45s max_stack computed %d / declared %d; scope computed %d / declared %d (init %d max %d); locals %d; %d/%d instructions reachable; exceptions %r' % (
                o, r['max_stack'], b['max_stack'], r['max_scope'], b['max_scope'] - b['init_scope'], b['init_scope'],
                b['max_scope'], b['locals'], r['reachable'], r['ins'], b['exceptions']))
    refs = verify_abc_refs(abc)
    return n, bad, refs, results


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    p = sys.argv[1]
    sel = sys.argv[2:] or None
    n, bad, refs, _ = run(p, sel, quiet=not sel)
    print('verified %d bodies, %d with errors; ABC reference errors: %d %s' % (n, bad, len(refs), refs[:5]))
    sys.exit(1 if bad or refs else 0)
