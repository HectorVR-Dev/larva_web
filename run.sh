#!/bin/bash
deactivate 2>/dev/null
cd ./client || { echo "Error: No se pudo cambiar al directorio"; exit 1; }
./run.sh

sleep 2

cd ../jetson || { echo "Error: No se pudo cambiar al directorio"; exit 1; }
./run.sh

exit 0
```
