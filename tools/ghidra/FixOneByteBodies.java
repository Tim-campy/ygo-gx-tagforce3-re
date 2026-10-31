// SPDX-License-Identifier: GPL-2.0-only
// Repair functions whose body is a single byte. ApplyNames.java creates a missing function at a named address;
// when no instruction had been disassembled there (import stubs, effect handlers reached only through data
// tables), Ghidra records a one-byte body although the decompiler follows the real code, so the registry size
// and the byte counts of tools/progress.py are wrong. For each such function the script disassembles from the
// entry (following flow) and re-derives the body with CreateFunctionCmd.fixupFunctionBody. A function whose entry
// does not decode as an instruction is left alone and listed. Idempotent. Optional argument "dry" only reports.
// Usage (headless, not -readOnly, so the fix is saved):
//   analyzeHeadless <projdir> TF3 -process rel_duel_eng.prx -noanalysis -scriptPath tools/ghidra
//       -postScript FixOneByteBodies.java
// Recorded in docs/subsystems/system.md ("Function boundaries").
// @category TF3

import java.util.ArrayList;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;

public class FixOneByteBodies extends GhidraScript {
	@Override
	protected void run() throws Exception {
		boolean dry = getScriptArgs().length > 0 && getScriptArgs()[0].equals("dry");
		ArrayList<Function> todo = new ArrayList<>();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (!f.isExternal() && !f.isThunk() && f.getBody().getNumAddresses() == 1) {
				todo.add(f);
			}
		}
		int fixed = 0, failed = 0;
		long bytes = 0;
		for (Function f : todo) {
			if (dry) {
				continue;
			}
			if (getInstructionAt(f.getEntryPoint()) == null) {
				new DisassembleCommand(f.getEntryPoint(), null, true).applyTo(currentProgram, monitor);
			}
			if (getInstructionAt(f.getEntryPoint()) == null) {
				printerr("no instruction at " + f.getEntryPoint() + " " + f.getName());
				failed++;
				continue;
			}
			CreateFunctionCmd.fixupFunctionBody(currentProgram, f, monitor);
			long n = f.getBody().getNumAddresses();
			if (n > 1) {
				fixed++;
				bytes += n;
			} else {
				failed++;
			}
		}
		println(String.format("one-byte bodies: %d, fixed %d (%d bytes), left %d%s", todo.size(), fixed, bytes, failed,
			dry ? " (dry run)" : ""));
	}
}
