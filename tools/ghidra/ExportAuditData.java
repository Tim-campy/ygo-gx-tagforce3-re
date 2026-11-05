// SPDX-License-Identifier: GPL-2.0-only
// Export what tools/doc_audit.py needs from the current program, for the documentation-quality audit
// (docs/verification/documentation-quality-audit.md): the relocated memory image, every function with its body,
// applied prototype and thunk target, every reference to a function, and optionally the decompilation.
// Everything lands outside the repository: it contains game code and must never be committed.
// Usage (headless, read-only, every program of the project in one process):
//   analyzeHeadless <projdir> <proj> -process -noanalysis -readOnly -scriptPath <dir>
//       -postScript ExportAuditData.java <output dir> [decompile]
// @category TF3

import java.io.BufferedOutputStream;
import java.io.FileOutputStream;
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.Reference;

public class ExportAuditData extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String stem = args[0] + "/" + currentProgram.getName();
		if (args.length > 1 && args[1].equals("decompile")) {
			decompileAll(stem + ".c");
			return;
		}
		try (PrintWriter map = new PrintWriter(stem + ".map", "UTF-8");
				BufferedOutputStream mem = new BufferedOutputStream(new FileOutputStream(stem + ".mem"))) {
			long position = 0;
			for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
				if (!block.isInitialized() || !block.isLoaded()) {
					continue;
				}
				byte[] bytes = new byte[(int) block.getSize()];
				block.getBytes(block.getStart(), bytes);
				mem.write(bytes);
				map.printf("0x%08x\t%d\t%d\t%s\t%s%n", block.getStart().getOffset(), bytes.length, position,
					block.getName(), block.isExecute() ? "x" : "-");
				position += bytes.length;
			}
		}
		try (PrintWriter fn = new PrintWriter(stem + ".fn.tsv", "UTF-8");
				PrintWriter xr = new PrintWriter(stem + ".xref.tsv", "UTF-8")) {
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				if (f.isExternal()) {
					continue;
				}
				StringBuilder body = new StringBuilder();
				for (AddressRange r : f.getBody()) {
					body.append(String.format("%x-%x;", r.getMinAddress().getOffset(), r.getMaxAddress().getOffset()));
				}
				Function target = f.isThunk() ? f.getThunkedFunction(false) : null;
				fn.printf("0x%08x\t%s\t%s\t%s\t%d\t%s\t%s\t%d\t%s%n", f.getEntryPoint().getOffset(), f.getName(),
					group(f), target == null ? "" : String.format("0x%08x", target.getEntryPoint().getOffset()),
					f.getBody().getNumAddresses(), body, f.getReturnType().getName(), f.getParameterCount(),
					f.getPrototypeString(false, false));
				for (Reference ref : getReferencesTo(f.getEntryPoint())) {
					Function from = getFunctionContaining(ref.getFromAddress());
					xr.printf("0x%08x\t0x%08x\t%s\t%s%n", f.getEntryPoint().getOffset(), ref.getFromAddress().getOffset(),
						from == null ? "" : String.format("0x%08x", from.getEntryPoint().getOffset()), ref.getReferenceType());
				}
			}
		}
		println("exported " + stem);
	}

	private void decompileAll(String path) throws Exception {
		DecompInterface decompiler = new DecompInterface();
		decompiler.openProgram(currentProgram);
		try (PrintWriter out = new PrintWriter(path, "UTF-8")) {
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				if (f.isExternal() || f.isThunk() || monitor.isCancelled()) {
					continue;
				}
				out.printf("//==== 0x%08x %s%n", f.getEntryPoint().getOffset(), f.getName());
				DecompileResults r = decompiler.decompileFunction(f, 20, monitor);
				out.println(r.getDecompiledFunction() != null ? r.getDecompiledFunction().getC() : "// decompile failed");
			}
		}
		decompiler.dispose();
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
