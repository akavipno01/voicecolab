from __future__ import annotations

import asyncio
import os
import random
import subprocess
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import APP_NAME, OUTPUTS_DIR, TEMP_DIR, VOICES_DIR, ensure_directories
from .database import db, initialize_database
from .model_runtime import (
    get_model,
    inference_executor,
    remove_model,
    runtime_state,
    start_model_download,
    _update_state,
)


ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".webm"}
MAX_REFERENCE_BYTES = 50 * 1024 * 1024


whisper_model = None
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "turbo")
transcription_tasks = {}

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    initialize_database()
    global whisper_model
    try:
        from faster_whisper import WhisperModel
        print(f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}'...")
        whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cuda", compute_type="float16")
        print("Whisper model loaded successfully on CUDA!")
    except Exception as e:
        print(f"Failed to load Whisper on CUDA: {e}. Falling back to CPU...")
        from faster_whisper import WhisperModel
        whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        print("Whisper model loaded successfully on CPU!")
    yield


app = FastAPI(title=APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Audio-Id", "X-Seed", "X-Generation-Time", "X-Audio-Duration", "X-Audio-Format", "X-Audio-Srt"],
)


class ProfilePatch(BaseModel):
    name: str | None = None
    ref_text: str | None = None
    language: str | None = None
    notes: str | None = None


class AppSettingsPatch(BaseModel):
    audio_format: str
    download_directory: str = ""


def _row(row):
    return dict(row) if row else None


def _safe_child(directory: Path, filename: str) -> Path | None:
    if not filename or Path(filename).name != filename:
        return None
    candidate = (directory / filename).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        return None
    return candidate


async def _store_upload(upload: UploadFile, destination: Path) -> None:
    total = 0
    with destination.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_REFERENCE_BYTES:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Audio tham chiếu không được vượt quá 50 MB.")
            handle.write(chunk)


def _validate_upload(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Hãy sử dụng audio WAV, MP3, FLAC, M4A, OGG hoặc WebM.",
        )
    return extension


@app.get("/health")
def health():
    return {"ok": True, "name": APP_NAME, "runtime": runtime_state()}


@app.get("/runtime")
def model_status():
    return runtime_state()


@app.post("/model/download", status_code=202)
def download_model():
    return start_model_download()


@app.delete("/model")
def delete_model():
    try:
        return remove_model()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/profiles")
def list_profiles():
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM voice_profiles ORDER BY created_at DESC"
        ).fetchall()
    return [_row(row) for row in rows]


@app.get("/settings")
def get_settings():
    defaults = {"audio_format": "wav", "download_directory": ""}
    with db() as connection:
        rows = connection.execute("SELECT key, value FROM app_settings").fetchall()
    defaults.update({row["key"]: row["value"] for row in rows})
    return defaults


@app.put("/settings")
def update_settings(patch: AppSettingsPatch):
    audio_format = patch.audio_format.lower().strip()
    if audio_format not in {"wav", "mp3", "flac"}:
        raise HTTPException(status_code=422, detail="Định dạng audio không hợp lệ.")
    values = {
        "audio_format": audio_format,
        "download_directory": patch.download_directory.strip(),
    }
    now = time.time()
    with db() as connection:
        for key, value in values.items():
            connection.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, now),
            )
    return values


@app.post("/profiles", status_code=201)
async def create_profile(
    name: Annotated[str, Form()],
    consent_confirmed: Annotated[bool, Form()],
    ref_audio: Annotated[UploadFile, File()],
    ref_text: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "Auto",
    notes: Annotated[str, Form()] = "",
):
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="Bạn cần nhập tên hồ sơ giọng.")
    if not consent_confirmed:
        raise HTTPException(status_code=422, detail="Bạn cần xác nhận có quyền sử dụng giọng nói này.")
    extension = _validate_upload(ref_audio)
    profile_id = uuid.uuid4().hex[:12]
    filename = f"{profile_id}{extension}"
    destination = VOICES_DIR / filename
    await _store_upload(ref_audio, destination)
    now = time.time()
    try:
        with db() as connection:
            connection.execute(
                """
                INSERT INTO voice_profiles
                (id, name, ref_audio_path, ref_text, language, notes,
                 consent_confirmed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (profile_id, clean_name, filename, ref_text.strip(), language, notes.strip(), now, now),
            )
            row = connection.execute(
                "SELECT * FROM voice_profiles WHERE id=?", (profile_id,)
            ).fetchone()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return _row(row)


@app.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, patch: ProfilePatch):
    values = patch.model_dump(exclude_none=True)
    allowed = {"name", "ref_text", "language", "notes"}
    values = {key: value.strip() for key, value in values.items() if key in allowed}
    if "name" in values and not values["name"]:
        raise HTTPException(status_code=422, detail="Tên hồ sơ giọng không được để trống.")
    if not values:
        raise HTTPException(status_code=422, detail="Không có nội dung nào cần cập nhật.")
    values["updated_at"] = time.time()
    assignments = ", ".join(f"{key}=?" for key in values)
    with db() as connection:
        cursor = connection.execute(
            f"UPDATE voice_profiles SET {assignments} WHERE id=?",
            (*values.values(), profile_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giọng.")
        row = connection.execute(
            "SELECT * FROM voice_profiles WHERE id=?", (profile_id,)
        ).fetchone()
    return _row(row)


@app.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str):
    with db() as connection:
        row = connection.execute(
            "SELECT ref_audio_path, is_system FROM voice_profiles WHERE id=?", (profile_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giọng.")
        if row["is_system"] == 1:
            raise HTTPException(status_code=403, detail="Không thể xóa giọng nói hệ thống.")
        connection.execute("DELETE FROM voice_profiles WHERE id=?", (profile_id,))
    path = _safe_child(VOICES_DIR, row["ref_audio_path"])
    if path:
        path.unlink(missing_ok=True)


@app.get("/profiles/{profile_id}/audio")
def profile_audio(profile_id: str):
    with db() as connection:
        row = connection.execute(
            "SELECT ref_audio_path FROM voice_profiles WHERE id=?", (profile_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giọng.")
    path = _safe_child(VOICES_DIR, row["ref_audio_path"])
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy audio tham chiếu.")
    return FileResponse(path)


def _run_generation(model, *, text: str, language: str | None, ref_audio: str,
                    ref_text: str | None, speed: float, num_step: int,
                    guidance_scale: float, seed: int, denoise: bool,
                    postprocess_output: bool):
    import torch

    torch.manual_seed(seed)
    generated = model.generate(
        text=text,
        language=language,
        ref_audio=ref_audio,
        ref_text=ref_text or None,
        num_step=num_step,
        guidance_scale=guidance_scale,
        speed=speed,
        denoise=denoise,
        postprocess_output=postprocess_output,
    )
    return generated[0], int(getattr(model, "sampling_rate", 24000))


def _generate_srt(text: str, total_duration: float) -> str:
    import re
    clean_txt = text.strip()
    if not clean_txt:
        return ""
    
    raw_sentences = re.split(r'([.?!。？！\n]+)', clean_txt)
    
    sentences = []
    current = ""
    for part in raw_sentences:
        if not part:
            continue
        if re.match(r'^[.?!。？！\n]+$', part):
            current += part
            sentences.append(current.strip())
            current = ""
        else:
            if current:
                sentences.append(current.strip())
            current = part
    if current:
        sentences.append(current.strip())
        
    sentences = [s for s in sentences if s]
    
    final_segments = []
    for s in sentences:
        if len(s) > 80:
            parts = re.split(r'([,;:\-，、；：]+)', s)
            curr_seg = ""
            for p in parts:
                if not p:
                    continue
                if re.match(r'^[,;:\-，、；：]+$', p):
                    curr_seg += p
                    final_segments.append(curr_seg.strip())
                    curr_seg = ""
                else:
                    if curr_seg:
                        final_segments.append(curr_seg.strip())
                    curr_seg = p
            if curr_seg:
                final_segments.append(curr_seg.strip())
        else:
            final_segments.append(s)
            
    final_segments = [s for s in final_segments if s]
    
    if not final_segments:
        final_segments = [clean_txt]
        
    char_counts = [len(s) for s in final_segments]
    total_chars = sum(char_counts)
    
    if total_chars == 0:
        return ""
        
    srt_lines = []
    current_time = 0.0
    
    for i, seg in enumerate(final_segments):
        ratio = char_counts[i] / total_chars
        duration = ratio * total_duration
        start_time = current_time
        end_time = current_time + duration
        current_time = end_time
        
        def format_timestamp(t: float) -> str:
            hours = int(t // 3600)
            minutes = int((t % 3600) // 60)
            seconds = int(t % 60)
            milliseconds = int(round((t % 1) * 1000))
            if milliseconds == 1000:
                seconds += 1
                milliseconds = 0
            return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
            
        srt_lines.append(str(i + 1))
        srt_lines.append(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}")
        srt_lines.append(seg)
        srt_lines.append("")
        
    return "\n".join(srt_lines)


OUTPUT_FORMATS = {
    "wav": {"extension": "wav", "media_type": "audio/wav"},
    "flac": {"extension": "flac", "media_type": "audio/flac"},
    "mp3": {"extension": "mp3", "media_type": "audio/mpeg"},
}


def _write_output_audio(
    output_path: Path,
    audio_array,
    sample_rate: int,
    output_format: str,
) -> None:
    import soundfile as sf

    if output_format == "wav":
        sf.write(str(output_path), audio_array, sample_rate, format="WAV")
        return
    if output_format == "flac":
        sf.write(str(output_path), audio_array, sample_rate, format="FLAC")
        return

    temporary_wav = TEMP_DIR / f"{uuid.uuid4().hex}.wav"
    try:
        sf.write(str(temporary_wav), audio_array, sample_rate, format="WAV")
        import imageio_ffmpeg

        completed = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-v", "error",
                "-i", str(temporary_wav),
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(
                completed.stderr.decode("utf-8", errors="replace")
                or "FFmpeg không tạo được tệp MP3."
            )
    finally:
        temporary_wav.unlink(missing_ok=True)


def _split_text_by_sentences(text: str, max_chars: int = 1500) -> list[str]:
    import re
    # Split text by sentence endings (. ! ? \n)
    raw_sentences = re.split(r'([.?!。？！\n]+)', text)
    
    chunks = []
    current_chunk = ""
    
    i = 0
    while i < len(raw_sentences):
        sentence = raw_sentences[i]
        punctuation = raw_sentences[i+1] if i + 1 < len(raw_sentences) else ""
        i += 2
        
        full_sentence = (sentence + punctuation).strip()
        if not full_sentence:
            continue
            
        if len(current_chunk) + len(full_sentence) + 1 <= max_chars:
            if current_chunk:
                current_chunk += " " + full_sentence
            else:
                current_chunk = full_sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            # If the single sentence is longer than max_chars, we must force-split it
            if len(full_sentence) > max_chars:
                subparts = re.split(r'([,;，、\s]+)', full_sentence)
                curr_sub = ""
                for sp in subparts:
                    if len(curr_sub) + len(sp) <= max_chars:
                        curr_sub += sp
                    else:
                        if curr_sub.strip():
                            chunks.append(curr_sub.strip())
                        curr_sub = sp
                if curr_sub.strip():
                    current_chunk = curr_sub
                else:
                    current_chunk = ""
            else:
                current_chunk = full_sentence
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks


def _parse_srt(srt_content: str) -> list[dict]:
    import re
    blocks = re.split(r'\n\s*\n', srt_content.replace('\r\n', '\n').strip())
    segments = []
    
    def time_to_seconds(t_str: str) -> float:
        parts = re.split(r'[:,\.]', t_str.strip())
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        # Find the line containing "-->"
        time_line = None
        time_line_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_line = line
                time_line_idx = idx
                break
                
        if time_line and time_line_idx >= 0:
            time_match = re.search(r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3})', time_line)
            if time_match:
                start_t = time_to_seconds(time_match.group(1))
                end_t = time_to_seconds(time_match.group(2))
                text_content = " ".join(lines[time_line_idx + 1:])
                segments.append({
                    "start": start_t,
                    "end": end_t,
                    "text": text_content
                })
    return sorted(segments, key=lambda x: x["start"])


@app.post("/generate")
async def generate(
    text: Annotated[str, Form()] = "",
    profile_id: Annotated[str | None, Form()] = None,
    ref_audio: Annotated[UploadFile | None, File()] = None,
    ref_text: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "Auto",
    speed: Annotated[float, Form(ge=0.6, le=1.5)] = 1.0,
    num_step: Annotated[int, Form(ge=4, le=64)] = 16,
    guidance_scale: Annotated[float, Form(ge=0.5, le=5.0)] = 2.0,
    seed: Annotated[int | None, Form(ge=0, le=2147483647)] = None,
    denoise: Annotated[bool, Form()] = True,
    postprocess_output: Annotated[bool, Form()] = True,
    output_format: Annotated[str, Form()] = "wav",
    srt_file: Annotated[UploadFile | None, File()] = None,
):
    clean_text = text.strip()
    srt_segments = []
    srt_content = ""
    
    if srt_file:
        srt_bytes = await srt_file.read()
        srt_content = srt_bytes.decode("utf-8", errors="ignore")
        srt_segments = _parse_srt(srt_content)
        if not srt_segments:
            raise HTTPException(status_code=422, detail="File SRT không hợp lệ hoặc rỗng.")
        if not clean_text:
            clean_text = " ".join([seg["text"] for seg in srt_segments])
    else:
        if not clean_text:
            raise HTTPException(status_code=422, detail="Hãy nhập nội dung hoặc tải lên file SRT.")
            
    if len(clean_text) > 100000:
        raise HTTPException(status_code=422, detail="Mỗi lần tạo được giới hạn tối đa 100.000 ký tự (khoảng 2 giờ âm thanh).")
        
    if not srt_file:
        chunks = _split_text_by_sentences(clean_text, max_chars=1500)
        if not chunks:
            raise HTTPException(status_code=422, detail="Nội dung nhập vào không hợp lệ.")

    output_format = output_format.lower().strip()
    if output_format not in OUTPUT_FORMATS:
        raise HTTPException(status_code=422, detail="Định dạng audio không hợp lệ.")

    temporary_reference: Path | None = None
    resolved_profile_id = None
    profile_name = "Giọng tạm thời"
    reference_path: Path | None = None

    if profile_id:
        with db() as connection:
            profile = connection.execute(
                "SELECT * FROM voice_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        if not profile:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giọng.")
        reference_path = _safe_child(VOICES_DIR, profile["ref_audio_path"])
        resolved_profile_id = profile_id
        profile_name = profile["name"]
        ref_text = ref_text.strip() or profile["ref_text"]
        if language == "Auto" and profile["language"] != "Auto":
            language = profile["language"]
    elif ref_audio:
        extension = _validate_upload(ref_audio)
        temporary_reference = TEMP_DIR / f"{uuid.uuid4().hex}{extension}"
        await _store_upload(ref_audio, temporary_reference)
        reference_path = temporary_reference
    else:
        raise HTTPException(status_code=422, detail="Hãy chọn một giọng đã lưu hoặc thêm audio tham chiếu.")

    if not reference_path or not reference_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy audio tham chiếu.")

    used_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    started = time.perf_counter()
    try:
        model = await get_model()
        loop = asyncio.get_running_loop()
        import torch
        sample_rate = 24000
        
        if srt_segments:
            total_segments = len(srt_segments)
            _update_state(
                status="generating",
                progress=0.0,
                detail=f"Đang chuẩn bị tạo giọng cho {total_segments} phụ đề SRT...",
            )
            
            # Find total duration and allocate empty full waveform
            total_duration = srt_segments[-1]["end"]
            total_samples = int(total_duration * sample_rate)
            waveform = torch.zeros((1, total_samples), dtype=torch.float32)
            
            for idx, seg in enumerate(srt_segments):
                seg_text = seg["text"].strip()
                if not seg_text:
                    continue
                    
                progress_pct = round((idx / total_segments) * 100, 1)
                _update_state(
                    status="generating",
                    progress=progress_pct,
                    detail=f"Đang xử lý phụ đề {idx + 1}/{total_segments} ({progress_pct}%)",
                )
                
                seg_waveform, sr = await loop.run_in_executor(
                    inference_executor(),
                    lambda s_text=seg_text: _run_generation(
                        model,
                        text=s_text,
                        language=None if language == "Auto" else language,
                        ref_audio=str(reference_path),
                        ref_text=ref_text.strip() or None,
                        speed=speed,
                        num_step=num_step,
                        guidance_scale=guidance_scale,
                        seed=used_seed,
                        denoise=denoise,
                        postprocess_output=postprocess_output,
                    ),
                )
                sample_rate = sr
                if seg_waveform.ndim == 1:
                    seg_waveform = seg_waveform.unsqueeze(0)
                seg_waveform = seg_waveform.detach().cpu().float()
                
                start_sample = int(seg["start"] * sample_rate)
                end_sample = int(seg["end"] * sample_rate)
                target_samples = end_sample - start_sample
                gen_samples = seg_waveform.shape[-1]
                
                if target_samples <= 0:
                    continue
                    
                if start_sample >= total_samples:
                    continue
                if end_sample > total_samples:
                    end_sample = total_samples
                    target_samples = end_sample - start_sample
                    
                if gen_samples > target_samples:
                    # Resample to fit target window
                    stretched = torch.nn.functional.interpolate(
                        seg_waveform.unsqueeze(0),
                        size=target_samples,
                        mode='linear',
                        align_corners=False
                    ).squeeze(0)
                    waveform[:, start_sample:end_sample] = stretched
                else:
                    # Place at the start of the window
                    waveform[:, start_sample:start_sample+gen_samples] = seg_waveform
            
            _update_state(
                status="ready",
                progress=100.0,
                detail="Mô hình đã sẵn sàng.",
            )
        else:
            waveforms = []
            total_chunks = len(chunks)
            _update_state(
                status="generating",
                progress=0.0,
                detail=f"Đang chuẩn bị tạo âm thanh cho {total_chunks} đoạn văn...",
            )
            
            for idx, chunk_text in enumerate(chunks):
                progress_pct = round((idx / total_chunks) * 100, 1)
                _update_state(
                    status="generating",
                    progress=progress_pct,
                    detail=f"Đang xử lý đoạn {idx + 1}/{total_chunks} ({progress_pct}%)",
                )
                
                chunk_waveform, sr = await loop.run_in_executor(
                    inference_executor(),
                    lambda c_text=chunk_text: _run_generation(
                        model,
                        text=c_text,
                        language=None if language == "Auto" else language,
                        ref_audio=str(reference_path),
                        ref_text=ref_text.strip() or None,
                        speed=speed,
                        num_step=num_step,
                        guidance_scale=guidance_scale,
                        seed=used_seed,
                        denoise=denoise,
                        postprocess_output=postprocess_output,
                    ),
                )
                sample_rate = sr
                if chunk_waveform.ndim == 1:
                    chunk_waveform = chunk_waveform.unsqueeze(0)
                chunk_waveform = chunk_waveform.detach().cpu().float()
                waveforms.append(chunk_waveform)
                
            if not waveforms:
                raise HTTPException(status_code=500, detail="Không tạo được âm thanh.")
                
            _update_state(
                status="ready",
                progress=100.0,
                detail="Mô hình đã sẵn sàng.",
            )
            
            waveform = torch.cat(waveforms, dim=-1)
            
        generation_time = round(time.perf_counter() - started, 2)
        audio_id = uuid.uuid4().hex[:12]
        format_info = OUTPUT_FORMATS[output_format]
        filename = f"{audio_id}.{format_info['extension']}"
        output_path = OUTPUTS_DIR / filename
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        waveform = waveform.detach().cpu().float()
        audio_array = waveform.numpy()
        if audio_array.ndim == 2:
            audio_array = audio_array.T
        _write_output_audio(
            output_path,
            audio_array,
            sample_rate,
            output_format,
        )
        duration = round(waveform.shape[-1] / sample_rate, 2)
        now = time.time()
        with db() as connection:
            connection.execute(
                """
                INSERT INTO generations
                (id, profile_id, profile_name, text, language, audio_path,
                 output_format, duration_seconds, generation_time, seed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audio_id, resolved_profile_id, profile_name, clean_text,
                    language, filename, output_format, duration, generation_time,
                    used_seed, now,
                ),
            )
        import base64
        if not srt_file:
            srt_content = _generate_srt(clean_text, duration)
        srt_base64 = base64.b64encode(srt_content.encode("utf-8")).decode("ascii")

        return FileResponse(
            output_path,
            media_type=format_info["media_type"],
            headers={
                "X-Audio-Id": audio_id,
                "X-Seed": str(used_seed),
                "X-Generation-Time": str(generation_time),
                "X-Audio-Duration": str(duration),
                "X-Audio-Format": output_format,
                "X-Audio-Srt": srt_base64,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        if "TorchCodec is required" in str(exc) or "load_with_torchcodec" in str(exc):
            detail = (
                "Không thể đọc audio tham chiếu bằng phiên bản dịch vụ cũ. "
                "Hãy đóng hoàn toàn Voice Clone, chạy lại setup.ps1 rồi mở ứng dụng."
            )
        else:
            detail = f"Không thể tạo giọng nói: {exc}"
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        if temporary_reference:
            with suppress(OSError):
                temporary_reference.unlink()


@app.get("/history")
def history():
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM generations ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return [_row(row) for row in rows]


@app.get("/history/{audio_id}/audio")
def history_audio(audio_id: str):
    with db() as connection:
        row = connection.execute(
            "SELECT audio_path, output_format FROM generations WHERE id=?", (audio_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả tạo giọng.")
    path = _safe_child(OUTPUTS_DIR, row["audio_path"])
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp audio đã tạo.")
    output_format = (row["output_format"] or path.suffix.lstrip(".") or "wav").lower()
    format_info = OUTPUT_FORMATS.get(output_format, OUTPUT_FORMATS["wav"])
    return FileResponse(
        path,
        media_type=format_info["media_type"],
        filename=f"voice-clone-{audio_id}.{format_info['extension']}",
    )


@app.delete("/history/{audio_id}", status_code=204)
def delete_history(audio_id: str):
    with db() as connection:
        row = connection.execute(
            "SELECT audio_path FROM generations WHERE id=?", (audio_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy kết quả tạo giọng.")
        connection.execute("DELETE FROM generations WHERE id=?", (audio_id,))
    path = _safe_child(OUTPUTS_DIR, row["audio_path"])
    if path:
        path.unlink(missing_ok=True)


def _extract_pdf_text(file_bytes: bytes) -> list[dict]:
    import io
    from pypdf import PdfReader
    
    pages_data = []
    reader = PdfReader(io.BytesIO(file_bytes))
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_data.append({
            "id": i + 1,
            "title": f"Trang {i + 1}",
            "text": text.strip()
        })
    return pages_data


def _extract_epub_text(file_bytes: bytes) -> list[dict]:
    import io
    import tempfile
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    
    chapters_data = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(file_bytes)
        temp_file_path = temp_file.name
        
    try:
        # Ignore EbookLib warnings about duplicate files, metadata etc.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            book = epub.read_epub(temp_file_path)
            
        item_id = 1
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content()
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Check for headings to make chapter titles
                title = ""
                heading = soup.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = heading.get_text().strip()
                
                text = soup.get_text()
                # Clean up text lines
                lines = [line.strip() for line in text.splitlines()]
                clean_text = "\n".join([line for line in lines if line])
                
                if clean_text.strip():
                    if not title:
                        title = f"Chương {item_id}"
                    chapters_data.append({
                        "id": item_id,
                        "title": title,
                        "text": clean_text.strip()
                    })
                    item_id += 1
    finally:
        try:
            import os
            os.unlink(temp_file_path)
        except Exception:
            pass
            
    return chapters_data


@app.post("/extract-document")
async def extract_document(file: UploadFile = File(...)):
    filename = file.filename or ""
    file_bytes = await file.read()
    
    if filename.lower().endswith(".pdf"):
        try:
            items = _extract_pdf_text(file_bytes)
            title = filename.rsplit(".", 1)[0]
            return {
                "title": title,
                "type": "pdf",
                "items": items
            }
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Lỗi đọc tài liệu PDF: {str(e)}")
            
    elif filename.lower().endswith(".epub"):
        try:
            items = _extract_epub_text(file_bytes)
            title = filename.rsplit(".", 1)[0]
            return {
                "title": title,
                "type": "epub",
                "items": items
            }
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Lỗi đọc tài liệu EPUB: {str(e)}")
            
    else:
        raise HTTPException(status_code=422, detail="Chỉ hỗ trợ tài liệu định dạng PDF hoặc EPUB.")


class TranscribeResponse(BaseModel):
    task_id: str
    message: str


class TaskStatusResponse(BaseModel):
    status: str
    srt: str | None = None
    srt_file: str | None = None
    language: str | None = None
    error: str | None = None


def format_timestamp(seconds: float) -> str:
    import datetime
    td = datetime.timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds_int = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"


def process_transcription(task_id: str, temp_path: str, filename: str):
    try:
        transcription_tasks[task_id]["status"] = "processing"
        print(f"Task {task_id}: Transcribing {filename}...")
        
        segments, info = whisper_model.transcribe(temp_path, beam_size=5)
        
        srt_content = ""
        for i, segment in enumerate(segments, start=1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            text = segment.text.strip()
            
            srt_content += f"{i}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
            
        import os
        base_name = os.path.splitext(filename)[0]
        srt_filename = f"{base_name}_{task_id}.srt"
        srt_path = OUTPUTS_DIR / srt_filename
        
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        transcription_tasks[task_id]["status"] = "completed"
        transcription_tasks[task_id]["srt"] = srt_content
        transcription_tasks[task_id]["srt_file"] = str(srt_path)
        transcription_tasks[task_id]["language"] = info.language
        print(f"Task {task_id}: Completed. SRT saved to {srt_path}")
        
    except Exception as e:
        print(f"Task {task_id}: Error - {e}")
        transcription_tasks[task_id]["status"] = "error"
        transcription_tasks[task_id]["error"] = str(e)
    finally:
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    import uuid
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    ext = Path(file.filename).suffix.lower()
    
    temp_file = TEMP_DIR / f"{uuid.uuid4().hex}{ext}"
    content = await file.read()
    with open(temp_file, "wb") as f:
        f.write(content)
    
    task_id = uuid.uuid4().hex
    transcription_tasks[task_id] = {
        "status": "queued",
        "srt": None,
        "srt_file": None,
        "language": None,
        "error": None
    }
    
    background_tasks.add_task(process_transcription, task_id, str(temp_file), file.filename)
    
    return TranscribeResponse(
        task_id=task_id, 
        message="Transcription task queued. Check status using /status/{task_id}"
    )


@app.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_status(task_id: str):
    if task_id not in transcription_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatusResponse(
        status=transcription_tasks[task_id]["status"],
        srt=transcription_tasks[task_id]["srt"],
        srt_file=transcription_tasks[task_id]["srt_file"],
        language=transcription_tasks[task_id]["language"],
        error=transcription_tasks[task_id]["error"]
    )


@app.get("/download/{task_id}")
def download_srt(task_id: str):
    import os
    if task_id not in transcription_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    srt_file = transcription_tasks[task_id].get("srt_file")
    if not srt_file or not os.path.exists(srt_file):
        raise HTTPException(status_code=404, detail="SRT file not available")
        
    return FileResponse(srt_file, media_type='text/plain', filename=os.path.basename(srt_file))
