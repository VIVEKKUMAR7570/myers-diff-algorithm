import sys


KEEP = 0
DEL = 1
INS = 2


def read_file_lines(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if len(data) == 0:
        return []
    parts = data.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return parts


def _myers_core(a, b):
    n = len(a)
    m = len(b)
    if n == 0:
        return [INS] * m
    if m == 0:
        return [DEL] * n
    max_d = n + m
    offset = max_d
    # V array indexed by diagonal k = x - y, stored at offset + k.
    # V[k] = furthest reaching x on diagonal k.
    V = [-1] * (2 * max_d + 1)
    V[offset + 1] = 0
    # trace[d] holds copy of V slice for diagonals in [-d, d].
    # trace[d][k + d] == V_d[k]. Only 2*d+1 entries copied per d.
    trace = []
    a_local = a
    b_local = b
    D = -1
    for d in range(max_d + 1):
        found = False
        # walk diagonals k = -d, -d+2, ..., d
        for k in range(-d, d + 1, 2):
            idx = offset + k
            # choose down (insertion) or right (deletion)
            # prefer deletion when equal for determinism
            if k == -d or (k != d and V[idx - 1] < V[idx + 1]):
                x = V[idx + 1]
            else:
                x = V[idx - 1] + 1
            y = x - k
            # snake: follow equal elements diagonally
            # guard y >= 0 because negative index would wrap in python
            while x < n and y < m and x >= 0 and y >= 0 and a_local[x] == b_local[y]:
                x += 1
                y += 1
            V[idx] = x
            if x >= n and y >= m:
                found = True
                break
        # store only relevant slice, not whole array
        trace.append(V[offset - d:offset + d + 1])
        if found:
            D = d
            break
    # reconstruct edit script from trace
    ops_rev = []
    x = n
    y = m
    for d in range(D, 0, -1):
        k = x - y
        vprev = trace[d - 1]
        if k == -d:
            prev_k = k + 1
        elif k == d:
            prev_k = k - 1
        else:
            # vprev index for diagonal q is q + (d - 1)
            # so V[q=k-1] at k+d-2 and V[q=k+1] at k+d
            if vprev[k + d - 2] < vprev[k + d]:
                prev_k = k + 1
            else:
                prev_k = k - 1
        prev_x = vprev[prev_k + d - 1]
        prev_y = prev_x - prev_k
        if prev_k == k + 1:
            # down step: insertion
            x0 = prev_x
            y0 = prev_y + 1
            edit = INS
        else:
            # right step: deletion
            x0 = prev_x + 1
            y0 = prev_y
            edit = DEL
        num_keep = x - x0
        # y - y0 should equal num_keep
        for _ in range(num_keep):
            ops_rev.append(KEEP)
        ops_rev.append(edit)
        x = prev_x
        y = prev_y
    # initial snake from (0,0)
    for _ in range(x):
        ops_rev.append(KEEP)
    ops_rev.reverse()
    return ops_rev


def myers_diff(a, b):
    n = len(a)
    m = len(b)
    # common prefix
    lim = n if n < m else m
    pref = 0
    while pref < lim and a[pref] == b[pref]:
        pref += 1
    # common suffix without overlapping prefix
    suff = 0
    while suff < (n - pref) and suff < (m - pref) and a[n - 1 - suff] == b[m - 1 - suff]:
        suff += 1
    if suff == 0:
        a_mid = a[pref:]
        b_mid = b[pref:]
    else:
        a_mid = a[pref:n - suff]
        b_mid = b[pref:m - suff]
    nmid_a = len(a_mid)
    nmid_b = len(b_mid)
    if nmid_a == 0 and nmid_b == 0:
        mid_ops = []
    elif nmid_a == 0:
        mid_ops = [INS] * nmid_b
    elif nmid_b == 0:
        mid_ops = [DEL] * nmid_a
    else:
        # fast path: disjoint sequences need no search;
        # minimal script is all deletes then all inserts.
        try:
            if nmid_a < nmid_b:
                s = set(a_mid)
                disjoint = True
                for v in b_mid:
                    if v in s:
                        disjoint = False
                        break
            else:
                s = set(b_mid)
                disjoint = True
                for v in a_mid:
                    if v in s:
                        disjoint = False
                        break
            if disjoint:
                mid_ops = [DEL] * nmid_a + [INS] * nmid_b
            else:
                mid_ops = _myers_core(a_mid, b_mid)
        except TypeError:
            mid_ops = _myers_core(a_mid, b_mid)
    ops = [KEEP] * pref + mid_ops + [KEEP] * suff
    # enforce delete-before-insert inside each change block
    norm = []
    idx = 0
    total = len(ops)
    while idx < total:
        if ops[idx] == KEEP:
            norm.append(KEEP)
            idx += 1
        else:
            dc = 0
            ic = 0
            while idx < total and ops[idx] != KEEP:
                if ops[idx] == DEL:
                    dc += 1
                else:
                    ic += 1
                idx += 1
            if dc:
                norm.extend([DEL] * dc)
            if ic:
                norm.extend([INS] * ic)
    return norm


def render_line_diff(a_lines, b_lines, ops):
    out = []
    i = 0
    j = 0
    for op in ops:
        if op == KEEP:
            out.append(b" " + a_lines[i] + b"\n")
            i += 1
            j += 1
        elif op == DEL:
            out.append(b"-" + a_lines[i] + b"\n")
            i += 1
        else:
            out.append(b"+" + b_lines[j] + b"\n")
            j += 1
    return out


def character_ranges(old_s, new_s, char_ops):
    old_idx = []
    new_idx = []
    p = 0
    q = 0
    for op in char_ops:
        if op == KEEP:
            p += 1
            q += 1
        elif op == DEL:
            old_idx.append(p)
            p += 1
        else:
            new_idx.append(q)
            q += 1

    def fmt(idxs):
        if not idxs:
            return "."
        parts = []
        s = idxs[0]
        prev = s
        for cur in idxs[1:]:
            if cur == prev + 1:
                prev = cur
            else:
                parts.append(str(s) + "-" + str(prev + 1))
                s = cur
                prev = cur
        parts.append(str(s) + "-" + str(prev + 1))
        return ",".join(parts)

    return fmt(old_idx), fmt(new_idx)


def render_highlight(a_byte_lines, b_byte_lines, a_str_lines, b_str_lines, ops):
    out = []
    i = 0
    j = 0
    idx = 0
    total = len(ops)
    while idx < total:
        if ops[idx] == KEEP:
            out.append(b" " + a_byte_lines[i] + b"\n")
            i += 1
            j += 1
            idx += 1
        else:
            del_start = i
            ins_start = j
            dc = 0
            ic = 0
            while idx < total and ops[idx] != KEEP:
                if ops[idx] == DEL:
                    dc += 1
                    i += 1
                else:
                    ic += 1
                    j += 1
                idx += 1
            for k2 in range(dc):
                out.append(b"-" + a_byte_lines[del_start + k2] + b"\n")
            paired = dc if dc < ic else ic
            for k2 in range(ic):
                out.append(b"+" + b_byte_lines[ins_start + k2] + b"\n")
                if k2 < paired:
                    old_s = a_str_lines[del_start + k2]
                    new_s = b_str_lines[ins_start + k2]
                    char_ops = myers_diff(old_s, new_s)
                    ro, rn = character_ranges(old_s, new_s, char_ops)
                    out.append(("? " + ro + " | " + rn + "\n").encode("ascii"))
    return out


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("lines", "highlight"):
        print("usage: main.py lines|highlight A_PATH B_PATH", file=sys.stderr)
        return 2
    command, a_path, b_path = sys.argv[1:]
    a_lines = read_file_lines(a_path)
    if a_lines is None:
        print("error: cannot read file: " + a_path, file=sys.stderr)
        return 2
    b_lines = read_file_lines(b_path)
    if b_lines is None:
        print("error: cannot read file: " + b_path, file=sys.stderr)
        return 2
    if command == "lines":
        ops = myers_diff(a_lines, b_lines)
        chunks = render_line_diff(a_lines, b_lines, ops)
        if chunks:
            sys.stdout.buffer.write(b"".join(chunks))
        return 0
    else:
        try:
            a_str = [x.decode("utf-8") for x in a_lines]
            b_str = [x.decode("utf-8") for x in b_lines]
            ok = True
        except UnicodeDecodeError:
            ok = False
            a_str = []
            b_str = []
        ops = myers_diff(a_lines, b_lines)
        if ok:
            chunks = render_highlight(a_lines, b_lines, a_str, b_str, ops)
        else:
            chunks = render_line_diff(a_lines, b_lines, ops)
        if chunks:
            sys.stdout.buffer.write(b"".join(chunks))
        return 0


raise SystemExit(main())
