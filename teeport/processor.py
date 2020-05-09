# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import websockets
import numpy as np
from json import dumps, loads
import urllib.parse
import sys
import traceback

from opt.utils.helpers import make_async, make_sync
from .constants import WS_MSG_MAX_SIZE

class Processor:
    def __init__(self, uri, name=None, local=True):
        self.uri = uri  # platform uri
        self.name = name  # processor name
        self.local = local  # local or remote processor
        self.socket = None  # websocket client
        self.id = None  # websocket id
        self.task = None  # main async task
        self.process = None  # process function
        
    def status(self, width=16):
        print(f'{"uri": <{width}}: {self.uri}')
        print(f'{"name": <{width}}: {self.name}')
        print(f'{"local": <{width}}: {self.local}')
        if self.socket:
            print(f'{"socket": <{width}}: connected')
        else:
            print(f'{"socket": <{width}}: not connected')
        if self.id:
            print(f'{"socket id": <{width}}: {self.id}')
        if self.process:
            print(f'{"process": <{width}}: set')
        else:
            print(f'{"process": <{width}}: not set')
        if self.task:
            print(f'{"main task": <{width}}: running')
        else:
            print(f'{"main task": <{width}}: not running')
        
    @make_sync
    async def start(self):
        if self.socket:
            print('processor: already connected')
            return
        if not self.process:
            print('processor: please set the process function before starting processor')
            return
        
        params = {'type': 'processor'}
        if self.name:
            params['name'] = self.name
        query = f'?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}'
        self.socket = await websockets.connect(self.uri + query, max_size=WS_MSG_MAX_SIZE)
        self.run()
        
    def stop(self):
        if self.socket:
            asyncio.ensure_future(self.socket.close())
        else:
            print('processor: already stopped')
            
    def set_process(self, process):
        self.process = make_async(process)
    
    async def logic(self, msg):
        msg = loads(msg)
        if msg['type'] == 'hello':
            self.id = msg['id']
            
            get_client = {
                'type': 'getClient',
                'id': self.id
            }
            await self.socket.send(dumps(get_client))
        elif msg['type'] == 'client':
            self.name = msg['client']['name']
        elif msg['type'] == 'process':
            commander_id = msg['commanderId']
            X = msg['data']
            P = await self.process(X)

            res = {
                'type': 'processed',
                'data': P,
                'commanderId': commander_id
            }
            await self.socket.send(dumps(res))
        else:
            print(msg)
    
    async def listen(self):
        async for msg in self.socket:
            await self.logic(msg)
    
    def run(self):
        if not self.process:
            print('processor: please set the process function before running processor')
            return
        if self.task:
            print('processor: already running')
            return
        if not self.socket:
            print('processor: please connect before running')
            return
        
        def done_callback(future):
            self.task = None
            
            # close the socket
            if self.socket and not self.socket.closed:
                make_sync(self.socket.close)()
                self.socket = None
                self.id = None
                
            try:
                res = future.result()
            except websockets.exceptions.ConnectionClosedError:
                self.id = None
                self.socket = None
                print('processor: disconnected, cleaned up')
            except asyncio.CancelledError:
                print('processor: running cancelled, cleaned up')
            except:
                print('processor: bad things happened')
                print('-' * 60)
                traceback.print_exc(file=sys.stdout)
                print('-' * 60)
            else:  #  socket has been closed by user
                self.socket = None
                self.id = None
                print('processor: stopped')
                
        self.task = asyncio.ensure_future(self.listen())
        self.task.add_done_callback(done_callback)
