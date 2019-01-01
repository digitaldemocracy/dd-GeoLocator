#!/usr/bin/env python
import os
import sys

from app import create_app

def run(port=9000):
    app = create_app()
    app.run(host='0.0.0.0',port=port)
    app.config['SERVER_PORT']=port

if __name__ == '__main__':
    port = 9000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run(port)

