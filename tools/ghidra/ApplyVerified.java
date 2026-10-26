// SPDX-License-Identifier: GPL-2.0-only
// Apply runtime verification from re/verified.tsv (program<TAB>address<TAB>results file<TAB>summary).
// Each listed function of the current program that is already DOCUMENTED (ApplySignatures.java) gets the
// VERIFIED tag, which ExportFunctions.java turns into the "verified" status, and a line in its plate comment
// naming the PPSSPP results file (docs/verification/results/). Rows for other programs are skipped, so one
// file serves BOOT.BIN and every module. Usage (headless):
//   analyzeHeadless <projdir> <proj> -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript ApplyVerified.java <verified.tsv>
// @category TF3

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

public class ApplyVerified extends GhidraScript {
	public static final String TAG = "VERIFIED";

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			throw new IllegalArgumentException("usage: ApplyVerified.java <verified.tsv>");
		}
		String program = currentProgram.getName();
		int applied = 0;
		for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
			if (line.isBlank() || line.startsWith("#") || line.startsWith("program\t")) {
				continue;
			}
			String[] f = line.split("\t", -1);
			if (f.length != 4) {
				printerr("expected 4 tab-separated fields: " + line);
				continue;
			}
			if (!f[0].equals(program)) {
				continue;
			}
			Function function = getFunctionAt(toAddr(Long.parseUnsignedLong(f[1].replaceFirst("^0x", ""), 16)));
			if (function == null) {
				printerr("no function at " + f[1]);
				continue;
			}
			// verified is above documented: the signature and comment must already be in place.
			if (function.getTags().stream().noneMatch(t -> t.getName().equals("DOCUMENTED"))) {
				printerr("not documented, skipped: " + f[1] + " " + function.getName());
				continue;
			}
			String note = "Verified in " + f[2] + ": " + f[3];
			String comment = function.getComment();
			if (comment == null || !comment.contains(note)) {
				function.setComment(comment == null ? note : comment + "\n" + note);
			}
			function.addTag(TAG);
			applied++;
		}
		println("verified " + applied + " functions");
	}
}
