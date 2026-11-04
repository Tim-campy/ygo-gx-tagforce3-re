// SPDX-License-Identifier: GPL-2.0-only
// Create functions that createFunction refuses: 8-byte entries that only set an argument in the delay slot of a
// jump into another function (BOOT.BIN 0x0881d8f4, "j container_resolve_path; move a3, zero"; rel_duel_draw
// 0x0989c910) and that the analyser had typed as data. Arguments come in pairs <entry> <length in bytes> (hex, with
// or without 0x); the script clears data units in the range, disassembles it and creates a function with exactly
// that body under its default name
// (ApplyNames.java names it afterwards). Existing functions are left alone, so it is idempotent.
// Usage (headless, not -readOnly, so the functions are saved):
//   analyzeHeadless <projdir> TF3 -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript CreateFunctionBody.java 0x0881d8f4 8
// Recorded in docs/subsystems/system.md ("Function boundaries").
// @category TF3

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.symbol.SourceType;

public class CreateFunctionBody extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length == 0 || args.length % 2 != 0) {
			throw new IllegalArgumentException("usage: CreateFunctionBody.java <entry> <length> [<entry> <length> ...]");
		}
		for (int i = 0; i < args.length; i += 2) {
			Address entry = toAddr(Long.parseUnsignedLong(args[i].replaceFirst("^0x", ""), 16));
			long length = Long.parseUnsignedLong(args[i + 1].replaceFirst("^0x", ""), 16);
			if (getFunctionAt(entry) != null) {
				println("function exists at " + entry);
				continue;
			}
			AddressSet body = new AddressSet(entry, entry.add(length - 1));
			// The analyser may have typed these words as data (seen for both known cases); the range is code
			// by the disassembly, so clear the data units first.
			if (getDataContaining(entry) != null || getDataContaining(entry.add(length - 1)) != null) {
				clearListing(entry, entry.add(length - 1));
				println("cleared data at " + entry);
			}
			new DisassembleCommand(body, body, false).applyTo(currentProgram, monitor);
			CreateFunctionCmd cmd = new CreateFunctionCmd(null, entry, body, SourceType.DEFAULT);
			if (cmd.applyTo(currentProgram, monitor)) {
				println("created " + entry + " (" + length + " bytes)");
			}
			else {
				printerr("cannot create " + entry + ": " + cmd.getStatusMsg());
			}
		}
	}
}
