"""Render an animated product walkthrough from verified UI captures and local speech.

No synthetic clicks or fabricated UI results: motion consists of camera moves,
editorial focus outlines, and transitions between actual captured states.
Captions have no background; only white text with a thin outline.
"""
from __future__ import annotations
import argparse, json, math, re, shutil, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/submission'
BUILD=ROOT/'.tmp/submission-motion'
W,H,FPS=1920,1080,24

def seconds(path):
    with wave.open(str(path)) as f:return f.getnframes()/f.getframerate()

def ease(v):
    v=max(0.,min(1.,v));return v*v*(3-2*v)

def stamp(v):
    m=round(v*1000);return f'{m//3600000:02}:{m//60000%60:02}:{m//1000%60:02},{m%1000:03}'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ffmpeg',default='ffmpeg')
    ap.add_argument('--font',default='C:/Windows/Fonts/msyh.ttc')
    ap.add_argument('--preview',action='store_true',help='Render representative motion frames without audio')
    a=ap.parse_args();BUILD.mkdir(parents=True,exist_ok=True)
    scenes=json.loads((OUT/'video-scenes.json').read_text('utf-8-sig'))
    font={n:ImageFont.truetype(a.font,n) for n in [35,40,46,54,64,72,86,106]}
    shots={s['image']:Image.open(OUT/'assets'/s['image']).convert('RGB') for s in scenes}
    for s in scenes:
        if s.get('secondary'):shots[s['secondary']]=Image.open(OUT/'assets'/s['secondary']).convert('RGB')
    bg=Image.new('RGB',(W,H));d=ImageDraw.Draw(bg)
    for y in range(H):
        u=y/H;d.line((0,y,W,y),fill=(round(245-12*u),round(247-9*u),round(239-10*u)))
    d.ellipse((1370,-250,2230,610),fill='#e4ebdf')
    d.ellipse((-400,730,340,1450),fill='#e6ecdf')
    hero_art=Image.open(ROOT/'frontend/src/assets/decor/study-sculpture-v2.png').convert('RGB')
    screen=(72,110,1848,950);sw=screen[2]-screen[0];sh=screen[3]-screen[1]
    mask=Image.new('L',(sw,sh));ImageDraw.Draw(mask).rounded_rectangle((0,0,sw,sh),radius=24,fill=255)
    shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
    for n in range(13,0,-1):sd.rounded_rectangle((72-n,116-n,1848+n,957+n),radius=24+n,fill=(21,53,42,2))
    def text_layer(text,xy,size,color,opacity=1):
        layer=Image.new('RGBA',(W,H));p=ImageDraw.Draw(layer)
        p.text(xy,text,font=font[size],fill=(*color,round(255*max(0,min(1,opacity)))))
        return layer
    def crop_box(im,focus,t,duration):
        iw,ih=im.size;ratio=sw/sh
        bw=min(iw,ih*ratio);bh=bw/ratio
        base=((iw-bw)/2,(ih-bh)/2,bw,bh)
        fx,fy,ex,ey=focus
        tw=min(iw,max((ex-fx)*iw,(ey-fy)*ih*ratio));th=tw/ratio
        if th>ih:th=ih;tw=th*ratio
        tx=max(0,min(iw-tw,(fx+ex)*iw/2-tw/2));ty=max(0,min(ih-th,(fy+ey)*ih/2-th/2))
        move=ease((t-2.5)/6.5)
        # Return partway toward context at the end, without abrupt zoom reversals.
        move*=1-0.22*ease((t-duration+4)/3.2)
        box=[base[k]+([tx,ty,tw,th][k]-base[k])*move for k in range(4)]
        drift=.008*math.sin(t/duration*math.pi)**2
        box[0]+=box[2]*drift/2;box[1]+=box[3]*drift/2;box[2]*=1-drift;box[3]*=1-drift
        return tuple(box)
    marks={'03-review.png':(.438,.296,.598,.341),'07-radar.png':(.77,.36,.945,.436),'09-completed.png':(.205,.64,.60,.72)}
    def screen_view(scene,t,duration):
        im=shots[scene['image']];focus=scene.get('focus',[.05,.05,.95,.95])
        x,y,cw,ch=crop_box(im,focus,t,duration)
        view=im.crop((x,y,x+cw,y+ch)).resize((sw,sh),Image.Resampling.BICUBIC)
        if scene.get('secondary') and t<4.8:
            second=shots[scene['secondary']];ch2=second.width*sh/sw
            q=second.crop((0,(second.height-ch2)/2,second.width,(second.height+ch2)/2)).resize((sw,sh),Image.Resampling.LANCZOS)
            view=Image.blend(q,view,ease((t-2.8)/2))
        marker=marks.get(scene['image'])
        if marker and 7<t<13.5:
            alpha=ease((t-7)/.55)*(1-ease((t-12.5)/1))
            layer=Image.new('RGBA',(sw,sh));pen=ImageDraw.Draw(layer)
            x1,y1,x2,y2=marker;box=((x1*im.width-x)*sw/cw-8,(y1*im.height-y)*sh/ch-8,(x2*im.width-x)*sw/cw+8,(y2*im.height-y)*sh/ch+8)
            pen.rounded_rectangle(box,radius=13,outline=(188,136,57,round(245*alpha)),width=4)
            view=Image.alpha_composite(view.convert('RGBA'),layer).convert('RGB')
        return view
    def visual(index,t,duration):
        s=scenes[index];im=bg.copy();kind=s.get('kind','ui')
        if kind in ['intro','outro']:
            art=hero_art.copy()
            z=1+0.022*math.sin(t/duration*math.pi)
            art=art.resize((round(1240*z),round(827*z)),Image.Resampling.BICUBIC)
            ax=round(820-45*ease(t/1.3)-(art.width-1240)/2);ay=round(150+(1-ease(t/1.3))*35)
            am=Image.new('L',art.size,255);ad=ImageDraw.Draw(am)
            for edge in range(90):ad.line((edge,0,edge,art.height),fill=round(255*ease(edge/90)))
            im.paste(art,(ax,ay),am)
            p=ImageDraw.Draw(im);p.text((108,235),'学伴管家',font=font[106],fill='#163f34')
            words=['把学习，','安排好。'] if kind=='intro' else ['下一步，','清楚一点。']
            for j,word in enumerate(words):
                alpha=ease((t-.35-j*.24)/.9)
                im=Image.alpha_composite(im.convert('RGBA'),text_layer(word,(112,405+j*110+(1-alpha)*24),86,(24,66,52),alpha)).convert('RGB')
            for j,word in enumerate(['资料','截止','复习']):
                alpha=ease((t-1.3-j*.3)/.7)
                im=Image.alpha_composite(im.convert('RGBA'),text_layer(word,(115+j*185,735),40,(78,104,84),alpha)).convert('RGB')
        elif kind=='mobile':
            p=ImageDraw.Draw(im);p.text((125,300),'换个屏幕，',font=font[86],fill='#163f34');p.text((125,412),'继续学习。',font=font[86],fill='#163f34')
            for j,word in enumerate(['随手记','随时看']):
                alpha=ease((t-2-j*3)/1)
                im=Image.alpha_composite(im.convert('RGBA'),text_layer(word,(130+j*235,610),54,(66,108,85),alpha)).convert('RGB')
            phone=shots[s['image']].resize((400,865),Image.Resampling.LANCZOS)
            x=round(1230-95*ease(t/1.4));y=round(70+7*math.sin(t/4))
            p=ImageDraw.Draw(im);p.rounded_rectangle((x-14,y-14,x+414,y+879),radius=40,fill='#233e34')
            pm=Image.new('L',phone.size);ImageDraw.Draw(pm).rounded_rectangle((0,0,400,865),radius=26,fill=255);im.paste(phone,(x,y),pm)
        else:
            im=Image.alpha_composite(im.convert('RGBA'),shadow).convert('RGB')
            view=screen_view(s,t,duration);offset=round(48*(1-ease(t/.9)))
            im.paste(view,(screen[0]+offset,screen[1]),mask)
            title_alpha=ease(t/.5)*(1-ease((t-3.8)/1.0))
            im=Image.alpha_composite(im.convert('RGBA'),text_layer(s['title'],(80,27+(1-ease(t/.7))*10),46,(22,63,52),title_alpha)).convert('RGB')
        return im
    if a.preview:
        for i in range(len(scenes)):
            for t in ([1.,9.] if i not in (0,len(scenes)-1) else [2.]):
                visual(i,t,23).save(BUILD/f'preview-{i:02}-{int(t):02}.jpg',quality=90)
        print('Motion keyframe previews ready');return
    def run(args):subprocess.run([a.ffmpeg,'-hide_banner','-loglevel','error','-y',*args],check=True)
    raw_paths=[BUILD/f'audio/{i:02}.wav' for i in range(1,len(scenes)+1)]
    raw_times=[seconds(p) for p in raw_paths]
    durations=[];subtitles=[];chapters=[];all_captions=[];audio_list=[];cursor=0.
    extra=max(0.,(184-sum(raw_times)-1.1*len(scenes))/len(scenes))
    for i,(s,path,raw) in enumerate(zip(scenes,raw_paths,raw_times)):
        pad=.65+extra+(1 if i==len(scenes)-1 else 0)
        apath=BUILD/f'audio/motion-{i:02}.wav'
        run(['-i',str(path),'-af',f'loudnorm=I=-16:TP=-1.5:LRA=11,adelay=450,apad=pad_dur={pad}', '-ar','48000','-ac','1',str(apath)])
        duration=math.ceil(seconds(apath)*FPS)/FPS;durations.append(duration)
        # Match video rounding with less than one frame of extra silence.
        run(['-i',str(apath),'-af','apad','-t',str(duration),str(BUILD/f'audio/aligned-{i:02}.wav')])
        audio_list.append(f"file '{(BUILD/f'audio/aligned-{i:02}.wav').as_posix()}'")
        phrases=[x.strip() for x in re.split(r'(?<=[。！？；，])',s['voice']) if x.strip()]
        caps=[]
        for phrase in phrases:
            if caps and len(caps[-1])+len(phrase)<=24:caps[-1]+=phrase
            else:caps.append(phrase)
        weight=sum(len(x) for x in caps);local=.45;timed=[]
        for caption in caps:
            length=raw*len(caption)/weight
            timed.append((local,local+length,caption))
            subtitles.append(f'{len(subtitles)+1}\n{stamp(cursor+local)} --> {stamp(cursor+local+length)}\n{caption}\n')
            local+=length
        all_captions.append(timed)
        chapters.append({'scene':i+1,'start_seconds':cursor,'duration_seconds':duration,'title':s['title']});cursor+=duration
    assert 180<=cursor<=300,f'Duration outside competition range: {cursor}'
    (BUILD/'audio-concat.txt').write_text('\n'.join(audio_list),'utf-8')
    run(['-f','concat','-safe','0','-i',str(BUILD/'audio-concat.txt'),'-c:a','libmp3lame','-b:a','160k',str(BUILD/'narration.mp3')])
    cmd=[a.ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(BUILD/'narration.mp3'),'-c:v','libx264','-preset','veryfast','-crf','22','-threads','6','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(BUILD/'final.mp4')]
    with open(BUILD/'encode.log','wb') as err:
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=err)
        try:
            previous=None
            for i,duration in enumerate(durations):
                print(f'Rendering {i+1}/{len(scenes)} {duration:.2f}s',flush=True)
                for frame in range(round(duration*FPS)):
                    t=frame/FPS;im=visual(i,t,duration)
                    if previous is not None and t<.72:im=Image.blend(previous,im,ease(t/.72))
                    caption=next((text for start,end,text in all_captions[i] if start<=t<end),'')
                    if caption:
                        pen=ImageDraw.Draw(im);box=pen.textbbox((0,0),caption,font=font[40]);x=(W-box[2]+box[0])/2
                        # Transparent caption: no rectangle, plate, or shaded region.
                        pen.text((x,1000),caption,font=font[40],fill='white',stroke_width=2,stroke_fill='#24342f')
                    if i==0 and t<.55:im=Image.blend(bg,im,ease(t/.55))
                    if i==len(scenes)-1 and t>duration-.7:im=Image.blend(im,bg,ease((t-duration+.7)/.7))
                    process.stdin.write(im.tobytes())
                previous=visual(i,duration-1/FPS,duration)
            process.stdin.close();code=process.wait()
            if code:raise RuntimeError((BUILD/'encode.log').read_text(errors='replace'))
        except BaseException:
            process.kill();raise
    assert 180<=cursor<=300,f'Duration outside competition range: {cursor}'
    shutil.copy2(BUILD/'final.mp4',OUT/'学伴管家-介绍与演示.mp4')
    shutil.copy2(BUILD/'narration.mp3',OUT/'学伴管家-旁白.mp3')
    (OUT/'学伴管家-介绍与演示.srt').write_text('\n'.join(subtitles),'utf-8')
    meta={'version':2,'seconds':cursor,'resolution':'1920x1080','fps':FPS,'narration_characters':sum(len(s['voice']) for s in scenes),'tts':'Local Qwen3-TTS / Vivian','subtitle_style':'white outlined text; transparent background','subtitle_timing':'phrase timing estimated from text length','motion':'camera push-ins, focus outlines, device float, staggered title reveal, dissolve transitions','visual_source':'Actual app screenshots; editorial motion, not a continuous recording','chapters':chapters}
    (OUT/'video-metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf-8')
    print(f'Done: {cursor:.2f}s; {(OUT/"学伴管家-介绍与演示.mp4").stat().st_size/1024**2:.1f} MiB',flush=True)

if __name__=='__main__':main()
