// SPDX-License-Identifier: GPL-2.0-only
// Fold code fragments that were created as separate functions back into the function they belong to.
// A fragment is a block that is only reached from inside its parent (a switch case reached through the parent's
// `jr`, the tail of a loop or a branch target) and that uses the parent's registers and stack frame; the PPSSPP
// symbol import created functions at such addresses (re/names-ppsspp.csv, "create only" rows), and Ghidra then
// put the switch cases in pseudo-namespaces `switchD_<jr address>`.
// Arguments: pairs <parent entry> <fragment entry> (hex, with or without 0x). For each pair the script removes the
// function at the fragment entry and re-derives the parent body from its flow (CreateFunctionCmd.fixupFunctionBody).
// If the parent body does not then contain the fragment, the fragment function is re-created and an error printed,
// so nothing is lost. A fragment reached only from other fragments (a loop head the switch cases jump back to) is
// only reached once those are merged: list it after them, or run the script again. Idempotent: a pair whose fragment is already inside the parent changes nothing.
// Usage (headless, not -readOnly, so the fix is saved):
//   analyzeHeadless <projdir> TF3 -process BOOT.BIN -noanalysis -scriptPath tools/ghidra
//       -postScript MergeFragments.java 0x08804a00 0x08804b3c 0x08804a00 0x08804b90
// Recorded fixes: docs/subsystems/system.md, "Registry hygiene".
// @category TF3

import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class MergeFragments extends GhidraScript {
	private Address addr(String s) {
		return toAddr(Long.parseUnsignedLong(s.replaceFirst("^0x", ""), 16));
	}

	@Override
	protected void run() throws Exception {
		String[] a = getScriptArgs();
		if (a.length == 0 || a.length % 2 != 0) {
			throw new IllegalArgumentException("usage: MergeFragments.java (<parent entry> <fragment entry>)...");
		}
		for (int i = 0; i < a.length; i += 2) {
			Address entry = addr(a[i]);
			Address frag = addr(a[i + 1]);
			Function parent = getFunctionAt(entry);
			if (parent == null) {
				printerr("no function at " + entry);
				continue;
			}
			long before = parent.getBody().getNumAddresses();
			Function f = getFunctionAt(frag);
			String fname = f == null ? "-" : f.getName(true);
			if (f != null && !f.equals(parent)) {
				removeFunction(f);
			}
			CreateFunctionCmd.fixupFunctionBody(currentProgram, parent, monitor);
			if (!parent.getBody().contains(frag)) {
				printerr(String.format("%s: parent %s does not reach %s; fragment restored", frag, entry, frag));
				createFunction(frag, null);
				continue;
			}
			println(String.format("merged %s (%s) into %s %s: body %d -> %d bytes", frag, fname, entry,
				parent.getName(), before, parent.getBody().getNumAddresses()));
		}
	}
}
