import argparse
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--file_id",help="filename without .json or .mp3 extension")
parser.add_argument("--min_gap",default=0.5,type=float,help="minimum gap between words to use for splitting")
parser.add_argument("--debug",action="store_true")
args = parser.parse_args()


# temporarily running them from "others/"
ctm_file = "".join(("others/",args.file_id,"_align.json"))
audio_file = ".".join(("others/"+args.file_id,"mp3"))

# leaving offset here in case the algo changes to require it
def trim(base_filename,audio_file,start,end,offset):
    """Write out a segment of an audio file to wav, based on start, end,
    and offset times in seconds.
    """
    FNULL = open("/dev/null")
    # still os.path.join for adding out dir later
    segment = os.path.join("{}_{}_{}.wav".format(
                                    base_filename,
                                   "{:07d}".format(int((offset+start)*100)),
                                   "{:07d}".format(int((offset+end)*100))))
    duration = end-start
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"],
                stdout=FNULL,stderr=FNULL)

    return segment

with open(ctm_file) as f:
    ctm = json.loads(f.read())
    # could eventually put it in a single loop, like
    #for word in json.loads(f.read()):

    null_word = {'case':None, 'conf':None, 'duration':0, 'end':0, 'orig':None, 'pred':None, 'start':0, 'word':None}
    gaps = [second['start']-first['end'] for first,second in zip([null_word]+ctm,ctm)]

    last = 0
    #last_gap = 0
    total_written = 0
    for i,gap in enumerate(gaps):
        if gap > args.min_gap:

            #print("longer than .5: ", gap)
            #print(i)
            #print(" ".join([word['word'] for word in ctm[last:i]]))

            n_words = i-last
            n_mismatches = sum([word['case'] == 'mismatch' for word in ctm[last:i]])

            if n_words > 3 and n_mismatches > 2:
                #print("passed check. writing from {} to {}".format(ctm[last]['start'],ctm[i]['start']))
                #and gaps[i+1] > .2 \
                ## could potentially be out of index

                #and ctm[last-1]['case']=='success' \
                #and ctm[last]['case']=='success' \
                #and ctm[i-1]['case']=='success' \
                #and ctm[i]['case']=='success':

                #print("\t".join([word['word'] for word in ctm[last:i]]))
                #print("\t".join(["X" if word['case'] == "mismatch" else "O" for word in ctm[last:i]]))

                clip_start = ctm[last]['start'] #-(last_gap/10.) ##ctm[last-1]['end'] #+(last_gap/10.)
                clip_end = ctm[i]['start'] #-(gap/10.) ##ctm[i-1]['end'] #+gap/2.
                wav_name = trim(args.file_id,audio_file,clip_start,clip_end,0)

                # fine for now, but what if a file had a "." in the name
                with open(".".join([wav_name.split(".")[0],"txt"]),"w") as f:
                    f.write(" ".join([word["word"] for word in ctm[last:i]]))
                    if args.debug:
                        f.write("\n{} {} {}".format(ctm[last]['start'],ctm[i]['start'],gap))
                total_written += clip_end-clip_start

            #last_gap = ctm[i]['start']-ctm[i-1]['end']
            last = i
            #print(ctm[i]['case'],ctm[i+1]['case'])

print("Wrote {} seconds out of {} ({:.2f}%).".format(total_written,ctm[-1]['end'],(total_written/ctm[-1]['end'])*100))
