import os
import multiprocessing
import json
import subprocess

import gentle

def data_generator(file_id):

    # input sources
    audio_dir = "../audio_second" ### boto here to grab from s3 bucket
    transcripts_dir = "../audio_second" ### "~/scribie/records"

    audio_file = os.path.join(audio_dir,"{}.mp3".format(file_id))
    txt_file = os.path.join(transcripts_dir,"{}.txt".format(file_id))

    # output
    text_out_dir = "../audio_second/text_testing" ###"~/deepspeech_data/stm"
    wav_out_dir = "../audio_second/audio_testing" ###"~/deepspeech_data/wav"

    # reading json from alignment using gentle
    with open(txt_file,"r") as tr:
        transcript = tr.read()
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

            # append captured word to current string if total time is under 20s
            else:
                current = " ".join([current,catch["alignedWord"]])
                end_time = catch["end"]

        # miss after prior success(es)
        elif catch["case"] != "success" and current:
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
        start_end_duration.append((float("{:.2f}".format(start)),
                                   float("{:.2f}".format(end)),
                                   float("{:.2f}".format(end-start))))

    # zip strings and times
    text_and_times = list(zip(strings,start_end_duration))

    # write strings to text files and split mp3 file into consituent wav files
    for text,(start,end,duration) in text_and_times:
        with open(os.path.join(text_out_dir,"{}_{}_{}.txt".format(file_id,start,end)),"w") as f:
            f.write(text)

        audio_segment = "{}_{}_{}.wav".format(os.path.join(wav_out_dir,file_id),start,end)
        subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                        "{}".format(audio_segment),"trim","{}".format(start),
                        "{}".format(duration),"remix","-"])

        file_dur = float(subprocess.Popen(["soxi","-D","{}".format(audio_segment)],
                                          stdout=subprocess.PIPE).stdout.read().strip())
        assert file_dur == duration
