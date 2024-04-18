#!/usr/bin/env python3

import os
import subprocess
import json
import time
import sys
import shutil

name="_smon.out"

sid=os.getsid(os.getpid())


def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

with open(name, "w") as outfile:

    env = {}
    #put some batch scheduler specific env
    for k in os.environ:
        if k.startswith(("PBS_", "SLURM_", "OSG")):
            env[k] = os.environ[k]

    #figure out max PPN
    max_ppn = os.sysconf('SC_NPROCESSORS_CONF') #default to all available cores
    if "PBS_NUM_PPN" in os.environ:
        max_ppn = int(os.environ["PBS_NUM_PPN"])
    #from https://slurm.schedmd.com/srun.html
    if "SLURM_CPUS_ON_NODE" in os.environ: #incase SLURM_NTASKS is not set?
        max_ppn = int(os.environ["SLURM_CPUS_ON_NODE"])
    if "SLURM_NTASKS" in os.environ:
        max_ppn = int(os.environ["SLURM_NTASKS"])

    #figure out max mem
    max_mem = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    max_walltime = None
    if "PBS_JOBID" in os.environ:
        #PBS doesn't expose requested memory in ENV.. I need to query from qstat
        out=subprocess.check_output(["qstat", "-f1", os.environ["PBS_JOBID"]]).decode("utf-8")
        qstat={}
        for line in out.split("\n"):
            delpos = line.find("=")
            if delpos == -1: continue
            k=line[0:delpos].strip()
            v=line[delpos+1:].strip()
            qstat[k] = v

        if "Resource_List.vmem" in qstat:
            #only carbonate has this
            max_mem_str = qstat["Resource_List.vmem"] #64gb, etc..
            if max_mem_str.endswith("gb"):
                max_mem = int(max_mem_str[0:-2])*1024*1024*1024 #pbs treats gb and GB the same..

        if "Walltime.Remaining" in qstat:
            max_walltime = int(qstat["Walltime.Remaining"])

    if "SLURM_MEM_PER_NODE" in os.environ:
        #Default units are megabytes unless the SchedulerParameters configuration parameter includes the "default_gbytes" option for gigabytes.
        #https://slurm.schedmd.com/sbatch.html
        max_mem = int(os.environ["SLURM_MEM_PER_NODE"])*1024*1024 

    if "PBS_WALLTIME" in os.environ:
        max_walltime = int(os.environ["PBS_WALLTIME"])
    
    #TODO - figure out how to find walltime for slurm
    #https://confluence.csiro.au/display/SC/Reference+Guide%3A+Migrating+from+Torque+to+SLURMt

    #query for gpu info
    gpus = None
    if shutil.which("nvidia-smi") is not None:
        try:
            out=subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,pci.bus_id,driver_version,memory.total,compute_mode", "--format=csv"]).decode("utf-8")
            lines=out.strip().split("\n")
            header=lines.pop(0)
            gpus = []
            for line in lines:
                cols=line.split(", ")
                gpus.append({
                    "index": cols[0],
                    "name": cols[1],
                    "bus_id": cols[2],
                    "driver_version": cols[3],
                    "memory.total": cols[4],
                    "compute_mode": cols[5],
                })
        except subprocess.CalledProcessError as e:
            print(e)

    #dump info that doesn't change on the first entry
    json.dump({
        "time": time.time(), 
        "uname": os.uname(), #os/kernerl/hostname version
        "cpu_total": os.sysconf('SC_NPROCESSORS_CONF'),
        "cpu_requested": max_ppn,

        "gpus": gpus,

        "memory_total": os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'),
        "memory_requested": max_mem,

        "walltime_requested": max_walltime,

        "sid": sid,
        "uid": os.environ['USER'],

        "env": env,

        }, outfile)

    outfile.write("\n")
    outfile.flush()

    #now start infinite loop!
    while True:

        #query gpu usage
        if gpus != None:
            gpus = []
            out=subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,pstate,temperature.gpu,utilization.gpu,utilization.memory", "--format=csv"]).decode("utf-8")
            lines=out.strip().split("\n")
            header=lines.pop(0)
            for line in lines:
                cols=line.split(", ")
                gpus.append({
                    "index": cols[0],
                    "name": cols[1],
                    "pstate": cols[2], #The current performance state for the GPU. States range from P0 (maximum performance) to P12 (minimum performance).
                    "temperature.gpu": int(cols[3]),
                    "utilization.gpu": int(cols[4][:-1]), #remove %
                    "utilization.memory": int(cols[5][:-1]), #remove %
                    #"fan.speed": int(cols[6][:-1]), #remove % ([N/A] on bridges2)
                })

        #query process under current session (query every 2 seconds for 1 minute)
        processes = {}
        for i in range(30):
            out=subprocess.check_output(["ps", "-s", str(sid), "ho", "pid,pcpu,pmem,rss,vsz,etime,cmd"]).decode("utf-8")
            for line in out.split("\n"):
                if line == "":
                    continue
                tokens=line.split()
                pid=tokens[0]
                pcpu=float(tokens[1])
                pmem=float(tokens[2])
                rss=int(tokens[3])
                vsz=int(tokens[4])
                etime=tokens[5]
                cmd=' '.join(tokens[6:])

                #ignore myself.
                if cmd.startswith("ps -s"):
                    continue

                #ignore smon 
                if cmd.startswith("python ./smon"):
                    continue

                #etime == elapsed time .. don't include process that just got started? (TODO why did I do this?)
                if etime == "00:00": 
                    continue

                if not pid in processes:
                    processes[pid] = []
                processes[pid].append({"pid": pid, "pcpu": pcpu, "pmem": pmem, "rss": rss, "vsz": vsz, "etime": etime, "cmd": cmd})

            time.sleep(2)

        #aggregate(max) processes list for each pid
        processes_groups = []
        for pid in processes:
            group = processes[pid]
            last = group[len(group)-1]
            agg = {"pid": last["pid"], "pcpu": 0, "pmem": 0, "rss": 0, "vsz": 0, "etime": last["etime"], "cmd": last["cmd"]}
	    #pick max value
            for p in group:
                agg["pcpu"]=max(agg["pcpu"], p["pcpu"])
                agg["pmem"]=max(agg["pmem"], p["pmem"])
                agg["rss"]=max(agg["rss"], p["rss"])
                agg["vsz"]=max(agg["vsz"], p["vsz"])

            processes_groups.append(agg)

        #query disk usage
        disks = []
        try:
            out=subprocess.check_output(["du", "-s"]).decode("utf-8")
            for line in out.split("\n"):
                if line == "":
                    continue
                tokens=line.split()
                size=int(tokens[0])
                path=tokens[1]
                disks.append({"path": path, "size": size})
        except subprocess.CalledProcessError as err:
            #sometimes files go missing while running du.. but that's ok
            print(err)

        json.dump({
            "time": time.time(), 
            "processes": processes_groups, 
            "disks": disks,
            "gpus": gpus,
            "memory_avail": os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_AVPHYS_PAGES'),
            #"memory_avail": psutil.virtual_memory().available,
            #"memory_used": psutil.virtual_memory().used,
            #"memory_free": psutil.virtual_memory().free,
            }, outfile)

        outfile.write("\n")
        outfile.flush()

