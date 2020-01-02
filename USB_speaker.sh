#!/bin/bash

#read -p 'User name :' useName
#read -sp 'Password :' passW
#echo 
#read -p 'Host :' hostName


#sshpass -p $passW ssh $useName@$hostName

pactl list short sinks

usb_speaker=$(pactl list short sinks | grep alsa* | awk '{print $2}')

pactl set-default-sink $usb_speaker


su t2s



echo 'set-default-sink 0'  |  sudo tee -a /etc/pulse/default.pa
echo 'set-default-source 0'  |  sudo tee -a /etc/pulse/default.pa



~                                                                                                                                                                                                           
~                                                                                                                                                                                                           
~                                                                                                                                                                                                           
~                                                                  
