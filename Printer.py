#!/usr/bin/python3

import os
import subprocess
import itertools
import time
import requests

from copy import deepcopy
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import dateutil, netifaces
except ImportError as e:
    os.system("apt install -y python3-dateutil python3-netifaces")

from dateutil.parser import *
from dateutil.tz import *
import netifaces as ni
from netifaces import AF_INET, AF_INET6, AF_LINK, AF_PACKET, AF_BRIDGE


# ---- Collect System INFO
def ubuntu_version():
    version = subprocess.check_output("lsb_release -r | awk '{print $2}'", shell=True).decode("utf-8").strip('\n')
    return version


def get_hostname():
    host = subprocess.check_output("grep 'host' /home/client/fusion-linux/cache/syncConfig | awk '{print $3}' | sed 's/\"//g'", shell=True).decode("utf-8").strip('\n')
    return host


def get_vpn_ip():
    try: 
        ip = ni.ifaddresses('tun0')[AF_INET][0]['addr']
    except Exception as ex:
        print(ex)
        ip = ""
    if not ip:
        return  "VPN interface tun0 tunnel not found"
    else:
        return ip


def get_serialnumber():
    try:
        serial = subprocess.check_output("cat /home/client/.config/touch2success/drone.conf | grep serialnumber | cut -d'=' -f2", shell=True).decode("utf-8").strip('\n')
    except CalledProcessError as e:
        print(e)
    if not serial:
        return "no serial number found"
    else:
        return serial


# --- Printer drivers
def update_paperSource_CutTiming_PaperSize(printer):
    print("Updating the paperSource cutting timing_paperSize")
    subprocess.call("lpadmin -p TM-T20_{} -o TmxPaperSource=PageFeedCut".format(printer), shell=True)
    subprocess.call("lpadmin -p TM-T20_{} -o TmtPaperSource=PageFeedCut".format(printer), shell=True)
    subprocess.call("lpadmin -p TM-T20_{} -o CutTiming=Page".format(printer), shell=True)


def install_cups_epson():
    print("---------------------------------------------------------EPSON---------------------------------------------------------------------")
    subprocess.call("wget -N arditmula.com/epson.tar.gz", shell=True)
    subprocess.call("tar xvf epson.tar.gz", shell=True)
    subprocess.call("cd epson;SHELL=/bin/sh PATH=/bin:/sbin:/usr/bin:/usr/sbin; bash install.sh", shell=True)


def install_star_tsp100():
    print("---------------------------------------------------------STAR---------------------------------------------------------------------")
    subprocess.call("wget -N https://s3-eu-west-1.amazonaws.com/t2s-staging-prod-cloudfiles-private.com/star_yuge.sh", shell=True)
    subprocess.call("chmod 755 star_yuge.sh", shell=True)
    subprocess.call("cd .;SHELL=/bin/sh PATH=/bin:/sbin:/usr/bin:/usr/sbin; bash star_yuge.sh", shell=True)
    printer = "star"
    update_paperSource_CutTiming_PaperSize(printer)


def install_seiko_rp_d10():
    print("---------------------------------------------------------SEIKO---------------------------------------------------------------------")
    subprocess.call("wget -N https://s3.eu-west-2.amazonaws.com/prod-cloudfiles-private.com/seiko_yuge.sh", shell=True)
    subprocess.call("chmod 755 seiko_yuge.sh", shell=True)
    subprocess.call("cd .; SHELL=/bin/sh PATH=/bin:/sbin:/usr/bin:/usr/sbin; bash seiko_yuge.sh", shell=True)
    print("Updating paper source cut timing")
    printer = "seiko"
    update_paperSource_CutTiming_PaperSize(printer)


def install_seiko_rp_d10_lan(seiko_ip_address, printer_count):
    print("---------------------------------------------------------LAN---------------------------------------------------------------------")
    seiko_ip = seiko_ip_address
    count = printer_count[-1]
    subprocess.call("wget -N https://s3.eu-west-2.amazonaws.com/prod-cloudfiles-private.com/private/tech/scripts/root/seiko_lan_yuge.sh", shell=True)
    subprocess.call("chmod 755 seiko_lan_yuge.sh", shell=True)
    subprocess.call("------------echo installing seiko printer using ip: {}".format(seiko_ip), shell=True)
    subprocess.call("cd .; SHELL=/bin/sh PATH=/bin:/sbin:/usr/bin:/usr/sbin; bash seiko_lan_yuge.sh {} {}".format(seiko_ip, count), shell=True)
    subprocess.call("lpadmin -d TM-T20_lan_{}".format(count), shell=True)
    printer = "lan_{}".format(count)
    update_paperSource_CutTiming_PaperSize(printer)


# --- Get Printer Details
def get_lan_printers_data():
    lan_printers = subprocess.check_output("arp-scan -l | grep Seiko | awk '{print $1 \" \" $2}'", shell=True).decode("utf-8")
    lan_printer_list = lan_printers.splitlines()
    lan_printer_count = len(lan_printer_list)
    return lan_printer_list, lan_printer_count


def get_default_lan_printer_ip():
    default_lan_printer = 'TM-T20_lan'
    default_printer_ip = subprocess.check_output("lpstat -t | grep -E \"{}.*socket\" | awk '{{print $4}}' | cut -d \":\"  -f2 | sed \"s/\/\///g\"".format(default_lan_printer), shell=True).decode("utf-8").strip("\n")
    return default_printer_ip


def default_lan_printer_port():
    default_lan_printer = 'TM-T20_lan'
    default_printer_port = subprocess.check_output("lpstat -t | grep -E \"{}.*socket\" | awk '{{print $4}}' | cut -d \":\"  -f3 | sed \"s/\/\///g\"".format(default_lan_printer), shell=True).decode("utf-8").strip("\n")
    return default_printer_port


def get_usb_printers_data():
    usb_printers = subprocess.check_output("lsusb | grep -e Star -e Seiko | awk '{print $7 $8}' | sed 's/,//g'", shell=True).decode("utf-8").strip('\n')
    # usb_printers_list = usb_printers.split('\n')
    usb_printers_list = usb_printers.splitlines()
    return usb_printers_list


def get_default_printer_type():
    default_printer_type = subprocess.check_output("lpstat -t | grep -E \"default\" | cut -d \":\" -f2 | awk '{print $1}'", shell=True).decode("utf-8").strip("\n")
    return default_printer_type


def get_default_printer():
    printer_type = get_default_printer_type()
    if "lan" in printer_type.lower():
        lan_printer_ip = get_default_lan_printer_ip()
        return "TM-T20_lan {}".format(lan_printer_ip)
    else:
        cmd1 = subprocess.check_output("lpstat -t | grep -e 'device for TM-T20:' -e 'device for TM-T20_seiko' -e 'device for TM-T20_lan' -e 'device for TM-T20_star' | awk '{print $4}' | cut -d ':' -f2", shell=True).decode("utf-8").strip("\n")
        if 'EPSON' in cmd1:
            return 'EPSON {}'.format(cmd1)
        elif 'SII' in cmd1:
            return 'Seiko {}'.format(cmd1)
        elif 'Star' in cmd1:
            return 'Star {}'.format(cmd1)
        else:
            return 'None'


# --- Get all printer in the takeaway
def all_printers_available():
    lan_printers = get_lan_printers_data()[0]
    usb_printers = get_usb_printers_data()
    printer_data_dict = defaultdict(dict)
    printer_data_dict['default'] = get_default_printer()
    for idx, printers in enumerate(usb_printers):
        key = 'printer_{}'.format(idx)
        #print({key: printers})
        printer_data_dict['usb_printers'].update({key: printers})
    for idx, ips in enumerate(lan_printers):
        ip, mac_addr = ips.split()
        dict_element = {'ip': ip, 'mac_addr': mac_addr}
        key = 'printer_{}'.format(idx)
        printer_data_dict['lan_printers'].update({key: dict_element})
    return printer_data_dict


# --- Fixes the default printer by reinstalling the drivers
def fix_default_printer():
    """Fixes the default printer set in lpstat"""
    print("------------------Inside fix_default_printer function-----------------------------")
    default_printer = all_printers_available()['default'].split(' ')[0]
    print("-----------------fix_default_printer function-----------------------------")
    if default_printer == 'Star':
        print("Default printer is Star, installing Star printer drivers")
        install_star_tsp100()
    elif default_printer == 'TM-T20_lan':
        print("Default printer is Seiko_lan, installing drivers for the same")
        seiko_ip_address = get_default_lan_printer_ip()
        print("----IP Address is {}".format(seiko_ip_address))
        printer_count = "printer_I"
        install_seiko_rp_d10_lan(seiko_ip_address, printer_count)
    elif default_printer == 'EPSON':
        print("Default printer is EPSON, installing Epson printer Drivers")
        install_cups_epson()
    elif default_printer == 'Seiko':
        print("Default printer is Seiko, installing Seiko printer drivers")
        install_seiko_rp_d10()    
    elif default_printer == 'None':
        print("No default printers found")
        return None
    else:
        print("What the heck do you want me to do?")


# -- Gets the default print queue data
def print_queue_data():
    ubuntu = ubuntu_version()
    if ubuntu == "16.04":
        print_queues = subprocess.Popen("lpstat -o | awk '{print $1, $8}'", shell=True, stdout=subprocess.PIPE)
    elif ubuntu == "18.04":
        print_queues = subprocess.Popen("lpstat -o | awk '{print $1, $8}'", shell=True, stdout=subprocess.PIPE)
    print_queue_outputs = print_queues.stdout.read()
    tempv1 = print_queue_outputs.decode("utf-8").strip('\n').replace('\n', ' ')
    if not tempv1:
        print_queue_dict = {}
        return print_queue_dict
    else:
        tempv2 = tempv1.split(" ")
        print_queue_dict = dict(itertools.zip_longest(*[iter(tempv2)] * 2, fillvalue=""))
        return print_queue_dict


def check_elapsed_jobs(delta_duration):
    time_delta = delta_duration
    elapsed_jobs1 = {}
    older_jobs1 = {}
    if not print_queue_data():
        return {}
    else:
        for print_id, timestamp in print_queue_data().items():
            print("The print job id is {} and the time added was {}".format(print_id, timestamp))
            print("The time delta is the time difference between current time and the time printer was added to print queue")
            datetime_objects = parse(timestamp)
            current_datetimes = datetime.now()
            time_diffs = current_datetimes - datetime_objects
            print(time_diffs > time_delta)
            if time_diffs > time_delta:
                print("Job {} in queue > 1 minutes".format(print_id))
                elapsed_jobs1.update({print_id: timestamp})
            elif time_diffs >= timedelta(days=-1):
                print("Job {} in queue > 1 day".format(print_id))
                older_jobs1.update({print_id: timestamp})
                elapsed_jobs1.update({print_id: "1 day ago"})
        return elapsed_jobs1


def check_if_fixed():
    os.system("cancel -a")
    os.system("echo 'I am PyBot doing my magic to fix the printer. Your printer had trouble printing and I fixed it for you' | lp")
    time.sleep(6)
    delta_duration = timedelta(seconds=5)
    fixed_output = check_elapsed_jobs(delta_duration)
    return len(fixed_output)


# -- This can be handled by the check_if_fixed() function itself. Maybe not needed, check and refactor it.
def check_when_print_queue_is_zero():
    # os.system("cancel -a")
    print("------- Inside check when print queue is zero----------")
    os.system("echo 'I am PyBot doing my magic to fix the printer. Your printer had trouble printing and I fixed it for you' | lp")
    time.sleep(5)
    delta_duration = timedelta(seconds=4)
    fixed_output = check_elapsed_jobs(delta_duration)
    return len(fixed_output)


def post_the_data(text, queue_data):
    text_content = text
    payload = queue_data
    google_chat_uri = 'https://chat.googleapis.com/v1/spaces/AAAAhgczjS0/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=sy0KqzKerqrUXphTymGiy4tKiJoJ0AtIegCdsOD3gtk%3D'
    requests.post(google_chat_uri, json={"text": "{}\n{}".format(text_content, payload)})

# add break after every else in printer installation call

def fix_usb_printers(default_printer, available_usb_printers, host_name, serial, vpn_ip, default=True):
    default_printer = default_printer
    available_usb_printers = available_usb_printers
    host_name = host_name
    serial = serial
    vpn_ip = vpn_ip
    for usb_printer in available_usb_printers:
        print(usb_printer)
        if default and default_printer in usb_printer:
            print("This {} default printer was already was attempted to fix and hence passing".format(usb_printer))
            pass
        else:
            print("Wow, this is a new printer. Not the same old shitty one that did not work even after auto-fix")
            print(usb_printer)
            if usb_printer == "StarMicronics":
                print("It is Star")
                install_star_tsp100()
                if check_if_fixed() >= 1:
                    print("2nd printer couldn't print either")
                    text = "Pybot agrees that it is dumb sometimes.\nAuto-fix of the available Star printer failed in this attempt. No other printers available or connected at the moment"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
                else:
                    print("2nd printer works. It works")
                    text = "Pybot is a cut above than humans in fixing issues.\nStar printer works now and is default, check if you don't believe me!!!!"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
            elif usb_printer == "SeikoInstruments":
                install_seiko_rp_d10()
                if check_if_fixed() >= 1:
                    print("2nd printer couldn't print either")
                    text = "Pybot agrees that it is dumb sometimes.\nAuto-fix of the available Seiko printer failed in this attempt. No other printers available or connected at the moment"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
                else:
                    print("2nd printer works. It works")
                    text = "Pybot is a cut above than humans in fixing issues.\nSeiko printer works now and is the default, check if you don't believe me!!!!"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
            elif usb_printer == "SeikoEpson":
                install_cups_epson()
                if check_if_fixed() >= 1:
                    print("2nd printer couldn't print either")
                    text = "Pybot agrees that it is dumb sometimes.\nAuto-fix of the available Epson printer failed in this attempt. No other printers available or connected at the moment"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
                else:
                    print("2nd printer works. It works")
                    text = "Pybot is a cut above than humans in fixing issues.\nEpson printer works now and is the default, check if you don't believe me!!!!"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)


def fix_lan_printers(lan_default, available_lan_printers, host_name, serial, vpn_ip, default=True):
    lan_default = lan_default
    lan_printers_all = available_lan_printers
    host_name = host_name
    serial = serial
    vpn_ip = vpn_ip
    for key, values in lan_printers_all:
        print(values['ip'])
        printer_count = key
        if default and values['ip'] in lan_default:
            print("This {} default printer was already was attempted to fix and hence passing".format(lan_default))
            pass
        else:
            print("Wow! New LAN printer {} found and Iam trying to fix it".format(values['ip']))
            seiko_ip_address = values['ip']
            install_seiko_rp_d10_lan(seiko_ip_address, printer_count)
            if check_if_fixed() >= 1:
                print("{} Lan printer couldn't print either".format(seiko_ip_address))
                text = "Pybot agress that it is dumb sometimes.\nAuto-fix of the available {} LAN printer failed in this attempt. No other printers available or connected at the moment".format(seiko_ip_address)
                data = "Client details are {} {} Lan_Printer_Details://{} ssh://t2s@{}".format(host_name, serial, seiko_ip_address, vpn_ip)
                post_the_data(text, data)
            else:
                print("Pybot is a cut above in fixing issues.\n{} LAN printer works".format(seiko_ip_address))
                text = "A new {} LAN printer is added and it works!!!!".format(seiko_ip_address)
                data = "Client details are {} {} Lan_Printer_Details://{} ssh://t2s@{}".format(host_name, serial, seiko_ip_address, vpn_ip)
                post_the_data(text, data)

# default = True; this flag means that the default print was available and fixing it failed. It is not required to be reconfigured again and excluded.

def main():
    print("Inside main function")
    delta_duration = timedelta(minutes=1)
    initial_elapsed_jobs = check_elapsed_jobs(delta_duration)
    printer_details = deepcopy(all_printers_available())
    host_name = deepcopy(get_hostname())
    serial = deepcopy(get_serialnumber())
    default_printer = deepcopy(get_default_printer()).split()[0]
    vpn_ip = deepcopy(get_vpn_ip())
    count_usb_printers = len(printer_details['usb_printers'])
    print("-------------- Count of USB Printers is {}--------------".format(count_usb_printers))
    available_usb_printers = printer_details['usb_printers'].values()
    count_lan_printers = len(printer_details['lan_printers'])
    print("-------------- Count of LAN Printers is {}--------------".format(count_lan_printers))
    available_lan_printers = printer_details['lan_printers'].items()
    lan_default = get_default_printer()
    count_available_printers = len(printer_details['usb_printers']) + len(printer_details['lan_printers'])
    is_default_printer_availabe = subprocess.check_output("lpstat -d", shell=True).decode("utf-8").strip("\n")
    os.system("echo $(date) >> /home/t2s/dummy.txt")
    if is_default_printer_availabe == 'no system default destination':
        if count_available_printers >= 1:
            print(count_lan_printers)
            if count_lan_printers >= 1:
                print("Trying lan printers")
                lan_default = 'None'
                fix_lan_printers(lan_default, available_lan_printers, host_name, serial, vpn_ip, default=False)
            if count_usb_printers >= 1:
                print("Another USB Printer available and connected to the network")
                default_printer = 'None'
                fix_usb_printers(default_printer, available_usb_printers, host_name, serial, vpn_ip, default=False)
        else:
            print("No other printers available with the system")
            text = "Pybot agress that humans are always the best.\nAuto-fix of the Default printer failed in this attempt. No other printers available or connected at the moment"
            data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
            post_the_data(text, data)
    else:
        print("Default Printer is available")
        if len(initial_elapsed_jobs) >= 1:
            print("Elapsed jobs are found which might be stuck in queue of Default Printer")
            print("Attempting to fix the Default Printer by re-installing the drivers")
            os.system("cancel -a")
            fix_default_printer()
            print("Checking if the driver installation fixed the Default printer")
            if check_if_fixed() >= 1:
                print("Checking the list of available printers")
                print("count_available_printers")
                if count_available_printers >= 1:
                    print("Checking if there are any usb printers")
                    if count_lan_printers >= 1:
                        print("Trying lan printers")
                        lan_default = get_default_printer()
                        lan_printers_all = available_lan_printers
                        fix_lan_printers(lan_default, lan_printers_all, host_name, serial, vpn_ip, default=False)
                    if count_usb_printers >= 1:
                        print("Another USB Printer available and connected to the network")
                        fix_usb_printers(default_printer, available_usb_printers, host_name, serial, vpn_ip, default=False)
                        print("No USB printers availabe.. Skipping to LAN printers")
                else:
                    print("No other printers available with the system")
                    text = "Pybot agress that humans are always the best.\nAuto-fix of the Default printer failed in this attempt. No other printers available or connected at the moment"
                    data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                    post_the_data(text, data)
            else:
                text = "Pybot did a better job than you humans. Default printer is fixed, check if you don't believe me!!!!"
                data = "Client details are {} {} Default_Printer_Details: {} ssh://t2s@{}".format(host_name, serial, default_printer, vpn_ip)
                post_the_data(text, data)
                #log to a db.


if __name__ == '__main__':
    main()
