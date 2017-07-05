import argparse
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--file_id")
args = parser.parse_args()


ctm_file = "".join((args.file_id,"_align.json"))
audio_file = ".".join((args.file_id,"mp3"))

# leaving offset here in case the algo changes to require it
def trim(base_filename,audio_file,start,end,offset):
    """Write out a segment of an audio file to wav, based on start, end,
    and offset times in seconds.
    """

    segment = os.path.join(".","{}_{}_{}.wav".format(
                                    base_filename,
                                   "{:07d}".format(int((offset+start)*100)),
                                   "{:07d}".format(int((offset+end)*100))))
    duration = end-start
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"])

    return


with open(ctm_file) as f:
    ctm = json.loads(f.read())
    # could eventually put it in a single loop, like
    #for word in json.loads(f.read()):

last_end = 0
capturing = False
for word in ctm:
    if not capturing:
        # start capturing
        if word['case'] == 'mismatch':
            clip_start = last_end #word['start']-(word['start']-last_end)/2.
            last_end = word['end']
            capturing = True

        # just keep track of the end of this word
        elif word['case'] == 'success': # else:
            last_end = word['end']
    else:
        # capture this word too
        if word['case'] == 'mismatch':
            last_end = word['end']

        # stop capturing and write segment if it's long enough
        elif word['case'] == 'success': # else:
            clip_end = word['start'] #word['start']-(word['start']-last_end)/2.
            words = [word['word'] for word in ctm \
                if word['start'] >= clip_start and word['end'] <= clip_end]
            if len(words) > 2:
                print(words)
                trim(args.file_id,audio_file,clip_start,clip_end,0)
            capturing = False

