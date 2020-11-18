For Algorithm Users
===================

Use an optimizer
----------------

.. code-block:: python

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Use the optimizer
    optimize = teeport.use_optimizer('isBiBX4Rv')

    optimize(evaluate)

Ship an evaluator
-----------------

.. code-block:: python

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Ship the problem
    teeport.run_evaluator(evaluate)
    # evaluator id: S6QV_KO-s

For Algorithm Developers
========================

Use an evaluator
----------------

.. code-block:: python

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Use the evaluator
    evaluate = teeport.use_evaluator('c4oiY1_oe')

    X = np.random.rand(30, 8)
    Y = evaluate(X)

Ship an optimizer
-----------------

.. code-block:: python
    :emphasize-lines: 7

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Ship the algorithm
    teeport.run_optimizer(optimize)
    # optimizer id: vRpl0gFr_

For Both
========

Use a processor
---------------

.. code-block:: python

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Use the processor
    process = teeport.use_processor('BLBaVJxOy')

    result = process(data)

Ship a processor
----------------

.. code-block:: python

    from teeport import Teeport

    # Connect to the platform
    teeport = Teeport('ws://localhost:8080/')

    # Ship the processor
    teeport.run_processor(process)
    # processor id: BLBaVJxOy
