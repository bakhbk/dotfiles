#!/bin/bash

echo "--- Starting Network Settings Reset ---"

# 1. Fix: Use quoted variables and specific off flags
services=$(networksetup -listallnetworkservices | tail -n +2)

while read -r service; do
    # Remove disabled marker (*)
    name=$(echo "$service" | sed 's/^\*//')
    echo "Resetting: $name"
    
    # Use sudo once for the whole block to avoid spamming
    sudo networksetup -setwebproxystate "$name" off 2>/dev/null
    sudo networksetup -setsecurewebproxystate "$name" off 2>/dev/null
    sudo networksetup -setsocksfirewallproxystate "$name" off 2>/dev/null
    
    # Fix for the "Invalid parameters" error: disable instead of setting empty URL
    sudo networksetup -setautoproxystate "$name" off 2>/dev/null
done <<< "$services"

# 2. Recreating Location (Solid method)
echo "Recreating Network Location..."
sudo networksetup -createlocation TempLoc populate > /dev/null
sudo networksetup -switchtolocation TempLoc
sudo networksetup -deletelocation Automatic 2>/dev/null
sudo networksetup -createlocation Automatic populate > /dev/null
sudo networksetup -switchtolocation Automatic
sudo networksetup -deletelocation TempLoc 2>/dev/null

# 3. DNS & DHCP
echo "Flushing DNS and renewing DHCP..."
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
sudo ipconfig set en0 DHCP 2>/dev/null

echo "Done. If 'Outline' still exists, remove it manually in Settings -> VPN."
