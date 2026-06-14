#!/bin/bash
# Kadr Media Dashboard — ikki marta bosib ishga tushiring
cd "$(dirname "$0")"
clear
echo "  Kadr Media Dashboard ishga tushyapti..."
echo ""
# Brauzerni 2 soniyadan keyin avtomatik ochish
( sleep 2 && open "http://localhost:3000" ) &
python3 server.py
