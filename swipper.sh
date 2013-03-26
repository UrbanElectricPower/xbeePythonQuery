#!/bin/bash

#File that holds the currently written .res file
file="CURRENT.txt"
table="Channel_Normal_Table"
comm="mdb-export"
timesleep=15


while true; do

        cd /cygdrive/z/
        echo "Moved into the data directory"

        pres=$(head -1 $file)
        com=$(tail -1 $file)
        res="${pres}"

        echo "The current .res file being used is $res"

        blah=$(mdb-export "${res}" "${table}" | cut -f 6 | sort -t, -k2 -n | tail -1 | awk -F',' '{print $6, $9, $10}')

        echo $blah
        cd ~/Swip 
        python swipz.py $blah
        echo "$(date) \t Step Recorded: ${blah}" >> ~/Swip/swipz.log
        echo "Sleeping for $timesleep seconds"
        sleep $timesleep
    done


#echo "mdb-export "${RES}" "${TABLE}""
