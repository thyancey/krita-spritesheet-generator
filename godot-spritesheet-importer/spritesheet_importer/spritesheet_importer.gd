@tool
extends EditorPlugin

var importer

func _enter_tree() -> void:
	importer = preload("res://addons/spritesheet_importer/spritesheet_importer_plugin.gd").new()
	add_import_plugin(importer)

func _exit_tree() -> void:
	remove_import_plugin(importer)
	importer = null
