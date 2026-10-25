// SPDX-License-Identifier: GPL-2.0-only
// Export every function of the current program as re/functions.csv rows (id,name,group,status,size).
// Group comes from the function's top-level Ghidra namespace (see CLAUDE.md naming), status is left
// blank so tools/progress.py infers unknown/named. Usage (headless):
//   analyzeHeadless <projdir> <proj> -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript ExportFunctions.java <output.csv>
// @category TF3

import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Namespace;

public class ExportFunctions extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			throw new IllegalArgumentException("usage: ExportFunctions.java <output.csv>");
		}
		int count = 0;
		try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
			out.println("id,name,group,status,size");
			for (Function function : currentProgram.getFunctionManager().getFunctions(true)) {
				if (function.isExternal()) {
					continue;
				}
				// Ghidra shows a thunk under its target's name; keep the rows distinguishable.
				String name = function.getName();
				if (function.isThunk() && !name.startsWith("thunk_")) {
					name = "thunk_" + name;
				}
				out.printf("0x%08x,%s,%s,,%d%n", function.getEntryPoint().getOffset(), name, group(function),
					function.getBody().getNumAddresses());
				count++;
			}
		}
		println("exported " + count + " functions to " + args[0]);
	}

	private static String group(Function function) {
		Namespace namespace = function.getParentNamespace();
		if (namespace == null || namespace.isGlobal()) {
			return "";
		}
		while (!namespace.getParentNamespace().isGlobal()) {
			namespace = namespace.getParentNamespace();
		}
		return namespace.getName();
	}
}
