# Copyright (c) 2019-2020, SPEAR3 authors (see AUTHORS.txt).
# Licensed under the BSD 3-clause license (see LICENSE.txt)

# The reason we need nest_asyncio is that we run multiple event loops in a
# single thread, that's not allowed. The future work should be create a new
# thread for each event loop so we can get rid of nest_asyncio
import nest_asyncio
nest_asyncio.apply()

from .teeport import Teeport
