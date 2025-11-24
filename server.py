#!/usr/bin/env python3
"""
Motivora Studio – Local Flask frontend for Blender-powered turntable renders.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Union

import threading
import secrets
import sys
import re

from flask import (
    Flask,
    Response,
    after_this_request,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.utils import secure_filename
from models import db, User, Render
from license_checker import LicenseChecker, can_download

# Google OAuth imports
try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    from google_auth_oauthlib.flow import Flow
    GOOGLE_OAUTH_AVAILABLE = True
except ImportError:
    GOOGLE_OAUTH_AVAILABLE = False

APP_ROOT = Path(__file__).resolve().parent
TURN_TABLE_SCRIPT = APP_ROOT / "turntable.py"
DEFAULT_BLENDER_BIN = Path("/Applications/Blender.app/Contents/MacOS/Blender")
ALLOWED_EXTENSIONS = {".stl"}
OUTPUT_FORMAT = os.environ.get("MOTIVORA_FORMAT", "mp4").lower()
RENDER_SECONDS = float(os.environ.get("MOTIVORA_SECONDS", "10"))
FRAMES_PER_SECOND = int(os.environ.get("MOTIVORA_FPS", "25"))
BASE_RENDER_FPS = int(os.environ.get("MOTIVORA_RENDER_FPS", "11"))
if BASE_RENDER_FPS < 1:
    BASE_RENDER_FPS = 11
FINAL_VIDEO_FPS = FRAMES_PER_SECOND
RENDER_SIZE = int(os.environ.get("MOTIVORA_SIZE", "1080"))
ROTATION_AXIS = os.environ.get("MOTIVORA_AXIS", "Z").upper()
if ROTATION_AXIS not in {"X", "Y", "Z"}:
    ROTATION_AXIS = "Z"
if OUTPUT_FORMAT not in {"webm", "mp4"}:
    OUTPUT_FORMAT = "mp4"
DEFAULT_QUALITY = os.environ.get("MOTIVORA_QUALITY", "ultra").lower()
if DEFAULT_QUALITY not in {"fast", "standard", "ultra"}:
    DEFAULT_QUALITY = "ultra"
DOWNLOAD_URL = os.environ.get("MOTIVORA_DOWNLOAD_URL", "/download")
FFMPEG_BIN = os.environ.get("MOTIVORA_FFMPEG", "ffmpeg")

# Storage directory for persistent renders
STORAGE_ROOT = APP_ROOT / "storage"
STORAGE_ROOT.mkdir(exist_ok=True)
(STORAGE_ROOT / "renders").mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB upload limit
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{APP_ROOT / 'motivora.db'}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth_login"
login_manager.login_message = "Please log in to access this page."

ACTIVE_JOBS: Dict[str, Dict[str, Union[str, float]]] = {}
ACTIVE_PROCESSES: Dict[str, subprocess.Popen[str]] = {}

# Initialize license checker
license_checker = LicenseChecker()

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_ENABLED = GOOGLE_OAUTH_AVAILABLE and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

if GOOGLE_OAUTH_ENABLED:
    # OAuth 2.0 scopes
    SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


# Helper functions for license management
def get_user_license_key() -> Optional[str]:
    """Get license key from session or user model."""
    if current_user.is_authenticated:
        return session.get("license_key") or getattr(current_user, "license_key", None)
    return None


def get_user_tier() -> str:
    """Get current user's subscription tier (optimized)."""
    if os.environ.get("MOTIVORA_DEV_MODE") == "1":
        return "pro"  # Dev mode: everyone gets pro access
    if not current_user.is_authenticated:
        return "free"
    
    # First check database subscription_tier (updated by webhooks)
    if hasattr(current_user, 'subscription_tier') and current_user.subscription_tier:
        # Check if subscription has expired
        if current_user.subscription_expires_at and current_user.subscription_expires_at < datetime.utcnow():
            # Subscription expired, downgrade to free
            if current_user.subscription_tier != "free":
                current_user.subscription_tier = "free"
                current_user.subscription_expires_at = None
                db.session.commit()
            return "free"
        return current_user.subscription_tier
    
    # Fallback: check license key if available
    license_key = get_user_license_key()
    if license_key:
        result = license_checker.validate_license(license_key, current_user.email)
        if result.get("valid"):
            tier = result.get("tier", "free")
            # Update database with tier from license
            if tier != current_user.subscription_tier:
                current_user.subscription_tier = tier
                db.session.commit()
            return tier
    
    return "free"


def user_can_download() -> bool:
    """Check if current user can download renders."""
    return can_download(get_user_tier())


def get_upgrade_url(tier: str = "pro") -> str:
    """Get Lemon Squeezy upgrade URL for a specific tier."""
    # Get variant ID for the tier
    if tier == "pro":
        variant_id = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_PRO")
    elif tier == "enterprise":
        variant_id = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE")
    else:
        variant_id = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_PRO")  # Default to Pro
    
    # Get store URL from environment or use default
    store_url = os.environ.get("LEMON_SQUEEZY_STORE_URL", "https://motivora.lemonsqueezy.com")
    
    if variant_id:
        return f"{store_url}/checkout/buy/{variant_id}"
    
    # Fallback to generic upgrade URL
    return os.environ.get("LEMON_SQUEEZY_UPGRADE_URL", f"{store_url}/checkout")


EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def resolve_blender_path() -> Path:
    """Find a usable Blender executable."""
    configured = os.environ.get("BLENDER_BIN")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path
    if DEFAULT_BLENDER_BIN.is_file():
        return DEFAULT_BLENDER_BIN

    from shutil import which

    exe = which("blender")
    if exe:
        return Path(exe)
    raise FileNotFoundError("Blender executable not found. Update BLENDER_BIN in server.py.")


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def render_form(message: Optional[str] = None, status: str = "") -> str:
    return render_template(
        "index.html",
        message=message,
        status_message=status,
        default_quality=DEFAULT_QUALITY,
        current_year=datetime.now().year,
        app_mode=True,
        body_class="app-mode",
        download_url=DOWNLOAD_URL,
        OUTPUT_FORMAT=OUTPUT_FORMAT,
        current_user=current_user if current_user.is_authenticated else None,
    )


def render_marketing() -> str:
    return render_template(
        "index.html",
        message=None,
        status_message="",
        default_quality=DEFAULT_QUALITY,
        current_year=datetime.now().year,
        app_mode=False,
        body_class="marketing-mode",
        download_url=DOWNLOAD_URL,
        OUTPUT_FORMAT=OUTPUT_FORMAT,
    )


def _interpolate_video(
    input_path: Path,
    output_path: Path,
    fps: int,
    video_format: str,
) -> None:
    if fps <= 0:
        shutil.move(input_path, output_path)
        return

    filter_expr = f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        filter_expr,
        "-an",
    ]

    if video_format == "mp4":
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
            ]
        )
    else:
        cmd.extend(
            [
                "-c:v",
                "libvpx-vp9",
                "-pix_fmt",
                "yuva420p",
                "-b:v",
                "0",
                "-crf",
                "12",
            ]
        )
    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg interpolation failed ({result.returncode}). "
            f"Command: {' '.join(cmd)}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        )

    try:
        input_path.unlink(missing_ok=True)
    except Exception:
        pass


def invoke_blender(
    blender_bin: Path,
    input_model: Path,
    output_path: Path,
    axis: str,
    offset: float,
    auto: bool,
    quality: str,
    video_format: str,
    render_size: int,
    watermark: bool = False,
    kelvin: int = 5600,
    auto_brightness: bool = False,
    exposure: float = 0.0,
) -> subprocess.Popen[str]:
    command = [
        str(blender_bin),
        "-b",
        "-P",
        str(TURN_TABLE_SCRIPT),
        "--",
        "--input",
        str(input_model),
        "--out",
        str(output_path),
        "--seconds",
        str(RENDER_SECONDS),
        "--fps",
        str(BASE_RENDER_FPS),
        "--size",
        str(render_size),
        "--axis",
        axis,
        "--format",
        video_format,
        "--offset",
        str(offset),
    ]
    if auto:
        command.append("--auto")
    command.extend(["--quality", quality])
    if watermark:
        command.append("--watermark")
    command.extend(["--kelvin", str(kelvin)])
    if auto_brightness:
        command.append("--auto_brightness")
    else:
        command.extend(["--exposure", str(exposure)])

    env = os.environ.copy()
    extra_paths = [p for p in sys.path if p]
    existing = env.get("PYTHONPATH")
    if existing:
        env["PYTHONPATH"] = os.pathsep.join(extra_paths + [existing])
    else:
        env["PYTHONPATH"] = os.pathsep.join(extra_paths)

    print(f"[Server] Launching Blender: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    return process


def _monitor_blender_job(
    job_id: str,
    process: subprocess.Popen[str],
    total_frames: int,
) -> None:
    job = ACTIVE_JOBS[job_id]
    output_path = Path(job["output_path"])
    workdir = Path(job["workdir"])
    blender_output_path = Path(job.get("blender_output_path", job["output_path"]))
    needs_interpolation = job.get("needs_interpolation", False)
    final_fps = int(job.get("final_fps", FINAL_VIDEO_FPS))
    video_format = job.get("video_format", OUTPUT_FORMAT)
    axis = job.get("axis", "Z")
    recent_lines: list[str] = []
    frame_durations: list[float] = []
    last_frame_index: Optional[int] = None
    last_frame_timestamp: Optional[float] = None
    try:
        stdout = process.stdout
        if stdout is None:
            raise RuntimeError("Failed to capture Blender output.")
        for raw_line in stdout:
            line = raw_line.strip()
            if not line:
                continue
            recent_lines.append(line)
            if len(recent_lines) > 10:
                recent_lines.pop(0)
            if line.startswith("[AUTO]"):
                job["message"] = line
                try:
                    parts = dict(
                        segment.split("=")
                        for segment in line.strip("[]").split()
                        if "=" in segment
                    )
                    if "axis" in parts:
                        job["axis"] = parts["axis"]
                    if "offset" in parts:
                        job["offset"] = float(parts["offset"])
                except Exception:
                    pass
                continue
            job["message"] = line
            if line.startswith("Fra:"):
                parts = [token for token in line.replace(":", " ").split() if token]
                frame_numbers = [token for token in parts if token.isdigit()]
                if frame_numbers:
                    frame = int(frame_numbers[0])
                    progress = min(100.0, max(0.0, (frame / total_frames) * 100.0))
                    job["progress"] = progress
                    job["message"] = f"Rendering frame {frame} of {total_frames} (axis {axis})"
                    now = time.time()
                    
                    # Update database if render record exists
                    if job.get("user_id"):
                        with app.app_context():
                            try:
                                render_record = Render.query.filter_by(job_id=job_id).first()
                                if render_record:
                                    render_record.progress = progress
                                    render_record.message = job["message"]
                                    db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                print(f"[Database] Update failed for job {job_id}: {e}", flush=True)
                    if last_frame_index is not None and frame > last_frame_index and last_frame_timestamp:
                        delta = now - last_frame_timestamp
                        if delta > 0:
                            frame_durations.append(delta)
                            if len(frame_durations) > 20:
                                frame_durations.pop(0)
                    last_frame_index = frame
                    last_frame_timestamp = now
                    job["last_frame_index"] = frame
                    job["last_frame_timestamp"] = now
                    warmup = 5
                    if len(frame_durations) >= warmup:
                        # Use more frames for better accuracy, with recent frames weighted more
                        sample = frame_durations[-20:] if len(frame_durations) > 20 else frame_durations
                        # Calculate weighted average (recent frames count more)
                        weights = [i + 1 for i in range(len(sample))]
                        weighted_sum = sum(d * w for d, w in zip(sample, weights))
                        weight_total = sum(weights)
                        avg_frame = weighted_sum / weight_total
                        job["avg_frame_time"] = avg_frame
                        frames_remaining = max(0, total_frames - frame)
                        # Account for time already spent on current frame
                        current_frame_elapsed = now - last_frame_timestamp if last_frame_timestamp else 0
                        # Base estimate: time for remaining frames + time already spent on current frame
                        # Add 25% buffer for variance in frame times (some frames take longer)
                        base_eta = (avg_frame * frames_remaining) + current_frame_elapsed
                        eta_estimate = base_eta * 1.25
                        job["eta_seconds"] = max(0.0, eta_estimate)
                    else:
                        job["eta_seconds"] = None
    except Exception as exc:  # noqa: BLE001
        job["state"] = "error"
        job["message"] = f"Blender output error: {exc}"
    finally:
        return_code = process.wait()
        if return_code == 0 and blender_output_path.exists():
            try:
                if needs_interpolation:
                    job["message"] = "Post-processing frames for smoother motion…"
                    _interpolate_video(blender_output_path, output_path, final_fps, video_format)
                elif blender_output_path != output_path:
                    shutil.move(blender_output_path, output_path)
                # Move file to persistent storage if user is logged in
                render_record = None
                if job.get("user_id"):
                    persistent_path = STORAGE_ROOT / "renders" / f"{job_id}{Path(output_path).suffix}"
                    try:
                        shutil.copy2(output_path, persistent_path)
                        file_size = persistent_path.stat().st_size
                        
                        with app.app_context():
                            try:
                                render_record = Render.query.filter_by(job_id=job_id).first()
                                if render_record:
                                    render_record.file_path = str(persistent_path)
                                    render_record.file_size = file_size
                                    render_record.state = "finished"
                                    render_record.progress = 100.0
                                    render_record.message = f"Render complete (axis {axis})."
                                    render_record.finished_at = datetime.utcnow()
                                    db.session.commit()
                            except Exception as e:
                                db.session.rollback()
                                print(f"[Database] Failed to update render record: {e}", flush=True)
                    except Exception as e:
                        print(f"[Storage] Failed to copy file to persistent storage: {e}", flush=True)
                        
                job.update(
                    {
                        "state": "finished",
                        "message": f"Render complete (axis {axis}).",
                        "progress": 100.0,
                        "eta_seconds": 0.0,
                    }
                )
            except Exception as exc:
                error_msg = f"Post-processing failed: {exc}"
                job.update(
                    {
                        "state": "error",
                        "message": error_msg,
                        "progress": job.get("progress", 0.0),
                        "eta_seconds": None,
                    }
                )
                # Update database
                if job.get("user_id"):
                    with app.app_context():
                        render_record = Render.query.filter_by(job_id=job_id).first()
                        if render_record:
                            render_record.state = "error"
                            render_record.message = error_msg
                            render_record.finished_at = datetime.utcnow()
                            db.session.commit()
                print(f"[Post] {exc}", flush=True)
        elif job.get("state") != "error":
            detail = recent_lines[-1] if recent_lines else "No additional output from Blender."
            tail = "\n".join(recent_lines[-5:])
            message = f"Blender rendering failed (code {return_code}). Last line: {detail}"
            job.update(
                {
                    "state": "error",
                    "message": message,
                    "progress": job.get("progress", 0.0),
                    "eta_seconds": None,
                }
            )
            print(f"[Turntable] {message}\n--- Blender tail ---\n{tail}\n-------------------", flush=True)
            # Update database
            if job.get("user_id"):
                with app.app_context():
                    render_record = Render.query.filter_by(job_id=job_id).first()
                    if render_record:
                        render_record.state = "error"
                        render_record.message = message
                        render_record.finished_at = datetime.utcnow()
                        db.session.commit()
        if job.get("state") == "error":
            shutil.rmtree(workdir, ignore_errors=True)
            job["cleanup_done"] = True
        ACTIVE_PROCESSES.pop(job_id, None)


@app.route("/render", methods=["GET", "POST"])
def render_page() -> Union[Response, str]:
    if request.method == "GET":
        # Show app interface by default, marketing page only if ?marketing=1
        if request.args.get("marketing") == "1":
            return render_marketing()
        # Welcome message for first-time users
        if current_user.is_authenticated:
            status_msg = f"Welcome back, {current_user.name}! Ready to render."
        else:
            status_msg = "Upload an STL file to get started. No account required!"
        return render_form(status=status_msg)

    uploaded = request.files.get("model")
    if not uploaded or uploaded.filename == "":
        return jsonify({"message": "Please choose an STL file to upload."}), 400

    filename = secure_filename(uploaded.filename)
    if not allowed_file(filename):
        return jsonify({"message": "Only .stl files are supported."}), 400

    workdir = Path(tempfile.mkdtemp(prefix="bellarue_"))
    input_path = workdir / filename
    uploaded.save(input_path)

    try:
        auto_orientation = request.form.get("auto_orientation", "1") == "1"
        axis = request.form.get("axis", ROTATION_AXIS).upper()
        if axis not in {"X", "Y", "Z"}:
            axis = ROTATION_AXIS
        # Parse and validate form inputs (optimized)
        offset = max(0.0, min(360.0, float(request.form.get("offset", "0"))))
        quality = request.form.get("quality", DEFAULT_QUALITY).lower()
        if quality not in {"fast", "standard", "ultra"}:
            quality = DEFAULT_QUALITY
        video_format = request.form.get("format", OUTPUT_FORMAT).lower()
        if video_format not in {"webm", "mp4"}:
            video_format = OUTPUT_FORMAT
        render_size = int(request.form.get("resolution", str(RENDER_SIZE)))
        if render_size not in {720, 1080, 1440, 2160}:
            render_size = RENDER_SIZE
        kelvin = max(2000, min(10000, int(request.form.get("kelvin", "5600"))))

        # Brightness settings (optimized)
        auto_brightness = request.form.get("auto_brightness", "1") == "1"
        try:
            exposure = 0.0 if auto_brightness else max(-2.0, min(2.0, float(request.form.get("exposure", "0.0"))))
        except (ValueError, TypeError):
            exposure = 0.0

        # Check STL file size (before processing)
        stl_size = input_path.stat().st_size
        max_stl_size = 100 * 1024 * 1024  # 100MB limit for STL files
        if stl_size > max_stl_size:
            shutil.rmtree(workdir, ignore_errors=True)
            return jsonify({
                "message": f"STL file too large ({stl_size / (1024*1024):.1f}MB). Maximum size is 100MB."
            }), 400
        
        # Check concurrent render limit per user
        MAX_CONCURRENT_RENDERS = 5
        user_id = None
        # In dev mode, NO watermarks ever. Force pro access.
        is_dev_mode = os.environ.get("MOTIVORA_DEV_MODE") == "1"
        if is_dev_mode:
            needs_watermark = False  # Dev mode = no watermark, pro access
        else:
            needs_watermark = True  # Default: anonymous users get watermarked
            if current_user.is_authenticated:
                needs_watermark = get_user_tier() == "free"
        
        if current_user.is_authenticated:
            user_id = current_user.id
            
            # Check concurrent render limit
            with app.app_context():
                current_renders = Render.query.filter_by(
                    user_id=user_id,
                    state="running"
                ).count()
                if current_renders >= MAX_CONCURRENT_RENDERS:
                    shutil.rmtree(workdir, ignore_errors=True)
                    return jsonify({
                        "message": f"Maximum {MAX_CONCURRENT_RENDERS} concurrent renders allowed. Please wait for current renders to complete."
                    }), 429

        input_model = input_path

        suffix = ".mp4" if video_format == "mp4" else ".webm"
        mimetype = "video/mp4" if video_format == "mp4" else "video/webm"
        output_path = workdir / f"turntable{suffix}"
        needs_interpolation = BASE_RENDER_FPS != FINAL_VIDEO_FPS
        if needs_interpolation:
            blender_output_path = workdir / f"turntable_base{suffix}"
        else:
            blender_output_path = output_path
        blender_bin = resolve_blender_path()

        process = invoke_blender(
            blender_bin,
            input_model,
            blender_output_path,
            axis,
            offset,
            auto_orientation,
            quality,
            video_format,
            render_size,
            watermark=needs_watermark,
            kelvin=kelvin,
            auto_brightness=auto_brightness,
            exposure=exposure,
        )

        job_id = secrets.token_hex(8)
        total_frames = max(1, int(round(RENDER_SECONDS * BASE_RENDER_FPS)))
        download_name = f"{Path(filename).stem}_turntable{suffix}"
        quality_label = quality.capitalize()
        if auto_orientation:
            launch_message = f"Launching Blender ({quality_label}, auto orientation)…"
        else:
            launch_message = f"Launching Blender ({quality_label}, axis {axis}, start {offset:.1f}°)…"
        
        # Create render record in database if user is logged in
        render_record = None
        if user_id:
            render_record = Render(
                job_id=job_id,
                user_id=user_id,
                filename=filename,
                download_name=download_name,
                file_path=str(output_path),  # Temporary path, will be updated when finished
                mimetype=mimetype,
                quality=quality,
                video_format=video_format,
                render_size=render_size,
                axis=axis,
                offset=offset,
                auto_orientation=auto_orientation,
                state="running",
                progress=0.0,
                message=launch_message,
                started_at=datetime.utcnow(),
            )
            db.session.add(render_record)
            db.session.commit()
        
        ACTIVE_JOBS[job_id] = {
            "state": "running",
            "message": launch_message,
            "progress": 0.0,
            "output_path": str(output_path),
            "workdir": str(workdir),
            "download_name": download_name,
            "mimetype": mimetype,
            "video_format": video_format,
            "render_size": render_size,
            "axis": axis,
            "offset": offset,
            "auto": auto_orientation,
            "quality": quality,
            "started_at": time.time(),
            "eta_seconds": None,
            "total_frames": total_frames,
            "last_frame_index": 0,
            "last_frame_timestamp": None,
            "avg_frame_time": None,
            "needs_interpolation": needs_interpolation,
            "final_fps": FINAL_VIDEO_FPS,
            "blender_output_path": str(blender_output_path),
            "base_fps": BASE_RENDER_FPS,
            "user_id": user_id,
        }

        ACTIVE_PROCESSES[job_id] = process

        thread = threading.Thread(
            target=_monitor_blender_job,
            args=(job_id, process, total_frames),
            daemon=True,
        )
        thread.start()

        return jsonify({"job_id": job_id}), 202
    except FileNotFoundError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"message": str(exc)}), 500
    except ValueError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"message": f"Rendering failed: {exc}"}), 500


@app.route("/", methods=["GET"])
def index() -> Response:
    # Root shows marketing page, /render shows app
    return render_marketing()


@app.route("/download", methods=["GET"])
def download_page() -> str:
    """Desktop app download page."""
    # Check if auto-download is requested
    auto_download = request.args.get("auto", "true").lower() == "true"
    
    return render_template(
        "download.html",
        current_year=datetime.now().year,
        OUTPUT_FORMAT=OUTPUT_FORMAT,
        current_user=current_user if current_user.is_authenticated else None,
        auto_download=auto_download,
    )


@app.route("/download/app", methods=["GET"])
def download_app():
    """Download desktop app for the user's OS."""
    user_agent = request.headers.get("User-Agent", "").lower()
    
    # Detect OS from user agent
    if "mac" in user_agent or "darwin" in user_agent:
        platform = "macos"
        filename = "MotivoraStudio.dmg"
        mimetype = "application/x-apple-diskimage"
    elif "win" in user_agent:
        platform = "windows"
        filename = "MotivoraStudio.exe"
        mimetype = "application/x-msdownload"
    elif "linux" in user_agent:
        platform = "linux"
        filename = "MotivoraStudio.AppImage"
        mimetype = "application/x-executable"
    else:
        # Default to macOS if unknown
        platform = "macos"
        filename = "MotivoraStudio.dmg"
        mimetype = "application/x-apple-diskimage"
    
    # Check if file exists
    downloads_dir = APP_ROOT / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    app_file = downloads_dir / filename
    
    if app_file.exists():
        # File exists, serve it
        return send_file(
            app_file,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename,
        )
    else:
        # File doesn't exist yet - redirect to page with message
        return redirect(url_for("download_page", error="not_ready", platform=platform))


@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id: str):
    # Try database first
    render_record = Render.query.filter_by(job_id=job_id).first()
    if render_record:
        return jsonify({
            "state": render_record.state,
            "message": render_record.message or "",
            "progress": float(render_record.progress or 0.0),
            "eta_seconds": None,
        })
    
    # Fallback to active jobs
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return jsonify({"state": "unknown", "message": "Job not found."}), 404

    if job.get("state") == "error" and not job.get("cleanup_done"):
        shutil.rmtree(Path(job["workdir"]), ignore_errors=True)
        job["cleanup_done"] = True

    eta_seconds = job.get("eta_seconds")
    if job.get("state") == "running":
        avg_frame = job.get("avg_frame_time")
        last_ts = job.get("last_frame_timestamp")
        last_frame = job.get("last_frame_index")
        total_frames = job.get("total_frames")
        started = job.get("started_at")
        now = time.time()
        if avg_frame and last_ts and last_frame is not None and total_frames:
            frames_remaining = max(0, total_frames - last_frame)
            # Use the ETA from the monitor thread, but add a small buffer if it seems too optimistic
            base_eta = job.get("eta_seconds", 0.0)
            current_frame_time = now - last_ts
            # If current frame is taking longer than average, adjust ETA upward
            if current_frame_time > avg_frame * 1.5:
                adjustment = (current_frame_time - avg_frame) * 0.5
                eta_seconds = max(0.0, base_eta + adjustment)
            else:
                eta_seconds = base_eta
        elif started and job.get("progress", 0.0) > 0:
            progress = job["progress"]
            elapsed = max(0.0, now - started)
            eta_seconds = max(0.0, elapsed * (100.0 - progress) / progress)

    return jsonify(
        {
            "state": job.get("state", "unknown"),
            "message": job.get("message", ""),
            "progress": float(job.get("progress", 0.0)),
            "eta_seconds": eta_seconds,
        }
    )


@app.route("/status/ping", methods=["GET"])
def status_ping():
    return jsonify({"ok": True})


@app.route("/cancel/<job_id>", methods=["POST"])
def cancel_job(job_id: str):
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return jsonify({"message": "Job not found."}), 404
    
    if job.get("state") != "running":
        return jsonify({"message": "Job is not running."}), 400
    
    process = ACTIVE_PROCESSES.get(job_id)
    if process:
        try:
            process.terminate()
            time.sleep(0.5)
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
        ACTIVE_PROCESSES.pop(job_id, None)
    
    workdir = Path(job.get("workdir", ""))
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    
    job.update({
        "state": "cancelled",
        "message": "Render cancelled by user.",
        "progress": job.get("progress", 0.0),
        "eta_seconds": None,
        "cleanup_done": True,
    })
    
    return jsonify({"message": "Job cancelled successfully."})


@app.route("/download/<job_id>", methods=["GET"])
def download(job_id: str):
    # Try database first for logged-in users
    render_record = Render.query.filter_by(job_id=job_id).first()
    if render_record:
        # Check authorization - only owner can access renders with user_id
        if render_record.user_id:
            if not current_user.is_authenticated or render_record.user_id != current_user.id:
                return jsonify({"message": "Unauthorized"}), 403
        
        # Check if user can download (free tier cannot download) - skip in dev mode
        is_dev_mode = os.environ.get("MOTIVORA_DEV_MODE") == "1"
        if not is_dev_mode and current_user.is_authenticated and not user_can_download():
            return jsonify({
                "message": "Download requires Pro subscription. Upgrade to download watermark-free videos.",
                "upgrade_url": get_upgrade_url(),
            }), 403
        
        file_path = Path(render_record.file_path)
        
        # Security: Ensure file path is within storage directory
        try:
            file_path_resolved = file_path.resolve()
            storage_root_resolved = STORAGE_ROOT.resolve()
            if not str(file_path_resolved).startswith(str(storage_root_resolved)):
                return jsonify({"message": "Invalid file path"}), 403
        except (OSError, ValueError):
            return jsonify({"message": "Invalid file path"}), 403
        
        # Use try-except to handle race condition where file might be deleted
        try:
            if file_path.exists():
                return send_file(
                    file_path,
                    mimetype=render_record.mimetype,
                    as_attachment=True,
                    download_name=render_record.download_name,
                )
        except FileNotFoundError:
            pass
        return render_form(message="Rendered file could not be found.")
    
    # Fallback to active jobs for anonymous renders
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return render_form(message="Render job not found.")
    if job.get("state") != "finished":
        return render_form(message="Render is not finished yet.")
    
    # Check dev mode - allow all downloads in dev mode
    is_dev_mode = os.environ.get("MOTIVORA_DEV_MODE") == "1"
    
    # Anonymous users cannot download (preview only) - skip in dev mode
    if not is_dev_mode and not current_user.is_authenticated:
        return jsonify({
            "message": "Sign up to download videos. Free accounts get watermarked previews. Upgrade to Pro for downloads.",
            "upgrade_url": get_upgrade_url(),
        }), 403
    
    # Check if authenticated user can download - skip in dev mode
    if not is_dev_mode and not user_can_download():
        return jsonify({
            "message": "Download requires Pro subscription. Upgrade to download watermark-free videos.",
            "upgrade_url": get_upgrade_url(),
        }), 403

    output_path = Path(job["output_path"])
    workdir = Path(job["workdir"])
    
    # Handle race conditions (optimized)
    try:
        if not output_path.exists():
            job["cleanup_needed"] = True
            if workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)
            ACTIVE_JOBS.pop(job_id, None)
            return render_form(message="Rendered file could not be found.")

        response = send_file(
            output_path,
            mimetype=job.get("mimetype", "video/webm"),
            as_attachment=True,
            download_name=job.get("download_name", "turntable.webm"),
        )

        @after_this_request
        def cleanup(response):  # type: ignore[override]
            # Clean up after response is sent
            try:
                if workdir.exists():
                    shutil.rmtree(workdir, ignore_errors=True)
            except Exception:
                pass
            ACTIVE_JOBS.pop(job_id, None)
            return response

        return response
    except FileNotFoundError:
        ACTIVE_JOBS.pop(job_id, None)
        return render_form(message="Rendered file could not be found.")


# Authentication routes
@app.route("/auth/signup", methods=["GET", "POST"])
def auth_signup():
    """User signup."""
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template(
            "auth.html",
            mode="signup",
            current_year=datetime.now().year,
            OUTPUT_FORMAT=OUTPUT_FORMAT,
            google_oauth_enabled=GOOGLE_OAUTH_ENABLED,
        )
    
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    
    if not email or not name or not password:
        return jsonify({"message": "Email, name, and password are required."}), 400
    
    # Validate email format
    import re
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(email):
        return jsonify({"message": "Invalid email format."}), 400
    
    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters."}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered. Please log in."}), 400
    
    user = User(email=email, name=name, subscription_tier="free")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    login_user(user, remember=True)
    return jsonify({"message": "Account created successfully.", "redirect": url_for("dashboard")}), 200


@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    """User login."""
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template(
            "auth.html",
            mode="login",
            current_year=datetime.now().year,
            OUTPUT_FORMAT=OUTPUT_FORMAT,
            google_oauth_enabled=GOOGLE_OAUTH_ENABLED,
        )
    
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    
    if not email or not password:
        return jsonify({"message": "Email and password are required."}), 400
    
    # Validate email format
    if not EMAIL_PATTERN.match(email):
        return jsonify({"message": "Invalid email format."}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid email or password."}), 401
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    login_user(user, remember=True)
    return jsonify({"message": "Logged in successfully.", "redirect": url_for("dashboard")}), 200


@app.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    """User logout."""
    logout_user()
    return jsonify({"message": "Logged out successfully.", "redirect": url_for("render_page")}), 200


# Google OAuth routes
@app.route("/auth/google", methods=["GET"])
def auth_google():
    """Initiate Google OAuth login."""
    if not GOOGLE_OAUTH_ENABLED:
        return redirect(url_for("auth_login", error="google_disabled"))
    
    try:
        # Get redirect URI from request or use default
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")
        if not redirect_uri:
            # Build from request host
            if request.is_secure:
                scheme = "https"
            else:
                scheme = "http"
            redirect_uri = f"{scheme}://{request.host}/auth/google/callback"
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = redirect_uri
        
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        
        session["oauth_state"] = state
        return redirect(authorization_url)
    except Exception as e:
        print(f"[OAuth] Error initiating Google login: {e}", flush=True)
        return jsonify({"message": "Failed to initiate Google login."}), 500


@app.route("/auth/google/callback", methods=["GET"])
def auth_google_callback():
    """Handle Google OAuth callback."""
    if not GOOGLE_OAUTH_ENABLED:
        return redirect(url_for("auth_login"))
    
    error = request.args.get("error")
    if error:
        return redirect(url_for("auth_login", error=error))
    
    state = request.args.get("state")
    if not state or state != session.get("oauth_state"):
        session.pop("oauth_state", None)  # Clear invalid state
        return redirect(url_for("auth_login", error="invalid_state"))
    
    try:
        code = request.args.get("code")
        if not code:
            return redirect(url_for("auth_login", error="missing_code"))
        
        # Get redirect URI
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")
        if not redirect_uri:
            if request.is_secure:
                scheme = "https"
            else:
                scheme = "http"
            redirect_uri = f"{scheme}://{request.host}/auth/google/callback"
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = redirect_uri
        
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        idinfo = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        
        google_id = idinfo.get("sub")
        email = idinfo.get("email", "").strip().lower()
        name = idinfo.get("name", email.split("@")[0])
        picture = idinfo.get("picture")
        
        if not email:
            return redirect(url_for("auth_login", error="no_email"))
        
        # Find or create user
        user = User.query.filter((User.email == email) | (User.google_id == google_id)).first()
        
        if user:
            # Update existing user
            if not user.google_id:
                user.google_id = google_id
            if not user.name or user.name == user.email.split("@")[0]:
                user.name = name
            user.last_login = datetime.utcnow()
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                subscription_tier="free",
                last_login=datetime.utcnow(),
            )
            db.session.add(user)
        
        db.session.commit()
        login_user(user, remember=True)
        
        return redirect(url_for("dashboard"))
    except ValueError as e:
        print(f"[OAuth] Invalid token: {e}", flush=True)
        return redirect(url_for("auth_login", error="invalid_token"))
    except Exception as e:
        print(f"[OAuth] Error handling callback: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return redirect(url_for("auth_login", error="oauth_error"))


# Dashboard routes
@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """User dashboard with render history."""
    renders = Render.query.filter_by(user_id=current_user.id).order_by(Render.created_at.desc()).limit(50).all()
    
    stats = {
        "total_renders": current_user.renders.count(),
        "renders_this_month": current_user.render_count_this_month,
        "subscription_tier": get_user_tier(),
    }
    
    # Get upgrade URL for current tier
    upgrade_url = get_upgrade_url("pro") if stats["subscription_tier"] == "free" else get_upgrade_url("enterprise")
    
    return render_template(
        "dashboard.html",
        renders=renders,
        stats=stats,
        current_user=current_user,
        current_year=datetime.now().year,
        OUTPUT_FORMAT=OUTPUT_FORMAT,
        upgrade_url=upgrade_url,
    )


@app.route("/dashboard/render/<int:render_id>", methods=["GET"])
@login_required
def dashboard_render(render_id: int):
    """View/download a specific render from dashboard."""
    render_record = Render.query.get_or_404(render_id)
    
    if render_record.user_id != current_user.id:
        return jsonify({"message": "Unauthorized"}), 403
    
    # Check license for downloads
    if not user_can_download():
        return jsonify({
            "message": "Download requires Pro subscription. Upgrade to download watermark-free videos.",
            "upgrade_url": get_upgrade_url(),
        }), 403
    
    file_path = Path(render_record.file_path)
    if not file_path.exists():
        return jsonify({"message": "Render file not found."}), 404
    
    return send_file(
        file_path,
        mimetype=render_record.mimetype,
        as_attachment=True,
        download_name=render_record.download_name,
    )


# License management routes
@app.route("/api/license/check", methods=["GET"])
@login_required
def check_license():
    """Check user's license status."""
    license_key = get_user_license_key()
    
    if not license_key:
        return jsonify({
            "valid": False,
            "tier": "free",
            "message": "No license key found",
            "upgrade_url": get_upgrade_url(),
        }), 200
    
    result = license_checker.validate_license(license_key, current_user.email)
    result["upgrade_url"] = get_upgrade_url()
    
    return jsonify(result), 200


@app.route("/api/license/activate", methods=["POST"])
@login_required
def activate_license():
    """Activate a license key for the current user."""
    data = request.get_json()
    license_key = data.get("license_key", "").strip()
    
    if not license_key:
        return jsonify({"error": "License key is required"}), 400
    
    # Validate license
    result = license_checker.validate_license(license_key, current_user.email)
    
    if result.get("valid"):
        # Store license key in session
        session["license_key"] = license_key
        # Update subscription tier in database
        tier = result.get("tier", "free")
        current_user.subscription_tier = tier
        expires_at = result.get("expires_at")
        if expires_at:
            try:
                # Try ISO format first
                if "T" in expires_at or " " in expires_at:
                    current_user.subscription_expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                else:
                    current_user.subscription_expires_at = datetime.strptime(expires_at, "%Y-%m-%d")
            except Exception:
                pass
        db.session.commit()
        
        return jsonify({
            "message": "License activated successfully",
            "tier": tier,
        }), 200
    else:
        return jsonify({
            "error": result.get("message", "Invalid license key"),
        }), 400


@app.route("/webhooks/lemonsqueezy", methods=["POST"])
def lemonsqueezy_webhook():
    """
    Handle Lemon Squeezy webhook events for subscription updates.
    
    Events handled:
    - subscription_created: New subscription created
    - subscription_updated: Subscription updated (renewed, changed, etc.)
    - subscription_cancelled: Subscription cancelled
    - subscription_expired: Subscription expired
    """
    try:
        # Verify webhook signature (optional but recommended)
        # Lemon Squeezy sends a signature header you can verify
        signature = request.headers.get("X-Signature")
        webhook_secret = os.environ.get("LEMON_SQUEEZY_WEBHOOK_SECRET")
        
        # Get webhook data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        event_name = data.get("meta", {}).get("event_name")
        event_data = data.get("data", {})
        attributes = event_data.get("attributes", {})
        
        # Get customer email from subscription
        customer_email = attributes.get("user_email")
        if not customer_email:
            # Try to get from customer relationship
            customer_id = event_data.get("relationships", {}).get("customer", {}).get("data", {}).get("id")
            if customer_id:
                # Fetch customer details from Lemon Squeezy API
                api_key = os.environ.get("LEMON_SQUEEZY_API_KEY")
                if api_key:
                    import requests
                    response = requests.get(
                        f"https://api.lemonsqueezy.com/v1/customers/{customer_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        customer_data = response.json().get("data", {})
                        customer_email = customer_data.get("attributes", {}).get("email")
        
        if not customer_email:
            print(f"[Webhook] No email found for event: {event_name}", flush=True)
            return jsonify({"error": "No customer email found"}), 400
        
        # Find user by email
        user = User.query.filter_by(email=customer_email).first()
        if not user:
            print(f"[Webhook] User not found for email: {customer_email}", flush=True)
            return jsonify({"error": "User not found"}), 404
        
        # Get variant ID to determine tier
        variant_id = attributes.get("variant_id")
        variant_id_pro = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_PRO")
        variant_id_enterprise = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE")
        
        # Determine tier from variant ID
        if variant_id == variant_id_pro:
            tier = "pro"
        elif variant_id == variant_id_enterprise:
            tier = "enterprise"
        else:
            tier = "free"
        
        # Handle different events
        if event_name in ("subscription_created", "subscription_updated", "subscription_renewed"):
            # Active subscription
            user.subscription_tier = tier
            # Get subscription end date
            ends_at = attributes.get("ends_at")
            if ends_at:
                try:
                    # Try ISO format first
                    if "T" in ends_at or " " in ends_at:
                        user.subscription_expires_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                    else:
                        user.subscription_expires_at = datetime.strptime(ends_at, "%Y-%m-%d")
                except Exception:
                    pass
            db.session.commit()
            print(f"[Webhook] Updated user {user.email} to tier: {tier}", flush=True)
            
        elif event_name in ("subscription_cancelled", "subscription_expired", "subscription_payment_failed"):
            # Subscription cancelled or expired - downgrade to free
            user.subscription_tier = "free"
            user.subscription_expires_at = None
            db.session.commit()
            print(f"[Webhook] Downgraded user {user.email} to free tier", flush=True)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"[Webhook] Error processing webhook: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 8888))
    app.run(host="0.0.0.0", port=port, debug=False)

