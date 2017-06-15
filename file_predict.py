import argparse
import subprocess
import math
import os
import time
from predict_2conv import predict

parser = argparse.ArgumentParser()
parser.add_argument("--model",default="/home/aaron/deepspeech.pytorch/models-merged-1149-5x1024/deepspeech_13.pth.tar")
parser.add_argument("--file_dir",default="/home/aaron/data/mp3s")
parser.add_argument("--segment_duration",default=10,type=int,help="Max segment duration to trim audio file, that will later be further clipped")
parser.add_argument("--scan_range",default=.25,type=float,help="Percent of segment to scan back for in searching for the next split point")
parser.add_argument("--minimum_gap",default=.25,type=float,help="Min gap duration (s) between words for splitting segments")
parser.add_argument("file_id",default=None)
args = parser.parse_args()


def transcribe(file_id,seg_dur,scan_frac,min_gap):
    """Transcribe an audio file by splitting it into segments of seg_dur 
    seconds, passing each to the predict function of a trained DeepSpeech model, 
    rescoring the outputs using a trained KenLM model. Segments are trimmed 
    based on word gaps of min_gap or more seconds, that are searched for within 
    the last scan_frac fraction of a given segment to find the next split point.
    """ 

    # get file duration
    float_dur = float(subprocess.Popen(["soxi","-D","{}".format(file_id)],
        stdout=subprocess.PIPE).stdout.read().strip())
    duration = int(math.ceil(float_dur))
    scan_range = seg_dur * scan_frac

    # write wav file if it doesn't exist
    wav_file = "./auds/{}.wav".format(os.path.basename(file_id).split(".")[0])
    if not os.path.isfile(wav_file):
        print("Converting file to wav")
        subprocess.call(["sox",file_id,"-r","16k",wav_file,"remix","-"])
    
    FNULL = open("/dev/null")
    start_time = time.time()
    predictions = []
    start,iteration = 0,0
    finished = False

    while not finished: 
        print("Processing segment {}...".format(iteration))

        # write segments and generate predictions 
        segment = "./auds/{}.wav".format(start)
        subprocess.call(["sox",wav_file,segment,"trim",str(start),str(seg_dur)],
                stdout=FNULL,stderr=FNULL)
        try:
            res = predict(args.model,segment)
        except RuntimeError:
            print("Segment {} seems to be empty.".format(iteration))
            start += seg_dur
            if start > duration:
                finished = True
        #for time comparisons: res = [(word["word"],word["start"]) for word in res]

        # cycle through this segment's word gaps in reverse order until passing
        # scan_range, choosing the next segment's start time as either the 
        # first gap of at least min_gap seconds in length, or the end of the 
        # segment if none are found
        else:
            # add in offset
            for catch in res:
                catch["start"] += start
            # last segment
            if start + seg_dur > duration:
                predictions.extend(res)
                finished = True
            else:    
                scan_boundary = (start + seg_dur) - scan_range
                
                # start time of next word used to calculate gap
                next_word_start = start + seg_dur

                for i,word in enumerate(res[::-1]):
                    # end time of current word used to calculate gap
                    this_word_end = word["start"] + word["duration"]
                    
                    # went past the scan range and found no good splits, 
                    # so just use the whole segment
                    if this_word_end < scan_boundary:
                        predictions.extend(res)
                        start += seg_dur
                        break

                    # found a good split
                    if next_word_start - this_word_end >= min_gap:
                        if i == 0:
                            predictions.extend(res)
                        else:
                            predictions.extend(res[:-i])
                        start = this_word_end
                        break
                    
                    # no good split yet, so continue looping
                    next_word_start = word["start"]
                
        os.remove(segment)
        iteration += 1
        
        #res = [word["word"] if word["conf"] > .92 else "____" for word in res]
        #predictions.append(" ".join(res))
        #print([(word["word"],word["start"]) for word in predictions])

    end_time = time.time()
    print("{} segments processed in {} seconds.".format(
        iteration,int(end_time-start_time)))

    #return [" ".join(word["word"] for word in predictions)]
    # take care of rounding here after proper format is decided
    return predictions

if __name__ == "__main__":
    path = args.file_dir
    segment_duration = args.segment_duration
    scan_range = args.scan_range
    min_gap = args.minimum_gap
    filename = os.path.join(path,args.file_id)
    outfile = "./auds/{}.ctm".format(os.path.basename(filename).split(".")[0]) 
    #for time comparisons: outfile = "./auds/{}_times.txt".format(os.path.basename(filename).split(".")[0])

    print(filename)
    print(transcribe(filename,segment_duration,scan_range,min_gap))

    # not sure exactly what format to write (as actual json?) so this is temporary
    #ctms = transcribe(filename,segment_duration)
    #with open(outfile,"w") as f:
    #    f.write(str(ctms))

