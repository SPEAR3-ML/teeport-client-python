# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import inspect
import websockets
import numpy as np
from json import dumps, loads
from anytree import NodeMixin, RenderTree

from opt.utils.helpers import make_async, make_sync

from .optimizer import Optimizer
from .evaluator import Evaluator
from .processor import Processor
from .wildcard import Wildcard

class Teeport(NodeMixin):
    def __init__(self, uri, name=None, parent=None, children=None):
        self.uri = uri
        self.optimizer = None
        self.evaluator = None
        self.processors = []
        # hidden figure, this guy is the freeman of the teeport
        self.wildcard = None
        # tree related
        self.spawn_count = 0
        if name:
            self.name = name
        else:
            if parent:
                self.name = f'{parent.name}_{parent.spawn_count}'
            else:
                self.name = 't0'
        self.parent = parent
        if children:
            self.children = children
    
    def link(self):
        if self.wildcard:
            if self.wildcard.task:
                print('teeport: already linked')
                return
            else:
                self.wildcard.start()
        else:
            self.wildcard = Wildcard(self.uri)
            self.wildcard.start()
            
    def unlink(self):
        if self.wildcard:
            if self.wildcard.task:
                self.wildcard.stop()
                self.wildcard = None
            else:
                print('teeport: already unlinked')
        else:
            print('teeport: not linked yet')
    
    def is_busy(self):
        return bool(self.wildcard and self.wildcard.task)
    
    def status(self, width=16):
        print('General\n' + '=' * 80)
        print(f'{"uri": <{width}}: {self.uri}')
        print(f'{"name": <{width}}: {self.name}')
        self.show_topology(f'{"topology": <{width}}: ')
        if self.wildcard:
            print('\nWildcard\n' + '=' * 80)
            self.wildcard.status()
        if self.optimizer:
            print('\nOptimizer\n' + '=' * 80)
            self.optimizer.status()
        if self.evaluator:
            print('\nEvaluator\n' + '=' * 80)
            self.evaluator.status()
        if self.processors:
            print('\nProcessors\n' + '=' * 80)
        for i, processor in enumerate(self.processors):
            if i:
                print('\n')
            print(f'Processor {i + 1}')
            processor.status()
        
    def run_optimizer(self, optimize, name=None, private=False, auto_start=True,
                      connected_callback=None, started_callback=None, finished_callback=None):
        if self.optimizer:
            if self.optimizer.task:
                print('teeport: please stop the current optimizer first')
                return
        
        optimizer = Optimizer(self.uri, name, private)
        optimizer.set_optimize(optimize)
        optimizer.connected_callback = connected_callback
        optimizer.started_callback = started_callback
        optimizer.finished_callback = finished_callback
        if auto_start:
            optimizer.start()
        self.optimizer = optimizer
        return True
        
    def run_evaluator(self, evaluate, class_id=None, name=None, configs=None, private=False, auto_start=True,
                      connected_callback=None, finished_callback=None):
        if self.evaluator:
            if self.evaluator.task:
                print('teeport: please stop the current evaluator first')
                return
        
        evaluator = Evaluator(self.uri, class_id, name, configs, private)
        evaluator.set_evaluate(evaluate)
        evaluator.connected_callback = connected_callback
        evaluator.finished_callback = finished_callback
        if auto_start:
            evaluator.start()
        self.evaluator = evaluator
        return True
        
    def run_processor(self, process, name=None):
        processor = Processor(self.uri, name)
        processor.set_process(process)
        processor.start()
        self.processors.append(processor)
        return True
        
    @make_sync
    async def use_optimizer(self, optimize=None, name=None):
        if self.optimizer:
            if self.optimizer.task:
                print('teeport: please stop the current optimizer first')
                return
        
        if optimize is None:
            pass
        elif type(optimize) == str:
            # do this link/unlink thing so that users don't need to care about it
            if self.is_busy():
                client = self.wildcard.check_client(optimize)
            else:
                self.link()
                client = self.wildcard.check_client(optimize)
                self.unlink()
                
            try:
                client_type = client['type']
            except:
                print(f'teeport: optimizer {optimize} does not exist')
                return None
            else:
                if client_type != 'optimizer':
                    print(f'teeport: client {optimizer} is not an optimizer')
                    return None
                
                # init an optimizer, this one will not run
                optimizer = Optimizer(self.uri, client['name'], local=False)
                optimizer.id = client['id']
                self.optimizer = optimizer
                optimize_w = self._get_optimize_remote(optimizer.id)
                self.optimizer.optimize = optimize_w
                return optimize_w
        else:
            return self._get_optimize_local(optimize)
    
    def use_evaluator(self, evaluate=None, class_id=None, name=None, configs=None):
        if self.evaluator:
            if self.evaluator.task:
                print('teeport: please stop the current evaluator first')
                return
        
        if evaluate is None:
            return
        elif type(evaluate) == str:
            # do this link/unlink thing so that users don't need to care about it
            if self.is_busy():
                client = self.wildcard.check_client(evaluate)
            else:
                self.link()
                client = self.wildcard.check_client(evaluate)
                self.unlink()
            try:
                client_type = client['type']
            except:
                print(f'teeport: evaluator {evaluate} does not exist')
                return None
            else:
                if client_type != 'evaluator':
                    print(f'teeport: client {evaluate} is not an evaluator')
                    return None
                
                # init an evaluator, this one will not run
                evaluator = Evaluator(self.uri, client['classId'], client['name'], client['configs'], local=False)
                evaluator.id = client['id']
                self.evaluator = evaluator
                evaluate_w = self._get_evaluate_remote(evaluator.id, client['configs'])
                self.evaluator.evaluate = evaluate_w
                return evaluate_w
        else:
            return self._get_evaluate_local(evaluate, class_id, name, configs)
    
    def use_processor(self, process=None, name=None):
        if process is None:
            pass
        elif type(process) == str:
            pass
        else:
            pass
            
    def _init_optimizer_private(self, optimize):
        connected = asyncio.get_event_loop().create_future()
        
        def connected_callback():
            connected.set_result(True)

        def finished_callback():
            # unlink the wildcard
            self.unlink()
            # stop the private evaluator
            if self.evaluator:
                if self.evaluator.private:
                    self.evaluator.stop()
            # stop the optimizer
            if self.optimizer:
                self.optimizer.stop()

        success = self.run_optimizer(optimize, private=True, auto_start=False,
                                     connected_callback=connected_callback,
                                     finished_callback=finished_callback)
        if not success:
            return
        return connected
    
    def _init_evaluator_private(self, evaluate, class_id=None, name=None, configs=None):
        connected = asyncio.get_event_loop().create_future()
        
        def connected_callback():
            connected.set_result(True)

        # only triggered when not manually called stop()
        def finished_callback():
            # unlink the wildcard
            self.unlink()
            # stop the optimizer
            if self.optimizer:
                self.optimizer.stop()

        success = self.run_evaluator(evaluate, class_id=class_id, name=name, configs=configs,
                                     private=True, auto_start=False,
                                     connected_callback=connected_callback,
                                     finished_callback=finished_callback)
        if not success:
            return
        return connected
    
    # this method will only be called when there is a remote evaluator registered
    # but the evaluator is not running
    def _get_evaluate_remote(self, evaluator_id, configs=None):
        # closure trick
        cache = {
            'count': 0,  # called number
            'opt_task': None,  # get X in optimize
            'eval_task': None  # get Y in evaluate
        }
        configs_default = configs
        @make_sync
        async def evaluate_w(X, configs=None):
            if cache['eval_task'] and not cache['eval_task'].done():
                cache['eval_task'].cancel()
                print('teeport: something goes wrong on evaluation')
                return

            cache['eval_task'] = asyncio.get_event_loop().create_future()

            if cache['count'] == 0:  # first time run evaluate
                # create the manual optimizer
                async def optimize(func):
                    while True:
                        if not cache['opt_task']:  # first loop
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            Y = func(X, configs or configs_default)
                            cache['eval_task'].set_result(Y)
                        else:
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            _X, _configs = await cache['opt_task']
                            Y = func(_X, _configs or configs_default)
                            cache['eval_task'].set_result(Y)

                # run optimizer and get the socket id
                connected = asyncio.get_event_loop().create_future()
                def connected_callback():
                    connected.set_result(True)

                def finished_callback():
                    # unlink the wildcard
                    self.unlink()
                    # stop the optimizer
                    if self.optimizer:
                        self.optimizer.stop()
                    # cancel the tasks in cache
                    if cache['opt_task'] and not cache['opt_task'].done():
                        cache['opt_task'].cancel()
                    if cache['eval_task'] and not cache['eval_task'].done():
                        cache['eval_task'].cancel()

                success = self.run_optimizer(optimize, private=True,
                                             connected_callback=connected_callback,
                                             finished_callback=finished_callback)
                if not success:
                    return

                await connected
                optimizer_id = self.optimizer.id

                self.link()
                self.wildcard.init_task(optimizer_id, evaluator_id)
            else:
                if cache['opt_task'] and not cache['opt_task'].done():
                    cache['opt_task'].set_result([X, configs])
                else:
                    print('teeport: something goes wrong on optimization')
                    return

            Y = await cache['eval_task']
            cache['count'] = cache['count'] + 1
            return Y
        return evaluate_w
    
    def _get_evaluate_local(self, evaluate, class_id=None, name=None, configs=None):
        eval_connected = self._init_evaluator_private(evaluate, class_id, name, configs)
        
        # closure trick
        cache = {
            'count': 0,  # called number
            'opt_task': None,  # get X in optimize
            'eval_task': None  # get Y in evaluate
        }
        configs_default = configs
        @make_sync
        async def evaluate_w(X, configs=None):
            if cache['eval_task'] and not cache['eval_task'].done():
                cache['eval_task'].cancel()
                print('teeport: something goes wrong on evaluation')
                return

            cache['eval_task'] = asyncio.get_event_loop().create_future()

            if cache['count'] == 0:  # first time run evaluate
                # run the private evaluator
                self.evaluator.start()
                await eval_connected
                evaluator_id = self.evaluator.id
                
                # create the manual optimize function
                async def optimize(func):
                    while True:
                        if not cache['opt_task']:  # first loop
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            Y = func(X, configs or configs_default)
                            cache['eval_task'].set_result(Y)
                        else:
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            _X, _configs = await cache['opt_task']
                            Y = func(_X, _configs or configs_default)
                            cache['eval_task'].set_result(Y)

                # run the private optimizer
                opt_connected = asyncio.get_event_loop().create_future()
                def connected_callback():
                    opt_connected.set_result(True)

                def finished_callback():
                    # unlink the wildcard
                    self.unlink()
                    # stop the optimizer
                    if self.optimizer:
                        self.optimizer.stop()
                    if self.evaluator:
                        self.evaluator.stop()
                    # cancel the tasks in cache
                    if cache['opt_task'] and not cache['opt_task'].done():
                        cache['opt_task'].cancel()
                    if cache['eval_task'] and not cache['eval_task'].done():
                        cache['eval_task'].cancel()

                success = self.run_optimizer(optimize, private=True,
                                             connected_callback=connected_callback,
                                             finished_callback=finished_callback)
                if not success:
                    return

                await opt_connected
                optimizer_id = self.optimizer.id

                self.link()
                self.wildcard.init_task(optimizer_id, evaluator_id)
            else:
                if cache['opt_task'] and not cache['opt_task'].done():
                    cache['opt_task'].set_result([X, configs])
                else:
                    print('teeport: something goes wrong on optimization')
                    return

            Y = await cache['eval_task']
            cache['count'] = cache['count'] + 1
            return Y
        return evaluate_w
    
    def _get_optimize_remote(self, optimizer_id):
        @make_sync
        async def optimize_w(evaluate, task_name=None):
            # check if a task is running
            if self.is_busy():
                print('teeport: an optimization task is currently running, cannot start a new one')
                return
            if self.evaluator and self.evaluator.task:
                print('teeport: an evaluation task is currently running, cannot start a new one')
                return

            # run a private evaluator
            eval_connected = self._init_evaluator_private(evaluate)
            if not eval_connected:
                print('teeport: initialize private evaluator failed')
                return
            self.evaluator.start()
            await eval_connected
            evaluator_id = self.evaluator.id

            # create and start the task
            self.link()
            self.wildcard.init_task(optimizer_id, evaluator_id, task_name)
        return optimize_w
    
    def _get_optimize_local(self, optimize):
        # init a private optimizer
        opt_connected = self._init_optimizer_private(optimize)
        if not opt_connected:  # returned none, should be a coro
            print('teeport: initialize private optimizer failed')
            return

        @make_sync
        async def optimize_w(evaluate, task_name=None):
            # check if a task is running
            if self.is_busy():
                print('teeport: an optimization task is currently running, cannot start a new one')
                return
            if self.evaluator and self.evaluator.task:
                print('teeport: an evaluation task is currently running, cannot start a new one')
                return

            # start the private optimizer
            if opt_connected.done():
                _opt_connected = self._init_optimizer_private(optimize)
                if not _opt_connected:  # returned none, should be a coro
                    print('teeport: initialize private optimizer failed')
                    return
            else:
                _opt_connected = opt_connected
            self.optimizer.start()
            await _opt_connected
            optimizer_id = self.optimizer.id

            # run a private evaluator
            eval_connected = self._init_evaluator_private(evaluate)
            if not eval_connected:
                self.optimize.stop()
                print('teeport: initialize private evaluator failed')
                return
            self.evaluator.start()
            await eval_connected
            evaluator_id = self.evaluator.id

            # create and start the task
            self.link()
            self.wildcard.init_task(optimizer_id, evaluator_id, task_name)
        return optimize_w
        
    def stop(self, recursive=True):
        if recursive:
            for child in self.children:
                child.stop(recursive)
            
        self.unlink()
        
        if self.optimizer:
            self.optimizer.stop()
        if self.evaluator:
            self.evaluator.stop()
        for processor in self.processors:
            processor.stop()
    
    def reset(self, recursive=True):
        if recursive:
            for child in self.children:
                child.reset(recursive)
            
        self.stop(False)
        self.optimizer = None
        self.evaluator = None
        self.processors = []
        
        self.spawn_count = 0
        self.children = ()
            
    def spawn(self, name=None):
        sub_tee = Teeport(self.uri, name, parent=self)
        self.spawn_count += 1
        return sub_tee
    
    def show_topology(self, label=''):
        for i, [pre, _, node] in enumerate(RenderTree(self)):
            treestr = f'{pre}{node.name}'
            if not i:
                print(label + treestr.ljust(8))
            else:
                print(' ' * len(label) + treestr.ljust(8))
