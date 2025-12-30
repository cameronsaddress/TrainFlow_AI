#!/bin/bash
# Run modules sequentially
for i in {2..24}
do
   echo "--------------------------------------"
   echo "STARTING MODULE $i"
   echo "--------------------------------------"
   docker exec trainflow-backend python3 /app/tools/generate_module_raw.py --module-index $i
   if [ $? -ne 0 ]; then
       echo "Module $i Failed!"
       exit 1
   fi
   echo "Module $i Complete."
   sleep 2
done
