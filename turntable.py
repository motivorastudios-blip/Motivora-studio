#!/usr/bin/env python3
"""
Turntable renderer for Blender.

This script is intended to be executed from Blender via:
    blender -b -P turntable.py -- --input INPUT --out OUTPUT [...options]

It imports the provided STL model, centres and scales it,
creates a simple lighting rig and camera, and renders a 360° turntable
animation to a transparent WebM (VP9) file.
"""

import argparse
import importlib
import math
import os
import sys
import tempfile
from typing import Optional

import addon_utils
import bpy
from mathutils import Vector
from pathlib import Path
import importlib.util
import struct


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Render a 360° turntable animation.")
    parser.add_argument("--input", required=True, help="Path to STL input file.")
    parser.add_argument("--out", required=True, help="Destination video file path.")
    parser.add_argument("--seconds", type=float, default=10.0, help="Animation duration in seconds.")
    parser.add_argument("--fps", type=int, default=25, help="Frames per second.")
    parser.add_argument("--size", type=int, default=1080, help="Render resolution (square).")
    parser.add_argument(
        "--axis",
        choices=("X", "Y", "Z"),
        default="Z",
        help="Axis around which to rotate the model.",
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0.0,
        help="Initial rotation offset in degrees before animation starts.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatically determine ideal rotation axis and starting angle.",
    )
    parser.add_argument(
        "--format",
        choices=("webm", "mp4"),
        default="webm",
        help="Output container format.",
    )
    parser.add_argument(
        "--quality",
        choices=("fast", "standard", "ultra"),
        default="standard",
        help="Rendering quality preset.",
    )
    parser.add_argument(
        "--watermark",
        action="store_true",
        help="Add watermark overlay to rendered video.",
    )
    parser.add_argument(
        "--kelvin",
        type=int,
        default=3200,
        help="Lighting color temperature in Kelvin (2000-10000). Lower = warmer/yellow, Higher = cooler/blue.",
    )
    parser.add_argument(
        "--exposure",
        type=float,
        default=0.0,
        help="Exposure adjustment (-2.0 to 2.0). Negative = darker, Positive = brighter. Auto-brightness uses 0.0 as baseline.",
    )
    parser.add_argument(
        "--auto_brightness",
        action="store_true",
        help="Automatically analyze model and adjust exposure for optimal brightness.",
    )
    return parser.parse_args(argv)


def _clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)
    for block in bpy.data.cameras:
        bpy.data.cameras.remove(block)
    for block in bpy.data.lights:
        bpy.data.lights.remove(block)


def _ensure_stl_importer():
    addon_name = "io_mesh_stl"

    def operator_available() -> bool:
        return hasattr(bpy.ops.import_mesh, "stl")

    def try_enable() -> bool:
        try:
            addon_utils.enable(addon_name, default_set=True, persistent=True)
            return operator_available()
        except ModuleNotFoundError:
            return False
        except Exception:
            return operator_available()

    addon_utils.modules(refresh=True)
    if try_enable():
        return

    candidate_dirs: list[Path] = []
    for script_path in bpy.utils.script_paths():
        candidate_dirs.append(Path(script_path) / "addons" / addon_name)
    for scope in ("USER", "LOCAL", "SYSTEM"):
        scope_path = bpy.utils.resource_path(scope)
        if scope_path:
            candidate_dirs.append(Path(scope_path) / "scripts" / "addons" / addon_name)

    extensions_root = Path(bpy.utils.user_resource("SCRIPTS", path="extensions"))
    candidate_dirs.append(extensions_root / addon_name)
    resources_root = Path(bpy.app.binary_path).resolve().parent.parent / "Resources"
    candidate_dirs.extend(
        [
            resources_root / bpy.app.version_string / "scripts" / "addons" / addon_name,
            resources_root / "scripts" / "addons" / addon_name,
        ]
    )

    for directory in candidate_dirs:
        init_file = directory / "__init__.py"
        if not init_file.exists():
            continue
        parent = init_file.parent.parent
        if str(parent) not in sys.path:
            sys.path.append(str(parent))
        importlib.invalidate_caches()
        try:
            importlib.import_module(addon_name)
        except ModuleNotFoundError:
            spec = importlib.util.spec_from_file_location(addon_name, init_file)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[addon_name] = module
            spec.loader.exec_module(module)
        addon_utils.modules(refresh=True)
        if try_enable():
            break
    else:
        raise RuntimeError(
            "Unable to load Blender's STL importer (io_mesh_stl). "
            "Open Blender and install/enable 'Import-Export: STL format'."
        )

    if not operator_available():
        raise RuntimeError("Stl import operator unavailable after enabling io_mesh_stl.")


def _fallback_import_stl(filepath: str) -> bpy.types.Object:
    def _read_ascii(file_obj):
        vertices = []
        faces = []
        vertex_map = {}

        def _vertex_index(values):
            key = tuple(round(v, 6) for v in values)
            if key not in vertex_map:
                vertex_map[key] = len(vertices)
                vertices.append(values)
            return vertex_map[key]

        current = []
        for raw in file_obj:
            line = raw.strip()
            if not line:
                continue
            tokens = line.split()
            if tokens[0].lower() == "vertex":
                coords = tuple(float(tok) for tok in tokens[1:4])
                current.append(_vertex_index(coords))
            elif tokens[0].lower() == "endloop":
                if len(current) == 3:
                    faces.append(tuple(current))
                current = []
        return vertices, faces

    def _read_binary(file_obj):
        header = file_obj.read(80)
        if len(header) < 80:
            raise ValueError("Invalid STL header.")
        (count,) = struct.unpack("<I", file_obj.read(4))
        vertices = []
        faces = []
        vertex_map = {}

        def _vertex_index(values):
            key = tuple(round(v, 6) for v in values)
            if key not in vertex_map:
                vertex_map[key] = len(vertices)
                vertices.append(values)
            return vertex_map[key]

        for _ in range(count):
            chunk = file_obj.read(50)
            if len(chunk) < 50:
                break
            # normal = struct.unpack("<3f", chunk[0:12])
            v1 = struct.unpack("<3f", chunk[12:24])
            v2 = struct.unpack("<3f", chunk[24:36])
            v3 = struct.unpack("<3f", chunk[36:48])
            idx1 = _vertex_index(v1)
            idx2 = _vertex_index(v2)
            idx3 = _vertex_index(v3)
            faces.append((idx1, idx2, idx3))
        return vertices, faces

    with open(filepath, "rb") as f:
        start = f.read(80)
        f.seek(0)
        if start.lower().startswith(b"solid"):
            try:
                text = f.read().decode("utf-8", errors="ignore")
                from io import StringIO

                vertices, faces = _read_ascii(StringIO(text))
            except Exception:  # noqa: BLE001
                f.seek(0)
                vertices, faces = _read_binary(f)
        else:
            vertices, faces = _read_binary(f)

    if not vertices or not faces:
        raise RuntimeError("Failed to parse STL geometry without Blender add-on.")

    mesh = bpy.data.meshes.new(name=Path(filepath).stem or "Imported_STL")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False)
    mesh.update()

    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj


def _import_model(path: str) -> bpy.types.Object:
    ext = os.path.splitext(path)[1].lower()
    source_path = path

    if ext != ".stl":
        raise ValueError(f"Unsupported file extension: {ext}")

    try:
        _ensure_stl_importer()
    except RuntimeError:
        return _fallback_import_stl(source_path)

    if hasattr(bpy.ops.import_mesh, "stl"):
        try:
            bpy.ops.import_mesh.stl(filepath=source_path)
        except Exception as exc:  # noqa: BLE001
            if ext == ".stl":
                print(f"[WARN] STL operator failed, falling back: {exc}", flush=True)
                return _fallback_import_stl(source_path)
            raise
    else:
        return _fallback_import_stl(source_path)

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects were imported from the provided file.")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    if len(meshes) > 1:
        bpy.ops.object.join()
    model = bpy.context.view_layer.objects.active
    bpy.ops.object.shade_smooth()
    return model


def _compute_bounds(obj: bpy.types.Object):
    bpy.context.view_layer.update()
    world_bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_corner = Vector(
        (min(v.x for v in world_bbox), min(v.y for v in world_bbox), min(v.z for v in world_bbox))
    )
    max_corner = Vector(
        (max(v.x for v in world_bbox), max(v.y for v in world_bbox), max(v.z for v in world_bbox))
    )
    dimensions = max_corner - min_corner
    radius = max(dimensions.x, dimensions.y, dimensions.z) * 0.5
    return min_corner, max_corner, dimensions, radius


def _center_and_scale(model: bpy.types.Object):
    bpy.ops.object.select_all(action="DESELECT")
    model.select_set(True)
    bpy.context.view_layer.objects.active = model

    bpy.context.view_layer.update()
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    model.location = Vector((0.0, 0.0, 0.0))
    bpy.context.view_layer.update()

    _, _, dimensions, _ = _compute_bounds(model)
    max_dim = max(dimensions.x, dimensions.y, dimensions.z)
    target_size = 2.2
    if max_dim > 0:
        scale_factor = target_size / max_dim
        model.scale = [s * scale_factor for s in model.scale]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Recentre after scaling
    bpy.context.view_layer.update()
    _, _, _, radius = _compute_bounds(model)
    radius = max(radius, 1.0)
    # Keep model centred at origin for consistent turntable rotation
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    model.location = Vector((0.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    return radius


def _apply_material(model: bpy.types.Object):
    mat_name = "BR_Matte"
    material = bpy.data.materials.get(mat_name)
    if material is None:
        material = bpy.data.materials.new(mat_name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        for node in list(nodes):
            nodes.remove(node)
        output = nodes.new("ShaderNodeOutputMaterial")
        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.location = (-200, 0)
        output.location = (0, 0)
        shader.inputs["Base Color"].default_value = (0.82, 0.80, 0.76, 1.0)
        shader.inputs["Roughness"].default_value = 0.55
        if "Sheen Tint" in shader.inputs:
            try:
                shader.inputs["Sheen Tint"].default_value = 0.2
            except Exception:  # noqa: BLE001
                pass
        material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    if model.data.materials:
        model.data.materials.clear()
    model.data.materials.append(material)
    if hasattr(model.data, "use_auto_smooth"):
        model.data.use_auto_smooth = True


def _auto_orientation(model: bpy.types.Object) -> tuple[str, float]:
    """
    Smart auto-orientation that analyzes the mesh shape, symmetry, and distribution
    to determine the best rotation axis and starting angle for a turntable.
    """
    # Get mesh data
    mesh = model.data
    if not mesh.vertices:
        return "Z", 0.0
    
    # Calculate bounding box dimensions
    bbox = [Vector(corner) for corner in model.bound_box]
    xs = [corner[0] for corner in bbox]
    ys = [corner[1] for corner in bbox]
    zs = [corner[2] for corner in bbox]
    lengths = {
        "X": max(xs) - min(xs),
        "Y": max(ys) - min(ys),
        "Z": max(zs) - min(zs),
    }
    
    # Get all vertex positions
    vertices = [model.matrix_world @ Vector(v.co) for v in mesh.vertices]
    
    # Calculate center of mass
    center = Vector((0.0, 0.0, 0.0))
    for v in vertices:
        center += v
    center /= len(vertices)
    
    # Calculate variance along each axis (measure of distribution)
    variances = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    for v in vertices:
        diff = v - center
        variances["X"] += diff.x ** 2
        variances["Y"] += diff.y ** 2
        variances["Z"] += diff.z ** 2
    for axis in variances:
        variances[axis] /= len(vertices)
    
    # Analyze aspect ratios
    dims = sorted(lengths.items(), key=lambda x: x[1], reverse=True)
    longest_dim = dims[0][0]
    shortest_dim = dims[2][0]
    middle_dim = dims[1][0]
    
    longest_length = dims[0][1]
    middle_length = dims[1][1]
    shortest_length = dims[2][1]
    
    # Calculate ratios
    aspect_ratio_longest_middle = longest_length / middle_length if middle_length > 0 else 1.0
    aspect_ratio_middle_shortest = middle_length / shortest_length if shortest_length > 0 else 1.0
    
    # Decision tree for smart axis selection
    axis = "Z"
    offset = 0.0
    
    # Case 1: Very tall/thin object (like a standing figure)
    if longest_dim == "Z" and aspect_ratio_longest_middle > 1.5:
        axis = "Z"
        # Determine best starting angle by checking which horizontal view shows more detail
        if lengths["X"] < lengths["Y"]:
            offset = 90.0  # Start showing wider side
    
    # Case 2: Flat/horizontal object (like a plate or table)
    elif shortest_dim == "Z" and aspect_ratio_longest_middle < 1.3:
        axis = "Z"
        # For flat objects, start showing the longer side
        if lengths["X"] > lengths["Y"]:
            offset = 0.0
        else:
            offset = 90.0
    
    # Case 3: Long horizontal object (like a rod or sword)
    elif (longest_dim in ("X", "Y") and aspect_ratio_longest_middle > 1.8):
        # Rotate around Z (vertical axis) to show length
        axis = "Z"
        # Start showing the side with more dimension in Y
        if longest_dim == "X":
            offset = 90.0  # Start showing Y side
        else:
            offset = 0.0
    
    # Case 4: Cube-like or balanced object
    elif aspect_ratio_longest_middle < 1.3:
        axis = "Z"  # Default vertical rotation
        # Check variance to see which horizontal axis has more variation
        if variances["X"] > variances["Y"] * 1.2:
            offset = 0.0  # More variation in X, show X side
        elif variances["Y"] > variances["X"] * 1.2:
            offset = 90.0  # More variation in Y, show Y side
        else:
            # Check which dimension shows more "interesting" angles
            # Analyze edge directions
            edge_directions = []
            if mesh.edges:
                for edge in mesh.edges:
                    v1 = vertices[edge.vertices[0]]
                    v2 = vertices[edge.vertices[1]]
                    edge_dir = (v2 - v1).normalized()
                    edge_directions.append(edge_dir)
            
            # Count edges that are primarily horizontal (XY plane)
            horizontal_edges = sum(1 for e in edge_directions if abs(e.z) < 0.5) if edge_directions else 0
            
            if horizontal_edges > len(edge_directions) * 0.6:
                # Mostly horizontal structure - start showing longer horizontal dimension
                if lengths["X"] > lengths["Y"]:
                    offset = 0.0
                else:
                    offset = 90.0
            else:
                # Mixed structure - default to showing X side
                offset = 0.0
    
    # Case 5: Vertical object but not extremely tall
    else:
        axis = "Z"
        # For moderately tall objects, analyze which view is more interesting
        # Check if object has more detail in X or Y direction
        x_range_detail = max(xs) - min(xs)
        y_range_detail = max(ys) - min(ys)
        
        if x_range_detail > y_range_detail * 1.2:
            offset = 0.0  # Show X side (more detail)
        elif y_range_detail > x_range_detail * 1.2:
            offset = 90.0  # Show Y side (more detail)
        else:
            # Similar detail - check variance
            if variances["X"] > variances["Y"]:
                offset = 0.0
            else:
                offset = 90.0
    
    return axis, offset


def _auto_brightness(model: bpy.types.Object, radius: float) -> float:
    """Analyze model geometry to determine optimal exposure (optimized)."""
    if not model or not model.data:
        return 0.0
    bbox = [model.matrix_world @ Vector(corner) for corner in model.bound_box]
    dims = [max(v[i] for v in bbox) - min(v[i] for v in bbox) for i in range(3)]
    volume = dims[0] * dims[1] * dims[2]
    sa_to_vol = (2 * sum(dims[i] * dims[(i+1)%3] for i in range(3)) / volume) if volume > 0 else 0
    exposure = max(-1.5, min(1.5, -radius * 0.3 + (1.0 - min(sa_to_vol / 10.0, 1.0)) * 0.4))
    return exposure


def _look_at(obj: bpy.types.Object, target: Vector):
    direction = target - obj.location
    if direction.length == 0:
        return
    rotation = direction.to_track_quat("-Z", "Y")
    obj.rotation_euler = rotation.to_euler()


def _setup_camera(scene: bpy.types.Scene, radius: float, focus_point: Vector | None = None):
    if focus_point is None:
        focus_point = Vector((0.0, 0.0, 0.0))
    camera_data = bpy.data.cameras.new("BR_Camera")
    camera_obj = bpy.data.objects.new("BR_Camera", camera_data)
    scene.collection.objects.link(camera_obj)
    scene.camera = camera_obj

    safe_radius = radius * 1.15 + 0.15
    distance = max(safe_radius * 3.0, 3.6)
    height = max(safe_radius * 1.3, 1.6)
    camera_obj.location = Vector((0.0, -distance, height))
    _look_at(camera_obj, focus_point)

    camera_data.lens_unit = "FOV"
    camera_data.angle = math.radians(48)
    camera_data.clip_start = 0.01
    camera_data.clip_end = 1000
    return camera_obj


def _kelvin_to_rgb(kelvin: int) -> tuple[float, float, float]:
    """
    Convert Kelvin temperature to RGB color.
    Based on the Planckian locus approximation.
    Returns normalized RGB values (0.0-1.0).
    """
    # Clamp to reasonable range
    kelvin = max(1000, min(40000, kelvin))
    
    # Normalize to 0-1 range for calculations
    temp = kelvin / 100.0
    
    # Calculate red component
    if temp <= 66:
        red = 1.0
    else:
        red = temp - 60
        red = 329.698727446 * (red ** -0.1332047592)
        red = max(0.0, min(1.0, red / 255.0))
    
    # Calculate green component
    if temp <= 66:
        green = temp
        green = 99.4708025861 * math.log(green) - 161.1195681661
        green = max(0.0, min(1.0, green / 255.0))
    else:
        green = temp - 60
        green = 288.1221695283 * (green ** -0.0755148492)
        green = max(0.0, min(1.0, green / 255.0))
    
    # Calculate blue component
    if temp >= 66:
        blue = 1.0
    elif temp <= 19:
        blue = 0.0
    else:
        blue = temp - 10
        blue = 138.5177312231 * math.log(blue) - 305.0447927307
        blue = max(0.0, min(1.0, blue / 255.0))
    
    return (red, green, blue)


def _create_area_light(scene: bpy.types.Scene, name: str, location: Vector, power: float, size: float, color: tuple[float, float, float] | None = None):
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = power
    # Use provided color or default warm color
    light_data.color = color if color else (0.8, 0.66, 0.31)
    light_data.shape = "RECTANGLE"
    light_data.size = size
    light_data.size_y = size * 0.65

    light_obj = bpy.data.objects.new(name, light_data)
    light_obj.location = location
    scene.collection.objects.link(light_obj)
    _look_at(light_obj, Vector((0.0, 0.0, 0.4)))
    return light_obj


def _setup_lighting(scene: bpy.types.Scene, radius: float, kelvin: int = 3200):
    safe_radius = radius * 1.1 + 0.1
    key_distance = max(safe_radius * 2.4, 3.0)
    fill_distance = key_distance * 1.1
    height = max(safe_radius * 1.15, 1.6)
    
    # Convert Kelvin to RGB color
    light_color = _kelvin_to_rgb(kelvin)
    # Slightly cooler fill light for contrast
    fill_kelvin = min(10000, kelvin + 500)
    fill_color = _kelvin_to_rgb(fill_kelvin)

    _create_area_light(
        scene,
        "BR_Key_Light",
        Vector((key_distance * 0.6, -key_distance, height)),
        power=1800,
        size=max(safe_radius * 1.5, 1.8),
        color=light_color,
    )
    _create_area_light(
        scene,
        "BR_Fill_Light",
        Vector((-key_distance * 0.6, -fill_distance, height * 0.9)),
        power=900,
        size=max(safe_radius * 1.4, 1.8),
        color=fill_color,
    )
    top_light = _create_area_light(
        scene,
        "BR_Top_Fill",
        Vector((0.0, 0.0, height * 2.1)),
        power=700,
        size=max(safe_radius * 2.0, 2.6),
        color=light_color,
    )
    top_light.rotation_euler = (math.radians(180), 0.0, 0.0)


def _enable_gpu_devices() -> bool:
    """Attempt to switch Cycles to GPU rendering (Metal / OptiX / CUDA / HIP / OneAPI)."""
    try:
        addon_utils.enable("cycles", default_set=True, persistent=True)
    except Exception:  # noqa: BLE001
        pass

    prefs = bpy.context.preferences
    cycles_addon = prefs.addons.get("cycles")
    if not cycles_addon:
        return False

    cprefs = cycles_addon.preferences
    device_prop = cprefs.bl_rna.properties.get("compute_device_type")
    if not device_prop:
        return False

    available_types = {item.identifier for item in device_prop.enum_items}
    preferred_order = []
    if sys.platform == "darwin":
        preferred_order.append("METAL")
    preferred_order.extend(["OPTIX", "CUDA", "HIP", "ONEAPI"])
    preferred_order.append("NONE")

    device_choice = next((item for item in preferred_order if item in available_types), None)
    if not device_choice or device_choice == "NONE":
        return False

    try:
        cprefs.compute_device_type = device_choice
    except Exception:  # noqa: BLE001
        return False

    try:
        cprefs.get_devices()
    except Exception:  # noqa: BLE001
        pass

    devices = getattr(cprefs, "devices", [])
    if not devices:
        return False

    enabled = False
    for device in devices:
        if device.type == "CPU":
            device.use = False
        else:
            device.use = True
            enabled = True

    system_prefs = getattr(prefs, "system", None)
    if system_prefs and hasattr(system_prefs, "compute_device_type"):
        system_prefs.compute_device_type = device_choice

    return enabled


def _configure_world(scene: bpy.types.Scene):
    if scene.world is None:
        scene.world = bpy.data.worlds.new("BR_World")
    scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes
    for node in list(nodes):
        nodes.remove(node)

    output_node = nodes.new(type="ShaderNodeOutputWorld")
    background = nodes.new(type="ShaderNodeBackground")
    background.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    background.inputs[1].default_value = 1.0
    output_node.location = (200, 0)
    background.location = (0, 0)
    links = scene.world.node_tree.links
    links.new(background.outputs["Background"], output_node.inputs["Surface"])


def _animate_turntable(model: bpy.types.Object, frame_start: int, frame_end: int, axis: str, offset_degrees: float):
    axis_index = {"X": 0, "Y": 1, "Z": 2}[axis.upper()]
    base_rotation = [0.0, 0.0, 0.0]
    base_rotation[axis_index] = math.radians(offset_degrees)
    model.rotation_euler = tuple(base_rotation)
    model.keyframe_insert(data_path="rotation_euler", frame=frame_start)

    final_rotation = list(model.rotation_euler)
    final_rotation[axis_index] = math.radians(offset_degrees + 360.0)
    model.rotation_euler = final_rotation
    model.keyframe_insert(data_path="rotation_euler", frame=frame_end + 1)

    if model.animation_data and model.animation_data.action:
        for fcurve in model.animation_data.action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"

    model.rotation_euler = tuple(base_rotation)


def _configure_tiles(scene: bpy.types.Scene, gpu_enabled: bool, base_tile: int = 256):
    tile_gpu = max(64, min(512, base_tile * 2))
    tile_cpu = max(32, min(256, base_tile))
    tile_size = tile_gpu if gpu_enabled else tile_cpu

    render = scene.render
    cycles_settings = getattr(scene, "cycles", None)

    if hasattr(render, "use_persistent_data"):
        render.use_persistent_data = True
    if cycles_settings and hasattr(cycles_settings, "use_persistent_data"):
        cycles_settings.use_persistent_data = True

    targets = [
        (render, "tile_x"),
        (render, "tile_y"),
        (cycles_settings, "tile_x") if cycles_settings else (None, None),
        (cycles_settings, "tile_y") if cycles_settings else (None, None),
        (cycles_settings, "tile_size") if cycles_settings else (None, None),
    ]
    for target, attr in targets:
        if target and hasattr(target, attr):
            try:
                setattr(target, attr, tile_size)
            except Exception:  # noqa: BLE001
                continue


def _add_watermark(scene: bpy.types.Scene, size: int):
    """Add watermark overlay using compositor nodes."""
    scene.use_nodes = True
    tree = scene.node_tree
    
    # Clear existing nodes
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    
    # Create nodes
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")
    render_layers.location = (-400, 0)
    
    # Text node for watermark
    text_node = tree.nodes.new(type="CompositorNodeText")
    text_node.location = (-400, -300)
    text_node.text = "MOTIVORA STUDIO"
    text_node.size = size * 0.08  # Scale text with resolution
    text_node.location_x = 0.0  # Center horizontally
    text_node.location_y = -0.5  # Bottom half
    
    # Color node for watermark (semi-transparent white)
    color_node = tree.nodes.new(type="CompositorNodeMixRGB")
    color_node.location = (-200, -200)
    color_node.blend_type = "MIX"
    color_node.inputs["Fac"].default_value = 0.6  # 60% opacity
    
    # Set watermark color (white)
    color_input = color_node.inputs["Color2"]
    color_input.default_value = (1.0, 1.0, 1.0, 1.0)
    
    # Composite output
    composite = tree.nodes.new(type="CompositorNodeComposite")
    composite.location = (200, 0)
    
    # Connect: Render -> Mix -> Output
    # Mix watermark text over the render
    tree.links.new(render_layers.outputs["Image"], color_node.inputs["Color1"])
    tree.links.new(text_node.outputs["Alpha"], color_node.inputs["Fac"])
    
    # Connect watermark color to mix
    # For text overlay, we need to use the text alpha and mix properly
    # Create alpha overlay node
    mix_overlay = tree.nodes.new(type="CompositorNodeMixRGB")
    mix_overlay.location = (0, 0)
    mix_overlay.blend_type = "MIX"
    mix_overlay.inputs["Fac"].default_value = 0.7  # 70% opacity
    
    # Set watermark text color (white)
    mix_overlay.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1.0)
    
    # Connect: Render -> Mix Overlay
    tree.links.new(render_layers.outputs["Image"], mix_overlay.inputs["Color1"])
    # Use text alpha to mask where watermark appears
    tree.links.new(text_node.outputs["Alpha"], mix_overlay.inputs["Fac"])
    # Mix watermark text color
    text_color = tree.nodes.new(type="CompositorNodeRGB")
    text_color.location = (-200, -400)
    text_color.outputs["RGBA"].default_value = (1.0, 1.0, 1.0, 1.0)
    
    # Better approach: use Mix node with multiply for watermark effect
    tree.links.new(mix_overlay.outputs["Image"], composite.inputs["Image"])
    
    # Also connect alpha from render layers
    if "Alpha" in render_layers.outputs:
        tree.links.new(render_layers.outputs["Alpha"], composite.inputs["Alpha"])


def _add_watermark_v2(scene: bpy.types.Scene, size: int):
    """Add watermark overlay using compositor nodes - using image overlay method."""
    scene.use_nodes = True
    tree = scene.node_tree
    
    # Clear existing nodes
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    
    # Create render layers node
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")
    render_layers.location = (-400, 0)
    
    # Create a simple overlay using a color node and mix
    # We'll create a semi-transparent white rectangle at the bottom
    rgb_node = tree.nodes.new(type="CompositorNodeRGB")
    rgb_node.location = (-400, -300)
    rgb_node.outputs[0].default_value = (1.0, 1.0, 1.0, 0.6)  # White, 60% opacity
    
    # Create a mask for bottom portion (where watermark goes)
    # Use a gradient node to create a mask at the bottom
    gradient_node = tree.nodes.new(type="CompositorNodeValToRGB")
    gradient_node.location = (-400, -500)
    
    # Mix node to overlay watermark
    mix_node = tree.nodes.new(type="CompositorNodeMixRGB")
    mix_node.location = (0, 0)
    mix_node.blend_type = "OVERLAY"
    mix_node.inputs["Fac"].default_value = 0.3  # 30% blend for subtle watermark
    
    # Composite output
    composite = tree.nodes.new(type="CompositorNodeComposite")
    composite.location = (200, 0)
    
    # Connect: Render -> Mix -> Output
    tree.links.new(render_layers.outputs["Image"], mix_node.inputs["Color1"])
    tree.links.new(rgb_node.outputs["RGBA"], mix_node.inputs["Color2"])
    tree.links.new(mix_node.outputs["Image"], composite.inputs["Image"])
    
    # Connect alpha
    if "Alpha" in render_layers.outputs:
        tree.links.new(render_layers.outputs["Alpha"], composite.inputs["Alpha"])
    
    # Note: For a proper text watermark, you'd need to render text to an image first
    # or use Blender's text object in a separate render pass. This is a simplified version.


def _configure_render(
    scene: bpy.types.Scene,
    output_path: str,
    fps: int,
    size: int,
    video_format: str,
    quality: str,
    watermark: bool = False,
    exposure: float = 0.0,
):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Force Eevee when available; otherwise fall back to Cycles with reduced samples.
    forced_engine = "BLENDER_EEVEE"
    engine_prop = scene.render.bl_rna.properties.get("engine")
    available_engines = {item.identifier for item in engine_prop.enum_items} if engine_prop else set()
    quality = quality.lower()
    gpu_enabled = _enable_gpu_devices()

    def _setup_cycles(sample_count: int, resolution_scale: float = 1.0):
        scene.render.engine = "CYCLES"
        if hasattr(scene.cycles, "device"):
            scene.cycles.device = "GPU" if gpu_enabled else "CPU"
        _configure_tiles(scene, gpu_enabled, base_tile=size // 4 or 256)
        if hasattr(scene.cycles, "samples"):
            scene.cycles.samples = sample_count
        if hasattr(scene.cycles, "use_adaptive_sampling"):
            scene.cycles.use_adaptive_sampling = True
        if hasattr(scene.cycles, "adaptive_threshold"):
            scene.cycles.adaptive_threshold = 0.05  # Increased from 0.01 - faster convergence
        if hasattr(scene.cycles, "adaptive_min_samples"):
            try:
                # Reduced minimum samples for faster rendering
                scene.cycles.adaptive_min_samples = max(4, min(32, sample_count // 8))  # Reduced from //4
            except Exception:  # noqa: BLE001
                pass
        if hasattr(scene.cycles, "use_preview_adaptive_sampling"):
            scene.cycles.use_preview_adaptive_sampling = True
        if hasattr(scene.cycles, "use_denoising"):
            scene.cycles.use_denoising = True
        denoiser_prop = scene.cycles.bl_rna.properties.get("denoiser")
        if denoiser_prop:
            available = {item.identifier for item in denoiser_prop.enum_items}
            for option in ("OPTIX", "OPENIMAGEDENOISE", "NLM"):
                if option in available:
                    try:
                        scene.cycles.denoiser = option
                        break
                    except Exception:  # noqa: BLE001
                        continue
        # Reduce bounces significantly for speed (still looks good with denoising)
        if hasattr(scene.cycles, "max_bounces"):
            scene.cycles.max_bounces = 4  # Reduced from 12 - much faster
        if hasattr(scene.cycles, "diffuse_bounces"):
            scene.cycles.diffuse_bounces = 2  # Faster
        if hasattr(scene.cycles, "glossy_bounces"):
            scene.cycles.glossy_bounces = 2  # Faster
        if hasattr(scene.cycles, "transparent_max_bounces"):
            scene.cycles.transparent_max_bounces = 4  # Faster
        if hasattr(scene.cycles, "use_fast_gi"):
            scene.cycles.use_fast_gi = True
        if hasattr(scene.cycles, "use_denoising") and gpu_enabled:
            if hasattr(scene.cycles, "use_optix_ai_denoising"):
                try:
                    scene.cycles.use_optix_ai_denoising = True
                except Exception:  # noqa: BLE001
                    pass
        scene.render.resolution_x = int(size * resolution_scale)
        scene.render.resolution_y = int(size * resolution_scale)

    if quality == "fast":
        if forced_engine in available_engines:
            scene.render.engine = forced_engine
            if hasattr(scene.eevee, "taa_render_samples"):
                scene.eevee.taa_render_samples = 16  # Reduced from 24 for speed
            if hasattr(scene.eevee, "taa_samples"):
                scene.eevee.taa_samples = 8  # Reduced from 12 for speed
            if hasattr(scene.eevee, "use_gtao"):
                scene.eevee.use_gtao = True
            if hasattr(scene.eevee, "use_soft_shadows"):
                scene.eevee.use_soft_shadows = True
            if hasattr(scene.eevee, "shadow_cube_size"):
                scene.eevee.shadow_cube_size = "512"  # Reduced from 1024 for speed
            if hasattr(scene.eevee, "shadow_cascade_size"):
                scene.eevee.shadow_cascade_size = "512"  # Reduced from 1024 for speed
        else:
            _setup_cycles(32)  # Reduced from 48 for speed
        scene.render.resolution_x = size
        scene.render.resolution_y = size
    elif quality == "ultra":
        # Balanced: 128 samples with denoising - still 2.5x faster than old 320 samples
        # Denoising maintains quality while allowing lower samples
        _setup_cycles(128, 1.0)  # Reduced from 320, removed resolution scale
    else:  # standard
        # Good balance: 96 samples - much faster than old 160, still high quality
        _setup_cycles(96, 1.0)  # Reduced from 160

    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.film_transparent = True

    scene.render.image_settings.file_format = "FFMPEG"
    color_prop = scene.render.image_settings.bl_rna.properties.get("color_mode")
    target_color = "RGBA" if video_format == "webm" else "RGB"
    try:
        if color_prop and any(item.identifier == target_color for item in color_prop.enum_items):
            scene.render.image_settings.color_mode = target_color
        else:
            scene.render.image_settings.color_mode = "RGB"
    except TypeError:
        scene.render.image_settings.color_mode = "RGB"

    if video_format == "mp4":
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.use_lossless_output = False
        scene.render.ffmpeg.audio_codec = "NONE"
        pixel_prop = scene.render.ffmpeg.bl_rna.properties.get("pixel_format")
        if pixel_prop and any(item.identifier == "YUV420P" for item in pixel_prop.enum_items):
            scene.render.ffmpeg.pixel_format = "YUV420P"
        if hasattr(scene.render.ffmpeg, "use_alpha"):
            scene.render.ffmpeg.use_alpha = False
    else:
        scene.render.ffmpeg.format = "WEBM"
        codec_prop = scene.render.ffmpeg.bl_rna.properties.get("codec")
        if codec_prop:
            codecs_available = {item.identifier for item in codec_prop.enum_items}
            if "WEBM_VP9" in codecs_available:
                scene.render.ffmpeg.codec = "WEBM_VP9"
            elif "WEBM" in codecs_available:
                scene.render.ffmpeg.codec = "WEBM"
            elif "AV1" in codecs_available:
                scene.render.ffmpeg.codec = "AV1"
        scene.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
        scene.render.ffmpeg.use_lossless_output = False
        scene.render.ffmpeg.audio_codec = "NONE"
        pixel_prop = scene.render.ffmpeg.bl_rna.properties.get("pixel_format")
        if pixel_prop:
            pixels_available = {item.identifier for item in pixel_prop.enum_items}
            if "YUVA420P" in pixels_available:
                scene.render.ffmpeg.pixel_format = "YUVA420P"
            elif "RGBA" in pixels_available:
                scene.render.ffmpeg.pixel_format = "RGBA"
        if hasattr(scene.render.ffmpeg, "use_alpha"):
            scene.render.ffmpeg.use_alpha = True
    scene.render.ffmpeg.use_autosplit = False
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = exposure  # Use provided exposure value
    scene.render.filepath = output_path
    
    # Add watermark if requested
    if watermark:
        _add_watermark_v2(scene, size)


def main():
    args = _parse_args()
    scene = bpy.context.scene

    _clean_scene()
    model = _import_model(args.input)
    radius = _center_and_scale(model)
    _apply_material(model)
    _configure_world(scene)
    _setup_camera(scene, radius)
    _setup_lighting(scene, radius, kelvin=args.kelvin)

    frame_start = 1
    frame_count = max(int(round(args.seconds * args.fps)), 1)
    frame_end = frame_start + frame_count - 1
    scene.frame_start = frame_start
    scene.frame_end = frame_end

    axis = args.axis
    offset = args.offset
    if args.auto:
        axis, offset = _auto_orientation(model)
        print(f"[AUTO] axis={axis} offset={offset:.1f}", flush=True)

    # Calculate exposure (auto-brightness or manual)
    exposure = args.exposure
    if args.auto_brightness:
        auto_exposure = _auto_brightness(model, radius)
        exposure = auto_exposure
        print(f"[AUTO] exposure={exposure:.2f}", flush=True)

    _animate_turntable(model, frame_start, frame_end, axis, offset)
    _configure_render(scene, args.out, args.fps, args.size, args.format, args.quality, args.watermark, exposure=exposure)

    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f"[Turntable] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

