# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import asyncio
import inspect
import urllib.parse
from functools import wraps

def make_async(func):
    """Make a function async.

    Parameters
    ----------
    func : function
        The function to be made async.
        Can be a normal (sync) function or an async function

    Returns
    -------
    function
        The async version of the input `func`
        
    Notes
    -----
    A sync function is just a `normal` function, which will block
    the current thread when executing; While an async function is
    a promise, which is non-blocking.

    """
    if inspect.iscoroutinefunction(func):
        return func
    else:
        @wraps(func)
        async def func_a(*args, **kwargs):
            await asyncio.sleep(0)
            return func(*args, **kwargs)
        
        return func_a

def make_sync(func):
    """Make a function sync.

    Parameters
    ----------
    func : function
        The function to be made sync.
        Can be a normal (sync) function or an async function

    Returns
    -------
    function
        The sync version of the input `func`

    """
    if inspect.iscoroutinefunction(func):
        @wraps(func)
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

# Attempt to use quote_plus to work around the None value encoding issue
# https://stackoverflow.com/a/18648642/4263605
def params_2_querystring(params):
    keys = params.keys()  # do not preserve params order
    query = '?' + '&'.join([key + '=' + urllib.parse.quote_plus(str(params[key])) for key in keys])
    return query
