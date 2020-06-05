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

class Optimizer:
    def __init__(self, uri, name=None, private=False, local=True):
        self.uri = uri  # platform uri
        self.name = name  # optimizer name
        self.private = private # if the optimizer is private (other clients can't use)
        self.local = local  # local or remote optimizer
        self.socket = None  # websocket client
        self.id = None  # websocket id
        self.task = None  # main async task
        self.optimize = None  # optimize function
        self.opt_task_info = None  # optimization task info
        self.opt_task = None  # optimization async task
        self.eval_task = None  # evaluation async task
        # callbacks
        self.connected_callback = None
        self.started_callback = None
        self.finished_callback = None
    
    def status(self, width=16):
        print(f'{"uri": <{width}}: {self.uri}')
        print(f'{"name": <{width}}: {self.name}')
        print(f'{"private": <{width}}: {self.private}')
        print(f'{"local": <{width}}: {self.local}')
        if self.socket:
            print(f'{"socket": <{width}}: connected')
        else:
            print(f'{"socket": <{width}}: not connected')
        if self.id:
            print(f'{"socket id": <{width}}: {self.id}')
        if self.optimize:
            print(f'{"optimize": <{width}}: set')
        else:
            print(f'{"optimize": <{width}}: not set')
        if self.task:
            print(f'{"main task": <{width}}: running')
        else:
            print(f'{"main task": <{width}}: not running')
        if self.opt_task:
            print(f'{"opt task": <{width}}: running')
        else:
            print(f'{"opt task": <{width}}: not running')
        if self.opt_task_info:
            print(f'{"opt task info": <{width}}: {self.opt_task_info}')
        if self.eval_task:
            print(f'{"eval task": <{width}}: running')
        else:
            print(f'{"eval task": <{width}}: not running')
        
    @make_sync
    async def start(self):
        if self.socket:
            print('optimizer: already started')
            return
        if not self.optimize:
            print('optimizer: please set the optimize function before starting optimizer')
            return
        
        params = {
            'type': 'optimizer',
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
            print('optimizer: already stopped')
            
    def _cancel_opt_task(self):
        # has to cancel eval task first, since we warpped the async evaluate to be
        # a sync function, and opt task must wait for this sync function, once the
        # evaluate does not return anymore, you can't really cancel the opt task due
        # to the lack of the 'await' point in optimize. The only way out is throw an
        # exception inside the wrapped evaluate, this will terminate the sync optimize
        # function and cancel the opt task
        if self.eval_task and not self.eval_task.done():
            self.eval_task.cancel()
        elif self.opt_task and not self.opt_task.done():
            self.opt_task.cancel()
            
    def cancel_optimize(self):
        if self.opt_task:
            self._cancel_opt_task()
        else:
            print('optimizer: no optimization task running')
        
    def set_optimize(self, optimize):
        if self.optimize:
            print('optimizer: remove the current optimize function first')
            return
        
        self.optimize = make_async(optimize)
    
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
        elif msg['type'] == 'taskCreated':
            optimizer_id = msg['optimizerId']
            evaluator_id = msg['evaluatorId']
            task_id = msg['id']
            if optimizer_id != self.id:
                print('optimizer: wrong number, please check the server logic')
                return
            
            opt_task_info = {
                'evaluator_id': evaluator_id,
                'task_id': task_id,
            }
            self.opt_task_info = opt_task_info
        elif msg['type'] == 'startTask':
            # create the evaluate function
            @make_sync
            async def evaluate(X, configs=None):
                point = {
                    'type': 'evaluate',
                    'data': X.tolist(),
                    'configs': configs
                }
                await self.socket.send(dumps(point))
                
                # run eval task
                self.eval_task = asyncio.get_event_loop().create_future()
                Y = await self.eval_task
                self.eval_task = None
                return Y
            
            # run opt task
            def done_callback(future):
                # save for later
                task_id = self.opt_task_info['task_id']

                # clean up the sub task
                if self.eval_task:
                    self.eval_task.cancel()
                    self.eval_task = None
                    
                # clean up the opt task
                self.opt_task = None
                self.opt_task_info = None
                
                try:
                    res = future.result()
                except asyncio.CancelledError:
                    print('optimizer: optimization cancelled')
                    
                    # notify the platform to cancel the task
                    if self.socket and not self.socket.closed:
                        stop_task = {
                            'type': 'stopTask',
                            'id': task_id
                        }
                        make_sync(self.socket.send)(dumps(stop_task))
                except:
                    # notify the platform to cancel the task
                    if self.socket and not self.socket.closed:
                        stop_task = {
                            'type': 'stopTask',
                            'id': task_id
                        }
                        make_sync(self.socket.send)(dumps(stop_task))
                    print('-' * 60)
                    traceback.print_exc(file=sys.stdout)
                    print('-' * 60)
                else:
                    print('optimizer: optimization finished')
                    
                    # notify the platform to complete the task
                    if self.socket and not self.socket.closed:
                        complete_task = {
                            'type': 'completeTask',
                            'id': task_id
                        }
                        make_sync(self.socket.send)(dumps(complete_task))
                        
                if self.finished_callback:
                    self.finished_callback()
                        
            self.opt_task = asyncio.ensure_future(self.optimize(evaluate))
            self.opt_task.add_done_callback(done_callback)
            
            if self.started_callback:
                self.started_callback()
                
        elif msg['type'] == 'evaluated':
            if self.eval_task and not self.eval_task.done():
                Y = np.array(msg['data'])
                self.eval_task.set_result(Y)
        elif msg['type'] == 'stopTask':
            self._cancel_opt_task()
        else:
            print(msg)
    
    async def listen(self):
        async for msg in self.socket:
            await self.logic(msg)
    
    # run message queue
    def run(self):
        if not self.optimize:
            print('optimizer: please set the optimize function before running optimizer')
            return
        if self.task:
            print('optimizer: already running')
            return
        if not self.socket:
            print('optimizer: please connect before running')
            return
        
        def done_callback(future):
            self.task = None
            
            # clean up the opt task
            if self.opt_task:
                self._cancel_opt_task()
            
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
                print('optimizer: disconnected, cleaned up')
            except asyncio.CancelledError:
                print('optimizer: running cancelled, cleaned up')
            except:
                print('optimizer: bad things happened')
                print('-' * 60)
                traceback.print_exc(file=sys.stdout)
                print('-' * 60)
            else:  #  socket has been closed by user
                self.socket = None
                self.id = None
                print('optimizer: stopped')
                
        self.task = asyncio.ensure_future(self.listen())
        self.task.add_done_callback(done_callback)
