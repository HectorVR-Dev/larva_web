#!/bin/bash

# Script de Inicialización de Registros GPIO para Jetson Orin Nano
# Configura el Pinmux para permitir control GPIO (Output)

echo "Iniciando configuracion de registros GPIO..."

# Pin 7 - Addr: 0x2448030 - Val: 0xA
busybox devmem 0x2448030 w 0xA

# Pin 11 - Addr: 0x2430098 - Val: 0x5
busybox devmem 0x2430098 w 0x5

# Pin 13 - Addr: 0x243D030 - Val: 0x1005
busybox devmem 0x243D030 w 0x1005

# Pin 15 - Addr: 0x2440020 - Val: 0x5
busybox devmem 0x2440020 w 0x5

# Pin 19 - Addr: 0x243D040 - Val: 0x5
busybox devmem 0x243D040 w 0x5

# Pin 21 - Addr: 0x243D018 - Val: 0x5
busybox devmem 0x243D018 w 0x5

# Pin 23 - Addr: 0x243D028 - Val: 0x1005
busybox devmem 0x243D028 w 0x1005

# Pin 29 - Addr: 0x2430068 - Val: 0x8
busybox devmem 0x2430068 w 0x8

# Pin 12 - Addr: 0x2434088 - Val: 0x1006
busybox devmem 0x2434088 w 0x1006

# Pin 16 - Addr: 0x243D020 - Val: 0x5
busybox devmem 0x243D020 w 0x5

# Pin 18 - Addr: 0x243D010 - Val: 0x5
busybox devmem 0x243D010 w 0x5

# Pin 22 - Addr: 0x243D000 - Val: 0x5
busybox devmem 0x243D000 w 0x5

# Pin 24 - Addr: 0x243D008 - Val: 0x9
busybox devmem 0x243D008 w 0x9

# Pin 26 - Addr: 0x243D038 - Val: 0x9
busybox devmem 0x243D038 w 0x9

# Pin 32 - Addr: 0x2434080 - Val: 0x5
busybox devmem 0x2434080 w 0x5

# Pin 36 - Addr: 0x2430090 - Val: 0x5
busybox devmem 0x2430090 w 0x5

echo "Configuracion de registros GPIO finalizada."