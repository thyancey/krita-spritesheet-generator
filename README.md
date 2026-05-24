# Krita → Godot Spritesheet Pipeline

A two-part workflow for exporting animations from Krita and importing them into Godot as `AnimatedSprite2D` resources, with named animations and correct frame timings.

## Structure

**`/krita-spritesheet-generator`** — Krita plugin for exporting spritesheets. Forked from [ShannonHG/krita-spritesheet-generator](https://github.com/ShannonHG/krita-spritesheet-generator) with additions for animation marker support and JSON metadata export.

**`/godot-spritesheet-importer`** — Godot addon that reads the exported PNG + JSON and creates a `SpriteFrames` resource automatically.

See the README in each folder for installation and usage.

## License

Original Krita plugin by [ShannonHG](https://github.com/ShannonHG), MIT licensed — see `krita-spritesheet-generator/LICENSE`.

Godot importer and Krita plugin additions by Tom Yancey, MIT licensed — see `LICENSE`.
