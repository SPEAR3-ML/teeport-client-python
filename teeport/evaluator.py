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

class Evaluator:
    def __init__(self, uri, class_id=None, name=None, configs=None, private=False, local=True):
        self.uri = uri  # platform uri
        self.class_id = class_id  # problem id
        self.name = name  # evaluator name
        self.configs = configs  # evaluator configs
        self.private = private # if the evaluator is private (other clients can't use)
        self.local = local  # local or remote evaluator
        self.socket = None  # websocket client
        self.id = None  # websocket id
        self.task = None  # main async task
        self.evaluate= None  # evaluate function
        # callbacks
        self.connected_callback = None
        self.finished_callback = None
    
    def status(self, width=16):
        print(f'{"uri": <{width}}: {self.uri}')
        print(f'{"problem id": <{width}}: {self.class_id}')
        print(f'{"name": <{width}}: {self.name}')
        self.show_configs(f'{"configs": <{width}}: ')
        print(f'{"private": <{width}}: {self.private}')
        print(f'{"local": <{width}}: {self.local}')
        if self.socket:
            print(f'{"socket": <{width}}: connected')
        else:
            print(f'{"socket": <{width}}: not connected')
        if self.id:
            print(f'{"socket id": <{width}}: {self.id}')
        if self.evaluate:
            print(f'{"evaluate": <{width}}: set')
        else:
            print(f'{"evaluate": <{width}}: not set')
        if self.task:
            print(f'{"main task": <{width}}: running')
        else:
            print(f'{"main task": <{width}}: not running')
        
    @make_sync
    async def start(self):
        if self.socket:
            print('evaluator: already started')
            return
        if not self.evaluate:
            print('evaluator: please set the evaluate function before starting evaluator')
            return
        
        params = {
            'type': 'evaluator',
            'classId': self.class_id,
            'configs': dumps(self.configs),
            'private': self.private
        }
        if self.name:
            params['name'] = self.name
        query = f'?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}'
        self.socket = await websockets.connect(self.uri + query, max_size=WS_MSG_MAX_SIZE)
        self.run()
        
    def stop(self):
        if self.socket:
            asyncio.ensure_future(self.socket.close())
        else:
            print('evaluator: already stopped')
            
    def set_evaluate(self, evaluate):
        self.evaluate = make_async(evaluate)
    
    async def logic(self, msg):
        msg = loads(msg)
        if msg['type'] == 'hello':
            self.id = msg['id']
            
            if self.connected_callback:
                self.connected_callback()
            
            get_client = {
                'type': 'getClient',
                'id': self.id
            }
            await self.socket.send(dumps(get_client))
        elif msg['type'] == 'client':
            self.name = msg['client']['name']
        elif msg['type'] == 'evaluate':
            task_id = msg['taskId']
            try:
                configs = msg['configs']
            except:
                configs = self.configs
            X = msg['data']
            Y = await self.evaluate(np.array(X), configs)

            res = {
                'type': 'evaluated',
                'data': Y.tolist(),
                'taskId': task_id
            }
            await self.socket.send(dumps(res))
        else:
            print(msg)
    
    async def listen(self):
        async for msg in self.socket:
            await self.logic(msg)
    
    def run(self):
        if not self.evaluate:
            print('evaluator: please set the evaluate function before running evaluator')
            return
        if self.task:
            print('evaluator: already running')
            return
        if not self.socket:
            print('evaluator: please connect before running')
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
                self.socket = None
                self.id = None
                print('evaluator: disconnected, cleaned up')
                
                if self.finished_callback:
                    self.finished_callback()
            except websockets.exceptions.ConnectionClosedOK:
                self.socket = None
                self.id = None
                print('evaluator: stopped')
            except asyncio.CancelledError:
                print('evaluator: running cancelled, cleaned up')
            except:
                print('evaluator: bad things happened')
                print('-' * 60)
                traceback.print_exc(file=sys.stdout)
                print('-' * 60)
                
                if self.finished_callback:
                    self.finished_callback()
            else:  #  socket has been closed by user
                self.socket = None
                self.id = None
                print('evaluator: stopped')
                
        self.task = asyncio.ensure_future(self.listen())
        self.task.add_done_callback(done_callback)

    def show_configs(self, label=''):
        for i, line in enumerate(dumps(self.configs, indent=4).split('\n')):
            if not i:
                print(label + line)
            else:
                print(' ' * len(label) + line)
