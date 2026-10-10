import os, json, time, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HOME'] = str(ROOT / '.tmp/tts-cache')
os.environ['TORCH_HOME'] = str(ROOT / '.tmp/tts-cache')
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel
torch.set_num_threads(6)
torch.manual_seed(42)
out = ROOT / '.tmp/submission-build/audio'
out.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description='Run in a local Qwen3-TTS environment; model weights are not bundled.')
parser.add_argument('--model', required=True)
args = parser.parse_args()
model = Qwen3TTSModel.from_pretrained(args.model, device_map='cuda:0', dtype=torch.bfloat16, attn_implementation='sdpa', local_files_only=True)
print('Loaded local model; speakers:', model.get_supported_speakers(), flush=True)
scenes = json.loads((ROOT/'docs/submission/video-scenes.json').read_text('utf-8'))
for i, scene in enumerate(scenes, 1):
    target = out / f'{i:02}.wav'
    if target.exists():
        print('Reusing',target.name,flush=True)
        continue
    start=time.time()
    wavs, rate=model.generate_custom_voice(text=scene['voice'], language='Chinese', speaker='Vivian', max_new_tokens=1800, do_sample=True, temperature=0.65, top_p=0.9)
    sf.write(str(target),wavs[0],rate)
    print(f'{i:02} duration={len(wavs[0])/rate:.2f}s generation={time.time()-start:.1f}s',flush=True)
