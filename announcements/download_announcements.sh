#!/bin/bash

newFileDir=data/$(date +%F)
mkdir -p $newFileDir
dateWithTime=$(date +'%d.%m.%y-%H-%M-%S')
newFilePath="${newFileDir}/${foo}ann${dateWithTime}.json" 
wget https://files.cloudgdansk.pl/d/otwarte-dane/ztm/bsk.json -O $newFilePath