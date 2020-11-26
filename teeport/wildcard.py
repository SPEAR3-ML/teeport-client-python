# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import websockets
import numpy as np
from json import dumps, loads
import urllib.parse
import sys
import traceback

from .utils import make_async, make_sync
from .constants import WS_MSG_MAX_SIZE

class Wildcard:
    def __init__(self, uri, name=None):
        self.uri = uri  # platform uri
        self.name = name  # wildcard name
        self.socket = None  # websocket client
        self.id = None  # websocket id
        self.task = None  # main async task
        self.task_id = None  # the opt task id
        self.sub_task = None  # sub async task
    
    def status(self, width=16):
        print(f'{"uri": <{width}}: {self.uri}')
        print(f'{"name": <{width}}: {self.name}')
        if self.socket:
            print(f'{"socket": <{width}}: connected')
        else:
            print(f'{"socket": <{width}}: not connected')
        if self.id:
            print(f'{"socket id": <{width}}: {self.id}')
        if self.task:
            print(f'{"main task": <{width}}: running')
        else:
            print(f'{"main task": <{width}}: not running')
        if self.task_id:
            print(f'{"task id": <{width}}: {self.task_id}')
        if self.sub_task:
            print(f'{"sub task": <{width}}: running')
        else:
            print(f'{"sub task": <{width}}: not running')
        
    @make_sync
    async def start(self):
        if self.socket:
            print('wildcard: already connected')
            return
        
        params = {'type': 'wildcard'}
        if self.name:
            params['name'] = self.name
        query = f'?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}'
        self.socket = await websockets.connect(self.uri + query, max_size=WS_MSG_MAX_SIZE)
        self.run()
        
    def stop(self):
        if self.socket:
            asyncio.ensure_future(self.socket.close())
        else:
            print('wildcard: already stopped')
        
        # Reset the task id
        self.task_id = None
    
    async def wait_for_reply(self, task_name):
        self.sub_task = asyncio.get_event_loop().create_future()
        self.sub_task.name = task_name
        r = await self.sub_task
        self.sub_task = None
        return r
    
    @make_sync
    async def check_client(self, client_id):
        get_client = {
            'type': 'getClient',
            'id': client_id
        }
        await self.socket.send(dumps(get_client))
        client = await self.wait_for_reply(f'check_client:{client_id}')
        return client
    
    @make_sync
    async def init_task(self, optimizer_id, evaluator_id, configs=None):
        new_task = {
            'type': 'newTask',
            'optimizerId': optimizer_id,
            'evaluatorId': evaluator_id,
            'configs': configs
        }
        await self.socket.send(dumps(new_task))
        task_id = await self.wait_for_reply('new_task')
        self.task_id = task_id
        
#         observe_task = {
#             'type': 'observeTask',
#             'id': task_id
#         }
#         await self.socket.send(dumps(observe_task))
        
        start_task = {
            'type': 'startTask',
            'id': task_id
        }
        await self.socket.send(dumps(start_task))

    @make_sync
    async def get_tasks(self):
        get_tasks = {
            'type': 'getTasks'
        }
        await self.socket.send(dumps(get_tasks))
        tasks = await self.wait_for_reply('get_tasks')
        return tasks

    @make_sync
    async def delete_task(self, task_id):
        delete_task = {
            'type': 'deleteTask',
            'id': task_id
        }
        await self.socket.send(dumps(delete_task))
        
    @make_sync
    async def stop_task(self):
        stop_task = {
            'type': 'stopTask',
            'id': self.task_id
        }
        await self.socket.send(dumps(stop_task))
    
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
            client = msg['client']
            if self.sub_task and not self.sub_task.done():
                if self.sub_task.name == f'check_client:{client["id"]}':
                    self.sub_task.set_result(client)
            if self.id == client['id']:
                self.name = client['name']
        elif msg['type'] == 'taskCreated':
            task_id = msg['id']
            if self.sub_task and not self.sub_task.done():
                if self.sub_task.name == 'new_task':
                    self.sub_task.set_result(task_id)
        elif msg['type'] == 'tasks':
            tasks = msg['tasks']
            if self.sub_task and not self.sub_task.done():
                if self.sub_task.name == 'get_tasks':
                    self.sub_task.set_result(tasks)
        elif msg['type'] == 'startTask':
            print('wildcard: optimization started')
        elif msg['type'] == 'pauseTask':
            print('wildcard: optimization paused')
        elif msg['type'] == 'stopTask':
            print('wildcard: optimization cancelled')
        elif msg['type'] == 'completeTask':
            print('wildcard: optimization completed')
        else:
            print(msg)
    
    async def listen(self):
        async for msg in self.socket:
            await self.logic(msg)
    
    def run(self):
        if self.task:
            print('evaluator: already running')
            return
        if not self.socket:
            print('wildcard: please connect before running')
            return
        
        def done_callback(future):
            self.task = None
            
            # clean up the sub task
            if self.sub_task:
                self.sub_task.cancel()
                
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
                print('wildcard: disconnected, cleaned up')
            except asyncio.CancelledError:
                # print('wildcard: running cancelled, cleaned up')
                pass
            except:
                print('wildcard: bad things happened')
                print('-' * 60)
                traceback.print_exc(file=sys.stdout)
                print('-' * 60)
            else:  #  socket has been closed by user
                self.socket = None
                self.id = None
                # print('wildcard: stopped')
                
        self.task = asyncio.ensure_future(self.listen())
        self.task.add_done_callback(done_callback)
