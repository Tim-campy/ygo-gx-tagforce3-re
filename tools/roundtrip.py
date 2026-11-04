#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Round-trip check of the format writers over the real disc and saves (the `reimplemented` bar).

  roundtrip.py --check <PSP_GAME> [--saves DIR] [--only ID[,ID...]] [-v]
  roundtrip.py --list

For every format id of re/formats.csv that has a writer, the check parses every instance on the disc with
the tool's reader, serialises it again with the tool's writer and compares bytes:

- whole files and archive members: parse -> encode must equal the original bytes;
- tables embedded in an executable (BOOT.BIN, gmodule/*.prx): the bytes the table owns are first overwritten
  with a filler (0xA5), then the writer writes the parsed model back into that copy; the whole executable
  must equal the original, so every owned byte is reproduced by the writer and nothing outside is touched;
- DATA0 saves: save.py decodes to JSON-ready values and rebuilds the 0x20000-byte buffer.

Nothing is written to disk. Exit status 1 when any instance of a requested format differs.
"""

import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
FILLER = 0xA5


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_modules = {}


def tool(name):
    if name not in _modules:
        _modules[name] = _load(name)
    return _modules[name]


def blank(data, spans, filler=FILLER):
    """Copy of `data` with every (offset, size) span overwritten by `filler`."""
    out = bytearray(data)
    for offset, size in spans:
        out[offset:offset + size] = bytes([filler]) * size
    return bytes(out)


def rewrite_problems(label, data, spans, write, model):
    """Blank the owned spans, write the model back, compare with the original executable."""
    if not spans:
        return [f"{label}: no bytes claimed"]
    rebuilt = write(blank(data, spans), model)
    if rebuilt == data:
        return []
    first = next(i for i in range(min(len(data), len(rebuilt))) if data[i] != rebuilt[i]) \
        if len(data) == len(rebuilt) else min(len(data), len(rebuilt))
    return [f"{label}: differs at file offset {first:#x}"]


class Disc:
    def __init__(self, root, saves=None):
        self.root = Path(root)
        self.usrdir = self.root / "USRDIR"
        self.saves = Path(saves) if saves else None
        self._cache = {}

    def read(self, relative):
        if relative not in self._cache:
            path = self.root / relative
            self._cache[relative] = path.read_bytes()
        return self._cache[relative]

    @property
    def boot(self):
        return self.read("SYSDIR/BOOT.BIN")

    def module(self, name):
        return self.read(f"USRDIR/gmodule/{name}.prx")

    def files(self, pattern):
        return sorted(p for p in self.usrdir.rglob(pattern) if p.is_file())

    def archives(self):
        """(label, bytes) of every EHP archive on the disc: loose files (gzip-wrapped ones inflated), archives
        embedded in BOOT.BIN and the gmodules, and archives nested in members (`.gz` members inflated). Cached
        as a list of labels only; bytes are re-read on demand to keep memory low."""
        ehp = tool("ehp")

        def nested(label, data):
            yield label, data
            for name, blob in ehp.parse(data):
                name, blob = ehp.unwrap(name, blob)
                if ehp.is_archive(blob):
                    yield from nested(f"{label}/{name}", blob)

        def top(path, label):
            with open(path, "rb") as handle:
                head = handle.read(4)
            if head[:2] != b"\x1f\x8b" and head != ehp.MAGIC and head != b"\x7fELF":
                return
            data = ehp.read_file(path)
            if ehp.is_elf(data):
                for offset, archive in ehp.embedded_archives(data):
                    yield from nested(f"{label}@{offset:#x}", archive)
            elif ehp.is_archive(data):
                yield from nested(label, data)

        yield from top(self.root / "SYSDIR" / "BOOT.BIN", "BOOT.BIN")
        for path in sorted(p for p in self.usrdir.rglob("*") if p.is_file()):
            yield from top(path, path.relative_to(self.usrdir).as_posix())


CHECKS = {}


def check(*format_ids):
    def register(function):
        for format_id in format_ids:
            CHECKS[format_id] = function
        return function
    return register


# --------------------------------------------------------------------------------------------- card_db

def _cardinfo_results(disc):
    if "cardinfo" not in disc._cache:
        cardinfo = tool("cardinfo")
        results = {}
        for path in disc.files("duelsys/cardinfo_*.ehp"):
            data = path.read_bytes()
            model = cardinfo.decode_archive(data)
            rebuilt = cardinfo.encode_members(model)
            members = dict(cardinfo.ehp.parse(data))
            results[path.name] = (members, rebuilt, cardinfo.encode_archive(model) == data)
        disc._cache["cardinfo"] = results
    return disc._cache["cardinfo"]


def _member_check(disc, prefixes):
    count, problems = 0, []
    for archive, (members, rebuilt, _) in _cardinfo_results(disc).items():
        for name, blob in members.items():
            if name.startswith(prefixes):
                count += 1
                if rebuilt.get(name) != blob:
                    problems.append(f"{archive}/{name}: differs")
    return count, problems


@check("cardinfo_ehp")
def check_cardinfo_ehp(disc):
    results = _cardinfo_results(disc)
    return len(results), [f"{name}: archive differs" for name, (_, _, same) in results.items() if not same]


@check("card_prop")
def check_card_prop(disc):
    return _member_check(disc, ("CARD_Prop",))


@check("card_dict")
def check_card_dict(disc):
    return _member_check(disc, ("DICT_",))


@check("card_samepict")
def check_card_samepict(disc):
    return _member_check(disc, ("CARD_SamePict_",))


@check("card_genre")
def check_card_genre(disc):
    return _member_check(disc, ("CARD_Genre",))


@check("dlg_text")
def check_dlg_text(disc):
    return _member_check(disc, ("DLG_Indx_", "DLG_Text_"))


# --------------------------------------------------------------------------------------------- archives

def _archive_members(disc):
    """[(archive label, member layout, [(name, bytes)])], one pass over the disc shared by ptrs_txt, tmf and ehf."""
    if "archive_members" not in disc._cache:
        ehp = tool("ehp")
        found = []
        for label, data in disc.archives():
            members = [(name, blob) for name, blob in ehp.parse(data)
                       if ehp.is_ptrs(name) or name.lower().endswith((".tmf", ".ehf"))]
            if members:
                found.append((label, ehp.member_offsets(data), members))
        disc._cache["archive_members"] = found
    return disc._cache["archive_members"]


@check("ptrs_txt")
def check_ptrs_txt(disc):
    ehp = tool("ehp")
    count, problems = 0, []
    for label, layout, members in _archive_members(disc):
        for name, blob in members:
            if ehp.is_ptrs(name):
                count += 1
                if ehp.build_ptrs(ehp.parse_ptrs(blob, layout), layout) != blob:
                    problems.append(f"{label}/{name}: differs")
    return count, problems


@check("tmf")
def check_tmf(disc):
    ehf = tool("ehf")
    count, problems = 0, []
    for label, _, members in _archive_members(disc):
        for name, blob in members:
            if name.lower().endswith(".tmf"):
                count += 1
                if ehf.build_tmf(ehf.decode_tmf(blob)) != blob:
                    problems.append(f"{label}/{name}: differs")
    return count, problems


@check("ehf")
def check_ehf(disc):
    ehf = tool("ehf")
    count, problems = 0, []
    for label, _, members in _archive_members(disc):
        for name, blob in members:
            if name.lower().endswith(".ehf"):
                count += 1
                try:
                    same = ehf.build(ehf.decode(blob)) == blob
                except (ehf.EhfError, ValueError, struct.error) as error:
                    problems.append(f"{label}/{name}: {error}")
                    continue
                if not same:
                    problems.append(f"{label}/{name}: differs")
    return count, problems


@check("tgm_etc_scene")
def check_tgm_etc_scene(disc):
    """Scene block (leading scalar tracks) of every flag-2 TGMT on the disc, gzip members inflated."""
    tgm = tool("tgm")
    count, problems, seen = 0, [], set()
    for path in tgm.iter_archives([disc.usrdir]):
        for prefix, members, _ in tgm.archive_members(path.read_bytes()):
            for name, raw_name, blob in tgm.tgm_members(members):
                if blob[:4] != tgm.TGMT:
                    continue
                tmt = tgm.Tmt(blob)
                if not tmt.flags & tgm.TMT_FLAG_CAMERA:
                    continue
                count += 1
                scene = tgm.read_scene(tmt)
                label = f"{path.relative_to(disc.usrdir).as_posix()}:{prefix}{raw_name}"
                problems += rewrite_problems(label, blob, tgm.scene_spans(tmt, scene), tgm.write_scene, scene)                     if scene["layout"] else []
                seen.add(scene["layout"])
    return count, problems


# --------------------------------------------------------------------------------------------- shop / deck

@check("pack_table")
def check_pack_table(disc):
    tables = tool("tables")
    prx = disc.module("rel_shop")
    packs = tables.read_packs(prx)
    return 1, rewrite_problems("rel_shop pack table", prx, tables.pack_spans(prx, packs), tables.write_packs, packs)


@check("limit_list")
def check_limit_list(disc):
    tables = tool("tables")
    boot = disc.boot
    limits = tables.read_limits(boot)
    return 1, rewrite_problems("BOOT.BIN limit list", boot, [tables.limit_span(boot)], tables.write_limits, limits)


def strtbl_problems(instances):
    """instances: [(label, bytes)] of headed/offset-list string tables; parse -> strtbl.build."""
    strtbl = tool("strtbl")
    problems = []
    for label, blob in instances:
        table = strtbl.parse(blob)
        if strtbl.build(table["strings"], table["layout"], table["has_end_offset"]) != blob:
            problems.append(f"{label}: differs")
    return len(instances), problems


@check("recipe_names")
def check_recipe_names(disc):
    decks = tool("decks")
    _, members = decks.find_recipe_archive(disc.boot)
    return strtbl_problems([(name, blob) for name, blob in members if name.startswith("recipe_name_")])


def _recipe_table(disc, key, writer):
    decks = tool("decks")
    boot = disc.boot
    return 1, rewrite_problems(f"recipe {key} table", boot, [decks.table_spans(boot)[key]],
                               getattr(decks, writer), decks.read_recipes(boot)[key])


@check("recipe_owner_table")
def check_recipe_owner_table(disc):
    return _recipe_table(disc, "owners", "write_owners")


@check("recipe_level_table")
def check_recipe_level_table(disc):
    return _recipe_table(disc, "levels", "write_levels")


@check("recipe_variant_table")
def check_recipe_variant_table(disc):
    return _recipe_table(disc, "variants", "write_variants")


@check("recipe_card_list")
def check_recipe_card_list(disc):
    decks = tool("decks")
    boot = disc.boot
    lists = decks.read_card_lists(boot)
    return 1, rewrite_problems("recipe card list", boot, decks.card_list_spans(boot, lists),
                               decks.write_card_lists, lists)


def _deck_members(disc, member):
    ehp = tool("ehp")
    return [(f"{path.name}/{member}", dict(ehp.parse(path.read_bytes()))[member])
            for path in disc.files("deck/all_*.ehp")]


@check("same_card_tbl")
def check_same_card_tbl(disc):
    decks = tool("decks")
    instances = _deck_members(disc, "sameCardTbl.dat")
    return len(instances), [f"{label}: differs" for label, blob in instances
                            if decks.build_same_card(decks.read_same_card(blob)) != blob]


@check("file_tbl")
def check_file_tbl(disc):
    decks = tool("decks")
    instances = _deck_members(disc, "fileTbl.dat")
    return len(instances), [f"{label}: differs" for label, blob in instances
                            if decks.build_file_table(decks.read_file_table(blob)) != blob]


@check("deck_tutorial_script")
def check_deck_tutorial_script(disc):
    decks, ehp = tool("decks"), tool("ehp")
    members = ehp.parse(disc.read("USRDIR/deck/tutorial.ehp"))
    scripts = [(name, blob) for name, blob in members if name.startswith("deck_tutorial") and name.endswith(".bin")]
    return len(scripts), [f"{name}: differs" for name, blob in scripts
                          if decks.tutorial_build(decks.tutorial_decode(blob)) != blob]


# --------------------------------------------------------------------------------------------- audio

def _sound_results(disc):
    if "sound" not in disc._cache:
        sound = tool("sound")
        results = []
        for bank in sound.parse(disc.read("USRDIR/snd/psp_snddat.bin")):
            model = sound.decode_bank(bank)
            results.append((bank.serial, bool(model["layers"]), sound.build_bank(model) == bank.data))
        disc._cache["sound"] = results
    return disc._cache["sound"]


@check("snd_cue")
def check_snd_cue(disc):
    results = _sound_results(disc)
    return len(results), [f"bank {serial}: differs" for serial, _, same in results if not same]


@check("snd_adpcm_layer")
def check_snd_adpcm_layer(disc):
    results = [r for r in _sound_results(disc) if r[1]]
    return len(results), [f"bank {serial}: differs" for serial, _, same in results if not same]


@check("voiceidchgtbl")
def check_voiceidchgtbl(disc):
    voices, ehp = tool("voices"), tool("ehp")
    instances = [(label, blob) for label, blob in ehp.walk_paths([disc.usrdir / "database", disc.usrdir / "duel",
                                                                    disc.usrdir / "labo"])
                 if label.lower().endswith("voiceidchgtbl.bin")]
    return len(instances), [f"{label}: differs" for label, blob in instances
                            if voices.build_change_table(voices.parse_change_table(blob)) != blob]


@check("boot_sound_tables")
def check_boot_sound_tables(disc):
    voices, sound = tool("voices"), tool("sound")
    banks = sound.parse(disc.read("USRDIR/snd/psp_snddat.bin"))
    elf = voices.prx_imports.Elf(disc.boot, voices.BOOT_BASE)
    stored = voices.boot_tables(elf, len(banks))
    problems = rewrite_problems("BOOT.BIN sound tables", disc.boot, voices.boot_table_spans(elf, len(banks)),
                                voices.write_boot_tables, (list(stored[0]), list(stored[1])))
    derived = voices.derive_boot_tables([bank.size for bank in banks], [len(bank.cues) for bank in banks])
    if derived != (list(stored[0]), list(stored[1])):
        problems.append("tables derived from the bank chain differ from BOOT.BIN")
    return 1, problems


# --------------------------------------------------------------------------------------------- duel tutorial

def _tutorial_members(disc, accept):
    ehp = tool("ehp")
    return [(name, blob) for name, blob in ehp.parse(disc.read("USRDIR/d_tutorial/tutorial.ehp")) if accept(name)]


@check("ydq")
def check_ydq(disc):
    tutorial = tool("tutorial")
    members = _tutorial_members(disc, lambda name: name.endswith(".ydq"))
    return len(members), [f"{name}: differs" for name, blob in members
                          if tutorial.ydq_encode(tutorial.ydq_decode(blob)) != blob]


@check("tuto_cmd")
def check_tuto_cmd(disc):
    tutorial = tool("tutorial")
    members = _tutorial_members(disc, lambda name: name.startswith("tuto_cmd_"))
    return len(members), [f"{name}: differs" for name, blob in members
                          if tutorial.cmd_build(tutorial.cmd_decode(blob)) != blob]


@check("tuto_text")
def check_tuto_text(disc):
    tutorial = tool("tutorial")
    members = _tutorial_members(disc, lambda name: name.startswith("tuto_text_"))
    problems = []
    for name, blob in members:
        language = name[len("tuto_text_")]
        if tutorial.text_build(tutorial.text_table(blob, language)[1], language) != blob:
            problems.append(f"{name}: differs")
    return len(members), problems


# --------------------------------------------------------------------------------------------- duel engine tables

@check("ai_priority_tables")
def check_ai_priority_tables(disc):
    ai = tool("ai_tables")
    prx = disc.module("rel_duel_eng")
    module = ai.Module(prx)
    return 1, rewrite_problems("rel_duel_eng AI tables", prx, ai.model_spans(module), ai.write_model,
                               ai.read_model(module))


@check("fusion_recipes")
def check_fusion_recipes(disc):
    fusion = tool("fusion")
    prx = disc.module("rel_duel_eng")
    module = fusion.Module(prx)
    return 1, rewrite_problems("fusion recipes", prx, [fusion.recipe_span(module)], fusion.write_recipes,
                               fusion.recipes(module))


@check("ritual_table")
def check_ritual_table(disc):
    fusion = tool("fusion")
    prx = disc.module("rel_duel_eng")
    module = fusion.Module(prx)
    records = fusion.rituals(module)
    return 1, rewrite_problems("ritual table", prx, [fusion.ritual_span(module, len(records))],
                               fusion.write_rituals, records)


def _effect_part(disc, part):
    ep = tool("effect_params")
    prx = disc.module("rel_duel_eng")
    module = ep.Module(prx)
    model = {part: ep.read_effect_model(module)[part]}
    spans = ep.effect_spans(module, part)
    return len(spans), rewrite_problems(f"rel_duel_eng {part}", prx, spans, ep.write_effect_model, model)


@check("effect_tables")
def check_effect_tables(disc):
    return _effect_part(disc, "tables")


@check("effect_lists")
def check_effect_lists(disc):
    return _effect_part(disc, "lists")


@check("counter_type_table")
def check_counter_type_table(disc):
    return _effect_part(disc, "counter_types")


def _boot_words(disc, key):
    sf = tool("search_filters")
    boot = disc.boot
    model = {key: sf.read_boot_word_tables(boot)[key]}
    return 1, rewrite_problems(f"BOOT.BIN {key}", boot, sf.boot_word_spans(boot, key), sf.write_boot_word_tables,
                               model)


@check("archetype_predicates")
def check_archetype_predicates(disc):
    return _boot_words(disc, "archetype_predicates")


@check("genre_map_table")
def check_genre_map_table(disc):
    return _boot_words(disc, "genre_map")


# --------------------------------------------------------------------------------------------- free roam

@check("hmp")
def check_hmp(disc):
    world, ehp = tool("world"), tool("ehp")
    instances = [(f"{archive}/{name}", blob) for archive, name, blob in world.hmp_members(disc.usrdir / "field" / "map")]
    # The one other .hmp on the disc: minigame/connection/data.ehp/mini_sn01.hmp.
    instances += [(label, blob) for label, blob in ehp.walk_paths([disc.usrdir / "minigame"])
                  if label.lower().endswith(".hmp")]
    return len(instances), [f"{label}: differs" for label, blob in instances
                            if world.build_hmp(world.WalkGrid(blob)) != blob]


@check("field_map_table")
def check_field_map_table(disc):
    world = tool("world")
    prx = disc.module("rel_field")
    rows = world.read_map_table_model(prx)
    return 1, rewrite_problems("rel_field map table", prx, world.map_table_spans(rows), world.write_map_table, rows)


@check("field_map_lighting")
def check_field_map_lighting(disc):
    world = tool("world")
    prx = disc.module("rel_field")
    return 1, rewrite_problems("rel_field lighting", prx, world.lighting_spans(), world.write_lighting,
                               world.read_lighting_model(prx))


@check("island_map_areas")
def check_island_map_areas(disc):
    world = tool("world")
    prx = disc.module("rel_field")
    return 1, rewrite_problems("rel_field island positions", prx, world.island_spans(), world.write_island_positions,
                               world.read_island_positions(prx))


@check("story_exit_cells")
def check_story_exit_cells(disc):
    world = tool("world")
    prx = disc.module("rel_story")
    model = world.read_exit_model(prx)
    return 1, rewrite_problems("rel_story exit tables", prx, world.exit_spans(model), world.write_exits, model)


@check("story_fixed_spots")
def check_story_fixed_spots(disc):
    world = tool("world")
    prx = disc.module("rel_story")
    return 1, rewrite_problems("rel_story fixed spots", prx, world.fixed_spot_spans(), world.write_fixed_spots,
                               world.read_fixed_spots(prx))


@check("story_char_table")
def check_story_char_table(disc):
    world = tool("world")
    prx = disc.module("rel_story")
    return 1, rewrite_problems("rel_story character table", prx, world.character_table_spans(),
                               world.write_character_table, world.read_character_table(prx))


@check("field_strtbl")
def check_field_strtbl(disc):
    ehp = tool("ehp")
    instances = [(label, blob) for label, blob in ehp.walk_paths([disc.usrdir / "field"])
                 if label.rsplit("/", 1)[-1].startswith("field_strtbl")]
    return strtbl_problems(instances)


@check("chr_wordstbl")
def check_chr_wordstbl(disc):
    """Cut-in voice captions: chr_wordstbl_<l>.bin in duel/cutin_*.ehp and duel/zakov*.ehp, and the voice-test
    copies chrcutin_*_wordstbl_<l>.bin / chrzakov*_wordstbl_<l>.bin in labo/voicetest.ehp."""
    ehp = tool("ehp")
    instances = [(label, blob) for label, blob in ehp.walk_paths([disc.usrdir / "duel", disc.usrdir / "labo"])
                 if "_wordstbl_" in label.rsplit("/", 1)[-1] and label.endswith(".bin")]
    return strtbl_problems(instances)


@check("tuto_legacy_cmd")
def check_tuto_legacy_cmd(disc):
    """NN_duel_command.bin of the legacy tutorial/tutorial_<l>.ehp archives (not loaded by the game)."""
    tutorial, ehp = tool("tutorial"), tool("ehp")
    instances = [(label, blob) for label, blob in ehp.walk_paths([disc.usrdir / "tutorial"])
                 if label.endswith("_duel_command.bin")]
    return len(instances), [f"{label}: differs" for label, blob in instances
                            if tutorial.legacy_build(tutorial.legacy_decode(blob)) != blob]


# --------------------------------------------------------------------------------------------- system

@check("module_descriptor")
def check_module_descriptor(disc):
    modules = tool("modules")
    boot = modules.prx_imports.Elf(disc.boot, modules.BOOT_BASE)
    model = {address: modules.read_descriptors(boot, address) for address in modules.DESCRIPTOR_TABLES}
    spans = [span for address, rows in model.items() for span in modules.descriptor_spans(boot, address, rows)]
    return len(model), rewrite_problems("BOOT.BIN module descriptors", disc.boot, spans, modules.write_descriptors,
                                        model)


@check("scene_table")
def check_scene_table(disc):
    modules = tool("modules")
    boot = modules.prx_imports.Elf(disc.boot, modules.BOOT_BASE)
    span = (boot.offset(modules.SCENE_TABLE - modules.BOOT_BASE), 8 * modules.SCENE_COUNT)
    return 1, rewrite_problems("BOOT.BIN scene table", disc.boot, [span], modules.write_scene_table,
                               modules.read_scene_table(boot))


@check("gmodule_prx")
def check_gmodule_prx(disc):
    modules = tool("modules")
    paths = sorted((disc.usrdir / "gmodule").glob("*.prx"))
    problems = []
    for path in paths:
        data = path.read_bytes()
        if modules.elf_build(modules.elf_decode(data)) != data:
            problems.append(f"{path.name}: differs")
    return len(paths), problems


# --------------------------------------------------------------------------------------------- executable tables

def _exe_row_check(row_id):
    def run_check(disc):
        et = tool("exe_tables")
        tables = et.TABLES[row_id]
        executables = {t.module: disc.boot if t.module == et.BOOT else disc.module(t.module) for t in tables}
        return len(tables), et.row_problems(executables, row_id, rewrite_problems)
    return run_check


for _row_id in tool("exe_tables").TABLES:
    CHECKS[_row_id] = _exe_row_check(_row_id)


@check("snd_shds_header")
def check_snd_shds_header(disc):
    et = tool("exe_tables")
    boot = disc.boot
    model = et.read_shds(boot)
    problems = rewrite_problems("BOOT.BIN SHDS header", boot, et.shds_spans(boot, model), et.write_shds, model)
    if model["bank_offsets"] != list(tool("voices").boot_tables(tool("voices").prx_imports.Elf(boot, et.BOOT_BASE),
                                                                 len(model["bank_offsets"]))[0]):
        problems.append("SHDS bank offsets differ from the boot_sound_tables reader")
    return 1, problems


# --------------------------------------------------------------------------------------------- saves

SAVE_REGIONS = {
    "save_data": None,  # the whole 0x20000-byte buffer
    "save_header": ("version", "header_unknown", "frame_counter", "open_psid"),
    "save_stored_decks": ("stored_decks",),
    "save_decks": ("deck_slots",),
    "save_player_profile": ("player_name", "team_name", "pad_fdf2", "duelist_level", "duelist_exp", "dp", "dp_earned"),
    "save_settings": ("settings",),
    "save_character_records": ("characters",),
    "save_recipe_table": ("recipes",),
    "save_duel_record": ("duel_record",),
    "save_collection": ("collection",),
    "save_pack_records": ("packs",),
    "save_picture_bits": ("picture_bits",),
    "save_character_flags": ("character_flags",),
    "save_record_table": ("record_table",),
    "save_flag_bytes": ("flag_bytes",),
    "save_card_list": ("card_list_count", "card_list", "card_list_state"),
    "save_progress_bytes": ("progress_bytes",),
    "story_block": None,  # filled below: every story_block.* leaf
    "story_field_save_block": ("story_block.field_save_block",),
    "story_flag_block": ("story_block.flag_block",),
}


def _save_results(disc):
    if "saves" not in disc._cache:
        if disc.saves is None:
            raise ValueError("give --saves DIR (plaintext DATA0 saves)")
        save = tool("save")
        results = []
        for path in sorted(disc.saves.glob("*.bin")):
            data = path.read_bytes()
            results.append((path.name, data, save.region_problems(data)))
        if not results:
            raise ValueError(f"no *.bin saves in {disc.saves}")
        disc._cache["saves"] = results
    return disc._cache["saves"]


def _save_check(format_id):
    def run_check(disc):
        save = tool("save")
        keys = SAVE_REGIONS[format_id]
        problems = []
        for name, data, differing in _save_results(disc):
            if keys is None:
                rebuilt = save.from_model(json.loads(json.dumps(save.to_model(data))))
                if rebuilt != data:
                    problems.append(f"{name}: differs")
            elif set(keys) & set(differing):
                problems.append(f"{name}: differs in {', '.join(sorted(set(keys) & set(differing)))}")
        return len(_save_results(disc)), problems
    return run_check


SAVE_REGIONS["story_block"] = tuple(key for _, _, key in tool("save")._leaves() if key.startswith("story_block."))

for _format_id in SAVE_REGIONS:
    CHECKS[_format_id] = _save_check(_format_id)


@check("deck_struct")
def check_deck_struct(disc):
    """The 0xc0-byte deck struct inside every deck slot (+0x4c) and stored deck (+0x54) of every save."""
    save = tool("save")
    count, problems = 0, []
    for name, data, _ in _save_results(disc):
        for label, base, size, number, inner in (("slot", save.DECK_BASE, save.DECK_SIZE, save.DECK_COUNT, 0x4C),
                                                 ("stored", save.STORED_BASE, save.STORED_SIZE, save.STORED_COUNT,
                                                  0x54)):
            for index in range(number):
                raw = data[base + size * index + inner:base + size * index + inner + 0xC0]
                if not any(raw):
                    continue
                count += 1
                model = json.loads(json.dumps(save._decode_deck_struct(raw)))
                if save._encode_deck_struct(model) != raw:
                    problems.append(f"{name} {label} {index}: differs")
    return count, problems


# --------------------------------------------------------------------------------------------- runner

def run(disc, only=None, verbose=False):
    failed = 0
    for format_id in sorted(CHECKS):
        if only and format_id not in only:
            continue
        if (format_id in SAVE_REGIONS or format_id == "deck_struct") and disc.saves is None:
            print(f"skip {format_id}: no --saves directory")
            continue
        try:
            count, problems = CHECKS[format_id](disc)
        except (OSError, ValueError, KeyError) as error:
            count, problems = 0, [f"error: {error}"]
        if problems:
            failed += 1
            print(f"FAIL {format_id}: {len(problems)} of {count} instances differ")
            for line in problems[:10 if not verbose else None]:
                print(f"     {line}")
        else:
            print(f"ok   {format_id}: {count} instance{'s' if count != 1 else ''} byte-identical")
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Round-trip the format writers over the disc and saves.")
    parser.add_argument("root", nargs="?", type=Path, help="PSP_GAME directory of the extracted disc")
    parser.add_argument("--check", action="store_true", help="run the round trips (the default action)")
    parser.add_argument("--saves", type=Path, help="directory of plaintext DATA0 saves (*.bin), read only")
    parser.add_argument("--only", help="comma-separated format ids")
    parser.add_argument("--list", action="store_true", help="list the format ids that have a round-trip check")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(sorted(CHECKS)))
        return 0
    if args.root is None:
        parser.error("give the PSP_GAME directory")
    only = set(args.only.split(",")) if args.only else None
    if only and only - set(CHECKS):
        parser.error(f"no round-trip check for {', '.join(sorted(only - set(CHECKS)))}")
    failed = run(Disc(args.root, args.saves), only, args.verbose)
    print("all round trips byte-identical" if not failed else f"{failed} format(s) FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
