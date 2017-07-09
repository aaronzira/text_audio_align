import sys
import argparse
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('file_id', type=str, help='file id to process')
parser.add_argument('--window-len', type=str, dest='window_len', help='number of words to look around the mismatch', default=5)
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
    FNULL = open(os.devnull, 'w')
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"], stdout=FNULL, stderr=FNULL)

    return

def save_txt(base_filename,txt,start,end,offset):
    txt_file = os.path.join(".","{}_{}_{}.txt".format(
                                    base_filename,
                                   "{:07d}".format(int((offset+start)*100)),
                                   "{:07d}".format(int((offset+end)*100))))
    with open(txt_file, 'w') as f:
        f.write(txt + "\n")

with open(ctm_file) as f:
    ctms = json.loads(f.read())
    # could eventually put it in a single loop, like
    #for word in json.loads(f.read()):

last_capture_end = 0
for index, ctm in enumerate(ctms):
    if ctm['case'] == 'mismatch':
        start_index = None
        end_index = None
        captures = []

        # we don't want overlaps between the segments
        if ctm['start'] < last_capture_end:
            continue

        if index - args.window_len < 0:
            # most probably this is mismatch is at the start
            continue

        if index + args.window_len > len(ctms):
            # most probably this is mismatch is towards the end
            continue

        # find the previous word which is a success with a decent gap
        for i in range(index - args.window_len, 0, -1):
            p = i - 1
            if p < 0:
                break;

            gap = ctms[i]['start'] - ctms[p]['end']
            if ctms[i]['case'] == 'success' and ctms[p]['case'] == 'success' and gap > 0.25 and ctms[p]['end'] > last_capture_end:
                start_index = i
                break;

        if not start_index:
            continue;

        # find the next word which is a success with a decent gap
        for i in range(index + args.window_len, len(ctms)):
            n = i + 1
            if n >= len(ctms):
                break;

            gap = ctms[n]['start'] - ctms[i]['end']
            if ctms[i]['case'] == 'success' and ctms[n]['case'] == 'success' and gap > 0.25:
                end_index = i
                break;

        if not end_index:
            continue;

        captures = ctms[start_index:end_index+1]

        words = ' '.join([c['word'] for c in captures])
        print("mistmatch captured at index {}, start_index {}, end_index {}, {}".format(index, start_index, end_index, words))

        clip_start = captures[0]['start']
        clip_end = captures[-1]['end']

        trim(args.file_id,audio_file, clip_start, clip_end, 0)
        save_txt(args.file_id, words, clip_start, clip_end, 0)

        last_capture_end = clip_end
