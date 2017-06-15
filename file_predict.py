import argparse
import subprocess
import math
import os

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


    start_multiple = seg_dur - 1
    current,iteration,predictions = 0,0,[]
    last_word_end = [0]

    # write wav file if it doesn't exist
    wav_file = "./auds/{}.wav".format(os.path.basename(file_id).split(".")[0])
    if not os.path.isfile(wav_file):
        print("Converting file to wav")
        subprocess.call(["sox","{}".format(file_id),"-r","16k","{}".format(wav_file),"remix","-"])

    n_segments = int(duration/start_multiple)

    for start in range(0,duration,start_multiple):
        print("Processing segment {} out of {}...".format(start/start_multiple,n_segments))

        # write segments with 1s overlap and predict on those
        subprocess.call(["sox","{}".format(wav_file),"./auds/{}.wav".format(start),
            "trim","{}".format(start),"{}".format(seg_dur)])
        res = predict(args.model,"./auds/{}.wav".format(start))

        # only retain the words that start outside some buffer before the end of the string
        res = [result for result in res if result["start"] <= start_multiple+.2]
        if res:
            # start of the string buffer depends on the last word in the previous catch
            last_word_end.append(res[-1]["start"]+res[-1]["duration"]-start_multiple)
            res = [result["word"] for result in res if result["start"] >= last_word_end[-2]-.15]
            # drop first words if they are the same as the last one
            for i in range(4):
                if start > 0 and res[i] == predictions[-1][-1]:
                    res = res[i+1:]
            predictions.append(res)
        iteration += 1

    return [" ".join(seg) for seg in predictions]

if __name__ == "__main__":
    path = args.file_dir
    segment_duration = args.segment_duration
    filename = os.path.join(path,args.file_id)
    print(filename)
    print(transcribe(filename,segment_duration))
