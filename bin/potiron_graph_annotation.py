#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def field2string(field, potiron_path):
    field_strings={}
    with open("{}doc/fields".format(potiron_path), 'r') as p:
        for line in p.readlines():
            brut_val, real_val = line.split('\t')
            field_strings[brut_val] = real_val[:-1]
    field_string = ""
    field_in_file_name = ""
    for word in field_strings[field].split(" "):
        field_string += "{} ".format(word)
        field_in_file_name += "{}-".format(word)
    return field_string[:-1], field_in_file_name[:-1]


def plot_annotation(field, fieldvalues, potiron_path):
    field_string, field_in_file_name = field2string(field, potiron_path)
    
    field_data = {}
    leg = []
    fieldvalues_string = ""  
    if field == "protocol":
        with open("{}doc/protocols".format(potiron_path),'r') as p:
            for line in p.readlines():
                val,n,_,_ = line.split('\t')
                field_data[n] = val
        for v in fieldvalues:
            if v in field_data:
                fieldvalues_string += "{}, ".format(field_data[v])
                leg.append(field_data[v])
            else:
                fieldvalues_string += "{}(unknown protocol), ".format(v)
                leg.append("{}(unknown protocol)".format(v))
    elif field == "dport" or field == "sport":
        with open("{}doc/ports".format(potiron_path),'r') as p:
            for line in p.readlines():
                n,val = line.split('\t')
                nb = n.split('-')
                if len(nb) == 2 :
                    for i in range(int(nb[0]),int(nb[1])):
                        field_data[i] = val[:-1]
                else:
                    field_data[n] = val[:-1]
        for v in fieldvalues:
            if v in field_data:
                fieldvalues_string += "{} ({}), ".format(v,field_data[v])
                leg.append("{} ({})".format(v,field_data[v]))
            else:
                fieldvalues_string += "{} (unknown {}), ".format(v,field_string)
                leg.append("{} (unknown {})".format(v,field_string))
    else:
        for v in fieldvalues:
            fieldvalues_string += "{}, ".format(v)
            leg.append(v)
    
    return field_string, field_in_file_name, fieldvalues_string, leg
    

def bubble_annotation(field, field_string, value, potiron_path):
    if field == "protocol":
        with open("{}doc/protocols".format(potiron_path),'r') as p:
            for line in p.readlines():
                l = line.split('\t')
                if value == l[1]:
                    return " - {}".format(l[0])
        return " - unknown protocol"
    elif field == "dport" or field == "sport":
        with open("{}doc/ports".format(potiron_path),'r') as p:
            for line in p.readlines():
                l = line.split('\t')
                if value == l[0]:
                    return " - {}".format(l[1][:-1])
        return (" - unknown {}".format(field_string))
    else:
        return