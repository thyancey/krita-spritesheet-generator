Parses .json files exported from the companion krita spritesheet plugin, allowing them to Import directly into SpriteFrames for an AnimatedSprite2D

Installation:
- enable the plugin, restart godot
- use the Import tab on spritesheet .json exported from the companion plugin, select "Krita Spritesheet" and reimport

JSON will look like this, with the filename, metadata, then each animation group


```json
{
    "spritesheet": "my_character.png",
    "fps": 24,
    "frameWidth": 128,
    "frameHeight": 128,
    "columns": 4,
    "rows": 2,
    "animations": [
        {
            "name": "idle",
            "loop": true,
            "frameCount": 4,
            "frames": [
                { "index": 0, "timelineFrame": 0, "durationFrames": 6, "durationSeconds": 0.25 },
                { "index": 1, "timelineFrame": 6, "durationFrames": 6, "durationSeconds": 0.25 }
            ]
        }
    ]
}
```