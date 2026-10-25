// SPDX-License-Identifier: GPL-2.0-only
// Apply function names from a CSV with columns address,group,name (lines starting with # are skipped).
// Each function goes into the Ghidra namespace named after its group, as CLAUDE.md requires; a missing
// function is created first, and a row with an empty name only creates it. Usage (headless):
//   analyzeHeadless <projdir> <proj> -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript ApplyNames.java <names.csv>
// @category TF3

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.SourceType;

public class ApplyNames extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length != 1) {
			throw new IllegalArgumentException("usage: ApplyNames.java <names.csv>");
		}
		int applied = 0;
		int created = 0;
		for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
			line = line.strip();
			if (line.isEmpty() || line.startsWith("#") || line.startsWith("address,")) {
				continue;
			}
			String[] f = line.split(",", -1);
			Address address = toAddr(Long.parseUnsignedLong(f[0].replaceFirst("^0x", ""), 16));
			Function function = getFunctionAt(address);
			if (function == null) {
				function = createFunction(address, null);
				if (function != null) {
					created++;
				}
			}
			if (function == null) {
				printerr("cannot create a function at " + address);
				continue;
			}
			if (f[2].isEmpty()) {  // create only, keep the default name
				continue;
			}
			Namespace namespace = getNamespace(null, f[1]);
			if (namespace == null) {
				namespace = currentProgram.getSymbolTable().createNameSpace(null, f[1], SourceType.USER_DEFINED);
			}
			function.setParentNamespace(namespace);
			function.setName(f[2], SourceType.USER_DEFINED);
			applied++;
		}
		println("applied " + applied + " names, created " + created + " functions");
	}
}
