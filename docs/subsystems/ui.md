# User interface

Not started; entry points found while working on containers.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0881e56c` | `ui_bind_ehf(ehf, tmf, callback, ehp)` | M | Called by `container_ehp_bind_members` for every `.ehf` member, with the `.tmf` member of the same base name and callback `0x088227d0`; followed by `0x0881e6a4(480.0, 272.0, 240.0, 136.0, ehf, 0)`, the PSP screen size and its centre. |

## Data

- `.ehf` (magic `EHF`, 1,029 members): 2D layouts, each paired with a `.tmf` of the same name.
- `loading.ehf` is looked up in the embedded archive at `0x088cc480` during start-up (`0x08835c68`).

## Open questions

- `.ehf` and `.tmf` layouts; what `0x0881e6a4` sets up from the screen-size arguments.
