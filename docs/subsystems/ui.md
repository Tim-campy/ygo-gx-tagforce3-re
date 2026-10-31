# User interface

Data formats established; code not yet analysed (entry points found while working on containers).

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0881e56c` | `ui_bind_ehf(ehf, tmf, callback, ehp)` | M | Called by `container_ehp_bind_members` for every `.ehf` member, with the `.tmf` member of the same base name and callback `0x088227d0`; followed by `0x0881e6a4(480.0, 272.0, 240.0, 136.0, ehf, 0)`, the PSP screen size and its centre. |

## Data

- `.ehf` (`docs/formats/ehf.md`): 2D layouts converted from Flash/SWF. Stage in twips (9600 × 5440 = 480 × 272 px), a main timeline of place/remove records with depths and mask (clip) depths, shapes made of textured quads stored as GE display lists, nested looping clips, and quantised keyframe tracks for an affine matrix and a colour transform. 1,225 on the disc, all parsed and cross-checked by `tools/ehf.py check` and exported as neutral JSON by `ehf.py json` (schema in `ehf.md`); renders of `loading.ehf`, the title screen and several menus look correct.
- `.tmf`: one flag byte per texture slot of the `.ehf`; bit 0 is probably additive blending, bit 4 unknown.
- Textures are `<name>.gim` members of the same archive (`docs/formats/gim.md`).
- `loading.ehf` is looked up in the embedded archive at `0x088cc480` (file offset `0xc84d4`) during start-up (`0x08835c68`).
- Each `.ehf` reserves a zero-filled work area of `align16(0x78 + 0x28 × peak live instances)` bytes: the runtime keeps per-instance state inside the file image (hypothesis, high).

## Open questions

- What `0x0881e6a4` sets up from the screen-size arguments (probably the stage-to-screen mapping).
- How `ui_bind_ehf` patches the texture and vertex placeholders of the display lists, and how callback `0x088227d0` finds a texture.
- Who plays a layout (frame stepping, looping, jumping to labels or frames) and how menus drive it; there are no frame labels or actions in the format.
- See also the open questions in `docs/formats/ehf.md`.
