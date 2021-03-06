#!/usr/bin/env python3


import subprocess
import os
import json
import sys
import potiron
import argparse
import redis
import datetime
import potiron_redis


bpf = potiron.tshark_filter


# Complete the packet with values that need some verifications
def fill_packet(packet):
    # Convert timestamp
    a, b = packet['timestamp'].split('.')
    dobj = datetime.datetime.fromtimestamp(float(a))
    stime = dobj.strftime("%Y-%m-%d %H:%M:%S")
    stime = stime + "." + b[:-3]
    packet['timestamp'] = stime
    try:
        protocol = int(packet['protocol'])
        packet['protocol'] = protocol
    except ValueError:
        pass
    sport = -1
    dport = -1
    if 'tsport' in packet and packet['tsport']:
        sport = packet['tsport']
    if 'usport' in packet and packet['usport']:
        sport = packet['usport']
    if 'tdport' in packet and packet['tdport']:
        dport = packet['tdport']
    if 'udport' in packet and packet['udport']:
        dport = packet['udport']
    if ('tsport' in packet) or ('usport' in packet):
        packet['sport'] = sport
    if ('tdport' in packet) or ('udport' in packet):
        packet['dport'] = dport
    if 'tsport' in packet:
        del packet['tsport']
    if 'usport' in packet:
        del packet['usport']
    if 'tdport' in packet:
        del packet['tdport']
    if 'udport' in packet:
        del packet['udport']
    if 'ipsrc' in packet and packet['ipsrc'] == '-':
        packet['ipsrc'] = None
    if 'ipdst' in packet and packet['ipdst'] == '-':
        packet['ipdst'] = None


# Process data saving into json file and storage into redis
def process_file(rootdir, filename, fieldfilter, b_redis, ck):
    # If tshark is not installed, exit and raise the error
    if not potiron.check_program("tshark"):
        raise OSError("The program tshark is not installed")
    # FIXME Put in config file
    # Name of the honeypot
    sensorname = potiron.derive_sensor_name(filename)
    allpackets = []
    # Describe the source
    allpackets.append({"type": potiron.TYPE_SOURCE, "sensorname": sensorname,
                       "filename": os.path.basename(filename), "bpf": bpf})
    # Each packet has a incremental numeric id
    # A packet is identified with its sensorname filename and packet id for
    # further aggregation with meta data.
    # Assumption: Each program process the pcap file the same way?
    packet_id = 0
    tshark_fields = potiron.tshark_fields
    cmd = "tshark -n -q -Tfields "
    if fieldfilter:
        if 'frame.time_epoch' not in fieldfilter:
            fieldfilter.insert(0, 'frame.time_epoch')
        if 'ip.proto' not in fieldfilter:
            fieldfilter.insert(1, 'ip.proto')
        for p in fieldfilter:
            cmd += "-e {} ".format(p)
    else:
        for f in tshark_fields:
            cmd += "-e {} ".format(f)
    cmd += "-E header=n -E separator=/s -E occurrence=f -Y '{}' -r {} -o tcp.relative_sequence_numbers:FALSE".format(bpf, filename)

    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    json_fields = potiron.json_fields
    special_fields = {'length': -1, 'ipttl': -1, 'iptos': 0, 'tcpseq': -1, 'tcpack': -1, 'icmpcode': 255, 'icmptype': 255}
    for line in proc.stdout.readlines():
        packet_id = packet_id + 1
        line = line[:-1].decode()
        packet = {}
        tab_line = line.split(' ')
        for i in range(len(tab_line)):
            if fieldfilter:
                valname = json_fields[tshark_fields.index(fieldfilter[i])]
            else:
                valname = json_fields[i]
            if valname in special_fields:
                v = special_fields[valname]
                try:
                    v = int(tab_line[i])
                except ValueError:
                    pass
                packet[valname] = v
            else:
                packet[valname] = tab_line[i]
        fill_packet(packet)
        packet['packet_id'] = packet_id
        packet['type'] = potiron.TYPE_PACKET
        packet['state'] = potiron.STATE_NOT_ANNOTATE
        # FIXME might consume a lot of memory
        allpackets.append(packet)

    # FIXME Implement polling because wait can last forever
    proc.wait()

    if proc.returncode != 0:
        errmsg = b"".join(proc.stderr.readlines())
        raise OSError("tshark failed. Return code {}. {}".format(proc.returncode, errmsg))
    # Write and save the json file
    jsonfilename = potiron.store_packet(rootdir, filename, json.dumps(allpackets))
    if b_redis:
        # If redis option, store data into redis
        potiron_redis.process_storage(jsonfilename, red, ck)


if __name__ == '__main__':
    # Parameters parser
    parser = argparse.ArgumentParser(description="Start the tool tshark and transform the output in a json document")
    parser.add_argument("-i", "--input", type=str, nargs=1, help="Pcap or compressed pcap filename")
    parser.add_argument("-c", "--console", action='store_true', help="Log output also to console")
    parser.add_argument("-ff", "--fieldfilter", nargs='+',help='Parameters to filter fields to display (ex: "tcp.srcport udp.srcport")')
    parser.add_argument("-o", "--outputdir", type=str, nargs=1, help="Output directory where the json documents will be stored")
    parser.add_argument("-tf", "--tsharkfilter", type=str, nargs='+', help='Tshark Filter (with wireshark/tshark synthax. ex: "ip.proto == 6")')
    parser.add_argument("-r", "--redis", action='store_true', help="Store data directly in redis")
    parser.add_argument('-u','--unix', type=str, nargs=1, help='Unix socket to connect to redis-server.')
    parser.add_argument('-ck', '--combined_keys', action='store_true', help='Set if combined keys should be used')
    args = parser.parse_args()
    potiron.logconsole = args.console
    if args.input is None:
        sys.stderr.write("At least a pcap file must be specified\n")
        sys.exit(1)
    else:
        if os.path.exists(args.input[0]) is False:
            sys.stderr.write("The filename {} was not found\n".format(args.input[0]))
            sys.exit(1)
        inputfile = args.input[0]
    if args.fieldfilter is None:
        fieldfilter = []
    else:
        fieldfilter = args.fieldfilter

    if args.tsharkfilter is not None:
        if len(args.tsharkfilter) == 1:
            tsharkfilter = args.tsharkfilter[0]
            bpf += " && {}".format(tsharkfilter)
        else:
            tsharkfilter = ""
            for f in args.tsharkfilter:
                tsharkfilter += "{} ".format(f)
            bpf += " && {}".format(tsharkfilter[:-1])

    b_redis = args.redis

    if b_redis:
        if args.unix is None:
            sys.stderr.write('A Unix socket must be specified.\n')
            sys.exit(1)
        usocket = args.unix[0]
        red = redis.Redis(unix_socket_path=usocket)

    ck = args.combined_keys

    if args.outputdir is None:
        sys.stderr.write("You should specify an output directory.\n")
        sys.exit(1)
    else:
        rootdir = args.outputdir[0]
        potiron.create_dirs(rootdir, inputfile)
        if os.path.isdir(rootdir) is False:
            sys.stderr.write("The root directory is not a directory\n")
            sys.exit(1)
    process_file(rootdir, inputfile, fieldfilter, b_redis, ck)
