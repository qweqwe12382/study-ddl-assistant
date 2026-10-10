"""Build the narrated review video from verified screenshots and local TTS WAVs.

Optional media tooling: Pillow and FFmpeg. Pass --ffmpeg /path/to/ffmpeg.
Input speech segments are .tmp/submission-build/audio/01.wav through 12.wav.
Scene text and screenshot names live in docs/submission/video-scenes.json.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/submission'
BUILD = ROOT / '.tmp/submission-build'


def seconds(path: Path) -> float:
    with wave.open(str(path)) as wav:
        return wav.getnframes() / wav.getframerate()


def stamp(value: float) -> str:
    milliseconds = round(value * 1000)
    return f'{milliseconds // 3600000:02}:{milliseconds // 60000 % 60:02}:{milliseconds // 1000 % 60:02},{milliseconds % 1000:03}'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--font', default='C:/Windows/Fonts/msyh.ttc')
    args = parser.parse_args()
    scenes = json.loads((OUT / 'video-scenes.json').read_text('utf-8'))
    sources = [BUILD / f'audio/{i:02}.wav' for i in range(1, len(scenes) + 1)]
    raw_total = sum(seconds(p) for p in sources)
    speed = max(1.0, raw_total / (270 - len(scenes) * 0.6))
    frames = BUILD / 'frames'
    frames.mkdir(exist_ok=True)
    fonts = {size: ImageFont.truetype(args.font, size) for size in [22, 29, 34, 50]}
    concat, audio_concat, subtitles, chapters = [], [], [], []
    cursor = 0.0

    def run(arguments):
        subprocess.run([args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *arguments], check=True)

    for index, (scene, source) in enumerate(zip(scenes, sources), 1):
        audio_path = BUILD / f'audio/processed-{index:02}.wav'
        run(['-i', str(source), '-af', f'atempo={speed:.7f},loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur=0.6',
             '-ar', '48000', '-ac', '1', str(audio_path)])
        duration = seconds(audio_path)
        audio_concat.append(f"file '{audio_path.as_posix()}'")
        image = Image.new('RGB', (1920, 1080), '#eef2eb')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1920, 140), fill='#163f34')
        draw.text((68, 25), scene['title'], font=fonts[50], fill='white')
        draw.text((70, 94), scene['subtitle'], font=fonts[29], fill='#d7e6d8')
        draw.text((1600, 57), f'{index:02} / {len(scenes):02}', font=fonts[34], fill='#efd196')
        shot = Image.open(OUT / 'assets' / scene['image']).convert('RGB')
        shot.thumbnail((1760, 748), Image.Resampling.LANCZOS)
        x = (1920 - shot.width) // 2
        y = 166 + (748 - shot.height) // 2
        draw.rounded_rectangle((x-9,y-9,x+shot.width+9,y+shot.height+9),radius=12,fill='#c7d5cb')
        image.paste(shot, (x, y))
        draw.text((66, 1034), '学伴管家  |  真实界面关键画面演示  |  合成数据与本地 TTS 配音',font=fonts[22], fill='#597265')
        # Phrase-level subtitle timing is estimated proportionally to text length.
        # It is not a forced-alignment transcript.
        phrases = [p.strip() for p in re.split(r'(?<=[。！？；，])', scene['voice']) if p.strip()]
        chunks = []
        for phrase in phrases:
            if chunks and len(chunks[-1]) + len(phrase) <= 36:
                chunks[-1] += phrase
            else:
                chunks.append(phrase)
        weights = sum(len(chunk) for chunk in chunks)
        local_cursor = 0.0
        for part, caption in enumerate(chunks):
            length = duration * len(caption) / weights
            frame = image.copy()
            painter = ImageDraw.Draw(frame)
            painter.rounded_rectangle((48, 938, 1872, 1015), radius=15, fill='#163f34')
            bounds = painter.textbbox((0, 0), caption, font=fonts[34])
            painter.text(((1920-(bounds[2]-bounds[0]))/2, 952), caption, font=fonts[34], fill='white')
            destination = frames / f'{index:02}-{part:02}.png'
            frame.save(destination)
            concat.extend([f"file '{destination.as_posix()}'", f'duration {length:.7f}'])
            subtitles.append(f'{len(subtitles)+1}\n{stamp(cursor+local_cursor)} --> {stamp(cursor+local_cursor+length)}\n{caption}\n')
            local_cursor += length
        chapters.append({'scene': index, 'start_seconds': cursor, 'duration_seconds': duration, 'title': scene['title']})
        cursor += duration
    concat.append(concat[-2])
    (BUILD/'video-concat.txt').write_text('\n'.join(concat), 'utf-8')
    (BUILD/'audio-concat.txt').write_text('\n'.join(audio_concat), 'utf-8')
    narration = OUT/'学伴管家-旁白.mp3'
    run(['-f','concat','-safe','0','-i',str(BUILD/'audio-concat.txt'),'-c:a','libmp3lame','-b:a','160k',str(narration)])
    movie = OUT/'学伴管家-介绍与演示.mp4'
    run(['-f','concat','-safe','0','-i',str(BUILD/'video-concat.txt'),'-i',str(narration),
         '-t',str(cursor),'-r','24','-c:v','libx264','-preset','medium','-crf','23',
         '-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(movie)])
    (OUT/'学伴管家-介绍与演示.srt').write_text('\n'.join(subtitles), 'utf-8')
    metadata={'seconds':cursor,'resolution':'1920x1080','fps':24,'speech_speed_factor':speed,
              'tts':'Local Qwen3-TTS-12Hz-0.6B-CustomVoice / Vivian',
              'subtitle_timing':'phrase timing estimated from text length', 'chapters':chapters}
    (OUT/'video-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf-8')
    assert 180 <= cursor <= 300, f'Competition duration out of range: {cursor}'
    print(f'Created {movie}: {cursor:.2f}s, {movie.stat().st_size/1024**2:.1f} MiB')


if __name__ == '__main__':
    main()
