// SPDX-License-Identifier: GPL-2.0-only
// Put code that lies outside every function back into functions (registry hygiene, round 5, 2026-11-04).
// An "orphan" is a run of disassembled instructions in an executable block that no function body contains.
// The script handles the two causes found in this project:
//  1. Switch bodies cut at a jump table: an orphan instruction is a case of a pointer table that a function loads
//     (a code reference to the table start). That function is decompiled and DecompilerSwitchAnalysisCmd recovers
//     the table, adds the computed-jump references and the switch override; the body is then re-derived from its
//     flow (CreateFunctionCmd.fixupFunctionBody). Tails reached by an ordinary branch of a function are re-derived
//     the same way.
//  2. Functions reached only through data (callback and descriptor tables, 8-byte `j` entries): an orphan run
//     that starts right after a function end (after `jr`/`j` and its delay slot) or at an address that a data
//     table without code references points to becomes a function (CreateFunctionCmd), followed by the same switch
//     recovery for the new function.
// Words that were never disassembled (dead code after an unconditional branch, data) are left alone.
// Arguments: "dry" (report only) or "apply"; an optional second argument limits the run to one address range
// "start-end" (hex). Idempotent. Usage (headless, not -readOnly for apply):
//   analyzeHeadless <projdir> TF3 -process rel_duel_draw.prx -noanalysis -scriptPath tools/ghidra
//       -postScript RepairOrphanCode.java apply
// Recorded in docs/subsystems/system.md ("Registry hygiene, round 5: code outside functions").
// @category TF3
import java.util.*;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.cmd.function.DecompilerSwitchAnalysisCmd;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.*;

public class RepairOrphanCode extends GhidraScript {
	private DecompInterface ifc;
	private boolean apply;
	private int switches, tails, created, failed;

	private AddressSet orphans(AddressSetView limit) {
		AddressSet covered = new AddressSet();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) covered.add(f.getBody());
		AddressSet out = new AddressSet();
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isExecute() || !b.isInitialized()) continue;
			AddressSet s = new AddressSet(b.getStart(), b.getEnd()).subtract(covered);
			if (limit != null) s = s.intersect(limit);
			InstructionIterator it = currentProgram.getListing().getInstructions(s, true);
			while (it.hasNext()) {
				Instruction i = it.next();
				out.add(i.getMinAddress(), i.getMaxAddress());
			}
		}
		return out;
	}

	/** Executable ranges outside every function (disassembled or not). */
	private AddressSet gaps(AddressSetView limit) {
		AddressSet covered = new AddressSet();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) covered.add(f.getBody());
		AddressSet out = new AddressSet();
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isExecute() || !b.isInitialized()) continue;
			AddressSet s = new AddressSet(b.getStart(), b.getEnd()).subtract(covered);
			if (limit != null) s = s.intersect(limit);
			out.add(s);
		}
		return out;
	}

	private boolean terminal(Instruction i) {
		if (i == null) return false;
		String m = i.getMnemonicString().toLowerCase();
		return m.equals("jr") || m.equals("j") || m.equals("_jr") || m.equals("_j");
	}

	/** Start of the pointer table containing address t (walk back over words that point into executable code). */
	private Address tableStart(Address t) throws Exception {
		Address a = t;
		for (int k = 0; k < 4096; k++) {
			Address p = a.subtract(4);
			if (!isCodePointer(p)) break;
			if (currentProgram.getReferenceManager().getReferenceCountTo(a) > 0 && hasCodeRef(a)) return a;
			a = p;
		}
		return a;
	}

	private boolean isCodePointer(Address p) {
		try {
			long v = getInt(p) & 0xffffffffL;
			Address x = toAddr(v);
			MemoryBlock b = currentProgram.getMemory().getBlock(x);
			return b != null && b.isExecute() && (v & 3) == 0;
		} catch (Exception e) {
			return false;
		}
	}

	private boolean hasCodeRef(Address a) {
		for (Reference r : currentProgram.getReferenceManager().getReferencesTo(a)) {
			if (getInstructionAt(r.getFromAddress()) != null) return true;
		}
		return false;
	}

	private Function codeUser(Address table) {
		for (Reference r : currentProgram.getReferenceManager().getReferencesTo(table)) {
			Function f = getFunctionContaining(r.getFromAddress());
			if (f != null && getInstructionAt(r.getFromAddress()) != null) return f;
		}
		return null;
	}

	private boolean recoverSwitches(Function f) throws Exception {
		long before = f.getBody().getNumAddresses();
		DecompileResults res = ifc.decompileFunction(f, 60, monitor);
		if (res != null && res.decompileCompleted() && apply) {
			new DecompilerSwitchAnalysisCmd(res).applyTo(currentProgram, monitor);
		}
		if (apply) CreateFunctionCmd.fixupFunctionBody(currentProgram, f, monitor);
		long after = f.getBody().getNumAddresses();
		if (after != before) println(String.format("body %s %s %d -> %d", f.getEntryPoint(), f.getName(), before, after));
		return after != before;
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		apply = args.length > 0 && args[0].equals("apply");
		AddressSet limit = null;
		if (args.length > 1) {
			String[] p = args[1].split("-");
			limit = new AddressSet(toAddr(Long.parseUnsignedLong(p[0].replaceFirst("^0x", ""), 16)),
				toAddr(Long.parseUnsignedLong(p[1].replaceFirst("^0x", ""), 16)));
		}
		ifc = new DecompInterface();
		ifc.openProgram(currentProgram);
		ReferenceManager rm = currentProgram.getReferenceManager();
		AddressSet orph = orphans(limit);
		long startBytes = orph.getNumAddresses();
		println("orphan instruction bytes before: " + startBytes);
		for (int round = 0; round < (apply ? 4 : 1); round++) {
		long roundStart = orph.getNumAddresses();
		int createdBefore = created + switches;
		// 1. Parents: functions that branch into an orphan, or load a pointer table whose entries point into one.
		//    Function pointers (an address computed by an instruction, or held in a table that no code loads)
		//    are entries.
		LinkedHashSet<Function> parents = new LinkedHashSet<>();
		HashSet<Address> dataEntries = new HashSet<>();
		AddressIterator ai = rm.getReferenceDestinationIterator(orph, true);
		while (ai.hasNext()) {
			Address to = ai.next();
			for (Reference r : rm.getReferencesTo(to)) {
				Address from = r.getFromAddress();
				Function ff = getFunctionContaining(from);
				if (r.getReferenceType().isFlow()) {
					if (ff != null) parents.add(ff);
				} else if (getInstructionAt(from) != null) {
					dataEntries.add(to);
				} else {
					Address t = tableStart(from);
					if (hasCodeRef(t)) {
						Function user = codeUser(t);
						if (user != null) parents.add(user);
					} else {
						dataEntries.add(to);
					}
				}
			}
		}
		for (Function f : parents) {
			if (monitor.isCancelled()) break;
			if (recoverSwitches(f)) switches++;
		}

		// 2. New functions. First the gaps that start right after a function's last delay slot (the word two
		//    before is a `jr`/`j` of that function), in address order, so that each new function ends where the
		//    next gap starts; then the data-referenced entries that are still outside every function.
		boolean grew = true;
		for (int pass = 0; grew && pass < 64 && apply; pass++) {
			grew = false;
			for (AddressRange r : gaps(limit).getAddressRanges()) {
				Address s = r.getMinAddress();
				if (s.getOffset() < 8) continue;
				Function pf = getFunctionContaining(s.subtract(4));
				Instruction j = getInstructionAt(s.subtract(8));
				if (pf == null || !terminal(j) || getFunctionContaining(s.subtract(8)) != pf) continue;
				if (!pf.getBody().getMaxAddress().equals(s.subtract(1))) continue; // a hole inside pf's extent
				if (getInt(s) == 0) continue;
				new DisassembleCommand(s, null, true).applyTo(currentProgram, monitor);
				if (getInstructionAt(s) == null) continue;
				CreateFunctionCmd cmd = new CreateFunctionCmd(s);
				if (cmd.applyTo(currentProgram, monitor)) {
					created++;
					grew = true;
					println("create " + s + " (after " + pf.getName() + ")");
					Function f = getFunctionAt(s);
					if (f != null) recoverSwitches(f);
				}
			}
		}
		orph = orphans(limit);
		TreeSet<Address> entries = new TreeSet<>();
		for (Address e : dataEntries) if (orph.contains(e)) entries.add(e);
		for (Address e : entries) {
			if (monitor.isCancelled()) break;
			if (getFunctionContaining(e) != null) continue;
			println("create " + e);
			if (!apply) { created++; continue; }
			new DisassembleCommand(e, null, true).applyTo(currentProgram, monitor);
			CreateFunctionCmd cmd = new CreateFunctionCmd(e);
			if (cmd.applyTo(currentProgram, monitor)) {
				created++;
				Function f = getFunctionAt(e);
				if (f != null) recoverSwitches(f);
			} else {
				failed++;
				printerr("cannot create " + e + ": " + cmd.getStatusMsg());
			}
		}
		orph = orphans(limit);
		println("round " + round + ": orphan instruction bytes " + roundStart + " -> " + orph.getNumAddresses());
		if (orph.getNumAddresses() == roundStart && created + switches == createdBefore) break;
		}
		long endBytes = orphans(limit).getNumAddresses();
		println(String.format("RESULT %s: parents re-derived %d, functions created %d, failed %d, orphan instruction bytes %d -> %d",
			apply ? "apply" : "dry", switches, created, failed, startBytes, endBytes));
		ifc.dispose();
	}
}
