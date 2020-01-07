#!/bin/bash
64_update () {
wget tech.touch2success.com/64.zip
unzip 64.zip
cd 64
sudo python3 stage		
exit 1
}

bit=$(uname -i)



If [ $bit == "x86_64" ]; 
then
        echo "alredy os is 64bit"
        exit 1
else
        echo "upgrade needed"
        64_update
