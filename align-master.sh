#!/bin/bash

#set -x

if [ $# -lt 2 ]
then
    echo "usage: ./align-master.sh filelist index"
    exit 1
fi

filelist=$1
if [ ! -f $filelist ]
then
    echo "$filelist not found"
    exit 1
fi

index=$2

for fid in `tail -n +$index $filelist`
do
	touch ~/data/deepspeech_data/alignments/${fid}.json
	index=`grep -n $fid $filelist | cut -d ':' -f1`
	python rename-alignments.py $fid --file_index $index
	python asr_data_gen.py --file $fid 2>>alignment.log
done
