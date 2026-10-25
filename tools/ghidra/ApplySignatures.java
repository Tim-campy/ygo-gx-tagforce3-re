// SPDX-License-Identifier: GPL-2.0-only
// Apply documented signatures from re/documented.tsv (address<TAB>C prototype<TAB>summary<TAB>doc path).
// Each function gets the prototype, a plate comment with the summary and the document that records its
// purpose, side effects and callers, and the DOCUMENTED tag that ExportFunctions.java turns into the
// "documented" status (docs/PROGRESS.md). Usage (headless):
//   analyzeHeadless <projdir> <proj> -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript ApplySignatures.java <documented.tsv>
// @category TF3

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.cmd.function.ApplyFunctionSignatureCmd;
import ghidra.app.script.GhidraScript;
import ghidra.app.util.cparser.C.CParser;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.FunctionDefinition;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class ApplySignatures extends GhidraScript {
	public static final String TAG = "DOCUMENTED";

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			throw new IllegalArgumentException("usage: ApplySignatures.java <documented.tsv>");
		}
		int applied = 0;
		for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
			if (line.isBlank() || line.startsWith("#") || line.startsWith("address\t")) {
				continue;
			}
			String[] f = line.split("\t", -1);
			if (f.length != 4) {
				printerr("expected 4 tab-separated fields: " + line);
				continue;
			}
			Function function = getFunctionAt(toAddr(Long.parseUnsignedLong(f[0].replaceFirst("^0x", ""), 16)));
			if (function == null) {
				printerr("no function at " + f[0]);
				continue;
			}
			// Headless has no tool services, so parse with the program's own data types.
			DataType parsed = new CParser(currentProgram.getDataTypeManager()).parse(f[1] + ";");
			FunctionDefinition signature = parsed instanceof FunctionDefinition ? (FunctionDefinition) parsed : null;
			if (signature == null || !signature.getName().equals(function.getName())) {
				printerr("cannot parse, or name differs from the function's: " + f[1]);
				continue;
			}
			if (!new ApplyFunctionSignatureCmd(function.getEntryPoint(), signature, SourceType.USER_DEFINED)
					.applyTo(currentProgram)) {
				printerr("cannot apply " + f[1]);
				continue;
			}
			// The parsed prototype carries no calling convention; use the compiler's default (PSP o32).
			function.setCallingConvention(currentProgram.getCompilerSpec().getDefaultCallingConvention().getName());
			function.setComment(f[2] + "\nDocumented in " + f[3]);
			function.addTag(TAG);
			applied++;
		}
		println("documented " + applied + " functions");
	}
}
