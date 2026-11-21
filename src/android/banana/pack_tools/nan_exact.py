

# ---- Hokkaido (src/android/banana/pack_tools, appended to Banana Native's vk_android_spv.py at build time) ----
# NMin / NMax / NClamp with Maxwell's NaN results written out as IsNan selects, and float controls that keep NaN and Inf, in every module.
# RADV on Xclipse (Galaxy S26) did not keep GLSL.std.450's NaN rules: the froxel fog compute shaders of Mario Kart World and Ocarina of
# Time wrote NaN that the game's FMNMX / saturate guards remove on the Switch, and bloom spread it over the screen (white picture, white blocks)

OP_IS_NAN = 156
GLSL_N_MIN, GLSL_N_MAX, GLSL_N_CLAMP = 79, 80, 81
CAP_SZ_INF_NAN_PRESERVE, MODE_SZ_INF_NAN_PRESERVE = 4466, 4461


def nan_exact_minmax(m):
    """Each float NMin / NMax: the other operand when one is NaN; NClamp: its low bound when x is NaN (saturation's 0). → instructions rewritten"""
    glsl = {x[1] for x in m.ins if x[0] & 0xffff == OP_EXT_INST_IMPORT and string_at(x, 2)[0] == 'GLSL.std.450'}

    def wanted(x):
        return (x[0] & 0xffff == OP_EXT_INST and x[3] in glsl and x[4] in (GLSL_N_MIN, GLSL_N_MAX, GLSL_N_CLAMP)
                and m.op(m.scalar_of(x[1])) == OP_TYPE_FLOAT)
    todo = [x for x in m.ins if wanted(x)]
    if not todo: return 0
    b1 = m.add_type(OP_TYPE_BOOL)
    bools = {}
    for x in todo:
        n = m.types[x[1]][3] if m.op(x[1]) == OP_TYPE_VECTOR else 1
        if n not in bools: bools[n] = b1 if n == 1 else m.add_type(OP_TYPE_VECTOR, b1, n)
    out = []
    for x in m.ins:
        if not wanted(x):
            out.append(x)
            continue
        ty, res = x[1], x[2]
        bt = bools[m.types[ty][3] if m.op(ty) == OP_TYPE_VECTOR else 1]
        t = m.new_id()
        out.append([x[0], ty, t, *x[3:]])
        if x[4] == GLSL_N_CLAMP:
            nx = m.new_id()
            out += [[4 << 16 | OP_IS_NAN, bt, nx, x[5]], [6 << 16 | OP_SELECT, ty, res, nx, x[6], t]]
        else:
            a, b = x[5], x[6]
            na, nb, s = m.new_id(), m.new_id(), m.new_id()
            out += [[4 << 16 | OP_IS_NAN, bt, na, a], [4 << 16 | OP_IS_NAN, bt, nb, b],
                    [6 << 16 | OP_SELECT, ty, s, na, b, t], [6 << 16 | OP_SELECT, ty, res, nb, a, s]]
    m.ins = out
    m.index()
    return len(todo)


def nan_inf_preserve(m):
    """SignedZeroInfNanPreserve for the module's 32-bit floats, so the driver neither assumes away NaN / Inf nor folds the IsNan tests"""
    if not m.entry or not any(x[0] & 0xffff == OP_TYPE_FLOAT and x[2] == 32 for x in m.ins): return False
    fn = m.entry[2]
    if any(x[0] & 0xffff == OP_EXECUTION_MODE and x[1] == fn and x[2] == MODE_SZ_INF_NAN_PRESERVE and x[3] == 32 for x in m.ins): return False
    if CAP_SZ_INF_NAN_PRESERVE not in m.caps:
        at = max(k for k, x in enumerate(m.ins) if x[0] & 0xffff == OP_CAPABILITY) + 1
        m.ins.insert(at, [2 << 16 | OP_CAPABILITY, CAP_SZ_INF_NAN_PRESERVE])
        if m.header[1] < 0x00010400 and 'SPV_KHR_float_controls' not in m.exts:
            s = lit_string('SPV_KHR_float_controls')
            m.ins.insert(at + 1, [(1 + len(s)) << 16 | OP_EXTENSION, *s])
    at = max(k for k, x in enumerate(m.ins) if x[0] & 0xffff in (OP_ENTRY_POINT, OP_EXECUTION_MODE)) + 1
    m.ins.insert(at, [4 << 16 | OP_EXECUTION_MODE, fn, MODE_SZ_INF_NAN_PRESERVE, 32])
    m.index()
    return True


HK_SAMPLE_OPS = {87, 88, 91, 92, 95}   # OpImageSample(Proj)(Implicit|Explicit)Lod, OpImageFetch
HK_OP_ALL, HK_OP_COMPOSITE_CONSTRUCT = 155, 80
ASTC_ERROR = (1.0, 0.0, 1.0, 1.0)


def astc_error_to_zero(m):
    """A float4 texel read as ASTC's error colour (1, 0, 1, 1) is 0 instead. Storage the game never filled reads as zero blocks, which the
    Switch samples as 0 and RADV on Xclipse decodes as the error colour: Mario Kart World's terrain arrays and Ocarina of Time's distant
    textures came out magenta. → reads rewritten"""
    f32 = m.find_type(OP_TYPE_FLOAT, 32)
    v4 = m.find_type(OP_TYPE_VECTOR, f32, 4) if f32 is not None else None
    if v4 is None: return 0

    def wanted(x): return x[0] & 0xffff in HK_SAMPLE_OPS and x[1] == v4
    todo = sum(1 for x in m.ins if wanted(x))
    if not todo: return 0
    mag, zero = vec4_const(m, f32, ASTC_ERROR), vec4_const(m, f32, (0.0, 0.0, 0.0, 0.0))
    b1 = m.add_type(OP_TYPE_BOOL)
    b4 = m.add_type(OP_TYPE_VECTOR, b1, 4)
    out = []
    for x in m.ins:
        if not wanted(x):
            out.append(x)
            continue
        t, eq, al, c4 = m.new_id(), m.new_id(), m.new_id(), m.new_id()
        out += [[x[0], v4, t, *x[3:]], [5 << 16 | OP_FORD_EQUAL, b4, eq, t, mag], [4 << 16 | HK_OP_ALL, b1, al, eq],
                [7 << 16 | HK_OP_COMPOSITE_CONSTRUCT, b4, c4, al, al, al, al], [6 << 16 | OP_SELECT, v4, x[2], c4, zero, t]]
    m.ins = out
    m.index()
    return todo


HK_TERMINATORS = {249, 250, 251, 252, 253, 254, 255, 4416}
HK_OP_LABEL, HK_OP_PHI, HK_OP_BRANCH, HK_OP_BRANCH_COND, HK_OP_SEL_MERGE, HK_OP_LOOP_MERGE = 248, 245, 249, 250, 247, 246
HK_OP_SAMPLED_IMAGE, HK_OP_QUERY_LOD, HK_OP_FLESS, HK_OP_LAND, HK_OP_FADD, HK_OP_VSHUF, HK_OP_CEXTRACT = 86, 105, 184, 167, 129, 79, 81
HK_IMAGE_OPERANDS = [(0x1, 1), (0x2, 1), (0x4, 2), (0x8, 1), (0x10, 1), (0x20, 1), (0x40, 1), (0x80, 1)]
GLSL_FLOOR = 8
PINK_EPS = 0.02


def _hk_f32(v): return struct.unpack('<I', struct.pack('<f', v))[0]


def _hk_composite(m, ty, ids):   # a constant composite of these constants (an existing one, else a new declaration)
    for x in m.ins:
        if x[0] & 0xffff == OP_CONSTANT_COMPOSITE and x[1] == ty and x[3:] == list(ids): return x[2]
    c = m.new_id()
    m._insert_decl([(3 + len(ids)) << 16 | OP_CONSTANT_COMPOSITE, ty, c, *ids])
    return c


def mip_error_split(m):
    """In a pixel shader, a float4 implicit-lod sample with any trace of ASTC's error colour (green under red and under blue) is read again in a branch, the
    texels that read as the error colour left out. A 2D (array) texture's four texels of the finer level are fetched and weighted as bilinear filtering does,
    without those: an edge between storage the game filled and storage it never did came out pink. When all four are, the coarser level, else the base level,
    else 0; when none is, the sample as it was (the finer level alone when the coarser one has a trace). Other textures: their two levels apart, one that reads
    as the error colour left out. Samples with no trace run as before; a sample in a loop header block is left as it is. → samples rewritten"""
    if m.model != 'ps': return 0
    f32 = m.find_type(OP_TYPE_FLOAT, 32)
    v4 = m.find_type(OP_TYPE_VECTOR, f32, 4) if f32 is not None else None
    if v4 is None: return 0

    def deftypes(): return {x[2]: x[1] for x in m.ins if x[0] & 0xffff in (OP_LOAD, HK_OP_SAMPLED_IMAGE, HK_OP_PHI, OP_COPY_OBJECT, OP_SELECT) and len(x) > 2}
    deftype = deftypes()

    def plan(x):   # (image type, dim, arrayed, explicit operand mask, offset operand ids, the integer offset id or None, texel path) of a sample this rewrites
        if x[0] & 0xffff != 87 or x[1] != v4: return None
        st = m.types.get(deftype.get(x[3]))
        if not st or st[0] & 0xffff != OP_TYPE_SAMPLED_IMAGE: return None
        im = m.types.get(st[2])
        if not im or im[0] & 0xffff != OP_TYPE_IMAGE or im[3] not in (0, 1, 2, 3) or im[4] == 1 or im[6] or im[2] != f32: return None
        mask, ops, k = (x[5], x[6:], 0) if len(x) > 5 else (0, [], 0)
        if mask & ~0xb9: return None   # Bias, ConstOffset, Offset, ConstOffsets, MinLod only
        offs, ioff = [], None
        for bit, n in HK_IMAGE_OPERANDS:
            if mask & bit:
                if bit in (0x8, 0x10, 0x20): offs += ops[k:k + n]
                if bit in (0x8, 0x10): ioff = ops[k]
                k += n
        return (st[2], im[3], im[5], 0x2 | (mask & 0x38), offs, ioff, im[3] == 1 and not mask & 0x20)

    if not any(plan(x) for x in m.ins): return 0
    if 50 not in m.caps:   # ImageQuery (the translator declares it in every module)
        m.ins.insert(max(k for k, x in enumerate(m.ins) if x[0] & 0xffff == OP_CAPABILITY) + 1, [2 << 16 | OP_CAPABILITY, 50])
        m.index()
    glsl = ensure_glsl(m)
    b1 = m.add_type(OP_TYPE_BOOL)
    b4 = m.add_type(OP_TYPE_VECTOR, b1, 4)
    v2 = m.add_type(OP_TYPE_VECTOR, f32, 2)
    v3 = m.add_type(OP_TYPE_VECTOR, f32, 3)
    i32 = m.add_type(OP_TYPE_INT, 32, 1)
    iv2, iv3 = m.add_type(OP_TYPE_VECTOR, i32, 2), m.add_type(OP_TYPE_VECTOR, i32, 3)
    c0, c1, ceps = m.add_const(f32, 0), m.add_const(f32, _hk_f32(1.0)), m.add_const(f32, _hk_f32(PINK_EPS))
    i0, i1 = m.add_const(i32, 0), m.add_const(i32, 1)
    half2 = _hk_composite(m, v2, [m.add_const(f32, _hk_f32(0.5))] * 2)
    corner = {d: _hk_composite(m, iv2, [i1 if d[0] else i0, i1 if d[1] else i0]) for d in ((0, 0), (1, 0), (0, 1), (1, 1))}
    mag, zero = vec4_const(m, f32, ASTC_ERROR), vec4_const(m, f32, (0.0, 0.0, 0.0, 0.0))
    deftype = deftypes()
    valtype = {x[2]: x[1] for x in m.ins if len(x) > 2 and ((x[0] & 0xffff) in (12, 43, 44, 61, 79, 80, 81, 82, 83, 169, 245) or 109 <= (x[0] & 0xffff) <= 201)}
    loop_blocks, lab = set(), None
    for x in m.ins:
        if x[0] & 0xffff == HK_OP_LABEL: lab = x[1]
        elif x[0] & 0xffff == HK_OP_LOOP_MERGE: loop_blocks.add(lab)
    out, tail, n, cur, orig, own = [], {}, 0, None, None, set()

    def e(op, ty, *words):   # emit an instruction with a result; → its id
        r = m.new_id()
        out.append([(3 + len(words)) << 16 | op, ty, r, *words])
        return r

    def glsl_op(ty, inst, *args): return e(OP_EXT_INST, ty, glsl, inst, *args)

    def trace(v):   # any trace of the error colour: green under red and under blue
        r, g, b = (e(HK_OP_CEXTRACT, f32, v, i) for i in range(3))
        ge = e(HK_OP_FADD, f32, g, ceps)
        return e(HK_OP_LAND, b1, e(HK_OP_FLESS, b1, ge, r), e(HK_OP_FLESS, b1, ge, b))

    def is_error(v): return e(HK_OP_ALL, b1, e(OP_FORD_EQUAL, b4, v, mag))

    def wide(b): return e(HK_OP_COMPOSITE_CONSTRUCT, b4, b, b, b, b)

    def pick(b, yes, no): return e(OP_SELECT, v4, wide(b), yes, no)

    for x in m.ins:
        op = x[0] & 0xffff
        if op == HK_OP_LABEL: cur = orig = x[1]
        p = plan(x) if cur is not None and orig not in loop_blocks else None
        if not p:
            out.append(x)
            if op in HK_TERMINATORS: cur = None
            continue
        imty, dim, arrayed, emask, offs, ioff, texels = p
        simg, coord = x[3], x[4]
        s0 = e(x[0] & 0xffff, v4, *x[3:])
        cond = trace(s0)
        fix, merge = m.new_id(), m.new_id()
        out += [[3 << 16 | HK_OP_SEL_MERGE, merge, 0], [4 << 16 | HK_OP_BRANCH_COND, cond, fix, merge], [2 << 16 | HK_OP_LABEL, fix]]
        comps = {0: 1, 1: 2, 2: 3, 3: 3}[dim]
        ct = m.types.get(valtype.get(coord))
        ncomp = ct[3] if ct and ct[0] & 0xffff == OP_TYPE_VECTOR else 1

        def first(k):   # the coordinate's first k components
            if ncomp == k: return coord
            return e(HK_OP_CEXTRACT, f32, coord, 0) if k == 1 else e(HK_OP_VSHUF, {2: v2, 3: v3}[k], coord, coord, *range(k))
        coord_q = first(comps)
        lvl = e(HK_OP_CEXTRACT, f32, e(HK_OP_QUERY_LOD, v2, simg, coord_q), 0)
        lo = glsl_op(f32, GLSL_FLOOR, lvl)
        hi = e(HK_OP_FADD, f32, lo, c1)

        def level(lod): return e(88, v4, simg, coord, emask, lod, *offs)
        s_lo, s_hi, s_base = level(lo), level(hi), level(c0)
        hi_bad, base_bad = is_error(s_hi), is_error(s_base)
        coarser = pick(hi_bad, pick(base_bad, zero, s_base), s_hi)
        if texels:
            img = e(100, imty, simg)
            lo_i = e(110, i32, lo)
            size = e(103, iv3 if arrayed else iv2, img, lo_i)
            size2 = e(HK_OP_VSHUF, iv2, size, size, 0, 1) if arrayed else size
            uv = first(2)
            t = e(131, v2, e(133, v2, uv, e(111, v2, size2)), half2)
            fl = glsl_op(v2, GLSL_FLOOR, t)
            fr = e(131, v2, t, fl)
            ib = e(110, iv2, fl)
            if ioff is not None: ib = e(128, iv2, ib, ioff)
            top = e(130, iv2, size2, corner[(1, 1)])
            if arrayed:
                layers = e(HK_OP_CEXTRACT, i32, size, 2)
                layer = glsl_op(i32, 45, e(110, i32, glsl_op(f32, 2, e(HK_OP_CEXTRACT, f32, coord, 2))), i0, e(130, i32, layers, i1))
            fx, fy = e(HK_OP_CEXTRACT, f32, fr, 0), e(HK_OP_CEXTRACT, f32, fr, 1)
            gx, gy = e(131, f32, c1, fx), e(131, f32, c1, fy)
            weights = {(0, 0): e(133, f32, gx, gy), (1, 0): e(133, f32, fx, gy), (0, 1): e(133, f32, gx, fy), (1, 1): e(133, f32, fx, fy)}
            acc = wsum = any_bad = all_bad = None
            for d, w in weights.items():
                c = glsl_op(iv2, 45, ib if d == (0, 0) else e(128, iv2, ib, corner[d]), corner[(0, 0)], top)
                if arrayed: c = e(HK_OP_COMPOSITE_CONSTRUCT, iv3, c, layer)
                tx = e(95, v4, img, c, 0x2, lo_i)
                bad = is_error(tx)
                wk = e(OP_SELECT, f32, bad, c0, w)
                part = e(142, v4, tx, wk)
                acc = part if acc is None else e(129, v4, acc, part)
                wsum = wk if wsum is None else e(129, f32, wsum, wk)
                any_bad = bad if any_bad is None else e(166, b1, any_bad, bad)
                all_bad = bad if all_bad is None else e(HK_OP_LAND, b1, all_bad, bad)
            kept = e(142, v4, acc, e(136, f32, c1, e(OP_SELECT, f32, all_bad, c1, wsum)))
            keep = pick(trace(s_hi), s_lo, s0)
            fixed = pick(any_bad, pick(all_bad, coarser, kept), keep)
        else:
            lo_bad = is_error(s_lo)
            fixed = pick(hi_bad, pick(lo_bad, pick(base_bad, zero, s_base), s_lo), pick(lo_bad, s_hi, s0))
        out += [[2 << 16 | HK_OP_BRANCH, merge], [2 << 16 | HK_OP_LABEL, merge], [7 << 16 | HK_OP_PHI, v4, x[2], s0, cur, fixed, fix]]
        own.add(x[2])
        cur = merge
        tail[orig] = merge
        n += 1
    for x in out:   # a block split here reaches its successors from its last part
        if x[0] & 0xffff == HK_OP_PHI and x[2] not in own:
            for k in range(4, len(x), 2):
                if x[k] in tail: x[k] = tail[x[k]]
    m.ins = out
    m.index()
    return n


_banana_precise_minmax = precise_minmax


def precise_minmax(m):
    n = _banana_precise_minmax(m)
    done = m.entry and any(x[0] & 0xffff == OP_EXECUTION_MODE and x[1] == m.entry[2] and x[2] == MODE_SZ_INF_NAN_PRESERVE for x in m.ins)
    if not done:   # (a module this ran on already keeps its selects as they are)
        nan_exact_minmax(m)
        astc_error_to_zero(m)
        mip_error_split(m)
        nan_inf_preserve(m)
    return n
