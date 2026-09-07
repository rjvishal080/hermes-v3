#!/usr/bin/env bash
pkill -f "python main.py" 2>/dev/null && echo "Backend stopped"
pkill -f "vite"           2>/dev/null && echo "Frontend stopped"
