import os
import re
import multiprocessing
import json
import subprocess

import boto3
import gentle

def data_generator(file_id):

    print("Processing file id {}".format(file_id))

    # input sources
    txt_file = "/home/aaron/records/{}.txt".format(file_id)
    audio_file = "./{}.mp3".format(file_id)

    # grab audio file
    bucket = boto3.resource("s3").Bucket("cgws")
    bucket.download_file("{}.mp3".format(file_id),audio_file)

    # output
    text_out_dir = "/home/aaron/deepspeech_data/stm"
    wav_out_dir = "/home/aaron/deepspeech_data/wav"

    # reading json from alignment using gentle
    with open(txt_file,"r") as tr:
        transcript = tr.read()
        transcript = re.sub("\d:\d+:\d+\.\d S(\d+|\?): ","",transcript)
        transcript = re.sub("\[.+?\]","",transcript)
        transcript = re.sub("\-"," ",transcript)
        transcript = re.sub("\s{2,}"," ",transcript)
        transcript = re.sub(r"[^a-zA-Z0-9\' ]","",transcript,re.UNICODE)

    resources = gentle.Resources()
    with gentle.resampled(audio_file) as wavfile:
        aligner = gentle.ForcedAligner(resources,transcript,nthreads=multiprocessing.cpu_count(),
                                       disfluency=False,conservative=False,disfluencies=set(["uh","um"]))
        result = aligner.transcribe(wavfile)

    # now a dictionary
    aligned = json.loads(result.to_json())

    # save all consecutively captured strings
    # and keep track of their start and stop times
    strings = []
    times = []

    # a string of consecutively captured words
    current = ""

    # every word as returned from gentle
    for catch in aligned["words"]:

        # consecutive capture
        if catch["case"] == "success" and current:
            running_time = catch["end"]-start_time

            # save string and start new one if adding this word would exceed 20s
            if running_time > 19.99:
                times.append(end_time)
                strings.append(current)

                start_time = catch["start"]
                times.append(start_time)
                current = catch["alignedWord"]
                end_time = catch["end"]

            # append captured word to current string if total time is under 20s
            else:
                current = " ".join([current,catch["alignedWord"]])
                end_time = catch["end"]

        # miss after prior success(es)
        elif (catch["case"] != "success" or catch["alignedWord"] == "<unk>") and current:
            strings.append(current)
            times.append(end_time)
            current = ""

        # success on first word in the file or after a miss
        elif catch["case"] == "success":
            start_time = catch["start"]
            times.append(start_time)
            current = catch["alignedWord"]
            end_time = catch["end"]

    # last word was a success but current string hasn't been saved yet
    if current:
        times.append(end_time)
        strings.append(current)
        current = ""

    # zip start, end, and duration of each string
    start_end_duration = []
    for start,end in zip(times[::2],times[1::2]):
        start_end_duration.append((int(start*100),
                                   int(end*100),
                                   round(end-start,2)))

    # zip strings and times
    text_and_times = list(zip(strings,start_end_duration))

    # write strings to text files and split mp3 file into consituent wav files
    for text,(start,end,duration) in text_and_times:
        with open(os.path.join(text_out_dir,"{}_{}_{}.txt".format(file_id,start,end)),"w") as f:
            f.write(text)

        audio_segment = "{}_{}_{}.wav".format(os.path.join(wav_out_dir,file_id),start,end)
        subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                        "{}".format(audio_segment),"trim","{}".format(start/100.),
                        "{}".format(duration),"remix","-"])

        file_dur = float(subprocess.Popen(["soxi","-D","{}".format(audio_segment)],
                                          stdout=subprocess.PIPE).stdout.read().strip())
        assert file_dur == duration

    total_dur = float(subprocess.Popen(["soxi","-D","{}".format(audio_file)],
                                       stdout=subprocess.PIPE).stdout.read().strip())
    print("Wrote {} files from {}, totalling {} seconds out of a possible {}.".format(
        len(text_and_times),file_id,sum([duration for (_,_,duration) in start_end_duration]),total_dur))

    os.remove(audio_file)
