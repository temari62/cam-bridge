#!/usr/bin/env bash
# Generate a self-signed TLS certificate for the CamBridge relay.
# Run this ON THE VPS. Pass the VPS public IP so clients can verify it.
#
#   ./gen_cert.sh 203.0.113.10
#
# Produces relay-cert.pem (give a copy to each PC as the "Cert file") and
# relay-key.pem (keep on the VPS only). Valid for 10 years.
set -e
IP="${1:?Usage: ./gen_cert.sh <VPS_PUBLIC_IP or domain>}"

# Use IP: SAN if it looks like an IPv4 address, otherwise DNS:
if [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then SAN="IP:$IP"; else SAN="DNS:$IP"; fi

openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout relay-key.pem -out relay-cert.pem \
  -subj "/CN=$IP" -addext "subjectAltName=$SAN"

echo
echo "Created relay-cert.pem and relay-key.pem"
echo "  * Start the relay:   python3 relay.py --tls --certfile relay-cert.pem --keyfile relay-key.pem"
echo "  * Copy relay-cert.pem to each PC and set it as the GUI 'Cert file' (or --cafile)."
