@tool
extends EditorImportPlugin

# -----------------------------------------------------------------------
# Godot EditorImportPlugin for Krita spritesheet exports.
#
# Drop your Krita-exported .png + .json into the Godot project folder.
# Godot will automatically run this importer on the .json file and
# produce a SpriteFrames resource with one named animation per group.
#
# Krita layer setup:
#   [Group] A_idle:0-14        <- loops by default
#   [Group] A_death:35-50:once <- plays once
#       └─ Paint Layers
# -----------------------------------------------------------------------

func _get_importer_name() -> String:
	return "krita.spritesheet"

func _get_visible_name() -> String:
	return "Krita Spritesheet"

func _get_recognized_extensions() -> PackedStringArray:
	return ["json"]

func _get_save_extension() -> String:
	return "tres"

func _get_resource_type() -> String:
	return "SpriteFrames"

func _get_priority() -> float:
	return 1.0

func _get_import_order() -> int:
	return 0

func _get_preset_count() -> int:
	return 1

func _get_preset_name(preset_index: int) -> String:
	return "Default"

func _get_import_options(path: String, preset_index: int) -> Array[Dictionary]:
	return []

func _get_option_visibility(path: String, option_name: StringName, options: Dictionary) -> bool:
	return true

func _get_source_file_dependencies(source_file: String, path: String) -> PackedStringArray:
	var file := FileAccess.open(source_file, FileAccess.READ)
	if file == null:
		return []
	var json := JSON.new()
	if json.parse(file.get_as_text()) != OK:
		return []
	file.close()
	var data = json.get_data()
	if not data is Dictionary or not data.has("spritesheet"):
		return []
	var png_path := source_file.get_base_dir().path_join(data["spritesheet"])
	return [png_path]

func _import(source_file: String, save_path: String, options: Dictionary, platform_variants: Array[String], gen_files: Array[String]) -> Error:
	# --- 1. Read and parse the JSON ---
	var file := FileAccess.open(source_file, FileAccess.READ)
	if file == null:
		printerr("KritaImporter: Could not open ", source_file)
		return ERR_CANT_OPEN

	var json := JSON.new()
	var parse_error := json.parse(file.get_as_text())
	file.close()

	if parse_error != OK:
		printerr("KritaImporter: JSON parse error in ", source_file, " — ", json.get_error_message())
		return ERR_PARSE_ERROR

	var data: Dictionary = json.get_data()

	# --- 2. Validate this is a Krita spritesheet JSON ---
	var required_keys := ["spritesheet", "frameWidth", "frameHeight", "columns", "animations"]
	for key in required_keys:
		if not data.has(key):
			return ERR_SKIP

	# --- 3. Load the PNG ---
	var png_path := source_file.get_base_dir().path_join(data["spritesheet"])
	var texture := load(png_path) as Texture2D
	if texture == null:
		printerr("KritaImporter: Could not load spritesheet texture at ", png_path)
		return ERR_FILE_NOT_FOUND

	# --- 4. Build SpriteFrames with one animation per group ---
	var sprite_frames := SpriteFrames.new()
	var frame_width: int = data["frameWidth"]
	var frame_height: int = data["frameHeight"]
	var columns: int = data["columns"]
	var animations: Array = data["animations"]

	if sprite_frames.has_animation("default"):
		sprite_frames.remove_animation("default")

	for anim_data in animations:
		var anim_name: String = anim_data["name"]
		var frames_data: Array = anim_data["frames"]
		# Per-animation loop flag — defaults to true if not present (backwards compat)
		var should_loop: bool = anim_data.get("loop", true)

		sprite_frames.add_animation(anim_name)
		sprite_frames.set_animation_loop(anim_name, should_loop)

		var all_equal := true
		var first_duration: float = float(frames_data[0]["durationSeconds"])
		for frame in frames_data:
			if abs(float(frame["durationSeconds"]) - first_duration) > 0.0001:
				all_equal = false
				break

		if all_equal:
			sprite_frames.set_animation_speed(anim_name, 1.0 / first_duration)
			for frame in frames_data:
				var atlas := _make_atlas(texture, int(frame["index"]), columns, frame_width, frame_height)
				sprite_frames.add_frame(anim_name, atlas)
		else:
			var min_duration := first_duration
			for frame in frames_data:
				var d := float(frame["durationSeconds"])
				if d < min_duration:
					min_duration = d

			sprite_frames.set_animation_speed(anim_name, 1.0 / min_duration)
			for frame in frames_data:
				var atlas := _make_atlas(texture, int(frame["index"]), columns, frame_width, frame_height)
				var repeat := max(1, roundi(float(frame["durationSeconds"]) / min_duration))
				for _i in range(repeat):
					sprite_frames.add_frame(anim_name, atlas)

		print("KritaImporter: '%s' — %d frames @ %.2f fps, loop=%s" % [
			anim_name,
			sprite_frames.get_frame_count(anim_name),
			sprite_frames.get_animation_speed(anim_name),
			should_loop
		])

	# --- 5. Save ---
	var result := ResourceSaver.save(sprite_frames, "%s.%s" % [save_path, _get_save_extension()])
	if result != OK:
		printerr("KritaImporter: Failed to save SpriteFrames resource")
	return result

func _make_atlas(texture: Texture2D, index: int, columns: int, frame_width: int, frame_height: int) -> AtlasTexture:
	var atlas := AtlasTexture.new()
	atlas.atlas = texture
	atlas.region = Rect2(
		(index % columns) * frame_width,
		(index / columns) * frame_height,
		frame_width,
		frame_height
	)
	return atlas
