// SPDX-License-Identifier: GPL-2.0-only
// Export every function of the current program as re/functions.csv rows (id,name,group,status,size).
// Group comes from the function's top-level Ghidra namespace (see CLAUDE.md naming). Status is
// "documented" for functions carrying the DOCUMENTED tag (ApplySignatures.java), "verified" when they also
// carry the VERIFIED tag (ApplyVerified.java), and blank otherwise, so tools/progress.py infers
// unknown/named. Usage (headless):
//   analyzeHeadless <projdir> <proj> -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript ExportFunctions.java <output.csv> [module id prefix, e.g. rel_story]
// @category TF3

import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Namespace;

public class ExportFunctions extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 1 || args.length > 2) {
			throw new IllegalArgumentException("usage: ExportFunctions.java <output.csv> [module id prefix]");
		}
		// Modules that share a load address (the scene and library slots) need module-qualified ids.
		String prefix = args.length == 2 ? args[1] + ":" : "";
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
				// Only functions tagged by ApplySignatures.java are "documented", and only documented ones
				// also tagged by ApplyVerified.java are "verified"; the rest is inferred.
				boolean documented = hasTag(function, "DOCUMENTED");
				String status = !documented ? "" : hasTag(function, "VERIFIED") ? "verified" : "documented";
				out.printf("%s0x%08x,%s,%s,%s,%d%n", prefix, function.getEntryPoint().getOffset(), name, group(function),
					status, function.getBody().getNumAddresses());
				count++;
			}
		}
		println("exported " + count + " functions to " + args[0]);
	}

	private static boolean hasTag(Function function, String tag) {
		return function.getTags().stream().anyMatch(t -> t.getName().equals(tag));
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
