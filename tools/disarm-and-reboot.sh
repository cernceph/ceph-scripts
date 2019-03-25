#!/bin/bash

echo -n Disabling NC Alarms...
roger update --nc_alarmed false --duration 15min `hostname -s`
echo done.
echo Rebooting in 5 seconds \(ctrl-c to cancel\)...
sleep 5
reboot
