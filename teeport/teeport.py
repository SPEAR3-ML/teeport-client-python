# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import inspect
import websockets
import numpy as np
from json import dumps, loads
from anytree import NodeMixin, RenderTree

from .utils import make_async, make_sync

from .optimizer import Optimizer
from .evaluator import Evaluator
from .processor import Processor
from .wildcard import Wildcard

class Teeport(NodeMixin):
    """The Teeport node class.

    Teeport node that connects to the Teeport backend service. Using Teeport
    node, one can use/ship an evaluator/optimizer/processor.
    Note that by design, one Teeport node can only hold one evaluator and
    one optimizer. The number of processors is unlimited, though.

    Parameters
    ----------
    uri : str
        The uri of the Teeport backend service.
        Usually looks like `ws://xxx.xxx.xxx.xxx:8080` or
        `wss://some.domain/io`
    name : str, optional
        Name of this Teeport node.
        If not specified, will be assigned a random two-word name
        at the time of initialization
    parent : object, optional
        The parent of this node.
        Use this to build a Teeport node network
    children : list of object, optional
        The children of this node.
        Use this to build a Teeport node network
    
    """
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
        """Connect to the backend service.

        By default, a newly created Teeport node doesn't automatically
        connect to the Teeport backend service. To connect manually, call
        this method.

        """
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
        """Disconnect from the backend service.

        Manually disconnect the possible websockets that connected to the
        Teeport backend service from this Teeport node.

        """
        if self.wildcard:
            if self.wildcard.task:
                self.wildcard.stop()
                self.wildcard = None
            else:
                print('teeport: already unlinked')
        else:
            print('teeport: not linked yet')
    
    def is_busy(self):
        """Check if there is an optimization task going on in this node.

        Returns
        -------
        bool
            True if there is a task going on, False otherwise.

        """
        return bool(self.wildcard and self.wildcard.task)
    
    def status(self, width=16):
        """Print out the status of this Teeport node.

        Get most of the important information of the current node.
        Including the information of the optimizer, the evaluator
        and the processors. Also display the node topology.

        Parameters
        ----------
        width : int
            The width of the property column in the printed form.

        """
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
        
    def run_optimizer(self, optimize, class_id=None, name=None, configs=None, private=False, auto_start=True,
                      connected_callback=None, started_callback=None, finished_callback=None):
        """Ship an optimization algorithm to the Teeport backend service.

        When ship an algorithm with this API, a local optimizer will be
        created in this Teeport node, and put into a standby mode. Whenever
        it receives a `start task` signal, one round of optimization will begin.

        Parameters
        ----------
        optimize : function
            The optimization algorithm to be shipped to Teeport.
        class_id : str, optional
            The id of the optimization algorithm.
            Usually something like `NSGA-II`, `PSO`, `EGO`, `RCDS`, etc.
            Note that `class_id` should be treated as the only identifier for
            the algorithm, so algorithms with the same `class_id` would be
            treated as identical algorithms.
            Even though this argument is optional, it's highly encouraged to
            provide a `class_id` for each shipped algorithm.
        name : str, optional
            The name of the optimization algorithm.
            Different from the `class_id`, the same class of algorithm can
            have different names. If set to `None`, which is the default
            value, the optimizer will be given a random two-word name by
            the time of shipping.
        configs : dict, optional
            The initial configurations for the `optimize` function.
            `configs` should agree with the one from the arguments of the
            `optimize` function.
        private : bool, optional
            If run the optimizer as private.
            If True, the optimizer's socket id will be concealed, so that no
            one else can use it by referring to the socket id.
        auto_start : bool, optional
            If activate the optimizer when shipping.
            If False, the optimizer won't be running even it's already
            connected to the Teeport service.
        connected_callback, started_callback, finished_callback : function, optional
            These are the hooks that get called at different stages of
            the optimizer. When the optimizer is connected to the Teeport
            service, the `connected_callback` function will be called;
            When the optimizer is started (activated),
            the `started_callback` function will be called;
            When the optimization is finished (the optimizer will be put
            to a standby mode),
            the `finished_callback` function will be called.

        Returns
        -------
        bool
            True if successful, False otherwise.

        """
        if self.optimizer:
            if self.optimizer.task:
                print('teeport: please stop the current optimizer first')
                return
        
        optimizer = Optimizer(self.uri, class_id, name, configs, private)
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
        """Ship an optimization problem to the Teeport backend service.

        When ship a problem with this API, a local evaluator will be
        created in this Teeport node, and put into a standby mode. Whenever
        it receives a `evaluate` signal, it will evaluate the `X` data
        in the websocket data package and return the evaluated `Y`.

        Parameters
        ----------
        evaluate : function
            The optimization problem to be shipped to Teeport.
        class_id : str, optional
            The id of the optimization problem.
            Usually something like `Rosenbrock`, `ZDT1`, `DTLZ2`, `DA`, etc.
            Note that `class_id` should be treated as the only identifier for
            the problem.
            It's highly encouraged to provide a `class_id`
            for each shipped problem.
        name : str, optional
            The name of the optimization problem.
        configs : dict, optional
            The initial configurations for the `evaluate` function.
            `configs` should agree with the one from the arguments of the
            `evaluate` function.
        private : bool, optional
            If run the evaluator as private.
            If True, the evaluator's socket id will be concealed.
        auto_start : bool, optional
            If activate the evaluator when shipping.
            If False, the evaluator won't be running even it's
            connected to the Teeport service.
        connected_callback, finished_callback : function, optional
            These are the hooks that get called at different stages of
            the evaluator. When the evaluator is connected to the Teeport
            service, the `connected_callback` function will be called;
            The `finished_callback` function will be called
            when the optimization is finished.

        Returns
        -------
        bool
            True if successful, False otherwise.

        See Also
        --------
        run_optimizer : Ship an optimizer to Teeport

        """
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
    async def use_optimizer(self, optimize=None, class_id=None, name=None, configs=None):
        """Use an optimization algorithm from the Teeport backend service.

        Use a remote optimization algorithm by providing its socket id, or
        use a local optimization algorithm to monitor the optimization
        process.

        Parameters
        ----------
        optimize : str or function
            The optimization algorithm to be used.
            Feed in a string to use the optimizer with the socket id
            of `optimize` on Teeport; Feed in a local function to monitor
            the optimization process.
        class_id : str, optional
            The id of the optimization algorithm. Only useful when the
            `optimize` argument is a function.
        name : str, optional
            The name of the optimization algorithm. Only useful when the
            `optimize` argument is a function.
        configs : dict, optional
            The configurations of the optimization algorithm to be used
            for the following optimization tasks. If set to None,
            the algorithm will use its default/initial configurations.

        Returns
        -------
        function
            A wrapped function if the argument `optimize` is a function;
            A newly created local optimize function otherwise. Either way,
            the returned function is a local normal (sync) function with the
            signature::

                optimize(evaluate)

            Where `evaluate` has the signature::

                Y = evaluate(X)

        """
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
                configs_init = configs or client['configs']
                optimizer = Optimizer(self.uri, client['classId'], client['name'], configs_init, local=False)
                optimizer.id = client['id']
                self.optimizer = optimizer
                optimize_w = self._get_optimize_remote(optimizer.id, configs_init)
                self.optimizer.optimize = optimize_w
                return optimize_w
        else:
            return self._get_optimize_local(optimize, class_id, name, configs)
    
    def use_evaluator(self, evaluate=None, class_id=None, name=None, configs=None):
        """Use an optimization problem from the Teeport backend service.

        Use a remote optimization problem by providing its socket id, or
        use a local optimization problem to monitor the optimization
        process.

        Parameters
        ----------
        evaluate : str or function
            The optimization problem to be used.
            Feed in a string to use the evaluator with the socket id
            of `evaluate` on Teeport; Feed in a local evaluation function
            to monitor the optimization process.
        class_id : str, optional
            The id of the optimization problem. Only useful when the
            `evaluate` argument is a function.
        name : str, optional
            The name of the optimization problem. Only useful when the
            `evaluate` argument is a function.
        configs : dict, optional
            The configurations of the optimization problem to be used
            for the following optimization tasks. If set to None,
            the problem will use its default/initial configurations.

        Returns
        -------
        function
            A wrapped function if the argument `evaluate` is a function;
            A newly created local evaluate function otherwise. Either way,
            the returned function is a local normal (sync) function with the
            signature::

                Y = evaluate(X)
        
        See Also
        --------
        use_optimizer :
            Use a remote optimization algorithm
            or monitor the local optimization process
        
        """
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
                # use configs passed from use_evaluator if possible
                configs_init = configs or client['configs']
                evaluator = Evaluator(self.uri, client['classId'], client['name'], configs_init, local=False)
                evaluator.id = client['id']
                self.evaluator = evaluator
                evaluate_w = self._get_evaluate_remote(evaluator.id, configs_init)
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
            
    def _init_optimizer_private(self, optimize, class_id=None, name=None, configs=None):
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

        success = self.run_optimizer(optimize, class_id=class_id, name=name, configs=configs,
                                     private=True, auto_start=False,
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
            # stop the private evaluator
            self.evaluator.stop()
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
    def _get_evaluate_remote(self, evaluator_id, configs):
        # configs is a needed argument
        # so be sure to get it in advance in the caller method

        # closure trick
        cache = {
            'count': 0,  # called number
            'opt_task': None,  # get X in optimize
            'eval_task': None  # get Y in evaluate
        }
        configs_init = configs

        @make_sync
        async def evaluate_w(X):
            if cache['eval_task'] and not cache['eval_task'].done():
                cache['eval_task'].cancel()
                print('teeport: something goes wrong on evaluation')
                return

            cache['eval_task'] = asyncio.get_event_loop().create_future()

            if cache['count'] == 0:  # first time run evaluate
                # create the manual optimizer
                # the manual optimizer does not respect the configs
                async def optimize(func, configs=None):
                    while True:
                        if not cache['opt_task']:  # first loop
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            Y = func(X)
                            cache['eval_task'].set_result(Y)
                        else:
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            _X = await cache['opt_task']  # avoid the late-bind issue of X in the closure
                            Y = func(_X)
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

                configs_all = {
                    'evaluator': configs_init
                }
                self.link()
                self.wildcard.init_task(optimizer_id, evaluator_id, configs_all)
            else:
                if cache['opt_task'] and not cache['opt_task'].done():
                    cache['opt_task'].set_result(X)
                else:
                    print('teeport: something goes wrong on optimization')
                    return

            Y = await cache['eval_task']
            cache['count'] = cache['count'] + 1
            return Y
        return evaluate_w
    
    def _get_evaluate_local(self, evaluate, class_id, name, configs):
        eval_connected = self._init_evaluator_private(evaluate, class_id, name, configs)
        
        # closure trick
        cache = {
            'count': 0,  # called number
            'opt_task': None,  # get X in optimize
            'eval_task': None  # get Y in evaluate
        }
        configs_init = configs

        @make_sync
        async def evaluate_w(X):
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
                async def optimize(func, configs=None):
                    while True:
                        if not cache['opt_task']:  # first loop
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            Y = func(X)
                            cache['eval_task'].set_result(Y)
                        else:
                            cache['opt_task'] = asyncio.get_event_loop().create_future()
                            _X = await cache['opt_task']
                            Y = func(_X)
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

                configs_all = {
                    'evaluator': configs_init
                }
                self.link()
                self.wildcard.init_task(optimizer_id, evaluator_id, configs_all)
            else:
                if cache['opt_task'] and not cache['opt_task'].done():
                    cache['opt_task'].set_result(X)
                else:
                    print('teeport: something goes wrong on optimization')
                    return

            Y = await cache['eval_task']
            cache['count'] = cache['count'] + 1
            return Y
        return evaluate_w
    
    def _get_optimize_remote(self, optimizer_id, configs):
        configs_init = configs

        @make_sync
        async def optimize_w(evaluate, configs=None):  # configs here is the init task configs
            # check if a task is running
            if self.is_busy():
                print('teeport: an optimization task is currently running, cannot start a new one')
                return
            if self.evaluator and self.evaluator.task:
                print('teeport: an evaluation task is currently running, cannot start a new one')
                return

            # normalize the configs
            configs_all = {}
            try:
                configs_evaluator = configs['evaluator']
            except:
                configs_evaluator = None
            try:
                configs_task = configs['task']
            except:
                configs_task = None
            try:
                configs_optimizer = configs['optimizer'] or configs_init
            except:
                configs_optimizer = configs_init
            configs_all['optimizer'] = configs_optimizer  # should be removed?
            configs_all['evaluator'] = configs_evaluator
            configs_all['task'] = configs_task

            # run a private evaluator
            eval_connected = self._init_evaluator_private(evaluate, None, configs=configs_evaluator)
            if not eval_connected:
                print('teeport: initialize private evaluator failed')
                return
            self.evaluator.start()
            await eval_connected
            evaluator_id = self.evaluator.id

            # create and start the task
            self.link()
            self.wildcard.init_task(optimizer_id, evaluator_id, configs_all)
            await self.wildcard.task
        return optimize_w
    
    def _get_optimize_local(self, optimize, class_id, name, configs):
        # init a private optimizer
        opt_connected = self._init_optimizer_private(optimize, class_id, name, configs)
        if not opt_connected:  # returned none, should be a coro
            print('teeport: initialize private optimizer failed')
            return
        configs_init = configs

        @make_sync
        async def optimize_w(evaluate, configs=None):
            # check if a task is running
            if self.is_busy():
                print('teeport: an optimization task is currently running, cannot start a new one')
                return
            if self.evaluator and self.evaluator.task:
                print('teeport: an evaluation task is currently running, cannot start a new one')
                return

            # start the private optimizer
            if opt_connected.done():
                _opt_connected = self._init_optimizer_private(optimize, class_id, name, configs_init)
                if not _opt_connected:  # returned none, should be a coro
                    print('teeport: initialize private optimizer failed')
                    return
            else:
                _opt_connected = opt_connected
            self.optimizer.start()
            await _opt_connected
            optimizer_id = self.optimizer.id

            # normalize the configs
            configs_all = {}
            try:
                configs_evaluator = configs['evaluator']
            except:
                configs_evaluator = None
            try:
                configs_task = configs['task']
            except:
                configs_task = None
            try:
                configs_optimizer = configs['optimizer']
            except:
                configs_optimizer = configs_init
            configs_all['optimizer'] = configs_optimizer
            configs_all['evaluator'] = configs_evaluator
            configs_all['task'] = configs_task

            # run a private evaluator
            eval_connected = self._init_evaluator_private(evaluate, None, configs=configs_evaluator)
            if not eval_connected:
                self.optimize.stop()
                print('teeport: initialize private evaluator failed')
                return
            self.evaluator.start()
            await eval_connected
            evaluator_id = self.evaluator.id

            # create and start the task
            self.link()
            self.wildcard.init_task(optimizer_id, evaluator_id, configs_all)
            await self.wildcard.task
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
