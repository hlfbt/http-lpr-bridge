#!/usr/bin/env python3

import argparse
import os
import sys
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyprintlpr import LprClient

class HTTPToLPRHandler(BaseHTTPRequestHandler):
    def send_CORS_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Method', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Headers', 'Content-Length')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_response(400)
            self.send_CORS_headers()
            self.end_headers()
            self.wfile.write(b"Error: Empty request body")
            return

        body = self.rfile.read(content_length)
        sent_mode = None

        try:
            with LprClient(self.server.printer_ip, port=self.server.printer_port,
                           queue=self.server.printer_queue, timeout=float(os.environ.get('PRINTER_SOCKET_TIMEOUT', 5.0))) \
            as lpr:
                lpr.sent_via = "raw"
                lpr.__print_lpr = lpr._print_lpr
                lpr._print_lpr = lambda data, job_title = None: (lpr.__setattr__('sent_via', "lpr"), lpr.__print_lpr(data, job_title))
                if self.server.print_mode.lower() == "lpr":
                    lpr._print_lpr(body)
                elif self.server.print_mode.lower() == "raw":
                    if not lpr.sock:
                        raise RuntimeError("Not connected to printer")
                    lpr.sock.sendall(body)
                else:
                    lpr.send(body)
                sent_mode = lpr.sent_via

            logging.info(f"{content_length} bytes -({sent_mode})-> {self.server.printer_queue} @ {self.server.printer_ip}:{self.server.printer_port}")
            self.send_response(200)
            self.send_CORS_headers()
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Sent {content_length} bytes to {self.server.printer_queue} @ {self.server.printer_ip} via {sent_mode}".encode('utf-8'))

        except Exception as e:
            logging.exception(f"Failed to queue print job: {e}")
            self.send_response(500)
            self.send_CORS_headers()
            self.end_headers()
            self.wfile.write(f"LPR error: {str(e)}".encode('utf-8'))

def main():
    if os.environ.get('LOGLEVEL'):
        logging.basicConfig(level=os.environ.get('LOGLEVEL').upper())

    parser = argparse.ArgumentParser(description="HTTP POST to LPR printer proxy daemon")

    def boolthy(val, default=False):
        if val is None:
            return None
        val = str(val).strip().upper()
        if val == "1" or val == "TRUE" or val == "YES" or val == "ON":
            return True
        elif val == "" or val == "0" or val == "FALSE" or val == "NO" or val == "OFF":
            return False
        else:
            return default

    parser.add_argument('--http-port', '-p', type=int, default=int(os.environ.get('HTTP_PORT', 9100)),
        help='Port this HTTP proxy server listens on (Default: 9100 or HTTP_PORT env)')
    parser.add_argument('--http-ip', '-l', type=str, default=os.environ.get('HTTP_IP', '0.0.0.0'),
        help='IP interface this HTTP proxy binds to (Default: 0.0.0.0 or HTTP_IP env)')
    env_printer_host = os.environ.get('PRINTER_HOST')
    parser.add_argument('--printer-host', '-H', type=str, default=env_printer_host, required=not env_printer_host,
        help='Target IP address or hostname of the LPR printer (Required or PRINTER_HOST env)')
    parser.add_argument('--printer-queue', '-P', type=str, default=os.environ.get('PRINTER_QUEUE', 'lp'),
        help='Target LPR queue directory identifier name (Default: lp or PRINTER_QUEUE env)')
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument('--force-raw', action='store_true',
        help='Send the body as-is without wrapping it in a LPR protocol compliant print job. Default when the printer port is not 515.')
    format_group.add_argument('--force-lpr', action='store_true',
        help='Force usage of the LPR protocol. Default when the printer port is 515. Takes precedence when both PRINTER_FORCE_RAW and PRINTER_FORCE_LPR env vars are specified.')

    if boolthy(os.environ.get('PRINTER_FORCE_RAW')):
        sys.argv.append('--force-raw')
    if boolthy(os.environ.get('PRINTER_FORCE_LPR')):
        sys.argv.append('--force-lpr')

    args = parser.parse_args()

    server_address = (args.http_ip, args.http_port)
    httpd = HTTPServer(server_address, HTTPToLPRHandler)

    httpd.printer_ip, httpd.printer_port = (args.printer_host.split(':') + [515])[:2]
    httpd.printer_port = int(httpd.printer_port)
    httpd.printer_queue = args.printer_queue
    httpd.print_mode = "lpr" if args.force_lpr else ("raw" if args.force_raw else "auto")

    logging.info(f"Starting proxy on http://{args.http_ip}:{args.http_port}")
    logging.info(f"Targeting LPR Printer at {httpd.printer_ip}:{httpd.printer_port} (queue {httpd.printer_queue})")
    if args.force_lpr or args.force_raw:
        logging.info(f"Forcing {"LPR" if args.force_lpr else "RAW"} mode")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("\nShutting down proxy server gracefully")
        httpd.server_close()
        sys.exit(0)

if __name__ == '__main__':
    main()
