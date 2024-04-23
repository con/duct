DUCT_PROFILER="smon.py"
CHILD_PROCESSES=5
MEM_KB=10
HOLD_MEM_TIME=2


ps -p $$ -o sid=
rm -f _smon.out
# TODO why doesnt CHILD_PROCESSES work?
# seq: invalid floating point argument: ‘./consume_mem.py’
# To me looks like it thinks consume_mem.py is an int, which means that $CHILD_PROCESSES is emptystring?
# setsid bash -c 'ps -p $$ -o sid=; $DUCT_PROFILER & jobs ; ./abandoning_parent.sh $CHILD_PROCESSES ./consume_mem.py $MEM_KB $HOLD_MEM_TIME ; kill %1'

# Does DUCT_PROFILER need to be run in same sid? Yes I think it does because it retrieves target SID from  OS
setsid bash -c 'ps -p $$ -o sid=; $DUCT_PROFILER ./abandoning_parent.sh 5 ./consume_mem.py 100 5'

# ./abandoning_parent.sh $CHILD_PROCESSES sleep 1



# ps -p $$	Process id of current script
# -o sid= 	only show SID, = hides header
# & jobs  	run cmd in background, show active jobs until they are done
# kill %1	kill current PID 
