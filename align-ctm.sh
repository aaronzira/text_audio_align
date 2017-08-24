#!/bin/bash

#set -x
#set -euxo pipefail

if [ $# -lt 3 ]
then
    echo "usage: ./align-ctm.sh filelist index dataset_dir"
    exit 1
fi

filelist=$1
if [ ! -f $filelist ]
then
    echo "$filelist not found"
    exit 1
fi

index=$2
dataset_dir=$3

for fid in `tail -n +$index $filelist`
do
	num_files=`find ${dataset_dir}/txt/${fid}_*.txt 2>/dev/null | wc -l`
	if [ $num_files -eq 0 ]
	then
		index=`grep -n $fid $filelist | cut -d ':' -f1`
		python gaps.py $fid --file-index $index --audio-dir /home/aaron/data/mp3s/ --align-dir ~/data/ctm-alignments/ --dataset-dir ${dataset_dir} --speaker-turns
	fi
done
