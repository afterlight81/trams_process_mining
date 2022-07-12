#!/bin/bash

echo "trip,stopId,stopName,timestamp,delay,variant,status" > departures.csv
echo "id,code,service,usedInTrip,brand,model,productionYear,floorHeight,passengersDoors" > vehicles.csv

for i in */*departures*.csv;do cat $i | tail -n +2 >> departures.csv;done
for i in */*vehicles*.csv;do cat $i | tail -n +2 >> vehicles.csv;done