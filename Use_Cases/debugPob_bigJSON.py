# Exploring use of Pobiverse with JSON
import sys
# sys.path.append('../pobshell')
import json
import pobshell

import os
usecase_dir = os.path.dirname(__file__)
json_file = os.path.join(usecase_dir, "osconfeed.json")
with open(json_file) as fp:
    # with open('/Users/peterdalloz/Dropbox/PYTHONDROPBOX/pobshell_project/Use_Cases/osconfeed.json') as fp:
    feed = json.load(fp)
print(sorted(feed['Schedule'].keys()))
pobshell.shell()


# find -cmd 'ls' -value 1449 /feed/Schedule
# find -cmd 'ls' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -ax' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -x1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1467 /feed/Schedule/venues
# cd /feed/Schedule/venues/25/serial
# find -cmd 'ls -xv' -value 'Exhibit Hall D' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhibit * D' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhi* ED' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhi* E' /feed/Schedule/venues
# find -value 'Exhi* E' /feed/Schedule/venues
# cd /feed/Schedule/venues/27/
# cd Schedule
# cd /feed/Schedule/speakers/352
# ls -l /feed/Schedule/speakers/352/serial/../*
# ls  /feed/Schedule/speakers/352/serial/../*
# ls -x /feed/Schedule/speakers/352/serial/../*
# ls -1 /feed/Schedule/speakers/352/serial/../*
# ls -x /feed/Schedule/speakers/352/serial/../*
# type /feed/Schedule/speakers/352/serial/../*
# cat /feed/Schedule/speakers/352/serial/../*
# cd Schedule
# cd Schedule


# cd feed
# ls
# find . -value 115
# help find
# find . -value 115 -uniq
# find -cmd 'ls' -value 1449 venues
# find -cmd 'ls' -value 1449 /feed/Schedule
# find -cmd 'ls' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -ax' -value 1449 /feed/Schedule/venues
# help ls
# find -cmd 'ls -1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -x1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1467 /feed/Schedule/venues
# cd /feed/Schedule/venues/25/serial
# ls
# ls -l
# ls -al
# cd ..
# cd 25
# ls -l
# cd /
# find -cmd 'ls -xv' -value 'Exhibit Hall D' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhibit * D' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhi* ED' /feed/Schedule/venues
# find -cmd 'ls -xv' -value 'Exhi* E' /feed/Schedule/venues
# find -value 'Exhi* E' /feed/Schedule/venues
# cd /feed/Schedule/venues/27/
# ls
# ls -al
# ls -l
# find -name category /feed
# ls
# ls -l
# cd /feed
# ls
# ls -l
# ls -x
# cd Schedule
# ls
# cd speakers
# ls
# ls -l
# find .. -ivalue '*john*'
# find .. -ivalue '*john*' -cmd 'ls -x'
# find .. -ivalue '*john*' -cmd 'ls -v'
# find .. -ivalue '*john*' -cmd 'ls -1v'
# find .. -ivalue '*john*' -cmd 'ls'
# find .. -ivalue '*john*' -cmd 'ls -l'
# man find
# ls
# ls -l
# ls /222
# ls ./222
# ls -l ./222
# ls -x ./222
# ls -x ./222/name
# ls -l ./222/name
# ls -v ./222/name
# find . -value '*Wolski*'
# find . value '*BDL*'
# find . -value '*BDL*'
# find . -value '*BDL*' -uniq
# find . -value 173466 -uniq -cmd 'ls -xv'
# cd !!
# cd ..
# cd fjsklfjk
# cd ..
# ls
# cd fjsklfjk
# find . -value 173466 -uniq
# cd ..
# find . -value 173466 -uniq
# cd /feed/Schedule/speakers/352
# ls
# ls -l
# cat
# cd ..
# cat
# ls

# cd 352
# ls
# ls ..
# ls ../*
# ls
# ls *
# ls */*
# ls ./*
# ls -l ./*
# cd serial
# ls ../*
# ls -l ../*
# find /feed -value 173466 -uniq -cmd 'ls -l ../*'
# find /feed -value 173466 -uniq -print 'p.name'
# find /feed -value 173466 -uniq -print 'p.parent_obj'
# find /feed -value 173466 -uniq -print 'type(p.parent_obj)'
# cd ..; ls -l
# cd ..
# cd 352/serial
# help
# doc .
# cat .
# cat ..
# cat ../*
# man dir
# help dir
# cat eval
# help eval
# eval
# find /feed -value 173466 -uniq
# ls
# ls ..
# ls ../*
# ls -l ../*
# cd /
# ls -l /feed/Schedule/speakers/352/serial/../*
# ls  /feed/Schedule/speakers/352/serial/../*
# ls -x /feed/Schedule/speakers/352/serial/../*
# man ls
# help ls
# ls -1 /feed/Schedule/speakers/352/serial/../*
# ls -x /feed/Schedule/speakers/352/serial/../*
# type /feed/Schedule/speakers/352/serial/../*
# cat /feed/Schedule/speakers/352/serial/../*
# help ls
# quit
# ls
# reload
# quit


# cd Schedule
# ls
# ls -l
# ls -al
# find . -name 'serial' -cmd 'ls -l'
# find . -name 'serial' -cmd 'ls'
# find . -name 'serial' -cmd 'ls -v'
# find . -name 'serial' -cmd 'ls -p'  # -p disabled as unnecessary now.  try ls .. or ls ../*
# find . -name 'serial' -cmd 'ls -l'

# find . -value 115
# help find
# find . -value 115 -uniq
# find -cmd 'ls' -value 1449 venues
# find -cmd 'ls' -value 1449 /feed/Schedule
# find -cmd 'ls' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -ax' -value 1449 /feed/Schedule/venues
# help ls
# find -cmd 'ls -1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -x1' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1449 /feed/Schedule/venues
# find -cmd 'ls -xv' -value 1467 /feed/Schedule/venues
# cd /feed/Schedule/venues/25/serial
# ls
# ls -l
# ls -al
# cd ..