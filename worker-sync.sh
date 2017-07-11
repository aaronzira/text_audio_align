#!/bin/bash

inotifywait -mqr -e close_write "/home/rajiv/align" | while read path action file
do
	echo "$file" | grep "_" 1>/dev/null 2>&1
	if [ $? -eq 0 ]
	then
		while true
		do
			scp -p /home/rajiv/align/$file eesen-worker:~/align/
			if [ $? -eq 0 ]
			then
				break
			else
				sleep 1
			fi
		done

        fid=`echo $file | cut -d '_' -f1`
        timeout 90 rsync -T /tmp -avztuq --timeout=60 -e ssh eesen-worker:~/align/$fid*.json ~/align/
	fi
done
