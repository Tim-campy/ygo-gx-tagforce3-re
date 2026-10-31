// SPDX-License-Identifier: GPL-2.0-only
// Repair a function whose body Ghidra cut short because it could not recover a jump table. Arguments come in
// groups of four: <entry> <jr address> <table address> <entry count> (hex, with or without 0x). For each group
// the script reads <count> 32-bit little-endian case addresses from the table, disassembles them, adds a
// COMPUTED_JUMP reference from the `jr` to each case, writes a decompiler jump-table override, and then
// re-derives the function body from its flow (CreateFunctionCmd.fixupFunctionBody). Idempotent: running it again
// changes nothing. Usage (headless, not -readOnly, so the fix is saved):
//   analyzeHeadless <projdir> TF3 -process rel_duel_eng.prx -noanalysis -scriptPath tools/ghidra
//       -postScript FixJumpTableFunction.java 0x09be2eac 0x09be2f24 0x09deb640 82
// Recorded fixes: docs/subsystems/battle.md, "Function boundaries".
// @category TF3

import java.util.ArrayList;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.pcode.JumpTable;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;

public class FixJumpTableFunction extends GhidraScript {
	private Address addr(String s) {
		return toAddr(Long.parseUnsignedLong(s.replaceFirst("^0x", ""), 16));
	}

	@Override
	protected void run() throws Exception {
		String[] a = getScriptArgs();
		if (a.length == 0 || a.length % 4 != 0) {
			throw new IllegalArgumentException("usage: FixJumpTableFunction.java (<entry> <jr> <table> <count>)...");
		}
		for (int g = 0; g < a.length; g += 4) {
			Address entry = addr(a[g]);
			Address jr = addr(a[g + 1]);
			Address table = addr(a[g + 2]);
			int count = Integer.parseInt(a[g + 3]);
			Function f = getFunctionAt(entry);
			if (f == null) {
				f = createFunction(entry, null);
			}
			if (f == null) {
				printerr("no function at " + entry);
				continue;
			}
			long before = f.getBody().getNumAddresses();
			ArrayList<Address> cases = new ArrayList<>();
			AddressSet starts = new AddressSet();
			for (int i = 0; i < count; i++) {
				Address c = addr(Long.toHexString(getInt(table.add(4L * i)) & 0xffffffffL));
				if (!cases.contains(c)) {
					cases.add(c);
				}
				starts.add(c);
			}
			new DisassembleCommand(starts, null, true).applyTo(currentProgram, monitor);
			Instruction jump = getInstructionAt(jr);
			if (jump == null) {
				printerr("no instruction at " + jr);
				continue;
			}
			int added = 0;
			for (Address c : cases) {
				boolean present = false;
				for (Reference r : jump.getReferencesFrom()) {
					present |= r.getToAddress().equals(c);
				}
				if (!present) {
					jump.addOperandReference(0, c, RefType.COMPUTED_JUMP, SourceType.USER_DEFINED);
					added++;
				}
			}
			new JumpTable(jr, cases, true, 0).writeOverride(f);
			CreateFunctionCmd.fixupFunctionBody(currentProgram, f, monitor);
			println(String.format("%s %s: %d cases (%d references added), body %d -> %d bytes", entry, f.getName(),
				cases.size(), added, before, f.getBody().getNumAddresses()));
		}
	}
}
