# Prior art

## ygotfToolkit

[eireetm/ygotfToolkit](https://github.com/eireetm/ygotfToolkit) is a Python modding toolkit for the whole Tag Force series (archives, card database, textures, audio, effects, save data, DLC). Its `FORMATS.md` was compared with this project's documents after they were written (2026-10-25).

Licence: the repository has no licence file. The maintainer of this project found the author stating on social media that the toolkit uses the same licence as this project (GPL-2.0). No code is taken from it. It is used in two ways: its documentation to cross-check facts and choose what to look at next, and the toolkit itself, run as an external tool on the maintainer's disc (read-only commands only), to extract data and cross-check results. Findings obtained with it say so in their basis. Any code adopted later must carry an attribution header and a note on where the licence was stated.

### Running it

Clone it outside this repository and point it at the disc image; write commands (`--set`, `--apply`, `--swap`, `--install`, `-o` with a binary) are not used. Marking the image read-only in the file system is a cheap safeguard.

```
python -I <ygotfToolkit>/ygotf.py info "game/<image>.iso"
python -I <ygotfToolkit>/ygotf.py effects "game/<image>.iso" --card 4844
python -I <ygotfToolkit>/ygotf.py cardpics "game/<image>.iso" extracted/cardj --archive cardj
```

Cross-checks so far: `info` reproduces this project's counts for EHP archives (531), card records (3,554), `.cip` images (3,560 / 3,553) and the limit list (114: 43/59/12); `effects` revealed four 8-byte effect lists (`effect-tables.md`); `cardpics` unmasks the `cardj` art (`cip.md`).

### Agreement

Independently established here and consistent with its notes: the EHP container, the `.cip` directory and DXT1/GIM images, the `cardinfo` Huffman descriptions and dictionary, the forbidden/limited list (including the default status 3 for unlisted cards), the 24-byte effect records selected by a 2-bit field, and the unencrypted `BOOT.BIN` on the European disc.

### Corrections it prompted (verified on our disc)

- `$m` + four digits (a card name by id) remains in 1,186 English descriptions; `cardinfo.md` had wrongly said no escape remains.
- ISO 9660 records on this disc carry no `;1` suffix; `file-index.md` had said they did.

### Where this project differs, for Tag Force 3 EU

- `CARD_Prop` word 0 holds ATK/10 and DEF/10 in 9-bit fields: 180 cards have an odd ATK/10 and 75 an odd DEF/10, which a layout with ATK/40 and DEF/20 cannot represent.
- Attribute values are 1 LIGHT, 2 DARK, 3 WATER, 4 FIRE, 5 EARTH, 6 WIND, 7 DIVINE.

### Leads, not yet verified on this game

| Lead | Measured on |
| --- | --- |
| Save data is one flat structure copied with a single `memcpy`; its layout can be read from small accessors returning `savework + K`; each card's forbidden/limited status is cached in its collection record, seeded from the built-in list. | TF6, TFsp |
| `snd/psp_snddat.bin` is a chain of `SP` banks padded to 2048 bytes, with 32-byte cue entries and RIFF ATRAC3/ATRAC3plus waves. | TF3 EU |
| `script/story_scr_<l>.ehp` holds paired offset/text tables (`EveI`/`EveL`, `SysMsgI`/`SysMsgL`); `story_scr_b.ehp` holds event bytecode. | TF3 onward |
| 8-byte `{card, handler}` lists next to the 24-byte effect tables. | TF1 |
| The `CPJ` card images are masked JPEGs rather than block-encrypted data. Confirmed on TF3 EU: the method was then derived independently from `BOOT.BIN` and implemented in `tools/cip.py jpeg`, whose output is byte-identical to the toolkit's for all 3,602 slots (`cip.md`). | TF2 onward |
| Export NIDs of the limit-list functions (lookup, copies allowed, save status, setter). | "every build" |
