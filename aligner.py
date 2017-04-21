import os
import json
import subprocess


def data_generator(file_id):

    # input sources
    audio_dir = "./" ### boto here to grab from s3 bucket
    transcripts_dir = "./" ### "~/scribie/records"

    audio_file = os.path.join(audio_dir,"{}.mp3".format(file_id))
    transcript = os.path.join(transcripts_dir,"{}.txt".format(file_id))

    # output
    text_out_dir = "text_testing" ###"~/deepspeech_data/stm"
    wav_out_dir = "audio_testing" ###"~/deepspeech_data/wav"



    # save all consecutively captured strings
    # and keep track of their start and stop times
    strings = []
    times = []

    # a string of consecutively captured words
    current = ""

    # write out json object from gentle
    ### need to specify gentle directory
    gentle_align = PATH_TO_GENTLE ###../gentle/align.py
    temp_json_file = "./output"
    subprocess.call(["python","{}".format(gentle_align),"{}".format(audio_file),
                    "{}".format(transcript),"-o","{}".format(temp_json_file)])

    # then read it in as a dictionary... skip this step and grab it on the fly?
    with open(temp_json_file,"r") as f:
        aligned = json.loads(f.read())

    ### not really necessary to delete temp_json_file because you'll write over it each time
    #could delete it at the end, or grap the output form gentle on the fly

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
        file_dur = float("{.:2f}".format(subprocess.call(["soxi","-D","{}".format(audio_segment)])))
        assert file_dur == duration
