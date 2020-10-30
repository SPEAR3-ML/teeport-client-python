# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import inspect

def make_async(func):
    if inspect.iscoroutinefunction(func):
        return func
    else:
        async def func_a(*args, **kwargs):
            await asyncio.sleep(0)
            return func(*args, **kwargs)
        
        return func_a

def make_sync(func):
    if inspect.iscoroutinefunction(func):
        def func_d(*args, **kwargs):
            try:
                res = asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
            return res
        
        return func_d
    else:
        return func
