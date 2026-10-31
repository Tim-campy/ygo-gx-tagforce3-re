#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the scene map: which module drives each screen, which archives, EHF layouts and string tables it
loads, and which string indices it draws. See docs/subsystems/ui.md ("Scene map").

  scenes.py map   <PSP_GAME> -o scenes.json         the map as JSON (write it outside the repository)
  scenes.py check <PSP_GAME>                        coverage: layouts and string tables attributed to a scene
  scenes.py refs  <PSP_GAME> <module> [--filter RE] every asset name a module's code uses, with its function
  scenes.py calls <PSP_GAME> <module> <callee RE>   resolved arguments at every call of matching functions

Method (static; nothing is executed natively):
1. BOOT.BIN and every gmodule/*.prx are decoded as raw MIPS words, function by function (starts are jal
   targets, relocated code pointers and the entry point). A forward pass keeps symbolic register and stack-slot
   values (constants, function arguments, call results, loads of absolute addresses), resets what may differ
   at branch targets, and records every data address formed and every call with its argument expressions.
2. Import stubs resolve by NID to BOOT.BIN or to the exporting module (tools/prx_imports.py) and are named
   from re/functions.csv. Call results are resolved through per-function return summaries, a small MIPS
   interpreter for leaf getters (for example "name array + 64 * index") and globals written once.
3. Asset names are the strings that calls receive (container_ehp_find_member, sprintf, the string accessor
   card_db_get_dictionary_word, ...), the strings the code addresses, and the asset-like strings in the
   module's data.
4. Names are matched against the disc (every archive, nested archive and member, BOOT.BIN's embedded
   archives), with the language letter normalised (`title_msg_j.bin` ~ `title_msg_<l>.bin`) and printf
   patterns expanded. A layout or string table is attributed to a module with a basis:
     call    - a resolved call argument names it (the module looks it up by name; certain);
     code    - the code addresses a string or a name array holding its name (high);
     data    - its name is in the module's data, no code reference found (medium);
     archive - only its archive is named; the archive's layouts are bound as a whole (inferred, high).
   Member names that occur in several archives (`strTbl.bin`) are attributed only through the archives the
   module names.
5. Modules map to scenes through BOOT.BIN's scene table (docs/subsystems/modules.md), library modules to the
   scenes whose modules load them (constant system_module_load ids) or import their library.
"""

import argparse
import bisect
import csv
import importlib.util
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prx_imports = _load("prx_imports")
ehp = _load("ehp")
strtbl = _load("strtbl")

BOOT_BASE = 0x08804000
# Runtime bases measured in PPSSPP (docs/subsystems/modules.md); other modules are reported by offset only.
BASES = {"BOOT.BIN": BOOT_BASE, "rel_title": 0x08e9aa00, "rel_story": 0x08e9aa00, "rel_deck": 0x08e9aa00,
         "rel_duel_mgr": 0x08e9aa00, "rel_field": 0x090ced00, "rel_shop": 0x090ced00,
         "rel_duel_draw": 0x0983fb00, "rel_duel_eng": 0x09be1400}
SCENE_TABLE, SCENE_COUNT = 0x088a1478, 31
GAME_TABLE = 0x0889fea4
ACCESSOR = "card_db_get_dictionary_word"  # generic headed string-table accessor (table, index)
FIND = "container_ehp_find_member"
STEM = re.compile(r"^[a-z][a-z0-9]*_[a-z0-9_]+$")
BUILDERS = ("system_sprintf", "system_strcpy", "system_strncpy")
MODULE_LOAD = ("system_module_load", "system_module_load_ex")
ASSET = re.compile(r"\.(ehp|ehf|bin|gim|tmf|tms|tmt|tma|ydq|ydc|dat|pmf|hmp|gz|at3|txt)$", re.I)
LANG = re.compile(r"_(e|f|g|i|j|s|x|eng|fra|ger|ita|spa|jpn|%s|%c)(?=\.|/|_)", re.I)
LANG_CODES = r"(?:e|f|g|i|j|s|eng|fra|ger|ita|spa|jpn)"
PREFIX = re.compile(r"^[a-z][a-z0-9]{2,}_$", re.I)  # a name prefix completed with a language code at runtime
PRINTF = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?[hl]*[sdiuxXc]")
SAVED = frozenset((16, 17, 18, 19, 20, 21, 22, 23, 28, 29, 30))
ARG_REGS = (4, 5, 6, 7)
R_MIPS_32 = 2
SP = 29
SCENE_LABELS = {
    0: "debug menu", 1: "debug menu", 2: "story / event runner", 3: "duel presentation (stand-alone)",
    4: "deck editor", 5: "free-roam field", 6: "duel session (RPS, versus, duel, results)", 7: "card shop",
    8: "SD character viewer (missing)", 9: "lab hub (database tools)", 0x0a: "movie viewer",
    0x0b: "cut-in viewer", 0x0c: "debug menu", 0x0d: "title, main menu, options", 0x0e: "download (HTML view)",
    0x0f: "blackjack", 0x10: "blackjack starter (missing)", 0x11: "dodgeball", 0x12: "dodgeball starter (missing)",
    0x13: "connection minigame", 0x14: "connection starter (missing)", 0x15: "underground duel",
    0x16: "underground starter (missing)", 0x17: "USB connection", 0x18: "quiz", 0x19: "reversi",
    0x1a: "reversi starter (missing)", 0x1b: "UMD swap", 0x1c: "throw minigame", 0x1d: "throw starter",
    0x1e: "gallery",
}


def _sext(v):
    return v - 0x10000 if v & 0x8000 else v


# --- Binary model ---------------------------------------------------------------------------------

class Binary:
    """One ELF image (BOOT.BIN or a gmodule PRX) at module-relative addresses (base 0)."""

    def __init__(self, name, data):
        self.name, self.data = name, data
        self.elf = prx_imports.Elf(data, 0)
        secs = self.elf.sections
        _, _, _, self.text_addr, self.text_off, self.text_size = secs[".text"]
        self.ranges = sorted((h[3], h[3] + h[5], h[4], n) for n, h in secs.items() if h[2] & 2 and h[5])
        self.data_ranges = [(lo, hi) for lo, hi, _, n in self.ranges if n.startswith((".data", ".rodata"))]
        bss = secs.get(".bss")
        # .bss has size 0 in the section headers; the PT_LOAD segment's p_memsz gives the real extent
        phoff, = struct.unpack_from("<I", data, 0x1C)
        self.bss = (0, 0)
        if phoff:
            p_vaddr, _, p_filesz, p_memsz = struct.unpack_from("<4I", data, phoff + 8)
            if p_memsz > p_filesz:
                self.bss = (p_vaddr + p_filesz, p_vaddr + p_memsz)
        self.entry, = struct.unpack_from("<I", data, 0x18)

    def in_data(self, addr):
        return any(lo <= addr < hi for lo, hi in self.data_ranges)

    def in_text(self, addr):
        return self.text_addr <= addr < self.text_addr + self.text_size

    def read(self, addr, size):
        """Little-endian unsigned value at addr; 0 inside .bss; None outside the image."""
        for lo, hi, off, _ in self.ranges:
            if lo <= addr and addr + size <= hi:
                return int.from_bytes(self.data[off + addr - lo:off + addr - lo + size], "little")
        if self.bss[0] <= addr < self.bss[1]:
            return 0
        return None

    def cstring(self, addr):
        """Printable ASCII NUL-terminated string (3+ characters) at addr, else None."""
        if not isinstance(addr, int) or not self.in_data(addr):
            return None
        off = self.elf.offset(addr)
        end = self.data.find(b"\0", off, off + 256)
        if end - off < 3:
            return None
        raw = self.data[off:end]
        return raw.decode() if all(0x20 <= c < 0x7f for c in raw) else None

    def data_strings(self):
        """{address: string} of every printable string in the data sections (start after a NUL)."""
        out = {}
        for lo, hi, off, name in self.ranges:
            if not name.startswith((".data", ".rodata")) or name.startswith(".rodata.sce"):
                continue
            for m in re.finditer(rb"[\x20-\x7e]{3,}(?=\x00)", self.data[off:off + hi - lo]):
                start, text = lo + m.start(), m.group().decode()
                out[start] = text
                aligned = (start + 3) & ~3  # printable bytes before a 4-aligned string are usually not part of it
                if aligned != start and aligned - start <= len(text) - 3:
                    out[aligned] = text[aligned - start:]
        return out

    def relocated_words(self):
        """{address: value} of every R_MIPS_32-relocated word (pointers stored in the image)."""
        out = {}
        for h in self.elf.sections.values():
            if h[1] != 0x700000A0 or not h[5]:
                continue
            for k in range(0, h[5] - 7, 8):
                offset, info = struct.unpack_from("<II", self.data, h[4] + k)
                if info & 0xff == R_MIPS_32:
                    value = self.read(offset, 4)
                    if value is not None:
                        out[offset] = value
        return out


# --- Instruction decoding -------------------------------------------------------------------------

BRANCH_OPS = {0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17}
LOADS = {0x20: 1, 0x21: 2, 0x23: 4, 0x24: 1, 0x25: 2}  # lb lh lw lbu lhu
STORES = {0x28: 1, 0x29: 2, 0x2b: 4}
NO_DEST_FUNCT = {0x08, 0x0c, 0x0d, 0x0f, 0x18, 0x19, 0x1a, 0x1b, 0x11, 0x13, 0x30, 0x31, 0x32, 0x33, 0x34,
                 0x36, 0x1c, 0x1d, 0x2c, 0x2d, 0x2e, 0x2f}


def branch_target(w, addr):
    """Target of a conditional branch (or b/j inside a function), else None."""
    op = w >> 26
    if op in BRANCH_OPS or op == 0x01 and ((w >> 16) & 31) in (0, 1, 2, 3, 0x10, 0x11, 0x12, 0x13) \
            or op == 0x11 and ((w >> 21) & 31) == 8 or op == 0x12 and ((w >> 21) & 31) == 8:
        return (addr + 4 + 4 * _sext(w & 0xffff)) & 0xffffffff
    if op == 0x02:
        return (w & 0x3ffffff) << 2
    return None


def dest_of(w):
    """GPR written by an instruction (None for stores, branches, FPU/VFPU-only ops); jal handled apart."""
    op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    if op == 0:
        funct = w & 0x3f
        return None if funct in NO_DEST_FUNCT else rd
    if 0x08 <= op <= 0x0f or op in LOADS or op in (0x22, 0x26):
        return rt
    if op in (0x11, 0x12) and rs in (0, 2, 3):  # mfc1/cfc1, mfc2/mfv
        return rt
    if op == 0x1f:
        return rt if (w & 0x3f) in (0, 4) else rd
    if op == 0x1c:
        return rd
    return None


class Function:
    __slots__ = ("start", "end", "calls", "refs", "returns", "leaf", "gstores")

    def __init__(self, start, end):
        self.start, self.end = start, end
        self.calls, self.refs, self.returns, self.gstores = [], [], [], []
        self.leaf = True


def analyse_function(binary, start, end, builders=frozenset()):
    """Symbolic forward pass over [start, end). Values: int (constant), ('arg', k), ('ret', target, args,
    site), ('gload', address, size), ('sp', offset), ('built', format) or None (unknown). `builders` are the
    stub addresses of sprintf/strcpy: a stack buffer they filled is passed on as ('built', their format)."""
    fn = Function(start, end)
    n = (end - start) // 4
    if n <= 0:
        return fn
    words = struct.unpack_from(f"<{n}I", binary.data, binary.elf.offset(start))
    # What each instruction writes: a register or a stack slot; branch edges inside the function.
    writes = []
    edges = defaultdict(list)
    for k, w in enumerate(words):
        op = w >> 26
        slot = ("s", _sext(w & 0xffff)) if op in STORES and ((w >> 21) & 31) == SP else None
        writes.append((dest_of(w) if op != 0x03 else 31, slot))
        t = branch_target(w, start + 4 * k)
        if t is not None and start <= t < end and t % 4 == 0:
            edges[(t - start) // 4].append(k)
    # Kill sets: everything written anywhere between a branch and its target (forward), or inside the loop
    # (backward); one conservative span per target. A call in the span kills the caller-saved registers.
    reg_pos, slot_pos, call_pos = defaultdict(list), defaultdict(list), []
    for k, (d, slot) in enumerate(writes):
        if d:
            reg_pos[d].append(k)
        if slot:
            slot_pos[slot].append(k)
        if words[k] >> 26 == 0x03 or words[k] >> 26 == 0 and words[k] & 0x3f == 0x09:
            call_pos.append(k)

    def touched(positions, lo, hi):
        j = bisect.bisect_left(positions, lo)
        return j < len(positions) and positions[j] < hi

    kills = {}
    for t, sources in edges.items():
        lo = min([s + 1 for s in sources if s < t] + [t])
        hi = max([s + 2 for s in sources if s >= t] + [t])
        regs = {r for r, pos in reg_pos.items() if touched(pos, lo, hi)}
        if touched(call_pos, lo, hi):
            regs.update(r for r in range(1, 32) if r not in SAVED)
        kills[t] = (regs, {sl for sl, pos in slot_pos.items() if touched(pos, lo, hi)})

    regs = [None] * 32
    regs[0] = 0
    for k, r in enumerate(ARG_REGS):
        regs[r] = ("arg", k)
    regs[SP] = ("sp", 0)
    slots = {}
    slots, built = {}, {}
    pending = None
    fresh = False  # the previous instruction was the delay slot of an unconditional jump
    for k, w in enumerate(words):
        addr = start + 4 * k
        if k in kills:
            kr, ks = kills[k]
            for r in kr:
                regs[r] = None
            for s in ks:
                slots.pop(s, None)
        elif fresh:  # reached only through a jump table or not at all: nothing is known
            regs = [None] * 32
            regs[0] = 0
            regs[SP] = ("sp", 0)
            slots = {}
        fresh = False
        op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        imm = w & 0xffff
        dest, value = dest_of(w), None
        a, b = regs[rs], regs[rt]
        if op == 0x0f:  # lui
            value = imm << 16
        elif op == 0x09:  # addiu
            if isinstance(a, int):
                value = (a + _sext(imm)) & 0xffffffff
                if rs and binary.in_data(value):
                    fn.refs.append((addr, value))
            elif isinstance(a, tuple) and a[0] == "sp":
                value = ("sp", a[1] + _sext(imm)) if rs != SP or rt != SP else ("sp", 0)
        elif op == 0x0d:  # ori
            if isinstance(a, int):
                value = a | imm
                if rs and binary.in_data(value):
                    fn.refs.append((addr, value))
        elif op == 0x0c:  # andi
            value = a & imm if isinstance(a, int) else None
        elif op in LOADS or op in STORES or op in (0x31, 0x35, 0x39, 0x3d):
            off = _sext(imm)
            target = (a + off) & 0xffffffff if isinstance(a, int) else None
            if target is not None and rs and binary.in_data(target):
                fn.refs.append((addr, target))
            if op in LOADS:
                if rs == SP:
                    value = slots.get(("s", off)) if op == 0x23 else None
                elif target is not None:
                    value = ("gload", target, LOADS[op])
            elif op in STORES:
                if rs == SP:
                    slots[("s", off)] = b if op == 0x2b else None
                elif target is not None and op == 0x2b:
                    fn.gstores.append((target, b))
        elif op == 0:
            funct = w & 0x3f
            if funct in (0x21, 0x25):  # addu, or: moves and constant sums
                if rs == 0:
                    value = b
                elif rt == 0:
                    value = a
                elif isinstance(a, int) and isinstance(b, int):
                    value = (a + b) & 0xffffffff if funct == 0x21 else a | b
            elif funct == 0x23 and isinstance(a, int) and isinstance(b, int):  # subu
                value = (a - b) & 0xffffffff
            elif funct == 0x00 and isinstance(b, int):  # sll
                value = (b << ((w >> 6) & 31)) & 0xffffffff
            elif funct == 0x09:  # jalr
                fn.leaf = False
                pending = (addr, None)
                continue
        elif op == 0x03:  # jal
            fn.leaf = False
            pending = (addr, (w & 0x3ffffff) << 2)
            continue
        if dest:
            regs[dest] = value
        if pending is not None:  # this instruction was the delay slot of a call
            site, target = pending
            args = tuple(built.get(v[1], v) if isinstance(v, tuple) and v[0] == "sp" else v
                         for v in (regs[r] for r in ARG_REGS))
            if target in builders and isinstance(regs[4], tuple) and regs[4][0] == "sp":
                built[regs[4][1]] = ("built", regs[5])
            if target is not None:
                fn.calls.append((site, target, args))
            for r in range(1, 32):
                if r not in SAVED:
                    regs[r] = None
            regs[2] = ("ret", target, args, site) if target is not None else None
            pending = None
            continue
        prev = words[k - 1] if k else 0
        if prev >> 26 == 0 and prev & 0x3f == 0x08 and k:  # delay slot of jr
            if (prev >> 21) & 31 == 31:
                fn.returns.append(regs[2])
            fresh = True
        elif k and (prev >> 26 == 0x02 or prev >> 16 == 0x1000):  # delay slot of j or b (beq zero, zero)
            fresh = True
    return fn


# --- Getter interpreter ---------------------------------------------------------------------------

RETURN = 0xdead0000
TOKEN = 0xf1000000  # results of imported calls inside the interpreter: TOKEN + n
STACK = (0x0bf00000, 0x0c000000)
LIKELY = {0x14: 0x04, 0x15: 0x05, 0x16: 0x06, 0x17: 0x07}


class _State:
    __slots__ = ("pc", "regs", "taint", "mem", "mtaint", "delay", "hi", "lo", "bss")

    def copy(self):
        c = _State()
        c.pc, c.regs, c.taint, c.mem, c.mtaint = self.pc, self.regs[:], self.taint[:], dict(self.mem), dict(self.mtaint)
        c.delay, c.hi, c.lo, c.bss = self.delay, self.hi, self.lo, self.bss
        return c


def emulate(binary, start, args, stubs=None, steps=6000, max_paths=32):
    """Interpret a function with integer arguments (None = unknown) and return its v0: an int, or
    ('call', name, args) when v0 is the result of an imported function called on the way (that call is not
    executed; its arguments are recorded). Local calls are followed. A branch that depends on memory of the
    module that reads as zero (an empty cache pointer, a "loaded" flag: runtime state) is explored both ways; the result is the one
    imported-call result or data pointer that the paths agree on. Covers the integer subset the compiler
    emits for getters and resource tables; an unknown operand, an unknown branch condition on arguments or
    an indirect call ends a path. Reads of .bss give 0."""
    stubs = stubs or {}
    tokens = []
    s0 = _State()
    s0.regs = [None] * 32
    s0.regs[0] = 0
    for r, v in zip(ARG_REGS, args):
        s0.regs[r] = v
    s0.regs[SP] = STACK[1] - 0x10000
    s0.regs[31] = RETURN
    s0.taint = [False] * 32
    s0.mem, s0.mtaint = {}, {}
    s0.pc, s0.delay, s0.hi, s0.lo, s0.bss = start, None, None, None, False
    todo, results, budget, paths = [s0], [], steps, 1
    while todo and budget > 0:
        st = todo.pop()
        box = [budget]
        result = _run(binary, st, stubs, tokens, todo, box, paths < max_paths)
        budget = box[0]
        paths = max(paths, len(todo) + len(results) + 1)
        if result is not None:
            results.append(result)
    calls = {r for r in results if r[0] == "call"}
    if len(calls) == 1:
        return calls.pop()
    if calls:
        return None
    # 0 is a null pointer (an empty cache, a missing entry) far more often than a useful constant
    ints = {r[0] for r in results if r[0] != "call" and r[0] and (not r[1] or binary.in_data(r[0]))}
    return ints.pop() if len(ints) == 1 else None


def _run(binary, st, stubs, tokens, todo, budget_box, may_fork):
    """Run one path until it returns; returns ('call', ...) or (v0, read_bss) or None."""
    regs, taint, mem, mtaint = st.regs, st.taint, st.mem, st.mtaint
    while budget_box[0] > 0:
        budget_box[0] -= 1
        pc = st.pc
        if not binary.in_text(pc):
            return None
        w = binary.read(pc, 4)
        op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        imm, sh, funct = w & 0xffff, (w >> 6) & 31, w & 0x3f
        a, b = regs[rs], regs[rt]
        t = taint[rs] or taint[rt]
        dest, value, jump, skip = None, None, None, False
        try:
            if op == 0:
                dest = rd
                if funct in (0x21, 0x25) and (rs == 0 or rt == 0):
                    value, t = (b, taint[rt]) if rs == 0 else (a, taint[rs])
                elif funct in (0x00, 0x02, 0x03):
                    t = taint[rt]
                    if funct == 0x00:
                        value = (b << sh) & 0xffffffff
                    elif funct == 0x02:
                        value = b >> sh
                    else:
                        value = ((b - (1 << 32) if b & 0x80000000 else b) >> sh) & 0xffffffff
                elif funct == 0x04:
                    value = (b << (a & 31)) & 0xffffffff
                elif funct == 0x06:
                    value = b >> (a & 31)
                elif funct in (0x20, 0x21):
                    value = (a + b) & 0xffffffff
                elif funct in (0x22, 0x23):
                    value = (a - b) & 0xffffffff
                elif funct == 0x24:
                    value = a & b
                elif funct == 0x25:
                    value = a | b
                elif funct == 0x26:
                    value = a ^ b
                elif funct == 0x27:
                    value = ~(a | b) & 0xffffffff
                elif funct == 0x2a:
                    value = int((a ^ 0x80000000) < (b ^ 0x80000000))
                elif funct == 0x2b:
                    value = int(a < b)
                elif funct == 0x0a:  # movz
                    value = a if b == 0 else regs[rd]
                elif funct == 0x0b:  # movn
                    value = a if b != 0 else regs[rd]
                elif funct in (0x18, 0x19):  # mult, multu
                    prod = a * b
                    st.lo, st.hi, dest = prod & 0xffffffff, (prod >> 32) & 0xffffffff, None
                elif funct == 0x12:
                    value, t = st.lo, False
                elif funct == 0x10:
                    value, t = st.hi, False
                elif funct == 0x08:  # jr
                    dest, jump = None, (a, None)
                else:
                    return None
            elif op == 0x0f:
                dest, value, t = rt, imm << 16, False
            elif op in (0x09, 0x0d, 0x0c, 0x0e, 0x0a, 0x0b):
                dest, t = rt, taint[rs]
                if op == 0x09:
                    value = (a + _sext(imm)) & 0xffffffff
                elif op == 0x0d:
                    value = a | imm
                elif op == 0x0c:
                    value = a & imm
                elif op == 0x0e:
                    value = a ^ imm
                elif op == 0x0b:
                    value = int(a < (_sext(imm) & 0xffffffff))
                else:
                    value = int((a ^ 0x80000000) < ((_sext(imm) & 0xffffffff) ^ 0x80000000))
            elif op == 0x1f and funct == 0:  # ext
                dest, value, t = rt, (a >> sh) & ((1 << (rd + 1)) - 1), taint[rs]
            elif op == 0x1f and funct == 0x20 and sh in (0x10, 0x18):  # seb, seh
                bits = 8 if sh == 0x10 else 16
                v = b & ((1 << bits) - 1)
                dest, value, t = rd, ((v - (1 << bits)) & 0xffffffff) if v >> (bits - 1) else v, taint[rt]
            elif op in LOADS:
                ea = (a + _sext(imm)) & 0xffffffff
                size = LOADS[op]
                got = _load(binary, st, ea, size)
                if got is False:
                    return None
                value, t = got
                if value is not None and op in (0x20, 0x21) and value >> (8 * size - 1):
                    value = (value - (1 << (8 * size))) & 0xffffffff
                dest = rt
            elif op in STORES:
                _store(st, (a + _sext(imm)) & 0xffffffff, STORES[op], b, taint[rt])
            elif op in (0x01, 0x04, 0x05, 0x06, 0x07) or op in LIKELY:
                base = LIKELY.get(op, op)
                target = (pc + 4 + 4 * _sext(imm)) & 0xffffffff
                likely = op in LIKELY or op == 0x01 and rt in (2, 3)
                if base == 0x04 and rs == rt:
                    taken = True
                else:
                    cond_taint = taint[rs] or (taint[rt] if base in (0x04, 0x05) else False)
                    if base == 0x01 and rt not in (0, 1, 2, 3):
                        return None
                    try:
                        taken = _branch(base, rt, a, b)
                    except TypeError:
                        if not cond_taint:
                            raise
                        taken = None
                    if cond_taint and may_fork:
                        # runtime state decides: explore the other way too
                        other = st.copy()
                        if taken is None or taken:
                            other.pc = pc + 8 if likely else pc + 4
                            if not likely:
                                other.delay = None
                        else:
                            other.pc, other.delay = pc + 4, (target, None)
                        todo.append(other)
                        taken = True if taken is None else taken
                    elif taken is None:
                        return None
                if taken:
                    jump = (target, None)
                elif likely:
                    skip = True
            elif op == 0x02:
                jump = ((pc & 0xf0000000) | ((w & 0x3ffffff) << 2), None)
            elif op == 0x03:
                jump = ((w & 0x3ffffff) << 2, pc + 8)
            elif op in (0x11, 0x12, 0x18, 0x19, 0x1b, 0x31, 0x34, 0x35, 0x36, 0x37, 0x39, 0x3c, 0x3d, 0x3e):
                if op in (0x11, 0x12) and rs in (0, 2, 3):  # mfc1/cfc1/mfv write a GPR we cannot know
                    dest, value, t = rt, None, True
            else:
                return None
        except TypeError:  # an unknown (None) operand
            return None
        if dest:
            regs[dest], taint[dest] = value, t
        if st.delay is not None:
            target, link = st.delay
            st.delay = None
            if link is None:
                if target == RETURN:
                    v = regs[2]
                    if isinstance(v, int) and TOKEN <= v < TOKEN + len(tokens):
                        return tokens[v - TOKEN]
                    return (v, st.bss)
                if target is None:
                    return None
                st.pc = target
            elif target in stubs:
                name = stubs[target]
                call_args = tuple(regs[r] for r in ARG_REGS)
                result = _library_call(binary, st, name, call_args)
                for r in range(1, 32):
                    if r not in SAVED:
                        regs[r], taint[r] = None, True
                if result is not None:
                    regs[2], taint[2] = result, False
                else:
                    tokens.append(("call", name, tuple(_as_text(binary, st, v) for v in call_args)))
                    regs[2] = TOKEN + len(tokens) - 1
                st.pc = link
            else:
                regs[31], taint[31] = link, False
                st.pc = target
            continue
        if skip:
            st.pc = pc + 8
            continue
        if jump is not None:
            st.delay = jump
        st.pc = pc + 4
    return None


def _load(binary, st, ea, size):
    """(value, taint) of `size` bytes at ea from the path's memory, else from the image; False if unmapped."""
    value, taint, missing = 0, False, False
    for k in range(size):
        if ea + k in st.mem:
            byte = st.mem[ea + k]
            if byte is None:
                return None, True
            value |= byte << (8 * k)
            taint = taint or st.mtaint.get(ea + k, False)
        else:
            missing = True
    if missing:
        if binary.in_text(ea) or ea < 0x100:
            return None, True  # a pointer read as 0 from runtime state, dereferenced: unknown
        image = binary.read(ea, size)
        if image is None:
            return False
        for k in range(size):
            if ea + k not in st.mem:
                value |= image & (0xff << (8 * k))
        # A zero read from the module's memory is runtime state the image cannot know (an empty cache
        # pointer, a "loaded" flag); branches on it are explored both ways. Non-zero static data (ids,
        # pointers in tables) is trusted.
        taint = taint or (not (STACK[0] <= ea < STACK[1]) and value == 0)
        if not binary.in_data(ea):
            st.bss = True
    return value, taint


def _store(st, ea, size, value, taint):
    for k in range(size):
        st.mem[ea + k] = None if value is None else (value >> (8 * k)) & 0xff
        st.mtaint[ea + k] = taint


def _read_cstring(binary, st, addr, limit=256):
    """Bytes of a NUL-terminated string from the path's memory or the image, or None."""
    if not isinstance(addr, int):
        return None
    out = bytearray()
    for k in range(limit):
        if addr + k in st.mem:
            c = st.mem[addr + k]
        else:
            c = binary.read(addr + k, 1)
        if c is None:
            return None
        if c == 0:
            return bytes(out)
        out.append(c)
    return None


def _write_cstring(st, addr, raw):
    for k, c in enumerate(raw + b"\0"):
        st.mem[addr + k] = c
        st.mtaint[addr + k] = False


def _format(binary, st, fmt, args):
    """Minimal printf: %s %c %d %u %x with flags and width; None if an argument is unknown."""
    out, k, pos = bytearray(), 0, 0
    for m in re.finditer(rb"%([-0 #+]*)(\d*)(?:\.\d+)?[hl]*([sdiuxXc%])", fmt):
        out += fmt[pos:m.start()]
        pos = m.end()
        conv = m.group(3)
        if conv == b"%":
            out += b"%"
            continue
        if k >= len(args):
            return None
        arg = args[k]
        k += 1
        if conv == b"s":
            text = _read_cstring(binary, st, arg)
            if text is None:
                return None
            out += text
        elif not isinstance(arg, int):
            return None
        elif conv == b"c":
            out.append(arg & 0xff)
        else:
            spec = "%" + m.group(1).decode() + m.group(2).decode() + ("d" if conv in (b"i", b"u") else conv.decode())
            out += (spec % (arg - (1 << 32) if conv in (b"d", b"i") and arg & 0x80000000 else arg)).encode()
    return bytes(out + fmt[pos:])


# Imported functions the interpreter executes (string building) or answers (the language index, read as 0:
# names are compared with the language letter normalised).
def _library_call(binary, st, name, args):
    a0, a1, a2, a3 = args
    if name == "save_get_language":
        return 0
    if name in ("system_strcpy", "system_strncpy"):
        raw = _read_cstring(binary, st, a1)
        if raw is None or not isinstance(a0, int):
            return None
        if name == "system_strncpy" and isinstance(a2, int):
            raw = raw[:a2]
        _write_cstring(st, a0, raw)
        return a0
    if name == "system_strcat":
        head, tail = _read_cstring(binary, st, a0), _read_cstring(binary, st, a1)
        if head is None or tail is None:
            return None
        _write_cstring(st, a0 + len(head), tail)
        return a0
    if name == "system_sprintf":
        fmt = _read_cstring(binary, st, a1)
        if fmt is None or not isinstance(a0, int):
            return None
        text = _format(binary, st, fmt, (a2, a3) + tuple(st.regs[8:12]))
        if text is None:
            return None
        _write_cstring(st, a0, text)
        return len(text)
    return None


def _as_text(binary, st, value):
    """A pointer argument into the path's own memory (a name built on the stack) becomes ('str', text)."""
    if isinstance(value, int) and value in st.mem:
        raw = _read_cstring(binary, st, value)
        if raw and all(0x20 <= c < 0x7f for c in raw):
            return ("str", raw.decode())
    return value


def _branch(base, rt, a, b):
    if base == 0x04:
        return a == b
    if base == 0x05:
        return a != b
    sa = a - (1 << 32) if a & 0x80000000 else a
    if base == 0x01:
        return sa < 0 if rt in (0, 2) else sa >= 0
    if base == 0x06:
        return sa <= 0
    return sa > 0


# --- Module analysis ------------------------------------------------------------------------------

class Module:
    """A scanned binary: functions, calls with argument expressions, references to data."""

    def __init__(self, name, data, stubs=None, base=None):
        self.name = name
        self.bin = Binary(name, data)
        self.base = BASES.get(name, 0) if base is None else base
        self.stubs = stubs or {}  # stub address -> callee name
        self.pointers = self.bin.relocated_words()
        text = struct.unpack_from(f"<{self.bin.text_size // 4}I", data, self.bin.text_off)
        starts = {(w & 0x3ffffff) << 2 for w in text if w >> 26 == 3}
        starts |= set(self.pointers.values())
        starts.add(self.bin.entry)
        starts.add(self.bin.text_addr)
        lo, hi = self.bin.text_addr, self.bin.text_addr + self.bin.text_size
        self.starts = sorted(s for s in starts if lo <= s < hi and s % 4 == 0)
        self.functions = {}
        builders = frozenset(a for a, n in self.stubs.items() if n in BUILDERS)
        for k, s in enumerate(self.starts):
            e = self.starts[k + 1] if k + 1 < len(self.starts) else hi
            self.functions[s] = analyse_function(self.bin, s, e, builders)
        self.gstores = defaultdict(list)
        for fn in self.functions.values():
            for addr, value in fn.gstores:
                self.gstores[addr].append(value)
        self._emu, self._memo = {}, {}

    def function_of(self, addr):
        k = bisect.bisect_right(self.starts, addr) - 1
        return self.starts[k] if k >= 0 else self.bin.text_addr

    def runtime(self, addr):
        return self.base + addr if self.base else None

    def label(self, addr):
        """`0x08e9c174` for a module with a known runtime base, else `+0x2174`."""
        return f"{self.base + addr:#010x}" if self.base else f"+{addr:#x}"

    def calls(self):
        for fn in self.functions.values():
            for site, target, args in fn.calls:
                yield fn, site, target, args

    def refs(self):
        for fn in self.functions.values():
            for site, target in fn.refs:
                yield fn, site, target

    def callee(self, target):
        if target in self.stubs:
            return self.stubs[target]
        return None

    # Expression resolution ------------------------------------------------------------------------

    def resolve(self, value, depth=0):
        """Simplify an argument expression: local getters are evaluated, call results of imported functions
        become ('call', name, args), globals written with a single value are replaced by it. Memoised;
        a cycle (a global whose stored value reads itself) resolves to the unresolved expression."""
        if value is None or isinstance(value, int) or depth > 6:
            return value
        if value in self._memo:
            return self._memo[value]
        self._memo[value] = value  # cycle guard
        result = self._resolve(value, depth)
        self._memo[value] = result
        return result

    def _resolve(self, value, depth):
        kind = value[0]
        if kind == "ret":
            _, target, args, site = value
            args = tuple(self.resolve(a, depth + 1) for a in args)
            name = self.callee(target)
            if name is not None:
                return ("call", name, args)
            fn = self.functions.get(target)
            if fn is None:
                return None
            key = (target, tuple(a if isinstance(a, int) else None for a in args))
            if fn.leaf or any(isinstance(a, int) for a in key[1]):
                if key not in self._emu:
                    self._emu[key] = emulate(self.bin, target, key[1], self.stubs)
                if self._emu[key] is not None:
                    return self._emu[key]
            rets = {r for r in fn.returns if r is not None}
            if len(rets) == 1:
                return self.resolve(substitute(rets.pop(), args), depth + 1)
            return ("ret", target, args, None)
        if kind == "built":
            return ("built", self.resolve(value[1], depth + 1))
        if kind == "call":  # an imported call whose arguments were substituted from a caller
            return ("call", value[1], tuple(self.resolve(a, depth + 1) for a in value[2]))
        if kind == "gload":
            stored = self.gstores.get(value[1], [])
            if not stored or len(stored) > 8:
                return value
            resolved = [self.resolve(v, depth + 1) for v in stored]
            if None not in resolved and len(set(resolved)) == 1:
                return resolved[0]
            return value
        return value

    def string_at(self, value):
        if isinstance(value, tuple) and value[0] == "str":
            return value[1]
        if isinstance(value, tuple) and value[0] == "built":  # the format a buffer was printed with
            fmt = self.string_at(value[1])
            return fmt if fmt and fmt not in ("%s", "%s%s") else None
        return self.bin.cstring(value) if isinstance(value, int) else None


def substitute(expr, args):
    """Replace ('arg', k) inside expr with args[k]."""
    if isinstance(expr, tuple):
        if expr[0] == "arg":
            return args[expr[1]] if expr[1] < len(args) else None
        return tuple(substitute(e, args) if isinstance(e, tuple) else e for e in expr)
    return expr


def has_arg(expr):
    if isinstance(expr, tuple):
        if expr[0] == "arg":
            return True
        return any(has_arg(e) for e in expr if isinstance(e, tuple))
    return False


def describe_expr(module, expr):
    """Short text for an argument: a string literal, a number, a call, or `?`."""
    if isinstance(expr, int):
        s = module.string_at(expr)
        return f'"{s}"' if s else (str(expr) if -0x10000 < expr < 0x10000 else f"{expr:#x}")
    if expr is None:
        return "?"
    if expr[0] == "arg":
        return f"arg{expr[1]}"
    if expr[0] == "call":
        return f"{expr[1]}(" + ", ".join(describe_expr(module, a) for a in expr[2]) + ")"
    if expr[0] == "ret":
        return f"{module.label(expr[1])}(" + ", ".join(describe_expr(module, a) for a in expr[2]) + ")"
    if expr[0] == "gload":
        return f"[{module.label(expr[1])}]"
    if expr[0] == "sp":
        return f"sp+{expr[1]:#x}"
    if expr[0] == "built":
        return "sprintf(" + describe_expr(module, expr[1]) + ")"
    if expr[0] == "str":
        return chr(34) + expr[1] + chr(34)
    return "?"


# --- Uses: names a module asks for, string indices it draws ----------------------------------------

def member_name(module, expr):
    """Name a find_member/accessor table expression resolves to (find_member's name argument), or None."""
    if isinstance(expr, tuple) and expr[0] == "call" and expr[1] == FIND:
        return module.string_at(expr[2][1]) if len(expr[2]) > 1 else None
    return None


def table_key(module, table):
    """Name of the string table an accessor call reads: the member name container_ehp_find_member was given,
    else a short description of the table expression (`find_member(?)`, `getter(4)`, `?`)."""
    name = member_name(module, table)
    if name:
        return norm(name)
    if isinstance(table, tuple) and table[0] == "call" and table[1] == FIND:
        return "find_member(" + describe_expr(module, table[2][1] if len(table[2]) > 1 else None) + ")"
    if isinstance(table, tuple) and table[0] == "ret":
        args = ", ".join(describe_expr(module, a) if isinstance(a, int) else "?" for a in table[2])
        return f"{module.label(table[1])}({args})"
    return describe_expr(module, table)


def callers_index(module):
    idx = defaultdict(list)
    for fn, site, target, args in module.calls():
        idx[target].append((fn, site, args))
    return idx


def expand(module, fn, exprs, callers, depth=3):
    """[(function, site, resolved exprs)]: exprs evaluated in fn, and, while they depend on fn's arguments,
    in each caller with that caller's arguments substituted (up to `depth` levels)."""
    out = []
    todo = [(fn, None, tuple(module.resolve(e) for e in exprs), 0)]
    while todo:
        f, site, values, level = todo.pop()
        if not any(has_arg(v) for v in values) or level >= depth or not callers.get(f.start):
            out.append((f, site, values))
            continue
        for cfn, csite, cargs in callers[f.start]:
            todo.append((cfn, csite, tuple(module.resolve(substitute(v, cargs)) for v in values), level + 1))
    return out


def uses(module):
    """Names and string indices the module's calls resolve to.
    Returns {"names": [(function, site, callee, string)], "strings": [(function, site, table, index)]}."""
    callers = callers_index(module)
    names, strings = [], []
    for fn, site, target, args in module.calls():
        callee = module.callee(target)
        if callee == ACCESSOR:
            for f, s, (table, index) in expand(module, fn, args[:2], callers):
                strings.append((f.start, s or site, table_key(module, table),
                                index if isinstance(index, int) else None))
            continue
        for arg in args:
            if arg is None or isinstance(arg, tuple) and arg[0] in ("arg", "sp"):
                continue
            text = module.string_at(module.resolve(arg))
            if text and (ASSET.search(text) or "/" in text):
                names.append((fn.start, site, callee or module.label(target), text))
    return {"names": names, "strings": strings}


# --- Disc index -----------------------------------------------------------------------------------

def norm(name):
    """Lower-case name with the language letter normalised: title_msg_j.bin -> title_msg_<l>.bin."""
    return LANG.sub("_<l>", name.lower())


def pattern_of(text):
    """Regex for a module string: printf specifiers and language letters become wildcards."""
    out, pos = [], 0
    for m in PRINTF.finditer(text):
        out.append(re.escape(text[pos:m.start()]))
        out.append(r"[^/]*?")
        pos = m.end()
    out.append(re.escape(text[pos:]))
    return "".join(out)


class Disc:
    """Every archive and its layouts and string tables (nested and embedded archives included)."""

    def __init__(self, game):
        game = Path(game)
        self.usrdir, self.boot = game / "USRDIR", game / "SYSDIR" / "BOOT.BIN"
        self.archives = {}  # archive label -> {"layouts": [...], "tables": [...], "members": set}
        files = sorted(p for p in self.usrdir.rglob("*") if p.is_file() and p.name.lower().endswith(
            (".ehp", ".ehp.gz")))
        for path in files:
            label = path.relative_to(self.usrdir).as_posix()
            self._add(label, ehp.read_file(path))
        for offset, archive in ehp.embedded_archives(self.boot.read_bytes()):
            self._add(f"BOOT.BIN@{offset:#x}", archive)

    def _add(self, label, data):
        if not ehp.is_archive(data):
            return
        entry = self.archives.setdefault(label, {"layouts": [], "tables": [], "members": set()})
        for name, blob in ehp.parse(data):
            name, blob = ehp.unwrap(name, blob)
            entry["members"].add(name.lower())
            if ehp.is_archive(blob):
                self._add(f"{label}/{name}", blob)
            elif name.lower().endswith(".ehf"):
                entry["layouts"].append(name)
            elif name.lower().endswith(".bin") and is_string_table(blob):
                entry["tables"].append(name)

    def items(self, kind):
        for label, entry in self.archives.items():
            for name in entry[kind]:
                yield label, name


def is_string_table(blob):
    try:
        strtbl.parse(blob)
        return True
    except (strtbl.TableError, struct.error, ValueError, UnicodeDecodeError):
        return False


# --- Building the map -----------------------------------------------------------------------------

def load_registry(path):
    """re/functions.csv as ({absolute BOOT.BIN address: name}, {(module, absolute address): name})."""
    boot, qualified = {}, {}
    if not Path(path).exists():
        return boot, qualified
    for row in csv.DictReader(open(path, encoding="utf-8")):
        prefix, _, address = row["id"].rpartition(":")
        try:
            value = int(address, 16)
        except ValueError:
            continue
        if prefix:
            qualified[(prefix, value)] = row["name"]
        else:
            boot[value] = row["name"]
    return boot, qualified


def name_of(provider, addr, registry):
    """Registry name of a provider-relative function address, else `provider+0xoffset`."""
    boot, qualified = registry
    base = BASES.get(provider, 0)
    if provider == "BOOT.BIN":
        return boot.get(BOOT_BASE + addr, f"FUN_{BOOT_BASE + addr:08x}")
    name = qualified.get((provider, base + addr)) if base else None
    if name is None and base and provider in ("rel_duel_eng", "rel_duel_draw"):
        name = boot.get(base + addr)  # these two have plain registry ids
    return name or f"{provider}+{addr:#x}"


def load_modules(game, registry, only=None):
    """{name: Module} for BOOT.BIN and every gmodule/*.prx (or only those in `only`), stubs named; plus
    {name: set(providers)}."""
    game = Path(game)
    raw = {"BOOT.BIN": (game / "SYSDIR" / "BOOT.BIN").read_bytes()}
    for p in sorted((game / "USRDIR" / "gmodule").glob("*.prx")):
        raw[p.stem] = p.read_bytes()
    elfs = {n: prx_imports.Elf(d, 0) for n, d in raw.items()}
    index = {}
    for provider, elf in elfs.items():
        for nid, (lib, addr) in prx_imports.exports(elf).items():
            index.setdefault((lib, nid), (provider, addr))
    modules, providers = {}, {}
    for name, data in raw.items():
        if only is not None and name not in only:
            continue
        stubs, used = {}, set()
        if name != "BOOT.BIN":
            for lib, nid, stub in prx_imports.imports(elfs[name]):
                if (lib, nid) in index:
                    provider, addr = index[(lib, nid)]
                    stubs[stub] = name_of(provider, addr, registry)
                    if provider not in ("BOOT.BIN", name):
                        used.add(provider)
        else:
            boot, _ = registry
            stubs = {a - BOOT_BASE: n for a, n in boot.items()}
        modules[name] = Module(name, data, stubs)
        providers[name] = used
    return modules, providers


def scene_tables(boot):
    """({scene: module name}, {module id: module name}) from BOOT.BIN's game-module and scene tables."""
    b = boot.bin
    ids, addr = {}, GAME_TABLE - BOOT_BASE
    while True:
        ident, _, name_ptr = b.read(addr, 4), b.read(addr + 4, 4), b.read(addr + 8, 4)
        if not ident or not name_ptr:
            break
        name = b.cstring(name_ptr)
        if not name:
            break
        ids[ident] = name[:-4] if name.endswith(".prx") else name
        addr += 16
    scenes = {}
    for k in range(SCENE_COUNT):
        scene, mid = b.read(SCENE_TABLE - BOOT_BASE + 8 * k, 4), b.read(SCENE_TABLE - BOOT_BASE + 8 * k + 4, 4)
        if mid in ids:
            scenes[scene] = ids[mid]
    return scenes, ids


class Matcher:
    """Matches module strings against archive labels and member names."""

    def __init__(self, disc):
        self.disc = disc
        self.archive_norm = {label: norm(label) for label in disc.archives}
        self._hit_cache, self._archive_cache = {}, {}
        self.member_index = defaultdict(set)  # normalised member name -> {(archive label, member name)}
        for label, entry in disc.archives.items():
            for kind in ("layouts", "tables"):
                for m in entry[kind]:
                    self.member_index[norm(m)].add((label, m))
            for m in entry["members"]:
                self.member_index[norm(m)].add((label, m))

    def archives_for(self, text):
        """Archive labels a path string (or printf pattern) names."""
        if text not in self._archive_cache:
            self._archive_cache[text] = self._archives_for(text)
        return self._archive_cache[text]

    def _archives_for(self, text):
        t = text.lower().lstrip("/")
        if PREFIX.match(t):  # "cardinfo_" + language code + ".ehp", built at runtime
            rx = re.compile(r"(?:^|/)" + re.escape(t) + LANG_CODES + r"\.ehp(?:\.gz)?$")
            return {label for label in self.archive_norm if "@" not in label and rx.search(label.lower())}
        if not t.endswith((".ehp", ".ehp.gz", "/")) and not PRINTF.search(t):
            return set()
        if "disc0:" in t:
            t = t.split("usrdir/", 1)[-1]
        if not t.endswith((".ehp", ".ehp.gz", "/")):
            return set()  # a printf pattern of something else (a member name, a message)
        rx = re.compile(r"(?:^|/)" + pattern_of(norm(t)) + (r"" if t.endswith("/") else r"(?:\.gz)?$"))
        return {label for label, n in self.archive_norm.items() if "@" not in label and rx.search(n)}

    def member_hits(self, text):
        """{(archive label, member name)} that a member-name string (or printf pattern) names."""
        t = text.lower().rsplit("/", 1)[-1]
        if PREFIX.match(t):  # "DICT_" + language letter + ".bin", built at runtime
            rx = re.compile("^" + re.escape(t) + LANG_CODES + r"\.[a-z0-9]+$")
            return {hit for m, hits in self.member_index.items() for hit in hits if rx.match(hit[1].lower())}
        if not ASSET.search(t):
            return set()
        key = norm(t)
        if key in self._hit_cache:
            return self._hit_cache[key]
        self._hit_cache[key] = out = self._member_hits(key)
        return out

    def _member_hits(self, key):
        if not PRINTF.search(key):
            return set(self.member_index.get(key, ()))
        rx = re.compile("^" + pattern_of(key) + "$")
        out = set()
        for m, hits in self.member_index.items():
            if rx.match(m):
                out |= hits
        return out


def collect(module, matcher):
    """Per module: the strings it uses with the strongest basis, and the archives/members they name."""
    strings = {}  # string -> (basis, set of function labels)
    rank = {"call": 0, "code": 1, "data": 2}

    def add(text, basis, func=None):
        cur = strings.get(text)
        if cur is None or rank[basis] < rank[cur[0]]:
            strings[text] = (basis, set() if cur is None else cur[1])
        if func is not None:
            strings[text][1].add(func)

    u = uses(module)
    for f, site, callee, text in u["names"]:
        add(text, "call", module.label(f))
    seen_targets = defaultdict(set)
    for fn, site, target in module.refs():
        seen_targets[target].add(fn.start)
    for target in list(module.pointers.values()):
        seen_targets.setdefault(target, set())
    data = module.bin.data_strings()
    addrs = sorted(data)
    for target, funcs in seen_targets.items():
        # the string at the target, or the first string within 8 bytes (records {u32, char name[]})
        k = bisect.bisect_left(addrs, target)
        if k >= len(addrs) or addrs[k] - target > 8:
            continue
        head = addrs[k]
        text = data[head]
        if not (ASSET.search(text) or PRINTF.search(text) and "/" in text):
            continue
        add(text, "code", None)
        for f in funcs:
            strings[text][1].add(module.label(f))
        # fixed-stride name array starting there
        stride = 0
        if k + 1 < len(addrs) and ASSET.search(data[addrs[k + 1]] or ""):
            stride = addrs[k + 1] - head
        j, nxt = k + 1, head + stride
        while stride and j < len(addrs) and addrs[j] == nxt and ASSET.search(data[addrs[j]]) and \
                Path(data[addrs[j]]).suffix.lower() == Path(text).suffix.lower():
            add(data[addrs[j]], "code", None)
            for f in funcs:
                strings[data[addrs[j]]][1].add(module.label(f))
            j, nxt = j + 1, nxt + stride
    for text in data.values():
        if ASSET.search(text) or PREFIX.match(text) or (PRINTF.search(text) and "/" in text and "." in text):
            add(text, "data")
    return strings, u


def build_map(game, registry_path=REPO / "re" / "functions.csv"):
    registry = load_registry(registry_path)
    modules, providers = load_modules(game, registry)
    disc = Disc(game)
    matcher = Matcher(disc)
    scenes, ids = scene_tables(modules["BOOT.BIN"])
    # Library modules: loaded by constant id, or imported.
    loads = defaultdict(set)
    for name, m in modules.items():
        for fn, site, target, args in m.calls():
            if m.callee(target) in MODULE_LOAD and isinstance(m.resolve(args[0]), int):
                mid = m.resolve(args[0])
                if mid in ids and ids[mid] != name:
                    loads[name].add(ids[mid])
        loads[name] |= providers.get(name, set())
    collected = {name: collect(m, matcher) for name, m in modules.items()}
    # Bare archive names held by BOOT.BIN (for example the bust-up table) are available to every module.
    boot_bare = {t: v for t, v in collected["BOOT.BIN"][0].items() if is_bare_archive(t)}
    per_module = {}
    for name, m in modules.items():
        strings, u = collected[name]
        archives = {}

        def claim(label, basis, text, funcs):
            cur = archives.get(label)
            if cur is None or BASIS_RANK[basis] < BASIS_RANK[cur["basis"]]:
                archives[label] = {"basis": basis, "string": text, "functions": sorted(funcs)}

        dirs = {d for d in (dir_of(t) for t in strings) if d}
        bare = {t: v for t, v in strings.items() if is_bare_archive(t)}
        texts = set(m.bin.data_strings().values())
        if ".ehp" in texts:  # stems completed with a separate ".ehp" at runtime (duel/basic_ue + .ehp)
            for stem in texts:
                if STEM.match(stem):
                    bare.setdefault(stem + ".ehp", ("data", set()))
        for text, (basis, funcs) in strings.items():
            if text in bare:
                continue
            for label in matcher.archives_for(text):
                claim(label, basis, text, funcs)
        for pool, own in ((bare, True), (boot_bare if name != "BOOT.BIN" else {}, False)):
            for text, (basis, funcs) in pool.items():
                labels = matcher.archives_for(text)
                composed = {lb for lb in labels if any(in_dir(lb, d) for d in dirs)}
                if composed:
                    for label in composed:
                        claim(label, worst(basis, "code"), text, funcs if own else ())
                elif own and len({matcher.archive_norm[lb] for lb in labels}) == 1:
                    for label in labels:  # a single archive family on the disc has this name
                        claim(label, basis, text, funcs)
        if name == "BOOT.BIN":  # embedded archives addressed by the code
            emb = {ehp.elf_module_offset(m.bin.data, off): off for off, _ in ehp.embedded_archives(m.bin.data)}
            for fn, site, target in m.refs():
                if target in emb:
                    label = f"BOOT.BIN@{emb[target]:#x}"
                    archives.setdefault(label, {"basis": "code", "string": None, "functions": []})
                    if m.label(fn.start) not in archives[label]["functions"]:
                        archives[label]["functions"].append(m.label(fn.start))
        members = {}  # (archive label, member name) -> best {"string", "basis", "functions"}
        for text, (basis, funcs) in strings.items():
            hits = matcher.member_hits(text)
            if not hits:
                continue
            own = {h for h in hits if _inside(h[0], archives)}
            if not own and len({matcher.archive_norm[h[0]] for h in hits}) == 1:
                own = hits  # a single archive family holds this member name: unambiguous
            for key in own:
                cur = members.get(key)
                if cur is None or BASIS_RANK[basis] < BASIS_RANK[cur["basis"]]:
                    members[key] = {"string": text, "basis": basis, "functions": sorted(funcs)}
        # String indices per table name.
        indices = defaultdict(lambda: defaultdict(set))
        for f, site, table, index in u["strings"]:
            indices[table][m.label(f)].add(index)
        per_module[name] = {"scenes": sorted(s for s, mod in scenes.items() if mod == name),
                            "loads": sorted(loads[name]), "archives": archives, "members": members,
                            "string_indices": indices, "calls": u}
    # Attribution of every layout and table.
    result = {"layouts": {}, "tables": {}}
    for kind in result:
        for label, member in disc.items(kind):
            entries = []
            for name, info in per_module.items():
                best = info["members"].get((label, member))
                if best is not None:
                    best = {"module": name, **best}
                else:
                    arch = [x for x in info["archives"] if label == x or label.startswith(x + "/")]
                    if arch:
                        via = info["archives"][arch[0]]
                        best = {"module": name, "basis": "archive", "string": via["string"] or arch[0],
                                "functions": via["functions"]}
                if best:
                    entries.append(best)
            result[kind][f"{label}:{member}"] = entries
    return {"scenes": scenes, "ids": ids, "modules": per_module, "attribution": result, "disc": disc}


BASIS_RANK = {"call": 0, "code": 1, "data": 2, "archive": 3}


def is_bare_archive(text):
    return "/" not in text and text.lower().endswith((".ehp", ".ehp.gz"))


def dir_of(text):
    """Directory a string names: `field/bustup`, `database/gallery/%s` -> `database/gallery`, else None."""
    t = text.rstrip("/")
    if t.endswith("/%s"):
        t = t[:-3]
    elif "." in t.rsplit("/", 1)[-1] or "%" in t or "/" not in t or " " in t:
        return None
    return t.lower() or None


def in_dir(label, directory):
    """True if an archive label sits directly in `directory` (a suffix of its directory path)."""
    parent = label.rsplit("/", 1)[0].lower() if "/" in label else ""
    return parent == directory or parent.endswith("/" + directory)


def worst(a, b):
    return a if BASIS_RANK[a] > BASIS_RANK[b] else b


def _inside(label, archives):
    """True if an archive label is one of `archives` or nested inside one."""
    return label in archives or any(label.startswith(a + "/") for a in archives)


def scenes_of(module_name, info):
    """Scenes that run a module: its own scene ids and the scenes of the modules that load it (transitively);
    BOOT.BIN is resident."""
    if module_name == "BOOT.BIN":
        return ["resident"]
    out, seen, todo = set(info["modules"][module_name]["scenes"]), {module_name}, [module_name]
    while todo:
        cur = todo.pop()
        for name, mi in info["modules"].items():
            if cur in mi["loads"] and name not in seen:
                seen.add(name)
                if mi["scenes"]:
                    out |= set(mi["scenes"])
                else:
                    todo.append(name)
    return sorted(out)


def to_json(info):
    mods = {}
    for name, mi in info["modules"].items():
        mods[name] = {
            "scenes": mi["scenes"], "run_in_scenes": scenes_of(name, info), "loads": mi["loads"],
            "base": f"{BASES[name]:#010x}" if name in BASES else None,
            "archives": [{"archive": a, **v} for a, v in sorted(mi["archives"].items())],
            "members": [{"archive": a, "member": n, **v} for (a, n), v in sorted(mi["members"].items())],
            "string_indices": {t: {f: sorted((i for i in s if i is not None)) + (["?"] if None in s else [])
                                   for f, s in sorted(fs.items())} for t, fs in sorted(mi["string_indices"].items())},
            "string_sites": site_summary(mi["calls"]["strings"]),
        }
    attribution = {}
    for kind, items in info["attribution"].items():
        attribution[kind] = {}
        for key, entries in sorted(items.items()):
            attribution[kind][key] = [{**e, "scenes": scenes_of(e["module"], info)} for e in entries]
    return {"schema": "tf3-scene-map", "version": 1,
            "scenes": [{"scene": s, "label": SCENE_LABELS.get(s, ""), "module": m}
                       for s, m in sorted(info["scenes"].items())],
            "modules": mods, "attribution": attribution}


def site_summary(requests):
    """Counts over accessor requests (function, site, table key, index): how many name their table and how many
    have a constant index."""
    named = [r for r in requests if r[2].endswith(".bin")]
    return {"requests": len(requests), "table_named": len(named),
            "index_constant": sum(1 for r in requests if r[3] is not None),
            "table_and_index": sum(1 for r in named if r[3] is not None)}


def coverage(doc):
    """{kind: (total, attributed to a module, attributed to a scene, by basis Counter, unattributed list)}."""
    out = {}
    sites = Counter()
    for mi in doc["modules"].values():
        sites.update(mi["string_sites"])
    out["string_requests"] = dict(sites)
    for kind, items in doc["attribution"].items():
        total = len(items)
        to_module = sum(1 for e in items.values() if e)
        to_scene = sum(1 for e in items.values() if any(x["scenes"] for x in e))
        basis = Counter(min((x["basis"] for x in e), key=BASIS_RANK.get) for e in items.values() if e)
        missing = sorted(k for k, e in items.items() if not e)
        out[kind] = (total, to_module, to_scene, basis, missing)
    return out


# --- Command line ---------------------------------------------------------------------------------

def output_allowed(path):
    resolved = Path(path).resolve()
    try:
        rel = resolved.relative_to(REPO.resolve())
    except ValueError:
        return True
    return "extracted" in rel.parts


def cmd_map(args):
    if not output_allowed(args.output):
        print("refusing to write inside the repository (use a scratch directory or extracted/)", file=sys.stderr)
        return 2
    doc = to_json(build_map(args.game))
    Path(args.output).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


def cmd_check(args):
    doc = to_json(build_map(args.game))
    cov = coverage(doc)
    failed = False
    sites = cov.pop("string_requests")
    for kind, (total, to_module, to_scene, basis, missing) in cov.items():
        print(f"{kind}: {total} on the disc, {to_module} attributed to a module "
              f"({to_module * 100 // max(total, 1)} %), {to_scene} to a scene; by best basis: "
              + ", ".join(f"{k} {v}" for k, v in sorted(basis.items(), key=lambda kv: BASIS_RANK[kv[0]])))
        groups = Counter(k.split(":", 1)[0].split("/")[0] if "@" not in k else k.split("/")[0] for k in missing)
        if missing:
            print(f"  unattributed by top-level directory: "
                  + ", ".join(f"{g} {n}" for g, n in sorted(groups.items())))
        if args.verbose:
            for k in missing:
                print(f"    {k}")
        failed |= total == 0
    print(f"string accessor requests ({ACCESSOR}, after following wrappers to their callers): "
          f"{sites.get('requests', 0)}, table named {sites.get('table_named', 0)}, constant index "
          f"{sites.get('index_constant', 0)}, both {sites.get('table_and_index', 0)}")
    print("OK" if not failed else "FAILED")
    return 1 if failed else 0


def cmd_refs(args):
    registry = load_registry(REPO / "re" / "functions.csv")
    modules, _ = load_modules(args.game, registry, {args.module})
    m = modules[args.module]
    matcher = Matcher(Disc(args.game)) if args.disc else None
    strings, u = collect(m, matcher)
    pat = re.compile(args.filter, re.I) if args.filter else None
    for text, (basis, funcs) in sorted(strings.items()):
        if pat and not pat.search(text):
            continue
        print(f"{basis:5s} {text}  " + " ".join(sorted(funcs)))
    return 0


def cmd_calls(args):
    registry = load_registry(REPO / "re" / "functions.csv")
    modules, _ = load_modules(args.game, registry, {args.module})
    m = modules[args.module]
    pat = re.compile(args.callee)
    for fn, site, target, call_args in sorted(m.calls(), key=lambda c: c[1]):
        name = m.callee(target) or m.label(target)
        if pat.search(name):
            shown = ", ".join(describe_expr(m, m.resolve(a)) for a in call_args)
            print(f"{m.label(site)} in {m.label(fn.start)}: {name}({shown})")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("map")
    p.add_argument("game", type=Path, help="extracted PSP_GAME directory")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_map)
    p = sub.add_parser("check")
    p.add_argument("game", type=Path)
    p.add_argument("-v", "--verbose", action="store_true", help="list every unattributed layout and table")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("refs")
    p.add_argument("game", type=Path)
    p.add_argument("module")
    p.add_argument("--filter")
    p.add_argument("--disc", action="store_true")
    p.set_defaults(func=cmd_refs)
    p = sub.add_parser("calls")
    p.add_argument("game", type=Path)
    p.add_argument("module")
    p.add_argument("callee")
    p.set_defaults(func=cmd_calls)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
