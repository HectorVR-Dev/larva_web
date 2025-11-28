#!/bin/bash

# Script de Inicialización de Registros GPIO para Jetson Orin Nano
# Configura el Pinmux para permitir control GPIO (Output)

echo "Iniciando configuracion de estados iniciales de GPIO..."

gpioset `gpiofind "PN.01"`=0 # Configura PN.01 (P15) como Output y lo pone en bajo (0V)

gpioset `gpiofind "PY.03"`=0 # Configura PY.03 (P18) como Output y lo pone en bajo (0V)

sudo i2cset -y 7 0x20 0x00 # Configura el estado inicial inicial del PCF8574 (0x20) como salida (0x00)

echo "Configuracion de registros GPIO finalizada."