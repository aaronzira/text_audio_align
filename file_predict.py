import argparse
import subprocess
import math
import os
import time
import numpy as np
from predict_2conv import predict

parser = argparse.ArgumentParser()
parser.add_argument("--model",default="/home/aaron/deepspeech.pytorch/models-merged-1149-5x1024/deepspeech_13.pth.tar")
parser.add_argument("--file_dir",default="/home/aaron/data/mp3s")
parser.add_argument("--segment_duration",default=10,type=int)
parser.add_argument("file_id",default=None)
args = parser.parse_args()


def transcribe(file_id,seg_dur):
    """Transcribe an audio file by splitting it into segments of seg_dur seconds,
    passing each to the predict function of a trained DeepSpeech model, rescoring 
    the outputs using a trained KenLM model, and attempting to remove overlapping 
    words from the output. 
    """ 

    # get the duration of the file 
    float_dur = float(subprocess.Popen(["soxi","-D","{}".format(file_id)],
        stdout=subprocess.PIPE).stdout.read().strip())
    duration = int(math.ceil(float_dur))


    #start_multiple = seg_dur #- 1
    predictions = []

    # write wav file if it doesn't exist
    wav_file = "./auds/{}.wav".format(os.path.basename(file_id).split(".")[0])
    if not os.path.isfile(wav_file):
        print("Converting file to wav")
        subprocess.call(["sox",file_id,"-r","16k",wav_file,"remix","-"])
    
    FNULL = open("/dev/null")
    #n_segments = int(duration/start_multiple)
    start_time = time.time()

    #for start in range(0,duration,start_multiple):
    start,iteration,finished = 0,0,False
    while not finished: 
        #print("Processing segment {} out of {}...".format(start/start_multiple,n_segments))
        print("Processing segment {}...".format(iteration))

        # write segments and generate predictions 
        segment = "./auds/{}.wav".format(start)
        subprocess.call(["sox",wav_file,segment,"trim",str(start),str(seg_dur)],stdout=FNULL,stderr=FNULL)
        try:
            res = predict(args.model,segment)
        except RuntimeError:
            #print("Segment {} seems to be empty.".format(start/start_multiple))
            print("Segment {} seems to be empty.".format(iteration))
            start += seg_dur
            if start > duration:
                finished = True
        #for time comparisons: res = [(word["word"],word["start"]) for word in res]

        # look for the largest gap between words that occurs in the second half of the capture
        # as determined by numer of words, and use that as the starting time for the next segment
        else:
            # add in offset
            for catch in res:
                catch["start"] += start

            if start+seg_dur > duration:
                predictions.extend(res)
                finished = True
            else:    
                halfway = len(res)/2
                first,second = res[:halfway],res[halfway:]

                starts = [word["start"] for word in second]
                starts.append(seg_dur+start)
                ends = [word["start"]+word["duration"] for word in second]
                gaps = [s-e for s,e in zip(starts[1:],ends)]
                print([round(gap,2) for gap in gaps])
                split_point = np.argmax(gaps)
                predictions.extend(first)
                predictions.extend(second[:split_point+1])

                start += ends[split_point]
        os.remove(segment)
        iteration += 1
        
        #res = [word["word"] if word["conf"] > .92 else "____" for word in res]
        #predictions.append(" ".join(res))
        #print([(word["word"],word["start"]) for word in predictions])
        """
        # only retain the words that start outside some buffer before the end of the string 
        res = [result for result in res if result["start"] <= start_multiple+.2]
        if res:
            # start of the string buffer depends on the last word in the previous catch
            last_word_end.append(res[-1]["start"]+res[-1]["duration"]-start_multiple)
            res = [(result["word"],result["conf"]) for result in res if result["start"] >= last_word_end[-2]-.15]
            # drop first words if they are the same as the last one 
            for i in range(4):
                if start > 0 and res[i] == predictions[-1][-1]:
                    res = res[i+1:]
            predictions.append(res)
        """
    end_time = time.time()
    print("{} segments processed in {} seconds.".format(iteration,int(end_time-start_time)))

    #print("{} segments processed in {} seconds.".format(n_segments+1,int(end_time-start_time)))
    #transcript = " ".join([" ".join(seg) for seg in predictions])
    #with open("./auds/transcript.txt","w") as f:
    #    f.write(transcript)
    #return transcript

    #return [" ".join(word["word"] for word in predictions)]
    # take care of rounding here after proper format is decided
    return predictions

if __name__ == "__main__":
    path = args.file_dir
    segment_duration = args.segment_duration
    filename = os.path.join(path,args.file_id)
    outfile = "./auds/{}.ctm".format(os.path.basename(filename).split(".")[0]) 
    #for time comparisons: outfile = "./auds/{}_times.txt".format(os.path.basename(filename).split(".")[0])

    print(filename)
    print(transcribe(filename,segment_duration))

    # not sure exactly what format to write (as actual json?) so this is temporary
    #ctms = transcribe(filename,segment_duration)
    #with open(outfile,"w") as f:
    #    f.write(str(ctms))

