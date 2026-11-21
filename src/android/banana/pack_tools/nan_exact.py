

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


def mip_error_split(m):
    """In a pixel shader, a float4 implicit-lod sample with any trace of ASTC's error colour (green under red and under blue) is read again level by level, and a
    level that reads as the error colour is left out: the coarser one when the finer one has content, else the finer one, else the base level, else 0. A
    trilinear sample between a level the game filled and one it never did came out pink. Samples with no such trace run as before (the extra reads are in a
    branch); a sample in a loop header block is left as it is. → samples rewritten"""
    if m.model != 'ps': return 0
    f32 = m.find_type(OP_TYPE_FLOAT, 32)
    v4 = m.find_type(OP_TYPE_VECTOR, f32, 4) if f32 is not None else None
    if v4 is None: return 0
    deftype = {x[2]: x[1] for x in m.ins if x[0] & 0xffff in (OP_LOAD, HK_OP_SAMPLED_IMAGE, HK_OP_PHI, OP_COPY_OBJECT, OP_SELECT) and len(x) > 2}

    def plan(x):   # (coordinate components of a level, arrayed, explicit operand mask, offset operand ids) of a sample this rewrites, else None
        if x[0] & 0xffff != 87 or x[1] != v4: return None
        st = m.types.get(deftype.get(x[3]))
        if not st or st[0] & 0xffff != OP_TYPE_SAMPLED_IMAGE: return None
        im = m.types.get(st[2])
        if not im or im[0] & 0xffff != OP_TYPE_IMAGE or im[3] not in (0, 1, 2, 3) or im[4] == 1 or im[6] or im[2] != f32: return None
        mask, ops, k = (x[5], x[6:], 0) if len(x) > 5 else (0, [], 0)
        if mask & ~0xb9: return None   # Bias, ConstOffset, Offset, ConstOffsets, MinLod only
        offs = []
        for bit, n in HK_IMAGE_OPERANDS:
            if mask & bit:
                if bit in (0x8, 0x10, 0x20): offs += ops[k:k + n]
                k += n
        return ({0: 1, 1: 2, 2: 3, 3: 3}[im[3]], im[5], 0x2 | (mask & 0x38), offs)

    if not any(plan(x) for x in m.ins): return 0
    if 50 not in m.caps:   # ImageQuery (the translator declares it in every module)
        m.ins.insert(max(k for k, x in enumerate(m.ins) if x[0] & 0xffff == OP_CAPABILITY) + 1, [2 << 16 | OP_CAPABILITY, 50])
        m.index()
    glsl = ensure_glsl(m)
    b1 = m.add_type(OP_TYPE_BOOL)
    b4 = m.add_type(OP_TYPE_VECTOR, b1, 4)
    v2 = m.add_type(OP_TYPE_VECTOR, f32, 2)
    vecn = {1: f32, 2: v2, 3: m.add_type(OP_TYPE_VECTOR, f32, 3)}
    c0, c1, ceps = m.add_const(f32, 0), m.add_const(f32, _hk_f32(1.0)), m.add_const(f32, _hk_f32(PINK_EPS))
    mag, zero = vec4_const(m, f32, ASTC_ERROR), vec4_const(m, f32, (0.0, 0.0, 0.0, 0.0))
    deftype = {x[2]: x[1] for x in m.ins if x[0] & 0xffff in (OP_LOAD, HK_OP_SAMPLED_IMAGE, HK_OP_PHI, OP_COPY_OBJECT, OP_SELECT) and len(x) > 2}
    loop_blocks, lab = set(), None
    for x in m.ins:
        if x[0] & 0xffff == HK_OP_LABEL: lab = x[1]
        elif x[0] & 0xffff == HK_OP_LOOP_MERGE: loop_blocks.add(lab)
    out, tail, n, cur, orig, own = [], {}, 0, None, None, set()
    for x in m.ins:
        op = x[0] & 0xffff
        if op == HK_OP_LABEL: cur = orig = x[1]
        p = plan(x) if cur is not None and orig not in loop_blocks else None
        if not p:
            out.append(x)
            if op in HK_TERMINATORS: cur = None
            continue
        comps, arrayed, emask, offs = p
        ids = iter(lambda: m.new_id(), None)
        s0, r, g, b, lt1, lt2, cond, fix, merge = (next(ids) for _ in range(9))
        out += [[x[0], v4, s0, *x[3:]],
                [5 << 16 | HK_OP_CEXTRACT, f32, r, s0, 0], [5 << 16 | HK_OP_CEXTRACT, f32, g, s0, 1], [5 << 16 | HK_OP_CEXTRACT, f32, b, s0, 2]]
        ge = next(ids)
        out += [[5 << 16 | HK_OP_FADD, f32, ge, g, ceps], [5 << 16 | HK_OP_FLESS, b1, lt1, ge, r], [5 << 16 | HK_OP_FLESS, b1, lt2, ge, b],
                [5 << 16 | HK_OP_LAND, b1, cond, lt1, lt2], [3 << 16 | HK_OP_SEL_MERGE, merge, 0], [4 << 16 | HK_OP_BRANCH_COND, cond, fix, merge],
                [2 << 16 | HK_OP_LABEL, fix]]
        coord = x[4]
        if arrayed:
            cq = next(ids)
            out.append([5 << 16 | HK_OP_CEXTRACT, f32, cq, coord, 0] if comps == 1 else [(5 + comps) << 16 | HK_OP_VSHUF, vecn[comps], cq, coord, coord, *range(comps)])
            coord_q = cq
        else:
            coord_q = coord
        q, lvl, lo, hi = next(ids), next(ids), next(ids), next(ids)
        out += [[5 << 16 | HK_OP_QUERY_LOD, v2, q, x[3], coord_q], [5 << 16 | HK_OP_CEXTRACT, f32, lvl, q, 0],
                [6 << 16 | OP_EXT_INST, f32, lo, glsl, GLSL_FLOOR, lvl], [5 << 16 | HK_OP_FADD, f32, hi, lo, c1]]
        reads = {}
        for name, lod in (('lo', lo), ('hi', hi), ('base', c0)):
            s, eq, al, bad = next(ids), next(ids), next(ids), next(ids)
            out += [[(7 + len(offs)) << 16 | 88, v4, s, x[3], coord, emask, lod, *offs], [5 << 16 | OP_FORD_EQUAL, b4, eq, s, mag],
                    [4 << 16 | HK_OP_ALL, b1, al, eq], [7 << 16 | HK_OP_COMPOSITE_CONSTRUCT, b4, bad, al, al, al, al]]
            reads[name] = (s, bad)
        alt, lof, hif, fixed = next(ids), next(ids), next(ids), next(ids)
        out += [[6 << 16 | OP_SELECT, v4, alt, reads['base'][1], zero, reads['base'][0]],
                [6 << 16 | OP_SELECT, v4, lof, reads['lo'][1], alt, reads['lo'][0]],
                [6 << 16 | OP_SELECT, v4, hif, reads['lo'][1], reads['hi'][0], s0],
                [6 << 16 | OP_SELECT, v4, fixed, reads['hi'][1], lof, hif],
                [2 << 16 | HK_OP_BRANCH, merge], [2 << 16 | HK_OP_LABEL, merge],
                [7 << 16 | HK_OP_PHI, v4, x[2], s0, cur, fixed, fix]]
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
